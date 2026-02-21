"""
MaaS Combined Router - Assembles all endpoint routers.

Provides a single router that combines all domain-specific routers.
"""

from typing import Optional

from fastapi import APIRouter

from .auth import router as auth_router
from .billing import router as billing_router
from .mesh import router as mesh_router
from .nodes import router as nodes_router


def get_combined_router(
    prefix: str = "/api/v1/maas",
    include_auth: bool = True,
    include_mesh: bool = True,
    include_nodes: bool = True,
    include_billing: bool = True,
) -> APIRouter:
    """
    Create a combined router with all MaaS endpoints.

    Args:
        prefix: URL prefix for all routes
        include_auth: Include authentication endpoints
        include_mesh: Include mesh management endpoints
        include_nodes: Include node management endpoints
        include_billing: Include billing endpoints

    Returns:
        Combined APIRouter
    """
    router = APIRouter(prefix=prefix)

    if include_auth:
        router.include_router(auth_router)

    if include_mesh:
        router.include_router(mesh_router)

    if include_nodes:
        router.include_router(nodes_router)

    if include_billing:
        router.include_router(billing_router)

    return router


# Default combined router
router = get_combined_router()


__all__ = ["get_combined_router", "router"]
