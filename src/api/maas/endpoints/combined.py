"""MaaS Combined Router - assembles all endpoint routers."""

from collections.abc import Iterable

from fastapi import APIRouter

from .auth import router as auth_router, root_router as auth_root_router
from .batman import router as batman_router
from .billing import router as billing_router
from .mesh import router as mesh_router
from .nodes import router as nodes_router
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
from .telemetry import router as telemetry_router, root_router as telemetry_root_router
from .vpn import router as vpn_router
from .users import router as users_router
from .swarm import router as swarm_router
from .ledger import router as ledger_router
from .swarm_orchestration import router as swarm_orchestration_router
from .vision import router as vision_router
from .service_identity_status import router as service_identity_status_router


_DEFAULT_MAAS_PREFIX = "/api/v1/maas"


def _join_prefix(base: str, suffix: str = "") -> str:
    clean_base = "/" + str(base or "").strip("/")
    clean_suffix = str(suffix or "").strip("/")
    return clean_base if not clean_suffix else f"{clean_base}/{clean_suffix}"


def _filtered_router(
    source: APIRouter,
    *,
    included_paths: Iterable[str] | None = None,
    excluded_paths: Iterable[str] | None = None,
) -> APIRouter:
    included = None if included_paths is None else {str(path) for path in included_paths}
    excluded = {str(path) for path in (excluded_paths or set())}
    if included is None and not excluded:
        return source
    filtered = APIRouter()
    for route in source.routes:
        path = getattr(route, "path", "")
        if included is not None and path not in included:
            continue
        if path not in excluded:
            filtered.routes.append(route)
    return filtered


def get_combined_router(
    *,
    prefix: str = _DEFAULT_MAAS_PREFIX,
    include_auth: bool = True,
    include_auth_namespace: bool = True,
    include_mesh: bool = True,
    include_mesh_namespace: bool = True,
    include_nodes: bool = True,
    include_nodes_namespace: bool = True,
    include_billing: bool = True,
    include_batman: bool = True,
    include_pilot: bool = True,
    include_compat: bool = True,
    mesh_root_excluded_paths: Iterable[str] | None = None,
    billing_excluded_paths: Iterable[str] | None = None,
) -> APIRouter:
    """Create a combined router with configurable MaaS domain slices."""
    router = APIRouter()
    maas_prefix = _join_prefix(prefix)
    use_default_prefix = maas_prefix == _DEFAULT_MAAS_PREFIX

    # --- MaaS v1 Group ---

    # Nodes (moved up to avoid shadowing by mesh parameters)
    if include_nodes:
        router.include_router(nodes_router, prefix=maas_prefix)
        if include_nodes_namespace:
            router.include_router(nodes_router, prefix=_join_prefix(maas_prefix, "nodes"))

    # Auth
    if include_auth:
        router.include_router(auth_root_router, prefix=maas_prefix)
        if include_auth_namespace:
            router.include_router(auth_router, prefix=maas_prefix)

    # Telemetry root aliases, such as /api/v1/maas/heartbeat and
    # /api/v1/maas/{mesh_id}/topology, are kept outside /telemetry for legacy clients.
    router.include_router(telemetry_root_router, prefix=maas_prefix)

    # Mesh
    if include_mesh:
        router.include_router(
            _filtered_router(
                mesh_router,
                excluded_paths=mesh_root_excluded_paths,
            ),
            prefix=maas_prefix,
        )
        if include_mesh_namespace:
            router.include_router(mesh_router, prefix=_join_prefix(maas_prefix, "mesh"))

    # Billing
    if include_billing:
        router.include_router(
            _filtered_router(
                billing_router,
                excluded_paths=billing_excluded_paths,
            ),
            prefix=_join_prefix(maas_prefix, "billing"),
        )

    # Rest
    if include_batman:
        router.include_router(batman_router, prefix=_join_prefix(maas_prefix, "batman"))
    if include_pilot:
        router.include_router(pilot_router, prefix=_join_prefix(maas_prefix, "pilot"))
    router.include_router(playbooks_router, prefix=_join_prefix(maas_prefix, "playbooks"))
    router.include_router(
        provisioning_router,
        prefix=_join_prefix(maas_prefix, "provisioning"),
    )
    router.include_router(
        marketplace_router,
        prefix=_join_prefix(maas_prefix, "marketplace"),
    )
    router.include_router(governance_router, prefix=_join_prefix(maas_prefix, "governance"))
    router.include_router(analytics_router, prefix=_join_prefix(maas_prefix, "analytics"))
    router.include_router(agent_mesh_router, prefix=_join_prefix(maas_prefix, "agents"))
    router.include_router(
        supply_chain_router,
        prefix=_join_prefix(maas_prefix, "supply-chain"),
    )
    router.include_router(policies_router, prefix=_join_prefix(maas_prefix, "policies"))
    router.include_router(telemetry_router, prefix=_join_prefix(maas_prefix, "telemetry"))
    if include_compat:
        compat_aliases = {"/api/v1/maas/compat/readiness"}
        if include_auth:
            compat_aliases.add("/api/v3/maas/auth/register")
        if include_billing:
            compat_aliases.add("/api/v1/maas/billing/pay")
        compat_alias_router = _filtered_router(
            compat_router,
            included_paths=compat_aliases,
        )
        if use_default_prefix:
            router.include_router(compat_alias_router)
        else:
            router.include_router(compat_alias_router, prefix=maas_prefix)

    # --- Specialized Groups ---
    if use_default_prefix:
        router.include_router(vpn_router, prefix="/api/v1/vpn")
        router.include_router(users_router, prefix="/api/v1/users")
        router.include_router(swarm_router, prefix="/api/v3/swarm")
        router.include_router(ledger_router, prefix="/api/v1/ledger")
        router.include_router(swarm_orchestration_router, prefix="/api/v1/swarm")
        router.include_router(vision_router, prefix="/api/v1/vision")
        router.include_router(
            service_identity_status_router,
            prefix="/api/v1/service-identity",
        )
    else:
        router.include_router(vpn_router, prefix=_join_prefix(maas_prefix, "vpn"))
        router.include_router(users_router, prefix=_join_prefix(maas_prefix, "users"))
        router.include_router(swarm_router, prefix=_join_prefix(maas_prefix, "swarm-v3"))
        router.include_router(ledger_router, prefix=_join_prefix(maas_prefix, "ledger"))
        router.include_router(
            swarm_orchestration_router,
            prefix=_join_prefix(maas_prefix, "swarm"),
        )
        router.include_router(vision_router, prefix=_join_prefix(maas_prefix, "vision"))
        router.include_router(
            service_identity_status_router,
            prefix=_join_prefix(maas_prefix, "service-identity"),
        )

    return router


# Default combined router
router = get_combined_router()

__all__ = ["get_combined_router", "router"]
