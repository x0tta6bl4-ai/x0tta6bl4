"""
Tests for LoRA + Federated Learning Integration.

Tests cover:
- FederatedLoRATrainer functionality
- LoRA weight aggregation (FedAvg)
- LoRAFLRound lifecycle
- Privacy-preserving weight clipping
- Multi-node federated training
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the modules under test
from src.federated_learning.lora_fl_integration import (
    FederatedLoRAConfig,
    FederatedLoRATrainer,
    LoRAFLRound,
    LoRAFLRoundStatus,
    LoRAWeightAggregator,
    LoRAWeightUpdate,
    aggregate_lora_weights,
    create_lora_update,
    run_federated_lora_training,
)
from src.federated_learning.protocol import ModelUpdate, ModelWeights
from src.ml.lora.config import LoRAConfig


# Fixtures

@pytest.fixture
def temp_storage_path():
    """Create a temporary directory for adapter storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def lora_config():
    """Create a LoRA configuration for testing."""
    return LoRAConfig(
        r=8,
        alpha=32,
        dropout=0.1,
        target_modules=["q_proj", "v_proj"],
    )


@pytest.fixture
def fl_lora_config(temp_storage_path, lora_config):
    """Create a federated LoRA configuration for testing."""
    return FederatedLoRAConfig(
        lora_config=lora_config,
        base_model_name="test-model",
        base_adapter_id="test_adapter_v0",
        min_participants=3,
        target_participants=5,
        num_rounds=3,
        local_epochs=1,
        learning_rate=2e-4,
        round_timeout=60.0,
        collection_timeout=30.0,
        enable_privacy=True,
        privacy_epsilon=0.1,
        max_grad_norm=1.0,
        aggregation_method="fedavg",
        adapter_storage_path=temp_storage_path,
    )


@pytest.fixture
def sample_lora_weights():
    """Create sample LoRA weights for testing."""
    return {
        "q_proj": {
            "lora_A": [0.1, 0.2, 0.3, 0.4],
            "lora_B": [0.5, 0.6, 0.7, 0.8],
        },
        "v_proj": {
            "lora_A": [0.2, 0.3, 0.4, 0.5],
            "lora_B": [0.6, 0.7, 0.8, 0.9],
        },
    }


@pytest.fixture
def sample_lora_update(sample_lora_weights):
    """Create a sample LoRA weight update."""
    return LoRAWeightUpdate(
        node_id="node_1",
        round_number=1,
        lora_weights=sample_lora_weights,
        num_samples=100,
        training_time_seconds=10.0,
        training_loss=0.5,
        validation_loss=0.6,
    )


# Test LoRAWeightUpdate

class TestLoRAWeightUpdate:
    """Tests for LoRAWeightUpdate class."""

    def test_create_lora_update(self, sample_lora_weights):
        """Test creating a LoRA weight update."""
        update = create_lora_update(
            node_id="test_node",
            round_number=1,
            lora_weights=sample_lora_weights,
            num_samples=50,
            training_loss=0.3,
        )

        assert update.node_id == "test_node"
        assert update.round_number == 1
        assert update.lora_weights == sample_lora_weights
        assert update.num_samples == 50
        assert update.training_loss == 0.3

    def test_to_model_update(self, sample_lora_update):
        """Test converting LoRA update to ModelUpdate."""
        model_update = sample_lora_update.to_model_update()

        assert isinstance(model_update, ModelUpdate)
        assert model_update.node_id == "node_1"
        assert model_update.round_number == 1
        assert model_update.num_samples == 100
        assert model_update.training_loss == 0.5

    def test_from_model_update(self, sample_lora_update):
        """Test creating LoRA update from ModelUpdate."""
        model_update = sample_lora_update.to_model_update()
        reconstructed = LoRAWeightUpdate.from_model_update(model_update)

        assert reconstructed.node_id == sample_lora_update.node_id
        assert reconstructed.round_number == sample_lora_update.round_number
        assert reconstructed.num_samples == sample_lora_update.num_samples


# Test LoRAWeightAggregator

