"""
MaaS API Pydantic Models.

Contains all request and response models for the MaaS API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    optimization_mode: str = Field(default="standard", pattern="^(standard|ml_routing|genetic_topo)$")
    federated_strategy: str = Field(default="fedavg", pattern="^(fedavg|hw_fedavg)$")
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
    mesh_deploy_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    mesh_provisioner_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    provisioner_cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


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
    optimization_mode: str = "standard"
    federated_strategy: str = "fedavg"
    peers: List[Dict[str, Any]]
    health_score: float  # 0.0 - 1.0
    control_policy_evidence: Dict[str, Any] = Field(default_factory=dict)
    mesh_lifecycle_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class MeshMetricsResponse(BaseModel):
    """Mesh metrics response."""
    mesh_id: str
    consciousness: Dict[str, Any]
    mape_k: Dict[str, Any]
    network: Dict[str, Any]
    control_policy_evidence: Dict[str, Any] = Field(default_factory=dict)
    mesh_metrics_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)
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
    mesh_id: Optional[str] = None
    node_id: Optional[str] = None
    enrollment_token: Optional[str] = Field(default=None, min_length=16)
    device_class: str = Field(
        default="edge",
        pattern="^(edge|robot|drone|gateway|sensor|server)$",
    )
    labels: Dict[str, str] = Field(default_factory=dict)
    public_keys: Dict[str, str] = Field(default_factory=dict)
    # Legacy single-key fields used by older clients/tests.
    public_key: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    hardware_id: Optional[str] = None
    attestation_data: Optional[Dict[str, Any]] = None
    enclave_enabled: bool = False


class NodeRegisterResponse(BaseModel):
    """Node registration response."""
    mesh_id: str
    node_id: str
    status: str  # pending_approval | approved
    message: str
    api_key: Optional[str] = None
    node_runtime_credential: Optional[str] = None
    node_runtime_credential_expires_at: Optional[datetime] = None
    raw_runtime_credential_returned_once: bool = False


class NodeRuntimeIdentityProof(BaseModel):
    """Bounded local identity proof for a node runtime action.

    This is stored and compared as a hash-only binding. It is not a live SVID
    verifier by itself.
    """

    binding_type: str = Field(
        ...,
        pattern="^(local_spiffe_hint|spiffe_svid_digest|verified_spiffe_svid|verified_jwt_svid|measured_attestation)$",
    )
    spiffe_id: Optional[str] = Field(default=None, max_length=512)
    attestation_digest: Optional[str] = Field(default=None, max_length=256)
    nonce: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_identity_material(self) -> "NodeRuntimeIdentityProof":
        binding_type = (self.binding_type or "").strip().lower()
        if binding_type == "local_spiffe_hint" and not self.spiffe_id:
            raise ValueError("spiffe_id is required for local_spiffe_hint")
        if binding_type == "measured_attestation" and not self.attestation_digest:
            raise ValueError("attestation_digest is required for measured_attestation")
        if binding_type in {
            "spiffe_svid_digest",
            "verified_spiffe_svid",
            "verified_jwt_svid",
        } and (not self.spiffe_id or not self.attestation_digest):
            raise ValueError(
                "spiffe_id and attestation_digest are required for SVID-based bindings"
            )
        return self


class NodeRuntimeIdentityBindRequest(NodeRuntimeIdentityProof):
    """Operator request to bind a node to a runtime identity proof hash."""


class NodeRuntimeIdentityBindResponse(BaseModel):
    """Hash-only node runtime identity binding response."""

    mesh_id: str
    node_id: str
    status: str = "bound"
    runtime_identity_binding_type: str
    runtime_identity_binding_hash_prefix: str
    runtime_identity_bound_at: datetime
    runtime_identity_last_verified_at: datetime
    raw_runtime_identity_proof_redacted: bool = True
    live_spiffe_svid_claim_allowed: bool = False
    trusted_runtime_identity_proxy_claim_allowed: bool = False
    api_side_jwt_svid_verification_claim_allowed: bool = False
    runtime_identity_verification_source: Optional[str] = None
    attestation_verifier_backend: Optional[str] = None
    attestation_verifier_provenance: Dict[str, Any] = Field(default_factory=dict)
    production_attestation_verifier_claim_allowed: bool = False
    production_trust_finality_claim_allowed: bool = False


class NodeRuntimeCredentialRotateRequest(BaseModel):
    """Node runtime credential rotation request."""
    ttl_seconds: int = Field(default=86400, ge=60, le=2592000)
    identity_proof: Optional[NodeRuntimeIdentityProof] = None


class NodeRuntimeCredentialRotateResponse(BaseModel):
    """Node runtime credential rotation response."""
    mesh_id: str
    node_id: str
    status: str = "rotated"
    api_key: str
    node_runtime_credential: str
    node_runtime_credential_expires_at: datetime
    node_runtime_credential_rotated_at: datetime
    raw_runtime_credential_returned_once: bool = True


class NodeMeasuredAttestationRefreshRequest(BaseModel):
    """Refresh a measured-attestation runtime identity binding."""
    attestation_data: Dict[str, Any]


class NodeApproveRequest(BaseModel):
    """Node approval request."""
    acl_profile: str = Field(default="default", pattern="^(default|strict|isolated)$")
    tags: List[str] = Field(default_factory=list)
    attestation_data: Optional[Dict[str, Any]] = None


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
    mesh_id: Optional[str] = None
    node_id: Optional[str] = None
    status: str = Field(default="healthy", pattern="^(healthy|degraded|unhealthy)$")
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    neighbors_count: int = 0
    routing_table_size: int = 0
    uptime: float = 0.0
    # Legacy compatibility fields used by some callers/tests.
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    latency_ms: Optional[float] = None
    traffic_mbps: Optional[float] = None
    active_connections: Optional[int] = None
    dataplane_probe_target: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern=r"^[A-Za-z0-9_.:%-]+$",
        description="Optional redacted-in-responses target used for bounded post-heal dataplane probes.",
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern=r"^[A-Za-z0-9_.:%-]+$",
        description="Compatibility alias for dataplane_probe_target.",
    )
    custom_metrics: Dict[str, Any] = Field(default_factory=dict)
    pheromones: Optional[Dict[str, Dict[str, float]]] = None  # For Stigmergy viz

    @model_validator(mode="after")
    def reject_empty_heartbeat(self) -> "NodeHeartbeatRequest":
        if not self.model_fields_set:
            raise ValueError("node_id or heartbeat data is required")
        return self


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
    access_token: Optional[str] = None  # Alias for session_token
    token_type: str = "session_token"
    expires_in: int = 86400  # 24 hours


class RegisterRequest(BaseModel):
    """User registration request."""
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=128)
    company: Optional[str] = Field(default=None, max_length=128)


class RegisterResponse(BaseModel):
    """User registration response."""
    user_id: str
    email: str
    api_key: str
    access_token: Optional[str] = None  # Alias for api_key
    token_type: str = "api_key"
    expires_in: int = 31536000
    message: str


class UserProfileResponse(BaseModel):
    """User profile response."""
    id: Optional[str] = None
    user_id: str
    email: str
    name: Optional[str] = None
    plan: str
    role: str = "user"
    requests_count: int = 0
    created_at: Optional[str] = None


class ApiKeyRotateRequest(BaseModel):
    """API key rotation request."""
    revoke_old: bool = Field(default=True)


class ApiKeyRotateResponse(BaseModel):
    """API key rotation response."""
    api_key: str
    created_at: Optional[str] = None
    message: str


class MeshScaleRequest(BaseModel):
    """Mesh scaling request."""
    target_count: Optional[int] = Field(default=None, ge=1, le=1000)
    action: Optional[str] = Field(default=None, pattern="^(scale_up|scale_down)$")
    count: Optional[int] = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def require_scale_target(self) -> "MeshScaleRequest":
        if self.target_count is None and self.count is None:
            raise ValueError("target_count or legacy count is required")
        return self


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
    "NodeRuntimeIdentityProof",
    "NodeRuntimeIdentityBindRequest",
    "NodeRuntimeIdentityBindResponse",
    "NodeRuntimeCredentialRotateRequest",
    "NodeRuntimeCredentialRotateResponse",
    "NodeMeasuredAttestationRefreshRequest",
    "NodeHeartbeatRequest",
    # Policy
    "PolicyRequest",
    "PolicyResponse",
    # Billing
    "BillingWebhookRequest",
    "BillingWebhookResponse",
    "LegacyBillingResponse",
]


class LegacyBillingResponse(BaseModel):
    """Compatibility response for legacy billing actions."""

    status: str
    message: str
    processed: bool = True
    event_id: Optional[str] = None
    user_id: Optional[str] = None
    plan_before: Optional[str] = None
    plan_after: Optional[str] = None
    requests_limit: Optional[int] = None
    idempotent_replay: bool = False
    data: Optional[Dict[str, Any]] = None
