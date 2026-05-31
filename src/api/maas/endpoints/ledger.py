"""
API Endpoints для Continuity Ledger

Semantic search и другие операции с ledger через API
"""

import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.coordination.events import EventBus, EventType
from src.core.reliability_policy import mark_degraded_dependency
from src.ledger.rag_search import get_ledger_rag
from src.services.service_event_trace import service_event_trace_history

try:
    from scripts.ops.run_cross_plane_proof_gate import (
        build_report as build_cross_plane_proof_gate_report,
    )
except Exception:  # pragma: no cover - exercised by fail-closed fallback
    build_cross_plane_proof_gate_report = None

logger = logging.getLogger(__name__)

router = APIRouter( tags=["ledger"])

CLAIM_SENSITIVE_QUERY_TERMS = (
    "production",
    "production-ready",
    "production readiness",
    "prod ready",
    "readiness",
    "deployment ready",
    "готов",
    "готовность",
    "продакшен",
    "dataplane",
    "data-plane",
    "traffic delivery",
    "customer traffic",
    "settlement",
    "finality",
    "payment",
    "token finality",
    "dpi",
    "bypass",
    "external reachability",
    "external dpi",
    "обход",
    "внешн",
)
QUERY_CLAIM_TERMS = {
    "production_readiness": (
        "production",
        "production-ready",
        "production readiness",
        "prod ready",
        "readiness",
        "deployment ready",
        "готов",
        "готовность",
        "продакшен",
    ),
    "dataplane_delivery": (
        "dataplane",
        "data-plane",
        "customer dataplane",
        "mesh dataplane",
    ),
    "traffic_delivery": (
        "traffic delivery",
        "customer traffic",
        "live traffic",
    ),
    "settlement_finality": (
        "settlement",
        "finality",
        "payment",
        "token finality",
    ),
    "dpi_bypass": (
        "dpi",
        "bypass",
        "external reachability",
        "external dpi",
        "обход",
        "внешн",
    ),
}
CLAIM_USAGE_GATE_BOUNDARY = (
    "Ledger search citations are retrieval context only. They are not standalone "
    "proof for production, dataplane, traffic, DPI, trust, or settlement claims; "
    "claim promotion must pass the cross-plane proof gate and current evidence "
    "context."
)


class SearchRequest(BaseModel):
    """Запрос на поиск в ledger"""

    query: str
    top_k: Optional[int] = 10
    include_verification: Optional[bool] = False
    include_current_evidence: Optional[bool] = False


class SearchResponse(BaseModel):
    """Ответ на поиск в ledger"""

    query: str
    results: list[Dict[str, Any]]
    total_results: int
    search_time_ms: float
    metadata: Dict[str, Any]


def _serialize_chunk(chunk: Any) -> Dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if is_dataclass(chunk):
        return asdict(chunk)
    if hasattr(chunk, "__dict__"):
        return dict(chunk.__dict__)
    return {"text": str(chunk)}


def _compact_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in citation.items() if value is not None}


