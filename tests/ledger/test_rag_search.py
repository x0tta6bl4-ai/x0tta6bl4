"""
Tests for Ledger RAG Search Integration
"""

import pytest
import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ledger.rag_search import LedgerRAGSearch, LedgerSearchResult


@pytest.mark.asyncio
async def test_ledger_rag_initialization():
    """Test LedgerRAGSearch initialization"""
    ledger_rag = LedgerRAGSearch()
    assert ledger_rag is not None
    assert ledger_rag.continuity_file.exists()
    assert not ledger_rag.is_indexed()


@pytest.mark.asyncio
async def test_index_ledger():
    """Test indexing CONTINUITY.md"""
    ledger_rag = LedgerRAGSearch()
    
    # Индексирование
    success = await ledger_rag.index_ledger()
    
    # Проверка
    assert success is True
    assert ledger_rag.is_indexed()


@pytest.mark.asyncio
async def test_query_ledger():
    """Test semantic search in ledger"""
    ledger_rag = LedgerRAGSearch()
    
    # Убеждаемся, что проиндексирован
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    # Поиск
    result = await ledger_rag.query("Какие метрики у нас хуже targets?")
    
    # Проверка
    assert isinstance(result, LedgerSearchResult)
    assert result.query == "Какие метрики у нас хуже targets?"
    assert result.total_results >= 0
    assert result.search_time_ms >= 0


@pytest.mark.asyncio
async def test_query_empty():
    """Test query with empty string"""
    ledger_rag = LedgerRAGSearch()
    
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    # Пустой запрос должен вернуть пустые результаты или ошибку
    result = await ledger_rag.query("")
    
    # Проверка
    assert isinstance(result, LedgerSearchResult)
    assert result.total_results >= 0


@pytest.mark.asyncio
async def test_search_method():
    """Test search method (returns dict)"""
    ledger_rag = LedgerRAGSearch()
    
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    # Поиск через search method
    result = await ledger_rag.search("Какие компоненты готовы к deployment?")
    
    # Проверка
    assert isinstance(result, dict)
    assert "query" in result
    assert "results" in result
    assert "total_results" in result
    assert "search_time_ms" in result

