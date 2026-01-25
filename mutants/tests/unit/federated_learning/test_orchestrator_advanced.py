"""
Unit tests for Advanced Federated Learning Orchestrator
"""

import pytest
from datetime import datetime, timedelta
import statistics

try:
    from src.federated_learning.orchestrator_advanced import (
        ScalingPolicy,
        ResourceMetric,
        PerformanceMetrics,
        ResourceUtilization,
        AdaptiveScaler,
        PerformancePredictor,
        ClusterOptimizer
    )
    ADVANCED_ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ADVANCED_ORCHESTRATOR_AVAILABLE = False


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestPerformanceMetrics:
    """Tests for PerformanceMetrics"""
    
    def test_metrics_initialization(self):
        """Test performance metrics initialization"""
        now = datetime.now()
        metrics = PerformanceMetrics(
            round_number=1,
            start_time=now,
            nodes_participated=100,
            total_time_ms=1000
        )
        
        assert metrics.round_number == 1
        assert metrics.nodes_participated == 100
        assert metrics.total_time_ms == 1000
    
    def test_calculate_efficiency(self):
        """Test efficiency calculation"""
        now = datetime.now()
        metrics = PerformanceMetrics(
            round_number=1,
            start_time=now,
            computation_time_ms=800,
            total_time_ms=1000
        )
        
        efficiency = metrics.calculate_efficiency()
        
        assert 0 <= efficiency <= 1
        assert efficiency == 0.8
    
    def test_efficiency_edge_cases(self):
        """Test efficiency with edge cases"""
        now = datetime.now()
        
        # Zero total time
        metrics = PerformanceMetrics(
            round_number=1,
            start_time=now,
            total_time_ms=0
        )
        assert metrics.calculate_efficiency() == 0.0
        
        # Computation > total (shouldn't happen but test bound)
        metrics = PerformanceMetrics(
            round_number=1,
            start_time=now,
            computation_time_ms=1500,
            total_time_ms=1000
        )
        assert metrics.calculate_efficiency() == 1.0


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestResourceUtilization:
    """Tests for ResourceUtilization"""
    
    def test_utilization_initialization(self):
        """Test resource utilization initialization"""
        now = datetime.now()
        util = ResourceUtilization(
            timestamp=now,
            cpu_percent=50,
            memory_percent=60,
            network_bandwidth_mbps=100,
            disk_io_percent=40,
            queue_depth=5,
            active_tasks=10
        )
        
        assert util.cpu_percent == 50
        assert util.memory_percent == 60
        assert util.queue_depth == 5
    
    def test_total_utilization_calculation(self):
        """Test total utilization calculation"""
        now = datetime.now()
        util = ResourceUtilization(
            timestamp=now,
            cpu_percent=50,
            memory_percent=50,
            network_bandwidth_mbps=50,
            disk_io_percent=50,
            queue_depth=0,
            active_tasks=0
        )
        
        total = util.total_utilization()
        
        # All metrics at 50 should give 0.5 (normalized to 0-1)
        assert 0.45 < total < 0.55


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestAdaptiveScaler:
    """Tests for AdaptiveScaler"""
    
    def test_scaler_initialization(self):
        """Test scaler initialization"""
        scaler = AdaptiveScaler()
        
        assert scaler.policy == ScalingPolicy.BALANCED
        assert scaler.current_nodes == 1
        assert len(scaler.utilization_history) == 0
    
    def test_scaler_custom_config(self):
        """Test scaler with custom configuration"""
        scaler = AdaptiveScaler(
            policy=ScalingPolicy.AGGRESSIVE,
            min_nodes=5,
            max_nodes=100,
            scale_up_threshold=0.7
        )
        
        assert scaler.policy == ScalingPolicy.AGGRESSIVE
        assert scaler.min_nodes == 5
        assert scaler.max_nodes == 100
        assert scaler.scale_up_threshold == 0.7
    
    def test_record_utilization(self):
        """Test recording utilization metrics"""
        scaler = AdaptiveScaler()
        now = datetime.now()
        
        for i in range(5):
            util = ResourceUtilization(
                timestamp=now,
                cpu_percent=50 + i * 10,
                memory_percent=50 + i * 10,
                network_bandwidth_mbps=50,
                disk_io_percent=50,
                queue_depth=i,
                active_tasks=i
            )
            scaler.record_utilization(util)
        
        assert len(scaler.utilization_history) == 5
    
    def test_record_performance(self):
        """Test recording performance metrics"""
        scaler = AdaptiveScaler()
        now = datetime.now()
        
        for i in range(3):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                total_time_ms=1000 - i * 100
            )
            scaler.record_performance(metrics)
        
        assert len(scaler.performance_history) == 3
    
    def test_scale_up_decision(self):
        """Test scale up decision"""
        scaler = AdaptiveScaler(scale_up_threshold=0.7, cooldown_seconds=0)
        
        # Add high utilization metrics
        now = datetime.now()
        for _ in range(10):
            util = ResourceUtilization(
                timestamp=now,
                cpu_percent=85,
                memory_percent=85,
                network_bandwidth_mbps=50,
                disk_io_percent=50,
                queue_depth=0,
                active_tasks=0
            )
            scaler.record_utilization(util)
        
        assert scaler.should_scale_up() == True
    
    def test_scale_down_decision(self):
        """Test scale down decision"""
        scaler = AdaptiveScaler(scale_down_threshold=0.3, cooldown_seconds=0)
        scaler.current_nodes = 10
        
        # Add low utilization metrics
        now = datetime.now()
        for _ in range(10):
            util = ResourceUtilization(
                timestamp=now,
                cpu_percent=15,
                memory_percent=15,
                network_bandwidth_mbps=10,
                disk_io_percent=10,
                queue_depth=0,
                active_tasks=0
            )
            scaler.record_utilization(util)
        
        assert scaler.should_scale_down() == True
    
    def test_scaling_limits(self):
        """Test that scaling respects min/max limits"""
        scaler = AdaptiveScaler(min_nodes=5, max_nodes=50)
        scaler.current_nodes = 5
        
        # Try to scale down below minimum
        scaler.last_scale_time = datetime.now() - timedelta(seconds=400)
        result = scaler.should_scale_down()
        assert result == False


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestPerformancePredictor:
    """Tests for PerformancePredictor"""
    
    def test_predictor_initialization(self):
        """Test predictor initialization"""
        predictor = PerformancePredictor()
        
        assert predictor.window_size == 20
        assert len(predictor.history) == 0
    
    def test_add_metrics(self):
        """Test adding metrics to predictor"""
        predictor = PerformancePredictor()
        now = datetime.now()
        
        for i in range(5):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                total_time_ms=1000 - i * 50
            )
            predictor.add_metrics(metrics)
        
        assert len(predictor.history) == 5
    
    def test_predict_next_round_time(self):
        """Test predicting next round execution time"""
        predictor = PerformancePredictor()
        now = datetime.now()
        
        # Add some historical data
        for i in range(10):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                total_time_ms=1000
            )
            predictor.add_metrics(metrics)
        
        predicted_time = predictor.predict_next_round_time()
        
        # Should be close to 1000
        assert 900 < predicted_time < 1100
    
    def test_predict_convergence_rounds(self):
        """Test predicting convergence rounds"""
        predictor = PerformancePredictor()
        now = datetime.now()
        
        # Simulate improving accuracy
        for i in range(10):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                total_time_ms=1000,
                model_accuracy=0.5 + i * 0.03
            )
            predictor.add_metrics(metrics)
        
        rounds = predictor.predict_convergence_rounds(target_accuracy=0.95)
        
        # Should predict positive number of rounds
        assert isinstance(rounds, int)
        assert rounds >= 0
    
    def test_identify_bottlenecks(self):
        """Test identifying performance bottlenecks"""
        predictor = PerformancePredictor()
        now = datetime.now()
        
        for i in range(10):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                aggregation_time_ms=400,
                network_time_ms=100,
                computation_time_ms=400,
                total_time_ms=1000,
                stragglers_count=5,
                nodes_participated=100
            )
            predictor.add_metrics(metrics)
        
        bottlenecks = predictor.identify_bottlenecks()
        
        assert 'aggregation' in bottlenecks
        assert 'network' in bottlenecks
        assert 'computation' in bottlenecks
        assert 'stragglers' in bottlenecks
    
    def test_recommend_optimizations(self):
        """Test optimization recommendations"""
        predictor = PerformancePredictor()
        now = datetime.now()
        
        # Create metrics with high aggregation bottleneck
        for i in range(10):
            metrics = PerformanceMetrics(
                round_number=i,
                start_time=now,
                aggregation_time_ms=600,
                network_time_ms=100,
                computation_time_ms=200,
                total_time_ms=1000,
                stragglers_count=0,
                nodes_participated=100
            )
            predictor.add_metrics(metrics)
        
        recommendations = predictor.recommend_optimizations()
        
        assert isinstance(recommendations, list)
        # Should recommend something about aggregation
        agg_recs = [r for r in recommendations if 'aggregat' in r.lower()]
        assert len(agg_recs) > 0


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestClusterOptimizer:
    """Tests for ClusterOptimizer"""
    
    def test_optimizer_initialization(self):
        """Test cluster optimizer initialization"""
        optimizer = ClusterOptimizer(num_nodes=100)
        
        assert optimizer.num_nodes == 100
        assert len(optimizer.node_latencies) == 0
    
    def test_recommend_partition_size(self):
        """Test partition size recommendation"""
        optimizer = ClusterOptimizer(num_nodes=100)
        
        # Default model size
        size = optimizer.recommend_partition_size(100)
        assert size > 0
        
        # Large model
        size_large = optimizer.recommend_partition_size(1500)
        assert size_large <= size
        
        # Small model
        size_small = optimizer.recommend_partition_size(5)
        assert size_small >= size
    
    def test_recommend_batch_size(self):
        """Test batch size recommendation"""
        optimizer = ClusterOptimizer(num_nodes=100)
        
        batch_size = optimizer.recommend_batch_size(100, 8)
        
        assert batch_size > 0
        assert batch_size >= 32  # Should be multiple of 32
    
    def test_get_summary(self):
        """Test getting optimizer summary"""
        optimizer = ClusterOptimizer(num_nodes=200)
        
        summary = optimizer.get_summary()
        
        assert 'total_nodes' in summary
        assert 'recommended_partitions' in summary
        assert 'recommended_batch_size' in summary
        assert 'optimization_timestamp' in summary
        assert summary['total_nodes'] == 200