def _citation_claim_usage_gate(
    citation: Dict[str, Any],
    *,
    claim_sensitive_query: bool,
    cross_plane_claim_gate: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not claim_sensitive_query:
        return None

    gate = cross_plane_claim_gate if isinstance(cross_plane_claim_gate, dict) else {}
    gate_allowed = gate.get("allowed") is True
    current_evidence = citation.get("current_evidence") is True
    historical = citation.get("historical_claim_inventory") is True
    requires_context = citation.get("requires_current_evidence_context") is True
    upstream_claim_gate = citation.get("upstream_claim_gate_summary")
    if not isinstance(upstream_claim_gate, dict):
        upstream_claim_gate = {}
    upstream_cross_plane_claim_gate = citation.get(
        "upstream_cross_plane_claim_gate_summary"
    )
    if not isinstance(upstream_cross_plane_claim_gate, dict):
        upstream_cross_plane_claim_gate = {}
    upstream_claim_gate_present = upstream_claim_gate.get("present") is True
    upstream_cross_plane_claim_gate_present = (
        upstream_cross_plane_claim_gate.get("present") is True
    )
    upstream_cross_plane_gate_allowed = (
        upstream_cross_plane_claim_gate.get("allowed") is True
        if upstream_cross_plane_claim_gate_present
        else None
    )
    external_dpi_intake_gate = citation.get("external_dpi_intake_claim_gate_summary")
    if not isinstance(external_dpi_intake_gate, dict):
        external_dpi_intake_gate = {}
    external_dpi_intake_gate_present = external_dpi_intake_gate.get("present") is True
    external_evidence_gap_record = (
        citation.get("external_evidence_gap_record") is True
        or external_dpi_intake_gate.get("external_evidence_gap_record") is True
    )
    blockers: list[str] = []

    if historical:
        blockers.append("historical_claim_inventory_not_proof")
    if requires_context:
        blockers.append("citation_requires_current_evidence_context")
    if not current_evidence:
        blockers.append("citation_not_current_evidence")
    if gate.get("available") is False:
        blockers.append("cross_plane_claim_gate_unavailable")
    if not gate_allowed:
        blockers.append("cross_plane_claim_gate_blocked")
    if upstream_claim_gate_present:
        blockers.append("upstream_claim_gate_local_only_not_proof")
    if (
        upstream_cross_plane_claim_gate_present
        and upstream_cross_plane_gate_allowed is not True
    ):
        blockers.append("upstream_cross_plane_claim_gate_blocked")
    if external_evidence_gap_record:
        blockers.append("external_evidence_gap_record_not_proof")
    if external_dpi_intake_gate_present:
        blockers.append("external_dpi_intake_citation_not_proof")
        if external_dpi_intake_gate.get("proof_gate_dpi_bypass_claim_allowed") is not True:
            blockers.append("external_dpi_proof_gate_not_allowed")

    return {
        "claim_sensitive_query": True,
        "standalone_claim_proof_allowed": False,
        "claim_promotion_allowed": not blockers,
        "current_context_allowed": bool(current_evidence and not historical),
        "cross_plane_gate_allowed": gate_allowed,
        "upstream_claim_gate_present": upstream_claim_gate_present,
        "upstream_cross_plane_claim_gate_present": (
            upstream_cross_plane_claim_gate_present
        ),
        "upstream_cross_plane_gate_allowed": upstream_cross_plane_gate_allowed,
        "external_dpi_intake_claim_gate_present": external_dpi_intake_gate_present,
        "external_evidence_gap_record": external_evidence_gap_record,
        "blockers": blockers,
        "claim_boundary": CLAIM_USAGE_GATE_BOUNDARY,
    }


def _claim_sensitive_citation_gate_summary(
    citations: list[Dict[str, Any]],
) -> Dict[str, Any]:
    gates = [
        citation.get("claim_usage_gate")
        for citation in citations
        if isinstance(citation.get("claim_usage_gate"), dict)
    ]
    return {
        "claim_sensitive_query": True,
        "citations_total": len(citations),
        "citation_gates_total": len(gates),
        "claim_promotion_allowed": bool(gates)
        and all(gate.get("claim_promotion_allowed") is True for gate in gates),
        "blocked_citations": sum(
            1 for gate in gates if gate.get("claim_promotion_allowed") is not True
        ),
        "historical_claim_inventory_citations": sum(
            1
            for citation in citations
            if citation.get("historical_claim_inventory") is True
        ),
        "requires_current_evidence_context_citations": sum(
            1
            for citation in citations
            if citation.get("requires_current_evidence_context") is True
        ),
        "current_evidence_citations": sum(
            1 for citation in citations if citation.get("current_evidence") is True
        ),
        "external_dpi_intake_citations": sum(
            1
            for citation in citations
            if isinstance(citation.get("external_dpi_intake_claim_gate_summary"), dict)
        ),
        "external_evidence_gap_record_citations": sum(
            1
            for citation in citations
            if citation.get("external_evidence_gap_record") is True
        ),
        "claim_boundary": CLAIM_USAGE_GATE_BOUNDARY,
    }


def _extract_citations(
    results: list[Dict[str, Any]],
    *,
    claim_sensitive_query: bool = False,
    cross_plane_claim_gate: Optional[Dict[str, Any]] = None,
) -> list[Dict[str, Any]]:
    citations: list[Dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any, Any]] = set()

    for result in results:
        if not isinstance(result, dict):
            continue
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        source = metadata.get("source") or result.get("source")
        source_class = metadata.get("source_class") or result.get("source_class")
        relative_path = metadata.get("relative_path") or result.get("relative_path")
        redacted = (
            metadata["redacted"] if "redacted" in metadata else result.get("redacted")
        )

        if not any((source, source_class, relative_path)):
            continue

        citation = _compact_citation(
            {
                "source": source,
                "source_class": source_class,
                "relative_path": relative_path,
                "title": metadata.get("title") or result.get("section"),
                "section": metadata.get("section") or result.get("section"),
                "document_id": metadata.get("document_id") or result.get("document_id"),
                "chunk_id": metadata.get("chunk_id") or result.get("chunk_id"),
                "file_suffix": metadata.get("file_suffix"),
                "latest_alias": metadata.get("latest_alias"),
                "event_id": metadata.get("event_id") or result.get("event_id"),
                "event_type": metadata.get("event_type") or result.get("event_type"),
                "source_agent": metadata.get("source_agent")
                or result.get("source_agent"),
                "service_name": metadata.get("service_name")
                or result.get("service_name"),
                "layer": metadata.get("layer") or result.get("layer"),
                "entrypoint": metadata.get("entrypoint") or result.get("entrypoint"),
                "evidence_summary": metadata.get("evidence_summary")
                or result.get("evidence_summary"),
                "claim_boundary_summary": metadata.get("claim_boundary_summary")
                or result.get("claim_boundary_summary"),
                "upstream_claim_gate_summary": metadata.get(
                    "upstream_claim_gate_summary"
                )
                or result.get("upstream_claim_gate_summary"),
                "upstream_cross_plane_claim_gate_summary": metadata.get(
                    "upstream_cross_plane_claim_gate_summary"
                )
                or result.get("upstream_cross_plane_claim_gate_summary"),
                "cross_plane_evidence_profile": metadata.get(
                    "cross_plane_evidence_profile"
                )
                or result.get("cross_plane_evidence_profile"),
                "economy_finality_summary": metadata.get("economy_finality_summary")
                or result.get("economy_finality_summary"),
                "external_dpi_intake_claim_gate_summary": metadata.get(
                    "external_dpi_intake_claim_gate_summary"
                )
                or result.get("external_dpi_intake_claim_gate_summary"),
                "external_evidence_gap_record": (
                    metadata["external_evidence_gap_record"]
                    if "external_evidence_gap_record" in metadata
                    else result.get("external_evidence_gap_record")
                ),
                "claim_status": metadata.get("claim_status")
                or result.get("claim_status"),
                "claim_scope": metadata.get("claim_scope")
                or result.get("claim_scope"),
                "current_evidence": (
                    metadata["current_evidence"]
                    if "current_evidence" in metadata
                    else result.get("current_evidence")
                ),
                "historical_claim_inventory": (
                    metadata["historical_claim_inventory"]
                    if "historical_claim_inventory" in metadata
                    else result.get("historical_claim_inventory")
                ),
                "requires_current_evidence_context": (
                    metadata["requires_current_evidence_context"]
                    if "requires_current_evidence_context" in metadata
                    else result.get("requires_current_evidence_context")
                ),
                "runtime_memory_priority": metadata.get("runtime_memory_priority")
                or result.get("runtime_memory_priority"),
                "redacted": redacted,
                "score": result.get("score"),
                "claim_adjusted_score": result.get("claim_adjusted_score"),
            }
        )
        claim_usage_gate = _citation_claim_usage_gate(
            citation,
            claim_sensitive_query=claim_sensitive_query,
            cross_plane_claim_gate=cross_plane_claim_gate,
        )
        if claim_usage_gate is not None:
            citation["claim_usage_gate"] = claim_usage_gate
        dedupe_key = (
            citation.get("relative_path"),
            citation.get("document_id"),
            citation.get("chunk_id"),
            citation.get("source"),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        citations.append(citation)

    return citations


def _metadata_with_citations(
    metadata: Dict[str, Any],
    results: list[Dict[str, Any]],
    *,
    claim_sensitive_query: bool = False,
    cross_plane_claim_gate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response_metadata = dict(metadata or {})
    citations = _extract_citations(
        results,
        claim_sensitive_query=claim_sensitive_query,
        cross_plane_claim_gate=cross_plane_claim_gate,
    )
    if citations:
        response_metadata["citations"] = citations
    if claim_sensitive_query:
        response_metadata["claim_sensitive_citation_gate"] = (
            _claim_sensitive_citation_gate_summary(citations)
        )
    return response_metadata


def _ledger_rag_surface_available(ledger_rag: Any) -> bool:
    return all(
        callable(getattr(ledger_rag, attr, None))
        for attr in ("is_indexed", "index_ledger", "query")
    )


def _ledger_continuity_file_available(ledger_rag: Any) -> bool:
    continuity_file = getattr(ledger_rag, "continuity_file", None)
    return continuity_file is not None and callable(
        getattr(continuity_file, "exists", None)
    )


def _ledger_verification_evidence_available(ledger_rag: Any) -> bool:
    return all(
        callable(getattr(ledger_rag, attr, None))
        for attr in (
            "is_verification_indexed",
            "index_verification_evidence",
            "verification_evidence_status",
        )
    )


def _ledger_current_evidence_available(ledger_rag: Any) -> bool:
    return all(
        callable(getattr(ledger_rag, attr, None))
        for attr in (
            "is_current_evidence_indexed",
            "index_current_evidence",
            "current_evidence_status",
        )
    )


def _query_requires_current_evidence(query: str) -> bool:
    normalized = " ".join(str(query or "").lower().replace("_", " ").split())
    return any(term in normalized for term in CLAIM_SENSITIVE_QUERY_TERMS)


def _query_cross_plane_claims(query: str) -> list[str]:
    normalized = " ".join(str(query or "").lower().replace("_", " ").split())
    claims = [
        claim_id
        for claim_id, terms in QUERY_CLAIM_TERMS.items()
        if any(term in normalized for term in terms)
    ]
    return claims or ["production_readiness"]


def _current_evidence_context_metadata(
    *,
    included: bool,
    reason: str,
    claim_sensitive_query: bool,
    explicit_request: bool,
) -> Dict[str, Any]:
    return {
        "included": included,
        "reason": reason,
        "claim_sensitive_query": claim_sensitive_query,
        "explicit_request": explicit_request,
        "claim_boundary": (
            "Current architecture evidence maps/audit are search context, not proof "
            "that the requested production, dataplane, trust, DPI, or settlement "
            "claim is true."
        ),
    }


def _cross_plane_claim_gate_metadata(query: str) -> Dict[str, Any]:
    claims = _query_cross_plane_claims(query)
    if build_cross_plane_proof_gate_report is None:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": claims,
            "available": False,
            "blockers": ["cross_plane_proof_gate_unavailable"],
            "claim_boundary": (
                "Cross-plane claim gate unavailable; claim-sensitive Ledger "
                "search must not promote production, dataplane, DPI, traffic, "
                "or settlement claims from search results alone."
            ),
        }
    try:
        report = build_cross_plane_proof_gate_report(Path("."), claims=tuple(claims))
    except Exception as exc:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": claims,
            "available": False,
            "blockers": [f"cross_plane_proof_gate_error:{type(exc).__name__}"],
            "claim_boundary": (
                "Cross-plane claim gate failed closed; claim-sensitive Ledger "
                "search must not promote production, dataplane, DPI, traffic, "
                "or settlement claims from search results alone."
            ),
        }
    return {
        "schema": report.get("schema"),
        "decision": report.get("decision"),
        "allowed": report.get("allowed") is True,
        "available": True,
        "requested_claim_ids": claims,
        "summary": report.get("summary"),
        "context": report.get("context"),
        "claim_results": report.get("claim_results"),
        "claim_boundary": report.get("claim_boundary"),
    }


