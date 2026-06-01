"""
MaaS Nodes Endpoints - Node registration and management.

Provides REST API endpoints for node registration, heartbeats, and revocation.
Modular implementation using src.api.maas.nodes package.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database import MeshInstance as DBMeshInstance, MeshNode, get_db
from ..auth import UserContext, get_current_user, get_optional_current_user
from ..models import (
    NodeApproveRequest,
    NodeHeartbeatRequest,
    NodeMeasuredAttestationRefreshRequest,
    NodeRegisterRequest,
    NodeRegisterResponse,
    NodeRuntimeIdentityBindRequest,
    NodeRuntimeIdentityBindResponse,
    NodeRuntimeCredentialRotateRequest,
    NodeRuntimeCredentialRotateResponse,
)
from ..nodes import (
    register_node as core_register_node,
    list_pending_nodes as core_list_pending_nodes,
    approve_node as core_approve_node,
    revoke_node as core_revoke_node,
    delete_node as core_delete_node,
    process_heartbeat as core_process_heartbeat,
    trigger_node_healing,
    node_readiness as core_node_readiness,
    get_node_telemetry_data,
    check_node_access,
    get_node_agent_config,
    is_node_measured_attestation_fresh,
    list_all_mesh_nodes,
    bind_node_runtime_identity as core_bind_node_runtime_identity,
    is_node_runtime_credential_expired,
    rotate_node_runtime_credential as core_rotate_node_runtime_credential,
    runtime_identity_proof_from_verified_context,
    verified_measured_attestation_context,
    verified_node_runtime_identity_from_jwt_svid,
    verified_node_runtime_identity_from_headers,
    verified_runtime_identity_failure_reason,
    verify_node_runtime_identity_binding,
    verify_node_runtime_credential,
    HeartbeatRequest as CoreHeartbeatRequest,
    AccessCheckRequest,
)

logger = logging.getLogger(__name__)
_LIVE_RUNTIME_IDENTITY_BINDING_TYPES = {"verified_spiffe_svid", "verified_jwt_svid"}

# No prefix here to support /{mesh_id}/nodes/... structure directly
router = APIRouter(tags=["nodes"])


def _request_client_host(request: Request | None) -> str | None:
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def _verified_runtime_identity_context_from_request(
    request: Request | None,
) -> Dict[str, Any] | None:
    if request is None:
        return None
    return verified_node_runtime_identity_from_headers(
        request.headers,
        client_host=_request_client_host(request),
    )


def _jwt_svid_runtime_identity_context_from_request(
    request: Request | None,
    *,
    expected_node_id: str | None,
) -> Dict[str, Any] | None:
    if request is None:
        return None
    return verified_node_runtime_identity_from_jwt_svid(
        request.headers,
        expected_node_id=expected_node_id,
    )


def _runtime_identity_context_for_bound_node(
    request: Request | None,
    node: MeshNode,
) -> Dict[str, Any] | None:
    binding_type = str(getattr(node, "runtime_identity_binding_type", "") or "").lower()
    if binding_type == "verified_jwt_svid":
        return _jwt_svid_runtime_identity_context_from_request(
            request,
            expected_node_id=str(getattr(node, "id", "") or ""),
        )
    return _verified_runtime_identity_context_from_request(request)


def _live_runtime_identity_failure_detail(
    binding_type: str,
    verified_identity: Dict[str, Any] | None,
) -> str:
    reason = verified_runtime_identity_failure_reason(verified_identity)
    if binding_type == "verified_jwt_svid":
        return "Verified JWT-SVID runtime identity required: " + reason
    if binding_type == "verified_spiffe_svid":
        return "Trusted verified runtime identity required: " + reason
    return "Live runtime identity required: " + reason


def _ensure_live_runtime_identity_for_bound_node(
    node: MeshNode,
    *,
    request: Request | None,
    db: Session,
) -> None:
    binding_type = str(getattr(node, "runtime_identity_binding_type", "") or "").lower()
    stored_hash = getattr(node, "runtime_identity_binding_hash", None)
    if binding_type == "measured_attestation" and stored_hash:
        if not is_node_measured_attestation_fresh(node):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Fresh measured attestation required",
            )
        return
    if binding_type not in _LIVE_RUNTIME_IDENTITY_BINDING_TYPES or not stored_hash:
        return

    verified_identity = _runtime_identity_context_for_bound_node(request, node)
    if not verify_node_runtime_identity_binding(
        None,
        stored_hash=stored_hash,
        stored_binding_type=binding_type,
        verified_identity_context=verified_identity,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_live_runtime_identity_failure_detail(binding_type, verified_identity),
        )

    node.runtime_identity_last_verified_at = datetime.utcnow()
    db.commit()


def _ensure_mesh_db_mirror(mesh_id: str, db: Session) -> None:
    """Helper to ensure mesh metadata exists in DB for foreign key constraints."""
    exists = db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
    if not exists:
        from ..registry import get_mesh

        registry_mesh = get_mesh(mesh_id)
        if registry_mesh is None:
            return

        logger.info(f"Creating DB mirror for mesh {mesh_id}")
        new_mesh = DBMeshInstance(
            id=mesh_id,
            name=str(getattr(registry_mesh, "name", None) or f"Mesh {mesh_id[:8]}"),
            owner_id=getattr(registry_mesh, "owner_id", None),
            plan=str(getattr(registry_mesh, "plan", None) or "starter"),
            region=str(getattr(registry_mesh, "region", None) or "global"),
            nodes=int(getattr(registry_mesh, "target_nodes", 0) or 0),
            pqc_profile=str(getattr(registry_mesh, "pqc_profile", None) or "edge"),
            status=str(getattr(registry_mesh, "status", None) or "active"),
            join_token=getattr(registry_mesh, "join_token", None),
            join_token_expires_at=getattr(
                registry_mesh,
                "join_token_expires_at",
                None,
            ),
            pqc_enabled=bool(getattr(registry_mesh, "pqc_enabled", True)),
            obfuscation=str(getattr(registry_mesh, "obfuscation", None) or "none"),
            traffic_profile=str(
                getattr(registry_mesh, "traffic_profile", None) or "none"
            ),
        )
        db.add(new_mesh)
        db.commit()


def _load_node_or_404(mesh_id: str, node_id: str, db: Session) -> MeshNode:
    node = (
        db.query(MeshNode)
        .filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id)
        .first()
    )
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def _ensure_node_runtime_credential(
    mesh_id: str,
    node_id: str,
    *,
    db: Session,
    runtime_credential: str | None,
) -> MeshNode:
    node = _load_node_or_404(mesh_id, node_id, db)
    if node.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Node must be approved before runtime access",
        )
    if not verify_node_runtime_credential(
        runtime_credential,
        getattr(node, "runtime_credential_hash", None),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid node runtime credential required",
        )
    if is_node_runtime_credential_expired(
        getattr(node, "runtime_credential_expires_at", None)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Node runtime credential expired",
        )
    return node


def _ensure_node_config_access(
    mesh_id: str,
    node_id: str,
    *,
    db: Session,
    current_user: UserContext | None,
    runtime_credential: str | None,
    request: Request | None,
) -> UserContext | None:
    if current_user is not None:
        return current_user

    mesh = db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
    if mesh is None:
        raise HTTPException(status_code=404, detail="Mesh not found")

    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db,
        runtime_credential=runtime_credential,
    )
    _ensure_live_runtime_identity_for_bound_node(node, request=request, db=db)
    return None


@router.post("/{mesh_id}/nodes/register", response_model=NodeRegisterResponse)
async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Register a new node in the mesh."""
    _ensure_mesh_db_mirror(mesh_id, db)
    if not req.enrollment_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="enrollment_token is required",
        )
    result = core_register_node(
        mesh_id,
        req.enrollment_token,
        db,
        node_id=req.node_id,
        device_class=req.device_class,
        hardware_id=req.hardware_id,
        enclave_enabled=req.enclave_enabled,
    )
    return {
        "mesh_id": mesh_id,
        "node_id": result["node_id"],
        "status": result["status"],
        "message": "Node registered and pending approval",
        "api_key": result.get("api_key"),
        "node_runtime_credential": result.get("node_runtime_credential"),
        "node_runtime_credential_expires_at": result.get(
            "node_runtime_credential_expires_at"
        ),
        "raw_runtime_credential_returned_once": result.get(
            "raw_runtime_credential_returned_once"
        )
        is True,
    }