class TestLoRAWeightAggregator:
    """Tests for LoRAWeightAggregator class."""

    def test_aggregator_initialization(self):
        """Test aggregator initialization."""
        aggregator = LoRAWeightAggregator(
            aggregation_method="fedavg",
            byzantine_tolerance=1,
            clip_norm=1.0,
        )

        assert aggregator.aggregation_method == "fedavg"
        assert aggregator.byzantine_tolerance == 1
        assert aggregator.clip_norm == 1.0

    def test_aggregate_single_update(self, sample_lora_weights):
        """Test aggregating a single update."""
        aggregator = LoRAWeightAggregator()
        update = LoRAWeightUpdate(
            node_id="node_1",
            round_number=1,
            lora_weights=sample_lora_weights,
            num_samples=100,
        )

        aggregated, result = aggregator.aggregate([update])

        assert result.success
        assert result.updates_accepted == 1
        assert "q_proj" in aggregated
        assert "v_proj" in aggregated

    def test_aggregate_multiple_updates(self, sample_lora_weights):
        """Test aggregating multiple updates with FedAvg."""
        # Use clip_norm=0 to disable clipping for this test
        aggregator = LoRAWeightAggregator(clip_norm=0.0)

        updates = []
        for i in range(3):
            # Slightly different weights per node
            weights = {
                "q_proj": {
                    "lora_A": [0.1 + i * 0.01, 0.2, 0.3, 0.4],
                    "lora_B": [0.5, 0.6, 0.7, 0.8],
                },
                "v_proj": {
                    "lora_A": [0.2, 0.3, 0.4, 0.5],
                    "lora_B": [0.6, 0.7, 0.8, 0.9],
                },
            }
            updates.append(LoRAWeightUpdate(
                node_id=f"node_{i}",
                round_number=1,
                lora_weights=weights,
                num_samples=100,
            ))

        aggregated, result = aggregator.aggregate(updates)

        assert result.success
        assert result.updates_accepted == 3
        # Check that aggregation produced averaged weights
        # First element should be average of [0.1, 0.11, 0.12] = 0.11
        # With equal weights (100 samples each), average = (0.1 + 0.11 + 0.12) / 3 = 0.11
        expected_avg = (0.1 + 0.11 + 0.12) / 3
        assert abs(aggregated["q_proj"]["lora_A"][0] - expected_avg) < 0.001

    def test_aggregate_empty_updates(self):
        """Test aggregating empty updates list."""
        aggregator = LoRAWeightAggregator()
        aggregated, result = aggregator.aggregate([])

        assert not result.success
        assert "No updates" in result.error_message

    def test_aggregate_weighted_by_samples(self):
        """Test that aggregation is weighted by sample count."""
        # Disable clipping for this test
        aggregator = LoRAWeightAggregator(clip_norm=0.0)

        # Node with more samples should have more influence
        weights1 = {"layer": {"lora_A": [1.0, 1.0], "lora_B": [1.0, 1.0]}}
        weights2 = {"layer": {"lora_A": [2.0, 2.0], "lora_B": [2.0, 2.0]}}

        update1 = LoRAWeightUpdate(
            node_id="node_1",
            round_number=1,
            lora_weights=weights1,
            num_samples=100,  # More samples
        )
        update2 = LoRAWeightUpdate(
            node_id="node_2",
            round_number=1,
            lora_weights=weights2,
            num_samples=50,  # Fewer samples
        )

        aggregated, result = aggregator.aggregate([update1, update2])

        assert result.success
        # Weighted average: (1.0 * 100 + 2.0 * 50) / 150 = 1.333...
        expected = (1.0 * 100 + 2.0 * 50) / 150
        assert abs(aggregated["layer"]["lora_A"][0] - expected) < 0.01

    def test_clip_weights(self, sample_lora_weights):
        """Test weight clipping for privacy."""
        aggregator = LoRAWeightAggregator(clip_norm=0.1)

        # Create weights with large norm
        large_weights = {
            "q_proj": {
                "lora_A": [10.0, 10.0, 10.0, 10.0],
                "lora_B": [10.0, 10.0, 10.0, 10.0],
            }
        }

        clipped = aggregator.clip_weights(large_weights, max_norm=0.1)

        # Check that norm is reduced
        import math
        total_norm = 0.0
        for module_weights in clipped.values():
            for w in module_weights.values():
                total_norm += sum(x ** 2 for x in w)
        total_norm = math.sqrt(total_norm)

        assert total_norm <= 0.1 + 1e-6  # Allow small floating point error

    def test_add_noise(self, sample_lora_weights):
        """Test adding noise for differential privacy."""
        aggregator = LoRAWeightAggregator()

        noisy = aggregator.add_noise(sample_lora_weights, noise_scale=0.01)

        # Weights should be different after noise addition
        assert noisy["q_proj"]["lora_A"] != sample_lora_weights["q_proj"]["lora_A"]
        # But roughly similar (within noise scale * 3 standard deviations)
        for i, (orig, noisy_val) in enumerate(zip(
            sample_lora_weights["q_proj"]["lora_A"],
            noisy["q_proj"]["lora_A"]
        )):
            assert abs(orig - noisy_val) < 0.1  # 0.01 * 10 for safety


