"""Event trace helpers bound to registered service identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.coordination.events import Event, EventBus, EventType
from src.services.service_identity_registry import KNOWN_EVENT_IDENTITY_SERVICES


EVENT_TRACE_CLAIM_BOUNDARY = (
    "Trace filters only bind EventBus source_agent values to registered service "
    "names and layers. They do not authenticate events, expose identity values, "
    "or prove live SPIRE/chain state."
)

REDACTED_IDENTITY_FIELDS = frozenset({"spiffe_id", "did", "wallet_address"})
REDACTED_IDENTITY_VALUE = "[redacted]"


def _matching_registrations(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> List[Dict[str, str]]:
    return [
        dict(registration)
        for registration in KNOWN_EVENT_IDENTITY_SERVICES
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
        for registration in KNOWN_EVENT_IDENTITY_SERVICES
    }
    known_layers = {
        registration["layer"]
        for registration in KNOWN_EVENT_IDENTITY_SERVICES
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
        "registered_services_total": len(KNOWN_EVENT_IDENTITY_SERVICES),
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
            if key_text.lower() in REDACTED_IDENTITY_FIELDS and child is not None:
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
