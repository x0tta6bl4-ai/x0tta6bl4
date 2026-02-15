"""
Performance benchmarks for Federated Learning aggregators.

Tests aggregation speed, memory usage, and scalability.
"""

import time
from typing import List

import pytest

try:
    from src.federated_learning.aggregators import (FedAvgAggregator,
                                                    KrumAggregator,
                                                    TrimmedMeanAggregator)
    from src.federated_learning.byzantine_robust import (
        AdaptiveTrimmedMeanAggregator, EnhancedKrumAggregator)
    from src.federated_learning.protocol import (GlobalModel, ModelUpdate,
                                                 ModelWeights)
    from src.federated_learning.secure_aggregators import (
        SecureFedAvgAggregator, SecureKrumAggregator)

    FL_AVAILABLE = True
except ImportError:
    FL_AVAILABLE = False


@pytest.mark.skipif(not FL_AVAILABLE, reason="FL aggregators not available")
class TestFLAggregatorBenchmarks:
    """Performance benchmarks for FL aggregators"""

    def _create_updates(
        self, num_updates: int, vector_size: int = 100
    ) -> List[ModelUpdate]:
        """Create test updates"""
        updates = []
        for i in range(num_updates):
            # Create weights with specified size
            weights = ModelWeights(
                layer_weights={"layer1": [float(j + i) for j in range(vector_size)]}
            )
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100,
                training_loss=0.5,
                validation_loss=0.6,
            )
            updates.append(update)
        return updates

    def test_fedavg_performance(self):
        """Benchmark FedAvg aggregator"""
        aggregator = FedAvgAggregator()

        # Test with different numbers of updates
        for num_updates in [5, 10, 20, 50]:
            updates = self._create_updates(num_updates, vector_size=100)

            start = time.time()
            result = aggregator.aggregate(updates)
            elapsed = time.time() - start

            assert result.success == True
            print(f"FedAvg: {num_updates} updates, {elapsed:.4f}s")

    def test_secure_fedavg_performance(self):
        """Benchmark SecureFedAvg aggregator"""
        aggregator = SecureFedAvgAggregator(enable_dp=True)

        updates = self._create_updates(10, vector_size=100)

        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start

        assert result.success == True
        print(f"SecureFedAvg: 10 updates, {elapsed:.4f}s")

    def test_krum_performance(self):
        """Benchmark Krum aggregator"""
        aggregator = KrumAggregator(f=1, multi_krum=True, m=2)

        # Test with different numbers of updates
        for num_updates in [5, 10, 20]:
            updates = self._create_updates(num_updates, vector_size=100)

            start = time.time()
            result = aggregator.aggregate(updates)
            elapsed = time.time() - start

            assert result.success == True
            print(f"Krum: {num_updates} updates, {elapsed:.4f}s")

    def test_enhanced_krum_performance(self):
        """Benchmark EnhancedKrum aggregator"""
        aggregator = EnhancedKrumAggregator(f=1, multi_krum=True, m=2)

        updates = self._create_updates(10, vector_size=100)

        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start

        assert result.success == True
        print(f"EnhancedKrum: 10 updates, {elapsed:.4f}s")

    def test_trimmed_mean_performance(self):
        """Benchmark TrimmedMean aggregator"""
        aggregator = TrimmedMeanAggregator(beta=0.1)

        updates = self._create_updates(10, vector_size=100)

        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start

        assert result.success == True
        print(f"TrimmedMean: 10 updates, {elapsed:.4f}s")

    def test_adaptive_trimmed_mean_performance(self):
        """Benchmark AdaptiveTrimmedMean aggregator"""
        aggregator = AdaptiveTrimmedMeanAggregator(beta=0.1)

        updates = self._create_updates(10, vector_size=100)

        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start

        assert result.success == True
        print(f"AdaptiveTrimmedMean: 10 updates, {elapsed:.4f}s")

    def test_scalability(self):
        """Test scalability with large models"""
        aggregator = FedAvgAggregator()

        # Test with different model sizes
        for vector_size in [100, 1000, 10000]:
            updates = self._create_updates(10, vector_size=vector_size)

            start = time.time()
            result = aggregator.aggregate(updates)
            elapsed = time.time() - start

            assert result.success == True
            print(f"Scalability: {vector_size} dims, {elapsed:.4f}s")

    def test_privacy_overhead(self):
        """Test privacy-preserving overhead"""
        # Without DP
        base_aggregator = FedAvgAggregator()
        updates = self._create_updates(10, vector_size=100)

        start = time.time()
        base_result = base_aggregator.aggregate(updates)
        base_time = time.time() - start

        # With DP
        secure_aggregator = SecureFedAvgAggregator(enable_dp=True)

        start = time.time()
        secure_result = secure_aggregator.aggregate(updates)
        secure_time = time.time() - start

        assert base_result.success == True
        assert secure_result.success == True

        overhead = (secure_time - base_time) / base_time * 100
        print(f"Privacy overhead: {overhead:.2f}%")

        # Overhead should be reasonable (< 50%)
        assert overhead < 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
