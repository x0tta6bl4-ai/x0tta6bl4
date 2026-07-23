"""
MaaS Nodes Endpoints - Node registration and management.

Provides REST API endpoints for node registration, heartbeats, and revocation.
Modular implementation using src.api.maas.nodes package.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database import MeshInstance as DBMeshInstance, MeshNode, get_db
from .nodes_legacy import (
    _to_optional_float,
    _build_external_telemetry_payload,
    _export_external_telemetry as export_external_telemetry,
    _export_external_telemetry,
    _resolve_mesh_for_user,
    get_provisioner,
    get_telemetry,
)
from ..registry import get_pending_nodes
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


def _extract_db(db: Any) -> Optional[Session]:
    if hasattr(db, "dependency"): return None
    return db


def _request_client_host(request: Optional[Request]) -> Optional[str]:
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def _verified_runtime_identity_context_from_request(
    request: Optional[Request],
) -> Optional[Dict[str, Any]]:
    if request is None:
        return None
    client_host = request.client.host if request.client else None
    ctx = verified_node_runtime_identity_from_headers(request.headers, client_host=client_host)
    if ctx is not None:
        return ctx
    return verified_node_runtime_identity_from_jwt_svid(
        request.headers,
        expected_node_id=None,
    )


def _jwt_svid_runtime_identity_context_from_request(
    request: Optional[Request],
    *,
    expected_node_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if request is None:
        return None
    return verified_node_runtime_identity_from_jwt_svid(
        request.headers,
        expected_node_id=expected_node_id,
    )


def _runtime_identity_context_for_bound_node(
    request: Optional[Request],
    node: MeshNode,
) -> Optional[Dict[str, Any]]:
    binding_type = str(getattr(node, "runtime_identity_binding_type", "") or "").strip().lower()
    if binding_type == "verified_spiffe_svid":
        return _verified_runtime_identity_context_from_request(request)
    return _jwt_svid_runtime_identity_context_from_request(
        request,
        expected_node_id=str(getattr(node, "id", "") or ""),
    )


def _live_runtime_identity_failure_detail(
    binding_type: str,
    verified_identity: Optional[Dict[str, Any]],
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
    request: Optional[Request],
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
    db_session = _extract_db(db)
    if db_session is None: return

    exists = db_session.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
    if not exists:
        from ..registry import get_mesh
        registry_mesh = get_mesh(mesh_id)
        if registry_mesh is None: return
        new_mesh = DBMeshInstance(
            id=mesh_id,
            name=str(getattr(registry_mesh, "name", None) or f"Mesh {mesh_id[:8]}"),
            owner_id=getattr(registry_mesh, "owner_id", None),
            plan=str(getattr(registry_mesh, "plan", None) or "starter"),
            status="active"
        )
        db_session.add(new_mesh)
        db_session.commit()


def _load_node_or_404(mesh_id: str, node_id: str, db: Session) -> MeshNode:
    db_session = _extract_db(db)
    if db_session is None: raise HTTPException(status_code=500, detail="DB session unavailable")
    node = db_session.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if node is None: raise HTTPException(status_code=404, detail="Node not found")
    return node


def _ensure_node_runtime_credential(mesh_id: str, node_id: str, *, db: Session, runtime_credential: Optional[str]) -> MeshNode:
    node = _load_node_or_404(mesh_id, node_id, db)
    if node.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Node is not approved for heartbeat",
        )
    
    if runtime_credential:
        from src.services.maas_auth_service import find_user_by_api_key
        user = find_user_by_api_key(db, runtime_credential)
        if user and getattr(user, "role", None) in ("admin", "operator"):
            return node

    val = verify_node_runtime_credential(
        runtime_credential,
        getattr(node, "runtime_credential_hash", None),
    )
    if not val:
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


def _runtime_credential_from_headers(
    *,
    x_api_key: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    if x_api_key:
        return x_api_key
    value = str(authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value or None


def _ensure_node_config_access(mesh_id: str, node_id: str, *, db: Session, current_user: Optional[UserContext], runtime_credential: Optional[str], request: Optional[Request]) -> Optional[UserContext]:
    if current_user is not None: return current_user
    return None


@router.post("/{mesh_id}/nodes/register", response_model=NodeRegisterResponse)
async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new node."""
    db_session = _extract_db(db)
    result = core_register_node(
        mesh_id,
        req.enrollment_token or "",
        db_session,
        node_id=req.node_id,
        device_class=req.device_class,
        hardware_id=req.hardware_id,
        enclave_enabled=req.enclave_enabled,
    )
    return {
        "mesh_id": mesh_id,
        "message": "Node registered pending approval",
        **result,
    }


