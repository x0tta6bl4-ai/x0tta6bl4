"""
MaaS Mesh Endpoints - Mesh lifecycle management.

Provides REST API endpoints for mesh deployment, scaling, and termination.
"""

import logging
from datetime import datetime
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


async def _resolve_mesh_for_user(mesh_id: str, user: UserContext) -> Any:
    """
    Resolve mesh instance and validate access.

    This keeps compatibility with tests that patch `get_mesh` in this module,
    while preserving ACL checks for non-owner access in real runtime.
    """
    instance = get_mesh(mesh_id)
    if instance is None:
        await require_mesh_access(mesh_id, user)
        instance = get_mesh(mesh_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mesh {mesh_id} not found",
            )

    if instance.owner_id != user.user_id:
        await require_mesh_access(mesh_id, user)

    return instance


def _build_mesh_status_response(instance: Any) -> MeshStatusResponse:
    """Convert mesh instance-like object into MeshStatusResponse."""
    nodes = getattr(instance, "node_instances", {}) or {}
    nodes_total = len(nodes)

    if hasattr(instance, "get_uptime") and callable(instance.get_uptime):
        uptime_seconds = float(instance.get_uptime())
    else:
        created_at = getattr(instance, "created_at", None)
        if created_at and hasattr(created_at, "__sub__"):
            uptime_seconds = max((datetime.utcnow() - created_at).total_seconds(), 0.0)
        else:
            uptime_seconds = 0.0

    if hasattr(instance, "get_health_score") and callable(instance.get_health_score):
        health_score = float(instance.get_health_score())
    else:
        health_score = 1.0 if nodes_total > 0 else 0.0

    nodes_healthy = 0
    peers: List[Dict[str, Any]] = []
    for node_id, node_data in nodes.items():
        node_status = (
            node_data.get("status")
            if isinstance(node_data, dict)
            else getattr(node_data, "status", "healthy")
        )
        if node_status == "healthy":
            nodes_healthy += 1
        peers.append({
            "node_id": str(node_id),
            "status": node_status or "unknown",
        })

    return MeshStatusResponse(
        mesh_id=instance.mesh_id,
        status=instance.status,
        nodes_total=nodes_total,
        nodes_healthy=nodes_healthy,
        uptime_seconds=uptime_seconds,
        pqc_enabled=bool(getattr(instance, "pqc_enabled", True)),
        obfuscation=str(getattr(instance, "obfuscation", "none")),
        traffic_profile=str(getattr(instance, "traffic_profile", "none")),
        peers=peers,
        health_score=max(0.0, min(1.0, health_score)),
    )


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
            name=request.name,
            nodes=request.nodes,
            billing_plan=request.billing_plan,
            pqc_enabled=request.pqc_enabled,
            obfuscation=request.obfuscation,
            traffic_profile=request.traffic_profile,
            join_token_ttl_sec=request.join_token_ttl_sec,
        )

        expires_at = getattr(instance, "join_token_expires_at", None)
        if expires_at and hasattr(expires_at, "isoformat"):
            expires_at_str = expires_at.isoformat()
        else:
            expires_at_str = ""

        return MeshDeployResponse(
            mesh_id=instance.mesh_id,
            join_config={
                "enrollment_token": str(getattr(instance, "join_token", "")),
                "ttl_sec": request.join_token_ttl_sec,
            },
            dashboard_url=f"/api/v1/maas/mesh/{instance.mesh_id}/status",
            status=instance.status,
            pqc_identity={
                "enabled": bool(getattr(instance, "pqc_enabled", request.pqc_enabled)),
                "profile": str(getattr(instance, "pqc_profile", "edge")),
            },
            pqc_enabled=bool(getattr(instance, "pqc_enabled", request.pqc_enabled)),
            created_at=(
                instance.created_at.isoformat()
                if getattr(instance, "created_at", None)
                else datetime.utcnow().isoformat()
            ),
            plan=str(getattr(instance, "plan", request.billing_plan)),
            join_token_expires_at=expires_at_str,
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

    return [_build_mesh_status_response(m) for m in user_meshes]


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
    instance = await _resolve_mesh_for_user(mesh_id, user)
    return _build_mesh_status_response(instance)


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
    instance = await _resolve_mesh_for_user(mesh_id, user)

    # Get metrics from instance
    if hasattr(instance, "get_consciousness_metrics") and callable(instance.get_consciousness_metrics):
        consciousness = instance.get_consciousness_metrics()
    else:
        status = _build_mesh_status_response(instance)
        consciousness = {
            "phi_ratio": 1.0,
            "entropy": 1.0 - status.health_score,
            "harmony": status.health_score,
            "state": "AWARE",
            "nodes_total": status.nodes_total,
            "nodes_healthy": status.nodes_healthy,
        }

    if hasattr(instance, "get_mape_k_state") and callable(instance.get_mape_k_state):
        mape_k = instance.get_mape_k_state()
    else:
        mape_k = {"phase": "MONITOR", "interval_seconds": 30, "directives": {}}

    if hasattr(instance, "get_network_metrics") and callable(instance.get_network_metrics):
        network = instance.get_network_metrics()
    else:
        status = _build_mesh_status_response(instance)
        network = {
            "nodes_active": status.nodes_total,
            "avg_latency_ms": 0.0,
            "throughput_mbps": 0.0,
        }

    return MeshMetricsResponse(
        mesh_id=mesh_id,
        consciousness=consciousness,
        mape_k=mape_k,
        network=network,
        timestamp=datetime.utcnow().isoformat(),
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
    await _resolve_mesh_for_user(mesh_id, user)

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
    await _resolve_mesh_for_user(mesh_id, user)

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
    await _resolve_mesh_for_user(mesh_id, user)

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
    await _resolve_mesh_for_user(mesh_id, user)

    events = get_mapek_events(mesh_id)
    return events[-limit:]


__all__ = ["router"]
