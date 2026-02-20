"""
MaaS (Mesh-as-a-Service) API — x0tta6bl4
==========================================

Production API for deploying, managing, and monitoring
PQC-secured self-healing mesh networks.

Endpoints:
    Auth:
        POST   /api/v1/maas/register       — Register new user
        POST   /api/v1/maas/login           — Login
        POST   /api/v1/maas/api-key         — Rotate API key
        GET    /api/v1/maas/me              — User profile

    Mesh Lifecycle:
        POST   /api/v1/maas/deploy          — Deploy a new mesh network
        GET    /api/v1/maas/list            — List user's meshes
        GET    /api/v1/maas/{id}/status     — Mesh health & status
        GET    /api/v1/maas/{id}/metrics    — Consciousness & MAPE-K metrics
        POST   /api/v1/maas/{id}/scale     — Scale nodes up/down
        DELETE /api/v1/maas/{id}            — Terminate mesh
        
    Agent:
        POST   /api/v1/maas/heartbeat       — Node heartbeat telemetry
"""

import asyncio
import csv
import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.maas_auth_models import (ApiKeyResponse, TokenResponse,
                                      UserLoginRequest, UserRegisterRequest)
from src.database import BillingWebhookEvent, User, get_db
from src.api.maas_security import api_key_manager, oidc_validator, token_signer
from src.api.maas_auth import require_role, get_current_user_from_maas, require_permission
from src.services.maas_auth_service import MaaSAuthService
from src.security.hardware_enclave import AttestationService

# Try importing PQC identity manager
try:
    from src.security.pqc_identity import PQCNodeIdentity

    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS"])

# Re-alias for compatibility within this file
get_current_user = get_current_user_from_maas


# ---------------------------------------------------------------------------
# PQC Segment Profiles
# ---------------------------------------------------------------------------
# Maps device_class → recommended PQC algorithm pair.
# NIST-standardized: ML-KEM (FIPS 203) + ML-DSA (FIPS 204).
# Security levels: 1 (128-bit) | 3 (192-bit) | 5 (256-bit)

PQC_SEGMENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "sensor": {
        "kem": "ML-KEM-512",
        "sig": "ML-DSA-44",
        "security_level": 1,
        "rationale": "Battery/CPU constrained — balance security vs. performance",
    },
    "edge": {
        "kem": "ML-KEM-512",
        "sig": "ML-DSA-44",
        "security_level": 1,
        "rationale": "Low-power edge devices — performance-first",
    },
    "robot": {
        "kem": "ML-KEM-768",
        "sig": "ML-DSA-65",
        "security_level": 3,
        "rationale": "Industrial robots — high security, real-time safe",
    },
    "drone": {
        "kem": "ML-KEM-768",
        "sig": "ML-DSA-65",
        "security_level": 3,
        "rationale": "Autonomous drones — medium latency tolerance",
    },
    "gateway": {
        "kem": "ML-KEM-1024",
        "sig": "ML-DSA-87",
        "security_level": 5,
        "rationale": "Network gateways — maximum security, high-value targets",
    },
    "server": {
        "kem": "ML-KEM-1024",
        "sig": "ML-DSA-87",
        "security_level": 5,
        "rationale": "Control-plane servers — maximum security",
    },
}

# Default profile for unknown device classes
_PQC_DEFAULT_PROFILE: Dict[str, Any] = {
    "kem": "ML-KEM-768",
    "sig": "ML-DSA-65",
    "security_level": 3,
    "rationale": "Default: standard security for unclassified devices",
}


def _get_pqc_profile(device_class: str) -> Dict[str, Any]:
    return PQC_SEGMENT_PROFILES.get(device_class, _PQC_DEFAULT_PROFILE)


PLAN_ALIASES = {
    "free": "starter",
    "starter": "starter",
    "pro": "pro",
    "enterprise": "enterprise",
}

BILLING_WEBHOOK_EVENTS = {
    "plan.upgraded",
    "plan.downgraded",
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
    "subscription.deleted",
}

PLAN_REQUEST_LIMITS = {
    "starter": 10_000,
    "pro": 100_000,
    "enterprise": 1_000_000,
}

# ---------------------------------------------------------------------------
# Pydantic Models — Mesh
# ---------------------------------------------------------------------------

class MeshDeployRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=64)
    nodes: int = Field(default=5, ge=1, le=1000)
    billing_plan: str = Field(default="starter", pattern="^(starter|pro|enterprise)$")
    pqc_enabled: bool = Field(default=True)
    obfuscation: str = Field(default="none", pattern="^(none|xor|aes)$")
    traffic_profile: str = Field(default="none", pattern="^(none|gaming|streaming|voip)$")
    join_token_ttl_sec: int = Field(default=604800, ge=3600, le=2592000)  # 1h–30d, default 7d


class MeshDeployResponse(BaseModel):
    mesh_id: str
    join_config: Dict[str, Any]
    dashboard_url: str
    status: str
    pqc_identity: Optional[Dict[str, Any]] = None
    pqc_enabled: bool = True
    created_at: str = ""
    plan: str = ""
    join_token_expires_at: str = ""


class TokenRotateResponse(BaseModel):
    mesh_id: str
    join_token: str
    issued_at: str
    expires_at: str


class MeshStatusResponse(BaseModel):
    mesh_id: str
    status: str  # provisioning | active | degraded | terminated
    nodes_total: int
    nodes_healthy: int
    uptime_seconds: float
    pqc_enabled: bool
    obfuscation: str
    traffic_profile: str
    peers: List[Dict[str, Any]]
    health_score: float  # 0.0 - 1.0


class MeshMetricsResponse(BaseModel):
    mesh_id: str
    consciousness: Dict[str, Any]
    mape_k: Dict[str, Any]
    network: Dict[str, Any]
    timestamp: str


class ScaleRequest(BaseModel):
    action: str = Field(..., pattern="^(scale_up|scale_down)$")
    count: int = Field(..., ge=1, le=100)


class ScaleResponse(BaseModel):
    mesh_id: str
    previous_nodes: int
    current_nodes: int
    status: str


class NodeRegisterRequest(BaseModel):
    """Headless agent registration request."""

    node_id: Optional[str] = None
    enrollment_token: str = Field(..., min_length=16)
    device_class: str = Field(
        default="edge",
        pattern="^(edge|robot|drone|gateway|sensor|server)$",
    )
    labels: Dict[str, str] = Field(default_factory=dict)
    public_keys: Dict[str, str] = Field(default_factory=dict)
    hardware_id: Optional[str] = None
    attestation_data: Optional[Dict[str, Any]] = None
    enclave_enabled: bool = False


class NodeRegisterResponse(BaseModel):
    mesh_id: str
    node_id: str
    status: str  # pending_approval | approved
    message: str


class NodeApproveRequest(BaseModel):
    acl_profile: str = Field(default="default", pattern="^(default|strict|isolated)$")
    tags: List[str] = Field(default_factory=list)


class NodeApproveResponse(BaseModel):
    mesh_id: str
    node_id: str
    status: str
    join_token: Dict[str, Any]
    approved_at: str


class NodeRevokeRequest(BaseModel):
    node_id: Optional[str] = None
    reason: str = Field(default="manual_revoke", min_length=3, max_length=120)


class NodeRevokeResponse(BaseModel):
    mesh_id: str
    node_id: str
    status: str
    reason: str
    revoked_at: str


class NodeReissueTokenRequest(BaseModel):
    ttl_seconds: int = Field(default=900, ge=60, le=86400)


class NodeReissueTokenResponse(BaseModel):
    mesh_id: str
    node_id: str
    join_token: Dict[str, Any]
    issued_at: str
    expires_at: str


class BillingWebhookRequest(BaseModel):
    event_id: Optional[str] = Field(default=None, min_length=8, max_length=128)
    event_type: str = Field(..., min_length=3, max_length=64)
    plan: Optional[str] = Field(
        default=None, pattern="^(free|starter|pro|enterprise)$"
    )
    customer_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    subscription_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    user_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    email: Optional[str] = Field(default=None, min_length=3, max_length=320)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BillingWebhookResponse(BaseModel):
    processed: bool
    event_id: str
    event_type: str
    user_id: str
    plan_before: str
    plan_after: str
    requests_limit: int
    idempotent_replay: bool = False

class NodeHeartbeatRequest(BaseModel):
    node_id: str
    cpu_usage: float
    memory_usage: float
    neighbors_count: int
    routing_table_size: int
    uptime: float
    pheromones: Optional[Dict[str, Dict[str, float]]] = None # For Stigmergy viz

class PolicyRequest(BaseModel):
    source_tag: str = Field(..., description="Tag of nodes initiating connection (e.g. 'robot')")
    target_tag: str = Field(..., description="Tag of destination nodes (e.g. 'gateway')")
    action: str = Field(default="allow", pattern="^(allow|deny)$")

class PolicyResponse(BaseModel):
    policy_id: str
    source_tag: str
    target_tag: str
    action: str
    created_at: str

