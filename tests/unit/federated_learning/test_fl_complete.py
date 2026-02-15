"""
Comprehensive tests for Federated Learning module.
"""

import random
import sys
import time

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.federated_learning.aggregators import (FedAvgAggregator,
                                                KrumAggregator,
                                                MedianAggregator,
                                                TrimmedMeanAggregator,
                                                get_aggregator)
from src.federated_learning.coordinator import (CoordinatorConfig,
                                                FederatedCoordinator,
                                                NodeStatus, TrainingRound)
from src.federated_learning.protocol import (AggregationResult, FLMessage,
                                             FLMessageType, GlobalModel,
                                             ModelUpdate, ModelWeights,
                                             SignedMessage, generate_keypair)

# ==================== Protocol Tests ====================


class TestModelWeights:
    """Tests for ModelWeights."""

    def test_creation(self):
        weights = ModelWeights(
            layer_weights={"layer1": [1.0, 2.0, 3.0]}, layer_biases={"layer1": [0.1]}
        )
        assert len(weights.layer_weights["layer1"]) == 3

    def test_to_flat_vector(self):
        weights = ModelWeights(
            layer_weights={"layer1": [1.0, 2.0], "layer2": [3.0, 4.0]},
            layer_biases={"layer1": [0.1], "layer2": [0.2]},
        )
        flat = weights.to_flat_vector()
        # Sorted keys: layer1, layer2
        # layer1 weights + bias + layer2 weights + bias
        assert flat == [1.0, 2.0, 0.1, 3.0, 4.0, 0.2]

    def test_compute_hash(self):
        weights = ModelWeights(layer_weights={"flat": [1.0, 2.0, 3.0]})
        hash1 = weights.compute_hash()
        hash2 = weights.compute_hash()
        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 64  # SHA256 hex


class TestModelUpdate:
    """Tests for ModelUpdate."""

    def test_creation(self):
        weights = ModelWeights(layer_weights={"flat": [1.0]})
        update = ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=weights,
            num_samples=100,
            training_loss=0.5,
        )
        assert update.node_id == "node-1"
        assert update.num_samples == 100

    def test_to_dict_and_back(self):
        weights = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        update = ModelUpdate(
            node_id="node-1", round_number=5, weights=weights, num_samples=50
        )

        d = update.to_dict()
        restored = ModelUpdate.from_dict(d)

        assert restored.node_id == "node-1"
        assert restored.round_number == 5
        assert restored.num_samples == 50


class TestGlobalModel:
    """Tests for GlobalModel."""

    def test_creation(self):
        weights = ModelWeights(layer_weights={"flat": [1.0, 2.0]})
        model = GlobalModel(version=1, round_number=1, weights=weights)
        assert model.version == 1
        assert model.weights_hash != ""  # Auto-computed

    def test_hash_chain(self):
        weights1 = ModelWeights(layer_weights={"flat": [1.0]})
        model1 = GlobalModel(version=1, round_number=1, weights=weights1)

        weights2 = ModelWeights(layer_weights={"flat": [2.0]})
        model2 = GlobalModel(
            version=2,
            round_number=2,
            weights=weights2,
            previous_hash=model1.weights_hash,
        )

        assert model2.previous_hash == model1.weights_hash


class TestSignedMessage:
    """Tests for SignedMessage."""

    def test_create_and_sign(self):
        private_key, public_key = generate_keypair()

        msg = SignedMessage(
            message_id="msg-1",
            sender_id="node-1",
            message_type=FLMessageType.LOCAL_UPDATE,
            payload={"data": "test"},
        )

        msg.sign(private_key)
        assert len(msg.signature) > 0

    def test_serialize_deserialize(self):
        private_key, public_key = generate_keypair()

        msg = SignedMessage(
            message_id="msg-1",
            sender_id="node-1",
            message_type=FLMessageType.HEARTBEAT,
            payload={"status": "ok"},
        )
        msg.sign(private_key)

        serialized = msg.to_bytes()
        restored = SignedMessage.from_bytes(serialized)

        assert restored.message_id == "msg-1"
        assert restored.sender_id == "node-1"
        assert restored.payload == {"status": "ok"}


