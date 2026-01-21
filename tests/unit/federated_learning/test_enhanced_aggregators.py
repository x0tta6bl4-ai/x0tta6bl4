"""
Unit tests for Enhanced Federated Learning Aggregators
"""

import pytest
from unittest.mock import Mock, patch
from typing import List

try:
    from src.federated_learning.aggregators_enhanced import (
        EnhancedAggregator,
        EnhancedFedAvgAggregator,
        AdaptiveAggregator,
        AggregationMetrics,
        get_enhanced_aggregator
    )
    from src.federated_learning.aggregators import FedAvgAggregator
    from src.federated_learning.protocol import (
        ModelUpdate,
        ModelWeights,
        GlobalModel
    )
    ENHANCED_AGGREGATORS_AVAILABLE = True
except ImportError:
    ENHANCED_AGGREGATORS_AVAILABLE = False
    EnhancedAggregator = None
    EnhancedFedAvgAggregator = None
    AdaptiveAggregator = None


@pytest.mark.skipif(not ENHANCED_AGGREGATORS_AVAILABLE, reason="Enhanced aggregators not available")
class TestEnhancedAggregator:
    """Tests for Enhanced Aggregator Base"""
    
    def test_enhanced_aggregator_initialization(self):
        """Test enhanced aggregator initialization"""
        aggregator = EnhancedAggregator(
            name="test_enhanced",
            enable_metrics=True
        )
        
        assert aggregator.name == "test_enhanced"
        assert aggregator.enable_metrics == True
        assert len(aggregator.metrics_history) == 0
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        aggregator = EnhancedAggregator()
        
        # Create mock updates with similar weights
        updates = [
            ModelUpdate(
                node_id=f"node-{i}",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [1.0 + i * 0.1, 2.0 + i * 0.1]}),
                num_samples=100
            )
            for i in range(3)
        ]
        
        global_model = GlobalModel(
            version=1,
            round_number=1,
            weights=ModelWeights(layer_weights={"layer1": [1.5, 2.5]}),
            num_contributors=3
        )
        
        quality = aggregator._calculate_quality_score(updates, global_model, None)
        
        assert 0.0 <= quality <= 1.0
    
    def test_convergence_score_calculation(self):
        """Test convergence score calculation"""
        aggregator = EnhancedAggregator()
        
        updates = [
            ModelUpdate(
                node_id="node-1",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [1.0]}),
                num_samples=100,
                training_loss=0.5
            )
        ]
        
        previous_model = GlobalModel(
            version=0,
            round_number=0,
            weights=ModelWeights(layer_weights={"layer1": [1.0]}),
            avg_training_loss=1.0
        )
        
        current_model = GlobalModel(
            version=1,
            round_number=1,
            weights=ModelWeights(layer_weights={"layer1": [1.0]}),
            avg_training_loss=0.5
        )
        
        convergence = aggregator._calculate_convergence_score(
            updates, current_model, previous_model
        )
        
        assert 0.0 <= convergence <= 1.0
    
    def test_get_aggregation_stats(self):
        """Test getting aggregation statistics"""
        aggregator = EnhancedAggregator(enable_metrics=True)
        
        # Simulate some aggregations
        aggregator.metrics_history = [
            AggregationMetrics(
                aggregation_time_seconds=1.0,
                quality_score=0.8,
                convergence_score=0.7,
                updates_accepted=5
            )
            for _ in range(5)
        ]
        
        stats = aggregator.get_aggregation_stats()
        
        assert 'total_aggregations' in stats
        assert 'avg_aggregation_time' in stats
        assert 'avg_quality_score' in stats
        assert stats['total_aggregations'] == 5


@pytest.mark.skipif(not ENHANCED_AGGREGATORS_AVAILABLE, reason="Enhanced aggregators not available")
class TestEnhancedFedAvgAggregator:
    """Tests for Enhanced FedAvg Aggregator"""
    
    def test_enhanced_fedavg_aggregation(self):
        """Test enhanced FedAvg aggregation"""
        aggregator = EnhancedFedAvgAggregator(enable_metrics=True)
        
        updates = [
            ModelUpdate(
                node_id=f"node-{i}",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [float(i), float(i+1)]}),
                num_samples=100,
                training_loss=0.5
            )
            for i in range(3)
        ]
        
        result = aggregator.aggregate(updates)
        
        assert result.success == True
        assert result.global_model is not None
        assert 'metrics' in result.metadata
    
    def test_metrics_in_result(self):
        """Test that metrics are included in result"""
        aggregator = EnhancedFedAvgAggregator(enable_metrics=True)
        
        updates = [
            ModelUpdate(
                node_id="node-1",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [1.0, 2.0]}),
                num_samples=100
            )
        ]
        
        result = aggregator.aggregate(updates)
        
        assert result.success == True
        metrics = result.metadata.get('metrics', {})
        assert 'aggregation_time_seconds' in metrics
        assert 'quality_score' in metrics


@pytest.mark.skipif(not ENHANCED_AGGREGATORS_AVAILABLE, reason="Enhanced aggregators not available")
class TestAdaptiveAggregator:
    """Tests for Adaptive Aggregator"""
    
    def test_adaptive_aggregator_initialization(self):
        """Test adaptive aggregator initialization"""
        aggregator = AdaptiveAggregator(
            trust_threshold=0.8,
            outlier_threshold=2.0
        )
        
        assert aggregator.trust_threshold == 0.8
        assert aggregator.outlier_threshold == 2.0
        assert aggregator.fedavg is not None
        assert aggregator.krum is not None
        assert aggregator.trimmed_mean is not None
    
    def test_strategy_selection(self):
        """Test strategy selection logic"""
        aggregator = AdaptiveAggregator()
        
        # Test with few updates (should use FedAvg)
        updates = [
            ModelUpdate(
                node_id=f"node-{i}",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [float(i)]}),
                num_samples=100
            )
            for i in range(3)
        ]
        
        strategy = aggregator._select_strategy(updates, None)
        assert strategy in ["fedavg", "krum", "trimmed_mean"]
    
    def test_get_strategy_stats(self):
        """Test getting strategy statistics"""
        aggregator = AdaptiveAggregator()
        
        # Simulate some strategy selections
        aggregator.strategy_history = ["fedavg", "krum", "fedavg", "trimmed_mean"]
        
        stats = aggregator.get_strategy_stats()
        
        assert 'total_aggregations' in stats
        assert 'strategy_usage' in stats
        assert 'strategy_counts' in stats
        assert stats['total_aggregations'] == 4


@pytest.mark.skipif(not ENHANCED_AGGREGATORS_AVAILABLE, reason="Enhanced aggregators not available")
class TestAggregationMetrics:
    """Tests for AggregationMetrics"""
    
    def test_metrics_initialization(self):
        """Test metrics initialization"""
        metrics = AggregationMetrics()
        
        assert metrics.aggregation_time_seconds == 0.0
        assert metrics.updates_received == 0
        assert metrics.updates_accepted == 0
        assert metrics.quality_score == 0.0
    
    def test_metrics_with_values(self):
        """Test metrics with actual values"""
        metrics = AggregationMetrics(
            aggregation_time_seconds=1.5,
            updates_received=10,
            updates_accepted=8,
            quality_score=0.85,
            convergence_score=0.75
        )
        
        assert metrics.aggregation_time_seconds == 1.5
        assert metrics.updates_received == 10
        assert metrics.updates_accepted == 8
        assert metrics.quality_score == 0.85
        assert metrics.convergence_score == 0.75

