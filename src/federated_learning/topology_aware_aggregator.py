"""
Topology-Aware Aggregator for Mesh-FL Integration
==================================================

Агрегатор, учитывающий топологию mesh-сети при агрегации обновлений модели.

Функции:
- Weight aggregation на основе link quality
- Prioritized updates от узлов с лучшим connectivity
- Устойчивость к node churn
- Интеграция с Batman-adv метриками
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class NodeConnectivity:
    """Connectivity information for a mesh node."""
    node_id: str
    link_quality: float = 1.0  # 0.0 - 1.0 (Batman-adv TQ)
    latency_ms: float = 0.0
    bandwidth_mbps: float = 100.0
    hop_count: int = 1
    last_updated: float = field(default_factory=time.time)
    
    def get_weight(self) -> float:
        """Calculate aggregation weight based on connectivity."""
        # Higher quality + lower latency + lower hops = higher weight
        latency_factor = 1.0 / (1.0 + self.latency_ms / 100.0)
        hop_factor = 1.0 / self.hop_count
        return self.link_quality * latency_factor * hop_factor


@dataclass
class ModelUpdate:
    """Model update from a worker node."""
    node_id: str
    round_number: int
    weights: Dict[str, np.ndarray]
    num_samples: int
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AggregationResult:
    """Result of model aggregation."""
    round_number: int
    aggregated_weights: Dict[str, np.ndarray]
    participating_nodes: List[str]
    total_samples: int
    aggregation_weights: Dict[str, float]
    metrics: Dict[str, Any] = field(default_factory=dict)


class TopologyAwareAggregator:
    """
    Агрегатор обновлений модели с учётом топологии mesh-сети.
    
    Features:
    - Weighted aggregation based on link quality
    - Byzantine-robust aggregation (coordinate-wise median)
    - Automatic handling of node churn
    - Integration with Batman-adv metrics
    
    Usage:
        aggregator = TopologyAwareAggregator()
        
        # Register nodes with connectivity info
        aggregator.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.9, latency_ms=10
        ))
        
        # Add updates
        aggregator.add_update(ModelUpdate(
            node_id="node-1", round_number=1, weights=..., num_samples=100
        ))
        
        # Aggregate
        result = await aggregator.aggregate(round_number=1)
    """
    
    def __init__(
        self,
        min_participants: int = 2,
        byzantine_robust: bool = True,
        connectivity_timeout: float = 30.0,
        churn_threshold: float = 0.3,  # 30% nodes can leave
    ):
        self.min_participants = min_participants
        self.byzantine_robust = byzantine_robust
        self.connectivity_timeout = connectivity_timeout
        self.churn_threshold = churn_threshold
        
        # Node registry
        self._nodes: Dict[str, NodeConnectivity] = {}
        
        # Pending updates per round
        self._updates: Dict[int, List[ModelUpdate]] = {}
        
        # Aggregation history
        self._history: List[AggregationResult] = []
        
        # Metrics
        self._metrics = {
            "total_aggregations": 0,
            "total_updates_processed": 0,
            "avg_participation": 0.0,
            "node_churn_events": 0,
        }
        
        logger.info(
            f"TopologyAwareAggregator initialized "
            f"(min_participants={min_participants}, byzantine_robust={byzantine_robust})"
        )
    
    def register_node(self, node_id: str, connectivity: NodeConnectivity) -> None:
        """Register a node with its connectivity information."""
        self._nodes[node_id] = connectivity
        logger.debug(f"Registered node {node_id}: link_quality={connectivity.link_quality:.2f}")
    
    def unregister_node(self, node_id: str) -> None:
        """Unregister a node (e.g., on disconnect)."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._metrics["node_churn_events"] += 1
            logger.info(f"Unregistered node {node_id} (churn event)")
    
    def update_connectivity(self, node_id: str, **kwargs) -> None:
        """Update connectivity info for a node."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            node.last_updated = time.time()
    
    def add_update(self, update: ModelUpdate) -> None:
        """Add a model update for aggregation."""
        if update.round_number not in self._updates:
            self._updates[update.round_number] = []
        self._updates[update.round_number].append(update)
        self._metrics["total_updates_processed"] += 1
    
    def get_expected_participants(self, round_number: int) -> List[str]:
        """Get list of expected participants for a round."""
        # Filter nodes with recent connectivity updates
        now = time.time()
        active_nodes = [
            node_id for node_id, conn in self._nodes.items()
            if now - conn.last_updated < self.connectivity_timeout
        ]
        return active_nodes
    
    async def aggregate(
        self,
        round_number: int,
        timeout: float = 60.0,
    ) -> Optional[AggregationResult]:
        """
        Aggregate updates for a round with topology-aware weighting.
        
        Args:
            round_number: The training round number
            timeout: Maximum time to wait for updates
            
        Returns:
            AggregationResult or None if insufficient participants
        """
        updates = self._updates.get(round_number, [])
        
        if len(updates) < self.min_participants:
            logger.warning(
                f"Insufficient participants for round {round_number}: "
                f"{len(updates)} < {self.min_participants}"
            )
            return None
        
        # Check for node churn
        expected = self.get_expected_participants(round_number)
        participating = [u.node_id for u in updates]
        churn_rate = 1.0 - len(set(participating) & set(expected)) / max(len(expected), 1)
        
        if churn_rate > self.churn_threshold:
            logger.warning(
                f"High churn rate detected: {churn_rate:.1%} > {self.churn_threshold:.1%}"
            )
        
        # Calculate aggregation weights
        weights = self._calculate_weights(updates)
        
        # Perform aggregation
        if self.byzantine_robust:
            aggregated = self._byzantine_robust_aggregate(updates, weights)
        else:
            aggregated = self._weighted_average(updates, weights)
        
        # Create result
        result = AggregationResult(
            round_number=round_number,
            aggregated_weights=aggregated,
            participating_nodes=participating,
            total_samples=sum(u.num_samples for u in updates),
            aggregation_weights=weights,
            metrics={
                "churn_rate": churn_rate,
                "participation_rate": len(participating) / max(len(expected), 1),
                "avg_link_quality": np.mean([
                    self._nodes[u.node_id].link_quality 
                    for u in updates if u.node_id in self._nodes
                ]),
            }
        )
        
        # Update metrics
        self._metrics["total_aggregations"] += 1
        self._metrics["avg_participation"] = (
            (self._metrics["avg_participation"] * (self._metrics["total_aggregations"] - 1) 
             + len(participating)) / self._metrics["total_aggregations"]
        )
        
        # Store history
        self._history.append(result)
        
        # Cleanup old updates
        if round_number in self._updates:
            del self._updates[round_number]
        
        logger.info(
            f"✅ Round {round_number} aggregated: "
            f"{len(participating)} nodes, {result.total_samples} samples, "
            f"avg_quality={result.metrics['avg_link_quality']:.2f}"
        )
        
        return result
    
    def _calculate_weights(self, updates: List[ModelUpdate]) -> Dict[str, float]:
        """Calculate aggregation weights based on topology and data."""
        weights = {}
        
        for update in updates:
            # Base weight from connectivity
            connectivity_weight = 1.0
            if update.node_id in self._nodes:
                connectivity_weight = self._nodes[update.node_id].get_weight()
            
            # Data weight (more samples = higher weight)
            data_weight = np.sqrt(update.num_samples)
            
            # Combined weight
            weights[update.node_id] = connectivity_weight * data_weight
        
        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _weighted_average(
        self,
        updates: List[ModelUpdate],
        weights: Dict[str, float],
    ) -> Dict[str, np.ndarray]:
        """Compute weighted average of updates."""
        aggregated = {}
        
        # Get all weight keys
        keys = set()
        for update in updates:
            keys.update(update.weights.keys())
        
        for key in keys:
            weighted_sum = None
            for update in updates:
                if key in update.weights:
                    w = weights.get(update.node_id, 0.0)
                    if weighted_sum is None:
                        weighted_sum = w * update.weights[key]
                    else:
                        weighted_sum = weighted_sum + w * update.weights[key]
            
            if weighted_sum is not None:
                aggregated[key] = weighted_sum
        
        return aggregated
    
    def _byzantine_robust_aggregate(
        self,
        updates: List[ModelUpdate],
        weights: Dict[str, float],
    ) -> Dict[str, np.ndarray]:
        """
        Byzantine-robust aggregation using coordinate-wise median
        with weighted fallback.
        """
        aggregated = {}
        
        # Get all weight keys
        keys = set()
        for update in updates:
            keys.update(update.weights.keys())
        
        for key in keys:
            values = []
            update_weights = []
            
            for update in updates:
                if key in update.weights:
                    values.append(update.weights[key])
                    update_weights.append(weights.get(update.node_id, 0.0))
            
            if len(values) >= 3:
                # Use coordinate-wise median for robustness
                stacked = np.stack(values)
                median = np.median(stacked, axis=0)
                
                # Weight the median with top-k values
                k = max(1, len(values) // 2)
                distances = [np.linalg.norm(v - median) for v in values]
                top_k_indices = np.argsort(distances)[:k]
                
                weighted_sum = None
                weight_sum = 0.0
                for idx in top_k_indices:
                    w = update_weights[idx]
                    if weighted_sum is None:
                        weighted_sum = w * values[idx]
                    else:
                        weighted_sum = weighted_sum + w * values[idx]
                    weight_sum += w
                
                if weight_sum > 0:
                    aggregated[key] = weighted_sum / weight_sum
                else:
                    aggregated[key] = median
            else:
                # Fall back to weighted average
                weighted_sum = None
                for i, v in enumerate(values):
                    w = update_weights[i]
                    if weighted_sum is None:
                        weighted_sum = w * v
                    else:
                        weighted_sum = weighted_sum + w * v
                aggregated[key] = weighted_sum
        
        return aggregated
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregator metrics."""
        return {
            **self._metrics,
            "active_nodes": len(self._nodes),
            "pending_rounds": len(self._updates),
            "history_size": len(self._history),
        }
    
    def get_node_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered nodes."""
        return {
            node_id: {
                "link_quality": conn.link_quality,
                "latency_ms": conn.latency_ms,
                "hop_count": conn.hop_count,
                "weight": conn.get_weight(),
                "last_updated": conn.last_updated,
            }
            for node_id, conn in self._nodes.items()
        }


class BatmanAdvMetricsProvider:
    """
    Provider for Batman-adv mesh metrics.
    
    Integrates with Batman-adv health monitor to provide
    real-time connectivity information.
    """
    
    def __init__(self, mesh_router: Any = None):
        self.mesh_router = mesh_router
        self._last_metrics: Dict[str, NodeConnectivity] = {}
    
    async def get_connectivity(self, node_id: str) -> Optional[NodeConnectivity]:
        """Get connectivity info for a node from Batman-adv."""
        if self.mesh_router is None:
            return None
        
        try:
            # Get originators (neighbors) from Batman-adv
            # This would integrate with actual Batman-adv API
            if hasattr(self.mesh_router, 'get_originators'):
                originators = await self.mesh_router.get_originators()
                for orig in originators:
                    if orig.get('node_id') == node_id or orig.get('address') == node_id:
                        return NodeConnectivity(
                            node_id=node_id,
                            link_quality=orig.get('tq', 1.0) / 255.0,  # Normalize TQ
                            latency_ms=orig.get('latency', 0.0),
                            hop_count=orig.get('hop_count', 1),
                        )
        except Exception as e:
            logger.warning(f"Failed to get Batman-adv metrics for {node_id}: {e}")
        
        return None
    
    async def update_all(self, aggregator: TopologyAwareAggregator) -> int:
        """Update connectivity info for all nodes."""
        updated = 0
        
        for node_id in list(aggregator._nodes.keys()):
            connectivity = await self.get_connectivity(node_id)
            if connectivity:
                aggregator.register_node(node_id, connectivity)
                updated += 1
        
        return updated


# Integration function
async def create_topology_aware_aggregator(
    mesh_router: Any = None,
    min_participants: int = 2,
    byzantine_robust: bool = True,
) -> Tuple[TopologyAwareAggregator, Optional[BatmanAdvMetricsProvider]]:
    """
    Create a topology-aware aggregator with optional Batman-adv integration.
    
    Args:
        mesh_router: Optional Batman-adv mesh router instance
        min_participants: Minimum participants for aggregation
        byzantine_robust: Enable Byzantine-robust aggregation
        
    Returns:
        Tuple of (aggregator, metrics_provider)
    """
    aggregator = TopologyAwareAggregator(
        min_participants=min_participants,
        byzantine_robust=byzantine_robust,
    )
    
    metrics_provider = None
    if mesh_router is not None:
        metrics_provider = BatmanAdvMetricsProvider(mesh_router)
    
    return aggregator, metrics_provider
