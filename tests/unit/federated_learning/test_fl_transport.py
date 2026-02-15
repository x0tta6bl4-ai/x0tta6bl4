"""Unit tests for FL Transport (client/server roundtrip)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from src.federated_learning.transport import (FLTransportClient,
                                              FLTransportServer)


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.current_round = 1
    coordinator.status = "waiting"
    coordinator.nodes = {"node-a": {}, "node-b": {}}
    coordinator.register_node = MagicMock()
    coordinator.submit_update = MagicMock(return_value=True)
    coordinator.get_global_model = MagicMock(return_value=None)
    return coordinator


class TestFLTransportServerInit:
    def test_init(self, mock_coordinator):
        server = FLTransportServer(mock_coordinator, host="127.0.0.1", port=9999)
        assert server.coordinator is mock_coordinator
        assert server.host == "127.0.0.1"
        assert server.port == 9999


class TestFLTransportClientInit:
    def test_init(self):
        client = FLTransportClient("http://localhost:8090", "worker-1")
        assert client.coordinator_url == "http://localhost:8090"
        assert client.node_id == "worker-1"

    def test_strips_trailing_slash(self):
        client = FLTransportClient("http://localhost:8090/", "worker-1")
        assert client.coordinator_url == "http://localhost:8090"


@pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not available")
class TestFLTransportRoundtrip:
    """Integration test: start server, connect client, verify roundtrip."""

    @pytest_asyncio.fixture
    async def server_and_client(self, mock_coordinator, monkeypatch):
        # Clear proxy env vars that interfere with local httpx requests
        for var in (
            "ALL_PROXY",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "all_proxy",
            "http_proxy",
            "https_proxy",
            "NO_PROXY",
            "no_proxy",
        ):
            monkeypatch.delenv(var, raising=False)
        """Start server on ephemeral port, create client."""
        server = FLTransportServer(mock_coordinator, host="127.0.0.1", port=0)
        # Use aiohttp test infrastructure for ephemeral port
        app = web.Application()
        app.router.add_post("/fl/register", server._handle_register)
        app.router.add_post("/fl/heartbeat", server._handle_heartbeat)
        app.router.add_post("/fl/submit_update", server._handle_submit_update)
        app.router.add_get("/fl/global_model", server._handle_get_global_model)
        app.router.add_get("/fl/round_info", server._handle_round_info)
        app.router.add_get("/fl/health", server._handle_health)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        try:
            await site.start()
        except OSError as exc:
            await runner.cleanup()
            pytest.skip(f"socket bind unavailable in test environment: {exc}")

        # Get actual port
        port = site._server.sockets[0].getsockname()[1]
        client = FLTransportClient(f"http://127.0.0.1:{port}", "worker-1")

        yield server, client, mock_coordinator

        await runner.cleanup()

    @pytest.mark.asyncio
    async def test_register(self, server_and_client):
        _, client, coordinator = server_and_client
        result = await client.register({"gpu": True})
        assert result is True
        coordinator.register_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat(self, server_and_client):
        _, client, _ = server_and_client
        result = await client.send_heartbeat()
        assert "status" in result
        assert result["node_id"] == "worker-1"

    @pytest.mark.asyncio
    async def test_round_info(self, server_and_client):
        _, client, _ = server_and_client
        info = await client.get_round_info()
        assert info["current_round"] == 1
        assert info["registered_nodes"] == 2

    @pytest.mark.asyncio
    async def test_global_model_not_found(self, server_and_client):
        _, client, _ = server_and_client
        model = await client.fetch_global_model()
        assert model is None

    @pytest.mark.asyncio
    async def test_submit_update(self, server_and_client):
        _, client, coordinator = server_and_client
        update = {
            "node_id": "worker-1",
            "round_number": 1,
            "weights": {"layer_weights": {}, "layer_biases": {}, "metadata": {}},
            "num_samples": 100,
            "training_loss": 0.5,
        }
        result = await client.submit_update(update)
        assert result is True