def _ledger_event_trace_index_available(ledger_rag: Any) -> bool:
    return all(
        callable(getattr(ledger_rag, attr, None))
        for attr in ("index_event_traces", "event_trace_status")
    )


def _ledger_event_trace_dependencies_available() -> bool:
    return callable(EventBus) and callable(service_event_trace_history) and bool(
        getattr(EventType, "__members__", None)
    )


def _safe_file_exists(ledger_rag: Any) -> bool:
    continuity_file = getattr(ledger_rag, "continuity_file", None)
    exists = getattr(continuity_file, "exists", None)
    if not callable(exists):
        return False
    return bool(exists())


def _safe_is_indexed(ledger_rag: Any) -> bool:
    is_indexed = getattr(ledger_rag, "is_indexed", None)
    if not callable(is_indexed):
        return False
    return bool(is_indexed())


def _ledger_readiness_status(ledger_rag: Any) -> Dict[str, Any]:
    rag_surface_ready = _ledger_rag_surface_available(ledger_rag)
    continuity_file_ready = _ledger_continuity_file_available(ledger_rag)
    verification_evidence_ready = _ledger_verification_evidence_available(ledger_rag)
    event_trace_index_ready = _ledger_event_trace_index_available(ledger_rag)
    event_trace_dependencies_ready = _ledger_event_trace_dependencies_available()
    file_exists = _safe_file_exists(ledger_rag)
    indexed = _safe_is_indexed(ledger_rag)
    ledger_runtime_ready = (
        rag_surface_ready
        and continuity_file_ready
        and file_exists
        and verification_evidence_ready
        and event_trace_index_ready
        and event_trace_dependencies_ready
    )

    degraded_dependencies = []
    if not rag_surface_ready:
        degraded_dependencies.append("rag")
    if not continuity_file_ready or not file_exists:
        degraded_dependencies.append("continuity_file")
    if not verification_evidence_ready:
        degraded_dependencies.append("verification_evidence")
    if not event_trace_index_ready:
        degraded_dependencies.append("event_trace_index")
    if not event_trace_dependencies_ready:
        degraded_dependencies.append("event_trace_dependencies")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "ledger_runtime_ready": ledger_runtime_ready,
        "indexed": indexed,
        "continuity_file": str(getattr(ledger_rag, "continuity_file", "")),
        "file_exists": file_exists,
        "rag_surface_ready": rag_surface_ready,
        "continuity_file_ready": continuity_file_ready,
        "verification_evidence_ready": verification_evidence_ready,
        "event_trace_index_ready": event_trace_index_ready,
        "event_trace_dependencies_ready": event_trace_dependencies_ready,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/ledger",
            "boundary": (
                "Ledger routes use the fixed /api/v1/ledger prefix, so they are "
                "outside legacy MaaS catch-all matching. They are still "
                "full-mode-only because src.core.app only registers this router "
                "when light mode is disabled."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "rag": (
                "Search and indexing depend on get_ledger_rag exposing is_indexed, "
                "index_ledger, and query."
            ),
            "continuity_file": (
                "The base ledger index is anchored on ledger_rag.continuity_file "
                "and its exists() check."
            ),
            "verification_evidence": (
                "Verification evidence indexing/status depends on the ledger RAG "
                "verification evidence methods."
            ),
            "event_trace_index": (
                "Runtime EventBus traces are indexed through ledger_rag "
                "event-trace methods."
            ),
            "event_trace_dependencies": (
                "Event trace indexing depends on EventBus, EventType, and "
                "service_event_trace_history."
            ),
        },
        "cross_plane_claim_gate": _cross_plane_claim_gate_metadata(
            "production readiness dataplane traffic delivery settlement dpi"
        ),
        "claim_boundary": (
            "Ledger readiness proves that the API can see the local RAG surfaces, "
            "continuity file handle, verification evidence methods, and EventBus "
            "trace indexing surfaces. It does not perform indexing, execute a "
            "semantic query, or prove the vector store contains fresh data."
        ),
    }


