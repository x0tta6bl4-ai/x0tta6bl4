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
from fastapi.responses import FileResponse, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import (
    cross_plane_claim_gate_metadata,
    readiness_cross_plane_claim_gate_metadata,
)
from src.api.maas_auth_models import (ApiKeyResponse, TokenResponse,
                                      UserLoginRequest, UserRegisterRequest)
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.reliability_policy import mark_degraded_dependency
from src.database import BillingWebhookEvent, User, get_db, MeshInstance as DBMeshInstance
from src.api.maas_security import api_key_manager, oidc_validator, token_signer
from src.api.maas_auth import require_role, get_current_user_from_maas, require_permission
from src.services.maas_auth_service import MaaSAuthService, find_user_by_api_key
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

_LEGACY_BILLING_SERVICE_NAME = "maas-billing"
_LEGACY_BILLING_SOURCE_AGENT = "maas-legacy-billing"
_LEGACY_BILLING_USAGE_SOURCE_AGENT = "maas-legacy-billing-usage"
_LEGACY_BILLING_LAYER = "billing_webhook_to_commerce_bridge"
_LEGACY_BILLING_USAGE_LAYER = "billing_usage_observed_state"
_LEGACY_HEARTBEAT_SOURCE_AGENT = "maas-legacy-heartbeat"
_LEGACY_HEARTBEAT_LAYER = "api_legacy_heartbeat_observed_state"
_LEGACY_LIFECYCLE_SOURCE_AGENT = "maas-legacy-lifecycle"
_LEGACY_LIFECYCLE_LAYER = "api_legacy_lifecycle_control_action"
_LEGACY_LIFECYCLE_READ_SOURCE_AGENT = "maas-legacy-lifecycle-read"
_LEGACY_LIFECYCLE_READ_LAYER = "api_legacy_lifecycle_observed_state"
_LEGACY_MAPEK_READ_SOURCE_AGENT = "maas-legacy-mapek-read"
_LEGACY_MAPEK_READ_LAYER = "api_legacy_mapek_observed_state"
_LEGACY_NODE_LIFECYCLE_SOURCE_AGENT = "maas-legacy-node-lifecycle"
_LEGACY_NODE_LIFECYCLE_LAYER = "api_legacy_node_lifecycle_control_action"
_LEGACY_NODE_READ_SOURCE_AGENT = "maas-legacy-node-read"
_LEGACY_NODE_READ_LAYER = "api_legacy_node_observed_state"
_LEGACY_TOKEN_LIFECYCLE_SOURCE_AGENT = "maas-legacy-token-lifecycle"
_LEGACY_TOKEN_LIFECYCLE_LAYER = "api_legacy_token_lifecycle_control_action"
_LEGACY_POLICY_LIFECYCLE_SOURCE_AGENT = "maas-legacy-policy-lifecycle"
_LEGACY_POLICY_LIFECYCLE_LAYER = "api_legacy_policy_lifecycle_control_action"
_LEGACY_POLICY_READ_SOURCE_AGENT = "maas-legacy-policy-read"
_LEGACY_POLICY_READ_LAYER = "api_legacy_policy_observed_state"
_LEGACY_BILLING_CLAIM_BOUNDARY = (
    "Legacy MaaS billing webhook evidence only. It records local webhook "
    "validation, idempotency state, and local user plan mutation; it does not "
    "prove provider settlement, bank settlement, or on-chain finality."
)
_LEGACY_BILLING_USAGE_CLAIM_BOUNDARY = (
    "Legacy MaaS billing usage observation only. It records a local read of "
    "in-memory mesh usage counters used for billing visibility; it does not "
    "prove customer payment state, external traffic volume, or provider "
    "settlement."
)
_LEGACY_HEARTBEAT_CLAIM_BOUNDARY = (
    "Legacy MaaS heartbeat evidence only. It records local auth/ownership checks "
    "and in-memory telemetry/MAPE-K mutation summaries for a known mesh node; it "
    "does not prove fresh network reachability, agent identity attestation, "
    "remote execution, escrow settlement, or dataplane health."
)
_LEGACY_LIFECYCLE_CLAIM_BOUNDARY = (
    "Legacy MaaS lifecycle evidence only. It records local quota checks, "
    "in-memory mesh registry mutation, and SQLAlchemy metadata persistence; it "
    "does not prove external node deployment, dataplane reachability, PQC key "
    "material validity, or successful agent enrollment."
)
_LEGACY_LIFECYCLE_READ_CLAIM_BOUNDARY = (
    "Legacy MaaS lifecycle read evidence only. It records bounded local reads of "
    "mesh registry/status/metrics state after auth checks; it does not prove "
    "fresh dataplane health, external node reachability, or agent enrollment."
)
_LEGACY_MAPEK_READ_CLAIM_BOUNDARY = (
    "Legacy MaaS MAPE-K event read evidence only. It records bounded local reads "
    "of the in-memory MAPE-K event buffer after mesh ownership checks; it does "
    "not prove fresh dataplane health, completed autonomous remediation, or "
    "durable event persistence."
)
_LEGACY_NODE_LIFECYCLE_CLAIM_BOUNDARY = (
    "Legacy MaaS node lifecycle evidence only. It records local enrollment-token "
    "checks, pending-node registry mutation, node approval/revocation state, "
    "one-time reissue-token state, and audit-log append attempts; it does not "
    "prove live agent identity, external dataplane reachability, hardware "
    "attestation validity, or that returned join tokens were used by a node."
)
_LEGACY_NODE_READ_CLAIM_BOUNDARY = (
    "Legacy MaaS node read evidence only. It records bounded local reads of "
    "in-memory approved, pending, and revoked node registry state after role and "
    "mesh ownership checks; it does not prove live node reachability, hardware "
    "attestation validity, or external dataplane membership."
)
_LEGACY_TOKEN_LIFECYCLE_CLAIM_BOUNDARY = (
    "Legacy MaaS join-token lifecycle evidence only. It records local in-memory "
    "join-token rotation metadata after mesh ownership checks; it does not prove "
    "token delivery to nodes, live agent enrollment, external dataplane "
    "reachability, or durable database persistence."
)
_LEGACY_POLICY_LIFECYCLE_CLAIM_BOUNDARY = (
    "Legacy MaaS policy lifecycle evidence only. It records local in-memory ACL "
    "policy creation after mesh ownership checks and audit-log append attempts; "
    "it does not prove dataplane policy enforcement, DB-backed policy "
    "persistence, or external node configuration refresh."
)
_LEGACY_POLICY_READ_CLAIM_BOUNDARY = (
    "Legacy MaaS policy read evidence only. It records bounded local reads of "
    "in-memory ACL policy and node-config decision state after available mesh "
    "checks; it does not prove dataplane enforcement, DB-backed policy "
    "persistence, or that nodes refreshed their local configuration."
)

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
    mesh_metrics_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str


_LEGACY_MESH_METRICS_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_LEGACY_MESH_METRICS_CLAIM_BOUNDARY = (
    "Legacy MaaS mesh metrics responses expose local registry, local MAPE-K, "
    "local consciousness, and local network-metric observations only. Latency, "
    "throughput, health, phase, or metric fields do not prove production "
    "readiness, production SLOs, dataplane delivery, customer traffic, external "
    "DPI bypass, or settlement finality."
)


def _legacy_mesh_metrics_claim_gate() -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.legacy_maas_mesh_metrics_claim_gate.v1",
        "surface": "legacy_maas_mesh.metrics",
        "local_mesh_metrics_observation_claim_allowed": True,
        "local_mape_k_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "claim_boundary": _LEGACY_MESH_METRICS_CLAIM_BOUNDARY,
    }


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


