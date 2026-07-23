"""MaaS Combined Router - assembles endpoint routers.

`MAAS_LIGHT_MODE=true` is used by local runtime verifiers. In that mode this
module must avoid importing heavyweight optional surfaces (for example swarm
orchestration, which imports torch) before the temporary API can answer
`/health`. The verifier exercises auth/mesh/nodes/telemetry only, so optional
routers are imported lazily only for the full application mode.
"""
from __future__ import annotations

import os

from fastapi import APIRouter

from .auth import router as auth_router, root_router as auth_root_router
from .mesh import router as mesh_router
from .nodes import router as nodes_router
from .telemetry import router as telemetry_router, root_router as telemetry_root_router
from .compat import router as compat_router

_LIGHT_MODE = os.getenv("MAAS_LIGHT_MODE", "false").lower() == "true"


def get_combined_router(
    *,
    prefix: str = "/api/v1/maas",
    include_auth: bool = True,
    include_mesh: bool = True,
    include_nodes: bool = True,
    include_telemetry: bool = True,
    include_billing: bool = True,
    include_batman: bool = True,
    include_pilot: bool = True,
    include_compat: bool = True,
) -> APIRouter:
    """Create a combined router with all MaaS endpoints."""
    router = APIRouter()
    p = prefix.rstrip("/") or "/api/v1/maas"
    custom_selection = not (
        include_auth
        and include_mesh
        and include_nodes
        and include_telemetry
        and include_billing
        and include_batman
        and include_pilot
    )
    include_auxiliary = p == "/api/v1/maas" and not custom_selection

    # 1. Fixed-path root-level routes (Highest Priority)
    # Auth root (register, login)
    if include_auth:
        router.include_router(auth_root_router, prefix=p)
    # Telemetry root (heartbeat)
    if include_telemetry:
        router.include_router(telemetry_root_router, prefix=p)

    # 2. Namespaced Routers (High Priority)
    if include_auth:
        router.include_router(auth_router, prefix=f"{p}/auth")
    if include_nodes:
        router.include_router(nodes_router, prefix=f"{p}/nodes")
    if include_mesh:
        router.include_router(mesh_router, prefix=f"{p}/mesh")
    if include_telemetry:
        router.include_router(telemetry_router, prefix=f"{p}/telemetry")

    if not _LIGHT_MODE:
        if include_batman:
            from .batman import router as batman_router
        if include_billing:
            from .billing import router as billing_router
        if include_pilot:
            from .pilot import router as pilot_router
        if include_auxiliary:
            from .playbooks import router as playbooks_router
            from .provisioning import router as provisioning_router
            from .marketplace import router as marketplace_router
            from .governance import router as governance_router
            from .analytics import router as analytics_router
            from .agent_mesh import router as agent_mesh_router
            from .supply_chain import router as supply_chain_router
            from .policies import router as policies_router
            from .vpn import router as vpn_router
            from .users import router as users_router
            from .swarm import router as swarm_router
            from .ledger import router as ledger_router
            from .swarm_orchestration import router as swarm_orchestration_router
            from .vision import router as vision_router
            from .service_identity_status import router as service_identity_status_router
            from .peaq_relay import router as peaq_relay_router

        if include_billing:
            router.include_router(billing_router, prefix=f"{p}/billing")
        if include_auxiliary:
            router.include_router(marketplace_router, prefix=f"{p}/marketplace")
            router.include_router(analytics_router, prefix=f"{p}/analytics")

        # Other namespaced ones
        if include_batman:
            router.include_router(batman_router, prefix=f"{p}/batman")
        if include_pilot:
            router.include_router(pilot_router, prefix=f"{p}/pilot")
        if include_auxiliary:
            router.include_router(playbooks_router, prefix=f"{p}/playbooks")
            router.include_router(provisioning_router, prefix=f"{p}/provisioning")
            router.include_router(governance_router, prefix=f"{p}/governance")
            router.include_router(agent_mesh_router, prefix=f"{p}/agents")
            router.include_router(supply_chain_router)
            router.include_router(policies_router, prefix=f"{p}/policies")

    # 3. Parameterized Root Routers (included AFTER fixed paths to avoid shadowing)
    # These match /{mesh_id}/...
    if include_nodes:
        router.include_router(nodes_router, prefix=p)
    if include_mesh:
        router.include_router(mesh_router, prefix=p)

    # 4. Compat Router (Absolute paths, lowest priority)
    if include_compat and include_auxiliary:
        router.include_router(compat_router)

    if not _LIGHT_MODE and include_auxiliary:
        # 5. Specialized Non-MaaS-V1
        router.include_router(vpn_router, prefix="/api/v1/vpn")
        router.include_router(users_router, prefix="/api/v1/users")
        router.include_router(swarm_router, prefix="/api/v3/swarm")
        router.include_router(ledger_router, prefix="/api/v1/ledger")
        router.include_router(swarm_orchestration_router, prefix="/api/v1/swarm")
        router.include_router(vision_router, prefix="/api/v1/vision")
        router.include_router(service_identity_status_router, prefix="/api/v1/service-identity")
        router.include_router(peaq_relay_router, prefix="/api/v1/peaq/relay")

    return router


# Default combined router
router = get_combined_router()

__all__ = ["get_combined_router", "router"]

