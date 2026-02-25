"""Unit tests for MeshTelemetryCollector (telemetry_collector.py)."""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture(autouse=True)
def mock_deps():
    with patch("src.mesh.telemetry_collector.get_optimizer") as mock_opt, \
         patch("src.mesh.telemetry_collector.get_yggdrasil_peers") as mock_peers, \
         patch("src.mesh.telemetry_collector.get_yggdrasil_status") as mock_status:
        mock_opt.return_value = MagicMock(_routes={})
        mock_peers.return_value = {"status": "ok", "peers": []}
        mock_status.return_value = {}
        yield mock_opt, mock_peers, mock_status


class TestMeshTelemetryCollectorInit:
    def test_default_interval(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        assert c.interval == 15

    def test_custom_interval(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector(interval_seconds=30)
        assert c.interval == 30

    def test_not_running_on_init(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        assert c._running is False

    def test_stop_sets_running_false(self, mock_deps):
        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()
        c._running = True
        c.stop()
        assert c._running is False


class TestCollectOnce:
    def test_skips_when_peers_status_not_ok(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {"status": "error"}
        optimizer = mock_opt.return_value

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.get_event_loop().run_until_complete(c._collect_once())
        optimizer.update_route_metrics.assert_not_called()

    def test_updates_route_for_each_peer(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [
                {"remote": "tls://10.0.0.1:9000"},
                {"remote": "tls://10.0.0.2:9000"},
            ],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {}
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.get_event_loop().run_until_complete(c._collect_once())
        assert optimizer.update_route_metrics.call_count == 2

    def test_registers_new_routes(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": "tls://10.0.0.1:9000"}],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {}  # Empty — route is new
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.get_event_loop().run_until_complete(c._collect_once())
        optimizer.register_route.assert_called_once()

    def test_skips_peers_without_remote(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": None}, {"remote": ""}],
        }
        optimizer = mock_opt.return_value
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.get_event_loop().run_until_complete(c._collect_once())
        optimizer.update_route_metrics.assert_not_called()

    def test_existing_route_not_re_registered(self, mock_deps):
        mock_opt, mock_peers, _ = mock_deps
        mock_peers.return_value = {
            "status": "ok",
            "peers": [{"remote": "tls://10.0.0.1:9000"}],
        }
        optimizer = mock_opt.return_value
        optimizer._routes = {"direct-tls://10.0.0.1:9000": MagicMock()}
        optimizer.optimize_routes.return_value = {"recommendations": []}

        from src.mesh.telemetry_collector import MeshTelemetryCollector
        c = MeshTelemetryCollector()

        asyncio.get_event_loop().run_until_complete(c._collect_once())
        optimizer.register_route.assert_not_called()