def validate_customer(api_key: str, db: Session) -> User:
    """Validate an API key for legacy query-param style callers."""
    user = find_user_by_api_key(db, api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


def _get_mesh_or_404(
    mesh_id: str,
    owner_id: Optional[str] = None,
) -> Any:
    """Resolve a mesh from legacy or modular runtime registries."""
    instance: Any = mesh_provisioner.get(mesh_id)
    if instance is None:
        try:
            from src.api.maas.registry import get_mesh as get_modular_mesh

            instance = get_modular_mesh(mesh_id)
        except Exception:
            instance = None

    if instance is None:
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")

    if owner_id is not None and str(getattr(instance, "owner_id", "")) != str(owner_id):
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")

    return instance


def _model_dump_compat(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if isinstance(model, dict):
        return dict(model)
    return {
        key: getattr(model, key)
        for key in dir(model)
        if not key.startswith("_") and not callable(getattr(model, key, None))
    }


def _current_user_id(current_user: Any) -> str:
    return str(getattr(current_user, "id", getattr(current_user, "user_id", "unknown")))


def _require_owner(mesh_id: str, current_user: Any) -> MeshInstance:
    return _get_mesh_or_404(mesh_id, _current_user_id(current_user))


def _is_join_token_expired(instance: "MeshInstance") -> bool:
    return datetime.utcnow() >= instance.join_token_expires_at


def _is_reissue_token_expired(token_data: Dict[str, Any]) -> bool:
    expires_raw = token_data.get("expires_at")
    if not isinstance(expires_raw, str):
        return True
    try:
        return datetime.utcnow() >= datetime.fromisoformat(expires_raw)
    except ValueError:
        return True


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


def _verify_billing_webhook_secret(provided_secret: Optional[str]) -> None:
    expected_secret = os.getenv("X0T_BILLING_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        return
    if not provided_secret or not secrets.compare_digest(
        provided_secret,
        expected_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid billing webhook secret")


def _verify_billing_webhook_hmac(
    payload: bytes,
    timestamp_header: Optional[str],
    signature_header: Optional[str],
) -> None:
    secret = os.getenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", "").strip()
    if not secret:
        return
    if not timestamp_header or not signature_header:
        raise HTTPException(
            status_code=401,
            detail="Missing HMAC headers: X-Billing-Timestamp and X-Billing-Signature",
        )
    try:
        timestamp_value = int(timestamp_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Billing-Timestamp")
    if abs(int(time.time()) - timestamp_value) > _billing_webhook_tolerance_seconds():
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


def _redacted_sha256_prefix(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _legacy_billing_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize legacy MaaS billing EventBus: %s", exc)
        return None


def _legacy_heartbeat_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize legacy MaaS heartbeat EventBus: %s", exc)
        return None


def _legacy_lifecycle_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize legacy MaaS lifecycle EventBus: %s", exc)
        return None


def _deployment_request_summary(req: MeshDeployRequest) -> Dict[str, Any]:
    return {
        "requested_nodes": req.nodes,
        "billing_plan": req.billing_plan,
        "pqc_enabled": req.pqc_enabled,
        "obfuscation": req.obfuscation,
        "traffic_profile": req.traffic_profile,
        "join_token_ttl_sec": req.join_token_ttl_sec,
        "mesh_name_present": bool(req.name),
    }


def _publish_legacy_lifecycle_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    req: MeshDeployRequest,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    node_count: Optional[int] = None,
    registry_mutated: bool = False,
    db_persisted: bool = False,
    join_token_issued: bool = False,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "legacy_mesh_deploy",
        "service_name": _LEGACY_LIFECYCLE_SOURCE_AGENT,
        "source_alias": _LEGACY_LIFECYCLE_SOURCE_AGENT,
        "layer": _LEGACY_LIFECYCLE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _deployment_request_summary(req),
        "node_count": node_count,
        "registry_mutated": registry_mutated,
        "db_persisted": db_persisted,
        "join_token_issued": join_token_issued,
        "safe_actuator": False,
        "read_only": not (registry_mutated or db_persisted),
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_LIFECYCLE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_LIFECYCLE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS lifecycle event: %s", exc)
        return None


def _mesh_list_summary_for_evidence(meshes: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_nodes = 0
    healthy_nodes = 0
    status_counts: Dict[str, int] = {}
    for mesh in meshes:
        total_nodes += int(mesh.get("nodes_total") or 0)
        healthy_nodes += int(mesh.get("nodes_healthy") or 0)
        status_value = str(mesh.get("status") or "unknown")[:40]
        status_counts[status_value] = status_counts.get(status_value, 0) + 1
    return {
        "mesh_count": len(meshes),
        "total_nodes": total_nodes,
        "healthy_nodes": healthy_nodes,
        "status_counts": status_counts,
    }


def _mesh_status_summary_for_evidence(
    response: MeshStatusResponse,
) -> Dict[str, Any]:
    data = _model_dump_compat(response)
    peers = data.get("peers") if isinstance(data.get("peers"), list) else []
    return {
        "status": str(data.get("status") or "unknown")[:40],
        "nodes_total": int(data.get("nodes_total") or 0),
        "nodes_healthy": int(data.get("nodes_healthy") or 0),
        "peer_count": len(peers),
        "pqc_enabled": bool(data.get("pqc_enabled")),
        "obfuscation": str(data.get("obfuscation") or "")[:40],
        "traffic_profile": str(data.get("traffic_profile") or "")[:40],
        "health_score": data.get("health_score"),
    }


def _mesh_metrics_summary_for_evidence(
    response: MeshMetricsResponse,
) -> Dict[str, Any]:
    data = _model_dump_compat(response)
    consciousness = (
        data.get("consciousness") if isinstance(data.get("consciousness"), dict) else {}
    )
    mape_k = data.get("mape_k") if isinstance(data.get("mape_k"), dict) else {}
    network = data.get("network") if isinstance(data.get("network"), dict) else {}
    claim_gate = (
        data.get("mesh_metrics_claim_gate")
        if isinstance(data.get("mesh_metrics_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        data.get("cross_plane_claim_gate")
        if isinstance(data.get("cross_plane_claim_gate"), dict)
        else {}
    )
    return {
        "consciousness_metric_count": len(consciousness),
        "mape_k_metric_count": len(mape_k),
        "network_metric_count": len(network),
        "mesh_metrics_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "production_readiness_claim_allowed": (
            claim_gate.get("production_readiness_claim_allowed")
            if isinstance(
                claim_gate.get("production_readiness_claim_allowed"), bool
            )
            else None
        ),
        "dataplane_delivery_claim_allowed": (
            claim_gate.get("dataplane_delivery_claim_allowed")
            if isinstance(claim_gate.get("dataplane_delivery_claim_allowed"), bool)
            else None
        ),
        "external_dpi_bypass_claim_allowed": (
            claim_gate.get("external_dpi_bypass_claim_allowed")
            if isinstance(claim_gate.get("external_dpi_bypass_claim_allowed"), bool)
            else None
        ),
        "has_timestamp": bool(data.get("timestamp")),
    }


def _publish_legacy_lifecycle_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    read_scope: str,
    mesh_count: Optional[int] = None,
    node_count: Optional[int] = None,
    healthy_node_count: Optional[int] = None,
    registry_source: str = "legacy_registry",
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": operation,
        "service_name": _LEGACY_LIFECYCLE_READ_SOURCE_AGENT,
        "source_alias": _LEGACY_LIFECYCLE_READ_SOURCE_AGENT,
        "layer": _LEGACY_LIFECYCLE_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": str(read_scope or "")[:80],
        "mesh_count": mesh_count,
        "node_count": node_count,
        "healthy_node_count": healthy_node_count,
        "registry_source": str(registry_source or "")[:80],
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_LIFECYCLE_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_LIFECYCLE_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS lifecycle read event: %s", exc)
        return None


def _mapek_events_summary_for_evidence(
    events: List[Dict[str, Any]],
    *,
    limit_requested: int,
    stored_event_count: int,
) -> Dict[str, Any]:
    phase_counts: Dict[str, int] = {}
    event_type_counts: Dict[str, int] = {}
    known_metric_mentions = 0
    node_id_mentions = 0
    timestamp_mentions = 0
    total_field_count = 0
    known_phases = {"MONITOR", "ANALYZE", "PLAN", "EXECUTE", "KNOWLEDGE"}
    known_event_types = {"node.heartbeat"}
    known_metric_fields = {
        "cpu_usage",
        "memory_usage",
        "neighbors_count",
        "routing_table_size",
        "uptime",
    }

    for event in events:
        if not isinstance(event, dict):
            continue
        total_field_count += len(event)
        phase = str(event.get("phase") or "unknown").upper()
        phase_bucket = phase if phase in known_phases else "other"
        phase_counts[phase_bucket] = phase_counts.get(phase_bucket, 0) + 1

        event_type = str(event.get("event_type") or "unknown")
        event_type_bucket = event_type if event_type in known_event_types else "other"
        event_type_counts[event_type_bucket] = (
            event_type_counts.get(event_type_bucket, 0) + 1
        )

        if event.get("node_id"):
            node_id_mentions += 1
        if event.get("timestamp"):
            timestamp_mentions += 1
        known_metric_mentions += sum(
            1 for field_name in known_metric_fields if field_name in event
        )

    return {
        "returned_event_count": len(events),
        "stored_event_count": stored_event_count,
        "limit_requested": limit_requested,
        "phase_counts": phase_counts,
        "event_type_counts": event_type_counts,
        "node_id_mentions": node_id_mentions,
        "timestamp_mentions": timestamp_mentions,
        "known_metric_mentions": known_metric_mentions,
        "total_field_count": total_field_count,
    }


def _publish_legacy_mapek_read_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    read_scope: str,
    limit_requested: int,
    stored_event_count: Optional[int] = None,
    returned_event_count: Optional[int] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "legacy_mapek_event_read",
        "service_name": _LEGACY_MAPEK_READ_SOURCE_AGENT,
        "source_alias": _LEGACY_MAPEK_READ_SOURCE_AGENT,
        "layer": _LEGACY_MAPEK_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": str(read_scope or "")[:80],
        "limit_requested": limit_requested,
        "stored_event_count": stored_event_count,
        "returned_event_count": returned_event_count,
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_MAPEK_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_MAPEK_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS MAPE-K read event: %s", exc)
        return None


def _node_register_request_summary_for_evidence(
    req: NodeRegisterRequest,
    *,
    enrollment_token_type: str = "unknown",
) -> Dict[str, Any]:
    attestation_data = (
        req.attestation_data if isinstance(req.attestation_data, dict) else {}
    )
    return {
        "device_class": req.device_class,
        "requested_node_id_present": bool(req.node_id),
        "enrollment_token_type": enrollment_token_type,
        "label_count": len(req.labels),
        "public_key_count": len(req.public_keys),
        "has_hardware_id": bool(req.hardware_id),
        "has_attestation_data": bool(attestation_data),
        "attestation_field_count": len(attestation_data),
        "enclave_enabled": bool(req.enclave_enabled),
    }


def _node_approve_request_summary_for_evidence(
    req: NodeApproveRequest,
    *,
    pending: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pending_data = pending if isinstance(pending, dict) else {}
    return {
        "acl_profile": req.acl_profile,
        "tag_count": len(req.tags),
        "pending_device_class": str(pending_data.get("device_class", ""))[:40],
        "pending_label_count": (
            len(pending_data.get("labels", {}))
            if isinstance(pending_data.get("labels"), dict)
            else 0
        ),
        "pending_public_key_count": (
            len(pending_data.get("public_keys", {}))
            if isinstance(pending_data.get("public_keys"), dict)
            else 0
        ),
        "pending_has_hardware_id": bool(pending_data.get("hardware_id")),
        "pending_enclave_enabled": bool(pending_data.get("enclave_enabled", False)),
    }


def _node_revoke_request_summary_for_evidence(
    req: NodeRevokeRequest,
) -> Dict[str, Any]:
    reason = str(req.reason or "")
    return {
        "body_node_id_present": bool(req.node_id),
        "reason_present": bool(reason),
        "reason_length": len(reason),
    }


def _node_reissue_request_summary_for_evidence(
    req: NodeReissueTokenRequest,
) -> Dict[str, Any]:
    return {"ttl_seconds": req.ttl_seconds}


def _publish_legacy_node_lifecycle_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    node_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    request_summary: Optional[Dict[str, Any]] = None,
    pending_registry_mutated: bool = False,
    node_registry_mutated: bool = False,
    revoked_registry_mutated: bool = False,
    reissue_token_mutated: bool = False,
    reissue_token_used: bool = False,
    audit_recorded: bool = False,
    join_token_issued: bool = False,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": operation,
        "service_name": _LEGACY_NODE_LIFECYCLE_SOURCE_AGENT,
        "source_alias": _LEGACY_NODE_LIFECYCLE_SOURCE_AGENT,
        "layer": _LEGACY_NODE_LIFECYCLE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": request_summary or {},
        "pending_registry_mutated": pending_registry_mutated,
        "node_registry_mutated": node_registry_mutated,
        "revoked_registry_mutated": revoked_registry_mutated,
        "reissue_token_mutated": reissue_token_mutated,
        "reissue_token_used": reissue_token_used,
        "audit_recorded": audit_recorded,
        "join_token_issued": join_token_issued,
        "read_only": False,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_NODE_LIFECYCLE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_NODE_LIFECYCLE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS node lifecycle event: %s", exc)
        return None


def _node_read_summary_for_evidence(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_device_class: Dict[str, int] = {}
    tag_entries = 0
    for node in nodes:
        status_value = str(node.get("status") or "unknown")[:40]
        by_status[status_value] = by_status.get(status_value, 0) + 1
        device_class = str(node.get("device_class") or "unknown")[:40]
        by_device_class[device_class] = by_device_class.get(device_class, 0) + 1
        tags = node.get("tags")
        if isinstance(tags, list):
            tag_entries += len(tags)
    return {
        "node_count": len(nodes),
        "by_status": by_status,
        "by_device_class": by_device_class,
        "tag_entry_count": tag_entries,
    }


def _publish_legacy_node_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    read_scope: str,
    node_status_filter: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": operation,
        "service_name": _LEGACY_NODE_READ_SOURCE_AGENT,
        "source_alias": _LEGACY_NODE_READ_SOURCE_AGENT,
        "layer": _LEGACY_NODE_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": str(read_scope or "")[:80],
        "node_status_filter": (
            str(node_status_filter)[:40] if node_status_filter is not None else None
        ),
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_NODE_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_NODE_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS node read event: %s", exc)
        return None


def _publish_legacy_token_lifecycle_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    ttl_seconds: Optional[int] = None,
    token_rotated: bool = False,
    join_token_issued: bool = False,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "legacy_join_token_rotate",
        "service_name": _LEGACY_TOKEN_LIFECYCLE_SOURCE_AGENT,
        "source_alias": _LEGACY_TOKEN_LIFECYCLE_SOURCE_AGENT,
        "layer": _LEGACY_TOKEN_LIFECYCLE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": {
            "ttl_seconds": ttl_seconds,
            "owner_check_required": current_user is not None,
        },
        "token_rotated": token_rotated,
        "join_token_issued": join_token_issued,
        "read_only": False,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_TOKEN_LIFECYCLE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_TOKEN_LIFECYCLE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS token lifecycle event: %s", exc)
        return None


def _policy_request_summary_for_evidence(
    req: PolicyRequest,
    *,
    policy_id: Optional[Any] = None,
) -> Dict[str, Any]:
    return {
        "policy_id_hash": _redacted_sha256_prefix(policy_id),
        "source_tag_hash": _redacted_sha256_prefix(req.source_tag),
        "target_tag_hash": _redacted_sha256_prefix(req.target_tag),
        "action": req.action,
        "source_tag_present": bool(req.source_tag),
        "target_tag_present": bool(req.target_tag),
    }


def _publish_legacy_policy_lifecycle_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    req: PolicyRequest,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    policy_id: Optional[Any] = None,
    policy_registry_mutated: bool = False,
    audit_recorded: bool = False,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "legacy_policy_create",
        "service_name": _LEGACY_POLICY_LIFECYCLE_SOURCE_AGENT,
        "source_alias": _LEGACY_POLICY_LIFECYCLE_SOURCE_AGENT,
        "layer": _LEGACY_POLICY_LIFECYCLE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _policy_request_summary_for_evidence(
            req,
            policy_id=policy_id,
        ),
        "policy_registry_mutated": policy_registry_mutated,
        "audit_recorded": audit_recorded,
        "read_only": False,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_POLICY_LIFECYCLE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_POLICY_LIFECYCLE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS policy lifecycle event: %s", exc)
        return None


def _policy_list_summary_for_evidence(
    policies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    action_counts: Dict[str, int] = {}
    for policy in policies:
        action = str(policy.get("action") or "unknown")[:40]
        action_counts[action] = action_counts.get(action, 0) + 1
    return {
        "policy_count": len(policies),
        "action_counts": action_counts,
    }


def _node_config_summary_for_evidence(config: Dict[str, Any]) -> Dict[str, Any]:
    policy_decisions = (
        config.get("policy_decisions")
        if isinstance(config.get("policy_decisions"), dict)
        else {}
    )
    decision_action_counts: Dict[str, int] = {}
    explicit_policy_count = 0
    for decision in policy_decisions.values():
        if not isinstance(decision, dict):
            continue
        action = str(decision.get("action") or "unknown")[:40]
        decision_action_counts[action] = decision_action_counts.get(action, 0) + 1
        if decision.get("reason") == "explicit_policy":
            explicit_policy_count += 1
    allowed_peers = (
        config.get("allowed_peers") if isinstance(config.get("allowed_peers"), list) else []
    )
    denied_peers = (
        config.get("denied_peers") if isinstance(config.get("denied_peers"), list) else []
    )
    return {
        "allowed_peer_count": len(allowed_peers),
        "denied_peer_count": len(denied_peers),
        "decision_count": len(policy_decisions),
        "explicit_policy_decision_count": explicit_policy_count,
        "decision_action_counts": decision_action_counts,
    }


def _publish_legacy_policy_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    node_id: Optional[Any] = None,
    read_scope: str,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_lifecycle_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": operation,
        "service_name": _LEGACY_POLICY_READ_SOURCE_AGENT,
        "source_alias": _LEGACY_POLICY_READ_SOURCE_AGENT,
        "layer": _LEGACY_POLICY_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": str(read_scope or "")[:80],
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_POLICY_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_POLICY_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS policy read event: %s", exc)
        return None


def _heartbeat_summary_for_evidence(req: NodeHeartbeatRequest) -> Dict[str, Any]:
    return {
        "payload_type": type(req).__name__,
        "numeric_fields": [
            "cpu_usage",
            "memory_usage",
            "neighbors_count",
            "routing_table_size",
            "uptime",
        ],
        "numeric_field_count": 5,
        "has_pheromones": isinstance(getattr(req, "pheromones", None), dict),
        "pheromone_destination_count": (
            len(req.pheromones) if isinstance(req.pheromones, dict) else 0
        ),
        "raw_metric_values_redacted": True,
        "payloads_redacted": True,
    }


def _publish_legacy_heartbeat_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    req: NodeHeartbeatRequest,
    current_user: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    node_found: bool = False,
    owner_checked: bool = False,
    authorized: bool = False,
    stored_telemetry: bool = False,
    mapek_event_recorded: bool = False,
    duration_ms: Optional[float] = None,
    telemetry_store_summary: Optional[Dict[str, Any]] = None,
    mapek_store_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_heartbeat_event_bus_from_request(request)
    if event_bus is None:
        return None

    if stored_telemetry and mapek_event_recorded:
        source_quality = "legacy_in_memory_telemetry_and_mapek"
    elif stored_telemetry:
        source_quality = "legacy_in_memory_telemetry_only"
    else:
        source_quality = "denied_before_state_mutation"

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "legacy_heartbeat",
        "service_name": _LEGACY_HEARTBEAT_SOURCE_AGENT,
        "source_alias": _LEGACY_HEARTBEAT_SOURCE_AGENT,
        "layer": _LEGACY_HEARTBEAT_LAYER,
        "status": status,
        "node_id_hash": _redacted_sha256_prefix(req.node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(_current_user_id(current_user))
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "node_found": node_found,
        "owner_checked": owner_checked,
        "authorized": authorized,
        "stored_telemetry": stored_telemetry,
        "mapek_event_recorded": mapek_event_recorded,
        "duration_ms": (
            round(float(duration_ms), 3) if duration_ms is not None else None
        ),
        "storage_backend": "legacy_in_memory",
        "source_quality": source_quality,
        "dataplane_confirmed": False,
        "read_only": not stored_telemetry,
        "observed_state": True,
        "safe_actuator": False,
        "heartbeat_summary": _heartbeat_summary_for_evidence(req),
        "telemetry_store_summary": telemetry_store_summary or {},
        "mapek_store_summary": mapek_store_summary or {},
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_HEARTBEAT_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_HEARTBEAT_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS heartbeat event: %s", exc)
        return None


def _publish_legacy_billing_webhook_event(
    request: Optional[Request],
    *,
    stage: str,
    req: BillingWebhookRequest,
    event_id: Optional[str],
    payload_hash: Optional[str],
    status: str,
    user_id: Optional[Any] = None,
    plan_before: Optional[str] = None,
    plan_after: Optional[str] = None,
    reason: str = "",
    idempotent_replay: bool = False,
) -> Optional[str]:
    event_bus = _legacy_billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": stage,
        "operation": "billing_webhook",
        "service_name": _LEGACY_BILLING_SERVICE_NAME,
        "source_alias": _LEGACY_BILLING_SOURCE_AGENT,
        "layer": _LEGACY_BILLING_LAYER,
        "billing_event_type": req.event_type,
        "billing_event_id_hash": _redacted_sha256_prefix(event_id),
        "payload_sha256": payload_hash,
        "user_id_hash": _redacted_sha256_prefix(user_id or req.user_id),
        "customer_id_hash": _redacted_sha256_prefix(req.customer_id),
        "subscription_id_hash": _redacted_sha256_prefix(req.subscription_id),
        "email_hash": _redacted_sha256_prefix(req.email.lower() if req.email else None),
        "plan_before": plan_before,
        "plan_after": plan_after,
        "status": status,
        "reason": str(reason or "")[:160],
        "idempotent_replay": idempotent_replay,
        "idempotency_recorded": True,
        "raw_identifiers_redacted": True,
        "claim_boundary": _LEGACY_BILLING_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_BILLING_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS billing webhook event: %s", exc)
        return None


def _billing_usage_summary_for_evidence(
    usage: Optional[Dict[str, Any]],
    *,
    scope: str,
) -> Dict[str, Any]:
    if not isinstance(usage, dict):
        return {}
    summary: Dict[str, Any] = {
        "scope": scope,
        "total_node_hours": usage.get("total_node_hours"),
    }
    if scope == "mesh":
        nodes = usage.get("nodes") if isinstance(usage.get("nodes"), list) else []
        summary.update(
            {
                "status": usage.get("status"),
                "active_nodes": usage.get("active_nodes"),
                "node_entries": len(nodes),
            }
        )
    else:
        meshes = usage.get("meshes") if isinstance(usage.get("meshes"), list) else []
        summary.update(
            {
                "mesh_count": usage.get("mesh_count"),
                "mesh_entries": len(meshes),
            }
        )
    return summary


def _publish_legacy_billing_usage_observation(
    request: Optional[Request],
    *,
    scope: str,
    owner_id: Optional[Any],
    mesh_id: Optional[Any] = None,
    usage: Optional[Dict[str, Any]] = None,
    status: str = "success",
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _legacy_billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_legacy",
        "stage": "observed_state",
        "operation": "billing_usage_read",
        "service_name": _LEGACY_BILLING_SERVICE_NAME,
        "source_alias": _LEGACY_BILLING_USAGE_SOURCE_AGENT,
        "layer": _LEGACY_BILLING_USAGE_LAYER,
        "scope": scope,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "usage_summary": _billing_usage_summary_for_evidence(usage, scope=scope),
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _LEGACY_BILLING_USAGE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _LEGACY_BILLING_USAGE_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish legacy MaaS billing usage event: %s", exc)
        return None


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
    return loaded if isinstance(loaded, dict) else None


def _cleanup_expired_billing_events(db: Session) -> None:
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
    _cleanup_expired_billing_events(db)
    existing = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail="Billing webhook event_id payload mismatch",
            )
        if existing.status == "done":
            return _deserialize_billing_event_response(existing.response_json) or {}
        if existing.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="Billing webhook event is already being processed",
            )
        raise HTTPException(
            status_code=409,
            detail="Billing webhook event previously failed",
        )

    try:
        db.add(
            BillingWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                status="processing",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Billing webhook event is already being processed",
        ) from exc
    return None


def _finalize_billing_event_processing(
    db: Session,
    event_id: str,
    response_payload: Dict[str, Any],
) -> None:
    row = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if row is None:
        raise RuntimeError("Billing event reservation missing")
    row.status = "done"
    row.response_json = json.dumps(response_payload)
    row.last_error = None
    row.processed_at = datetime.utcnow()
    db.commit()


def _fail_billing_event_processing(
    db: Session,
    event_id: str,
    error: str,
) -> None:
    row = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if row is None:
        return
    row.status = "failed"
    row.last_error = str(error)[:2000]
    row.processed_at = datetime.utcnow()
    db.commit()


def _resolve_billing_user(
    db: Session,
    req: BillingWebhookRequest,
) -> Optional[User]:
    metadata = req.metadata if isinstance(req.metadata, dict) else {}
    user_id = req.user_id or metadata.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            return user
    if req.customer_id:
        user = db.query(User).filter(User.stripe_customer_id == req.customer_id).first()
        if user is not None:
            return user
    if req.email:
        user = db.query(User).filter(User.email == req.email).first()
        if user is not None:
            return user
    return None


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
    matched_rules = [
        policy
        for policy in policies
        if _rule_matches(
            source_tags,
            target_tags,
            str(policy.get("source_tag", "")),
            str(policy.get("target_tag", "")),
        )
    ]
    if acl_profile == "isolated":
        return {"action": "deny", "reason": "acl_profile_isolated", "rules": []}
    if any(rule.get("action") == "deny" for rule in matched_rules):
        return {"action": "deny", "reason": "explicit_deny", "rules": matched_rules}
    if any(rule.get("action") == "allow" for rule in matched_rules):
        return {"action": "allow", "reason": "explicit_allow", "rules": matched_rules}
    if not policies and acl_profile == "default":
        return {"action": "allow", "reason": "legacy_open_mesh", "rules": []}
    return {"action": "deny", "reason": "default_deny_zero_trust", "rules": []}


def _find_mesh_id_for_node(node_id: str) -> Optional[str]:
    for mesh_id, instance in _mesh_registry.items():
        if node_id in getattr(instance, "node_instances", {}):
            return mesh_id
    return None


def _build_mapek_heartbeat_event(telemetry: NodeHeartbeatRequest) -> Dict[str, Any]:
    signals = {
        "cpu_usage": telemetry.cpu_usage,
        "memory_usage": telemetry.memory_usage,
        "neighbors_count": telemetry.neighbors_count,
        "routing_table_size": telemetry.routing_table_size,
        "uptime": telemetry.uptime,
    }
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
        "event_id": f"mapek-{uuid.uuid4().hex[:12]}",
        "phase": "MONITOR",
        "node_id": telemetry.node_id,
        "health_state": health_state,
        "recommendation": recommendation,
        "signals": signals,
        **signals,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _reissue_token_data(
    mesh_id: str,
    token: Optional[str],
    node_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    token_data = _mesh_reissue_tokens.get(mesh_id, {}).get(token)
    if not token_data:
        return None
    if token_data.get("used"):
        return None
    if node_id and token_data.get("node_id") != node_id:
        return None
    try:
        expires_at = datetime.fromisoformat(str(token_data.get("expires_at", "")))
    except ValueError:
        return None
    if datetime.utcnow() >= expires_at:
        return None
    return token_data


async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User,
    db: Session,
    request: Optional[Request] = None,
) -> MeshDeployResponse:
    """Legacy public deploy API backed by the current in-memory provisioner."""
    try:
        billing_service.check_quota(
            current_user,
            int(req.nodes),
            requested_plan=req.billing_plan,
        )
    except Exception as exc:
        _publish_legacy_lifecycle_event(
            request,
            stage="quota_rejected",
            status="failed",
            req=req,
            current_user=current_user,
            owner_id=_current_user_id(current_user),
            registry_mutated=False,
            db_persisted=False,
            join_token_issued=False,
            reason="quota_rejected",
        )
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    instance = await mesh_provisioner.create(
        user=current_user,
        name=req.name,
        nodes=req.nodes,
        pqc_enabled=req.pqc_enabled,
        obfuscation=req.obfuscation,
        traffic_profile=req.traffic_profile,
        join_token_ttl_sec=req.join_token_ttl_sec,
    )
    instance.plan = req.billing_plan
    instance.pqc_profile = "edge"

    db_mesh = DBMeshInstance(
        id=instance.mesh_id,
        name=instance.name,
        owner_id=_current_user_id(current_user),
        plan=req.billing_plan,
        region="global",
        nodes=req.nodes,
        pqc_profile="edge",
        status=instance.status,
        join_token=instance.join_token,
        join_token_expires_at=instance.join_token_expires_at,
        pqc_enabled=instance.pqc_enabled,
        obfuscation=instance.obfuscation,
        traffic_profile=instance.traffic_profile,
    )
    try:
        db.add(db_mesh)
        db.commit()
    except Exception as exc:
        db.rollback()
        async with _registry_lock:
            _mesh_registry.pop(instance.mesh_id, None)
        _publish_legacy_lifecycle_event(
            request,
            stage="db_persist_failed",
            status="failed",
            req=req,
            current_user=current_user,
            mesh_id=instance.mesh_id,
            owner_id=_current_user_id(current_user),
            node_count=len(getattr(instance, "node_instances", {}) or {}),
            registry_mutated=True,
            db_persisted=False,
            join_token_issued=bool(getattr(instance, "join_token", None)),
            reason="db_persist_failed",
        )
        raise HTTPException(
            status_code=500,
            detail="Mesh creation failed - database persistence error.",
        ) from exc

    _publish_legacy_lifecycle_event(
        request,
        stage="deployed",
        status="success",
        req=req,
        current_user=current_user,
        mesh_id=instance.mesh_id,
        owner_id=_current_user_id(current_user),
        node_count=len(getattr(instance, "node_instances", {}) or {}),
        registry_mutated=True,
        db_persisted=True,
        join_token_issued=bool(getattr(instance, "join_token", None)),
        reason="deployed",
    )

    return MeshDeployResponse(
        mesh_id=instance.mesh_id,
        join_config={
            "token": instance.join_token,
            "enrollment_token": instance.join_token,
            "ttl_sec": instance.join_token_ttl_sec,
        },
        dashboard_url=f"/api/v1/maas/{instance.mesh_id}/status",
        status=instance.status,
        pqc_identity={
            "enabled": instance.pqc_enabled,
            "did": f"did:x0t:{instance.mesh_id}",
            "profile": "edge",
            "keys": {
                "sig_alg": "ML-DSA-65",
                "kem_alg": "ML-KEM-768",
            },
        },
        pqc_enabled=instance.pqc_enabled,
        created_at=instance.created_at.isoformat(),
        plan=req.billing_plan,
        join_token_expires_at=instance.join_token_expires_at.isoformat(),
    )


async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    request: Optional[Request] = None,
) -> NodeRegisterResponse:
    """Register a node against a legacy mesh join or one-time reissue token."""
    try:
        instance = _get_mesh_or_404(mesh_id)
    except HTTPException:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_register",
            stage="mesh_lookup_denied",
            status="denied",
            mesh_id=mesh_id,
            node_id=req.node_id,
            request_summary=_node_register_request_summary_for_evidence(req),
            reason="mesh_not_found",
        )
        raise
    node_id = req.node_id or f"node-{uuid.uuid4().hex[:8]}"
    reissue_data = _reissue_token_data(mesh_id, req.enrollment_token, node_id)
    enrollment_token_type = "reissue" if reissue_data else "mesh_join"

    if reissue_data is None:
        if req.enrollment_token != instance.join_token:
            _publish_legacy_node_lifecycle_event(
                request,
                operation="legacy_node_register",
                stage="registration_denied",
                status="denied",
                mesh_id=mesh_id,
                node_id=node_id,
                owner_id=getattr(instance, "owner_id", None),
                request_summary=_node_register_request_summary_for_evidence(
                    req,
                    enrollment_token_type=enrollment_token_type,
                ),
                reason="invalid_enrollment_token",
            )
            raise HTTPException(status_code=401, detail="Invalid enrollment token")
        if _is_join_token_expired(instance):
            _publish_legacy_node_lifecycle_event(
                request,
                operation="legacy_node_register",
                stage="registration_denied",
                status="denied",
                mesh_id=mesh_id,
                node_id=node_id,
                owner_id=getattr(instance, "owner_id", None),
                request_summary=_node_register_request_summary_for_evidence(
                    req,
                    enrollment_token_type=enrollment_token_type,
                ),
                reason="enrollment_token_expired",
            )
            raise HTTPException(status_code=401, detail="Enrollment token expired")
    else:
        reissue_data["used"] = True
        _revoked_nodes.get(mesh_id, {}).pop(node_id, None)

    if node_id in _pending_nodes.get(mesh_id, {}):
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_register",
            stage="registration_denied",
            status="denied",
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_register_request_summary_for_evidence(
                req,
                enrollment_token_type=enrollment_token_type,
            ),
            revoked_registry_mutated=bool(reissue_data),
            reissue_token_used=bool(reissue_data),
            reason="node_already_pending",
        )
        raise HTTPException(status_code=409, detail=f"Node {node_id} already pending")

    _pending_nodes.setdefault(mesh_id, {})[node_id] = {
        "node_id": node_id,
        "device_class": req.device_class,
        "labels": dict(req.labels),
        "public_keys": dict(req.public_keys),
        "hardware_id": req.hardware_id,
        "attestation_data": req.attestation_data or {},
        "enclave_enabled": req.enclave_enabled,
        "requested_at": datetime.utcnow().isoformat(),
        "enrollment_token_type": "reissue" if reissue_data else "mesh_join",
    }
    _audit(mesh_id, node_id, "node.register", "Node registration pending approval")
    _publish_legacy_node_lifecycle_event(
        request,
        operation="legacy_node_register",
        stage="registration_pending",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary=_node_register_request_summary_for_evidence(
            req,
            enrollment_token_type=enrollment_token_type,
        ),
        pending_registry_mutated=True,
        revoked_registry_mutated=bool(reissue_data),
        reissue_token_used=bool(reissue_data),
        audit_recorded=True,
        reason="registration_pending",
    )

    return NodeRegisterResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="pending_approval",
        message="Node registration pending approval",
    )


async def approve_node(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest,
    current_user: User,
    request: Optional[Request] = None,
) -> NodeApproveResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_approve",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            request_summary=_node_approve_request_summary_for_evidence(req),
            reason="mesh_not_found_or_forbidden",
        )
        raise
    pending = _pending_nodes.get(mesh_id, {}).pop(node_id, None)
    if pending is None:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_approve",
            stage="pending_not_found",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_approve_request_summary_for_evidence(req),
            reason="pending_node_not_found",
        )
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    approved_at = datetime.utcnow()
    device_class = str(pending.get("device_class", "edge"))
    node_join_token = secrets.token_urlsafe(32)
    instance.node_instances[node_id] = {
        "id": node_id,
        "status": "healthy",
        "started_at": approved_at.isoformat(),
        "latency_ms": 0.0,
        "device_class": device_class,
        "labels": pending.get("labels", {}),
        "tags": list(req.tags),
        "acl_profile": req.acl_profile,
        "public_keys": pending.get("public_keys", {}),
        "hardware_id": pending.get("hardware_id"),
        "enclave_enabled": bool(pending.get("enclave_enabled", False)),
        "pqc_profile": _get_pqc_profile(device_class),
    }
    _revoked_nodes.get(mesh_id, {}).pop(node_id, None)
    _audit(mesh_id, _current_user_id(current_user), "node.approve", f"Approved {node_id}")
    try:
        signed_join_token = token_signer.sign_token(node_join_token, mesh_id)
    except Exception:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_approve",
            stage="join_token_issue_failed",
            status="failed",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_approve_request_summary_for_evidence(
                req,
                pending=pending,
            ),
            pending_registry_mutated=True,
            node_registry_mutated=True,
            revoked_registry_mutated=True,
            audit_recorded=True,
            join_token_issued=False,
            reason="join_token_issue_failed",
        )
        raise
    _publish_legacy_node_lifecycle_event(
        request,
        operation="legacy_node_approve",
        stage="approved",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary=_node_approve_request_summary_for_evidence(
            req,
            pending=pending,
        ),
        pending_registry_mutated=True,
        node_registry_mutated=True,
        revoked_registry_mutated=True,
        audit_recorded=True,
        join_token_issued=True,
        reason="node_approved",
    )

    return NodeApproveResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="approved",
        join_token=signed_join_token,
        approved_at=approved_at.isoformat(),
    )


async def revoke_node(
    mesh_id: str,
    node_id: str,
    req: NodeRevokeRequest,
    current_user: User,
    request: Optional[Request] = None,
) -> NodeRevokeResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_revoke",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            request_summary=_node_revoke_request_summary_for_evidence(req),
            reason="mesh_not_found_or_forbidden",
        )
        raise
    if node_id not in instance.node_instances:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_revoke",
            stage="node_not_found",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_revoke_request_summary_for_evidence(req),
            reason="node_not_found",
        )
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    revoked_at = datetime.utcnow().isoformat()
    instance.node_instances[node_id]["status"] = "revoked"
    _revoked_nodes.setdefault(mesh_id, {})[node_id] = {
        "reason": req.reason,
        "revoked_at": revoked_at,
        "revoked_by": _current_user_id(current_user),
    }
    _audit(mesh_id, _current_user_id(current_user), "node.revoke", req.reason)
    _publish_legacy_node_lifecycle_event(
        request,
        operation="legacy_node_revoke",
        stage="revoked",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary=_node_revoke_request_summary_for_evidence(req),
        node_registry_mutated=True,
        revoked_registry_mutated=True,
        audit_recorded=True,
        reason="node_revoked",
    )
    return NodeRevokeResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="revoked",
        reason=req.reason,
        revoked_at=revoked_at,
    )


