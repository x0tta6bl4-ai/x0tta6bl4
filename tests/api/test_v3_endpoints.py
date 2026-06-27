import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Mock the V3 components before they are imported by the endpoint module
from src.self_healing.mape_k_v3_integration import MAPEKV3Integration
from src.storage.immutable_audit_trail import ImmutableAuditTrail


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
        assert data["dataplane_confirmed"] is False
        assert data["production_readiness_claim_allowed"] is False
        assert data["cross_plane_claim_gate"]["allowed"] is False
        assert "trust_finality" in data["cross_plane_claim_gate"]["requested_claim_ids"]
        assert "status=operational does not prove production readiness" in (
            data["claim_boundary"]
        )


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
        assert data["local_model_analysis_claim_allowed"] is True
        assert data["control_action_applied"] is False
        assert data["dataplane_confirmed"] is False
        assert data["production_readiness_claim_allowed"] is False
        assert "dataplane_delivery" in data["graphsage_claim_gate"]["blocked_claim_ids"]
        assert data["cross_plane_claim_gate"]["allowed"] is False
        assert "local model inference" in data["claim_boundary"]
        mock_v3_integration.analyze_with_graphsage.assert_called_once()


@pytest.mark.asyncio
async def test_encode_stego_packet_boundary(app, mock_v3_integration):
    mock_v3_integration.encode_packet_stego.return_value = b"enc"
    request_data = {
        "payload": base64.b64encode(b"hello").decode(),
        "protocol_mimic": "http",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v3/stego/encode", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["encoded_packet"] == base64.b64encode(b"enc").decode()
        assert data["local_transform_claim_allowed"] is True
        assert data["dataplane_confirmed"] is False
        assert data["external_dpi_bypass_confirmed"] is False
        assert data["production_readiness_claim_allowed"] is False
        assert "external_dpi_bypass" in data["stego_claim_gate"]["blocked_claim_ids"]
        assert "dpi_bypass" in data["cross_plane_claim_gate"]["requested_claim_ids"]
        assert data["cross_plane_claim_gate"]["allowed"] is False
        assert "local encode/decode transform results only" in data["claim_boundary"]
        mock_v3_integration.encode_packet_stego.assert_called_once()


@pytest.mark.asyncio
async def test_run_chaos_test_boundary(app, mock_v3_integration):
    mock_v3_integration.run_chaos_test = AsyncMock(return_value={"survived": True})
    request_data = {"scenario": "node_down", "intensity": 0.5, "duration": 10.0}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v3/chaos/run", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["survived"] is True
        assert data["local_simulation_claim_allowed"] is True
        assert data["control_action_applied"] is False
        assert data["dataplane_confirmed"] is False
        assert data["production_slo_confirmed"] is False
        assert data["production_readiness_claim_allowed"] is False
        assert "live_failover" in data["chaos_claim_gate"]["blocked_claim_ids"]
        assert data["cross_plane_claim_gate"]["allowed"] is False
        assert "local digital-twin simulation results only" in data["claim_boundary"]
        mock_v3_integration.run_chaos_test.assert_called_once()
