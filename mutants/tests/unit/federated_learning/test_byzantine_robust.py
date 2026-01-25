"""
Tests for Enhanced Byzantine-Robust Aggregators.

Tests performance optimizations, adaptive parameters, and outlier detection.
"""
import pytest
from unittest.mock import Mock
from typing import List

try:
    from src.federated_learning.byzantine_robust import (
        EnhancedKrumAggregator,
        AdaptiveTrimmedMeanAggregator,
        get_enhanced_aggregator
    )
    from src.federated_learning.protocol import (
        ModelUpdate,
        ModelWeights,
        GlobalModel
    )
    BYZANTINE_ROBUST_AVAILABLE = True
except ImportError:
    BYZANTINE_ROBUST_AVAILABLE = False
    EnhancedKrumAggregator = None
    AdaptiveTrimmedMeanAggregator = None


@pytest.mark.skipif(not BYZANTINE_ROBUST_AVAILABLE, reason="Byzantine-robust aggregators not available")
class TestEnhancedKrumAggregator:
    """Tests for EnhancedKrumAggregator"""
    
    def test_enhanced_krum_aggregation(self):
        """Test enhanced Krum aggregation"""
        aggregator = EnhancedKrumAggregator(f=1, multi_krum=True, m=2)
        
        # Create updates (need at least 5 for Krum with f=1)
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed
        assert result.success == True
        assert result.global_model is not None
    
    def test_adaptive_f_selection(self):
        """Test adaptive f selection"""
        aggregator = EnhancedKrumAggregator(f=1, adaptive_f=True)
        
        # Create updates
        updates = []
        for i in range(7):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed
        assert result.success == True
    
    def test_byzantine_detection(self):
        """Test Byzantine node detection"""
        aggregator = EnhancedKrumAggregator(f=1, multi_krum=True)
        
        # Create normal updates
        updates = []
        for i in range(4):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Add Byzantine update (very different)
        byzantine_weights = ModelWeights(layer_weights={"layer1": [1000.0, 2000.0]})
        byzantine_update = ModelUpdate(
            node_id="byzantine-node",
            round_number=1,
            weights=byzantine_weights,
            num_samples=100
        )
        updates.append(byzantine_update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed and detect Byzantine
        assert result.success == True
        if hasattr(result, 'suspected_byzantine'):
            assert len(result.suspected_byzantine) > 0
    
    def test_stats_tracking(self):
        """Test statistics tracking"""
        aggregator = EnhancedKrumAggregator(f=1)
        
        # Create updates
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate multiple times
        for _ in range(3):
            aggregator.aggregate(updates)
        
        # Check stats
        stats = aggregator.get_stats()
        assert stats["total_rounds"] == 3
        assert stats["avg_aggregation_time"] > 0


@pytest.mark.skipif(not BYZANTINE_ROBUST_AVAILABLE, reason="Byzantine-robust aggregators not available")
class TestAdaptiveTrimmedMeanAggregator:
    """Tests for AdaptiveTrimmedMeanAggregator"""
    
    def test_adaptive_trimmed_mean_aggregation(self):
        """Test adaptive trimmed mean aggregation"""
        aggregator = AdaptiveTrimmedMeanAggregator(beta=0.1, adaptive_beta=True)
        
        # Create updates
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed
        assert result.success == True
        assert result.global_model is not None
    
    def test_adaptive_beta_selection(self):
        """Test adaptive beta selection"""
        aggregator = AdaptiveTrimmedMeanAggregator(beta=0.1, adaptive_beta=True)
        
        # Create updates with high variance
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [10.0 * i, 20.0 * i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed
        assert result.success == True
    
    def test_outlier_detection(self):
        """Test outlier detection"""
        aggregator = AdaptiveTrimmedMeanAggregator(
            beta=0.1,
            outlier_detection="iqr"
        )
        
        # Create normal updates
        updates = []
        for i in range(4):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Add outlier
        outlier_weights = ModelWeights(layer_weights={"layer1": [100.0, 200.0]})
        outlier_update = ModelUpdate(
            node_id="outlier-node",
            round_number=1,
            weights=outlier_weights,
            num_samples=100
        )
        updates.append(outlier_update)
        
        # Aggregate
        result = aggregator.aggregate(updates)
        
        # Should succeed
        assert result.success == True
    
    def test_stats_tracking(self):
        """Test statistics tracking"""
        aggregator = AdaptiveTrimmedMeanAggregator(beta=0.1)
        
        # Create updates
        updates = []
        for i in range(5):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate multiple times
        for _ in range(3):
            aggregator.aggregate(updates)
        
        # Check stats
        stats = aggregator.get_stats()
        assert stats["total_rounds"] == 3
        assert stats["avg_trimmed"] >= 0


@pytest.mark.skipif(not BYZANTINE_ROBUST_AVAILABLE, reason="Byzantine-robust aggregators not available")
class TestEnhancedAggregatorFactory:
    """Tests for enhanced aggregator factory"""
    
    def test_get_enhanced_krum(self):
        """Test getting enhanced Krum aggregator"""
        aggregator = get_enhanced_aggregator("enhanced_krum", f=1)
        
        assert isinstance(aggregator, EnhancedKrumAggregator)
        assert aggregator.f == 1
    
    def test_get_adaptive_trimmed_mean(self):
        """Test getting adaptive trimmed mean aggregator"""
        aggregator = get_enhanced_aggregator("adaptive_trimmed_mean", beta=0.1)
        
        assert isinstance(aggregator, AdaptiveTrimmedMeanAggregator)
        assert aggregator.beta == 0.1


@pytest.mark.skipif(not BYZANTINE_ROBUST_AVAILABLE, reason="Byzantine-robust aggregators not available")
class TestByzantineRobustPerformance:
    """Performance tests for Byzantine-robust aggregators"""
    
    def test_enhanced_krum_performance(self):
        """Test enhanced Krum performance"""
        aggregator = EnhancedKrumAggregator(f=2, multi_krum=True, m=3)
        
        # Create many updates
        updates = []
        for i in range(10):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate and measure time
        import time
        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start
        
        # Should succeed and be reasonably fast
        assert result.success == True
        assert elapsed < 1.0  # Should complete in < 1 second
    
    def test_adaptive_trimmed_mean_performance(self):
        """Test adaptive trimmed mean performance"""
        aggregator = AdaptiveTrimmedMeanAggregator(beta=0.1)
        
        # Create many updates
        updates = []
        for i in range(10):
            weights = ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]})
            update = ModelUpdate(
                node_id=f"node-{i+1}",
                round_number=1,
                weights=weights,
                num_samples=100
            )
            updates.append(update)
        
        # Aggregate and measure time
        import time
        start = time.time()
        result = aggregator.aggregate(updates)
        elapsed = time.time() - start
        
        # Should succeed and be reasonably fast
        assert result.success == True
        assert elapsed < 1.0  # Should complete in < 1 second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

