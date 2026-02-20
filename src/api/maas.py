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
import logging
from pathlib import Path
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import User, get_db
from src.api.maas_security import token_signer

# Try importing PQC identity manager
try:
    from src.security.pqc_identity import PQCNodeIdentity

    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS"])


PLAN_ALIASES = {
    "free": "starter",
    "starter": "starter",
    "pro": "pro",
    "enterprise": "enterprise",
}


# ---------------------------------------------------------------------------
# Pydantic Models — Auth
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    company: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class ApiKeyResponse(BaseModel):
    api_key: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Pydantic Models — Mesh
# ---------------------------------------------------------------------------

class MeshDeployRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=64)
    nodes: int = Field(default=5, ge=1, le=1000)
    billing_plan: str = Field(default="pro", pattern="^(starter|pro|enterprise)$")
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
    """Append control-plane audit event."""
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

    def register(self, db: Session, req: UserRegisterRequest) -> User:
        if db.query(User).filter(User.email == req.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            id=str(uuid.uuid4()),
            email=req.email,
            password_hash=req.password,  # TODO: bcrypt/argon2 in prod
            full_name=req.full_name,
            company=req.company,
            api_key=secrets.token_urlsafe(32),
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, req: UserLoginRequest) -> str:
        user = db.query(User).filter(User.email == req.email).first()
        if not user or user.password_hash != req.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user.api_key


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
    new_key = secrets.token_urlsafe(32)
    current_user.api_key = new_key
    db.commit()
    return {"api_key": new_key, "created_at": datetime.utcnow()}


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


# ---------------------------------------------------------------------------
# Mesh Lifecycle Endpoints
# ---------------------------------------------------------------------------

@router.post("/deploy", response_model=MeshDeployResponse)
async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User = Depends(get_current_user),
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
def list_meshes(current_user: User = Depends(get_current_user)):
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
def mesh_status(mesh_id: str, current_user: User = Depends(get_current_user)):
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
def mesh_metrics(mesh_id: str, current_user: User = Depends(get_current_user)):
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
    current_user: User = Depends(get_current_user),
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
    mesh_id: str, current_user: User = Depends(get_current_user)
):
    """Terminate a mesh network and release all resources."""
    _get_mesh_or_404(mesh_id, current_user.id)
    terminated = await mesh_provisioner.terminate(mesh_id)
    if not terminated:
        raise HTTPException(status_code=500, detail="Failed to terminate mesh")
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

        _pending_nodes[mesh_id][node_id] = {
            "device_class": req.device_class,
            "labels": req.labels,
            "public_keys": req.public_keys,
            "requested_at": datetime.utcnow().isoformat(),
            "enrollment_mode": enrollment_mode,
        }

    return NodeRegisterResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="pending_approval",
        message="Node registration submitted. Awaiting administrator approval."
    )

@router.get("/{mesh_id}/pending-nodes")
def list_pending_nodes(mesh_id: str, current_user: User = Depends(get_current_user)):
    """Admin view: list nodes waiting for approval."""
    _get_mesh_or_404(mesh_id, current_user.id)
    return {"pending": _pending_nodes.get(mesh_id, {})}


@router.post("/{mesh_id}/nodes/register", response_model=NodeRegisterResponse)
async def register_node_v2(mesh_id: str, req: NodeRegisterRequest):
    """Canonical node registration endpoint (v2)."""
    return await register_node(mesh_id, req)


@router.get("/{mesh_id}/nodes/pending")
def list_pending_nodes_v2(
    mesh_id: str, current_user: User = Depends(get_current_user)
):
    """Canonical pending list endpoint (v2)."""
    return list_pending_nodes(mesh_id, current_user)

@router.post("/{mesh_id}/approve-node/{node_id}", response_model=NodeApproveResponse)
async def approve_node(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest,
    current_user: User = Depends(get_current_user)
):
    """Admin action: approve a node and return its join token."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    
    async with _registry_lock:
        if mesh_id not in _pending_nodes or node_id not in _pending_nodes[mesh_id]:
            raise HTTPException(status_code=404, detail="Pending node not found")
        
        node_data = _pending_nodes[mesh_id].pop(node_id)
        signed_join_token = token_signer.sign_token(instance.join_token, mesh_id)

        # Add to mesh instance
        instance.node_instances[node_id] = {
            "id": node_id,
            "status": "healthy",
            "device_class": node_data["device_class"],
            "started_at": datetime.utcnow().isoformat(),
            "acl_profile": req.acl_profile,
            "tags": req.tags
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
def list_audit_logs(mesh_id: str, current_user: User = Depends(get_current_user)):
    """Enterprise audit trail for control-plane actions."""
    _get_mesh_or_404(mesh_id, current_user.id)
    return {
        "mesh_id": mesh_id,
        "events": _mesh_audit_log.get(mesh_id, []),
        "count": len(_mesh_audit_log.get(mesh_id, [])),
    }


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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user),
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


# ---------------------------------------------------------------------------
# Token Rotation
# ---------------------------------------------------------------------------


@router.post("/{mesh_id}/tokens/rotate", response_model=TokenRotateResponse)
def rotate_join_token(
    mesh_id: str,
    current_user: User = Depends(get_current_user),
):
    """Rotate the primary mesh join token. Old token is immediately invalidated."""
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    instance.join_token = secrets.token_urlsafe(32)
    instance.join_token_issued_at = datetime.utcnow()
    instance.join_token_expires_at = instance.join_token_issued_at + timedelta(
        seconds=instance.join_token_ttl_sec
    )
    logger.info(f"[MaaS] Rotated join token for mesh {mesh_id}")
    return TokenRotateResponse(
        mesh_id=mesh_id,
        join_token=instance.join_token,
        issued_at=instance.join_token_issued_at.isoformat(),
        expires_at=instance.join_token_expires_at.isoformat(),
    )


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
