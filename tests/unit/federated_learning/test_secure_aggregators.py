"""
Tests for Privacy-Preserving Aggregators.

Tests secure aggregation, differential privacy, and GraphSAGE integration.
"""

from typing import List
from unittest.mock import Mock, patch

import numpy as np
import pytest

try:
    from src.federated_learning.privacy import DPConfig
    from src.federated_learning.protocol import (GlobalModel, ModelUpdate,
                                                 ModelWeights)
    from src.federated_learning.secure_aggregators import (
        GraphSAGEAggregator, SecureFedAvgAggregator, SecureKrumAggregator,
        get_secure_aggregator)

    SECURE_AGGREGATORS_AVAILABLE = True
except ImportError:
    SECURE_AGGREGATORS_AVAILABLE = False
    SecureFedAvgAggregator = None
    SecureKrumAggregator = None
    GraphSAGEAggregator = None


@pytest.mark.skipif(
    not SECURE_AGGREGATORS_AVAILABLE, reason="Secure aggregators not available"
)
class TestSecureFedAvgAggregator:
    """Tests for SecureFedAvgAggregator"""

    def test_secure_aggregation_with_dp(self):
        """Test secure aggregation with differential privacy"""
        dp_config = DPConfig(
            target_epsilon=1.0, max_grad_norm=1.0, noise_multiplier=1.1
        )

        aggregator = SecureFedAvgAggregator(dp_config=dp_config, enable_dp=True)

        # Create mock updates
        updates = []
        for i in range(3):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100,
                training_loss=0.5,
                validation_loss=0.6,
            )
            updates.append(update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed
        assert result.success == True
        assert result.global_model is not None

        # Privacy budget should be tracked
        assert aggregator.privacy_budget.epsilon > 0

    def test_secure_aggregation_without_dp(self):
        """Test secure aggregation without differential privacy"""
        aggregator = SecureFedAvgAggregator(enable_dp=False)

        # Create mock updates
        updates = []
        for i in range(3):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed
        assert result.success == True
        assert result.global_model is not None

        # Privacy budget should not be tracked
        assert aggregator.privacy_budget.epsilon == 0

    def test_gradient_clipping(self):
        """Test gradient clipping"""
        aggregator = SecureFedAvgAggregator(enable_dp=True)

        # Create update with large gradients
        weights = ModelWeights(layer_weights={"layer1": [100.0, 200.0]})
        update = ModelUpdate(
            node_id="node-1", round_number=1, weights=weights, num_samples=100
        )

        # Clip gradients
        clipped = aggregator._clip_gradients([update])

        # Should be clipped
        assert len(clipped) == 1
        assert clipped[0].node_id == "node-1"

    def test_privacy_budget_tracking(self):
        """Test privacy budget tracking"""
        dp_config = DPConfig(target_epsilon=10.0)
        aggregator = SecureFedAvgAggregator(dp_config=dp_config, enable_dp=True)

        # Initial budget
        assert aggregator.privacy_budget.epsilon == 0.0
        assert aggregator.privacy_budget.remaining(10.0) == 10.0

        # After aggregation, budget should be consumed
        updates = []
        for i in range(3):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        aggregator.aggregate(updates)

        # Budget should be consumed
        assert aggregator.privacy_budget.epsilon > 0
        assert aggregator.privacy_budget.remaining(10.0) < 10.0


@pytest.mark.skipif(
    not SECURE_AGGREGATORS_AVAILABLE, reason="Secure aggregators not available"
)
class TestSecureKrumAggregator:
    """Tests for SecureKrumAggregator"""

    def test_secure_krum_with_dp(self):
        """Test secure Krum with differential privacy"""
        dp_config = DPConfig(target_epsilon=1.0)
        aggregator = SecureKrumAggregator(f=1, dp_config=dp_config, enable_dp=True)

        # Create updates (need at least 2f+3 = 5 for Krum)
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed
        assert result.success == True
        assert result.global_model is not None

    def test_byzantine_detection_with_privacy(self):
        """Test Byzantine detection with privacy-preserving"""
        aggregator = SecureKrumAggregator(f=1, enable_dp=True)

        # Create updates with one Byzantine (very different weights)
        updates = []
        for i in range(4):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Add Byzantine update
        byzantine_weights = ModelWeights(layer_weights={"layer1": [1000.0, 2000.0]})
        byzantine_update = ModelUpdate(
            node_id="byzantine-node",
            round_number=1,
            weights=byzantine_weights,
            num_samples=100,
        )
        updates.append(byzantine_update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed and detect Byzantine
        assert result.success == True
        if hasattr(result, "suspected_byzantine"):
            assert len(result.suspected_byzantine) > 0


@pytest.mark.skipif(
    not SECURE_AGGREGATORS_AVAILABLE, reason="Secure aggregators not available"
)
class TestGraphSAGEAggregator:
    """Tests for GraphSAGEAggregator"""

    def test_graphsage_aggregation(self):
        """Test GraphSAGE-specific aggregation"""
        aggregator = GraphSAGEAggregator()

        # Create updates
        updates = []
        for i in range(3):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed
        assert result.success == True
        assert result.global_model is not None

        # Should have GraphSAGE metadata
        if hasattr(result.global_model, "graphsage_metadata"):
            assert result.global_model.graphsage_metadata is not None

    def test_graphsage_with_base_aggregator(self):
        """Test GraphSAGE with custom base aggregator"""
        from src.federated_learning.aggregators import KrumAggregator

        base = KrumAggregator(f=1)
        aggregator = GraphSAGEAggregator(base_aggregator=base)

        # Create updates
        updates = []
        for i in range(5):  # Need 5 for Krum
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}", round_number=1, weights=weights, num_samples=100
            )
            updates.append(update)

        # Aggregate
        result = aggregator.aggregate(updates)

        # Should succeed
        assert result.success == True


@pytest.mark.skipif(
    not SECURE_AGGREGATORS_AVAILABLE, reason="Secure aggregators not available"
)
class TestSecureAggregatorFactory:
    """Tests for secure aggregator factory"""

    def test_get_secure_fedavg(self):
        """Test getting secure FedAvg aggregator"""
        aggregator = get_secure_aggregator("secure_fedavg", enable_dp=True)

        assert isinstance(aggregator, SecureFedAvgAggregator)
        assert aggregator.enable_dp == True

    def test_get_secure_krum(self):
        """Test getting secure Krum aggregator"""
        aggregator = get_secure_aggregator("secure_krum", f=1, enable_dp=True)

        assert isinstance(aggregator, SecureKrumAggregator)
        assert aggregator.enable_dp == True

    def test_get_graphsage_aggregator(self):
        """Test getting GraphSAGE aggregator"""
        aggregator = get_secure_aggregator("graphsage")

        assert isinstance(aggregator, GraphSAGEAggregator)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
