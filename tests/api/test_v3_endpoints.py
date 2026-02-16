from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Mock the V3 components before they are imported by the endpoint module
from src.self_healing.mape_k_v3_integration import MAPEKV3Integration
from src.storage.immutable_audit_trail import ImmutableAuditTrail
from src.testing.digital_twins import ChaosScenario


@pytest.fixture
def mock_v3_integration():
    mock_integration = MagicMock(spec=MAPEKV3Integration)
    mock_integration.get_status.return_value = {
        "graphsage_available": True,
        "stego_mesh_available": True,
        "digital_twins_available": True,
        "components_loaded": {
            "graphsage": True,
            "stego_mesh": True,
            "digital_twins": True,
        },
    }
    return mock_integration


@pytest.fixture
def mock_audit_trail():
    mock_trail = MagicMock(spec=ImmutableAuditTrail)
    mock_trail.get_statistics.return_value = {"total_records": 0}
    return mock_trail


from fastapi import FastAPI


@pytest.fixture
def app(monkeypatch, mock_v3_integration, mock_audit_trail):
    import src.api.v3_endpoints as v3_endpoints

    monkeypatch.setattr(v3_endpoints, "V3_AVAILABLE", True)
    monkeypatch.setattr(v3_endpoints, "get_v3_integration", lambda: mock_v3_integration)
    monkeypatch.setattr(v3_endpoints, "get_audit_trail", lambda: mock_audit_trail)

    app = FastAPI()
    app.include_router(v3_endpoints.router)
    yield app


@pytest.mark.asyncio
async def test_get_v3_status(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v3/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["components"]["graphsage_available"] is True


@pytest.mark.asyncio
async def test_analyze_with_graphsage(app, mock_v3_integration):
    from src.ml.anomaly_models import AnomalyAnalysis, FailureType

    mock_analysis = AnomalyAnalysis(
        failure_type=FailureType.NODE_FAILURE,
        confidence=0.9,
        recommended_action="reboot",
        severity=0.8,
        affected_nodes=["node-1"],
    )
    mock_v3_integration.analyze_with_graphsage = AsyncMock(return_value=mock_analysis)

    request_data = {
        "node_features": {"node-1": {"cpu": 0.9}},
        "node_topology": {"node-1": ["node-2"]},
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v3/graphsage/analyze", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["failure_type"] == "node_failure"
        assert data["confidence"] == 0.9
        mock_v3_integration.analyze_with_graphsage.assert_called_once()