@pytest.mark.skipif(not ADVANCED_ORCHESTRATOR_AVAILABLE, reason="Advanced orchestrator not available")
class TestScalingPolicies:
    """Tests for different scaling policies"""
    
    def test_conservative_policy(self):
        """Test conservative scaling policy"""
        scaler = AdaptiveScaler(policy=ScalingPolicy.CONSERVATIVE, scale_up_threshold=0.7)
        scaler.utilization_history = [
            ResourceUtilization(
                timestamp=datetime.now(),
                cpu_percent=90,
                memory_percent=90,
                network_bandwidth_mbps=50,
                disk_io_percent=50,
                queue_depth=0,
                active_tasks=0
            )
        ] * 10
        
        factor = scaler.get_scaling_factor()
        
        # Conservative should scale up by ~10%
        assert factor > 1.0
        assert factor < 1.2
    
    def test_aggressive_policy(self):
        """Test aggressive scaling policy"""
        scaler = AdaptiveScaler(policy=ScalingPolicy.AGGRESSIVE, scale_up_threshold=0.7)
        scaler.utilization_history = [
            ResourceUtilization(
                timestamp=datetime.now(),
                cpu_percent=90,
                memory_percent=90,
                network_bandwidth_mbps=50,
                disk_io_percent=50,
                queue_depth=0,
                active_tasks=0
            )
        ] * 10
        
        factor = scaler.get_scaling_factor()
        
        # Aggressive should scale up by ~50%
        assert factor > 1.3
        assert factor <= 1.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
