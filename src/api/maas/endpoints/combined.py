"""
MaaS Combined Router - Assembles all endpoint routers.

Provides a single router that combines all domain-specific routers.
"""


from fastapi import APIRouter

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


def get_combined_router(
    prefix: str = "/api/v1/maas",
    include_auth: bool = True,
    include_mesh: bool = True,
    include_nodes: bool = True,
    include_billing: bool = True,
    include_batman: bool = True,
    include_pilot: bool = True,
    include_playbooks: bool = True,
    include_provisioning: bool = True,
    include_marketplace: bool = True,
    include_governance: bool = True,
    include_analytics: bool = True,
    include_agent_mesh: bool = True,
    include_supply_chain: bool = True,
    include_compat: bool = True,
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
    Create a combined router with all MaaS endpoints.
    """
    router = APIRouter(prefix=prefix)

    if include_auth:
        router.include_router(auth_router)

    if include_mesh:
        router.include_router(mesh_router)

    if include_nodes:
        router.include_router(nodes_router)
        router.include_router(legacy_nodes_router)

    if include_billing:
        router.include_router(billing_router)

    if include_batman:
        router.include_router(batman_router)

    if include_pilot:
        router.include_router(pilot_router)

    if include_playbooks:
        router.include_router(playbooks_router)

    if include_provisioning:
        router.include_router(provisioning_router)

    if include_marketplace:
        router.include_router(marketplace_router)

    if include_governance:
        router.include_router(governance_router)

    if include_analytics:
        router.include_router(analytics_router)

    if include_agent_mesh:
        router.include_router(agent_mesh_router)

    if include_supply_chain:
        router.include_router(supply_chain_router)

    if include_compat:
        router.include_router(compat_router)

    if include_policies:
        router.include_router(policies_router)

    if include_telemetry:
        router.include_router(telemetry_router)

    if include_vpn:
        router.include_router(vpn_router)

    if include_users:
        router.include_router(users_router)

    if include_swarm:
        router.include_router(swarm_router)

    if include_ledger:
        router.include_router(ledger_router)

    if include_swarm_orchestration:
        router.include_router(swarm_orchestration_router)

    if include_vision:
        router.include_router(vision_router)

    if include_service_identity:
        router.include_router(service_identity_status_router)

    return router


# Default combined router
router = get_combined_router()


__all__ = ["get_combined_router", "router"]