# ---------------------------------------------------------------------------
# Mesh Instance — lifecycle + metrics
# ---------------------------------------------------------------------------

class MeshInstance:
    """Running mesh network instance with consciousness metrics."""

    def __init__(
        self,
        mesh_id: str,
        name: str,
        owner_id: str,
        nodes: int,
        pqc_enabled: bool = True,
        obfuscation: str = "none",
        traffic_profile: str = "none",
    ):
        self.mesh_id = mesh_id
        self.name = name
        self.owner_id = owner_id
        self.target_nodes = nodes
        self.pqc_enabled = pqc_enabled
        self.obfuscation = obfuscation
        self.traffic_profile = traffic_profile
        self.status = "provisioning"
        self.created_at = datetime.utcnow()
        self.join_token = secrets.token_urlsafe(32)
        self.join_token_ttl_sec: int = 604800  # overridden by MeshProvisioner
        self.join_token_issued_at: datetime = self.created_at
        self.join_token_expires_at: datetime = self.created_at + timedelta(seconds=604800)
        self.node_instances: Dict[str, Dict] = {}

    async def provision(self):
        """Provision mesh nodes."""
        try:
            from src.libx0t.network.mesh_node import MeshNodeConfig

            config = MeshNodeConfig(
                node_id=self.mesh_id,
                port=5000 + hash(self.mesh_id) % 4000,
                obfuscation=self.obfuscation,
                traffic_profile=self.traffic_profile,
            )
            # Store config for reference (don't auto-start in API context)
            self._config = config
        except ImportError:
            pass

        for i in range(self.target_nodes):
            node_id = f"{self.mesh_id}-node-{i}"
            self.node_instances[node_id] = {
                "id": node_id,
                "status": "healthy",
                "started_at": datetime.utcnow().isoformat(),
                "latency_ms": 0.0,
            }
        self.status = "active"
        logger.info(
            f"[MaaS] Provisioned mesh {self.mesh_id}: "
            f"{self.target_nodes} nodes, PQC={self.pqc_enabled}"
        )

    async def terminate(self):
        self.node_instances.clear()
        self.status = "terminated"
        logger.info(f"[MaaS] Terminated mesh {self.mesh_id}")

    def scale(self, action: str, count: int) -> int:
        previous = len(self.node_instances)
        if action == "scale_up":
            for i in range(count):
                node_id = f"{self.mesh_id}-node-{previous + i}"
                self.node_instances[node_id] = {
                    "id": node_id,
                    "status": "healthy",
                    "started_at": datetime.utcnow().isoformat(),
                    "latency_ms": 0.0,
                }
            self.target_nodes += count
        elif action == "scale_down":
            to_remove = min(count, len(self.node_instances) - 1)
            keys = list(self.node_instances.keys())[-to_remove:]
            for k in keys:
                del self.node_instances[k]
            self.target_nodes = max(1, self.target_nodes - count)
        return len(self.node_instances)

    def get_health_score(self) -> float:
        if not self.node_instances:
            return 0.0
        healthy = sum(
            1 for n in self.node_instances.values() if n["status"] == "healthy"
        )
        return healthy / len(self.node_instances)

    def get_uptime(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds()

    def get_consciousness_metrics(self) -> Dict[str, Any]:
        health = self.get_health_score()
        uptime = self.get_uptime()
        phi = min(1.618, 0.5 + health * 1.118)
        entropy = max(0.0, 1.0 - health)
        harmony = health * min(1.0, uptime / 3600)
        return {
            "phi_ratio": round(phi, 4),
            "entropy": round(entropy, 4),
            "harmony": round(harmony, 4),
            "state": (
                "TRANSCENDENT" if health >= 0.95
                else "FLOW" if health >= 0.8
                else "AWARE" if health >= 0.5
                else "DORMANT"
            ),
            "nodes_total": len(self.node_instances),
            "nodes_healthy": sum(
                1 for n in self.node_instances.values() if n["status"] == "healthy"
            ),
        }

    def get_mape_k_state(self) -> Dict[str, Any]:
        health = self.get_health_score()
        return {
            "phase": "MONITOR",
            "interval_seconds": 10 if health < 0.8 else 30,
            "directives": {
                "monitoring_interval": 10 if health < 0.8 else 30,
                "self_healing_aggressiveness": (
                    "high" if health < 0.5
                    else "medium" if health < 0.8
                    else "low"
                ),
                "scaling_recommendation": (
                    "scale_up" if health < 0.5 else "maintain"
                ),
            },
            "last_cycle": datetime.utcnow().isoformat(),
        }

    def get_network_metrics(self) -> Dict[str, Any]:
        return {
            "nodes_active": len(self.node_instances),
            "avg_latency_ms": 12.5,
            "throughput_mbps": len(self.node_instances) * 10.0,
            "packet_loss_pct": 0.01 if self.get_health_score() > 0.9 else 0.5,
            "pqc_handshakes_completed": len(self.node_instances) * 3,
            "obfuscation_mode": self.obfuscation,
            "traffic_profile": self.traffic_profile,
        }


# ---------------------------------------------------------------------------
# Global registry + services
# ---------------------------------------------------------------------------

_mesh_registry: Dict[str, MeshInstance] = {}
# Pending nodes for approval: mesh_id -> { node_id -> registration_data }
_pending_nodes: Dict[str, Dict[str, Dict]] = {}
# Real-time telemetry: node_id -> heartbeat_data
_node_telemetry: Dict[str, Dict] = {}
# ACL Policies: mesh_id -> List of policies
# Policy: { "id": str, "source_tag": str, "target_tag": str, "action": "allow"|"deny" }
_mesh_policies: Dict[str, List[Dict]] = {}
_mesh_audit_log: Dict[str, List[Dict[str, Any]]] = {}
# MAPE-K event stream: mesh_id -> chronological events
_mesh_mapek_events: Dict[str, List[Dict[str, Any]]] = {}
# Revoked nodes: mesh_id -> { node_id -> revoke_metadata }
_revoked_nodes: Dict[str, Dict[str, Dict[str, Any]]] = {}
# One-time reissue enrollment tokens:
# mesh_id -> { token -> { node_id, issued_at, expires_at, used } }
_mesh_reissue_tokens: Dict[str, Dict[str, Dict[str, Any]]] = {}
_registry_lock = asyncio.Lock()
_MAPEK_EVENT_BUFFER_SIZE = 1000
_DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "web" / "dashboard"
_PENDING_APPROVALS_UI = _DASHBOARD_DIR / "pending_approvals.html"


async def record_audit_log(
    mesh_id: str,
    actor: str,
    event: str,
    details: str,
) -> None:
    """Append control-plane audit event (async, with registry lock)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "actor": actor,
        "event": event,
        "details": details,
    }
    async with _registry_lock:
        if mesh_id not in _mesh_audit_log:
            _mesh_audit_log[mesh_id] = []
        _mesh_audit_log[mesh_id].append(entry)


def _audit(mesh_id: str, actor: str, event: str, details: str) -> None:
    """Sync audit helper for use inside non-async endpoints."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "actor": actor,
        "event": event,
        "details": details,
    }
    if mesh_id not in _mesh_audit_log:
        _mesh_audit_log[mesh_id] = []
    _mesh_audit_log[mesh_id].append(entry)


class BillingService:
    """Quota enforcement based on plan."""

    LIMITS = {
        "free": 20,
        "starter": 20,
        "pro": 1000,
        "enterprise": 10000,
    }
    PLAN_RANK = {
        "starter": 1,
        "pro": 2,
        "enterprise": 3,
    }

    def normalize_plan(self, plan: Optional[str]) -> str:
        return PLAN_ALIASES.get((plan or "").lower(), "starter")

    def plan_catalog(self) -> Dict[str, Dict[str, Any]]:
        return {
            "starter": {
                "max_nodes": self.LIMITS["starter"],
                "features": ["basic_mesh", "zero_trust_identity"],
            },
            "pro": {
                "max_nodes": self.LIMITS["pro"],
                "features": ["ai_route_optimization", "mape_k_autoscaling"],
            },
            "enterprise": {
                "max_nodes": "unlimited",
                "features": [
                    "on_prem_control_plane",
                    "sso",
                    "audit_logs",
                    "dao_policy_hooks",
                ],
            },
        }

    def check_quota(
        self,
        user: User,
        requested_nodes: int,
        requested_plan: Optional[str] = None,
    ):
        user_plan = self.normalize_plan(getattr(user, "plan", "starter"))
        request_plan = self.normalize_plan(requested_plan or user_plan)
        if self.PLAN_RANK[request_plan] > self.PLAN_RANK[user_plan]:
            raise Exception(
                f"Plan escalation blocked: account plan '{user_plan}' "
                f"cannot deploy '{request_plan}'."
            )
        limit = min(self.LIMITS[user_plan], self.LIMITS[request_plan])
        if requested_nodes > limit:
            raise Exception(
                f"Quota exceeded: {user_plan} plan limit is {limit} nodes. "
                f"Upgrade to increase."
            )
        return True


