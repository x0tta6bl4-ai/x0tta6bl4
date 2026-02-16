"""
MeshNetworkManager - aggregates mesh network metrics from real subsystems.

Provides statistics, route management, and healing operations for MAPE-K loop.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MeshNetworkManager:
    """
    Aggregates mesh network data from MeshRouter and Yggdrasil.

    Used by MAPEKLoop to monitor network health and trigger healing.
    """

    def __init__(self, node_id: str = "local"):
        self.node_id = node_id
        self._router = None  # lazy init
        self._healing_log: List[dict] = []
        self._route_preference: str = "balanced"

    def _get_router(self):
        """Lazy-init MeshRouter to avoid import-time side effects."""
        if self._router is None:
            try:
                from ..network.routing.mesh_router import MeshRouter

                self._router = MeshRouter(self.node_id)
                logger.info(f"MeshRouter initialized for node {self.node_id}")
            except Exception as e:
                logger.warning(f"MeshRouter unavailable: {e}")
        return self._router

    async def get_statistics(self) -> Dict[str, float]:
        """
        Collect real network statistics from subsystems.

        Returns keys expected by MAPEKLoop:
        - active_peers, avg_latency_ms, packet_loss_percent, mttr_minutes
        """
        stats: Dict[str, float] = {
            "active_peers": 0,
            "avg_latency_ms": 0.0,
            "packet_loss_percent": 0.0,
            "mttr_minutes": 0.0,
        }

        # MeshRouter metrics
        router = self._get_router()
        if router is not None:
            try:
                router_metrics = await router.get_mape_k_metrics()
                stats["packet_loss_percent"] = (
                    router_metrics.get("packet_drop_rate", 0) * 100
                )
                stats["active_peers"] = router_metrics.get("total_routes_known", 0)
                hop_count = router_metrics.get("avg_route_hop_count", 0)
                # Estimate latency from hop count (rough: ~15ms per hop)
                if hop_count > 0:
                    stats["avg_latency_ms"] = hop_count * 15.0
            except Exception as e:
                logger.debug(f"MeshRouter metrics unavailable: {e}")

        # Yggdrasil peer count (supplement)
        try:
            from ..network.yggdrasil_client import get_yggdrasil_peers

            peer_data = get_yggdrasil_peers()
            if peer_data and "count" in peer_data:
                ygg_count = peer_data["count"]
                stats["active_peers"] = max(stats["active_peers"], ygg_count)
        except Exception:
            pass

        # MTTR from healing log
        stats["mttr_minutes"] = self._compute_mttr()

        return stats

    async def set_route_preference(self, preference: str) -> bool:
        """
        Set route selection preference.

        Args:
            preference: One of 'low_latency', 'reliability', 'balanced'
        """
        valid = {"low_latency", "reliability", "balanced"}
        if preference not in valid:
            logger.warning(f"Invalid route preference: {preference}")
            return False
        self._route_preference = preference
        logger.info(f"Route preference set to {preference}")
        return True

    async def trigger_aggressive_healing(self) -> int:
        """
        Force route rediscovery for stale routes.

        Returns number of routes healed.
        """
        router = self._get_router()
        if router is None:
            return 0

        healed = 0
        start_time = time.time()
        try:
            active_routes = router.get_routes()
            for dest in list(active_routes.keys()):
                routes = active_routes[dest]
                stale = [r for r in routes if r.age > router.ROUTE_TIMEOUT * 0.8]
                for route in stale:
                    try:
                        await router._discover_route(dest)
                        healed += 1
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Aggressive healing failed: {e}")

        elapsed = (time.time() - start_time) / 60.0
        self._healing_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "healed": healed,
                "duration_minutes": elapsed,
            }
        )
        return healed

    async def trigger_preemptive_checks(self):
        """
        Proactively check route freshness for all known destinations.
        """
        router = self._get_router()
        if router is None:
            return

        try:
            active_routes = router.get_routes()
            for dest in list(active_routes.keys()):
                routes = active_routes[dest]
                # If best route is getting stale, start background discovery
                if routes and routes[0].age > router.ROUTE_TIMEOUT * 0.5:
                    try:
                        await router._discover_route(dest)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Preemptive check error: {e}")

    def _compute_mttr(self) -> float:
        """Compute mean time to repair from healing log (minutes)."""
        if not self._healing_log:
            return 0.0
        # Use last 10 entries
        recent = self._healing_log[-10:]
        durations = [
            entry["duration_minutes"] for entry in recent if entry["healed"] > 0
        ]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)
