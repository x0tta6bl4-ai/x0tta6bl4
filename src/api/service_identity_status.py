"""Redacted service identity status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from src.coordination.events import EventBus, EventType
from src.core.reliability_policy import mark_degraded_dependency
from src.services.service_event_trace import (
    service_event_trace_filter,
    service_event_trace_history,
)
from src.services.service_identity_registry import service_identity_registry_status


router = APIRouter(prefix="/api/v1/service-identity", tags=["Service Identity"])


def _registry_payload_ready(payload: Dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("redacted") is True
        and isinstance(payload.get("services_total"), int)
        and isinstance(payload.get("services"), list)
    )


def _service_identity_readiness_status(
    registry_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    registry_surface_ready = callable(service_identity_registry_status)
    trace_filter_ready = callable(service_event_trace_filter)
    trace_history_ready = callable(service_event_trace_history)
    event_bus_surface_ready = callable(EventBus)
    event_type_surface_ready = bool(getattr(EventType, "__members__", None))
    registry_payload_ready = (
        _registry_payload_ready(registry_payload)
        if registry_payload is not None
        else registry_surface_ready
    )

    checks = {
        "service_identity_registry": registry_surface_ready,
        "service_event_trace_filter": trace_filter_ready,
        "service_event_trace_history": trace_history_ready,
        "event_bus_surface": event_bus_surface_ready,
        "event_type_surface": event_type_surface_ready,
        "registry_payload": registry_payload_ready,
    }
    degraded_dependencies = [
        dependency for dependency, ready in checks.items() if not ready
    ]
    service_identity_runtime_ready = not degraded_dependencies

    return {
        "readiness_status": (
            "ready" if service_identity_runtime_ready else "degraded"
        ),
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "service_identity_runtime_ready": service_identity_runtime_ready,
        "registry_surface_ready": registry_surface_ready,
        "trace_filter_ready": trace_filter_ready,
        "trace_history_ready": trace_history_ready,
        "event_bus_surface_ready": event_bus_surface_ready,
        "event_type_surface_ready": event_type_surface_ready,
        "registry_payload_ready": registry_payload_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "event_bus_project_root": ".",
            "event_trace_filter": "registered_service_or_layer",
            "identity_values_redacted": True,
        },
        "claim_boundary": (
            "Readiness verifies the redacted service identity registry and trace "
            "query surfaces. It does not prove live SPIFFE, DID, wallet, or event "
            "producer identity values exist."
        ),
    }


@router.get("/status")
async def get_service_identity_status(request: Request):
    """Return identity configuration presence without exposing identity values."""
    payload = service_identity_registry_status()
    readiness = _service_identity_readiness_status(payload)
    for dependency in readiness["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return {**payload, **readiness}


@router.get("/event-trace-filter")
async def get_service_event_trace_filter(
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
):
    """Return redacted EventBus trace filter metadata for registered services."""
    return service_event_trace_filter(service_name=service_name, layer=layer)


@router.get("/event-traces")
async def get_service_event_traces(
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    replay_agent: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Return redacted EventBus traces filtered by registered service metadata."""
    return service_event_trace_history(
        EventBus("."),
        service_name=service_name,
        layer=layer,
        event_type=event_type,
        replay_agent=replay_agent,
        since=since,
        limit=limit,
    )