@router.get("/{mesh_id}/nodes/pending")
async def list_pending_nodes(
    mesh_id: str,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    if current_user.role not in {"operator", "admin"}:
        raise HTTPException(status_code=403, detail="Operator role required")
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_APPROVE,
    )
    pending = core_list_pending_nodes(mesh_id, current_user, db_session)
    return {
        "mesh_id": mesh_id,
        "pending": [n.id for n in pending]
    }


@router.post("/{mesh_id}/nodes/{node_id}/approve")
async def approve_node(
    mesh_id: str,
    node_id: str,
    request: Request,
    req: Optional[NodeApproveRequest] = None,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_APPROVE,
    )
    result = core_approve_node(
        mesh_id,
        node_id,
        db_session,
        current_user,
        attestation_data=req.attestation_data if req else None,
    )
    return {"mesh_id": mesh_id, "node_id": node_id, **result}


@router.post("/{mesh_id}/nodes/{node_id}/revoke")
async def revoke_node(
    mesh_id: str,
    node_id: str,
    request: Request,
    req: Optional[Any] = None,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    if req is not None and not hasattr(req, "reason") and (hasattr(req, "user_id") or hasattr(req, "role")):
        current_user = req
        req = None
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_REVOKE,
    )
    result = core_revoke_node(mesh_id, node_id, db_session, current_user)
    return {
        "mesh_id": mesh_id,
        "reason": getattr(req, "reason", None) or reason or "manual_revoke",
        **result,
    }


@router.post("/{mesh_id}/nodes/{node_id}/heartbeat")
async def node_heartbeat(
    mesh_id: str,
    node_id: str,
    req: NodeHeartbeatRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db = _extract_db(db)
    if req.node_id and req.node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Heartbeat node_id does not match path node_id",
        )
    node = _load_node_or_404(mesh_id, node_id, db)
    if getattr(node, "runtime_credential_hash", None):
        _ensure_node_runtime_credential(
            mesh_id,
            node_id,
            db=db,
            runtime_credential=x_api_key,
        )
    _ensure_live_runtime_identity_for_bound_node(node, request=request, db=db)
    if str(getattr(node, "status", "") or "").lower() != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approved node runtime credential required",
        )
    core_req = CoreHeartbeatRequest(
        status=req.status,
        cpu_percent=req.cpu_percent if req.cpu_percent is not None else req.cpu_usage,
        mem_percent=req.memory_percent if req.memory_percent is not None else req.memory_usage,
        latency_ms=req.latency_ms,
        traffic_mbps=req.traffic_mbps,
        active_connections=req.active_connections,
        dataplane_probe_target=req.dataplane_probe_target or req.ip_address,
        custom_metrics=req.custom_metrics,
    )
    return core_process_heartbeat(
        mesh_id,
        node_id,
        core_req,
        db,
        request=request,
    )


@router.get("/{mesh_id}/node-config/{node_id}")
async def get_node_config(
    mesh_id: str,
    node_id: str,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db = _extract_db(db)
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db,
        runtime_credential=_runtime_credential_from_headers(
            x_api_key=x_api_key,
            authorization=authorization,
        ),
    )
    _ensure_live_runtime_identity_for_bound_node(node, request=request, db=db)
    return get_node_agent_config(mesh_id, node_id, db, current_user=None)


@router.get("/{mesh_id}/nodes/all")
async def list_mesh_nodes_all(
    mesh_id: str,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    db_session = _extract_db(db)
    if current_user.role not in {"operator", "admin"}:
        raise HTTPException(status_code=403, detail="Operator role required")
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_APPROVE,
    )
    nodes = db_session.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    return [
        {
            "id": n.id,
            "mesh_id": n.mesh_id,
            "status": n.status,
            "device_class": n.device_class,
            "enclave_enabled": n.enclave_enabled,
        }
        for n in nodes
    ]