class TestFLMessage:
    """Tests for FLMessage convenience methods."""

    def test_round_start_message(self):
        weights = ModelWeights(layer_weights={"flat": [1.0]})
        model = GlobalModel(version=1, round_number=1, weights=weights)

        msg = FLMessage.round_start(round_number=1, global_model=model)

        assert msg.msg_type == FLMessageType.ROUND_START
        assert msg.content["round_number"] == 1

    def test_local_update_message(self):
        weights = ModelWeights(layer_weights={"flat": [1.0]})
        update = ModelUpdate(node_id="node-1", round_number=1, weights=weights)

        msg = FLMessage.local_update(update)

        assert msg.msg_type == FLMessageType.LOCAL_UPDATE
        assert msg.sender == "node-1"

    def test_error_message(self):
        msg = FLMessage.error("E001", "Test error", {"detail": "info"})

        assert msg.msg_type == FLMessageType.ERROR
        assert msg.content["error_code"] == "E001"


# ==================== Aggregator Tests ====================


def create_test_updates(n: int, dim: int = 10, add_byzantine: int = 0) -> list:
    """Create test model updates."""
    updates = []

    for i in range(n):
        # Normal updates cluster around similar values
        base_weights = [random.gauss(0, 0.1) for _ in range(dim)]

        weights = ModelWeights(layer_weights={"flat": base_weights})
        update = ModelUpdate(
            node_id=f"node-{i}",
            round_number=1,
            weights=weights,
            num_samples=random.randint(50, 200),
            training_loss=random.uniform(0.1, 0.5),
        )
        updates.append(update)

    # Add Byzantine updates (far from others)
    for i in range(add_byzantine):
        byzantine_weights = [random.gauss(10, 1) for _ in range(dim)]  # Far away
        weights = ModelWeights(layer_weights={"flat": byzantine_weights})
        update = ModelUpdate(
            node_id=f"byzantine-{i}", round_number=1, weights=weights, num_samples=100
        )
        updates.append(update)

    return updates


class TestFedAvgAggregator:
    """Tests for FedAvg aggregator."""

    def test_basic_aggregation(self):
        aggregator = FedAvgAggregator()
        updates = create_test_updates(5)

        result = aggregator.aggregate(updates)

        assert result.success
        assert result.global_model is not None
        assert result.updates_accepted == 5

    def test_empty_updates(self):
        aggregator = FedAvgAggregator()
        result = aggregator.aggregate([])

        assert not result.success
        assert "No updates" in result.error_message

    def test_weighted_by_samples(self):
        aggregator = FedAvgAggregator()

        # Node 1 has 900 samples with weights [10, 10]
        # Node 2 has 100 samples with weights [0, 0]
        # Weighted average should be close to [9, 9]

        update1 = ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=ModelWeights(layer_weights={"flat": [10.0, 10.0]}),
            num_samples=900,
        )
        update2 = ModelUpdate(
            node_id="node-2",
            round_number=1,
            weights=ModelWeights(layer_weights={"flat": [0.0, 0.0]}),
            num_samples=100,
        )

        result = aggregator.aggregate([update1, update2])

        assert result.success
        avg = result.global_model.weights.layer_weights["flat"]
        assert 8.5 < avg[0] < 9.5  # Close to 9


class TestKrumAggregator:
    """Tests for Krum aggregator."""

    def test_basic_aggregation(self):
        # Krum requires n >= 2f + 3, so with f=1, need n >= 5
        aggregator = KrumAggregator(f=1)
        updates = create_test_updates(6)

        result = aggregator.aggregate(updates)

        assert result.success
        assert result.global_model is not None

    def test_insufficient_nodes(self):
        aggregator = KrumAggregator(f=1)
        updates = create_test_updates(3)  # Need at least 5

        result = aggregator.aggregate(updates)

        assert not result.success
        assert "at least" in result.error_message

    def test_byzantine_detection(self):
        aggregator = KrumAggregator(f=2)

        # Create 7 normal updates and 2 Byzantine
        updates = create_test_updates(7, dim=10, add_byzantine=2)

        result = aggregator.aggregate(updates)

        assert result.success
        # Byzantine nodes should be in suspected list
        assert len(result.suspected_byzantine) >= 1

    def test_multi_krum(self):
        aggregator = KrumAggregator(f=1, multi_krum=True, m=3)
        updates = create_test_updates(6)

        result = aggregator.aggregate(updates)

        assert result.success
        assert result.updates_accepted == 3


