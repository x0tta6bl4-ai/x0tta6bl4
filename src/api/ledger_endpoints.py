"""
API Endpoints для Continuity Ledger

Semantic search и другие операции с ledger через API
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.ledger.rag_search import LedgerRAGSearch, get_ledger_rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])


class SearchRequest(BaseModel):
    """Запрос на поиск в ledger"""

    query: str
    top_k: Optional[int] = 10


class SearchResponse(BaseModel):
    """Ответ на поиск в ledger"""

    query: str
    results: list[Dict[str, Any]]
    total_results: int
    search_time_ms: float
    metadata: Dict[str, Any]


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

        # Выполнение поиска
        result = await ledger_rag.query(request.query, top_k=request.top_k)

        return SearchResponse(
            query=result.query,
            results=[asdict(chunk) for chunk in result.retrieved_chunks],
            total_results=len(result.retrieved_chunks),
            search_time_ms=result.retrieval_time_ms,
            metadata=result.metadata or {},
        )

    except Exception as e:
        logger.error(f"Ошибка при поиске в ledger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")


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
async def index_ledger(force: bool = False):
    """
    Индексирование CONTINUITY.md в RAG pipeline.

    Параметры:
    - force: Принудительная переиндексация (даже если уже проиндексировано)
    """
    try:
        ledger_rag = get_ledger_rag()
        success = await ledger_rag.index_ledger(force=force)

        if success:
            return {
                "status": "success",
                "message": "Ledger успешно проиндексирован",
                "indexed": ledger_rag.is_indexed(),
            }
        else:
            raise HTTPException(
                status_code=500, detail="Не удалось проиндексировать ledger"
            )

    except Exception as e:
        logger.error(f"Ошибка при индексировании ledger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка индексирования: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")