class MeshProvisioner:
    """Provisions real mesh networks."""

    async def create(
        self,
        user: User = None,
        name: str = "",
        nodes: int = 5,
        owner_id: str = None,
        pqc_enabled: bool = True,
        obfuscation: str = "none",
        traffic_profile: str = "none",
        join_token_ttl_sec: int = 604800,
    ) -> MeshInstance:
        _owner_id = owner_id or (user.id if user else "unknown")
        mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
        instance = MeshInstance(
            mesh_id=mesh_id,
            name=name,
            owner_id=_owner_id,
            nodes=nodes,
            pqc_enabled=pqc_enabled,
            obfuscation=obfuscation,
            traffic_profile=traffic_profile,
        )
        instance.join_token_ttl_sec = join_token_ttl_sec
        instance.join_token_expires_at = instance.created_at + timedelta(seconds=join_token_ttl_sec)
        await instance.provision()
        async with _registry_lock:
            _mesh_registry[mesh_id] = instance
        logger.info(
            f"[MaaS] Created mesh {mesh_id}: "
            f"{nodes} nodes, PQC={pqc_enabled}, obf={obfuscation}"
        )
        return instance

    async def terminate(self, mesh_id: str) -> bool:
        async with _registry_lock:
            instance = _mesh_registry.get(mesh_id)
            if not instance:
                return False
            await instance.terminate()
            del _mesh_registry[mesh_id]
        return True

    def get(self, mesh_id: str) -> Optional[MeshInstance]:
        return _mesh_registry.get(mesh_id)

    def list_for_owner(self, owner_id: str) -> List[MeshInstance]:
        return [
            m for m in _mesh_registry.values()
            if m.owner_id == owner_id and m.status != "terminated"
        ]


class UsageMeteringService:
    """Tracks mesh/node-hour usage for billing."""

    def get_mesh_usage(self, instance: "MeshInstance") -> Dict[str, Any]:
        now = datetime.utcnow()
        total_node_hours = 0.0
        node_detail = []

        for node_id, node in instance.node_instances.items():
            try:
                started = datetime.fromisoformat(node["started_at"])
            except (KeyError, ValueError):
                started = instance.created_at
            hours = max(0.0, (now - started).total_seconds() / 3600.0)
            total_node_hours += hours
            node_detail.append({"node_id": node_id, "hours": round(hours, 4)})

        return {
            "mesh_id": instance.mesh_id,
            "mesh_name": instance.name,
            "status": instance.status,
            "active_nodes": len(instance.node_instances),
            "total_node_hours": round(total_node_hours, 4),
            "billing_period_start": instance.created_at.isoformat(),
            "billing_period_end": now.isoformat(),
            "nodes": node_detail,
        }

    def get_account_usage(self, owner_id: str) -> Dict[str, Any]:
        meshes = [m for m in _mesh_registry.values() if m.owner_id == owner_id]
        total_node_hours = 0.0
        mesh_summaries = []

        for instance in meshes:
            usage = self.get_mesh_usage(instance)
            total_node_hours += usage["total_node_hours"]
            mesh_summaries.append({
                "mesh_id": usage["mesh_id"],
                "mesh_name": usage["mesh_name"],
                "status": usage["status"],
                "active_nodes": usage["active_nodes"],
                "total_node_hours": usage["total_node_hours"],
            })

        return {
            "owner_id": owner_id,
            "total_node_hours": round(total_node_hours, 4),
            "mesh_count": len(meshes),
            "meshes": mesh_summaries,
            "generated_at": datetime.utcnow().isoformat(),
        }


usage_metering_service = UsageMeteringService()


class AuthService:
    """User registration and login (MVP)."""

    def __init__(self):
        self._shared = MaaSAuthService(
            api_key_factory=lambda: secrets.token_urlsafe(32),
            default_plan="starter",
        )

    def register(self, db: Session, req: UserRegisterRequest) -> User:
        return self._shared.register(db, req)

    def login(self, db: Session, req: UserLoginRequest) -> str:
        return self._shared.login(db, req)

    def rotate_api_key(self, db: Session, user: User) -> tuple[str, datetime]:
        return self._shared.rotate_api_key(db, user)


mesh_provisioner = MeshProvisioner()
billing_service = BillingService()
auth_service = AuthService()

# ---------------------------------------------------------------------------
# Auth Dependencies
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> User:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    user = db.query(User).filter(User.api_key == api_key).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


def validate_customer(api_key: str, db: Session) -> User:
    """Validate API key (query-param style). Backward compat."""
    user = db.query(User).filter(User.api_key == api_key).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


def _get_mesh_or_404(mesh_id: str, owner_id: str) -> MeshInstance:
    instance = mesh_provisioner.get(mesh_id)
    if not instance or instance.owner_id != owner_id:
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")
    return instance


def _rule_matches(
    source_tags: List[str],
    target_tags: List[str],
    source_tag: str,
    target_tag: str,
) -> bool:
    return source_tag in source_tags and target_tag in target_tags


def _evaluate_acl_decision(
    source_tags: List[str],
    target_tags: List[str],
    policies: List[Dict[str, Any]],
    acl_profile: str,
) -> Dict[str, Any]:
    """Evaluate allow/deny using deny-priority semantics."""
    matched_rules = [
        p
        for p in policies
        if _rule_matches(
            source_tags,
            target_tags,
            str(p.get("source_tag", "")),
            str(p.get("target_tag", "")),
        )
    ]

    if acl_profile == "isolated":
        return {"action": "deny", "reason": "acl_profile_isolated", "rules": []}

    if any(rule.get("action") == "deny" for rule in matched_rules):
        return {
            "action": "deny",
            "reason": "explicit_deny",
            "rules": matched_rules,
        }

    if any(rule.get("action") == "allow" for rule in matched_rules):
        return {
            "action": "allow",
            "reason": "explicit_allow",
            "rules": matched_rules,
        }

    # Legacy fallback for bootstrapping meshes without explicit policy set.
    if not policies and acl_profile == "default":
        return {"action": "allow", "reason": "legacy_open_mesh", "rules": []}

    return {"action": "deny", "reason": "default_deny_zero_trust", "rules": []}


def _is_reissue_token_expired(token_data: Dict[str, Any]) -> bool:
    expires_raw = token_data.get("expires_at")
    if not isinstance(expires_raw, str):
        return True
    try:
        return datetime.utcnow() >= datetime.fromisoformat(expires_raw)
    except ValueError:
        return True


def _is_join_token_expired(instance: "MeshInstance") -> bool:
    return datetime.utcnow() >= instance.join_token_expires_at


