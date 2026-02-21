"""
MaaS Nodes Endpoints - Node registration and management.

Provides REST API endpoints for node registration, heartbeats, and revocation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import UserContext, get_current_user, require_mesh_access
from ..models import NodeHeartbeatRequest, NodeRegisterRequest, NodeRegisterResponse
from ..registry import (
    add_pending_node,
    get_node_telemetry,
    get_pending_nodes,
    is_node_revoked,
    remove_pending_node,
    update_node_telemetry,
)
from ..services import MeshProvisioner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["nodes"])


# Service instance
_provisioner: Optional[MeshProvisioner] = None


def get_provisioner() -> MeshProvisioner:
    """Get or create the mesh provisioner."""
    global _provisioner
    if _provisioner is None:
        _provisioner = MeshProvisioner()
    return _provisioner


@router.post(
    "/register",
    response_model=NodeRegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new node",
    description="Submit a node registration request for approval.",
)
async def register_node(
    request: NodeRegisterRequest,
    user: UserContext = Depends(get_current_user),
) -> NodeRegisterResponse:
    """
    Register a new node with the mesh.

    The node will be in pending state until approved by the mesh owner.
    """
    # Check mesh access
    await require_mesh_access(request.mesh_id, user)

    # Check if node is revoked
    if is_node_revoked(request.mesh_id, request.node_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Node {request.node_id} is revoked",
        )

    # Add to pending nodes
    add_pending_node(request.mesh_id, request.node_id, {
        "public_key": request.public_key,
        "capabilities": request.capabilities,
        "metadata": request.metadata,
        "requested_at": datetime.utcnow().isoformat(),
        "requested_by": user.user_id,
    })

    return NodeRegisterResponse(
        node_id=request.node_id,
        mesh_id=request.mesh_id,
        status="pending",
        message="Node registration submitted for approval",
    )


@router.post(
    "/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Submit node heartbeat",
    description="Submit telemetry data from a node.",
)
async def node_heartbeat(
    request: NodeHeartbeatRequest,
) -> Dict[str, Any]:
    """
    Submit a node heartbeat.

    This endpoint is called by nodes themselves, not users.
    In production, this would use node authentication (SPIFFE SVID).
    """
    # Update telemetry
    update_node_telemetry(request.node_id, {
        "mesh_id": request.mesh_id,
        "cpu_percent": request.cpu_percent,
        "memory_percent": request.memory_percent,
        "active_connections": request.active_connections,
        "timestamp": datetime.utcnow().isoformat(),
        "custom_metrics": request.custom_metrics,
    })

    return {
        "status": "ok",
        "node_id": request.node_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get(
    "/{mesh_id}/pending",
    summary="List pending nodes",
    description="Get all nodes pending approval for a mesh.",
)
async def list_pending_nodes(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all pending node registrations for a mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    pending = get_pending_nodes(mesh_id)

    return [
        {
            "node_id": node_id,
            "mesh_id": mesh_id,
            **data,
        }
        for node_id, data in pending.items()
    ]


@router.post(
    "/{mesh_id}/{node_id}/approve",
    summary="Approve node registration",
    description="Approve a pending node registration.",
)
async def approve_node(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Approve a pending node registration."""
    # Check access
    await require_mesh_access(mesh_id, user)

    provisioner = get_provisioner()

    try:
        result = await provisioner.approve_node(
            mesh_id=mesh_id,
            node_id=node_id,
            actor=user.user_id,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{mesh_id}/{node_id}/revoke",
    summary="Revoke node",
    description="Revoke a node from the mesh.",
)
async def revoke_node(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
    reason: str = Query(..., description="Revocation reason"),
) -> Dict[str, Any]:
    """Revoke a node from the mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    provisioner = get_provisioner()

    try:
        result = await provisioner.revoke_node(
            mesh_id=mesh_id,
            node_id=node_id,
            actor=user.user_id,
            reason=reason,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{mesh_id}/{node_id}/telemetry",
    summary="Get node telemetry",
    description="Get latest telemetry data for a node.",
)
async def get_telemetry(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get telemetry data for a node."""
    # Check access
    await require_mesh_access(mesh_id, user)

    telemetry = get_node_telemetry(node_id)

    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for node {node_id}",
        )

    return telemetry


@router.post(
    "/{mesh_id}/{node_id}/reissue",
    summary="Request credential reissue",
    description="Request a one-time token for credential reissue.",
)
async def request_reissue(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Request a credential reissue token.

    Returns a one-time token that can be used to reissue credentials
    for a compromised or expired node certificate.
    """
    import secrets
    from datetime import timedelta
    from ..registry import add_reissue_token

    # Check access
    await require_mesh_access(mesh_id, user)

    # Generate one-time token
    token = f"reissue_{secrets.token_urlsafe(32)}"

    # Store token
    add_reissue_token(mesh_id, token, {
        "node_id": node_id,
        "issued_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "used": False,
        "issued_by": user.user_id,
    })

    return {
        "node_id": node_id,
        "mesh_id": mesh_id,
        "reissue_token": token,
        "expires_in": 3600,
    }


__all__ = ["router"]
