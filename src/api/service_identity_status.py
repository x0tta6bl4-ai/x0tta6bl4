"""Redacted service identity status endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import (
    service_event_trace_filter,
    service_event_trace_history,
)
from src.services.service_identity_registry import service_identity_registry_status


router = APIRouter(prefix="/api/v1/service-identity", tags=["Service Identity"])


@router.get("/status")
async def get_service_identity_status():
    """Return identity configuration presence without exposing identity values."""
    return service_identity_registry_status()


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
