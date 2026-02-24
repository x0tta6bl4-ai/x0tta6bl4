"""
Mesh-FL Integration Layer
=========================

Объединяет Batman-adv mesh network с Federated Learning для
распределённого обучения моделей с учётом топологии сети.

Функции:
- Интеграция TopologyAwareAggregator с Batman-adv
- Управление FL training rounds на mesh сети
- Обработка node churn и connectivity changes
- Приоритизация узлов с лучшим connectivity

Usage:
    from src.federated_learning.mesh_fl_integration import (
        MeshFLIntegration,
        create_mesh_fl_integration,
    )

    integration = await create_mesh_fl_integration(
        mesh_router=router,
        node_id="node-001",
    )
    await integration.start()
    result = await integration.run_training_round()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .topology_aware_aggregator import (
    AggregationResult,
    BatmanAdvMetricsProvider,
    ModelUpdate,
    NodeConnectivity,
    TopologyAwareAggregator,
    create_topology_aware_aggregator,
)

logger = logging.getLogger(__name__)


@dataclass
class MeshFLConfig:
    """Configuration for Mesh-FL Integration."""
    
    # Aggregation settings
    min_participants: int = 2
    byzantine_robust: bool = True
    connectivity_timeout: float = 30.0
    churn_threshold: float = 0.3
    
    # Training settings
    num_rounds: int = 10
    round_timeout: float = 120.0
    min_round_interval: float = 5.0
    
    # Model settings
    model_version: str = "v1.0"
    enable_privacy: bool = True
    privacy_epsilon: float = 1.0
    
    # Batman-adv integration
    update_topology_interval: float = 10.0
    link_quality_threshold: float = 0.3  # Minimum TQ to participate


@dataclass
class TrainingRound:
    """Represents a single FL training round."""
    
    round_number: int
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    participants: List[str] = field(default_factory=list)
    updates: List[ModelUpdate] = field(default_factory=list)
    result: Optional[AggregationResult] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None


class MeshFLIntegration:
    """
    Интеграция Batman-adv mesh с Federated Learning.
    
    Features:
    - Topology-aware aggregation на основе Batman-adv TQ
    - Автоматическое обновление connectivity метрик
    - Устойчивость к node churn
    - Byzantine-robust aggregation
    
    Example:
        integration = MeshFLIntegration(
            mesh_router=batman_router,
            config=MeshFLConfig(min_participants=3),
        )
        await integration.start()
        
        # Register nodes
        integration.register_node("node-1", NodeConnectivity(...))
        
        # Run training
        result = await integration.run_training_round()
    """
    
    def __init__(
        self,
        mesh_router: Any = None,
        config: Optional[MeshFLConfig] = None,
        node_id: str = "coordinator",
    ):
        self.mesh_router = mesh_router
        self.config = config or MeshFLConfig()
        self.node_id = node_id
        
        # Components
        self._aggregator: Optional[TopologyAwareAggregator] = None
        self._metrics_provider: Optional[BatmanAdvMetricsProvider] = None
        
        # State
        self._running = False
        self._current_round: Optional[TrainingRound] = None
        self._rounds: List[TrainingRound] = []
        self._model_version = self.config.model_version
        
        # Background tasks
        self._topology_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._metrics = {
            "total_rounds": 0,
            "successful_rounds": 0,
            "failed_rounds": 0,
            "total_participants": 0,
            "avg_participation_rate": 0.0,
            "avg_round_duration": 0.0,
        }
        
        logger.info(
            f"MeshFLIntegration initialized "
            f"(node_id={node_id}, min_participants={self.config.min_participants})"
        )
    
    async def start(self) -> None:
        """Start Mesh-FL integration."""
        if self._running:
            logger.warning("Mesh-FL integration already running")
            return
        
        logger.info("🚀 Starting Mesh-FL Integration...")
        
        # Create aggregator with Batman-adv integration
        self._aggregator, self._metrics_provider = await create_topology_aware_aggregator(
            mesh_router=self.mesh_router,
            min_participants=self.config.min_participants,
            byzantine_robust=self.config.byzantine_robust,
        )
        
        self._running = True
        
        # Start topology update task
        if self._metrics_provider:
            self._topology_task = asyncio.create_task(
                self._topology_update_loop()
            )
        
        logger.info("✅ Mesh-FL Integration started")
    
    async def stop(self) -> None:
        """Stop Mesh-FL integration."""
        if not self._running:
            return
        
        logger.info("🛑 Stopping Mesh-FL Integration...")
        
        self._running = False
        
        # Cancel topology task
        if self._topology_task:
            self._topology_task.cancel()
            try:
                await self._topology_task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ Mesh-FL Integration stopped")
    
    def register_node(
        self,
        node_id: str,
        connectivity: Optional[NodeConnectivity] = None,
    ) -> None:
        """Register a node for FL participation."""
        if connectivity is None:
            connectivity = NodeConnectivity(node_id=node_id)
        
        self._aggregator.register_node(node_id, connectivity)
        logger.debug(f"Registered node {node_id} for FL")
    
    def unregister_node(self, node_id: str) -> None:
        """Unregister a node from FL participation."""
        self._aggregator.unregister_node(node_id)
        logger.debug(f"Unregistered node {node_id} from FL")
    
    def update_node_connectivity(
        self,
        node_id: str,
        link_quality: Optional[float] = None,
        latency_ms: Optional[float] = None,
        hop_count: Optional[int] = None,
    ) -> None:
        """Update connectivity info for a node."""
        kwargs = {}
        if link_quality is not None:
            kwargs["link_quality"] = link_quality
        if latency_ms is not None:
            kwargs["latency_ms"] = latency_ms
        if hop_count is not None:
            kwargs["hop_count"] = hop_count
        
        if kwargs:
            self._aggregator.update_connectivity(node_id, **kwargs)
    
    async def run_training_round(
        self,
        local_weights: Optional[Dict[str, np.ndarray]] = None,
        num_samples: int = 100,
    ) -> Optional[AggregationResult]:
        """
        Run a single FL training round.
        
        Args:
            local_weights: Local model weights to contribute
            num_samples: Number of local training samples
            
        Returns:
            AggregationResult or None if round failed
        """
        if not self._running or not self._aggregator:
            logger.error("Mesh-FL integration not running")
            return None
        
        round_number = self._metrics["total_rounds"] + 1
        
        # Create round object
        training_round = TrainingRound(round_number=round_number)
        self._current_round = training_round
        training_round.status = "running"
        
        logger.info(f"🔄 Starting FL training round {round_number}")
        
        try:
            # Get expected participants
            expected = self._aggregator.get_expected_participants(round_number)
            
            # Filter by link quality threshold
            eligible = [
                node_id for node_id in expected
                if self._get_node_link_quality(node_id) >= self.config.link_quality_threshold
            ]
            
            if len(eligible) < self.config.min_participants:
                logger.warning(
                    f"Insufficient eligible participants: "
                    f"{len(eligible)} < {self.config.min_participants} "
                    f"(link_quality_threshold={self.config.link_quality_threshold})"
                )
                training_round.status = "failed"
                training_round.error = "Insufficient eligible participants"
                self._metrics["failed_rounds"] += 1
                return None
            
            # Add local update if provided
            if local_weights is not None:
                local_update = ModelUpdate(
                    node_id=self.node_id,
                    round_number=round_number,
                    weights=local_weights,
                    num_samples=num_samples,
                )
                self._aggregator.add_update(local_update)
                training_round.updates.append(local_update)
            
            # Wait for updates from other nodes (simulated in this implementation)
            # In production, this would wait for actual network updates
            await asyncio.sleep(1.0)
            
            # Perform aggregation
            result = await self._aggregator.aggregate(
                round_number,
                timeout=self.config.round_timeout,
            )
            
            if result:
                training_round.result = result
                training_round.participants = result.participating_nodes
                training_round.status = "completed"
                training_round.completed_at = time.time()
                
                # Update metrics
                self._metrics["total_rounds"] += 1
                self._metrics["successful_rounds"] += 1
                self._metrics["total_participants"] += len(result.participating_nodes)
                
                duration = training_round.completed_at - training_round.started_at
                self._metrics["avg_round_duration"] = (
                    (self._metrics["avg_round_duration"] * (self._metrics["successful_rounds"] - 1) + duration)
                    / self._metrics["successful_rounds"]
                )
                
                logger.info(
                    f"✅ Round {round_number} completed: "
                    f"{len(result.participating_nodes)} participants, "
                    f"{duration:.2f}s duration"
                )
            else:
                training_round.status = "failed"
                training_round.error = "Aggregation returned no result"
                self._metrics["total_rounds"] += 1
                self._metrics["failed_rounds"] += 1
                logger.warning(f"⚠️ Round {round_number} failed: no result")
            
        except Exception as e:
            training_round.status = "failed"
            training_round.error = str(e)
            self._metrics["total_rounds"] += 1
            self._metrics["failed_rounds"] += 1
            logger.error(f"❌ Round {round_number} failed: {e}")
        
        finally:
            self._rounds.append(training_round)
            self._current_round = None
        
        return training_round.result
    
    async def run_training_session(
        self,
        num_rounds: Optional[int] = None,
        local_weights_provider: Optional[callable] = None,
    ) -> List[AggregationResult]:
        """
        Run multiple training rounds.
        
        Args:
            num_rounds: Number of rounds (default from config)
            local_weights_provider: Async function to get local weights per round
            
        Returns:
            List of successful AggregationResults
        """
        rounds = num_rounds or self.config.num_rounds
        results = []
        
        logger.info(f"🎯 Starting training session: {rounds} rounds")
        
        for i in range(rounds):
            # Get local weights if provider available
            local_weights = None
            if local_weights_provider:
                try:
                    local_weights = await local_weights_provider()
                except Exception as e:
                    logger.warning(f"Failed to get local weights: {e}")
            
            result = await self.run_training_round(local_weights=local_weights)
            if result:
                results.append(result)
            
            # Wait between rounds
            if i < rounds - 1:
                await asyncio.sleep(self.config.min_round_interval)
        
        logger.info(
            f"🏁 Training session complete: "
            f"{len(results)}/{rounds} successful rounds"
        )
        
        return results
    
    def _get_node_link_quality(self, node_id: str) -> float:
        """Get link quality for a node."""
        node_status = self._aggregator.get_node_status()
        if node_id in node_status:
            return node_status[node_id].get("link_quality", 0.0)
        return 0.0
    
    async def _topology_update_loop(self) -> None:
        """Background task to update topology from Batman-adv."""
        while self._running:
            try:
                if self._metrics_provider and self._aggregator:
                    updated = await self._metrics_provider.update_all(self._aggregator)
                    if updated > 0:
                        logger.debug(f"Updated connectivity for {updated} nodes")
            except Exception as e:
                logger.warning(f"Topology update failed: {e}")
            
            await asyncio.sleep(self.config.update_topology_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            "running": self._running,
            "node_id": self.node_id,
            "model_version": self._model_version,
            "current_round": (
                self._current_round.round_number if self._current_round else None
            ),
            "metrics": self._metrics,
            "aggregator_metrics": (
                self._aggregator.get_metrics() if self._aggregator else {}
            ),
            "node_count": (
                len(self._aggregator.get_node_status()) if self._aggregator else 0
            ),
        }
    
    def get_node_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered nodes."""
        if not self._aggregator:
            return {}
        return self._aggregator.get_node_status()
    
    def get_round_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of training rounds."""
        rounds = self._rounds[-limit:]
        return [
            {
                "round_number": r.round_number,
                "status": r.status,
                "participants": len(r.participants),
                "duration": (
                    r.completed_at - r.started_at if r.completed_at else None
                ),
                "error": r.error,
            }
            for r in rounds
        ]


async def create_mesh_fl_integration(
    mesh_router: Any = None,
    node_id: str = "coordinator",
    config: Optional[MeshFLConfig] = None,
) -> MeshFLIntegration:
    """
    Factory function to create Mesh-FL integration.
    
    Args:
        mesh_router: Batman-adv mesh router instance
        node_id: Node identifier
        config: Optional configuration
        
    Returns:
        Initialized MeshFLIntegration instance
    """
    integration = MeshFLIntegration(
        mesh_router=mesh_router,
        node_id=node_id,
        config=config,
    )
    await integration.start()
    return integration


# Integration with existing FL components
def integrate_with_fl_coordinator(
    mesh_fl: MeshFLIntegration,
    fl_coordinator: Any,
) -> None:
    """
    Integrate Mesh-FL with existing FL Coordinator.
    
    Args:
        mesh_fl: MeshFLIntegration instance
        fl_coordinator: Existing FederatedCoordinator instance
    """
    # Register existing FL nodes with mesh aggregator
    if hasattr(fl_coordinator, "nodes"):
        for node_id, node_info in fl_coordinator.nodes.items():
            connectivity = NodeConnectivity(
                node_id=node_id,
                link_quality=1.0,  # Default, will be updated by Batman-adv
            )
            mesh_fl.register_node(node_id, connectivity)
    
    logger.info(f"Integrated Mesh-FL with FL Coordinator ({len(fl_coordinator.nodes)} nodes)")