def _search_response_from_result(
    query: str,
    result: Any,
    *,
    claim_sensitive_query: bool = False,
    cross_plane_claim_gate: Optional[Dict[str, Any]] = None,
) -> SearchResponse:
    ledger_results = getattr(result, "results", None)
    if isinstance(ledger_results, list):
        search_time_ms = getattr(result, "search_time_ms", 0.0)
        if not isinstance(search_time_ms, (int, float)):
            search_time_ms = 0.0
        metadata = getattr(result, "metadata", {}) or {}
        return SearchResponse(
            query=getattr(result, "query", query),
            results=ledger_results,
            total_results=getattr(result, "total_results", len(ledger_results)),
            search_time_ms=float(search_time_ms),
            metadata=_metadata_with_citations(
                metadata,
                ledger_results,
                claim_sensitive_query=claim_sensitive_query,
                cross_plane_claim_gate=cross_plane_claim_gate,
            ),
        )

    chunks = getattr(result, "retrieved_chunks", []) or []
    retrieval_time_ms = getattr(result, "retrieval_time_ms", 0.0)
    if not isinstance(retrieval_time_ms, (int, float)):
        retrieval_time_ms = 0.0
    results = [_serialize_chunk(chunk) for chunk in chunks]
    return SearchResponse(
        query=getattr(result, "query", query),
        results=results,
        total_results=len(chunks),
        search_time_ms=float(retrieval_time_ms),
        metadata=_metadata_with_citations(
            getattr(result, "metadata", {}) or {},
            results,
            claim_sensitive_query=claim_sensitive_query,
            cross_plane_claim_gate=cross_plane_claim_gate,
        ),
    )