async def reissue_node_token(
    mesh_id: str,
    node_id: str,
    req: NodeReissueTokenRequest,
    current_user: User,
    request: Optional[Request] = None,
) -> NodeReissueTokenResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_reissue_token",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            request_summary=_node_reissue_request_summary_for_evidence(req),
            reason="mesh_not_found_or_forbidden",
        )
        raise
    if (
        node_id not in instance.node_instances
        and node_id not in _revoked_nodes.get(mesh_id, {})
    ):
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_reissue_token",
            stage="node_not_found",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_reissue_request_summary_for_evidence(req),
            reason="node_not_found",
        )
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(seconds=req.ttl_seconds)
    token = secrets.token_urlsafe(32)
    _mesh_reissue_tokens.setdefault(mesh_id, {})[token] = {
        "node_id": node_id,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "used": False,
        "issued_by": _current_user_id(current_user),
    }
    _audit(mesh_id, _current_user_id(current_user), "node.reissue_token", node_id)
    try:
        signed_token = token_signer.sign_token(token, mesh_id)
    except Exception:
        _publish_legacy_node_lifecycle_event(
            request,
            operation="legacy_node_reissue_token",
            stage="join_token_issue_failed",
            status="failed",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            request_summary=_node_reissue_request_summary_for_evidence(req),
            reissue_token_mutated=True,
            audit_recorded=True,
            join_token_issued=False,
            reason="join_token_issue_failed",
        )
        raise
    _publish_legacy_node_lifecycle_event(
        request,
        operation="legacy_node_reissue_token",
        stage="reissue_token_issued",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary=_node_reissue_request_summary_for_evidence(req),
        reissue_token_mutated=True,
        audit_recorded=True,
        join_token_issued=True,
        reason="reissue_token_issued",
    )
    return NodeReissueTokenResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        join_token=signed_token,
        issued_at=issued_at.isoformat(),
        expires_at=expires_at.isoformat(),
    )


