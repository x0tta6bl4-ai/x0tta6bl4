import sys  # Import sys for sys.modules patching
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import \
    FastAPI  # Keep FastAPI import for type hinting or future use if needed
from httpx import ASGITransport, AsyncClient

# This global mock is crucial to prevent prometheus_client from being imported and registering metrics
# before any test can run, solving the "Duplicated timeseries" error.
# It needs to be outside any fixture to affect module imports.


# --- Fixtures ---
@pytest_asyncio.fixture(name="client")
async def client_fixture(monkeypatch):  # Add monkeypatch for sys.modules
    """Create an asynchronous test client for the FastAPI app."""

    # 1. Patch sys.modules to prevent actual prometheus_client and graphsage_observe_mode imports
    mock_prometheus_client = MagicMock()
    mock_prometheus_client.Counter.return_value = (
        MagicMock()
    )  # Ensure calls to Counter() return a mock Counter instance

    mock_graphsage_observe_mode = MagicMock()

    # The actual patching must happen before the target modules are imported.
    # We set these in sys.modules so when demo_api imports them, it gets our mocks.
    monkeypatch.setitem(sys.modules, "prometheus_client", mock_prometheus_client)
    monkeypatch.setitem(
        sys.modules, "src.ml.graphsage_observe_mode", mock_graphsage_observe_mode
    )

    # 2. Import the actual FastAPI app instance from src.core.demo_api
    # This import must happen *after* the sys.modules patches are in place.
    from src.core.demo_api import app as demo_api_app
    from src.core.demo_api import \
        get_integrated_cycle_dependency  # Import the dependency
    # Import EBPFEvent, EBPFEventType from their source now that demo_api.py has delayed their import
    from src.network.ebpf.explainer import EBPFEvent, EBPFEventType

    # 3. Use dependency overrides to inject a mock IntegratedMAPEKCycle
    mock_mapek_cycle = MagicMock()

    # Configure the mock instance with expected return values for methods called by demo_api.py
    mock_mapek_cycle.get_system_status.return_value = {
        "status": "mock_operational",
        "mape_k_status": "mock_running",
        "chaos_engineering": {"enabled": True, "status": "active"},
        "graphsage_observe": {"enabled": True, "status": "monitoring"},
    }
    mock_mapek_cycle.run_cycle.return_value = {
        "anomaly_result": "mock_detected_successfully"
    }
    mock_mapek_cycle.run_chaos_experiment.return_value = {
        "chaos_result": "mock_executed_successfully"
    }

    # Mock for observe_detector
    mock_mapek_cycle.observe_detector = MagicMock()
    mock_mapek_cycle.observe_detector.get_stats.return_value = {
        "observe_stats": "mock_data"
    }

    # Mock for chaos_controller
    mock_mapek_cycle.chaos_controller = MagicMock()
    mock_mapek_cycle.chaos_controller.get_recovery_stats.return_value = {
        "chaos_stats": "mock_data"
    }

    # Mock for ebpf_explainer
    mock_mapek_cycle.ebpf_explainer = MagicMock()
    mock_mapek_cycle.ebpf_explainer.explain_event.return_value = (
        "mock_explanation_string"
    )

    # Override the dependency
    demo_api_app.dependency_overrides[get_integrated_cycle_dependency] = (
        lambda: mock_mapek_cycle
    )

    # Patch EBPFEvent and EBPFEventType for the actual EBPFEvent calls in demo_api.py
    # These patches need to be active during the test run, so they are applied globally
    # via monkeypatch.
    # Note: EBPFEvent and EBPFEventType are now imported from src.network.ebpf.explainer in demo_api.py
    monkeypatch.setattr(
        "src.network.ebpf.explainer.EBPFEvent",
        MagicMock(return_value=MagicMock(human_readable="mock_human_readable_output")),
    )
    monkeypatch.setattr("src.network.ebpf.explainer.EBPFEventType", MagicMock())

    async with AsyncClient(
        transport=ASGITransport(app=demo_api_app), base_url="http://test"
    ) as ac:
        yield ac

    demo_api_app.dependency_overrides = {}  # Clear overrides after test


# Removed the mock_integrated_mapek_cycle fixture as it's now handled via dependency injection


# --- Tests ---
@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test the root endpoint."""
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
async def test_get_api_status(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle as it's injected
    """Test the /api/status endpoint."""
    response = await client.get("/api/status")
    assert response.status_code == 200
    # The actual mock_mapek_cycle is now part of the client_fixture's scope.
    # We need to access the mock from the overridden dependency.
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = (
        get_integrated_cycle_dependency()
    )  # Get the mock used in the override
    assert response.json() == mock_mapek_cycle.get_system_status.return_value
    mock_mapek_cycle.get_system_status.assert_called_once()


@pytest.mark.asyncio
async def test_demo_anomaly_detection(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test the /api/demo/anomaly endpoint."""
    metrics = {
        "node_id": "node-001",
        "cpu_percent": 95.0,
        "memory_percent": 87.0,
        "packet_loss_percent": 7.0,
        "latency_ms": 150.0,
    }
    response = await client.post("/api/demo/anomaly", json=metrics)
    assert response.status_code == 200
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    assert response.json() == mock_mapek_cycle.run_cycle.return_value
    mock_mapek_cycle.run_cycle.assert_called_once_with(metrics)


