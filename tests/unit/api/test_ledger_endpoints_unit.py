"""
Unit tests for src/api/ledger_endpoints.py
Tests ledger search, index, and status endpoints.
"""

import os
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from fastapi import FastAPI

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ledger_rag():
    """Mock LedgerRAGSearch instance — fully MagicMock (no real Path)."""
    rag = MagicMock()
    rag.is_indexed.return_value = True
    # continuity_file as a MagicMock so .exists() works
    rag.continuity_file = MagicMock()
    rag.continuity_file.__str__ = MagicMock(return_value="/mnt/projects/CONTINUITY.md")
    rag.continuity_file.exists.return_value = True
    return rag


@pytest.fixture
def app_and_rag(mock_ledger_rag):
    """FastAPI app with mocked ledger RAG dependency."""
    with patch("src.api.ledger_endpoints.get_ledger_rag", return_value=mock_ledger_rag):
        from src.api.ledger_endpoints import router

        app = FastAPI()
        app.include_router(router)
        yield app, mock_ledger_rag


def _make_client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@dataclass
class _FakeChunk:
    text: str
    score: float


def _make_result(query: str, chunks: list, t_ms: float, metadata: dict):
    r = MagicMock()
    r.query = query
    r.retrieved_chunks = chunks
    r.retrieval_time_ms = t_ms
    r.metadata = metadata
    return r


# ===========================================================================
# POST /api/v1/ledger/search
# ===========================================================================


class TestSearchLedgerPost:

    @pytest.mark.asyncio
    async def test_search_success(self, app_and_rag):
        app, rag = app_and_rag
        mock_result = _make_result(
            "test query",
            [_FakeChunk(text="result1", score=0.9)],
            12.5,
            {"source": "CONTINUITY.md"},
        )
        rag.query = AsyncMock(return_value=mock_result)

        async with _make_client(app) as tc:
            resp = await tc.post(
                "/api/v1/ledger/search", json={"query": "test query", "top_k": 5}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "test query"
        assert body["total_results"] == 1
        assert len(body["results"]) == 1
        assert pytest.approx(body["search_time_ms"], abs=0.1) == 12.5

    @pytest.mark.asyncio
    async def test_search_auto_indexes(self, app_and_rag):
        """If not indexed, should call index_ledger first."""
        app, rag = app_and_rag
        rag.is_indexed.return_value = False
        rag.index_ledger = AsyncMock(return_value=True)
        mock_result = _make_result("q", [], 5.0, {})
        rag.query = AsyncMock(return_value=mock_result)

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 200
        rag.index_ledger.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_default_top_k(self, app_and_rag):
        app, rag = app_and_rag
        mock_result = _make_result("q", [], 1.0, {})
        rag.query = AsyncMock(return_value=mock_result)

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 200
        rag.query.assert_awaited_once_with("q", top_k=10)

    @pytest.mark.asyncio
    async def test_search_error(self, app_and_rag):
        app, rag = app_and_rag
        rag.query = AsyncMock(side_effect=RuntimeError("search failed"))

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"


# ===========================================================================
# GET /api/v1/ledger/search
# ===========================================================================


class TestSearchLedgerGet:

    @pytest.mark.asyncio
    async def test_get_search(self, app_and_rag):
        app, rag = app_and_rag
        mock_result = _make_result("hello", [], 2.0, {})
        rag.query = AsyncMock(return_value=mock_result)

        async with _make_client(app) as tc:
            resp = await tc.get(
                "/api/v1/ledger/search", params={"q": "hello", "top_k": 3}
            )
        assert resp.status_code == 200
        assert resp.json()["query"] == "hello"

    @pytest.mark.asyncio
    async def test_get_search_missing_q(self, app_and_rag):
        app, _ = app_and_rag
        async with _make_client(app) as tc:
            resp = await tc.get("/api/v1/ledger/search")
        assert resp.status_code == 422  # validation error


# ===========================================================================
# POST /api/v1/ledger/index
# ===========================================================================


class TestIndexLedger:

    @pytest.mark.asyncio
    async def test_index_success(self, app_and_rag):
        app, rag = app_and_rag
        rag.index_ledger = AsyncMock(return_value=True)

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/index")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["indexed"] is True

    @pytest.mark.asyncio
    async def test_index_force(self, app_and_rag):
        app, rag = app_and_rag
        rag.index_ledger = AsyncMock(return_value=True)

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/index", params={"force": True})
        assert resp.status_code == 200
        rag.index_ledger.assert_awaited_once_with(force=True)

    @pytest.mark.asyncio
    async def test_index_failure(self, app_and_rag):
        app, rag = app_and_rag
        rag.index_ledger = AsyncMock(return_value=False)

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/index")
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_index_exception(self, app_and_rag):
        app, rag = app_and_rag
        rag.index_ledger = AsyncMock(side_effect=RuntimeError("disk full"))

        async with _make_client(app) as tc:
            resp = await tc.post("/api/v1/ledger/index")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"


# ===========================================================================
# GET /api/v1/ledger/status
# ===========================================================================


class TestLedgerStatus:

    @pytest.mark.asyncio
    async def test_status(self, app_and_rag):
        app, rag = app_and_rag
        async with _make_client(app) as tc:
            resp = await tc.get("/api/v1/ledger/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "indexed" in body
        assert "continuity_file" in body
        assert "file_exists" in body

    @pytest.mark.asyncio
    async def test_status_error(self, app_and_rag):
        app, rag = app_and_rag
        rag.is_indexed.side_effect = RuntimeError("broken")

        async with _make_client(app) as tc:
            resp = await tc.get("/api/v1/ledger/status")
        assert resp.status_code == 500
