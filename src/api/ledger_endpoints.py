"""Compatibility shim for legacy ``src.api.ledger_endpoints`` imports.

The canonical implementation lives in ``src.api.maas.endpoints.ledger``.  This
module keeps old monkeypatch-based tests and callers working by routing the
patchable globals here into the canonical endpoint functions before delegation.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from .maas.endpoints import ledger as modular
from .maas.endpoints.ledger import *  # noqa: F401,F403
from src.coordination.events import EventBus, EventType
from src.ledger.rag_search import get_ledger_rag


router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])


@router.post("/search", response_model=modular.SearchResponse)
async def search_ledger(request: modular.SearchRequest):
    original_get_ledger_rag = modular.get_ledger_rag
    modular.get_ledger_rag = get_ledger_rag
    try:
        return await modular.search_ledger(request)
    finally:
        modular.get_ledger_rag = original_get_ledger_rag


@router.get("/search", response_model=modular.SearchResponse)
async def search_ledger_get(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    include_verification: bool = Query(False),
    include_current_evidence: bool = Query(False),
):
    request = modular.SearchRequest(
        query=q,
        top_k=top_k,
        include_verification=include_verification,
        include_current_evidence=include_current_evidence,
    )
    return await search_ledger(request)


@router.post("/event-traces/index")
async def index_event_traces(
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    replay_agent: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    force: bool = False,
):
    original_get_ledger_rag = modular.get_ledger_rag
    original_event_bus = modular.EventBus
    modular.get_ledger_rag = get_ledger_rag
    modular.EventBus = EventBus
    try:
        return await modular.index_event_traces(
            service_name=service_name,
            layer=layer,
            event_type=event_type,
            replay_agent=replay_agent,
            since=since,
            limit=limit,
            force=force,
        )
    finally:
        modular.get_ledger_rag = original_get_ledger_rag
        modular.EventBus = original_event_bus


@router.get("/event-traces/status")
async def event_trace_status():
    original_get_ledger_rag = modular.get_ledger_rag
    modular.get_ledger_rag = get_ledger_rag
    try:
        return await modular.event_trace_status()
    finally:
        modular.get_ledger_rag = original_get_ledger_rag


for route in modular.router.routes:
    if route.path in {
        "/api/v1/ledger/search",
        "/api/v1/ledger/event-traces/index",
        "/api/v1/ledger/event-traces/status",
    }:
        continue
    router.routes.append(route)
