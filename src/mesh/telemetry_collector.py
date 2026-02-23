import asyncio
import logging
from datetime import datetime
from src.network.yggdrasil_client import get_yggdrasil_peers, get_yggdrasil_status
from src.mesh.yggdrasil_optimizer import get_optimizer, RouteMetrics

logger = logging.getLogger(__name__)

class MeshTelemetryCollector:
    """
    Bridge between raw Yggdrasil data and the YggdrasilOptimizer.
    Periodically polls yggdrasilctl and updates route metrics.
    """
    
    def __init__(self, interval_seconds: int = 15):
        self.interval = interval_seconds
        self.optimizer = get_optimizer()
        self._running = False

    async def start(self):
        self._running = True
        logger.info(f"📡 Mesh Telemetry Collector started (Interval: {self.interval}s)")
        while self._running:
            try:
                await self._collect_once()
            except Exception as e:
                logger.error(f"Telemetry collection error: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False

    async def _collect_once(self):
        # 1. Get peers from Yggdrasil
        peers_data = get_yggdrasil_peers()
        if peers_data.get("status") != "ok":
            return

        for peer in peers_data.get("peers", []):
            peer_id = peer.get("remote")
            if not peer_id: continue
            
            # 2. Register/Update route in optimizer
            # Note: We use peer_id as both destination and next_hop for direct peers
            route_id = f"direct-{peer_id}"
            
            # In a real system, we'd fetch latency/loss per peer
            # For now, we simulate or fetch from a ping utility
            # For this MVP, let's assume 50ms as a baseline if not known
            latency = 50.0 
            
            self.optimizer.update_route_metrics(
                route_id=route_id,
                latency_ms=latency,
                packet_loss=0.0 # To be updated with real stats
            )
            
            # If new, register it
            if route_id not in self.optimizer._routes:
                self.optimizer.register_route(RouteMetrics(
                    route_id=route_id,
                    destination=peer_id,
                    next_hop=peer_id,
                    latency_ms=latency
                ))

        # 3. Trigger optimization cycle
        report = self.optimizer.optimize_routes()
        if report.get("recommendations"):
            logger.info(f"📍 Mesh Optimizer: {len(report['recommendations'])} recommendations generated.")

mesh_telemetry_collector = MeshTelemetryCollector()