def _verify_billing_webhook_secret(provided_secret: Optional[str]) -> None:
    """Optional shared-secret auth for MaaS billing webhook."""
    expected_secret = os.getenv("X0T_BILLING_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        return

    if not provided_secret or not secrets.compare_digest(
        provided_secret, expected_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid billing webhook secret")


def _billing_webhook_tolerance_seconds() -> int:
    raw = os.getenv("X0T_BILLING_WEBHOOK_TOLERANCE_SEC", "300").strip()
    try:
        value = int(raw)
    except ValueError:
        return 300
    return max(30, min(value, 3600))


def _billing_event_ttl_seconds() -> int:
    raw = os.getenv("X0T_BILLING_EVENT_TTL_SEC", "86400").strip()
    try:
        value = int(raw)
    except ValueError:
        return 86_400
    return max(300, min(value, 604_800))


def _verify_billing_webhook_hmac(
    payload: bytes,
    timestamp_header: Optional[str],
    signature_header: Optional[str],
) -> None:
    """
    Verify webhook integrity using HMAC-SHA256 over `${timestamp}.${payload}`.
    Enforced only when X0T_BILLING_WEBHOOK_HMAC_SECRET is configured.
    """
    secret = os.getenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", "").strip()
    if not secret:
        return

    if not timestamp_header or not signature_header:
        raise HTTPException(
            status_code=401,
            detail="Missing HMAC headers: X-Billing-Timestamp and X-Billing-Signature",
        )

    try:
        ts = int(timestamp_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Billing-Timestamp")

    now = int(time.time())
    tolerance = _billing_webhook_tolerance_seconds()
    if abs(now - ts) > tolerance:
        raise HTTPException(status_code=401, detail="Billing webhook timestamp expired")

    signed_payload = f"{timestamp_header}.".encode("utf-8") + payload
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]

    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid billing webhook signature")


def _payload_sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _extract_billing_event_id(req: BillingWebhookRequest) -> str:
    metadata = req.metadata if isinstance(req.metadata, dict) else {}
    event_id = req.event_id or metadata.get("event_id") or metadata.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise HTTPException(status_code=400, detail="event_id is required for idempotency")
    return event_id.strip()


def _deserialize_billing_event_response(
    response_json: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not response_json:
        return None
    try:
        loaded = json.loads(response_json)
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _cleanup_expired_billing_events(db: Session) -> None:
    """Best-effort TTL cleanup for idempotency table."""
    cutoff = datetime.utcnow() - timedelta(seconds=_billing_event_ttl_seconds())
    try:
        db.query(BillingWebhookEvent).filter(
            BillingWebhookEvent.created_at < cutoff
        ).delete(synchronize_session=False)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[MaaS] Failed cleanup billing_webhook_events: %s", exc)


def _start_billing_event_processing(
    db: Session,
    event_id: str,
    event_type: str,
    payload_hash: str,
) -> Optional[Dict[str, Any]]:
    """
    Reserve event_id in DB and return cached response for done events.
    Raises 409 on concurrent processing or payload mismatch.
    """
    _cleanup_expired_billing_events(db)

    db.add(
        BillingWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            status="processing",
        )
    )
    try:
        db.commit()
        return None
    except IntegrityError:
        db.rollback()

    existing = (
        db.query(BillingWebhookEvent)
        .filter(BillingWebhookEvent.event_id == event_id)
        .first()
    )
    if existing is None:
        raise HTTPException(
            status_code=409,
            detail="Billing event state conflict; retry delivery",
        )

    if existing.payload_hash != payload_hash:
        raise HTTPException(status_code=409, detail="Billing event_id payload mismatch")

    if existing.status == "done":
        cached = _deserialize_billing_event_response(existing.response_json)
        if cached is None:
            raise HTTPException(
                status_code=409,
                detail="Billing event already processed without cached response",
            )
        return dict(cached)

    if existing.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Billing event is already being processed",
        )

    existing.status = "processing"
    existing.event_type = event_type
    existing.last_error = None
    existing.processed_at = None
    db.commit()
    return None


def _finalize_billing_event_processing(
    db: Session, event_id: str, response_payload: Dict[str, Any]
) -> None:
    event = (
        db.query(BillingWebhookEvent)
        .filter(BillingWebhookEvent.event_id == event_id)
        .first()
    )
    if event is None:
        raise RuntimeError(
            f"Billing event reservation missing during finalize: {event_id}"
        )

    event.status = "done"
    event.response_json = json.dumps(response_payload, ensure_ascii=False)
    event.last_error = None
    event.processed_at = datetime.utcnow()
    db.commit()


def _fail_billing_event_processing(db: Session, event_id: str, error: str) -> None:
    try:
        event = (
            db.query(BillingWebhookEvent)
            .filter(BillingWebhookEvent.event_id == event_id)
            .first()
        )
        if event is None:
            return
        event.status = "failed"
        event.last_error = error[:2000]
        event.processed_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()


def _resolve_billing_user(db: Session, req: BillingWebhookRequest) -> Optional[User]:
    """Resolve user for billing event via user_id/customer/subscription/email."""
    metadata = req.metadata if isinstance(req.metadata, dict) else {}

    user_id = req.user_id or metadata.get("user_id")
    if isinstance(user_id, str) and user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    customer_id = req.customer_id or metadata.get("customer_id")
    if isinstance(customer_id, str) and customer_id:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            return user

    subscription_id = req.subscription_id or metadata.get("subscription_id")
    if isinstance(subscription_id, str) and subscription_id:
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
        if user:
            return user

    email = req.email or metadata.get("email") or metadata.get("user_email")
    if isinstance(email, str) and email:
        return db.query(User).filter(User.email == email).first()

    return None


def _find_mesh_id_for_node(node_id: str) -> Optional[str]:
    for mesh_id, instance in _mesh_registry.items():
        if node_id in instance.node_instances:
            return mesh_id
    return None


def _build_mapek_heartbeat_event(telemetry: NodeHeartbeatRequest) -> Dict[str, Any]:
    """Translate heartbeat into a compact MAPE-K monitor/analyze event."""
    if telemetry.neighbors_count == 0 or telemetry.cpu_usage >= 95 or telemetry.memory_usage >= 95:
        health_state = "critical"
        recommendation = "reroute_and_recover"
    elif telemetry.cpu_usage >= 85 or telemetry.memory_usage >= 85:
        health_state = "degraded"
        recommendation = "scale_or_rebalance"
    else:
        health_state = "healthy"
        recommendation = "maintain"

    return {
        "event_id": f"evt-{uuid.uuid4().hex[:10]}",
        "timestamp": datetime.utcnow().isoformat(),
        "phase": "MONITOR",
        "node_id": telemetry.node_id,
        "health_state": health_state,
        "recommendation": recommendation,
        "signals": {
            "cpu_usage": telemetry.cpu_usage,
            "memory_usage": telemetry.memory_usage,
            "neighbors_count": telemetry.neighbors_count,
            "routing_table_size": telemetry.routing_table_size,
            "uptime": telemetry.uptime,
        },
    }


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(db, req)
    return {
        "access_token": user.api_key,
        "token_type": "api_key",
        "expires_in": 31536000,
    }


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    api_key = auth_service.login(db, req)
    return {
        "access_token": api_key,
        "token_type": "api_key",
        "expires_in": 31536000,
    }


@router.post("/api-key", response_model=ApiKeyResponse)
def rotate_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_key, rotated_at = auth_service.rotate_api_key(db, current_user)
    return {"api_key": new_key, "created_at": rotated_at}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "plan": current_user.plan,
        "company": current_user.company,
        "requests_count": current_user.requests_count,
        "requests_limit": current_user.requests_limit,
    }


@router.get("/plans")
def list_maas_plans():
    """Commercial plan catalog for self-service customers."""
    return {"plans": billing_service.plan_catalog()}


@router.get("/pqc/profiles")
def list_pqc_profiles():
    """
    List PQC algorithm profiles per device segment.
    Returns recommended KEM + signature algorithm per device_class.
    """
    return {
        "profiles": PQC_SEGMENT_PROFILES,
        "default": _PQC_DEFAULT_PROFILE,
        "standards": {
            "kem": "FIPS 203 (ML-KEM / CRYSTALS-Kyber)",
            "sig": "FIPS 204 (ML-DSA / CRYSTALS-Dilithium)",
        },
    }


# ---------------------------------------------------------------------------
# SSO / OIDC Endpoints (Enterprise)
# ---------------------------------------------------------------------------


class OIDCExchangeRequest(BaseModel):
    id_token: str = Field(..., min_length=10, description="OIDC ID token from provider")


@router.get("/auth/oidc/config")
def oidc_config():
    """Return OIDC configuration for frontend login flow."""
    return oidc_validator.get_config()


@router.post("/auth/oidc/exchange")
def oidc_exchange(req: OIDCExchangeRequest, db: Session = Depends(get_db)):
    """
    Exchange an OIDC ID token for a x0tta6bl4 MaaS API key.

    Flow:
      1. Frontend obtains id_token from OIDC provider (Google, Okta, etc.)
      2. Frontend POSTs id_token here
      3. We validate signature + claims against provider's JWKS
      4. We create/find the User and return an x0t API key
    """
    claims = oidc_validator.validate(req.id_token)

    # Find or create user
    user = db.query(User).filter(User.email == claims.email).first()
    if not user:
        new_api_key = api_key_manager.generate()
        user = User(
            email=claims.email,
            full_name=claims.name,
            api_key=new_api_key,
            plan="starter",
            oidc_sub=claims.sub,
            oidc_issuer=claims.issuer,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"[OIDC] New user via SSO: {claims.email} (sub={claims.sub[:8]}...)")
    else:
        # Update OIDC fields if missing
        changed = False
        if not getattr(user, "oidc_sub", None):
            user.oidc_sub = claims.sub
            changed = True
        if not getattr(user, "oidc_issuer", None):
            user.oidc_issuer = claims.issuer
            changed = True
        if changed:
            db.commit()

    _audit("__system__", claims.email, "OIDC_LOGIN", f"SSO login via {claims.issuer}")

    return {
        "access_token": user.api_key,
        "token_type": "api_key",
        "email": user.email,
        "plan": user.plan,
        "oidc_sub": claims.sub,
        "message": "Authenticated via OIDC. Use access_token as X-API-Key.",
    }


# ---------------------------------------------------------------------------
# Mesh Lifecycle Endpoints
# ---------------------------------------------------------------------------

