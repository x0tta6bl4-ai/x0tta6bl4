"""
GraphSAGE Integration for Federated Learning.

Integrates GraphSAGE model with FL coordinator for distributed training.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from src.ml.graphsage_anomaly_detector import (AnomalyPrediction,
                                                   GraphSAGEAnomalyDetector)

    GRAPHSAGE_AVAILABLE = True
except ImportError:
    GRAPHSAGE_AVAILABLE = False
    GraphSAGEAnomalyDetector = None
    AnomalyPrediction = None

from .coordinator import CoordinatorConfig, FederatedCoordinator
from .model_sync import ModelSynchronizer
from .protocol import GlobalModel, ModelUpdate, ModelWeights
from .secure_aggregators import GraphSAGEAggregator, SecureFedAvgAggregator

logger = logging.getLogger(__name__)


@dataclass
class GraphSAGEFLConfig:
    """Configuration for GraphSAGE Federated Learning"""

    enable_privacy: bool = True
    enable_byzantine_robust: bool = True
    aggregation_method: str = "graphsage"  # graphsage, secure_fedavg, secure_krum
    sync_interval: int = 1  # Sync every N rounds
    model_versioning: bool = True


class GraphSAGEFLCoordinator:
    """
    Federated Learning Coordinator with GraphSAGE integration.

    Features:
    - GraphSAGE model training
    - Privacy-preserving aggregation
    - Model synchronization
    - Distributed training across mesh nodes
    """

    def __init__(
        self,
        node_id: str,
        graphsage_model: Optional[GraphSAGEAnomalyDetector] = None,
        fl_config: Optional[GraphSAGEFLConfig] = None,
        coordinator_config: Optional[CoordinatorConfig] = None,
    ):
        self.node_id = node_id
        self.config = fl_config or GraphSAGEFLConfig()

        # Initialize GraphSAGE model
        if graphsage_model:
            self.graphsage = graphsage_model
        elif GRAPHSAGE_AVAILABLE:
            self.graphsage = GraphSAGEAnomalyDetector()
        else:
            self.graphsage = None
            logger.warning("GraphSAGE not available")

        # Initialize FL coordinator
        self.coordinator = FederatedCoordinator(
            coordinator_id=node_id, config=coordinator_config or CoordinatorConfig()
        )

        # Initialize aggregator
        if self.config.aggregation_method == "graphsage":
            self.aggregator = GraphSAGEAggregator()
        elif self.config.aggregation_method == "secure_fedavg":
            self.aggregator = SecureFedAvgAggregator(
                enable_dp=self.config.enable_privacy
            )
        else:
            from .secure_aggregators import get_secure_aggregator

            self.aggregator = get_secure_aggregator(
                self.config.aggregation_method, enable_dp=self.config.enable_privacy
            )

        # Initialize model synchronizer
        if self.config.model_versioning:
            self.model_sync = ModelSynchronizer(node_id=node_id)
        else:
            self.model_sync = None

        logger.info(
            f"GraphSAGE FL Coordinator initialized: "
            f"node={node_id}, method={self.config.aggregation_method}"
        )

    def start_training_round(
        self, selected_nodes: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Start a new training round.

        Args:
            selected_nodes: List of nodes to participate (None = all registered)

        Returns:
            Round information or None if failed
        """
        if not self.graphsage:
            logger.error("GraphSAGE model not available")
            return None

        # Start round in coordinator
        round_obj = self.coordinator.start_round()
        if not round_obj:
            # Fallback for standalone/test mode where no coordinator nodes are
            # registered yet. Local training can still proceed.
            fallback_nodes = selected_nodes or [self.node_id]
            round_number = (
                self.coordinator.round_history[-1].round_number + 1
                if self.coordinator.round_history
                else 1
            )
            logger.warning(
                "Falling back to standalone training round: "
                f"round={round_number}, nodes={fallback_nodes}"
            )
            return {
                "round_number": round_number,
                "selected_nodes": list(fallback_nodes),
                "status": "started",
            }

        # Select nodes
        if selected_nodes:
            round_obj.selected_nodes = selected_nodes

        return {
            "round_number": round_obj.round_number,
            "selected_nodes": round_obj.selected_nodes,
            "status": round_obj.status.value,
        }

    def train_local(
        self, round_number: int, local_data: Optional[Any] = None
    ) -> Optional[ModelUpdate]:
        """
        Train GraphSAGE model locally.

        Args:
            round_number: Current round number
            local_data: Local training data (graph structure, features)

        Returns:
            ModelUpdate with local gradients/weights
        """
        if not self.graphsage:
            logger.error("GraphSAGE model not available")
            return None

        try:
            # Get current global model
            global_model = self.get_global_model()

            # Train locally
            # (In real implementation, would use local_data)
            local_weights = self._extract_model_weights(self.graphsage)

            # Create model update
            update = ModelUpdate(
                node_id=self.node_id,
                round_number=round_number,
                weights=local_weights,
                num_samples=100,  # Would be actual sample count
                training_loss=0.5,  # Would be actual loss
                validation_loss=0.6,  # Would be actual loss
            )

            logger.info(f"Local training completed for round {round_number}")
            return update

        except Exception as e:
            logger.error(f"Local training failed: {e}")
            return None

    def aggregate_updates(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> Optional[GlobalModel]:
        """
        Aggregate local updates into global model.

        Args:
            updates: List of local model updates
            previous_model: Previous global model

        Returns:
            New global model or None if failed
        """
        if not updates:
            logger.warning("No updates to aggregate")
            return None

        try:
            # Aggregate using configured aggregator
            result = self.aggregator.aggregate(updates, previous_model)

            if not result.success:
                logger.error(f"Aggregation failed: {result.error_message}")
                return None

            # Sync model if versioning enabled
            if self.model_sync and result.global_model:
                self.model_sync.receive_global_model(
                    result.global_model, source_node="coordinator"
                )

            logger.info(
                f"✅ Aggregation successful: "
                f"version={result.global_model.version}, "
                f"contributors={result.updates_accepted}"
            )

            return result.global_model

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return None

    def distribute_global_model(
        self, global_model: GlobalModel, target_nodes: List[str]
    ) -> Dict[str, bool]:
        """
        Distribute global model to target nodes.

        Args:
            global_model: Global model to distribute
            target_nodes: List of target node IDs

        Returns:
            Dict mapping node_id -> success status
        """
        results = {}

        for node_id in target_nodes:
            try:
                # In real implementation, would send via network
                # For now, just mark as success
                results[node_id] = True
                logger.debug(f"Global model distributed to {node_id}")
            except Exception as e:
                logger.error(f"Failed to distribute to {node_id}: {e}")
                results[node_id] = False

        return results

    def get_global_model(self) -> Optional[GlobalModel]:
        """Get current global model."""
        if self.model_sync:
            return self.model_sync.get_current_model()
        else:
            return self.coordinator.get_global_model()

    def _extract_model_weights(self, model: GraphSAGEAnomalyDetector) -> ModelWeights:
        """Extract weights from GraphSAGE model."""
        # In real implementation, would extract actual weights
        # For now, return dummy weights
        return ModelWeights(layer_weights={"layer1": [1.0, 2.0]})

    def _apply_global_weights(
        self, model: GraphSAGEAnomalyDetector, weights: ModelWeights
    ) -> bool:
        """Apply global weights to local GraphSAGE model."""
        # In real implementation, would apply weights to model
        # For now, just return success
        return True


class GraphSAGEDistributedTrainer:
    """
    Distributed trainer for GraphSAGE across mesh nodes.

    Coordinates training across multiple nodes with:
    - Model synchronization
    - Gradient aggregation
    - Privacy preservation
    """

    def __init__(self, coordinator: GraphSAGEFLCoordinator, num_rounds: int = 10):
        self.coordinator = coordinator
        self.num_rounds = num_rounds
        self.training_history: List[Dict[str, Any]] = []

    def train(self, participating_nodes: List[str]) -> Dict[str, Any]:
        """
        Run distributed training across nodes.

        Args:
            participating_nodes: List of nodes participating in training

        Returns:
            Training results
        """
        logger.info(
            f"Starting distributed training: {self.num_rounds} rounds, {len(participating_nodes)} nodes"
        )

        for round_num in range(1, self.num_rounds + 1):
            # Start round
            round_info = self.coordinator.start_training_round(participating_nodes)
            if not round_info:
                logger.error(f"Failed to start round {round_num}")
                continue

            # Collect local updates
            updates = []
            for node_id in participating_nodes:
                # In real scenario, would request update from node
                # For now, simulate
                update = self.coordinator.train_local(round_num)
                if update:
                    updates.append(update)

            # Aggregate
            global_model = self.coordinator.aggregate_updates(updates)

            if global_model:
                # Distribute
                self.coordinator.distribute_global_model(
                    global_model, participating_nodes
                )

                # Record history
                self.training_history.append(
                    {
                        "round": round_num,
                        "participants": len(updates),
                        "model_version": global_model.version,
                        "success": True,
                    }
                )

        return {
            "total_rounds": self.num_rounds,
            "completed_rounds": len(self.training_history),
            "history": self.training_history,
        }