def rotate_join_token(
    mesh_id: str,
    ttl_seconds: int = 604800,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
) -> TokenRotateResponse:
    try:
        instance = (
            _require_owner(mesh_id, current_user)
            if current_user is not None
            else _get_mesh_or_404(mesh_id)
        )
    except HTTPException:
        _publish_legacy_token_lifecycle_event(
            request,
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            ttl_seconds=ttl_seconds,
            token_rotated=False,
            join_token_issued=False,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    instance.join_token = secrets.token_urlsafe(32)
    instance.join_token_issued_at = issued_at
    instance.join_token_expires_at = expires_at
    instance.join_token_ttl_sec = ttl_seconds
    _publish_legacy_token_lifecycle_event(
        request,
        stage="rotated",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        ttl_seconds=ttl_seconds,
        token_rotated=True,
        join_token_issued=bool(getattr(instance, "join_token", None)),
        reason="join_token_rotated",
    )
    return TokenRotateResponse(
        mesh_id=mesh_id,
        join_token=instance.join_token,
        issued_at=issued_at.isoformat(),
        expires_at=expires_at.isoformat(),
    )


async def create_policy(
    mesh_id: str,
    req: PolicyRequest,
    current_user: User,
    request: Optional[Request] = None,
) -> PolicyResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_policy_lifecycle_event(
            request,
            stage="access_denied",
            status="denied",
            req=req,
            current_user=current_user,
            mesh_id=mesh_id,
            policy_registry_mutated=False,
            audit_recorded=False,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    policy = {
        "id": f"policy-{uuid.uuid4().hex[:8]}",
        "source_tag": req.source_tag,
        "target_tag": req.target_tag,
        "action": req.action,
        "created_at": datetime.utcnow().isoformat(),
    }
    _mesh_policies.setdefault(mesh_id, []).append(policy)
    _audit(mesh_id, _current_user_id(current_user), "policy.create", policy["id"])
    _publish_legacy_policy_lifecycle_event(
        request,
        stage="created",
        status="success",
        req=req,
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        policy_id=policy["id"],
        policy_registry_mutated=True,
        audit_recorded=True,
        reason="policy_created",
    )
    return PolicyResponse(
        policy_id=policy["id"],
        source_tag=req.source_tag,
        target_tag=req.target_tag,
        action=req.action,
        created_at=policy["created_at"],
    )


def get_node_config(
    mesh_id: str,
    node_id: str,
    request: Optional[Request] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    try:
        instance = (
            _require_owner(mesh_id, current_user)
            if current_user is not None
            else _get_mesh_or_404(mesh_id)
        )
    except HTTPException:
        _publish_legacy_policy_read_event(
            request,
            operation="legacy_node_config_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            read_scope="single_node_policy_config",
            reason="mesh_not_found_or_forbidden",
        )
        raise
    node = instance.node_instances.get(node_id)
    if not node:
        _publish_legacy_policy_read_event(
            request,
            operation="legacy_node_config_read",
            stage="node_not_found",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            read_scope="single_node_policy_config",
            reason="node_not_found",
        )
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    source_tags = set(node.get("tags", []))
    allowed_peers: List[str] = []
    denied_peers: List[str] = []
    decisions: Dict[str, Any] = {}
    for peer_id, peer in instance.node_instances.items():
        if peer_id == node_id:
            continue
        peer_tags = set(peer.get("tags", []))
        decision = {"action": "deny", "reason": "default_deny_zero_trust"}
        for policy in _mesh_policies.get(mesh_id, []):
            if (
                policy.get("source_tag") in source_tags
                and policy.get("target_tag") in peer_tags
            ):
                decision = {
                    "action": policy.get("action", "deny"),
                    "reason": "explicit_policy",
                    "policy_id": policy.get("id"),
                }
                break
        decisions[peer_id] = decision
        if decision["action"] == "allow":
            allowed_peers.append(peer_id)
        else:
            denied_peers.append(peer_id)

    response = {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "allowed_peers": allowed_peers,
        "denied_peers": denied_peers,
        "policy_decisions": decisions,
    }
    _publish_legacy_policy_read_event(
        request,
        operation="legacy_node_config_read",
        stage="node_config_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="single_node_policy_config",
        result_summary=_node_config_summary_for_evidence(response),
    )
    return response
def heartbeat(
    req: NodeHeartbeatRequest,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    started = time.monotonic()
    mesh_id = None
    mesh_instance = None
    for candidate_mesh_id, instance in _mesh_registry.items():
        if req.node_id in instance.node_instances:
            mesh_id = candidate_mesh_id
            mesh_instance = instance
            break
    if mesh_id is None:
        _publish_legacy_heartbeat_event(
            request,
            stage="denied",
            status="denied",
            req=req,
            current_user=current_user,
            node_found=False,
            owner_checked=False,
            authorized=False,
            duration_ms=(time.monotonic() - started) * 1000.0,
            telemetry_store_summary={
                "storage_backend": "legacy_in_memory",
                "mutation_attempted": False,
                "current_node_stored": False,
                "stored_nodes_total": len(_node_telemetry),
            },
            mapek_store_summary={
                "storage_backend": "legacy_in_memory",
                "mutation_attempted": False,
                "event_recorded": False,
                "mesh_event_count_after": 0,
                "buffer_limit": _MAPEK_EVENT_BUFFER_SIZE,
                "event_type": None,
            },
            reason="node_not_found",
        )
        raise HTTPException(status_code=404, detail=f"Node {req.node_id} not found")
    if current_user is not None and mesh_instance is not None:
        user_id = _current_user_id(current_user)
        user_role = str(getattr(current_user, "role", "")).lower()
        if (
            str(getattr(mesh_instance, "owner_id", "")) != user_id
            and user_role != "admin"
        ):
            _publish_legacy_heartbeat_event(
                request,
                stage="denied",
                status="denied",
                req=req,
                current_user=current_user,
                mesh_id=mesh_id,
                owner_id=getattr(mesh_instance, "owner_id", None),
                node_found=True,
                owner_checked=True,
                authorized=False,
                duration_ms=(time.monotonic() - started) * 1000.0,
                telemetry_store_summary={
                    "storage_backend": "legacy_in_memory",
                    "mutation_attempted": False,
                    "current_node_stored": req.node_id in _node_telemetry,
                    "stored_nodes_total": len(_node_telemetry),
                },
                mapek_store_summary={
                    "storage_backend": "legacy_in_memory",
                    "mutation_attempted": False,
                    "event_recorded": False,
                    "mesh_event_count_after": len(_mesh_mapek_events.get(mesh_id, [])),
                    "buffer_limit": _MAPEK_EVENT_BUFFER_SIZE,
                    "event_type": None,
                },
                reason="owner_mismatch",
            )
            raise HTTPException(status_code=404, detail=f"Node {req.node_id} not found")

    payload = {
        "node_id": req.node_id,
        "mesh_id": mesh_id,
        "cpu_usage": req.cpu_usage,
        "memory_usage": req.memory_usage,
        "neighbors_count": req.neighbors_count,
        "routing_table_size": req.routing_table_size,
        "uptime": req.uptime,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if getattr(req, "pheromones", None):
        payload["pheromones"] = req.pheromones
    _node_telemetry[req.node_id] = payload
    event = {
        **payload,
        "phase": "MONITOR",
        "event_type": "node.heartbeat",
    }
    _mesh_mapek_events.setdefault(mesh_id, []).append(event)
    _mesh_mapek_events[mesh_id] = _mesh_mapek_events[mesh_id][
        -_MAPEK_EVENT_BUFFER_SIZE:
    ]
    telemetry_store_summary = {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": True,
        "current_node_stored": req.node_id in _node_telemetry,
        "stored_nodes_total": len(_node_telemetry),
    }
    mapek_store_summary = {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": True,
        "event_recorded": True,
        "mesh_event_count_after": len(_mesh_mapek_events.get(mesh_id, [])),
        "buffer_limit": _MAPEK_EVENT_BUFFER_SIZE,
        "event_type": "node.heartbeat",
    }
    _publish_legacy_heartbeat_event(
        request,
        stage="accepted",
        status="success",
        req=req,
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(mesh_instance, "owner_id", None),
        node_found=True,
        owner_checked=current_user is not None,
        authorized=True,
        stored_telemetry=True,
        mapek_event_recorded=True,
        duration_ms=(time.monotonic() - started) * 1000.0,
        telemetry_store_summary=telemetry_store_summary,
        mapek_store_summary=mapek_store_summary,
        reason="accepted",
    )
    return {
        "status": "ack",
        "mesh_id": mesh_id,
        "node_id": req.node_id,
        "event_emitted": True,
    }


def list_mapek_events(
    mesh_id: str,
    limit: int = 100,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    try:
        instance = (
            _require_owner(mesh_id, current_user)
            if current_user is not None
            else _get_mesh_or_404(mesh_id)
        )
    except HTTPException as exc:
        _publish_legacy_mapek_read_event(
            request,
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="legacy_mapek_events",
            limit_requested=limit,
            stored_event_count=None,
            returned_event_count=0,
            reason=f"http_{exc.status_code}",
        )
        raise

    stored_events = _mesh_mapek_events.get(mesh_id, [])
    events = stored_events[-limit:]
    _publish_legacy_mapek_read_event(
        request,
        stage="mapek_event_list_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="legacy_mapek_events",
        limit_requested=limit,
        stored_event_count=len(stored_events),
        returned_event_count=len(events),
        result_summary=_mapek_events_summary_for_evidence(
            events,
            limit_requested=limit,
            stored_event_count=len(stored_events),
        ),
        reason="mapek_event_list_read",
    )
    return {"mesh_id": mesh_id, "events": events, "count": len(events)}


def get_onprem_profile(
    mesh_id: str,
    format: str = "json",
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    instance = (
        _require_owner(mesh_id, current_user)
        if current_user is not None
        else _get_mesh_or_404(mesh_id)
    )
    return {
        "schema_version": "1.0",
        "mesh_id": mesh_id,
        "format": format,
        "join_token": instance.join_token,
        "docker_compose": {
            "version": "3.9",
            "control-plane": "x0tta6bl4/maas-control-plane:latest",
            "services": {
                "control-plane": {
                    "image": "x0tta6bl4/maas-control-plane:latest",
                    "environment": {
                        "MESH_ID": mesh_id,
                        "PQC_ENABLED": str(instance.pqc_enabled).lower(),
                    },
                }
            },
        },
        "agent_configs": {
            node_id: {
                "mesh_id": mesh_id,
                "node_id": node_id,
                "join_token": instance.join_token,
            }
            for node_id in instance.node_instances
        },
        "install_instructions": [
            "Deploy control-plane service.",
            "Start each agent with its generated mesh_id and join_token.",
        ],
    }


def list_all_nodes(
    mesh_id: str,
    node_status: Optional[str] = None,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    try:
        instance = (
            _require_owner(mesh_id, current_user)
            if current_user is not None
            else _get_mesh_or_404(mesh_id)
        )
    except HTTPException:
        _publish_legacy_node_read_event(
            request,
            operation="legacy_node_list_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="mesh_node_list",
            node_status_filter=node_status,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    nodes: List[Dict[str, Any]] = []
    for node_id, node in instance.node_instances.items():
        status_value = "revoked" if node.get("status") == "revoked" else "approved"
        nodes.append({
            "node_id": node_id,
            "mesh_id": mesh_id,
            "status": status_value,
            "device_class": node.get("device_class", "edge"),
            "tags": node.get("tags", []),
        })
    for node_id, pending in _pending_nodes.get(mesh_id, {}).items():
        nodes.append({
            "node_id": node_id,
            "mesh_id": mesh_id,
            "status": "pending",
            "device_class": pending.get("device_class", "edge"),
            "tags": pending.get("tags", []),
        })
    if node_status:
        nodes = [node for node in nodes if node["status"] == node_status]

    by_status: Dict[str, int] = {}
    for node in nodes:
        by_status[node["status"]] = by_status.get(node["status"], 0) + 1
    for key in ("approved", "pending", "revoked"):
        by_status.setdefault(key, 0)

    _publish_legacy_node_read_event(
        request,
        operation="legacy_node_list_read",
        stage="node_list_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="mesh_node_list",
        node_status_filter=node_status,
        result_summary=_node_read_summary_for_evidence(nodes),
    )
    return {"mesh_id": mesh_id, "nodes": nodes, "by_status": by_status}


def list_pending_nodes(
    mesh_id: str,
    current_user: User,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    role = str(getattr(current_user, "role", "") or "").lower()
    if role not in {"admin", "operator"}:
        _publish_legacy_node_read_event(
            request,
            operation="legacy_pending_node_list_read",
            stage="role_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="pending_node_list",
            node_status_filter="pending",
            reason="operator_role_required",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_node_read_event(
            request,
            operation="legacy_pending_node_list_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="pending_node_list",
            node_status_filter="pending",
            reason="mesh_not_found_or_forbidden",
        )
        raise
    nodes = [
        {
            "node_id": node_id,
            "mesh_id": mesh_id,
            "status": "pending",
            "device_class": pending.get("device_class", "edge"),
            "tags": pending.get("tags", []),
        }
        for node_id, pending in sorted(_pending_nodes.get(mesh_id, {}).items())
    ]
    _publish_legacy_node_read_event(
        request,
        operation="legacy_pending_node_list_read",
        stage="pending_node_list_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="pending_node_list",
        node_status_filter="pending",
        result_summary=_node_read_summary_for_evidence(nodes),
    )
    return {
        "mesh_id": mesh_id,
        "pending": [node["node_id"] for node in nodes],
        "nodes": nodes,
        "count": len(nodes),
    }


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


def _legacy_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit", "rollback"))


def _legacy_registries_available() -> bool:
    registry_surfaces = (
        _mesh_registry,
        _pending_nodes,
        _node_telemetry,
        _mesh_policies,
        _mesh_audit_log,
        _mesh_mapek_events,
        _revoked_nodes,
        _mesh_reissue_tokens,
    )
    return all(isinstance(surface, dict) for surface in registry_surfaces) and all(
        callable(getattr(_registry_lock, attr, None))
        for attr in ("acquire", "release", "locked")
    )


def _legacy_services_available() -> bool:
    return (
        all(
            callable(getattr(mesh_provisioner, attr, None))
            for attr in ("create", "terminate", "get", "list_for_owner")
        )
        and all(
            callable(getattr(billing_service, attr, None))
            for attr in ("normalize_plan", "plan_catalog", "check_quota")
        )
        and all(
            callable(getattr(usage_metering_service, attr, None))
            for attr in ("get_mesh_usage", "get_account_usage")
        )
        and all(
            callable(getattr(auth_service, attr, None))
            for attr in ("register", "login", "rotate_api_key")
        )
    )


def _legacy_auth_dependencies_available() -> bool:
    return (
        callable(get_current_user_from_maas)
        and callable(get_current_user)
        and callable(require_permission)
        and callable(require_role)
        and callable(getattr(api_key_manager, "generate", None))
        and callable(getattr(oidc_validator, "get_config", None))
        and callable(getattr(oidc_validator, "validate", None))
    )


def _legacy_security_helpers_available() -> bool:
    return (
        callable(getattr(token_signer, "sign_token", None))
        and callable(getattr(AttestationService, "validate_node", None))
        and (not PQC_AVAILABLE or callable(PQCNodeIdentity))
    )


def _legacy_db_models_available() -> bool:
    required_model_attrs = (
        (User, ("id", "email", "api_key", "plan", "role")),
        (
            BillingWebhookEvent,
            ("event_id", "event_type", "payload_hash", "status", "created_at"),
        ),
        (DBMeshInstance, ("id", "name", "owner_id", "status", "plan", "created_at")),
    )
    return all(
        hasattr(model, attr)
        for model, attrs in required_model_attrs
        for attr in attrs
    )


def _legacy_readiness_status(db: Any) -> Dict[str, Any]:
    legacy_db_ready = _legacy_db_session_available(db)
    legacy_registries_ready = _legacy_registries_available()
    legacy_services_ready = _legacy_services_available()
    legacy_auth_ready = _legacy_auth_dependencies_available()
    legacy_security_ready = _legacy_security_helpers_available()
    legacy_models_ready = _legacy_db_models_available()
    maas_legacy_runtime_ready = (
        legacy_db_ready
        and legacy_registries_ready
        and legacy_services_ready
        and legacy_auth_ready
        and legacy_security_ready
        and legacy_models_ready
    )

    degraded_dependencies = []
    if not legacy_db_ready:
        degraded_dependencies.append("database")
    if not legacy_registries_ready:
        degraded_dependencies.append("registries")
    if not legacy_services_ready:
        degraded_dependencies.append("legacy_services")
    if not legacy_auth_ready:
        degraded_dependencies.append("auth_dependencies")
    if not legacy_security_ready:
        degraded_dependencies.append("security_helpers")
    if not legacy_models_ready:
        degraded_dependencies.append("db_models")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "maas_legacy_runtime_ready": maas_legacy_runtime_ready,
        "legacy_db_ready": legacy_db_ready,
        "legacy_registries_ready": legacy_registries_ready,
        "legacy_services_ready": legacy_services_ready,
        "legacy_auth_ready": legacy_auth_ready,
        "legacy_security_ready": legacy_security_ready,
        "legacy_models_ready": legacy_models_ready,
        "pqc_identity_available": PQC_AVAILABLE,
        "registry_counts": {
            "meshes": len(_mesh_registry) if isinstance(_mesh_registry, dict) else None,
            "pending_node_meshes": (
                len(_pending_nodes) if isinstance(_pending_nodes, dict) else None
            ),
            "telemetry_nodes": (
                len(_node_telemetry) if isinstance(_node_telemetry, dict) else None
            ),
            "revoked_node_meshes": (
                len(_revoked_nodes) if isinstance(_revoked_nodes, dict) else None
            ),
        },
        "route_precedence": {
            "fixed_prefix": "/api/v1/maas",
            "catch_all_owner": True,
            "known_shadowing_boundary": (
                "The legacy MaaS router is registered before modular MaaS routers "
                "and owns broad /api/v1/maas/{mesh_id}/... paths. Readiness is a "
                "static /api/v1/maas/readiness path registered before dynamic "
                "mesh routes in this router."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Legacy auth, DB mesh persistence, billing webhook idempotency, "
                "and user lookup require SQLAlchemy query/add/commit/rollback."
            ),
            "registries": (
                "Mesh runtime state, pending nodes, telemetry, policies, audit "
                "logs, MAPE-K events, revocations, and reissue tokens are held in "
                "module-level dictionaries guarded by _registry_lock."
            ),
            "legacy_services": (
                "MeshProvisioner, BillingService, UsageMeteringService, and "
                "AuthService back the legacy route implementations."
            ),
            "auth_dependencies": (
                "Legacy routes use both local X-API-Key auth and MaaS auth "
                "require_permission/require_role dependencies plus OIDC helpers."
            ),
            "security_helpers": (
                "Node approval/reissue paths require token_signer and hardware "
                "attestation; PQC identity is reported separately because the "
                "legacy router can still run without that optional import."
            ),
            "db_models": (
                "Legacy DB-backed paths depend on User, BillingWebhookEvent, and "
                "DBMeshInstance model fields."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_legacy_readiness"
        ),
        "claim_boundary": (
            "Legacy MaaS readiness proves the monolith route and local dependency "
            "surfaces are present. It does not deploy a mesh, mutate registries, "
            "query billing state, validate a node attestation, or prove every "
            "dynamic /{mesh_id}/... route is semantically healthy."
        ),
    }


async def legacy_billing_webhook(
    req: BillingWebhookRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_billing_webhook_secret: Optional[str] = None,
    x_billing_timestamp: Optional[str] = None,
    x_billing_signature: Optional[str] = None,
):
    """Legacy billing webhook compatibility entrypoint.

    The HTTP route is served by the modular billing router, but direct callers
    and citation tests still rely on the legacy function to emit the historical
    maas-legacy-billing EventBus evidence shape.
    """

    _verify_billing_webhook_secret(x_billing_webhook_secret)
    raw_payload = await request.body()
    _verify_billing_webhook_hmac(
        raw_payload,
        x_billing_timestamp,
        x_billing_signature,
    )
    event_id = _extract_billing_event_id(req)
    payload_hash = _payload_sha256_hex(raw_payload)
    try:
        cached = _start_billing_event_processing(
            db,
            event_id,
            req.event_type,
            payload_hash,
        )
    except Exception as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_legacy_billing_webhook_event(
            request,
            stage="idempotency_rejected",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            status="failed",
            user_id=req.user_id,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise
    if cached is not None:
        _publish_legacy_billing_webhook_event(
            request,
            stage="idempotent_replay",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            status="replayed",
            user_id=cached.get("user_id") or req.user_id,
            plan_before=cached.get("plan_before"),
            plan_after=cached.get("plan_after"),
            idempotent_replay=True,
        )
        return {**cached, "idempotent_replay": True}

    user_id_for_event: Optional[Any] = req.user_id
    plan_before: Optional[str] = None
    plan_after: Optional[str] = None
    try:
        user = _resolve_billing_user(db, req)
        if user is None:
            raise HTTPException(status_code=404, detail="Billing user not found")

        user_id_for_event = user.id
        plan_before = billing_service.normalize_plan(getattr(user, "plan", "starter"))
        if req.event_type in {"subscription.canceled", "subscription.deleted"}:
            plan_after = "starter"
        else:
            plan_after = billing_service.normalize_plan(req.plan or plan_before)

        user.plan = plan_after
        if req.customer_id:
            user.stripe_customer_id = req.customer_id
        if req.subscription_id:
            user.stripe_subscription_id = req.subscription_id
        db.commit()

        response_payload = {
            "processed": True,
            "event_id": event_id,
            "event_type": req.event_type,
            "user_id": user.id,
            "plan_before": plan_before,
            "plan_after": plan_after,
            "requests_limit": PLAN_REQUEST_LIMITS.get(
                plan_after, PLAN_REQUEST_LIMITS["starter"]
            ),
            "idempotent_replay": False,
        }
        _finalize_billing_event_processing(db, event_id, response_payload)
        _publish_legacy_billing_webhook_event(
            request,
            stage="processed",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            status="success",
            user_id=user_id_for_event,
            plan_before=plan_before,
            plan_after=plan_after,
        )
        return response_payload
    except Exception as exc:
        _fail_billing_event_processing(db, event_id, str(exc))
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_legacy_billing_webhook_event(
            request,
            stage="failed",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            status="failed",
            user_id=user_id_for_event,
            plan_before=plan_before,
            plan_after=plan_after,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise


@router.get("/{mesh_id}/metrics", response_model=MeshMetricsResponse)
async def legacy_mesh_metrics(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
):
    """Return legacy local mesh metrics with explicit fail-closed claim gates."""
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_lifecycle_read_event(
            request,
            operation="legacy_mesh_metrics_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="single_mesh_metrics",
            registry_source="legacy_or_modular_registry",
            reason="mesh_not_found_or_forbidden",
        )
        raise

    response = MeshMetricsResponse(
        mesh_id=mesh_id,
        consciousness=instance.get_consciousness_metrics(),
        mape_k=instance.get_mape_k_state(),
        network=instance.get_network_metrics(),
        mesh_metrics_claim_gate=_legacy_mesh_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _LEGACY_MESH_METRICS_CROSS_PLANE_CLAIMS,
            surface="legacy_maas_mesh.metrics",
        ),
        timestamp=datetime.utcnow().isoformat(),
    )
    summary = _mesh_metrics_summary_for_evidence(response)
    _publish_legacy_lifecycle_read_event(
        request,
        operation="legacy_mesh_metrics_read",
        stage="metrics_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="single_mesh_metrics",
        registry_source="legacy_or_modular_registry",
        result_summary=summary,
    )
    return response
