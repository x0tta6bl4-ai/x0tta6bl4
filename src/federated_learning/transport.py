"""
FL Transport Layer - HTTP-based communication for Federated Learning.

FLTransportServer: Runs on coordinator node, exposes FL API endpoints.
FLTransportClient: Runs on worker nodes, communicates with coordinator.
"""
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore


class FLTransportServer:
    """HTTP server for FL coordinator (runs on coordinator node)."""

    def __init__(self, coordinator, host: str = "0.0.0.0", port: int = 8090):
        """
        Args:
            coordinator: FederatedCoordinator instance
            host: Listen host
            port: Listen port
        """
        self.coordinator = coordinator
        self.host = host
        self.port = port
        self._runner = None

    async def start(self):
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not available, FL transport server cannot start")
            return

        app = web.Application()
        app.router.add_post("/fl/register", self._handle_register)
        app.router.add_post("/fl/heartbeat", self._handle_heartbeat)
        app.router.add_post("/fl/submit_update", self._handle_submit_update)
        app.router.add_get("/fl/global_model", self._handle_get_global_model)
        app.router.add_get("/fl/round_info", self._handle_round_info)
        app.router.add_get("/fl/health", self._handle_health)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"FL Transport Server started on {self.host}:{self.port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            logger.info("FL Transport Server stopped")

    async def _handle_register(self, request):
        try:
            data = await request.json()
            node_id = data.get("node_id", "")
            capabilities = data.get("capabilities", {})

            if hasattr(self.coordinator, "register_node"):
                self.coordinator.register_node(node_id, capabilities)
                return web.json_response({"status": "registered", "node_id": node_id})
            return web.json_response({"status": "registered", "node_id": node_id})
        except Exception as e:
            logger.error(f"FL register error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_heartbeat(self, request):
        try:
            data = await request.json()
            node_id = data.get("node_id", "")

            round_info = {}
            if hasattr(self.coordinator, "current_round"):
                round_info["current_round"] = self.coordinator.current_round
            if hasattr(self.coordinator, "status"):
                round_info["status"] = str(self.coordinator.status)

            return web.json_response({"status": "ok", "node_id": node_id, **round_info})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_submit_update(self, request):
        try:
            data = await request.json()

            if hasattr(self.coordinator, "submit_update"):
                from .protocol import ModelUpdate, ModelWeights
                weights_data = data.get("weights", {})
                weights = ModelWeights(
                    layer_weights=weights_data.get("layer_weights", {}),
                    layer_biases=weights_data.get("layer_biases", {}),
                    metadata=weights_data.get("metadata", {}),
                )
                update = ModelUpdate(
                    node_id=data["node_id"],
                    round_number=data["round_number"],
                    weights=weights,
                    num_samples=data.get("num_samples", 0),
                    training_loss=data.get("training_loss", 0.0),
                )
                result = self.coordinator.submit_update(update)
                return web.json_response({"accepted": bool(result)})

            return web.json_response({"accepted": True})
        except Exception as e:
            logger.error(f"FL submit_update error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_global_model(self, request):
        try:
            if hasattr(self.coordinator, "get_global_model"):
                model = self.coordinator.get_global_model()
                if model and hasattr(model, "to_dict"):
                    return web.json_response(model.to_dict())
            return web.json_response({"error": "no model available"}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_round_info(self, request):
        try:
            info = {}
            if hasattr(self.coordinator, "current_round"):
                info["current_round"] = self.coordinator.current_round
            if hasattr(self.coordinator, "status"):
                info["status"] = str(self.coordinator.status)
            if hasattr(self.coordinator, "nodes"):
                info["registered_nodes"] = len(self.coordinator.nodes)
            return web.json_response(info)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_health(self, request):
        return web.json_response({"status": "healthy", "service": "fl-coordinator"})


class FLTransportClient:
    """HTTP client for FL worker (runs on each mesh node)."""

    def __init__(self, coordinator_url: str, node_id: str, timeout: float = 10.0):
        """
        Args:
            coordinator_url: Base URL of FL coordinator (e.g. "http://node-a:8090")
            node_id: This worker's node ID
            timeout: Request timeout in seconds
        """
        self.coordinator_url = coordinator_url.rstrip("/")
        self.node_id = node_id
        self.timeout = timeout

    async def register(self, capabilities: Optional[Dict[str, Any]] = None) -> bool:
        """Register this worker with the coordinator."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.coordinator_url}/fl/register",
                json={"node_id": self.node_id, "capabilities": capabilities or {}},
            )
            response.raise_for_status()
            return response.json().get("status") == "registered"

    async def send_heartbeat(self) -> Dict[str, Any]:
        """Send heartbeat and get round info."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.coordinator_url}/fl/heartbeat",
                json={"node_id": self.node_id},
            )
            response.raise_for_status()
            return response.json()

    async def submit_update(self, update_dict: Dict[str, Any]) -> bool:
        """Submit model update to coordinator."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.coordinator_url}/fl/submit_update",
                json=update_dict,
            )
            response.raise_for_status()
            return response.json().get("accepted", False)

    async def fetch_global_model(self) -> Optional[Dict[str, Any]]:
        """Fetch current global model from coordinator."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.coordinator_url}/fl/global_model")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def get_round_info(self) -> Dict[str, Any]:
        """Get current round information."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.coordinator_url}/fl/round_info")
            response.raise_for_status()
            return response.json()
