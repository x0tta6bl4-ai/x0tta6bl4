"""
Unit tests for src/api/ledger_endpoints.py
Tests ledger search, index, and status endpoints.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
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
def client(mock_ledger_rag):
    """TestClient with mocked ledger RAG dependency."""
    with patch("src.api.ledger_endpoints.get_ledger_rag", return_value=mock_ledger_rag):
        from src.api.ledger_endpoints import router

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app), mock_ledger_rag


# ===========================================================================
# POST /api/v1/ledger/search
# ===========================================================================

class TestSearchLedgerPost:

    def test_search_success(self, client):
        tc, rag = client
        mock_result = MagicMock()
        mock_result.query = "test query"
        mock_result.results = [{"text": "result1", "score": 0.9}]
        mock_result.total_results = 1
        mock_result.search_time_ms = 12.5
        mock_result.metadata = {"source": "CONTINUITY.md"}
        rag.query = AsyncMock(return_value=mock_result)

        resp = tc.post("/api/v1/ledger/search", json={
            "query": "test query",
            "top_k": 5
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "test query"
        assert body["total_results"] == 1
        assert len(body["results"]) == 1
        assert pytest.approx(body["search_time_ms"], abs=0.1) == 12.5

    def test_search_auto_indexes(self, client):
        """If not indexed, should call index_ledger first."""
        tc, rag = client
        rag.is_indexed.return_value = False
        rag.index_ledger = AsyncMock(return_value=True)
        mock_result = MagicMock()
        mock_result.query = "q"
        mock_result.results = []
        mock_result.total_results = 0
        mock_result.search_time_ms = 5.0
        mock_result.metadata = {}
        rag.query = AsyncMock(return_value=mock_result)

        resp = tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 200
        rag.index_ledger.assert_awaited_once()

    def test_search_default_top_k(self, client):
        tc, rag = client
        mock_result = MagicMock()
        mock_result.query = "q"
        mock_result.results = []
        mock_result.total_results = 0
        mock_result.search_time_ms = 1.0
        mock_result.metadata = {}
        rag.query = AsyncMock(return_value=mock_result)

        resp = tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 200
        rag.query.assert_awaited_once_with("q", top_k=10)

    def test_search_error(self, client):
        tc, rag = client
        rag.query = AsyncMock(side_effect=RuntimeError("search failed"))

        resp = tc.post("/api/v1/ledger/search", json={"query": "q"})
        assert resp.status_code == 500
        assert "search failed" in resp.json()["detail"]


# ===========================================================================
# GET /api/v1/ledger/search
# ===========================================================================

class TestSearchLedgerGet:

    def test_get_search(self, client):
        tc, rag = client
        mock_result = MagicMock()
        mock_result.query = "hello"
        mock_result.results = []
        mock_result.total_results = 0
        mock_result.search_time_ms = 2.0
        mock_result.metadata = {}
        rag.query = AsyncMock(return_value=mock_result)

        resp = tc.get("/api/v1/ledger/search", params={"q": "hello", "top_k": 3})
        assert resp.status_code == 200
        assert resp.json()["query"] == "hello"

    def test_get_search_missing_q(self, client):
        tc, _ = client
        resp = tc.get("/api/v1/ledger/search")
        assert resp.status_code == 422  # validation error


# ===========================================================================
# POST /api/v1/ledger/index
# ===========================================================================

class TestIndexLedger:

    def test_index_success(self, client):
        tc, rag = client
        rag.index_ledger = AsyncMock(return_value=True)

        resp = tc.post("/api/v1/ledger/index")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["indexed"] is True

    def test_index_force(self, client):
        tc, rag = client
        rag.index_ledger = AsyncMock(return_value=True)

        resp = tc.post("/api/v1/ledger/index", params={"force": True})
        assert resp.status_code == 200
        rag.index_ledger.assert_awaited_once_with(force=True)

    def test_index_failure(self, client):
        tc, rag = client
        rag.index_ledger = AsyncMock(return_value=False)

        resp = tc.post("/api/v1/ledger/index")
        assert resp.status_code == 500

    def test_index_exception(self, client):
        tc, rag = client
        rag.index_ledger = AsyncMock(side_effect=RuntimeError("disk full"))

        resp = tc.post("/api/v1/ledger/index")
        assert resp.status_code == 500
        assert "disk full" in resp.json()["detail"]


# ===========================================================================
# GET /api/v1/ledger/status
# ===========================================================================

class TestLedgerStatus:

    def test_status(self, client):
        tc, rag = client
        resp = tc.get("/api/v1/ledger/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "indexed" in body
        assert "continuity_file" in body
        assert "file_exists" in body

    def test_status_error(self, client):
        tc, rag = client
        rag.is_indexed.side_effect = RuntimeError("broken")

        resp = tc.get("/api/v1/ledger/status")
        assert resp.status_code == 500
