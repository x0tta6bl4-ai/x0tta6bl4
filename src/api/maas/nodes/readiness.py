"""
MaaS Node Readiness - check local dependency status for node management.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Request
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.core.resilience.reliability_policy import mark_degraded_dependency

logger = logging.getLogger(__name__)


def _node_readiness_status(db: Session) -> Dict[str, Any]:
    """Internal helper to calculate readiness without Request object."""
    from src.database import MeshNode, MeshInstance, ACLPolicy, MarketplaceListing, MarketplaceEscrow
    from src.api.maas_auth import require_role, require_mesh_access
    from src.api.maas_security import token_signer
    from src.utils.audit import record_audit_log
    from .healing import MESH_HEALING_AVAILABLE
    from .heartbeat import _set_external_telemetry

    try:
        db.execute("SELECT 1")
        node_db_ready = True
    except Exception:
        node_db_ready = False

    node_model_ready = all(
        hasattr(m, "__table__")
        for m in [MeshNode, MeshInstance, ACLPolicy, MarketplaceListing, MarketplaceEscrow]
    )
    node_rbac_ready = callable(require_role) and callable(require_mesh_access)
    token_signer_ready = callable(getattr(token_signer, "sign_token", None))
    audit_log_ready = callable(record_audit_log)
    telemetry_bridge_ready = _set_external_telemetry is not None
    healing_service_ready = MESH_HEALING_AVAILABLE
    
    node_runtime_ready = (
        node_db_ready
        and node_model_ready
        and node_rbac_ready
        and token_signer_ready
        and audit_log_ready
    )

    degraded_dependencies = []
    if not node_db_ready:
        degraded_dependencies.append("database")
    if not node_model_ready:
        degraded_dependencies.append("node_models")
    if not node_rbac_ready:
        degraded_dependencies.append("rbac")
    if not token_signer_ready:
        degraded_dependencies.append("token_signing")
    if not audit_log_ready:
        degraded_dependencies.append("audit_log")
    if not telemetry_bridge_ready:
        degraded_dependencies.append("telemetry_bridge")
    if not healing_service_ready:
        degraded_dependencies.append("healing_service")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "node_runtime_ready": node_runtime_ready,
        "node_db_ready": node_db_ready,
        "node_model_ready": node_model_ready,
        "node_rbac_ready": node_rbac_ready,
        "token_signer_ready": token_signer_ready,
        "audit_log_ready": audit_log_ready,
        "telemetry_bridge_ready": telemetry_bridge_ready,
        "healing_service_ready": healing_service_ready,
        "degraded_dependencies": degraded_dependencies,
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_node_readiness"
        ),
    }


async def node_readiness(
    request: Request,
    db: Session,
) -> Dict[str, Any]:
    """Return local dependency readiness for modular MaaS node management."""
    payload = _node_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload

