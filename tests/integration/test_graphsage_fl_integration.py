"""
Integration tests for GraphSAGE Federated Learning.

Tests complete FL flow with GraphSAGE model.
"""

from typing import Dict, List
from unittest.mock import Mock, patch

import pytest

try:
    from src.federated_learning.graphsage_integration import (
        GraphSAGEDistributedTrainer, GraphSAGEFLConfig, GraphSAGEFLCoordinator)
    from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

    GRAPHSAGE_FL_AVAILABLE = True
except ImportError:
    GRAPHSAGE_FL_AVAILABLE = False
    GraphSAGEFLCoordinator = None
    GraphSAGEDistributedTrainer = None


@pytest.mark.skipif(
    not GRAPHSAGE_FL_AVAILABLE, reason="GraphSAGE FL integration not available"
)
class TestGraphSAGEFLCoordinator:
    """Tests for GraphSAGE FL Coordinator"""

    def test_coordinator_initialization(self):
        """Test coordinator initialization"""
        config = GraphSAGEFLConfig(enable_privacy=True, aggregation_method="graphsage")

        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1", fl_config=config)

        assert coordinator.node_id == "coordinator-1"
        assert coordinator.config.aggregation_method == "graphsage"
        assert coordinator.aggregator is not None

    def test_start_training_round(self):
        """Test starting training round"""
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1")

        # Start round
        round_info = coordinator.start_training_round()

        # Should succeed if GraphSAGE available
        if coordinator.graphsage:
            assert round_info is not None
            assert "round_number" in round_info

    def test_train_local(self):
        """Test local training"""
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1")

        if coordinator.graphsage:
            # Train locally
            update = coordinator.train_local(round_number=1)

            # Should return update
            assert update is not None
            assert update.node_id == "coordinator-1"
            assert update.round_number == 1

    def test_aggregate_updates(self):
        """Test aggregating updates"""
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1")

        # Create updates
        from src.federated_learning.protocol import ModelUpdate, ModelWeights

        updates = []
        for i in range(3):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Aggregate
        global_model = coordinator.aggregate_updates(updates)

        # Should succeed
        assert global_model is not None
        assert global_model.version > 0

    def test_distribute_global_model(self):
        """Test distributing global model"""
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1")

        # Create global model
        from src.federated_learning.protocol import GlobalModel, ModelWeights

        weights = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        global_model = GlobalModel(
            version=1, round_number=1, weights=weights, num_contributors=3
        )

        # Distribute
        results = coordinator.distribute_global_model(
            global_model, target_nodes=["node-1", "node-2", "node-3"]
        )

        # All should succeed
        assert len(results) == 3
        assert all(results.values())


@pytest.mark.skipif(
    not GRAPHSAGE_FL_AVAILABLE, reason="GraphSAGE FL integration not available"
)
class TestGraphSAGEDistributedTrainer:
    """Tests for GraphSAGE Distributed Trainer"""

    def test_distributed_training(self):
        """Test distributed training across nodes"""
        config = GraphSAGEFLConfig()
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1", fl_config=config)

        trainer = GraphSAGEDistributedTrainer(coordinator=coordinator, num_rounds=3)

        # Run training
        participating_nodes = ["node-1", "node-2", "node-3"]
        results = trainer.train(participating_nodes)

        # Should complete
        assert results["total_rounds"] == 3
        assert results["completed_rounds"] > 0
        assert len(results["history"]) > 0

    def test_training_with_privacy(self):
        """Test training with privacy-preserving"""
        config = GraphSAGEFLConfig(
            enable_privacy=True, aggregation_method="secure_fedavg"
        )
        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1", fl_config=config)

        trainer = GraphSAGEDistributedTrainer(coordinator=coordinator, num_rounds=2)

        # Run training
        results = trainer.train(["node-1", "node-2"])

        # Should complete
        assert results["completed_rounds"] > 0


@pytest.mark.skipif(
    not GRAPHSAGE_FL_AVAILABLE, reason="GraphSAGE FL integration not available"
)
class TestGraphSAGEFLEndToEnd:
    """End-to-end tests for GraphSAGE FL"""

    def test_complete_training_cycle(self):
        """Test complete training cycle"""
        config = GraphSAGEFLConfig(
            enable_privacy=True,
            enable_byzantine_robust=True,
            aggregation_method="graphsage",
        )

        coordinator = GraphSAGEFLCoordinator(node_id="coordinator-1", fl_config=config)

        # Start round
        round_info = coordinator.start_training_round(["node-1", "node-2", "node-3"])
        if not round_info:
            pytest.skip("GraphSAGE not available")

        # Train locally
        updates = []
        for node_id in ["node-1", "node-2", "node-3"]:
            # Simulate local training
            update = coordinator.train_local(round_info["round_number"])
            if update:
                updates.append(update)

        # Aggregate
        global_model = coordinator.aggregate_updates(updates)

        # Should succeed
        assert global_model is not None

        # Distribute
        results = coordinator.distribute_global_model(
            global_model, ["node-1", "node-2", "node-3"]
        )

        # All should succeed
        assert all(results.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
