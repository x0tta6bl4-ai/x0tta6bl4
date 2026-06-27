"""Redacted service identity status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.coordination.events import EventBus, EventType
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.services.service_event_trace import (
    service_event_trace_filter,
    service_event_trace_history,
)
from src.services.service_identity_registry import service_identity_registry_status


router = APIRouter( tags=["Service Identity"])
SERVICE_IDENTITY_CLAIM_GATE_BOUNDARY = (
    "Service identity status is redacted configuration and trace-surface "
    "evidence only. It does not prove live SPIFFE SVID issuance, DID ownership, "
    "wallet control, event-producer identity authenticity, chain identity "
    "finality, or production readiness."
)


def _registry_payload_ready(payload: Dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("redacted") is True
        and isinstance(payload.get("services_total"), int)
        and isinstance(payload.get("services"), list)
    )


def _service_identity_claim_gate(
    *,
    registry_payload_ready: bool,
    service_identity_runtime_ready: bool,
    surface: str = "service_identity.status",
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.service_identity.claim_gate.v1",
        "surface": surface,
        "decision": (
            "redacted_identity_configuration_only"
            if service_identity_runtime_ready and registry_payload_ready
            else "redacted_trace_query_only"
            if service_identity_runtime_ready
            else "identity_surface_degraded"
        ),
        "local_redacted_identity_registry_claim_allowed": bool(
            registry_payload_ready
        ),
        "local_trace_filter_surface_claim_allowed": bool(
            service_identity_runtime_ready
        ),
        "live_spiffe_svid_claim_allowed": False,
        "did_ownership_claim_allowed": False,
        "wallet_control_claim_allowed": False,
        "event_producer_identity_authenticity_claim_allowed": False,
        "chain_identity_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_live_spire_svid_evidence_for_svid_claim": True,
        "requires_did_challenge_evidence_for_did_ownership_claim": True,
        "requires_wallet_signature_evidence_for_wallet_control_claim": True,
        "requires_chain_finality_evidence_for_chain_identity_claim": True,
        "raw_identity_values_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": SERVICE_IDENTITY_CLAIM_GATE_BOUNDARY,
    }


def _redacted_trace_payload_ready(payload: Dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("redacted") is True
    )


def _attach_service_identity_trace_claim_gates(
    payload: Dict[str, Any],
    *,
    surface: str,
) -> Dict[str, Any]:
    trace_surface_ready = _redacted_trace_payload_ready(payload)
    return {
        **payload,
        "service_identity_claim_gate": _service_identity_claim_gate(
            registry_payload_ready=False,
            service_identity_runtime_ready=trace_surface_ready,
            surface=surface,
        ),
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface=surface
        ),
    }


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
        "service_identity_claim_gate": _service_identity_claim_gate(
            registry_payload_ready=registry_payload_ready,
            service_identity_runtime_ready=service_identity_runtime_ready,
        ),
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="service_identity_readiness"
        ),
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
    payload = service_event_trace_filter(service_name=service_name, layer=layer)
    return _attach_service_identity_trace_claim_gates(
        payload,
        surface="service_identity.event_trace_filter",
    )


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
    payload = service_event_trace_history(
        EventBus("."),
        service_name=service_name,
        layer=layer,
        event_type=event_type,
        replay_agent=replay_agent,
        since=since,
        limit=limit,
    )
    return _attach_service_identity_trace_claim_gates(
        payload,
        surface="service_identity.event_traces",
    )
