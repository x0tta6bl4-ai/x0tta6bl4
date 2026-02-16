from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.ledger.drift_detector import LedgerDriftDetector


@pytest.fixture
def mock_drift_detector():
    mock_detector = MagicMock(spec=LedgerDriftDetector)
    mock_detector._initialized = True
    mock_detector.anomaly_detector = True
    mock_detector.causal_engine = True

    file_mock = MagicMock()
    file_mock.exists.return_value = True
    file_mock.__str__.return_value = "/path/to/ledger.md"

    mock_detector.continuity_file = file_mock
    return mock_detector


@pytest.fixture
def app(monkeypatch, mock_drift_detector):
    from src.core.app import app

    monkeypatch.setattr(
        "src.api.ledger_drift_endpoints.get_drift_detector", lambda: mock_drift_detector
    )

    # The router is not included in the main app, so we need to include it for the test
    from src.api.ledger_drift_endpoints import router

    app.include_router(router)

    yield app


@pytest.mark.asyncio
async def test_drift_detector_status(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ledger/drift/status")
        assert response.status_code == 200
        data = response.json()
        assert data["initialized"] is True
        assert data["anomaly_detector_available"] is True
        assert data["causal_engine_available"] is True
        assert data["file_exists"] is True
        assert data["continuity_file"] == "/path/to/ledger.md"


@pytest.mark.asyncio
async def test_detect_drift(app, mock_drift_detector):
    mock_drift_result = {
        "timestamp": "2026-02-10T12:00:00Z",
        "total_drifts": 1,
        "code_drifts": 1,
        "metrics_drifts": 0,
        "doc_drifts": 0,
        "drifts": [{"type": "code", "details": "..."}],
        "graph": {"nodes": [], "edges": []},
        "status": "drifts_detected",
    }
    mock_drift_detector.detect_drift = AsyncMock(return_value=mock_drift_result)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ledger/drift/detect")
        assert response.status_code == 200
        data = response.json()
        assert data["total_drifts"] == 1
        assert data["status"] == "drifts_detected"
        mock_drift_detector.detect_drift.assert_called_once()
