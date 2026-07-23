"""
Statistics tracking for Mesh Router.

Provides thread-safe statistics tracking and MAPE-K metrics calculation.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict


logger = logging.getLogger(__name__)


@dataclass
class RouterStats:
    """Router statistics counters."""
    
    packets_sent: int = 0
    packets_received: int = 0
    packets_forwarded: int = 0
    packets_dropped: int = 0
    rreq_sent: int = 0
    rreq_received: int = 0
    rrep_sent: int = 0
    rrep_received: int = 0
    routes_discovered: int = 0


class RouterStatistics:
    """
    Thread-safe statistics tracking for mesh router.
    
    Tracks packet counts and calculates MAPE-K metrics for
    monitoring and adaptive behavior.
    
    Example:
        >>> stats = RouterStatistics()
        >>> await stats.increment("packets_sent")
        >>> metrics = await stats.get_mape_k_metrics(get_routes_func)
    """

    def __init__(self):
        """Initialize statistics tracker."""
        self._stats = RouterStats()
        self._lock = asyncio.Lock()

    async def increment(self, counter: str, amount: int = 1) -> None:
        """
        Increment a counter.
        
        Args:
            counter: Name of the counter to increment
            amount: Amount to increment by (default 1)
        """
        async with self._lock:
            if hasattr(self._stats, counter):
                current = getattr(self._stats, counter)
                setattr(self._stats, counter, current + amount)

    async def get_stats(self) -> Dict[str, int]:
        """
        Get current statistics.
        
        Returns:
            Dictionary of counter name -> value
        """
        async with self._lock:
            return {
                "packets_sent": self._stats.packets_sent,
                "packets_received": self._stats.packets_received,
                "packets_forwarded": self._stats.packets_forwarded,
                "packets_dropped": self._stats.packets_dropped,
                "rreq_sent": self._stats.rreq_sent,
                "rreq_received": self._stats.rreq_received,
                "rrep_sent": self._stats.rrep_sent,
                "rrep_received": self._stats.rrep_received,
                "routes_discovered": self._stats.routes_discovered,
            }

    async def get_mape_k_metrics(
        self,
        get_routes_func: Any,
    ) -> Dict[str, float]:
        """
        Calculate MAPE-K metrics for adaptive routing.
        
        Args:
            get_routes_func: Function that returns active routes dict
            
        Returns:
            Dictionary of metric name -> value
        """
        current_stats = await self.get_stats()

        metrics: Dict[str, float] = {}

        # 1. Packet Drop Rate
        total_packets_involved = (
            current_stats["packets_sent"]
            + current_stats["packets_received"]
            + current_stats["packets_forwarded"]
            + current_stats["rreq_sent"]
            + current_stats["rreq_received"]
            + current_stats["rrep_sent"]
            + current_stats["rrep_received"]
        )
        if total_packets_involved > 0:
            metrics["packet_drop_rate"] = (
                current_stats["packets_dropped"] / total_packets_involved
            )
        else:
            metrics["packet_drop_rate"] = 0.0

        # 2. Route Discovery Success Rate
        if current_stats["rreq_sent"] > 0:
            metrics["route_discovery_success_rate"] = (
                current_stats["routes_discovered"] / current_stats["rreq_sent"]
            )
        else:
            metrics["route_discovery_success_rate"] = 0.0

        # 3. Total Routes Known
        active_routes_dict = get_routes_func()
        metrics["total_routes_known"] = float(len(active_routes_dict))

        # 4. Average Route Hop Count
        total_hops = 0
        num_routes_for_avg = 0
        for dest_routes in active_routes_dict.values():
            for route_entry in dest_routes:
                total_hops += route_entry.hop_count
                num_routes_for_avg += 1

        if num_routes_for_avg > 0:
            metrics["avg_route_hop_count"] = total_hops / num_routes_for_avg
        else:
            metrics["avg_route_hop_count"] = 0.0

        # 5. Routing Overhead Ratio
        total_routing_control_packets = (
            current_stats["rreq_sent"]
            + current_stats["rreq_received"]
            + current_stats["rrep_sent"]
            + current_stats["rrep_received"]
        )
        total_data_packets = (
            current_stats["packets_sent"] + current_stats["packets_forwarded"]
        )

        if total_data_packets > 0:
            metrics["routing_overhead_ratio"] = (
                total_routing_control_packets / total_data_packets
            )
        else:
            metrics["routing_overhead_ratio"] = 0.0

        return metrics

    async def reset(self) -> None:
        """Reset all counters to zero."""
        async with self._lock:
            self._stats = RouterStats()
            logger.info("Router statistics reset")


__all__ = ["RouterStatistics", "RouterStats"]

