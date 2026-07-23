"""
MaaS Node Management Package.
"""
from __future__ import annotations

from .security import (
    MeshOperator,
    get_mesh_operator,
    check_permission,
    ensure_mesh_visibility,
    ensure_mesh_visibility_with_permission,
)
from .admission import (
    register_node,
    list_pending_nodes,
    approve_node,
    bind_node_runtime_identity,
    canonical_node_runtime_identity_binding_payload,
    revoke_node,
    delete_node,
    generate_node_runtime_credential,
    hash_verified_measured_attestation,
    hash_node_runtime_identity_binding,
    hash_node_runtime_credential,
    is_node_measured_attestation_fresh,
    is_node_runtime_credential_expired,
    measured_attestation_freshness_seconds,
    node_runtime_credential_expires_at,
    rotate_node_runtime_credential,
    runtime_identity_proof_from_verified_context,
    verified_node_runtime_identity_from_jwt_svid,
    verified_node_runtime_identity_from_headers,
    verified_measured_attestation_context,
    verified_runtime_identity_failure_reason,
    verify_node_runtime_identity_binding,
    verify_node_runtime_credential,
)
from .heartbeat import (
    HeartbeatRequest,
    process_heartbeat,
)
from .healing import (
    trigger_node_healing,
)
from .readiness import (
    node_readiness,
)
from .telemetry_acl import (
    get_node_telemetry_data,
    check_node_access,
    get_node_agent_config,
    list_all_mesh_nodes,
    AccessCheckRequest,
)

__all__ = [
    "MeshOperator",
    "get_mesh_operator",
    "check_permission",
    "ensure_mesh_visibility",
    "ensure_mesh_visibility_with_permission",
    "register_node",
    "list_pending_nodes",
    "approve_node",
    "bind_node_runtime_identity",
    "canonical_node_runtime_identity_binding_payload",
    "revoke_node",
    "delete_node",
    "generate_node_runtime_credential",
    "hash_verified_measured_attestation",
    "hash_node_runtime_identity_binding",
    "hash_node_runtime_credential",
    "is_node_measured_attestation_fresh",
    "is_node_runtime_credential_expired",
    "measured_attestation_freshness_seconds",
    "node_runtime_credential_expires_at",
    "rotate_node_runtime_credential",
    "runtime_identity_proof_from_verified_context",
    "verified_node_runtime_identity_from_jwt_svid",
    "verified_node_runtime_identity_from_headers",
    "verified_measured_attestation_context",
    "verified_runtime_identity_failure_reason",
    "verify_node_runtime_identity_binding",
    "verify_node_runtime_credential",
    "HeartbeatRequest",
    "process_heartbeat",
    "trigger_node_healing",
    "node_readiness",
    "get_node_telemetry_data",
    "check_node_access",
    "get_node_agent_config",
    "list_all_mesh_nodes",
    "AccessCheckRequest",
]