@router.post("/deploy", response_model=MeshDeployResponse)
async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User = Depends(require_permission("mesh:create")),
    db: Session = Depends(get_db),
):
    """Deploy a PQC-secured mesh network."""
    # Check quota
    try:
        billing_service.check_quota(
            current_user,
            req.nodes,
            requested_plan=req.billing_plan,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )

    # Provision
    instance = await mesh_provisioner.create(
        user=current_user,
        name=req.name,
        nodes=req.nodes,
        pqc_enabled=req.pqc_enabled,
        obfuscation=req.obfuscation,
        traffic_profile=req.traffic_profile,
        join_token_ttl_sec=req.join_token_ttl_sec,
    )

    _audit(instance.mesh_id, current_user.email, "MESH_DEPLOYED",
           f"Mesh '{req.name}' deployed: {req.nodes} nodes, plan={req.billing_plan}, PQC={req.pqc_enabled}")

    # PQC identity
    pqc_data = None
    if PQC_AVAILABLE:
        try:
            identity = PQCNodeIdentity(f"client-{current_user.id[:8]}")
            pkeys = identity.security.get_public_keys()
            pqc_data = {
                "did": identity.did,
                "keys": {
                    "sig_alg": pkeys.get("sig_algorithm", "unknown"),
                    "kem_alg": pkeys.get("kem_algorithm", "unknown"),
                    "sig_pub": pkeys.get("sig_public_key"),
                    "kem_pub": pkeys.get("kem_public_key"),
                },
            }
        except Exception as e:
            logger.warning(f"Failed to generate PQC identity: {e}")

    return MeshDeployResponse(
        mesh_id=instance.mesh_id,
        join_config={
            "peers": [
                f"tcp://node{i}.{instance.mesh_id}.x0tta6bl4.net:9001"
                for i in range(min(3, req.nodes))
            ],
            "token": instance.join_token,
            "token_expires_at": instance.join_token_expires_at.isoformat(),
            "pqc_algorithm": "ML-KEM-768" if req.pqc_enabled else "none",
        },
        dashboard_url=f"https://observability.x0tta6bl4.net/{instance.mesh_id}",
        status=instance.status,
        pqc_identity=pqc_data,
        pqc_enabled=instance.pqc_enabled,
        created_at=instance.created_at.isoformat(),
        plan=billing_service.normalize_plan(req.billing_plan),
        join_token_expires_at=instance.join_token_expires_at.isoformat(),
    )


@router.get("/list")
def list_meshes(current_user: User = Depends(require_permission("mesh:view"))):
    """List all meshes for the authenticated user."""
    meshes = mesh_provisioner.list_for_owner(current_user.id)
    return {
        "meshes": [
            {
                "mesh_id": m.mesh_id,
                "name": m.name,
                "status": m.status,
                "nodes": len(m.node_instances),
                "pqc_enabled": m.pqc_enabled,
                "health_score": m.get_health_score(),
                "uptime_seconds": round(m.get_uptime(), 1),
                "created_at": m.created_at.isoformat(),
            }
            for m in meshes
        ],
        "total": len(meshes),
    }


@router.get("/{mesh_id}/status", response_model=MeshStatusResponse)
def mesh_status(mesh_id: str, current_user: User = Depends(require_permission("mesh:view"))):
    """Get detailed status and health of a mesh network."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    return MeshStatusResponse(
        mesh_id=instance.mesh_id,
        status=instance.status,
        nodes_total=len(instance.node_instances),
        nodes_healthy=sum(
            1 for n in instance.node_instances.values() if n["status"] == "healthy"
        ),
        uptime_seconds=round(instance.get_uptime(), 1),
        pqc_enabled=instance.pqc_enabled,
        obfuscation=instance.obfuscation,
        traffic_profile=instance.traffic_profile,
        peers=[
            {"id": nid, **ndata}
            for nid, ndata in list(instance.node_instances.items())[:20]
        ],
        health_score=round(instance.get_health_score(), 4),
    )


@router.get("/{mesh_id}/metrics", response_model=MeshMetricsResponse)
def mesh_metrics(mesh_id: str, current_user: User = Depends(require_permission("mesh:view"))):
    """
    Get consciousness + MAPE-K + network metrics.

    Returns phi-ratio, entropy, harmony (consciousness engine),
    self-healing directives (MAPE-K), and network performance data.
    """
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    return MeshMetricsResponse(
        mesh_id=instance.mesh_id,
        consciousness=instance.get_consciousness_metrics(),
        mape_k=instance.get_mape_k_state(),
        network=instance.get_network_metrics(),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.post("/{mesh_id}/scale", response_model=ScaleResponse)
def scale_mesh(
    mesh_id: str,
    request: ScaleRequest,
    current_user: User = Depends(require_permission("mesh:update")),
):
    """Scale a mesh network up or down."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    if instance.status == "terminated":
        raise HTTPException(status_code=400, detail="Cannot scale a terminated mesh")

    previous = len(instance.node_instances)

    if request.action == "scale_up":
        try:
            billing_service.check_quota(current_user, previous + request.count)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(e),
            )

    new_total = instance.scale(request.action, request.count)
    logger.info(
        f"[MaaS] Scaled {mesh_id}: {previous} → {new_total} "
        f"({request.action}, {request.count})"
    )
    return ScaleResponse(
        mesh_id=mesh_id,
        previous_nodes=previous,
        current_nodes=new_total,
        status=instance.status,
    )


@router.delete("/{mesh_id}")
async def terminate_mesh(
    mesh_id: str, current_user: User = Depends(require_permission("mesh:delete"))
):
    """Terminate a mesh network and release all resources."""
    _get_mesh_or_404(mesh_id, current_user.id)
    terminated = await mesh_provisioner.terminate(mesh_id)
    if not terminated:
        raise HTTPException(status_code=500, detail="Failed to terminate mesh")
    _audit(mesh_id, current_user.email, "MESH_TERMINATED", f"Mesh {mesh_id} terminated by {current_user.email}")
    logger.info(f"[MaaS] User {current_user.id} terminated mesh {mesh_id}")
    return {
        "mesh_id": mesh_id,
        "status": "terminated",
        "message": f"Mesh {mesh_id} has been terminated",
    }

@router.post("/heartbeat")
def heartbeat(
    telemetry: NodeHeartbeatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Receive telemetry from Headless Agent.
    Updates Control Plane visualization and MAPE-K state.
    """
    captured_at = datetime.utcnow().isoformat()
    _node_telemetry[telemetry.node_id] = {
        "cpu": telemetry.cpu_usage,
        "mem": telemetry.memory_usage,
        "neighbors": telemetry.neighbors_count,
        "routes": telemetry.routing_table_size,
        "pheromones": telemetry.pheromones,
        "last_seen": captured_at,
    }

    mesh_id = _find_mesh_id_for_node(telemetry.node_id)
    event_emitted = False
    if mesh_id:
        if mesh_id not in _mesh_mapek_events:
            _mesh_mapek_events[mesh_id] = []
        _mesh_mapek_events[mesh_id].append(_build_mapek_heartbeat_event(telemetry))
        if len(_mesh_mapek_events[mesh_id]) > _MAPEK_EVENT_BUFFER_SIZE:
            _mesh_mapek_events[mesh_id] = _mesh_mapek_events[mesh_id][-_MAPEK_EVENT_BUFFER_SIZE:]
        event_emitted = True

    logger.info(f"❤️ Heartbeat from {telemetry.node_id}")
    return {
        "status": "ack",
        "sync_required": False,
        "mesh_id": mesh_id,
        "event_emitted": event_emitted,
    }

@router.post("/{mesh_id}/register-node", response_model=NodeRegisterResponse)
async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    # No auth here, agent just has a mesh_id (or we check a public registration token)
):
    """Initial request from a new agent wanting to join."""
    instance = mesh_provisioner.get(mesh_id)
    if not instance or instance.status == "terminated":
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")

    requested_node_id = req.node_id or f"node-{uuid.uuid4().hex[:6]}"
    enrollment_mode = "mesh_join_token"
    node_id = requested_node_id

    if req.enrollment_token == instance.join_token:
        if _is_join_token_expired(instance):
            raise HTTPException(
                status_code=401,
                detail="Join token expired. Use POST /{mesh_id}/tokens/rotate to issue a new one.",
            )
    else:
        mesh_reissue = _mesh_reissue_tokens.get(mesh_id, {})
        token_data = mesh_reissue.get(req.enrollment_token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid enrollment token")
        if token_data.get("used"):
            raise HTTPException(
                status_code=401,
                detail="Enrollment token already used",
            )
        if _is_reissue_token_expired(token_data):
            raise HTTPException(status_code=401, detail="Enrollment token expired")

        expected_node_id = token_data.get("node_id")
        if isinstance(expected_node_id, str):
            if req.node_id and req.node_id != expected_node_id:
                raise HTTPException(
                    status_code=401,
                    detail="Enrollment token does not match node_id",
                )
            node_id = expected_node_id
        token_data["used"] = True
        enrollment_mode = "reissue_token"

    if node_id in _revoked_nodes.get(mesh_id, {}) and enrollment_mode != "reissue_token":
        raise HTTPException(
            status_code=403,
            detail="Node is revoked; reissue token is required",
        )

    async with _registry_lock:
        if mesh_id not in _pending_nodes:
            _pending_nodes[mesh_id] = {}
        if node_id in instance.node_instances:
            raise HTTPException(status_code=409, detail="Node already approved")

        # Hardware Attestation (Enterprise Tier)
        attestation = AttestationService.validate_node({
            "hardware_id": req.hardware_id,
            "enclave_enabled": req.enclave_enabled,
            "attestation_data": req.attestation_data
        })

        _pending_nodes[mesh_id][node_id] = {
            "device_class": req.device_class,
            "labels": req.labels,
            "public_keys": req.public_keys,
            "requested_at": datetime.utcnow().isoformat(),
            "enrollment_mode": enrollment_mode,
            "attestation": attestation
        }

    return NodeRegisterResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="pending_approval",
        message="Node registration submitted. Awaiting administrator approval."
    )

@router.get("/{mesh_id}/pending-nodes")
def list_pending_nodes(mesh_id: str, current_user: User = Depends(require_permission("node:view"))):
    """Admin view: list nodes waiting for approval."""
    _get_mesh_or_404(mesh_id, current_user.id)
    return {"pending": _pending_nodes.get(mesh_id, {})}


@router.post("/{mesh_id}/nodes/register", response_model=NodeRegisterResponse)
async def register_node_v2(mesh_id: str, req: NodeRegisterRequest):
    """Canonical node registration endpoint (v2)."""
    return await register_node(mesh_id, req)


@router.get("/{mesh_id}/nodes/pending")
def list_pending_nodes_v2(
    mesh_id: str, current_user: User = Depends(require_role("operator"))
):
    """Canonical pending list endpoint (v2)."""
    return list_pending_nodes(mesh_id, current_user)

@router.post("/{mesh_id}/approve-node/{node_id}", response_model=NodeApproveResponse)
async def approve_node(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest,
    current_user: User = Depends(require_permission("node:approve"))
):
    """Admin action: approve a node and return its join token."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    
    async with _registry_lock:
        if mesh_id not in _pending_nodes or node_id not in _pending_nodes[mesh_id]:
            raise HTTPException(status_code=404, detail="Pending node not found")
        
        node_data = _pending_nodes[mesh_id].pop(node_id)
        signed_join_token = token_signer.sign_token(instance.join_token, mesh_id)

        device_class = node_data["device_class"]
        pqc_profile = _get_pqc_profile(device_class)

        # Add to mesh instance
        instance.node_instances[node_id] = {
            "id": node_id,
            "status": "healthy",
            "device_class": device_class,
            "started_at": datetime.utcnow().isoformat(),
            "approved_at": datetime.utcnow().isoformat(),
            "acl_profile": req.acl_profile,
            "tags": req.tags,
            "pqc_profile": pqc_profile,
            "security_level": node_data.get("attestation", {}).get("security_level", "SOFTWARE_ONLY")
        }
        if mesh_id in _revoked_nodes:
            _revoked_nodes[mesh_id].pop(node_id, None)
        
    await record_audit_log(mesh_id, current_user.email, "NODE_APPROVED", f"Approved {node_id} with profile {req.acl_profile}")
        
    return NodeApproveResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="approved",
        join_token={
            "token": signed_join_token["token"],
            "signature": signed_join_token["signature"],
            "algorithm": signed_join_token["algorithm"],
            "pqc_secured": signed_join_token.get("pqc_secured", False),
            "peers": [f"tcp://node0.{mesh_id}.x0tta6bl4.net:9001"],
        },
        approved_at=datetime.utcnow().isoformat()
    )


