"""
MaaS Mesh Endpoints - Mesh lifecycle management.

Provides REST API endpoints for mesh deployment, scaling, and termination.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import UserContext, get_current_user, require_mesh_access
from ..models import (
    MeshDeployRequest,
    MeshDeployResponse,
    MeshMetricsResponse,
    MeshScaleRequest,
    MeshStatusResponse,
)
from ..registry import get_all_meshes, get_mesh, get_audit_log, get_mapek_events
from ..services import MeshProvisioner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mesh", tags=["mesh"])


# Service instance (can be overridden for testing)
_provisioner: Optional[MeshProvisioner] = None


def get_provisioner() -> MeshProvisioner:
    """Get or create the mesh provisioner."""
    global _provisioner
    if _provisioner is None:
        _provisioner = MeshProvisioner()
    return _provisioner


@router.post(
    "/deploy",
    response_model=MeshDeployResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deploy a new mesh network",
    description="Create and deploy a new PQC-secured mesh network.",
)
async def deploy_mesh(
    request: MeshDeployRequest,
    user: UserContext = Depends(get_current_user),
) -> MeshDeployResponse:
    """
    Deploy a new mesh network.

    Requires authentication. Plan limits apply to node count.
    """
    provisioner = get_provisioner()

    try:
        instance = await provisioner.provision_mesh(
            owner_id=user.user_id,
            plan=request.plan,
            region=request.region,
            node_count=request.node_count,
            pqc_profile=request.pqc_profile,
            enable_consciousness=request.enable_consciousness,
        )

        return MeshDeployResponse(
            mesh_id=instance.mesh_id,
            status=instance.status,
            message="Mesh deployment initiated",
            nodes_expected=request.node_count,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to deploy mesh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deploy mesh",
        )


@router.get(
    "/list",
    response_model=List[MeshStatusResponse],
    summary="List user's meshes",
    description="Get all mesh networks owned by the authenticated user.",
)
async def list_meshes(
    user: UserContext = Depends(get_current_user),
    include_terminated: bool = Query(False, description="Include terminated meshes"),
) -> List[MeshStatusResponse]:
    """List all meshes owned by the user."""
    all_meshes = get_all_meshes()

    user_meshes = [
        mesh for mesh in all_meshes.values()
        if mesh.owner_id == user.user_id
    ]

    if not include_terminated:
        user_meshes = [
            m for m in user_meshes
            if m.status != "terminated"
        ]

    return [
        MeshStatusResponse(
            mesh_id=m.mesh_id,
            status=m.status,
            plan=m.plan,
            region=m.region,
            node_count=len(m.node_instances),
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in user_meshes
    ]


@router.get(
    "/{mesh_id}/status",
    response_model=MeshStatusResponse,
    summary="Get mesh status",
    description="Get detailed status of a mesh network.",
)
async def get_mesh_status(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> MeshStatusResponse:
    """Get status of a specific mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    return MeshStatusResponse(
        mesh_id=instance.mesh_id,
        status=instance.status,
        plan=instance.plan,
        region=instance.region,
        node_count=len(instance.node_instances),
        created_at=instance.created_at.isoformat() if instance.created_at else None,
    )


@router.get(
    "/{mesh_id}/metrics",
    response_model=MeshMetricsResponse,
    summary="Get mesh metrics",
    description="Get consciousness and MAPE-K metrics for a mesh.",
)
async def get_mesh_metrics(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> MeshMetricsResponse:
    """Get consciousness and MAPE-K metrics for a mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    # Get metrics from instance
    consciousness = instance.get_consciousness_metrics()
    mape_k = instance.get_mape_k_state()

    return MeshMetricsResponse(
        mesh_id=mesh_id,
        consciousness=consciousness,
        mape_k=mape_k,
        node_count=len(instance.node_instances),
    )


@router.post(
    "/{mesh_id}/scale",
    summary="Scale mesh nodes",
    description="Scale the number of nodes in a mesh.",
)
async def scale_mesh(
    mesh_id: str,
    request: MeshScaleRequest,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Scale mesh to target node count."""
    # Check access
    await require_mesh_access(mesh_id, user)

    provisioner = get_provisioner()

    try:
        result = await provisioner.scale_mesh(
            mesh_id=mesh_id,
            target_count=request.target_count,
            actor=user.user_id,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{mesh_id}",
    status_code=status.HTTP_200_OK,
    summary="Terminate mesh",
    description="Terminate a mesh network and all its nodes.",
)
async def terminate_mesh(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    reason: str = Query("user_request", description="Termination reason"),
) -> Dict[str, Any]:
    """Terminate a mesh network."""
    # Check access
    await require_mesh_access(mesh_id, user)

    provisioner = get_provisioner()

    try:
        result = await provisioner.terminate_mesh(
            mesh_id=mesh_id,
            actor=user.user_id,
            reason=reason,
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{mesh_id}/audit",
    summary="Get mesh audit log",
    description="Get audit log for mesh operations.",
)
async def get_mesh_audit(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    """Get audit log for a mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    log = get_audit_log(mesh_id)
    return log[-limit:]


@router.get(
    "/{mesh_id}/mapek",
    summary="Get MAPE-K events",
    description="Get MAPE-K event stream for a mesh.",
)
async def get_mesh_mapek(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    """Get MAPE-K events for a mesh."""
    # Check access
    await require_mesh_access(mesh_id, user)

    events = get_mapek_events(mesh_id)
    return events[-limit:]


__all__ = ["router"]