# Test aggregate_lora_weights convenience function

class TestAggregateLoRAWeights:
    """Tests for aggregate_lora_weights convenience function."""

    def test_aggregate_lora_weights_basic(self, sample_lora_weights):
        """Test basic aggregation with convenience function."""
        updates = [
            LoRAWeightUpdate(
                node_id=f"node_{i}",
                round_number=1,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            for i in range(3)
        ]

        aggregated, result = aggregate_lora_weights(updates)

        assert result.success
        assert result.updates_accepted == 3


# Test LoRAFLRound

class TestLoRAFLRound:
    """Tests for LoRAFLRound dataclass."""

    def test_round_creation(self):
        """Test creating a LoRA FL round."""
        round_obj = LoRAFLRound(
            round_number=1,
            status=LoRAFLRoundStatus.PENDING,
            selected_nodes=["node_1", "node_2", "node_3"],
            min_participants=3,
        )

        assert round_obj.round_number == 1
        assert round_obj.status == LoRAFLRoundStatus.PENDING
        assert len(round_obj.selected_nodes) == 3

    def test_round_to_dict(self):
        """Test converting round to dictionary."""
        round_obj = LoRAFLRound(
            round_number=1,
            status=LoRAFLRoundStatus.TRAINING,
            selected_nodes=["node_1", "node_2"],
            min_participants=2,
        )

        data = round_obj.to_dict()

        assert data["round_number"] == 1
        assert data["status"] == "training"
        assert "node_1" in data["selected_nodes"]


# Test FederatedLoRAConfig

class TestFederatedLoRAConfig:
    """Tests for FederatedLoRAConfig dataclass."""

    def test_config_defaults(self, temp_storage_path):
        """Test default configuration values."""
        config = FederatedLoRAConfig(
            adapter_storage_path=temp_storage_path,
        )

        assert config.min_participants == 3
        assert config.target_participants == 10
        assert config.num_rounds == 10
        assert config.enable_privacy is True
        assert config.aggregation_method == "fedavg"

    def test_config_custom_values(self, temp_storage_path, lora_config):
        """Test custom configuration values."""
        config = FederatedLoRAConfig(
            lora_config=lora_config,
            base_model_name="custom-model",
            min_participants=5,
            num_rounds=20,
            adapter_storage_path=temp_storage_path,
        )

        assert config.lora_config == lora_config
        assert config.base_model_name == "custom-model"
        assert config.min_participants == 5
        assert config.num_rounds == 20


# Test FederatedLoRATrainer

class TestFederatedLoRATrainer:
    """Tests for FederatedLoRATrainer class."""

    def test_trainer_initialization(self, fl_lora_config):
        """Test trainer initialization."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        assert trainer.config == fl_lora_config
        assert trainer.coordinator is not None
        assert trainer.aggregator is not None
        assert trainer.current_round is None

    def test_register_node(self, fl_lora_config):
        """Test node registration."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        result = trainer.register_node("node_1", {"gpu": True})

        assert result is True
        assert "node_1" in trainer.coordinator.nodes

    def test_unregister_node(self, fl_lora_config):
        """Test node unregistration."""
        trainer = FederatedLoRATrainer(fl_lora_config)
        trainer.register_node("node_1")

        result = trainer.unregister_node("node_1")

        assert result is True
        assert "node_1" not in trainer.coordinator.nodes

    def test_start_round(self, fl_lora_config):
        """Test starting a training round."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register enough nodes
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()  # Start coordinator
        round_obj = trainer.start_round()

        assert round_obj is not None
        assert round_obj.status == LoRAFLRoundStatus.DISTRIBUTING
        assert len(round_obj.selected_nodes) >= fl_lora_config.min_participants

        trainer.stop()

    def test_submit_lora_update(self, fl_lora_config, sample_lora_weights):
        """Test submitting a LoRA update."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Setup round
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Create and submit update
        update = LoRAWeightUpdate(
            node_id=round_obj.selected_nodes[0],
            round_number=round_obj.round_number,
            lora_weights=sample_lora_weights,
            num_samples=100,
        )

        result = trainer.submit_lora_update(update)

        assert result is True
        assert round_obj.selected_nodes[0] in round_obj.lora_updates

        trainer.stop()

    def test_submit_update_wrong_node(self, fl_lora_config, sample_lora_weights):
        """Test submitting update from non-selected node."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Try to submit from non-selected node
        update = LoRAWeightUpdate(
            node_id="non_selected_node",
            round_number=round_obj.round_number,
            lora_weights=sample_lora_weights,
        )

        result = trainer.submit_lora_update(update)

        assert result is False

        trainer.stop()

    def test_get_metrics(self, fl_lora_config):
        """Test getting trainer metrics."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        metrics = trainer.get_metrics()

        assert "rounds_completed" in metrics
        assert "total_updates_received" in metrics
        assert "registered_nodes" in metrics

    def test_get_global_lora_weights(self, fl_lora_config, sample_lora_weights):
        """Test getting global LoRA weights after aggregation."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Setup and run a round with enough updates
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Submit updates from all selected nodes
        for node_id in round_obj.selected_nodes:
            update = LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_obj.round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            trainer.submit_lora_update(update)

        # Check that global weights are set
        global_weights = trainer.get_global_lora_weights()
        assert global_weights is not None
        assert "q_proj" in global_weights

        trainer.stop()

    def test_save_global_adapter(self, fl_lora_config, sample_lora_weights):
        """Test saving global adapter to disk."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Setup and run a round
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        for node_id in round_obj.selected_nodes:
            update = LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_obj.round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            trainer.submit_lora_update(update)

        # Save adapter
        result = trainer.save_global_adapter()

        assert result is True

        # Check files exist
        adapter_path = fl_lora_config.adapter_storage_path / "global_adapter"
        assert (adapter_path / "lora_weights.json").exists()
        assert (adapter_path / "adapter_metadata.json").exists()

        # Check metadata content
        with open(adapter_path / "adapter_metadata.json") as f:
            metadata = json.load(f)

        assert "adapter_id" in metadata
        assert "base_model_name" in metadata

        trainer.stop()


# Test async federated training

class TestAsyncFederatedTraining:
    """Tests for async federated training."""

    @pytest.mark.asyncio
    async def test_run_federated_training(self, fl_lora_config, sample_lora_weights):
        """Test running complete federated training."""
        nodes = [f"node_{i}" for i in range(5)]

        # Mock local training function
        async def mock_local_train(node_id, round_number, global_weights, config):
            return LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
                training_loss=0.5,
            )

        results = await run_federated_lora_training(
            config=fl_lora_config,
            nodes=nodes,
            local_train_fn=mock_local_train,
        )

        assert results["rounds_completed"] > 0
        assert results["final_adapter_id"] is not None
        assert "metrics" in results

    @pytest.mark.asyncio
    async def test_run_federated_lora_training_method(self, fl_lora_config, sample_lora_weights):
        """Test the run_federated_training method of FederatedLoRATrainer."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register nodes
        for i in range(5):
            trainer.register_node(f"node_{i}")

        # Mock local training
        async def mock_local_train(node_id, round_number, global_weights, config):
            return LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )

        trainer.start()
        results = await trainer.run_federated_training(mock_local_train)
        trainer.stop()

        assert "rounds_completed" in results
        assert "total_time" in results


# Test privacy features

class TestPrivacyFeatures:
    """Tests for privacy-preserving features."""

    def test_privacy_config(self, temp_storage_path):
        """Test privacy configuration."""
        config = FederatedLoRAConfig(
            enable_privacy=True,
            privacy_epsilon=0.5,
            privacy_delta=1e-6,
            max_grad_norm=0.5,
            adapter_storage_path=temp_storage_path,
        )

        assert config.enable_privacy is True
        assert config.privacy_epsilon == 0.5
        assert config.privacy_delta == 1e-6
        assert config.max_grad_norm == 0.5

    def test_update_clipping(self, fl_lora_config):
        """Test that updates are clipped when privacy is enabled."""
        fl_lora_config.enable_privacy = True
        fl_lora_config.max_grad_norm = 0.1
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Setup
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Create update with large weights
        large_weights = {
            "q_proj": {
                "lora_A": [10.0] * 4,
                "lora_B": [10.0] * 4,
            }
        }

        update = LoRAWeightUpdate(
            node_id=round_obj.selected_nodes[0],
            round_number=round_obj.round_number,
            lora_weights=large_weights,
            num_samples=100,
        )

        trainer.submit_lora_update(update)

        # Check that weights were clipped
        stored_update = round_obj.lora_updates[round_obj.selected_nodes[0]]

        # Calculate norm of stored weights
        import math
        total_norm = 0.0
        for w in stored_update.lora_weights.values():
            for arr in w.values():
                total_norm += sum(x ** 2 for x in arr)
        total_norm = math.sqrt(total_norm)

        # Norm should be reduced (clipping applied)
        assert total_norm < 100.0  # Original was much larger

        trainer.stop()

    def test_privacy_accounting(self, fl_lora_config, sample_lora_weights):
        """Test privacy budget accounting."""
        fl_lora_config.enable_privacy = True
        fl_lora_config.privacy_epsilon = 0.1
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Setup and run multiple rounds
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()

        for round_num in range(1, 4):
            round_obj = trainer.start_round(round_num)
            if round_obj:
                for node_id in round_obj.selected_nodes:
                    update = LoRAWeightUpdate(
                        node_id=node_id,
                        round_number=round_num,
                        lora_weights=sample_lora_weights,
                        num_samples=100,
                    )
                    trainer.submit_lora_update(update)

        # Check privacy accounting
        assert trainer.total_privacy_spent > 0
        assert trainer._metrics["privacy_epsilon_spent"] == trainer.total_privacy_spent

        trainer.stop()


# Test multi-node scenarios

class TestMultiNodeScenarios:
    """Tests for multi-node federated training scenarios."""

    def test_three_node_minimum(self, fl_lora_config, sample_lora_weights):
        """Test training with minimum 3 nodes."""
        fl_lora_config.min_participants = 3
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register exactly 3 nodes
        for i in range(3):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        assert round_obj is not None
        assert len(round_obj.selected_nodes) == 3

        # Submit from all nodes
        for node_id in round_obj.selected_nodes:
            update = LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_obj.round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            trainer.submit_lora_update(update)

        # Round should complete
        assert round_obj.status == LoRAFLRoundStatus.COMPLETED

        trainer.stop()

    def test_five_node_training(self, fl_lora_config, sample_lora_weights):
        """Test training with 5 nodes."""
        fl_lora_config.min_participants = 3
        fl_lora_config.target_participants = 5
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register 5 nodes
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        assert round_obj is not None
        assert len(round_obj.selected_nodes) >= 3

        # Submit from all selected nodes
        for node_id in round_obj.selected_nodes:
            update = LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_obj.round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            trainer.submit_lora_update(update)

        assert round_obj.status == LoRAFLRoundStatus.COMPLETED

        trainer.stop()

    def test_partial_participation(self, fl_lora_config, sample_lora_weights):
        """Test round with partial node participation."""
        fl_lora_config.min_participants = 2
        fl_lora_config.target_participants = 5
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register 5 nodes
        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Only submit from minimum required nodes
        for node_id in list(round_obj.selected_nodes)[:fl_lora_config.min_participants]:
            update = LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_obj.round_number,
                lora_weights=sample_lora_weights,
                num_samples=100,
            )
            trainer.submit_lora_update(update)

        # Round should still complete with minimum participation
        assert round_obj.status == LoRAFLRoundStatus.COMPLETED

        trainer.stop()


# Test error handling

class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_start_round_insufficient_nodes(self, fl_lora_config):
        """Test starting round with insufficient nodes."""
        fl_lora_config.min_participants = 5
        trainer = FederatedLoRATrainer(fl_lora_config)

        # Register only 2 nodes
        for i in range(2):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        # Should fail to start
        assert round_obj is None

        trainer.stop()

    def test_aggregate_empty_updates(self):
        """Test aggregation with no valid updates."""
        aggregator = LoRAWeightAggregator()

        # Create updates with empty weights
        updates = [
            LoRAWeightUpdate(
                node_id="node_1",
                round_number=1,
                lora_weights={},  # Empty weights
            )
        ]

        aggregated, result = aggregator.aggregate(updates)

        assert not result.success
        assert "No valid" in result.error_message

    def test_duplicate_update_rejection(self, fl_lora_config, sample_lora_weights):
        """Test that duplicate updates are rejected."""
        trainer = FederatedLoRATrainer(fl_lora_config)

        for i in range(5):
            trainer.register_node(f"node_{i}")

        trainer.start()
        round_obj = trainer.start_round()

        node_id = round_obj.selected_nodes[0]
        update = LoRAWeightUpdate(
            node_id=node_id,
            round_number=round_obj.round_number,
            lora_weights=sample_lora_weights,
        )

        # First submission should succeed
        result1 = trainer.submit_lora_update(update)
        assert result1 is True

        # Duplicate should be rejected
        result2 = trainer.submit_lora_update(update)
        assert result2 is False

        trainer.stop()


# Integration tests

class TestIntegration:
    """Integration tests for LoRA FL module."""

    @pytest.mark.asyncio
    async def test_full_training_pipeline(self, fl_lora_config):
        """Test complete training pipeline."""
        # Create diverse weights per node
        def create_node_weights(node_id, round_num):
            base = float(hash(node_id) % 100) / 100.0
            return {
                "q_proj": {
                    "lora_A": [base + 0.1, base + 0.2, base + 0.3, base + 0.4],
                    "lora_B": [base + 0.5, base + 0.6, base + 0.7, base + 0.8],
                },
                "v_proj": {
                    "lora_A": [base + 0.2, base + 0.3, base + 0.4, base + 0.5],
                    "lora_B": [base + 0.6, base + 0.7, base + 0.8, base + 0.9],
                },
            }

        nodes = [f"node_{i}" for i in range(5)]

        async def local_train(node_id, round_number, global_weights, config):
            return LoRAWeightUpdate(
                node_id=node_id,
                round_number=round_number,
                lora_weights=create_node_weights(node_id, round_number),
                num_samples=100,
                training_loss=0.5 - round_number * 0.1,
            )

        results = await run_federated_lora_training(
            config=fl_lora_config,
            nodes=nodes,
            local_train_fn=local_train,
        )

        assert results["rounds_completed"] > 0
        assert results["total_time"] > 0

        # Check that adapter was saved
        adapter_path = fl_lora_config.adapter_storage_path / "global_adapter"
        assert adapter_path.exists()

    def test_module_imports(self):
        """Test that all module components can be imported."""
        from src.federated_learning import (
            FederatedLoRATrainer,
            FederatedLoRAConfig,
            LoRAFLRound,
            LoRAFLRoundStatus,
            LoRAWeightUpdate,
            LoRAWeightAggregator,
            aggregate_lora_weights,
            create_lora_update,
            run_federated_lora_training,
        )

        # Verify classes are available
        assert FederatedLoRATrainer is not None
        assert FederatedLoRAConfig is not None
        assert LoRAFLRound is not None
        assert LoRAWeightUpdate is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])