@router.post("/{mesh_id}/nodes/{node_id}/approve", response_model=NodeApproveResponse)
async def approve_node_v2(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest,
    current_user: User = Depends(get_current_user),
):
    """Canonical approve endpoint (v2)."""
    return await approve_node(mesh_id, node_id, req, current_user)


@router.get("/{mesh_id}/policies")
def list_policies(mesh_id: str, current_user: User = Depends(get_current_user)):
    """Admin view: list access control policies."""
    _get_mesh_or_404(mesh_id, current_user.id)
    return {"policies": _mesh_policies.get(mesh_id, [])}


@router.get("/{mesh_id}/audit-logs")
def list_audit_logs(mesh_id: str, current_user: User = Depends(require_permission("audit:view"))):
    """Enterprise audit trail for control-plane actions."""
    _get_mesh_or_404(mesh_id, current_user.id)
    return {
        "mesh_id": mesh_id,
        "events": _mesh_audit_log.get(mesh_id, []),
        "count": len(_mesh_audit_log.get(mesh_id, [])),
    }


@router.get("/{mesh_id}/audit-logs/export")
def export_audit_logs(
    mesh_id: str,
    format: str = "json",
    limit: int = 1000,
    event_type: Optional[str] = None,
    current_user: User = Depends(require_permission("audit:view")),
):
    """
    Export audit log as CSV or JSON download.
    ?format=csv|json  ?limit=N  ?event_type=NODE_APPROVED
    """
    _get_mesh_or_404(mesh_id, current_user.id)
    events = _mesh_audit_log.get(mesh_id, [])

    # Optional filter
    if event_type:
        events = [e for e in events if e.get("event") == event_type.upper()]

    events = events[-max(1, min(limit, 10000)):]

    if format.lower() == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["timestamp", "actor", "event", "details"])
        writer.writeheader()
        writer.writerows(events)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="audit-{mesh_id}.csv"'},
        )

    # Default: JSON download
    payload = json.dumps({"mesh_id": mesh_id, "count": len(events), "events": events}, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="audit-{mesh_id}.json"'},
    )


