from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.ledger.rag_search import LedgerRAGSearch
from src.rag.chunker import DocumentChunk
from src.rag.pipeline import RAGResult


@pytest.fixture
def mock_ledger_rag():
    mock_rag = MagicMock(spec=LedgerRAGSearch)
    mock_rag.is_indexed.return_value = True

    file_mock = MagicMock()
    file_mock.exists.return_value = True
    file_mock.__str__.return_value = "/path/to/ledger.md"

    mock_rag.continuity_file = file_mock
    return mock_rag


@pytest.fixture
def app(monkeypatch, mock_ledger_rag):
    from src.core.app import app

    monkeypatch.setattr(
        "src.api.ledger_endpoints.get_ledger_rag", lambda: mock_ledger_rag
    )

    yield app


@pytest.mark.asyncio
async def test_ledger_status(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ledger/status")
        assert response.status_code == 200
        data = response.json()
        assert data["indexed"] is True
        assert data["file_exists"] is True
        assert data["continuity_file"] == "/path/to/ledger.md"


@pytest.mark.asyncio
async def test_index_ledger(app, mock_ledger_rag):
    mock_ledger_rag.index_ledger = AsyncMock(return_value=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ledger/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_ledger_rag.index_ledger.assert_called_once_with(force=False)


@pytest.mark.asyncio
async def test_search_ledger_post(app, mock_ledger_rag):
    mock_chunk = DocumentChunk(
        text="result1",
        chunk_id="1",
        document_id="doc1",
        start_index=0,
        end_index=7,
        metadata={},
    )
    mock_query_result = RAGResult(
        query="test query",
        retrieved_chunks=[mock_chunk],
        scores=[0.9],
        context="result1",
        metadata={"engine": "test"},
        retrieval_time_ms=123.45,
    )
    mock_ledger_rag.query = AsyncMock(return_value=mock_query_result)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ledger/search", json={"query": "test query", "top_k": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["results"]) == 1
        # The result from the endpoint is a dict, not a DocumentChunk object
        assert data["results"][0]["text"] == "result1"
        mock_ledger_rag.query.assert_called_once_with("test query", top_k=1)


@pytest.mark.asyncio
async def test_search_ledger_get(app, mock_ledger_rag):
    mock_chunk = DocumentChunk(
        text="result1",
        chunk_id="1",
        document_id="doc1",
        start_index=0,
        end_index=7,
        metadata={},
    )
    mock_query_result = RAGResult(
        query="test query",
        retrieved_chunks=[mock_chunk],
        scores=[0.9],
        context="result1",
        metadata={"engine": "test"},
        retrieval_time_ms=54.32,
    )
    mock_ledger_rag.query = AsyncMock(return_value=mock_query_result)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ledger/search?q=test query&top_k=1")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["results"]) == 1
        assert data["results"][0]["text"] == "result1"
        mock_ledger_rag.query.assert_called_once_with("test query", top_k=1)