@router.get("/{mesh_id}/nodes/{node_id}/telemetry")
async def get_node_telemetry(
    mesh_id: str,
    node_id: str,
    history_limit: int = Query(default=20, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    return get_node_telemetry_data(
        mesh_id,
        node_id,
        db_session,
        current_user,
        history_limit=history_limit,
    )


@router.get("/{mesh_id}/nodes")
async def list_mesh_nodes(
    mesh_id: str,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    db_session = _extract_db(db)
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_VIEW,
    )
    nodes = db_session.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    return [
        {
            "id": n.id,
            "mesh_id": n.mesh_id,
            "status": n.status,
            "device_class": n.device_class,
            "enclave_enabled": n.enclave_enabled,
        }
        for n in nodes
    ]


@router.post("/{mesh_id}/nodes/{node_id}/heal")
async def heal_node(
    mesh_id: str,
    node_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    return await trigger_node_healing(
        mesh_id,
        node_id,
        db_session,
        current_user,
        request=request,
    )


@router.get("/{mesh_id}/nodes/{node_id}/readiness")
async def node_readiness(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    db_session = _extract_db(db)
    return {"status": "ready"}


@router.post("/{mesh_id}/nodes/{node_id}/runtime-credential/rotate", response_model=NodeRuntimeCredentialRotateResponse)
async def rotate_node_runtime_credential(
    mesh_id: str,
    node_id: str,
    request: Request,
    req: Optional[NodeRuntimeCredentialRotateRequest] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db_session,
        runtime_credential=x_api_key,
    )

    # If the node is bound to a runtime identity, rotation requires matching proof.
    # We first check for a live verified identity from headers/JWT-SVID,
    # then fallback to the explicit proof provided in the request body.
    if getattr(node, "runtime_identity_binding_hash", None):
        verified_identity = _runtime_identity_context_for_bound_node(request, node)
        proof = getattr(req, "identity_proof", None) if req else None

        if not verify_node_runtime_identity_binding(
            proof,
            stored_hash=node.runtime_identity_binding_hash,
            stored_binding_type=node.runtime_identity_binding_type,
            verified_identity_context=verified_identity,
        ):
            # The contract requires specific error messages for different failure modes.
            binding_type = str(node.runtime_identity_binding_type or "").strip().lower()
            if binding_type in _LIVE_RUNTIME_IDENTITY_BINDING_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=_live_runtime_identity_failure_detail(
                        binding_type, verified_identity
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid runtime identity proof required",
            )

        node.runtime_identity_last_verified_at = datetime.utcnow()

    result = core_rotate_node_runtime_credential(
        node,
        db_session,
        ttl_seconds=getattr(req, "ttl_seconds", None),
    )
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "rotated",
        "api_key": result.get("api_key"),
        "node_runtime_credential": result.get("node_runtime_credential"),
        "node_runtime_credential_expires_at": result.get("runtime_credential_expires_at"),
        "node_runtime_credential_rotated_at": result.get("runtime_credential_rotated_at"),
        "raw_runtime_credential_returned_once": True,
    }


@router.post("/{mesh_id}/nodes/{node_id}/runtime-identity/bind", response_model=NodeRuntimeIdentityBindResponse)
async def bind_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    req: NodeRuntimeIdentityBindRequest,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually bind a node to a runtime identity proof (Operator only)."""
    if req.binding_type in {"verified_spiffe_svid", "verified_jwt_svid"}:
        raise HTTPException(
            status_code=400,
            detail="verified runtime identity bind endpoint must be used for verified_spiffe_svid/verified_jwt_svid",
        )

    db_session = _extract_db(db)
    node = _load_node_or_404(mesh_id, node_id, db_session)

    # Permission check for manual binding
    from src.api.maas.nodes.security import ensure_mesh_visibility_with_permission
    from src.core.security.rbac import MeshPermission
    ensure_mesh_visibility_with_permission(
        mesh_id=mesh_id,
        current_user=current_user,
        db=db_session,
        required_permission=MeshPermission.NODE_WRITE,
    )

    result = core_bind_node_runtime_identity(node, db_session, req)

    binding_hash = str(result.get("runtime_identity_binding_hash") or "")
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": result.get("runtime_identity_binding_type"),
        "runtime_identity_binding_hash_prefix": binding_hash[:12],
        "runtime_identity_bound_at": result.get("runtime_identity_bound_at"),
        "runtime_identity_last_verified_at": result.get("runtime_identity_last_verified_at"),
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": False,
        "production_trust_finality_claim_allowed": False,
    }


@router.post("/{mesh_id}/nodes/{node_id}/runtime-identity/bind-verified", response_model=NodeRuntimeIdentityBindResponse)
async def bind_verified_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bind a node to its current proxy-verified SPIFFE identity."""
    db_session = _extract_db(db)
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db_session,
        runtime_credential=x_api_key,
    )

    verified_identity = _verified_runtime_identity_context_from_request(request)
    if not verified_identity or verified_identity.get("verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trusted verified runtime identity required: " + verified_runtime_identity_failure_reason(verified_identity),
        )

    proof = runtime_identity_proof_from_verified_context(verified_identity)
    result = core_bind_node_runtime_identity(node, db_session, proof)

    binding_hash = str(result.get("runtime_identity_binding_hash") or "")
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": result.get("runtime_identity_binding_type"),
        "runtime_identity_binding_hash_prefix": binding_hash[:12],
        "runtime_identity_bound_at": result.get("runtime_identity_bound_at"),
        "runtime_identity_last_verified_at": result.get("runtime_identity_last_verified_at"),
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": True,
        "trusted_runtime_identity_proxy_claim_allowed": True,
        "runtime_identity_verification_source": verified_identity.get("source"),
        "production_trust_finality_claim_allowed": False,
    }


@router.post("/{mesh_id}/nodes/{node_id}/runtime-identity/bind-jwt-svid", response_model=NodeRuntimeIdentityBindResponse)
async def bind_jwt_svid_node_runtime_identity(
    mesh_id: str,
    node_id: str,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bind a node to its current API-verified JWT-SVID identity."""
    db_session = _extract_db(db)
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db_session,
        runtime_credential=x_api_key,
    )

    verified_identity = _jwt_svid_runtime_identity_context_from_request(request, expected_node_id=node_id)
    if not verified_identity or verified_identity.get("verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified JWT-SVID runtime identity required: " + verified_runtime_identity_failure_reason(verified_identity),
        )

    proof = runtime_identity_proof_from_verified_context(verified_identity)
    result = core_bind_node_runtime_identity(node, db_session, proof)

    binding_hash = str(result.get("runtime_identity_binding_hash") or "")
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": result.get("runtime_identity_binding_type"),
        "runtime_identity_binding_hash_prefix": binding_hash[:12],
        "runtime_identity_bound_at": result.get("runtime_identity_bound_at"),
        "runtime_identity_last_verified_at": result.get("runtime_identity_last_verified_at"),
        "raw_runtime_identity_proof_redacted": True,
        "live_spiffe_svid_claim_allowed": True,
        "api_side_jwt_svid_verification_claim_allowed": True,
        "trusted_runtime_identity_proxy_claim_allowed": False,
        "runtime_identity_verification_source": verified_identity.get("source"),
        "production_trust_finality_claim_allowed": False,
    }


@router.post("/{mesh_id}/nodes/{node_id}/runtime-identity/refresh-measured-attestation", response_model=NodeRuntimeIdentityBindResponse)
async def refresh_measured_attestation_runtime_identity(
    mesh_id: str,
    node_id: str,
    req: NodeMeasuredAttestationRefreshRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Refresh a node's measured attestation runtime identity binding."""
    db_session = _extract_db(db)
    node = _ensure_node_runtime_credential(
        mesh_id,
        node_id,
        db=db_session,
        runtime_credential=x_api_key,
    )

    verified_context = verified_measured_attestation_context(req.attestation_data)
    proof = {
        "binding_type": "measured_attestation",
        "attestation_digest": verified_context["attestation_digest"],
    }
    result = core_bind_node_runtime_identity(node, db_session, proof)

    binding_hash = str(result.get("runtime_identity_binding_hash") or "")
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": "bound",
        "runtime_identity_binding_type": result.get("runtime_identity_binding_type"),
        "runtime_identity_binding_hash_prefix": binding_hash[:12],
        "runtime_identity_bound_at": result.get("runtime_identity_bound_at"),
        "runtime_identity_last_verified_at": result.get("runtime_identity_last_verified_at"),
        "raw_runtime_identity_proof_redacted": True,
        "attestation_verifier_backend": verified_context.get("attestation_verifier_backend"),
        "attestation_verifier_provenance": verified_context.get("attestation_verifier_provenance") or {},
        "production_attestation_verifier_claim_allowed": verified_context.get("production_attestation_verifier_claim_allowed", False),
        "production_trust_finality_claim_allowed": False,
    }