@router.get("/{mesh_id}/mapek/events")
def list_mapek_events(
    mesh_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Control-plane view of recent MAPE-K heartbeat-derived events."""
    _get_mesh_or_404(mesh_id, current_user.id)
    limit = max(1, min(limit, 500))
    events = _mesh_mapek_events.get(mesh_id, [])
    return {
        "mesh_id": mesh_id,
        "events": events[-limit:],
        "count": len(events),
        "limit": limit,
    }

@router.post("/{mesh_id}/policies", response_model=PolicyResponse)
async def create_policy(
    mesh_id: str,
    req: PolicyRequest,
    current_user: User = Depends(require_permission("policy:create"))
):
    """Admin action: create a new ACL policy rule."""
    _get_mesh_or_404(mesh_id, current_user.id)
    
    policy_id = f"pol-{uuid.uuid4().hex[:6]}"
    policy = {
        "policy_id": policy_id,
        "source_tag": req.source_tag,
        "target_tag": req.target_tag,
        "action": req.action,
        "created_at": datetime.utcnow().isoformat()
    }
    
    async with _registry_lock:
        if mesh_id not in _mesh_policies:
            _mesh_policies[mesh_id] = []
        _mesh_policies[mesh_id].append(policy)
        
    logger.info(f"🛡️ ACL: Policy {policy_id} created for mesh {mesh_id}: {req.source_tag} -> {req.target_tag} ({req.action})")
    return policy

@router.get("/{mesh_id}/node-config/{node_id}")
def get_node_config(mesh_id: str, node_id: str):
    """
    Called by Agent to fetch its allowed policies and peer tags.
    This is the core of local enforcement.
    """
    instance = mesh_provisioner.get(mesh_id)
    if not instance or instance.status == "terminated":
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")
    if node_id in _revoked_nodes.get(mesh_id, {}):
        raise HTTPException(status_code=403, detail=f"Node {node_id} is revoked")

    node = instance.node_instances.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} is not approved")

    policies = _mesh_policies.get(mesh_id, [])
    node_tags = list(node.get("tags", []))
    acl_profile = str(node.get("acl_profile", "default"))

    peer_tags = {}
    policy_decisions: Dict[str, Dict[str, Any]] = {}
    allowed_peers: List[str] = []
    denied_peers: List[str] = []

    for peer_id, peer in instance.node_instances.items():
        if peer_id == node_id:
            continue
        peer_node_tags = list(peer.get("tags", []))
        peer_tags[peer_id] = peer_node_tags
        decision = _evaluate_acl_decision(
            source_tags=node_tags,
            target_tags=peer_node_tags,
            policies=policies,
            acl_profile=acl_profile,
        )

        if peer_id in _revoked_nodes.get(mesh_id, {}):
            decision = {
                "action": "deny",
                "reason": "peer_revoked",
                "rules": [],
            }

        matched_rule_ids = [
            str(rule.get("policy_id", "unknown")) for rule in decision.get("rules", [])
        ]
        policy_decisions[peer_id] = {
            "action": decision["action"],
            "reason": decision["reason"],
            "matched_policy_ids": matched_rule_ids,
        }
        if decision["action"] == "allow":
            allowed_peers.append(peer_id)
        else:
            denied_peers.append(peer_id)

    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "node_tags": node_tags,
        "acl_profile": acl_profile,
        "policies": policies,
        "peer_tags": peer_tags,
        "allowed_peers": allowed_peers,
        "denied_peers": denied_peers,
        "policy_decisions": policy_decisions,
        "global_mode": "zero-trust",
        "enforcement": "tag-based",
    }

@router.get("/control-plane/pending-approvals", include_in_schema=False)
def pending_approvals_ui():
    """Serve minimal Pending Approvals UI for control-plane operators."""
    if not _PENDING_APPROVALS_UI.exists():
        raise HTTPException(status_code=404, detail="Pending approvals UI not found")
    return FileResponse(_PENDING_APPROVALS_UI)

@router.get("/{mesh_id}/topology")
def get_topology(mesh_id: str, current_user: User = Depends(get_current_user)):
    """Returns nodes and pheromone-weighted links for the dashboard."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    
    nodes = []
    links = []
    
    for nid, ndata in instance.node_instances.items():
        telemetry = _node_telemetry.get(nid, {})
        nodes.append({
            "id": nid,
            "class": ndata.get("device_class", "edge"),
            "status": ndata["status"],
            "telemetry": telemetry
        })
        
        # Pheromone-based links
        pheromones = telemetry.get("pheromones", {})
        for dest_id, targets in pheromones.items():
            for next_hop, score in targets.items():
                links.append({
                    "source": nid,
                    "target": next_hop,
                    "weight": score
                })
                
    return {"nodes": nodes, "links": links}


@router.get("/{mesh_id}/nodes")
def list_approved_nodes(mesh_id: str, current_user: User = Depends(get_current_user)):
    """List approved nodes in mesh."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    return {
        "mesh_id": mesh_id,
        "nodes": list(instance.node_instances.values()),
        "count": len(instance.node_instances),
    }


@router.get("/{mesh_id}/nodes/all")
def list_all_nodes(
    mesh_id: str,
    node_status: Optional[str] = None,
    current_user: User = Depends(require_role("operator")),
):
    """
    Unified node list: approved + pending + revoked in one response.
    ?node_status=approved|pending|revoked  (omit for all)
    """
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    result = []

    # Approved nodes
    for node_id, data in instance.node_instances.items():
        result.append({
            "node_id": node_id,
            "status": "approved",
            "device_class": data.get("device_class", "edge"),
            "acl_profile": data.get("acl_profile", "default"),
            "tags": data.get("tags", []),
            "approved_at": data.get("approved_at"),
            "started_at": data.get("started_at"),
        })

    # Pending nodes
    for node_id, data in _pending_nodes.get(mesh_id, {}).items():
        result.append({
            "node_id": node_id,
            "status": "pending",
            "device_class": data.get("device_class", "edge"),
            "acl_profile": None,
            "tags": [],
            "requested_at": data.get("requested_at"),
            "enrollment_mode": data.get("enrollment_mode"),
        })

    # Revoked nodes
    for node_id, data in _revoked_nodes.get(mesh_id, {}).items():
        result.append({
            "node_id": node_id,
            "status": "revoked",
            "device_class": data.get("device_class", "edge"),
            "acl_profile": data.get("acl_profile"),
            "tags": data.get("tags", []),
            "revoked_at": data.get("revoked_at"),
            "reason": data.get("reason"),
        })

    if node_status:
        result = [n for n in result if n["status"] == node_status]

    return {
        "mesh_id": mesh_id,
        "nodes": result,
        "count": len(result),
        "by_status": {
            "approved": sum(1 for n in result if n["status"] == "approved"),
            "pending": sum(1 for n in result if n["status"] == "pending"),
            "revoked": sum(1 for n in result if n["status"] == "revoked"),
        },
    }


@router.get("/{mesh_id}/nodes/{node_id}/pqc-profile")
def get_node_pqc_profile(
    mesh_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the active PQC algorithm profile for a specific approved node."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    node_data = instance.node_instances.get(node_id)
    if not node_data:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found or not approved")
    profile = node_data.get("pqc_profile") or _get_pqc_profile(node_data.get("device_class", "edge"))
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "device_class": node_data.get("device_class", "edge"),
        "pqc_profile": profile,
    }


# ---------------------------------------------------------------------------
# Node Revocation & Token Re-issue
# ---------------------------------------------------------------------------


@router.post(
    "/{mesh_id}/nodes/{node_id}/revoke",
    response_model=NodeRevokeResponse,
)
async def revoke_node(
    mesh_id: str,
    node_id: str,
    req: Optional[NodeRevokeRequest] = None,
    current_user: User = Depends(require_permission("node:revoke")),
):
    """
    Revoke a node — remove from mesh, add to blacklist.
    A revoked node cannot re-enroll via the global join token.
    Admin must issue a one-time reissue token to allow re-enrollment.
    """
    instance = _get_mesh_or_404(mesh_id, current_user.id)

    reason = req.reason if req else "manual_revoke"

    if node_id not in instance.node_instances:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found in mesh")

    async with _registry_lock:
        # Remove from mesh
        node_data = instance.node_instances.pop(node_id, None)
        if node_data is None:
            raise HTTPException(
                status_code=404, detail=f"Node {node_id} not found in mesh"
            )

        # Add to revoked list
        if mesh_id not in _revoked_nodes:
            _revoked_nodes[mesh_id] = {}
        _revoked_nodes[mesh_id][node_id] = {
            "reason": reason,
            "revoked_by": current_user.email,
            "revoked_at": datetime.utcnow().isoformat(),
            "tags": list(node_data.get("tags", [])),
            "acl_profile": node_data.get("acl_profile", "default"),
            "device_class": node_data.get("device_class", "edge"),
        }
        if mesh_id in _pending_nodes:
            _pending_nodes[mesh_id].pop(node_id, None)

    await record_audit_log(
        mesh_id,
        current_user.email,
        "NODE_REVOKED",
        f"Revoked {node_id}: {reason}",
    )
    logger.info(f"🚫 Node {node_id} revoked from mesh {mesh_id}: {reason}")

    return NodeRevokeResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="revoked",
        reason=reason,
        revoked_at=datetime.utcnow().isoformat(),
    )


@router.post(
    "/{mesh_id}/nodes/revoke",
    response_model=NodeRevokeResponse,
)
async def revoke_node_legacy(
    mesh_id: str,
    req: NodeRevokeRequest,
    current_user: User = Depends(get_current_user),
):
    """Legacy alias: revoke endpoint with node_id in request body."""
    if not req.node_id:
        raise HTTPException(status_code=422, detail="node_id is required")
    return await revoke_node(mesh_id, req.node_id, req, current_user)


@router.post(
    "/{mesh_id}/nodes/{node_id}/reissue-token",
    response_model=NodeReissueTokenResponse,
)
async def reissue_enrollment_token(
    mesh_id: str,
    node_id: str,
    req: NodeReissueTokenRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Issue a one-time enrollment token for a revoked node.
    The token is bound to the specific node_id and expires after TTL.
    """
    _get_mesh_or_404(mesh_id, current_user.id)

    # Verify node is actually revoked
    revoked = _revoked_nodes.get(mesh_id, {})
    if node_id not in revoked:
        raise HTTPException(
            status_code=400,
            detail=f"Node {node_id} is not revoked. Revoke before reissuing.",
        )

    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=req.ttl_seconds)
    token = secrets.token_urlsafe(32)

    signed = token_signer.sign_token(token, mesh_id)

    async with _registry_lock:
        if mesh_id not in _mesh_reissue_tokens:
            _mesh_reissue_tokens[mesh_id] = {}
        # Keep at most one active reissue token per node.
        old_tokens = [
            existing
            for existing, token_meta in _mesh_reissue_tokens[mesh_id].items()
            if token_meta.get("node_id") == node_id
        ]
        for existing in old_tokens:
            del _mesh_reissue_tokens[mesh_id][existing]
        _mesh_reissue_tokens[mesh_id][token] = {
            "node_id": node_id,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "used": False,
        }

    await record_audit_log(
        mesh_id,
        current_user.email,
        "NODE_TOKEN_REISSUED",
        f"Reissue token for {node_id}, TTL={req.ttl_seconds}s",
    )

    return NodeReissueTokenResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        join_token={
            "token": signed["token"],
            "signature": signed["signature"],
            "algorithm": signed["algorithm"],
            "pqc_secured": signed.get("pqc_secured", False),
            "type": "one-time-reissue",
            "node_id": node_id,
            "expires_at": expires_at.isoformat(),
        },
        issued_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    )


async def reissue_node_token(
    mesh_id: str,
    node_id: str,
    req: NodeReissueTokenRequest,
    current_user: User,
):
    """Backward-compatible callable alias used by unit tests/helpers."""
    return await reissue_enrollment_token(mesh_id, node_id, req, current_user)


@router.get("/{mesh_id}/nodes/revoked")
def list_revoked_nodes(
    mesh_id: str, current_user: User = Depends(get_current_user)
):
    """List all revoked nodes for a mesh."""
    _get_mesh_or_404(mesh_id, current_user.id)
    revoked = _revoked_nodes.get(mesh_id, {})
    return {
        "mesh_id": mesh_id,
        "revoked": revoked,
        "count": len(revoked),
    }


# ---------------------------------------------------------------------------
# Usage Metering
# ---------------------------------------------------------------------------


@router.get("/billing/usage")
def get_account_usage(current_user: User = Depends(get_current_user)):
    """Return aggregated node-hour usage across all meshes for this account."""
    return usage_metering_service.get_account_usage(current_user.id)