@router.post("/search", response_model=SearchResponse)
async def search_ledger(request: SearchRequest):
    """
    Semantic search в Continuity Ledger через RAG.

    Использует существующий RAG pipeline для semantic search в CONTINUITY.md.

    Примеры запросов:
    - "Какие метрики у нас хуже targets?"
    - "Какие issues нужно решить в первую очередь?"
    - "Что изменилось за последнюю неделю?"
    - "Какие компоненты готовы к deployment?"
    """
    try:
        ledger_rag = get_ledger_rag()

        # Убеждаемся, что ledger проиндексирован
        if not ledger_rag.is_indexed():
            logger.info("Индексирование ledger...")
            await ledger_rag.index_ledger()

        if request.include_verification and not ledger_rag.is_verification_indexed():
            logger.info("Индексирование verification evidence...")
            await ledger_rag.index_verification_evidence()
        current_evidence_status = None
        claim_sensitive_query = _query_requires_current_evidence(request.query)
        explicit_current_evidence = request.include_current_evidence is True
        include_current_evidence = explicit_current_evidence or claim_sensitive_query
        current_evidence_reason = (
            "explicit_request" if explicit_current_evidence else "claim_sensitive_query"
        )
        if include_current_evidence:
            if not _ledger_current_evidence_available(ledger_rag):
                raise RuntimeError("current evidence indexing is unavailable")
            if not ledger_rag.is_current_evidence_indexed():
                logger.info("Индексирование current architecture evidence...")
                await ledger_rag.index_current_evidence()
            current_evidence_status = ledger_rag.current_evidence_status()

        # Выполнение поиска
        result = await ledger_rag.query(request.query, top_k=request.top_k)

        cross_plane_claim_gate = (
            _cross_plane_claim_gate_metadata(request.query)
            if claim_sensitive_query
            else None
        )
        response = _search_response_from_result(
            request.query,
            result,
            claim_sensitive_query=claim_sensitive_query,
            cross_plane_claim_gate=cross_plane_claim_gate,
        )
        if current_evidence_status is not None:
            response.metadata["current_evidence"] = current_evidence_status
        response.metadata["current_evidence_context"] = _current_evidence_context_metadata(
            included=current_evidence_status is not None,
            reason=(
                current_evidence_reason
                if current_evidence_status is not None
                else "not_requested_or_detected"
            ),
            claim_sensitive_query=claim_sensitive_query,
            explicit_request=explicit_current_evidence,
        )
        if cross_plane_claim_gate is not None:
            response.metadata["cross_plane_claim_gate"] = cross_plane_claim_gate
        return response

    except Exception as e:
        logger.error(f"Ошибка при поиске в ledger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search", response_model=SearchResponse)