class TestTrimmedMeanAggregator:
    """Tests for Trimmed Mean aggregator."""

    def test_basic_aggregation(self):
        aggregator = TrimmedMeanAggregator(beta=0.2)
        updates = create_test_updates(10)

        result = aggregator.aggregate(updates)

        assert result.success
        # Should trim 2 from each end (20% of 10)
        assert result.updates_accepted == 6

    def test_outlier_resistance(self):
        aggregator = TrimmedMeanAggregator(beta=0.2)

        # Normal updates at ~1.0, outliers at 100
        updates = []
        for i in range(8):
            weights = ModelWeights(layer_weights={"flat": [1.0]})
            updates.append(
                ModelUpdate(node_id=f"node-{i}", round_number=1, weights=weights)
            )

        # Add outliers
        for i in range(2):
            weights = ModelWeights(layer_weights={"flat": [100.0]})
            updates.append(
                ModelUpdate(node_id=f"outlier-{i}", round_number=1, weights=weights)
            )

        result = aggregator.aggregate(updates)

        assert result.success
        # Result should be close to 1.0, not affected by outliers
        avg = result.global_model.weights.layer_weights["flat"][0]
        assert avg < 10  # Much less than 100


class TestMedianAggregator:
    """Tests for Median aggregator."""

    def test_basic_aggregation(self):
        aggregator = MedianAggregator()
        updates = create_test_updates(5)

        result = aggregator.aggregate(updates)

        assert result.success
        assert result.updates_accepted == 5

    def test_median_value(self):
        aggregator = MedianAggregator()

        # Create updates with known values
        values = [1.0, 2.0, 100.0]  # Median should be 2.0
        updates = []
        for i, v in enumerate(values):
            weights = ModelWeights(layer_weights={"flat": [v]})
            updates.append(
                ModelUpdate(node_id=f"node-{i}", round_number=1, weights=weights)
            )

        result = aggregator.aggregate(updates)

        assert result.success
        median = result.global_model.weights.layer_weights["flat"][0]
        assert median == 2.0


class TestAggregatorFactory:
    """Tests for aggregator factory function."""

    def test_get_fedavg(self):
        agg = get_aggregator("fedavg")
        assert isinstance(agg, FedAvgAggregator)

    def test_get_krum(self):
        agg = get_aggregator("krum", f=2)
        assert isinstance(agg, KrumAggregator)

    def test_get_trimmed_mean(self):
        agg = get_aggregator("trimmed_mean", beta=0.15)
        assert isinstance(agg, TrimmedMeanAggregator)

    def test_unknown_aggregator(self):
        with pytest.raises(ValueError):
            get_aggregator("unknown")


# ==================== Coordinator Tests ====================


class TestFederatedCoordinator:
    """Tests for FederatedCoordinator."""

    def test_creation(self):
        coordinator = FederatedCoordinator("coord-1")
        assert coordinator.coordinator_id == "coord-1"

    def test_register_node(self):
        coordinator = FederatedCoordinator("coord-1")

        result = coordinator.register_node("node-1")
        assert result

        result = coordinator.register_node("node-1")  # Duplicate
        assert not result

    def test_unregister_node(self):
        coordinator = FederatedCoordinator("coord-1")
        coordinator.register_node("node-1")

        result = coordinator.unregister_node("node-1")
        assert result

        result = coordinator.unregister_node("node-1")  # Already removed
        assert not result

    def test_heartbeat(self):
        coordinator = FederatedCoordinator("coord-1")
        coordinator.register_node("node-1")

        coordinator.update_heartbeat("node-1", {"status": "ok"})

        assert coordinator.nodes["node-1"].last_heartbeat > 0

    def test_initialize_model(self):
        coordinator = FederatedCoordinator("coord-1")
        weights = ModelWeights(layer_weights={"flat": [1.0, 2.0]})

        model = coordinator.initialize_model(weights)

        assert model.version == 0
        assert coordinator.global_model is not None

    def test_get_eligible_nodes(self):
        config = CoordinatorConfig(min_trust_score=0.5)
        coordinator = FederatedCoordinator("coord-1", config)

        coordinator.register_node("node-1")
        coordinator.register_node("node-2")

        # Lower trust of node-2
        coordinator.nodes["node-2"].trust_score = 0.3

        eligible = coordinator.get_eligible_nodes()

        assert "node-1" in eligible
        assert "node-2" not in eligible

    def test_ban_node(self):
        coordinator = FederatedCoordinator("coord-1")
        coordinator.register_node("node-1")

        coordinator.ban_node("node-1", "Test reason")

        assert coordinator.nodes["node-1"].status == NodeStatus.BANNED
        assert "node-1" not in coordinator.get_eligible_nodes()


