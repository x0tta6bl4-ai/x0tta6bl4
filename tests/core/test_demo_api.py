import sys
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cycle():
    """Shared MagicMock for IntegratedMAPEKCycle."""
    m = MagicMock()
    m.get_system_status.return_value = {
        "status": "mock_operational",
        "mape_k_status": "mock_running",
        "chaos_engineering": {"enabled": True, "status": "active"},
        "graphsage_observe": {"enabled": True, "status": "monitoring"},
    }
    m.run_cycle.return_value = {"anomaly_result": "mock_detected_successfully"}
    m.run_chaos_experiment.return_value = {"chaos_result": "mock_executed_successfully"}
    m.observe_detector = MagicMock()
    m.observe_detector.get_stats.return_value = {"observe_stats": "mock_data"}
    m.chaos_controller = MagicMock()
    m.chaos_controller.get_recovery_stats.return_value = {"chaos_stats": "mock_data"}
    m.ebpf_explainer = MagicMock()
    m.ebpf_explainer.explain_event.return_value = "mock_explanation_string"
    return m


@pytest_asyncio.fixture(name="client")
async def client_fixture(monkeypatch, mock_cycle):
    """Async test client with mocked dependencies."""
    mock_prometheus = MagicMock()
    mock_prometheus.Counter.return_value = MagicMock()
    monkeypatch.setitem(sys.modules, "prometheus_client", mock_prometheus)
    monkeypatch.setitem(sys.modules, "src.ml.graphsage_observe_mode", MagicMock())

    from src.core.demo_api import app as demo_api_app
    from src.core.demo_api import get_integrated_cycle_dependency

    monkeypatch.setattr(
        "src.network.ebpf.explainer.EBPFEvent",
        MagicMock(return_value=MagicMock(human_readable="mock_human_readable_output")),
    )
    monkeypatch.setattr("src.network.ebpf.explainer.EBPFEventType", MagicMock())

    demo_api_app.dependency_overrides[get_integrated_cycle_dependency] = lambda: mock_cycle

    async with AsyncClient(
        transport=ASGITransport(app=demo_api_app), base_url="http://test"
    ) as ac:
        yield ac

    demo_api_app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "name": "x0tta6bl4",
        "version": "1.0.0",
        "status": "operational",
        "components": {
            "mape_k": "integrated",
            "graphsage_observe": "enabled",
            "chaos_engineering": "enabled",
            "ebpf_explainer": "enabled",
        },
    }


@pytest.mark.asyncio
async def test_get_api_status(client: AsyncClient, mock_cycle):
    response = await client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == mock_cycle.get_system_status.return_value
    mock_cycle.get_system_status.assert_called_once()


@pytest.mark.asyncio
async def test_demo_anomaly_detection(client: AsyncClient, mock_cycle):
    metrics = {
        "node_id": "node-001",
        "cpu_percent": 95.0,
        "memory_percent": 87.0,
        "packet_loss_percent": 7.0,
        "latency_ms": 150.0,
    }
    response = await client.post("/api/demo/anomaly", json=metrics)
    assert response.status_code == 200
    assert response.json() == mock_cycle.run_cycle.return_value
    mock_cycle.run_cycle.assert_called_once_with(metrics)


@pytest.mark.asyncio
async def test_demo_anomaly_detection_error(client: AsyncClient, mock_cycle):
    mock_cycle.run_cycle.side_effect = Exception("Anomaly error")
    response = await client.post("/api/demo/anomaly", json={"node_id": "node-001"})
    assert response.status_code == 500
    assert "Anomaly error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_demo_chaos_experiment(client: AsyncClient, mock_cycle):
    experiment = {"type": "node_failure", "duration": 10}
    response = await client.post("/api/demo/chaos", json=experiment)
    assert response.status_code == 200
    assert response.json() == mock_cycle.run_chaos_experiment.return_value
    mock_cycle.run_chaos_experiment.assert_called_once_with(
        experiment.get("type"), experiment.get("duration")
    )


@pytest.mark.asyncio
async def test_demo_chaos_experiment_error(client: AsyncClient, mock_cycle):
    mock_cycle.run_chaos_experiment.side_effect = Exception("Chaos error")
    response = await client.post("/api/demo/chaos", json={"type": "node_failure"})
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_observe_mode_stats(client: AsyncClient, mock_cycle):
    response = await client.get("/api/demo/observe-mode/stats")
    assert response.status_code == 200
    assert response.json() == mock_cycle.observe_detector.get_stats.return_value
    mock_cycle.observe_detector.get_stats.assert_called_once()


@pytest.mark.asyncio
async def test_get_observe_mode_stats_not_enabled(client: AsyncClient, mock_cycle):
    mock_cycle.observe_detector = None
    response = await client.get("/api/demo/observe-mode/stats")
    assert response.status_code == 404
    assert "Observe Mode not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_chaos_stats(client: AsyncClient, mock_cycle):
    response = await client.get("/api/demo/chaos/stats")
    assert response.status_code == 200
    assert response.json() == mock_cycle.chaos_controller.get_recovery_stats.return_value
    mock_cycle.chaos_controller.get_recovery_stats.assert_called_once()


@pytest.mark.asyncio
async def test_get_chaos_stats_not_enabled(client: AsyncClient, mock_cycle):
    mock_cycle.chaos_controller = None
    response = await client.get("/api/demo/chaos/stats")
    assert response.status_code == 404
    assert "Chaos Controller not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_explain_ebpf_event(client: AsyncClient, mock_cycle):
    event_type = "packet_drop"
    response = await client.get(f"/api/demo/explain/{event_type}")
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == event_type
    assert data["explanation"] == "mock_explanation_string"
    assert "human_readable" in data


@pytest.mark.asyncio
async def test_explain_ebpf_event_not_enabled(client: AsyncClient, mock_cycle):
    mock_cycle.ebpf_explainer = None
    response = await client.get("/api/demo/explain/packet_drop")
    assert response.status_code == 404
    assert "eBPF Explainer not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_explain_ebpf_event_error(client: AsyncClient, mock_cycle):
    mock_cycle.ebpf_explainer.explain_event.side_effect = Exception("eBPF explain error")
    response = await client.get("/api/demo/explain/packet_drop")
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
