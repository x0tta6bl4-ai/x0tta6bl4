"""
MaaS API Pydantic Models.

Contains all request and response models for the MaaS API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth Models
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "api_key"
    expires_in: int = 31536000


class ApiKeyResponse(BaseModel):
    """API key rotation response."""
    api_key: str
    created_at: datetime


class OIDCExchangeRequest(BaseModel):
    """OIDC token exchange request."""
    id_token: str = Field(..., min_length=10, description="OIDC ID token from provider")


# ---------------------------------------------------------------------------
# Mesh Models
# ---------------------------------------------------------------------------

class MeshDeployRequest(BaseModel):
    """Mesh deployment request."""
    name: str = Field(..., min_length=3, max_length=64)
    nodes: int = Field(default=5, ge=1, le=1000)
    billing_plan: str = Field(default="starter", pattern="^(starter|pro|enterprise)$")
    pqc_enabled: bool = Field(default=True)
    obfuscation: str = Field(default="none", pattern="^(none|xor|aes)$")
    traffic_profile: str = Field(default="none", pattern="^(none|gaming|streaming|voip)$")
    join_token_ttl_sec: int = Field(default=604800, ge=3600, le=2592000)  # 1h–30d, default 7d


class MeshDeployResponse(BaseModel):
    """Mesh deployment response."""
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
    """Token rotation response."""
    mesh_id: str
    join_token: str
    issued_at: str
    expires_at: str


class MeshStatusResponse(BaseModel):
    """Mesh status response."""
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
    """Mesh metrics response."""
    mesh_id: str
    consciousness: Dict[str, Any]
    mape_k: Dict[str, Any]
    network: Dict[str, Any]
    timestamp: str


class ScaleRequest(BaseModel):
    """Mesh scaling request."""
    action: str = Field(..., pattern="^(scale_up|scale_down)$")
    count: int = Field(..., ge=1, le=100)


class ScaleResponse(BaseModel):
    """Mesh scaling response."""
    mesh_id: str
    previous_nodes: int
    current_nodes: int
    status: str


# ---------------------------------------------------------------------------
# Node Models
# ---------------------------------------------------------------------------

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
    """Node registration response."""
    mesh_id: str
    node_id: str
    status: str  # pending_approval | approved
    message: str


class NodeApproveRequest(BaseModel):
    """Node approval request."""
    acl_profile: str = Field(default="default", pattern="^(default|strict|isolated)$")
    tags: List[str] = Field(default_factory=list)


class NodeApproveResponse(BaseModel):
    """Node approval response."""
    mesh_id: str
    node_id: str
    status: str
    join_token: Dict[str, Any]
    approved_at: str


class NodeRevokeRequest(BaseModel):
    """Node revocation request."""
    node_id: Optional[str] = None
    reason: str = Field(default="manual_revoke", min_length=3, max_length=120)


class NodeRevokeResponse(BaseModel):
    """Node revocation response."""
    mesh_id: str
    node_id: str
    status: str
    reason: str
    revoked_at: str


class NodeReissueTokenRequest(BaseModel):
    """Node token reissue request."""
    ttl_seconds: int = Field(default=900, ge=60, le=86400)


class NodeReissueTokenResponse(BaseModel):
    """Node token reissue response."""
    mesh_id: str
    node_id: str
    join_token: Dict[str, Any]
    issued_at: str
    expires_at: str


class NodeHeartbeatRequest(BaseModel):
    """Node heartbeat telemetry."""
    node_id: str
    cpu_usage: float
    memory_usage: float
    neighbors_count: int
    routing_table_size: int
    uptime: float
    pheromones: Optional[Dict[str, Dict[str, float]]] = None  # For Stigmergy viz


# ---------------------------------------------------------------------------
# Policy Models
# ---------------------------------------------------------------------------

class PolicyRequest(BaseModel):
    """ACL policy creation request."""
    source_tag: str = Field(..., description="Tag of nodes initiating connection (e.g. 'robot')")
    target_tag: str = Field(..., description="Tag of destination nodes (e.g. 'gateway')")
    action: str = Field(default="allow", pattern="^(allow|deny)$")


class PolicyResponse(BaseModel):
    """ACL policy response."""
    policy_id: str
    source_tag: str
    target_tag: str
    action: str
    created_at: str


# ---------------------------------------------------------------------------
# Billing Models
# ---------------------------------------------------------------------------

class BillingWebhookRequest(BaseModel):
    """Billing webhook request."""
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
    """Billing webhook response."""
    processed: bool
    event_id: str
    event_type: str
    user_id: str
    plan_before: str
    plan_after: str
    requests_limit: int
    idempotent_replay: bool = False


# ---------------------------------------------------------------------------
# Additional Auth Models (for new endpoints)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """User login request."""
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginResponse(BaseModel):
    """User login response."""
    user_id: str
    session_token: str
    expires_in: int = 86400  # 24 hours


class RegisterRequest(BaseModel):
    """User registration request."""
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=128)


class RegisterResponse(BaseModel):
    """User registration response."""
    user_id: str
    email: str
    api_key: str
    message: str


class UserProfileResponse(BaseModel):
    """User profile response."""
    user_id: str
    email: str
    name: Optional[str] = None
    plan: str
    created_at: Optional[str] = None


class ApiKeyRotateRequest(BaseModel):
    """API key rotation request."""
    revoke_old: bool = Field(default=True)


class ApiKeyRotateResponse(BaseModel):
    """API key rotation response."""
    api_key: str
    message: str


class MeshScaleRequest(BaseModel):
    """Mesh scaling request."""
    target_count: int = Field(..., ge=1, le=1000)


__all__ = [
    # Auth
    "TokenResponse",
    "ApiKeyResponse",
    "OIDCExchangeRequest",
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "UserProfileResponse",
    "ApiKeyRotateRequest",
    "ApiKeyRotateResponse",
    # Mesh
    "MeshDeployRequest",
    "MeshDeployResponse",
    "TokenRotateResponse",
    "MeshStatusResponse",
    "MeshMetricsResponse",
    "ScaleRequest",
    "ScaleResponse",
    "MeshScaleRequest",
    # Node
    "NodeRegisterRequest",
    "NodeRegisterResponse",
    "NodeApproveRequest",
    "NodeApproveResponse",
    "NodeRevokeRequest",
    "NodeRevokeResponse",
    "NodeReissueTokenRequest",
    "NodeReissueTokenResponse",
    "NodeHeartbeatRequest",
    # Policy
    "PolicyRequest",
    "PolicyResponse",
    # Billing
    "BillingWebhookRequest",
    "BillingWebhookResponse",
]