@router.get("/{mesh_id}/nodes/pending")
async def list_pending_nodes(
    mesh_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List nodes awaiting approval."""
    if getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    pending_nodes = core_list_pending_nodes(mesh_id, current_user, db)
    return {
        "mesh_id": mesh_id,
        "pending": {
            node.id: {
                "node_id": node.id,
                "device_class": node.device_class,
                "hardware_id": node.hardware_id,
                "status": node.status,
            }
            for node in pending_nodes
        },
    }


@router.post("/{mesh_id}/nodes/{node_id}/approve")
async def approve_node(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Approve a pending node registration."""
    return core_approve_node(
        mesh_id,
        node_id,
        db,
        current_user,
        attestation_data=req.attestation_data if req else None,
    )


@router.post("/{mesh_id}/nodes/{node_id}/revoke")
async def revoke_node(
    mesh_id: str,
    node_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Revoke a node's mesh access."""
    mesh = db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
    current_user_id = getattr(
        current_user,
        "id",
        getattr(current_user, "user_id", None),
    )
    is_owner = bool(mesh is not None and mesh.owner_id == current_user_id)
    if not is_owner and getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    return core_revoke_node(mesh_id, node_id, db, current_user)


@router.post(
    "/{mesh_id}/nodes/{node_id}/runtime-credential/rotate",
    response_model=NodeRuntimeCredentialRotateResponse,
)
async def rotate_node_runtime_credential(
    mesh_id: str,
    node_id: str,
    req: NodeRuntimeCredentialRotateRequest | None = None,
    current_user: Optional[UserContext] = Depends(get_optional_current_user),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Rotate a node-bound runtime credential and return the raw value once."""
    node = _load_node_or_404(mesh_id, node_id, db)
    if current_user is None:
        node = _ensure_node_runtime_credential(
            mesh_id,
            node_id,
            db=db,
            runtime_credential=x_api_key,
        )
        binding_type = str(
            getattr(node, "runtime_identity_binding_type", "") or ""
        ).lower()
        if (
            binding_type == "measured_attestation"
            and getattr(node, "runtime_identity_binding_hash", None)
            and not is_node_measured_attestation_fresh(node)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Fresh measured attestation required",
            )
        verified_identity = _runtime_identity_context_for_bound_node(request, node)
        if not verify_node_runtime_identity_binding(
            req.identity_proof if req else None,
            stored_hash=getattr(node, "runtime_identity_binding_hash", None),
            stored_binding_type=getattr(node, "runtime_identity_binding_type", None),
            verified_identity_context=verified_identity,
        ):
            detail = "Valid runtime identity proof required"
            if getattr(node, "runtime_identity_binding_type", None) == "verified_spiffe_svid":
                detail = (
                    "Trusted verified runtime identity required: "
                    + verified_runtime_identity_failure_reason(verified_identity)
                )
            if getattr(node, "runtime_identity_binding_type", None) == "verified_jwt_svid":
                detail = (
                    "Verified JWT-SVID runtime identity required: "
                    + verified_runtime_identity_failure_reason(verified_identity)
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail,
            )
        if (
            getattr(node, "runtime_identity_binding_hash", None)
            and binding_type != "measured_attestation"
        ):
            from datetime import datetime

            node.runtime_identity_last_verified_at = datetime.utcnow()
    elif getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )

    rotated = core_rotate_node_runtime_credential(
        node,
        db,
        ttl_seconds=(req.ttl_seconds if req else None),
    )
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "rotated",
        "api_key": rotated["api_key"],
        "node_runtime_credential": rotated["node_runtime_credential"],
        "node_runtime_credential_expires_at": rotated[
            "runtime_credential_expires_at"
        ],
        "node_runtime_credential_rotated_at": rotated[
            "runtime_credential_rotated_at"
        ],
        "raw_runtime_credential_returned_once": True,
    }


@router.post(
    "/{mesh_id}/nodes/{node_id}/runtime-identity/bind",
    response_model=NodeRuntimeIdentityBindResponse,
)
async def bind_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    req: NodeRuntimeIdentityBindRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bind a node to hash-only runtime identity proof metadata."""
    if getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    if req.binding_type in {"verified_spiffe_svid", "verified_jwt_svid"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use verified runtime identity bind endpoint for verified SVID bindings",
        )

    node = _load_node_or_404(mesh_id, node_id, db)
    bound = core_bind_node_runtime_identity(node, db, req)
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": bound["runtime_identity_binding_type"],
        "runtime_identity_binding_hash_prefix": bound[
            "runtime_identity_binding_hash"
        ][:12],
        "runtime_identity_bound_at": bound["runtime_identity_bound_at"],
        "runtime_identity_last_verified_at": bound[
            "runtime_identity_last_verified_at"
        ],
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": False,
        "trusted_runtime_identity_proxy_claim_allowed": False,
        "api_side_jwt_svid_verification_claim_allowed": False,
        "runtime_identity_verification_source": None,
        "production_trust_finality_claim_allowed": False,
    }


@router.post(
    "/{mesh_id}/nodes/{node_id}/runtime-identity/refresh-measured-attestation",
    response_model=NodeRuntimeIdentityBindResponse,
)
async def refresh_measured_attestation_runtime_identity(
    mesh_id: str,
    node_id: str,
    req: NodeMeasuredAttestationRefreshRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Refresh a node measured-attestation binding with redacted proof material."""
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db,
        runtime_credential=x_api_key,
    )
    verified_identity = verified_measured_attestation_context(req.attestation_data)
    proof = runtime_identity_proof_from_verified_context(verified_identity)
    bound = core_bind_node_runtime_identity(node, db, proof)
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": bound["runtime_identity_binding_type"],
        "runtime_identity_binding_hash_prefix": bound[
            "runtime_identity_binding_hash"
        ][:12],
        "runtime_identity_bound_at": bound["runtime_identity_bound_at"],
        "runtime_identity_last_verified_at": bound[
            "runtime_identity_last_verified_at"
        ],
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": False,
        "trusted_runtime_identity_proxy_claim_allowed": False,
        "api_side_jwt_svid_verification_claim_allowed": False,
        "runtime_identity_verification_source": str(
            verified_identity.get("source") or "tee"
        ),
        "attestation_verifier_backend": str(
            verified_identity.get("attestation_verifier_backend") or ""
        ),
        "attestation_verifier_provenance": dict(
            verified_identity.get("attestation_verifier_provenance") or {}
        ),
        "production_attestation_verifier_claim_allowed": bool(
            verified_identity.get("production_attestation_verifier_claim_allowed")
        ),
        "production_trust_finality_claim_allowed": False,
    }


@router.post(
    "/{mesh_id}/nodes/{node_id}/runtime-identity/bind-verified",
    response_model=NodeRuntimeIdentityBindResponse,
)
async def bind_verified_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Bind a node to SPIFFE identity verified by a trusted mTLS proxy."""
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db,
        runtime_credential=x_api_key,
    )
    verified_identity = _verified_runtime_identity_context_from_request(request)
    if not verified_identity or verified_identity.get("verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Trusted verified runtime identity required: "
                + verified_runtime_identity_failure_reason(verified_identity)
            ),
        )

    proof = runtime_identity_proof_from_verified_context(verified_identity)
    bound = core_bind_node_runtime_identity(node, db, proof)
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": bound["runtime_identity_binding_type"],
        "runtime_identity_binding_hash_prefix": bound[
            "runtime_identity_binding_hash"
        ][:12],
        "runtime_identity_bound_at": bound["runtime_identity_bound_at"],
        "runtime_identity_last_verified_at": bound[
            "runtime_identity_last_verified_at"
        ],
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": True,
        "trusted_runtime_identity_proxy_claim_allowed": True,
        "api_side_jwt_svid_verification_claim_allowed": False,
        "runtime_identity_verification_source": str(
            verified_identity.get("source") or "trusted_proxy"
        ),
        "production_trust_finality_claim_allowed": False,
    }