@pytest.mark.asyncio
async def test_demo_anomaly_detection_error(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test error handling for /api/demo/anomaly endpoint."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.run_cycle.side_effect = Exception("Anomaly error")
    metrics = {"node_id": "node-001"}
    response = await client.post("/api/demo/anomaly", json=metrics)
    assert response.status_code == 500
    assert "Anomaly error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_demo_chaos_experiment(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test the /api/demo/chaos endpoint."""
    experiment = {"type": "node_failure", "duration": 10}
    response = await client.post("/api/demo/chaos", json=experiment)
    assert response.status_code == 200
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    assert response.json() == mock_mapek_cycle.run_chaos_experiment.return_value
    mock_mapek_cycle.run_chaos_experiment.assert_called_once_with(
        experiment.get("type"), experiment.get("duration")
    )


@pytest.mark.asyncio
async def test_demo_chaos_experiment_error(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test error handling for /api/demo/chaos endpoint."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.run_chaos_experiment.side_effect = Exception("Chaos error")
    experiment = {"type": "node_failure"}
    response = await client.post("/api/demo/chaos", json=experiment)
    assert response.status_code == 500
    assert "Chaos error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_observe_mode_stats(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test the /api/demo/observe-mode/stats endpoint."""
    response = await client.get("/api/demo/observe-mode/stats")
    assert response.status_code == 200
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    assert response.json() == mock_mapek_cycle.observe_detector.get_stats.return_value
    mock_mapek_cycle.observe_detector.get_stats.assert_called_once()


@pytest.mark.asyncio
async def test_get_observe_mode_stats_not_enabled(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test /api/demo/observe-mode/stats when observe_detector is not enabled."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.observe_detector = None  # Simulate not enabled
    response = await client.get("/api/demo/observe-mode/stats")
    assert response.status_code == 404
    assert "Observe Mode not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_chaos_stats(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test the /api/demo/chaos/stats endpoint."""
    response = await client.get("/api/demo/chaos/stats")
    assert response.status_code == 200
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    assert (
        response.json()
        == mock_mapek_cycle.chaos_controller.get_recovery_stats.return_value
    )
    mock_mapek_cycle.chaos_controller.get_recovery_stats.assert_called_once()


@pytest.mark.asyncio
async def test_get_chaos_stats_not_enabled(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test /api/demo/chaos/stats when chaos_controller is not enabled."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.chaos_controller = None  # Simulate not enabled
    response = await client.get("/api/demo/chaos/stats")
    assert response.status_code == 404
    assert "Chaos Controller not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_explain_ebpf_event(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test the /api/demo/explain/{event_type} endpoint."""
    event_type = "packet_drop"
    response = await client.get(f"/api/demo/explain/{event_type}")
    assert response.status_code == 200
    from src.core.demo_api import get_integrated_cycle_dependency

    # EBPFEvent and EBPFEventType are now imported within client_fixture, so access them via monkeypatch
    mock_mapek_cycle = get_integrated_cycle_dependency()
    assert response.json() == {
        "event_type": event_type,
        "explanation": mock_mapek_cycle.ebpf_explainer.explain_event.return_value,
        "human_readable": MagicMock().human_readable,  # EBPFEvent is mocked, get human_readable from it
    }
    # Assert that the explainer method was called with a correctly constructed EBPFEvent
    mock_mapek_cycle.ebpf_explainer.explain_event.assert_called_once_with(
        MagicMock(
            event_type=MagicMock(),
            timestamp=0.0,
            node_id="demo-node",
            program_id="demo-program",
            details={"demo": True},
        )
    )


@pytest.mark.asyncio
async def test_explain_ebpf_event_not_enabled(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test /api/demo/explain/{event_type} when ebpf_explainer is not enabled."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.ebpf_explainer = None  # Simulate not enabled
    response = await client.get("/api/demo/explain/packet_drop")
    assert response.status_code == 404
    assert "eBPF Explainer not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_explain_ebpf_event_error(
    client: AsyncClient,
):  # Removed mock_integrated_mapek_cycle
    """Test error handling for /api/demo/explain/{event_type} endpoint."""
    from src.core.demo_api import get_integrated_cycle_dependency

    mock_mapek_cycle = get_integrated_cycle_dependency()
    mock_mapek_cycle.ebpf_explainer.explain_event.side_effect = Exception(
        "eBPF explain error"
    )
    response = await client.get("/api/demo/explain/packet_drop")
    assert response.status_code == 500
    assert "eBPF explain error" in response.json()["detail"]
