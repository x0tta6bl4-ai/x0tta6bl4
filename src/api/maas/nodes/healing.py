"""
MaaS Node Healing - trigger MAPE-K loop for specific nodes.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status

from src.coordination.events import EventType, get_event_bus
from src.database import MeshNode
from .security import ensure_mesh_visibility_with_permission
from src.core.rbac import MeshPermission

logger = logging.getLogger(__name__)

_MESH_HEALING_RESPONSE_CLAIM_BOUNDARY = (
    "MaaS node heal response means a local mesh-network-manager healing action "
    "was requested and summarized through redacted EventBus evidence. The "
    "status field is kept for API compatibility, but it must not be read as "
    "restored live dataplane behavior unless post_action_dataplane_revalidation "
    "later cites bounded dataplane probe evidence."
)

try:
    from src.mesh.network_manager import MeshNetworkManager, VerificationMode
    MESH_HEALING_AVAILABLE = True
except ImportError:
    MESH_HEALING_AVAILABLE = False


def _mesh_manager_event_ids(event_bus: Any) -> List[str]:
    if event_bus is None or not hasattr(event_bus, "get_event_history"):
        return []
    try:
        events = event_bus.get_event_history(
            source_agent="mesh-network-manager",
            limit=100,
        )
        return [str(e.event_id) for e in events]
    except Exception:
        return []


def _mesh_healing_control_plane_evidence(
    event_bus: Any,
    evidence_before: List[str],
) -> Dict[str, Any]:
    if event_bus is None:
        return {"source_agents": [], "event_ids": [], "payloads_redacted": True}
    
    current_ids = _mesh_manager_event_ids(event_bus)
    new_ids = [eid for eide in current_ids if (eid := eide) not in set(evidence_before)]
    
    return {
        "source_agents": ["mesh-network-manager"] if new_ids else [],
        "event_ids": new_ids,
        "events_total": len(new_ids),
        "payloads_redacted": True,
    }


def _mesh_healing_post_action_revalidation(
    healed: int,
    control_plane_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": "pending_revalidation" if healed > 0 else "not_required",
        "control_plane_evidence": control_plane_evidence,
        "dataplane_probe_required": healed > 0,
        "payloads_redacted": True,
    }


async def trigger_node_healing(
    mesh_id: str,
    node_id: str,
    db: Any,
    current_user: Any,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """Trigger the MAPE-K healing loop for a node."""
    ensure_mesh_visibility_with_permission(
        mesh_id, current_user, db, MeshPermission.NODE_HEAL
    )
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if not MESH_HEALING_AVAILABLE:
        logger.warning(f"Healing requested for node {node_id} but healing service unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Healing service unavailable.",
        )
    
    try:
        from src.coordination.events import get_event_bus
        state = getattr(request, "state", None) if request else None
        event_bus = getattr(state, "event_bus", None) if state else None
        project_root = getattr(state, "event_project_root", ".") if state else "."
        
        manager_kwargs = {"node_id": node_id}
        if event_bus:
            manager_kwargs["event_bus"] = event_bus
        if project_root:
            manager_kwargs["event_project_root"] = project_root
            
        evidence_before = _mesh_manager_event_ids(event_bus)

        manager = MeshNetworkManager(**manager_kwargs)
        healed = await manager.trigger_aggressive_healing(
            auto_restore_nodes=True,
            verification_mode=VerificationMode.FULL,
        )
        
        control_plane_evidence = _mesh_healing_control_plane_evidence(event_bus, evidence_before)
        post_action_dataplane_revalidation = _mesh_healing_post_action_revalidation(
            healed=healed, control_plane_evidence=control_plane_evidence
        )
        
        return {
            "status": "healed" if healed > 0 else "no_action",
            "node_id": node_id,
            "components_healed": healed,
            "healing_claim": "local_control_action_applied" if healed > 0 else "local_control_no_action",
            "dataplane_confirmed": False,
            "post_action_dataplane_revalidation": post_action_dataplane_revalidation,
            "claim_boundary": _MESH_HEALING_RESPONSE_CLAIM_BOUNDARY,
            "control_plane_evidence": control_plane_evidence,
        }
    except Exception as e:
        logger.error(f"Healing failed for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Healing failed: {str(e)}")