@router.post(
    "/{mesh_id}/nodes/{node_id}/runtime-identity/bind-jwt-svid",
    response_model=NodeRuntimeIdentityBindResponse,
)
async def bind_jwt_svid_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Bind a node to a JWT-SVID verified cryptographically by the API."""
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db,
        runtime_credential=x_api_key,
    )
    verified_identity = _jwt_svid_runtime_identity_context_from_request(
        request,
        expected_node_id=node_id,
    )
    if not verified_identity or verified_identity.get("verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Verified JWT-SVID runtime identity required: "
                + verified_runtime_identity_failure_reason(verified_identity)
            ),
        )

    proof = runtime_identity_proof_from_verified_context(verified_identity)
    bound = core_bind_node_runtime_identity(node, db, proof)
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": bound["runtime_identity_binding_type"],
        "runtime_identity_binding_hash_prefix": bound[
            "runtime_identity_binding_hash"
        ][:12],
        "runtime_identity_bound_at": bound["runtime_identity_bound_at"],
        "runtime_identity_last_verified_at": bound[
            "runtime_identity_last_verified_at"
        ],
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": True,
        "trusted_runtime_identity_proxy_claim_allowed": False,
        "api_side_jwt_svid_verification_claim_allowed": True,
        "runtime_identity_verification_source": str(
            verified_identity.get("source") or "jwt_svid"
        ),
        "production_trust_finality_claim_allowed": False,
    }


@router.delete("/{mesh_id}/nodes/{node_id}")
async def delete_node(
    mesh_id: str,
    node_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Delete a node registration."""
    return core_delete_node(mesh_id, node_id, db, current_user)


@router.post("/{mesh_id}/nodes/{node_id}/heartbeat")
async def node_heartbeat(
    mesh_id: str,
    node_id: str,
    req: NodeHeartbeatRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Update node heartbeat and telemetry."""
    # Ensure node_id is consistent
    if req.node_id is not None and req.node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Heartbeat node_id must match path node_id",
        )
    effective_node_id = node_id
    node = _ensure_node_runtime_credential(
        mesh_id,
        effective_node_id,
        db=db,
        runtime_credential=x_api_key,
    )
    _ensure_live_runtime_identity_for_bound_node(node, request=request, db=db)

    core_req = CoreHeartbeatRequest(
        status=req.status,
        cpu_percent=req.cpu_percent if req.cpu_percent is not None else req.cpu_usage,
        mem_percent=(
            req.memory_percent
            if req.memory_percent is not None
            else req.memory_usage
        ),
        latency_ms=req.latency_ms,
        traffic_mbps=req.traffic_mbps,
        active_connections=(
            req.active_connections
            if req.active_connections is not None
            else req.neighbors_count
        ),
        dataplane_probe_target=req.dataplane_probe_target or req.ip_address,
        custom_metrics={
            **(req.custom_metrics or {}),
            "routing_table_size": req.routing_table_size,
            "uptime": req.uptime,
        },
    )
    return core_process_heartbeat(mesh_id, effective_node_id, core_req, db, request)


@router.get("/{mesh_id}/nodes/all")
async def list_mesh_nodes_all(
    mesh_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all nodes in a mesh under the legacy /nodes/all path."""
    if getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    return list_all_mesh_nodes(mesh_id, db, current_user)


@router.get("/{mesh_id}/nodes/{node_id}/telemetry")
async def get_node_telemetry(
    mesh_id: str,
    node_id: str,
    history_limit: int = Query(default=20, ge=1, le=200),
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return node telemetry snapshot + recent history."""
    return get_node_telemetry_data(mesh_id, node_id, db, current_user, history_limit)


@router.post("/{mesh_id}/nodes/check-access")
async def check_access(
    mesh_id: str,
    req: AccessCheckRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-side ACL enforcement."""
    return check_node_access(mesh_id, req, db, current_user)


@router.get("/{mesh_id}/node-config/{node_id}")
async def get_node_config(
    mesh_id: str,
    node_id: str,
    current_user: Optional[UserContext] = Depends(get_optional_current_user),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Get node agent configuration."""
    effective_user = _ensure_node_config_access(
        mesh_id,
        node_id,
        db=db,
        current_user=current_user,
        runtime_credential=x_api_key,
        request=request,
    )
    return get_node_agent_config(mesh_id, node_id, db, effective_user)


@router.get("/{mesh_id}/nodes")
async def list_mesh_nodes(
    mesh_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all nodes in a mesh."""
    if getattr(current_user, "role", "user") not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    return list_all_mesh_nodes(mesh_id, db, current_user)


@router.post("/{mesh_id}/nodes/{node_id}/heal")
async def heal_node(
    mesh_id: str,
    node_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Trigger node healing."""
    return await trigger_node_healing(mesh_id, node_id, db, current_user, request)


@router.get("/{mesh_id}/nodes/{node_id}/readiness")
async def node_readiness(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
):
    """Check node readiness."""
    return await core_node_readiness(mesh_id, node_id, db)
