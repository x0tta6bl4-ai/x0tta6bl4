"""
MaaS API Endpoints Package.

Contains FastAPI routers for different API domains:
- mesh: Mesh lifecycle management
- nodes: Node registration and management
- billing: Billing and invoicing
- auth: Authentication endpoints
"""

from typing import Any

# Lazy loading for routers
__all__ = [
    "mesh_router",
    "nodes_router",
    "billing_router",
    "auth_router",
    "get_combined_router",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for routers."""
    if name == "mesh_router":
        from .mesh import router as mesh_router
        return mesh_router
    if name == "nodes_router":
        from .nodes import router as nodes_router
        return nodes_router
    if name == "billing_router":
        from .billing import router as billing_router
        return billing_router
    if name == "auth_router":
        from .auth import router as auth_router
        return auth_router
    if name == "get_combined_router":
        from . import combined
        return combined.get_combined_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
