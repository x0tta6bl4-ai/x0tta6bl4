"""
MaaS Node Healing - trigger MAPE-K loop for specific nodes.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

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

_MESH_HEALING_SOURCE_AGENT = "mesh-network-manager"


def _mesh_manager_event_ids(event_bus: Any) -> List[str]:
    if event_bus is None or not hasattr(event_bus, "get_event_history"):
        return []
    try:
        events = event_bus.get_event_history(
            source_agent=_MESH_HEALING_SOURCE_AGENT,
            limit=100,
        )
        return [str(e.event_id) for e in events]
    except Exception:
        return []


def _mesh_manager_new_events(event_bus: Any, event_ids: Sequence[str]) -> List[Any]:
    if event_bus is None or not hasattr(event_bus, "get_event_history"):
        return []

    wanted = {str(event_id) for event_id in event_ids}
    if not wanted:
        return []

    events: List[Any] = []
    for event_type in (
        EventType.PIPELINE_STAGE_END,
        EventType.TASK_FAILED,
        EventType.TASK_BLOCKED,
    ):
        try:
            history = event_bus.get_event_history(
                event_type=event_type,
                source_agent=_MESH_HEALING_SOURCE_AGENT,
                limit=1000,
            )
        except Exception:
            continue
        for event in history:
            if str(getattr(event, "event_id", "")) in wanted:
                events.append(event)

    events.sort(key=lambda item: getattr(item, "timestamp", ""))
    return events


def _safe_evidence(value: Any) -> Dict[str, Any]:
    evidence = value if isinstance(value, dict) else {}
    event_ids = [
        str(event_id)
        for event_id in evidence.get("event_ids", [])
        if str(event_id).strip()
    ][:20]
    source_agents = [
        str(agent)
        for agent in evidence.get("source_agents", [])
        if str(agent).strip()
    ][:10]
    try:
        events_total = int(evidence.get("events_total") or len(event_ids))
    except (TypeError, ValueError):
        events_total = len(event_ids)
    try:
        event_ids_count = int(evidence.get("event_ids_count") or len(event_ids))
    except (TypeError, ValueError):
        event_ids_count = len(event_ids)

    return {
        "source_agents": source_agents,
        "event_ids": event_ids,
        "events_total": events_total,
        "event_ids_count": event_ids_count,
        "redacted": evidence.get("redacted") is True,
    }


def _safe_claim_gate(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None

    blockers = [
        str(blocker)
        for blocker in value.get("blockers", [])
        if str(blocker).strip()
    ][:10]
    return {
        "schema": str(value.get("schema") or ""),
        "decision": str(value.get("decision") or ""),
        "post_action_probe_enabled": bool(value.get("post_action_probe_enabled")),
        "post_action_probe_target_present": bool(
            value.get("post_action_probe_target_present")
        ),
        "post_action_probe_attempted": bool(value.get("post_action_probe_attempted")),
        "post_action_dataplane_revalidated": bool(
            value.get("post_action_dataplane_revalidated")
        ),
        "dataplane_confirmed": bool(value.get("dataplane_confirmed")),
        "restored_dataplane_claim_allowed": bool(
            value.get("restored_dataplane_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": bool(
            value.get("traffic_delivery_claim_allowed")
        ),
        "customer_traffic_claim_allowed": bool(
            value.get("customer_traffic_claim_allowed")
        ),
        "external_reachability_claim_allowed": bool(
            value.get("external_reachability_claim_allowed")
        ),
        "production_slo_claim_allowed": bool(value.get("production_slo_claim_allowed")),
        "production_readiness_claim_allowed": bool(
            value.get("production_readiness_claim_allowed")
        ),
        "requires_post_action_dataplane_revalidation": bool(
            value.get("requires_post_action_dataplane_revalidation")
        ),
        "blockers": blockers,
        "evidence": _safe_evidence(value.get("evidence")),
        "claim_boundary": str(value.get("claim_boundary") or ""),
        "redacted": True,
    }


def _latest_post_action_dataplane_revalidation(
    events: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    for event in reversed(list(events)):
        data = getattr(event, "data", None)
        if not isinstance(data, dict):
            continue

        raw_revalidation = data.get("post_action_dataplane_revalidation")
        if not isinstance(raw_revalidation, dict):
            continue

        claim_gate = _safe_claim_gate(raw_revalidation.get("claim_gate"))
        if claim_gate is None:
            claim_gate = _safe_claim_gate(data.get("claim_gate"))

        probe_attempted = bool(raw_revalidation.get("probe_attempted"))
        dataplane_confirmed = bool(raw_revalidation.get("dataplane_confirmed"))
        post_action_revalidated = bool(
            raw_revalidation.get("post_action_dataplane_revalidated")
        )
        restored_allowed = bool(
            claim_gate and claim_gate.get("restored_dataplane_claim_allowed")
        )
        post_action_revalidated = bool(
            post_action_revalidated and restored_allowed
        )
        if dataplane_confirmed and post_action_revalidated and restored_allowed:
            status_value = "success"
            reason = "bounded_dataplane_probe_succeeded"
        elif probe_attempted:
            status_value = "failed"
            reason = "bounded_dataplane_probe_failed"
        else:
            status_value = "pending_revalidation"
            reason = "bounded_dataplane_probe_not_attempted"

        return {
            "schema": "x0tta6bl4.maas_node_heal.post_action_dataplane_revalidation.v1",
            "status": status_value,
            "reason": reason,
            "probe_enabled": bool(raw_revalidation.get("probe_enabled")),
            "probe_target_present": bool(raw_revalidation.get("probe_target_present")),
            "probe_attempted": probe_attempted,
            "dataplane_confirmed": dataplane_confirmed,
            "post_action_dataplane_revalidated": post_action_revalidated,
            "restored_dataplane_claim_allowed": restored_allowed,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_reachability_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "claim_gate": claim_gate,
            "evidence": _safe_evidence(raw_revalidation.get("evidence")),
            "claim_boundary": str(raw_revalidation.get("claim_boundary") or ""),
            "payloads_redacted": True,
        }
    return None


def _mesh_healing_control_plane_evidence(
    event_bus: Any,
    evidence_before: List[str],
) -> Dict[str, Any]:
    if event_bus is None:
        return {"source_agents": [], "event_ids": [], "payloads_redacted": True}
    
    current_ids = _mesh_manager_event_ids(event_bus)
    new_ids = [eid for eide in current_ids if (eid := eide) not in set(evidence_before)]
    new_events = _mesh_manager_new_events(event_bus, new_ids)
    operations = sorted(
        {
            str(event.data.get("operation"))
            for event in new_events
            if isinstance(getattr(event, "data", None), dict)
            and event.data.get("operation")
        }
    )
    statuses = sorted(
        {
            str(event.data.get("status"))
            for event in new_events
            if isinstance(getattr(event, "data", None), dict)
            and event.data.get("status") is not None
        }
    )
    post_action = _latest_post_action_dataplane_revalidation(new_events)
    
    return {
        "source_agents": [_MESH_HEALING_SOURCE_AGENT] if new_ids else [],
        "event_ids": new_ids,
        "events_total": len(new_ids),
        "operations": operations,
        "statuses": statuses,
        "dataplane_confirmed": bool(
            post_action and post_action.get("dataplane_confirmed")
        ),
        "post_action_dataplane_revalidated": bool(
            post_action and post_action.get("post_action_dataplane_revalidated")
        ),
        "payloads_redacted": True,
    }


def _mesh_healing_post_action_revalidation(
    healed: int,
    control_plane_evidence: Dict[str, Any],
    event_bus: Any = None,
) -> Dict[str, Any]:
    events = _mesh_manager_new_events(
        event_bus=event_bus,
        event_ids=control_plane_evidence.get("event_ids", []),
    )
    bounded_revalidation = _latest_post_action_dataplane_revalidation(events)
    if bounded_revalidation is not None:
        return {
            **bounded_revalidation,
            "control_plane_evidence": control_plane_evidence,
            "dataplane_probe_required": healed > 0,
        }

    return {
        "status": "pending_revalidation" if healed > 0 else "not_required",
        "reason": (
            "no_bounded_post_action_dataplane_probe_attached"
            if healed > 0
            else "no_healing_action_applied"
        ),
        "control_plane_evidence": control_plane_evidence,
        "dataplane_probe_required": healed > 0,
        "probe_attempted": False,
        "dataplane_confirmed": False,
        "post_action_dataplane_revalidated": False,
        "restored_dataplane_claim_allowed": False,
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
        state = getattr(request, "state", None) if request else None
        event_bus = getattr(state, "event_bus", None) if state else None
        project_root = getattr(state, "event_project_root", ".") if state else "."
        if event_bus is None:
            try:
                event_bus = get_event_bus(project_root)
            except Exception as exc:
                logger.warning("Failed to initialize healing EventBus: %s", exc)
                event_bus = None
        
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
            post_action_dataplane_probe_target=getattr(node, "ip_address", None),
        )
        
        control_plane_evidence = _mesh_healing_control_plane_evidence(event_bus, evidence_before)
        post_action_dataplane_revalidation = _mesh_healing_post_action_revalidation(
            healed=healed,
            control_plane_evidence=control_plane_evidence,
            event_bus=event_bus,
        )
        dataplane_confirmed = bool(
            post_action_dataplane_revalidation.get("dataplane_confirmed")
        )
        
        return {
            "status": "healed" if healed > 0 else "no_action",
            "node_id": node_id,
            "components_healed": healed,
            "healing_claim": "local_control_action_applied" if healed > 0 else "local_control_no_action",
            "dataplane_confirmed": dataplane_confirmed,
            "post_action_dataplane_revalidated": bool(
                post_action_dataplane_revalidation.get(
                    "post_action_dataplane_revalidated"
                )
            ),
            "restored_dataplane_claim_allowed": bool(
                post_action_dataplane_revalidation.get(
                    "restored_dataplane_claim_allowed"
                )
            ),
            "post_action_dataplane_revalidation": post_action_dataplane_revalidation,
            "claim_boundary": _MESH_HEALING_RESPONSE_CLAIM_BOUNDARY,
            "control_plane_evidence": control_plane_evidence,
        }
    except Exception as e:
        logger.error(f"Healing failed for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Healing failed: {str(e)}")