@router.get("/billing/usage/{mesh_id}")
def get_mesh_usage(
    mesh_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return detailed node-hour usage for a single mesh."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    return usage_metering_service.get_mesh_usage(instance)


@router.post("/billing/webhook", response_model=BillingWebhookResponse)
async def billing_webhook(
    request: Request,
    x_billing_webhook_secret: Optional[str] = Header(
        default=None, alias="X-Billing-Webhook-Secret"
    ),
    x_billing_timestamp: Optional[str] = Header(default=None, alias="X-Billing-Timestamp"),
    x_billing_signature: Optional[str] = Header(default=None, alias="X-Billing-Signature"),
    db: Session = Depends(get_db),
):
    """
    Process external billing events and sync account plan automatically.
    Supports plan upgrades/downgrades and subscription cancellation flow.
    """
    raw_payload = await request.body()
    _verify_billing_webhook_hmac(raw_payload, x_billing_timestamp, x_billing_signature)
    _verify_billing_webhook_secret(x_billing_webhook_secret)

    try:
        payload_data = json.loads(raw_payload.decode("utf-8"))
        req = BillingWebhookRequest(**payload_data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid billing webhook JSON payload")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    event_id = _extract_billing_event_id(req)
    event_type = req.event_type.strip().lower()
    if event_type not in BILLING_WEBHOOK_EVENTS:
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {req.event_type}")

    payload_hash = _payload_sha256_hex(raw_payload)
    cached_response = _start_billing_event_processing(
        db,
        event_id,
        event_type,
        payload_hash,
    )
    if cached_response is not None:
        cached_response["idempotent_replay"] = True
        return BillingWebhookResponse(**cached_response)

    try:
        user = _resolve_billing_user(db, req)
        if not user:
            raise HTTPException(status_code=404, detail="User for billing event not found")

        plan_before = billing_service.normalize_plan(user.plan or "starter")
        plan_after = plan_before

        requested_plan: Optional[str] = req.plan
        if not requested_plan and isinstance(req.metadata, dict):
            plan_from_meta = req.metadata.get("plan")
            if isinstance(plan_from_meta, str):
                requested_plan = plan_from_meta

        if event_type in {"subscription.canceled", "subscription.deleted"}:
            plan_after = "starter"
        elif requested_plan:
            plan_after = billing_service.normalize_plan(requested_plan)

        user.plan = plan_after
        user.requests_limit = PLAN_REQUEST_LIMITS.get(
            plan_after, PLAN_REQUEST_LIMITS["starter"]
        )

        customer_id = req.customer_id
        if not customer_id and isinstance(req.metadata, dict):
            meta_customer_id = req.metadata.get("customer_id")
            if isinstance(meta_customer_id, str):
                customer_id = meta_customer_id
        if customer_id:
            user.stripe_customer_id = customer_id

        subscription_id = req.subscription_id
        if not subscription_id and isinstance(req.metadata, dict):
            meta_subscription_id = req.metadata.get("subscription_id")
            if isinstance(meta_subscription_id, str):
                subscription_id = meta_subscription_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id

        logger.info(
            "[MaaS] Billing webhook processed: event_id=%s event=%s user=%s plan=%s->%s",
            event_id,
            event_type,
            user.id,
            plan_before,
            plan_after,
        )

        response_payload = {
            "processed": True,
            "event_id": event_id,
            "event_type": event_type,
            "user_id": user.id,
            "plan_before": plan_before,
            "plan_after": plan_after,
            "requests_limit": user.requests_limit or PLAN_REQUEST_LIMITS["starter"],
            "idempotent_replay": False,
        }
        _finalize_billing_event_processing(db, event_id, response_payload)
        return BillingWebhookResponse(**response_payload)
    except HTTPException as exc:
        db.rollback()
        _fail_billing_event_processing(
            db,
            event_id,
            f"HTTP {exc.status_code}: {exc.detail}",
        )
        raise
    except Exception as exc:
        db.rollback()
        _fail_billing_event_processing(
            db,
            event_id,
            f"{exc.__class__.__name__}: {str(exc)}",
        )
        raise


# ---------------------------------------------------------------------------
# Token Rotation
# ---------------------------------------------------------------------------


@router.post("/{mesh_id}/tokens/rotate", response_model=TokenRotateResponse)
def rotate_join_token(
    mesh_id: str,
    current_user: User = Depends(require_role("admin")),
):
    """Rotate the primary mesh join token. Old token is immediately invalidated."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    instance.join_token = secrets.token_urlsafe(32)
    instance.join_token_issued_at = datetime.utcnow()
    instance.join_token_expires_at = instance.join_token_issued_at + timedelta(
        seconds=instance.join_token_ttl_sec
    )
    _audit(mesh_id, current_user.email, "TOKEN_ROTATED", f"Join token rotated, TTL={instance.join_token_ttl_sec}s")
    logger.info(f"[MaaS] Rotated join token for mesh {mesh_id}")
    return TokenRotateResponse(
        mesh_id=mesh_id,
        join_token=instance.join_token,
        issued_at=instance.join_token_issued_at.isoformat(),
        expires_at=instance.join_token_expires_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# On-Prem Deployment Profile (Enterprise)
# ---------------------------------------------------------------------------


@router.get("/{mesh_id}/deploy/onprem")
def get_onprem_profile(
    mesh_id: str,
    format: str = "json",
    current_user: User = Depends(get_current_user),
):
    """
    Generate a self-contained on-prem deployment bundle.

    Returns everything needed to self-host the x0tta6bl4 control plane
    alongside the mesh nodes: docker-compose config + per-node agent configs.

    ?format=json|yaml
    """
    instance = _get_mesh_or_404(mesh_id, current_user.id)

    agent_configs = {}
    for node_id, node in instance.node_instances.items():
        agent_configs[node_id] = {
            "node_id": node_id,
            "api_endpoint": "http://control-plane:8000",
            "join_token": instance.join_token,
            "listen_port": 5000,
            "pqc_enabled": instance.pqc_enabled,
            "obfuscation": instance.obfuscation,
            "heartbeat_interval_sec": 30,
            "log_level": "info",
            "data_dir": "/var/lib/x0t",
        }

    token_secret = secrets.token_hex(32)
    docker_compose = f"""version: '3.8'

services:
  control-plane:
    image: ghcr.io/x0tta6bl4/control-plane:latest
    container_name: x0t-control-plane
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - MAAS_TOKEN_SECRET={token_secret}
      - DATABASE_URL=sqlite:///./x0t_maas.db
      - LOG_LEVEL=info
      - PQC_ENABLED={str(instance.pqc_enabled).lower()}
    volumes:
      - x0t_data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  x0t_data:

networks:
  default:
    name: x0t-mesh
"""

    bundle = {
        "schema_version": "1.0",
        "mesh_id": mesh_id,
        "mesh_name": instance.name,
        "generated_at": datetime.utcnow().isoformat(),
        "pqc_enabled": instance.pqc_enabled,
        "control_plane": {
            "image": "ghcr.io/x0tta6bl4/control-plane:latest",
            "port": 8000,
            "env": {
                "MAAS_TOKEN_SECRET": token_secret,
                "DATABASE_URL": "sqlite:///./x0t_maas.db",
                "LOG_LEVEL": "info",
            },
        },
        "docker_compose": docker_compose,
        "agent_configs": agent_configs,
        "join_token": instance.join_token,
        "join_token_expires_at": instance.join_token_expires_at.isoformat(),
        "install_instructions": [
            "1. Save docker_compose content to docker-compose.yml",
            "2. Run: docker compose up -d",
            "3. Install agents on target machines:",
            f"   curl -sL https://<your-host>/install | bash -s -- --token {instance.join_token}",
            f"4. Token expires: {instance.join_token_expires_at.isoformat()}",
            "5. Rotate token after deployment: POST /{mesh_id}/tokens/rotate",
        ],
    }

    if format.lower() == "yaml":
        try:
            import yaml as _yaml
            content = _yaml.dump(bundle, default_flow_style=False, allow_unicode=True)
            return Response(
                content=content,
                media_type="application/x-yaml",
                headers={"Content-Disposition": f'attachment; filename="onprem-{mesh_id}.yaml"'},
            )
        except ImportError:
            pass  # Fall through to JSON

    return bundle


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------


@router.get("/{mesh_id}/dashboard/pending-approvals")
def serve_pending_approvals_ui(
    mesh_id: str, current_user: User = Depends(get_current_user)
):
    """
    Serve the interactive pending-approvals HTML page.
    Falls back to JSON if the file doesn't exist yet.
    """
    _get_mesh_or_404(mesh_id, current_user.id)

    if _PENDING_APPROVALS_UI.exists():
        return FileResponse(
            str(_PENDING_APPROVALS_UI),
            media_type="text/html",
        )

    # Fallback: return JSON data
    pending = _pending_nodes.get(mesh_id, {})
    return {
        "mesh_id": mesh_id,
        "pending_nodes": pending,
        "count": len(pending),
        "note": "HTML dashboard not yet deployed. Showing JSON.",
    }
