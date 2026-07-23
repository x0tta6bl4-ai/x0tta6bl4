"""Event trace helpers bound to registered service and API source agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.coordination.events import Event, EventBus, EventType
from src.services.service_identity_registry import KNOWN_EVENT_TRACE_SERVICES


EVENT_TRACE_CLAIM_BOUNDARY = (
    "Trace filters only bind EventBus source_agent values to registered service "
    "names and layers. They do not authenticate events, expose identity values, "
    "or prove live SPIRE/chain state."
)

REDACTED_EVENT_TRACE_FIELDS = frozenset(
    {
        "api_key",
        "api_token",
        "access_token",
        "refresh_token",
        "bot_token",
        "did",
        "password",
        "private_key",
        "raw_vpn_uri",
        "secret",
        "subscription_link",
        "token",
        "uuid",
        "vpn_uri",
        "wallet_address",
        "spiffe_id",
    }
)
REDACTED_IDENTITY_VALUE = "[redacted]"


def _matching_registrations(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> List[Dict[str, str]]:
    return [
        dict(registration)
        for registration in KNOWN_EVENT_TRACE_SERVICES
        if (service_name is None or registration["service_name"] == service_name)
        and (layer is None or registration["layer"] == layer)
    ]


def _registration_source_agent(registration: Dict[str, str]) -> str:
    return registration.get("source_agent") or registration["service_name"]


def service_event_trace_filter(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, object]:
    """Return a redacted EventBus trace filter for registered services."""
    services = _matching_registrations(service_name=service_name, layer=layer)
    known_service_names = {
        registration["service_name"]
        for registration in KNOWN_EVENT_TRACE_SERVICES
    }
    known_layers = {
        registration["layer"]
        for registration in KNOWN_EVENT_TRACE_SERVICES
    }

    unknown_service = (
        service_name is not None and service_name not in known_service_names
    )
    unknown_layer = layer is not None and layer not in known_layers
    status = "ok"
    if unknown_service or unknown_layer:
        status = "unknown_filter"
    elif (service_name is not None or layer is not None) and not services:
        status = "no_match"

    return {
        "status": status,
        "claim_boundary": EVENT_TRACE_CLAIM_BOUNDARY,
        "redacted": True,
        "service_name": service_name,
        "layer": layer,
        "source_agents": sorted(
            _registration_source_agent(service) for service in services
        ),
        "services_total": len(services),
        "registered_services_total": len(KNOWN_EVENT_TRACE_SERVICES),
        "known_layers": sorted(known_layers),
        "services": services,
    }


def _source_agents_for_filter(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> Optional[Set[str]]:
    if service_name is None and layer is None:
        return None
    trace_filter = service_event_trace_filter(
        service_name=service_name,
        layer=layer,
    )
    return set(trace_filter["source_agents"])


def get_service_event_history(
    bus: EventBus,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> List[Event]:
    """Read EventBus history through registered service/layer filters."""
    source_agents = _source_agents_for_filter(service_name=service_name, layer=layer)
    if source_agents == set():
        return []
    return bus.get_event_history(
        event_type=event_type,
        since=since,
        limit=limit,
        source_agents=source_agents,
    )


def get_service_event_replay(
    bus: EventBus,
    agent_id: str,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    since: Optional[datetime] = None,
) -> List[Event]:
    """Replay events through registered service/layer filters."""
    source_agents = _source_agents_for_filter(service_name=service_name, layer=layer)
    if source_agents == set():
        return []
    return bus.replay_events(agent_id, since=since, source_agents=source_agents)


def _redact_identity_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in REDACTED_EVENT_TRACE_FIELDS and child is not None:
                redacted[key_text] = REDACTED_IDENTITY_VALUE
            else:
                redacted[key_text] = _redact_identity_values(child)
        return redacted

    if isinstance(value, list):
        return [_redact_identity_values(item) for item in value]

    if isinstance(value, tuple):
        return [_redact_identity_values(item) for item in value]

    return value


def serialize_service_event_trace(event: Event) -> Dict[str, object]:
    """Serialize an EventBus event without exposing identity values."""
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "source_agent": event.source_agent,
        "timestamp": event.timestamp.isoformat(),
        "target_agents": sorted(event.target_agents) if event.target_agents else None,
        "priority": event.priority,
        "requires_ack": event.requires_ack,
        "acked_by": sorted(event.acked_by),
        "data": _redact_identity_values(event.data),
        "evidence_summary": event_trace_evidence_summary(event.data),
        "redacted": True,
    }


def service_event_trace_history(
    bus: EventBus,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    replay_agent: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> Dict[str, object]:
    """Return redacted EventBus traces through registered service/layer filters."""
    trace_filter = service_event_trace_filter(
        service_name=service_name,
        layer=layer,
    )
    bounded_limit = max(1, min(limit, 1000))

    if trace_filter["status"] == "unknown_filter":
        events: List[Event] = []
    elif replay_agent:
        events = get_service_event_replay(
            bus,
            replay_agent,
            service_name=service_name,
            layer=layer,
            since=since,
        )
        if event_type:
            events = [event for event in events if event.event_type == event_type]
        events = events[-bounded_limit:]
    else:
        events = get_service_event_history(
            bus,
            service_name=service_name,
            layer=layer,
            event_type=event_type,
            since=since,
            limit=bounded_limit,
        )

    return {
        "status": trace_filter["status"],
        "claim_boundary": EVENT_TRACE_CLAIM_BOUNDARY,
        "redacted": True,
        "filter": trace_filter,
        "replay_agent": replay_agent,
        "event_type": event_type.value if event_type else None,
        "limit": bounded_limit,
        "events_total": len(events),
        "events": [serialize_service_event_trace(event) for event in events],
    }


def event_trace_evidence_summary(payload: Any) -> Dict[str, Any]:
    """Analyze an event payload and generate a standardized evidence summary."""
    if not isinstance(payload, dict):
        return {
            "available": False,
            "settlement_evidence": {
                "present": False,
                "provider": None,
                "settlement_action": None,
                "dataplane_confirmed": False,
                "live_provider_settlement_confirmed": False,
                "bank_settlement_confirmed": False,
                "chain_finality_confirmed": False,
                "db_write_evidence": {"attempted": False, "committed": False},
                "output_summary": {},
            },
            "runtime_evidence": {
                "present": False,
                "evidence_blocks_present": [],
            },
            "cross_plane_evidence_profile": {
                "dataplane_confirmed": False,
                "dataplane_claim_gate_required": False,
                "dataplane_claim_gate_allowed": False,
                "production_ready_candidate": False,
                "claim_boundary_present": False,
                "primary_status": "unknown",
                "dataplane_claim_blockers": [],
            }
        }

    # 1. settlement_evidence
    payload_settlement = payload.get("settlement_evidence") or {}
    settlement_summary = {
        "present": "settlement_evidence" in payload,
        "provider": payload_settlement.get("provider"),
        "settlement_action": payload_settlement.get("settlement_action"),
        "dataplane_confirmed": payload_settlement.get("dataplane_confirmed", False),
        "live_provider_settlement_confirmed": payload_settlement.get("live_provider_settlement_confirmed", False),
        "bank_settlement_confirmed": payload_settlement.get("bank_settlement_confirmed", False),
        "chain_finality_confirmed": payload_settlement.get("chain_finality_confirmed", False),
        "db_write_evidence": payload_settlement.get("db_write_evidence") or {"attempted": False, "committed": False},
        "output_summary": payload_settlement.get("output_summary") or {},
    }
    if "settlement_evidence" in payload and isinstance(payload["settlement_evidence"], dict):
        for k, v in payload["settlement_evidence"].items():
            if k == "claim_gate" and isinstance(v, dict):
                settlement_summary[k] = {"present": True, **v}
            else:
                settlement_summary[k] = v
        settlement_summary["present"] = True

    # 2. runtime_evidence
    evidence_keys = [
        k for k in payload
        if k.endswith("_evidence") and k != "settlement_evidence"
    ]
    runtime_summary = {
        "present": len(evidence_keys) > 0,
        "evidence_blocks_present": evidence_keys,
    }

    # 3. cross_plane_evidence_profile
    dataplane_confirmed = payload.get("dataplane_confirmed") is True
    if not dataplane_confirmed:
        # Check sub-evidence blocks or nested dicts
        for k, v in payload.items():
            if isinstance(v, dict) and v.get("dataplane_confirmed") is True:
                dataplane_confirmed = True
                break

    has_revalidation = (
        "post_action_dataplane_revalidation" in payload 
        or "post_action_dataplane_revalidated" in payload
        or any(
            isinstance(v, dict) and ("post_action_dataplane_revalidation" in v or "post_action_dataplane_revalidated" in v)
            for v in payload.values()
        )
    )

    cross_plane = {
        "dataplane_confirmed": dataplane_confirmed,
        "dataplane_claim_gate_required": has_revalidation,
        "dataplane_claim_gate_allowed": dataplane_confirmed,
        "production_ready_candidate": False,
        "claim_boundary_present": "claim_boundary" in payload or "claim_boundary_summary" in payload,
        "primary_status": payload.get("status") or "unknown",
        "dataplane_claim_blockers": [],
    }

    # Support parsing fields directly if they are already in the payload's cross_plane_evidence_profile
    payload_profile = payload.get("cross_plane_evidence_profile")
    if isinstance(payload_profile, dict):
        cross_plane.update(payload_profile)

    return {
        "available": True,
        "settlement_evidence": settlement_summary,
        "runtime_evidence": runtime_summary,
        "cross_plane_evidence_profile": cross_plane,
        "post_action_dataplane_revalidation": payload.get("post_action_dataplane_revalidation"),
        "post_action_dataplane_revalidated": payload.get("post_action_dataplane_revalidated"),
    }
