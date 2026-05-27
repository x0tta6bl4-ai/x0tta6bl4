"""
API Endpoints для Continuity Ledger

Semantic search и другие операции с ledger через API
"""

import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.coordination.events import EventBus, EventType
from src.ledger.rag_search import get_ledger_rag
from src.services.service_event_trace import service_event_trace_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])


class SearchRequest(BaseModel):
    """Запрос на поиск в ledger"""

    query: str
    top_k: Optional[int] = 10
    include_verification: Optional[bool] = False


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


def _extract_citations(results: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
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
                "redacted": redacted,
                "score": result.get("score"),
            }
        )
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
    metadata: Dict[str, Any], results: list[Dict[str, Any]]
) -> Dict[str, Any]:
    response_metadata = dict(metadata or {})
    citations = _extract_citations(results)
    if citations:
        response_metadata["citations"] = citations
    return response_metadata


def _search_response_from_result(query: str, result: Any) -> SearchResponse:
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
            metadata=_metadata_with_citations(metadata, ledger_results),
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

        # Выполнение поиска
        result = await ledger_rag.query(request.query, top_k=request.top_k)

        return _search_response_from_result(request.query, result)

    except Exception as e:
        logger.error(f"Ошибка при поиске в ledger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search", response_model=SearchResponse)
async def search_ledger_get(
    q: str = Query(..., description="Поисковый запрос"),
    top_k: int = Query(10, description="Количество результатов"),
):
    """
    Semantic search в Continuity Ledger (GET версия).

    Параметры:
    - q: Поисковый запрос
    - top_k: Количество результатов (по умолчанию 10)
    """
    request = SearchRequest(query=q, top_k=top_k)
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
async def ledger_status():
    """
    Статус индексирования ledger.
    """
    try:
        ledger_rag = get_ledger_rag()
        return {
            "indexed": ledger_rag.is_indexed(),
            "continuity_file": str(ledger_rag.continuity_file),
            "file_exists": ledger_rag.continuity_file.exists(),
        }
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