async def search_ledger_get(
    q: str = Query(..., description="Поисковый запрос"),
    top_k: int = Query(10, description="Количество результатов"),
    include_verification: bool = Query(
        False,
        description="Index verification evidence",
    ),
    include_current_evidence: bool = Query(
        False,
        description="Index current architecture evidence maps/audit",
    ),
):
    """
    Semantic search в Continuity Ledger (GET версия).

    Параметры:
    - q: Поисковый запрос
    - top_k: Количество результатов (по умолчанию 10)
    """
    request = SearchRequest(
        query=q,
        top_k=top_k,
        include_verification=include_verification,
        include_current_evidence=include_current_evidence,
    )
    return await search_ledger(request)


@router.post("/index")
async def index_ledger(force: bool = False, include_verification: bool = False):
    """
    Индексирование CONTINUITY.md в RAG pipeline.

    Параметры:
    - force: Принудительная переиндексация (даже если уже проиндексировано)
    """
    try:
        ledger_rag = get_ledger_rag()
        success = await ledger_rag.index_ledger(force=force)
        verification = None
        if success and include_verification:
            verification_success = await ledger_rag.index_verification_evidence(
                force=force
            )
            verification = ledger_rag.verification_evidence_status()
            verification["index_success"] = verification_success

        if success:
            return {
                "status": "success",
                "message": "Ledger успешно проиндексирован",
                "indexed": ledger_rag.is_indexed(),
                "verification_evidence": verification,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Не удалось проиндексировать ledger"
            )

    except Exception as e:
        logger.error(f"Ошибка при индексировании ledger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def ledger_status(request: Request):
    """
    Статус индексирования ledger.
    """
    try:
        ledger_rag = get_ledger_rag()
        payload = _ledger_readiness_status(ledger_rag)
        for dependency in payload["degraded_dependencies"]:
            mark_degraded_dependency(request, dependency)
        return payload
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evidence/index")
async def index_verification_evidence(
    force: bool = False,
    max_files: Optional[int] = Query(
        None, ge=1, description="Optional limit for indexing a sample of evidence files"
    ),
):
    """
    Индексирование docs/verification artifacts в runtime RAG surface.
    """
    try:
        ledger_rag = get_ledger_rag()
        success = await ledger_rag.index_verification_evidence(
            force=force,
            max_files=max_files,
        )
        status_payload = ledger_rag.verification_evidence_status()
        status_payload["index_success"] = success

        if success:
            return {
                "status": "success",
                "message": "Verification evidence успешно проиндексирован",
                "verification_evidence": status_payload,
            }
        raise HTTPException(
            status_code=500, detail="Не удалось проиндексировать verification evidence"
        )

    except Exception as e:
        logger.error(
            f"Ошибка при индексировании verification evidence: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/evidence/status")
async def verification_evidence_status():
    """
    Статус docs/verification artifacts как runtime evidence source.
    """
    try:
        ledger_rag = get_ledger_rag()
        return ledger_rag.verification_evidence_status()
    except Exception as e:
        logger.error(
            f"Ошибка при получении статуса verification evidence: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")


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
    """
    Index redacted EventBus traces into the runtime RAG surface.
    """
    try:
        ledger_rag = get_ledger_rag()
        trace_payload = service_event_trace_history(
            EventBus("."),
            service_name=service_name,
            layer=layer,
            event_type=event_type,
            replay_agent=replay_agent,
            since=since,
            limit=limit,
        )
        success = await ledger_rag.index_event_traces(
            trace_payload,
            force=force,
        )
        status_payload = ledger_rag.event_trace_status()
        status_payload["index_success"] = success
        status_payload["trace_filter"] = trace_payload["filter"]
        status_payload["events_seen"] = trace_payload["events_total"]

        if success:
            return {
                "status": "success",
                "message": "EventBus traces успешно проиндексированы",
                "event_traces": status_payload,
            }
        raise HTTPException(
            status_code=500, detail="Не удалось проиндексировать EventBus traces"
        )

    except Exception as e:
        logger.error(f"Ошибка при индексировании EventBus traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/event-traces/status")
async def event_trace_status():
    """
    Status for EventBus traces indexed into runtime RAG surface.
    """
    try:
        ledger_rag = get_ledger_rag()
        return ledger_rag.event_trace_status()
    except Exception as e:
        logger.error(
            f"Ошибка при получении статуса EventBus traces: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")