class TestTrainingRound:
    """Tests for training rounds."""

    def test_start_round(self):
        config = CoordinatorConfig(min_participants=3, target_participants=5)
        coordinator = FederatedCoordinator("coord-1", config)

        # Register enough nodes
        for i in range(6):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0]}))

        round_obj = coordinator.start_round()

        assert round_obj is not None
        assert round_obj.round_number == 1
        assert len(round_obj.selected_nodes) <= 5

    def test_start_round_insufficient_nodes(self):
        config = CoordinatorConfig(min_participants=5)
        coordinator = FederatedCoordinator("coord-1", config)

        coordinator.register_node("node-1")
        coordinator.register_node("node-2")

        round_obj = coordinator.start_round()

        assert round_obj is None

    def test_submit_update(self):
        config = CoordinatorConfig(min_participants=2, target_participants=3)
        coordinator = FederatedCoordinator("coord-1", config)

        for i in range(5):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0]}))
        round_obj = coordinator.start_round()

        # Submit from a selected node
        selected_node = list(round_obj.selected_nodes)[0]
        update = ModelUpdate(
            node_id=selected_node,
            round_number=1,
            weights=ModelWeights(layer_weights={"flat": [1.0]}),
            num_samples=100,
        )

        result = coordinator.submit_update(update)

        assert result
        assert selected_node in coordinator.current_round.received_updates

    def test_submit_from_unselected_node(self):
        config = CoordinatorConfig(min_participants=2, target_participants=3)
        coordinator = FederatedCoordinator("coord-1", config)

        for i in range(5):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0]}))
        coordinator.start_round()

        # Find an unselected node
        unselected = None
        for i in range(5):
            if f"node-{i}" not in coordinator.current_round.selected_nodes:
                unselected = f"node-{i}"
                break

        if unselected:
            update = ModelUpdate(
                node_id=unselected,
                round_number=1,
                weights=ModelWeights(layer_weights={"flat": [1.0]}),
            )

            result = coordinator.submit_update(update)
            assert not result


class TestFullTrainingCycle:
    """Integration tests for full training cycles."""

    def test_complete_training_round(self):
        config = CoordinatorConfig(
            min_participants=3, target_participants=5, aggregation_method="fedavg"
        )
        coordinator = FederatedCoordinator("coord-1", config)

        # Setup
        for i in range(6):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0] * 10}))

        # Start round
        round_obj = coordinator.start_round()
        assert round_obj is not None

        # Submit updates from all selected nodes
        for node_id in round_obj.selected_nodes:
            update = ModelUpdate(
                node_id=node_id,
                round_number=1,
                weights=ModelWeights(
                    layer_weights={"flat": [random.gauss(0, 0.1) for _ in range(10)]}
                ),
                num_samples=random.randint(50, 200),
            )
            coordinator.submit_update(update)

        # Round should be completed
        assert coordinator.current_round.status.value == "completed"
        assert coordinator.global_model.version == 1

    def test_multiple_rounds(self):
        # Use fedavg for simpler testing (Krum needs n >= 2f+3 = 5 for f=1)
        config = CoordinatorConfig(
            min_participants=3, target_participants=4, aggregation_method="fedavg"
        )
        coordinator = FederatedCoordinator("coord-1", config)

        for i in range(6):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0] * 5}))

        # Run 3 rounds
        for round_num in range(1, 4):
            round_obj = coordinator.start_round()
            assert round_obj is not None

            for node_id in round_obj.selected_nodes:
                update = ModelUpdate(
                    node_id=node_id,
                    round_number=round_num,
                    weights=ModelWeights(
                        layer_weights={"flat": [random.gauss(0, 0.1) for _ in range(5)]}
                    ),
                    num_samples=100,
                )
                coordinator.submit_update(update)

        assert coordinator.global_model.version == 3
        assert len(coordinator.round_history) == 3

    def test_metrics_tracking(self):
        config = CoordinatorConfig(
            min_participants=3, target_participants=4, aggregation_method="fedavg"
        )
        coordinator = FederatedCoordinator("coord-1", config)

        for i in range(5):
            coordinator.register_node(f"node-{i}")

        coordinator.initialize_model(ModelWeights(layer_weights={"flat": [0.0]}))

        # Run a round
        round_obj = coordinator.start_round()
        for node_id in round_obj.selected_nodes:
            coordinator.submit_update(
                ModelUpdate(
                    node_id=node_id,
                    round_number=1,
                    weights=ModelWeights(layer_weights={"flat": [1.0]}),
                    num_samples=100,
                )
            )

        metrics = coordinator.get_metrics()

        assert metrics["rounds_completed"] == 1
        assert metrics["registered_nodes"] == 5
        assert metrics["global_model_version"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
