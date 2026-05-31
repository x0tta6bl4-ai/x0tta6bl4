"""
MaaS Combined Router - Assembles all endpoint routers.

Provides a single router that combines all domain-specific routers.
Modular implementation for v4.0 architecture.
"""

from collections.abc import Collection

from fastapi import APIRouter

from .auth import root_router as auth_root_router
from .auth import router as auth_router
from .batman import router as batman_router
from .billing import router as billing_router
from .mesh import router as mesh_router
from .nodes import router as nodes_router
from .nodes_legacy import router as legacy_nodes_router
from .pilot import router as pilot_router
from .playbooks import router as playbooks_router
from .provisioning import router as provisioning_router
from .marketplace import router as marketplace_router
from .governance import router as governance_router
from .analytics import router as analytics_router
from .agent_mesh import router as agent_mesh_router
from .supply_chain import router as supply_chain_router
from .compat import router as compat_router
from .policies import router as policies_router
from .telemetry import router as telemetry_router
from .vpn import router as vpn_router
from .users import router as users_router
from .swarm import router as swarm_router
from .ledger import router as ledger_router
from .swarm_orchestration import router as swarm_orchestration_router
from .vision import router as vision_router
from .service_identity_status import router as service_identity_status_router


def _filtered_router(
    source: APIRouter,
    *,
    include_paths: Collection[str] | None = None,
    exclude_paths: Collection[str] | None = None,
) -> APIRouter:
    """Return a lightweight router copy with selected route paths."""
    include_set = set(include_paths) if include_paths is not None else None
    exclude_set = set(exclude_paths or ())
    if include_set is None and not exclude_set:
        return source

    filtered = APIRouter()
    for route in source.routes:
        path = getattr(route, "path", "")
        if include_set is not None and path not in include_set:
            continue
        if path in exclude_set:
            continue
        filtered.routes.append(route)
    return filtered


def get_combined_router(
    prefix: str = "",
    include_auth: bool = True,
    include_auth_namespace: bool = True,
    include_mesh: bool = True,
    include_mesh_namespace: bool = True,
    mesh_root_excluded_paths: Collection[str] | None = None,
    mesh_namespace_excluded_paths: Collection[str] | None = None,
    include_nodes: bool = True,
    include_legacy_nodes: bool = True,
    legacy_nodes_excluded_paths: Collection[str] | None = ("/register",),
    include_billing: bool = True,
    billing_excluded_paths: Collection[str] | None = None,
    include_batman: bool = True,
    include_pilot: bool = True,
    include_playbooks: bool = True,
    include_provisioning: bool = True,
    include_marketplace: bool = True,
    include_governance: bool = True,
    include_analytics: bool = True,
    include_agent_mesh: bool = True,
    include_supply_chain: bool = True,
    include_compat: bool = False,
    compat_include_paths: Collection[str] | None = None,
    include_policies: bool = True,
    include_telemetry: bool = True,
    include_vpn: bool = True,
    include_users: bool = True,
    include_swarm: bool = True,
    include_ledger: bool = True,
    include_swarm_orchestration: bool = True,
    include_vision: bool = True,
    include_service_identity: bool = True,
) -> APIRouter:
    """
    Create a combined router with all domain endpoints.
    """
    router = APIRouter(prefix=prefix)

    # --- MaaS v1 Group ---
    if include_auth:
        router.include_router(auth_root_router, prefix="/api/v1/maas")
        if include_auth_namespace:
            router.include_router(auth_router, prefix="/api/v1/maas")

    if include_mesh:
        router.include_router(
            _filtered_router(mesh_router, exclude_paths=mesh_root_excluded_paths),
            prefix="/api/v1/maas",
        )
        if include_mesh_namespace:
            router.include_router(
                _filtered_router(
                    mesh_router,
                    exclude_paths=mesh_namespace_excluded_paths,
                ),
                prefix="/api/v1/maas/mesh",
            )

    if include_nodes:
        router.include_router(nodes_router, prefix="/api/v1/maas")
        if include_legacy_nodes:
            router.include_router(
                _filtered_router(
                    legacy_nodes_router,
                    exclude_paths=legacy_nodes_excluded_paths,
                ),
                prefix="/api/v1/maas",
            )

    if include_billing:
        router.include_router(
            _filtered_router(billing_router, exclude_paths=billing_excluded_paths),
            prefix="/api/v1/maas/billing",
        )
        # Legacy billing v1
        try:
            from src.api.billing import router as billing_v1_router
            router.include_router(billing_v1_router) # already has /api/v1/billing
        except ImportError:
            pass

    if include_batman:
        router.include_router(batman_router, prefix="/api/v1/maas/batman")

    if include_pilot:
        router.include_router(pilot_router, prefix="/api/v1/maas/pilot")

    if include_playbooks:
        router.include_router(playbooks_router, prefix="/api/v1/maas/playbooks")

    if include_provisioning:
        router.include_router(provisioning_router, prefix="/api/v1/maas/provisioning")

    if include_marketplace:
        router.include_router(marketplace_router, prefix="/api/v1/maas/marketplace")

    if include_governance:
        router.include_router(governance_router, prefix="/api/v1/maas/governance")

    if include_analytics:
        router.include_router(analytics_router, prefix="/api/v1/maas/analytics")

    if include_agent_mesh:
        router.include_router(agent_mesh_router, prefix="/api/v1/maas/agents")

    if include_supply_chain:
        router.include_router(supply_chain_router, prefix="/api/v1/maas/supply-chain")

    if include_compat:
        router.include_router(
            _filtered_router(compat_router, include_paths=compat_include_paths)
        )

    if include_policies:
        router.include_router(policies_router, prefix="/api/v1/maas/policies")

    if include_telemetry:
        router.include_router(telemetry_router, prefix="/api/v1/maas/telemetry")

    # --- Specialized Groups ---
    if include_vpn:
        router.include_router(vpn_router, prefix="/vpn")
        router.include_router(vpn_router, prefix="/api/v1/vpn")

    if include_users:
        router.include_router(users_router, prefix="/api/v1/users")

    if include_swarm:
        router.include_router(swarm_router, prefix="/api/v3/swarm")

    if include_ledger:
        router.include_router(ledger_router, prefix="/api/v1/ledger")

    if include_swarm_orchestration:
        router.include_router(swarm_orchestration_router, prefix="/api/v1/swarm")

    if include_vision:
        router.include_router(vision_router, prefix="/api/v1/vision")

    if include_service_identity:
        router.include_router(service_identity_status_router, prefix="/api/v1/service-identity")

    return router


# Default combined router
router = get_combined_router()

__all__ = ["get_combined_router", "router"]
