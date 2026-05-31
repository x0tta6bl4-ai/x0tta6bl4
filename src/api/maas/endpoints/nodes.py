"""
MaaS Nodes Endpoints - Node registration and management.

Provides REST API endpoints for node registration, heartbeats, and revocation.
Modular implementation using src.api.maas.nodes package.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.database import MeshInstance as DBMeshInstance, get_db
from ..auth import UserContext, get_current_user
from ..models import NodeHeartbeatRequest, NodeRegisterRequest, NodeRegisterResponse
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
    list_all_mesh_nodes,
    HeartbeatRequest as CoreHeartbeatRequest,
    AccessCheckRequest,
)

logger = logging.getLogger(__name__)

# No prefix here to support /{mesh_id}/nodes/... structure directly
router = APIRouter(tags=["nodes"])


def _ensure_mesh_db_mirror(mesh_id: str, db: Session) -> None:
    """Mirror an in-memory mesh registry entry into this DB session if needed."""
    if db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first():
        return

    from ..registry import get_mesh as get_registry_mesh

    instance = get_registry_mesh(mesh_id)
    if instance is None:
        return

    db.add(
        DBMeshInstance(
            id=instance.mesh_id,
            name=instance.name,
            owner_id=instance.owner_id,
            plan=instance.plan,
            region=getattr(instance, "region", None) or "global",
            nodes=getattr(instance, "target_nodes", 0) or len(instance.node_instances),
            pqc_profile=getattr(instance, "pqc_profile", None) or "edge",
            status=instance.status,
            join_token=getattr(instance, "join_token", ""),
            join_token_expires_at=getattr(instance, "join_token_expires_at", None),
            pqc_enabled=getattr(instance, "pqc_enabled", True),
            obfuscation=getattr(instance, "obfuscation", "none"),
            traffic_profile=getattr(instance, "traffic_profile", "none"),
        )
    )
    db.commit()


def _node_register_response(mesh_id: str, result: Dict[str, Any]) -> NodeRegisterResponse:
    return NodeRegisterResponse(
        mesh_id=mesh_id,
        node_id=str(result["node_id"]),
        status=str(result["status"]),
        message="Node registration pending approval",
    )


@router.get("/nodes/readiness")
async def node_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    """Check local dependency status for node management."""
    return await core_node_readiness(request, db)


@router.post("/nodes/register", response_model=NodeRegisterResponse, status_code=status.HTTP_202_ACCEPTED)
async def register_node_no_path(
    req: NodeRegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new node (pending approval) using mesh_id from payload."""
    if not req.mesh_id:
        raise HTTPException(status_code=400, detail="mesh_id is required in payload")
    _ensure_mesh_db_mirror(req.mesh_id, db)
    result = core_register_node(
        mesh_id=req.mesh_id,
        enrollment_token=req.enrollment_token or "",
        db=db,
        node_id=req.node_id,
        device_class=req.device_class,
        hardware_id=req.hardware_id,
    )
    return _node_register_response(req.mesh_id, result)


@router.post("/{mesh_id}/nodes/register", response_model=NodeRegisterResponse, status_code=status.HTTP_202_ACCEPTED)
async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new node (pending approval)."""
    _ensure_mesh_db_mirror(mesh_id, db)
    result = core_register_node(
        mesh_id=mesh_id,
        enrollment_token=req.enrollment_token or "",
        db=db,
        node_id=req.node_id,
        device_class=req.device_class,
        hardware_id=req.hardware_id,
    )
    return _node_register_response(mesh_id, result)


@router.get("/{mesh_id}/nodes/pending")
async def list_pending(
    mesh_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """List nodes awaiting approval."""
    return core_list_pending_nodes(mesh_id, current_user, db)


@router.post("/{mesh_id}/nodes/{node_id}/heartbeat")
async def node_heartbeat(
    mesh_id: str,
    node_id: str,
    req: NodeHeartbeatRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Update node heartbeat and telemetry."""
    # Ensure node_id is consistent
    effective_node_id = req.node_id or node_id

    core_req = CoreHeartbeatRequest(
        status="healthy",
        cpu_percent=req.cpu_percent if req.cpu_percent is not None else req.cpu_usage,
        mem_percent=(
            req.memory_percent
            if req.memory_percent is not None
            else req.memory_usage
        ),
        active_connections=(
            req.active_connections
            if req.active_connections is not None
            else req.neighbors_count
        ),
        custom_metrics={
            **(req.custom_metrics or {}),
            "routing_table_size": req.routing_table_size,
            "uptime": req.uptime,
        },
    )
    return core_process_heartbeat(mesh_id, effective_node_id, core_req, db, request)


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
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch allowed policies and peer tags for an agent."""
    return get_node_agent_config(mesh_id, node_id, db, current_user)


@router.get("/{mesh_id}/nodes/all")
async def list_all_nodes(
    mesh_id: str,
    node_status: Optional[str] = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all nodes in a mesh."""
    return list_all_mesh_nodes(mesh_id, db, current_user, node_status)


@router.post("/{mesh_id}/nodes/{node_id}/approve")
async def approve_node(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
    attestation_data: Optional[Dict[str, Any]] = None
):
    """Approve a pending node."""
    return core_approve_node(mesh_id, node_id, db, current_user, attestation_data)


@router.post("/{mesh_id}/nodes/{node_id}/revoke")
async def revoke_node(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """Revoke node access."""
    return core_revoke_node(mesh_id, node_id, db, current_user)


@router.delete("/{mesh_id}/nodes/{node_id}")
async def delete_node(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """Delete a node permanently."""
    return core_delete_node(mesh_id, node_id, db, current_user)


@router.post("/{mesh_id}/nodes/{node_id}/heal")
async def heal_node(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
    request: Request = None,
):
    """Trigger healing for a node."""
    return await trigger_node_healing(mesh_id, node_id, db, current_user, request)
