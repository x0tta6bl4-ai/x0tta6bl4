import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.rag.chunker import DocumentChunk
from src.rag.pipeline import RAGResult
from src.core.app import app as fastapi_app

@pytest.fixture
def app():
    return fastapi_app

@pytest.fixture
def mock_ledger_rag(monkeypatch):
    mock = MagicMock()
    # Correct monkeypatch paths for modular architecture
    monkeypatch.setattr("src.ledger.rag_search.get_ledger_rag", lambda: mock)
    try:
        monkeypatch.setattr("src.api.ledger_endpoints.get_ledger_rag", lambda: mock)
    except (ImportError, ModuleNotFoundError):
        pass
    return mock

@pytest.mark.asyncio
async def test_print_routes(app):
    """Debug helper to print all registered routes."""
    for route in app.routes:
        if hasattr(route, "path"):
            print(f"ROUTE: {route.path} -> {route.name}")
    assert True

@pytest.mark.asyncio
async def test_ledger_status(app, mock_ledger_rag):
    # _safe_is_indexed calls it: returns bool(is_indexed())
    mock_ledger_rag.is_indexed.return_value = True

    # Also mock these helpers used in _ledger_readiness_status
    mock_ledger_rag.engine = MagicMock()
    mock_ledger_rag.file_path = "ledger.json"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ledger/status")
        assert response.status_code == 200
        data = response.json()
        assert data["indexed"] is True

@pytest.mark.asyncio
async def test_index_ledger(app, mock_ledger_rag):
    mock_ledger_rag.index_ledger = AsyncMock(return_value=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ledger/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

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
        assert data["results"][0]["text"] == "result1"

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
