"""
ML-based neighbor scoring for mesh network route selection.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mesh-neighbor-scorer"


class NeighborScorer:
    """Scores neighbors using ML-based reliability metrics."""

    def __init__(self, node_id: str, ml_enabled: bool = True):
        self.node_id = node_id
        self._ml_enabled = ml_enabled
        self._neighbor_stats: Dict[str, Dict[str, float]] = {}

    def ml_score_neighbor(
        self, neighbor_id: str, rssi: float, load: float, hops: int
    ) -> float:
        """
        Calculate reliability score for a neighbor using hybrid ML logic.

        Formula:
            score = delivery_prob * delay_factor
            where:
                delivery_prob = 0.95 if rssi > -70 else 0.70
                delivery_prob *= 0.5 if load > 0.8
                delay_factor = 1.0 / (hops * 15.0 + 1.0)

        Args:
            neighbor_id: Unique identifier for the neighbor node
            rssi: Received Signal Strength Indicator in dBm (typically -30 to -100)
            load: Current load on the neighbor (0.0 to 1.0)
            hops: Number of hops to reach this neighbor

        Returns:
            Reliability score between 0.0 and 1.0, higher is better
        """
        delivery_prob = 0.95 if rssi > -70 else 0.70
        if load > 0.8:
            delivery_prob *= 0.5

        delay_factor = 1.0 / (hops * 15.0 + 1.0)
        score = delivery_prob * delay_factor

        self._neighbor_stats[neighbor_id] = {
            "score": score,
            "last_rssi": rssi,
            "last_load": load,
            "timestamp": time.time(),
        }

        return score

    def select_best_neighbor(self, neighbors: List[Dict[str, Any]]) -> Optional[str]:
        """
        Select the best next hop based on ML scores.

        Args:
            neighbors: List of neighbor dictionaries, each containing:
                - id: Neighbor identifier
                - rssi: Signal strength (optional, default -100)
                - load: Current load (optional, default 0.0)
                - hops: Hop count (optional, default 1)

        Returns:
            Node ID of the best neighbor, or None if neighbors list is empty
        """
        if not neighbors:
            return None

        scored_neighbors: List[Tuple[str, float]] = []
        for n in neighbors:
            score = self.ml_score_neighbor(
                n["id"], n.get("rssi", -100), n.get("load", 0.0), n.get("hops", 1)
            )
            scored_neighbors.append((n["id"], score))

        return max(scored_neighbors, key=lambda x: x[1])[0]

    def get_neighbor_stats(self) -> Dict[str, Dict[str, float]]:
        """Get current neighbor scoring statistics."""
        return dict(self._neighbor_stats)

    def reset_stats(self) -> None:
        """Reset all neighbor statistics."""
        self._neighbor_stats.clear()
