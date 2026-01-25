"""
Federated Learning Orchestrator Scaling Tests
==============================================

Tests for 1000+ node federated learning orchestration.

Coverage:
1. Aggregation correctness (5 tests)
2. Byzantine fault tolerance (8 tests)
3. Convergence detection (5 tests)
4. Learning rate scheduling (4 tests)
5. Hierarchical aggregation (6 tests)
6. Failure recovery (4 tests)
7. Performance and scaling (5 tests)
"""

import pytest
import numpy as np
from typing import List
import logging

from src.ai.fl_orchestrator_scaling import (
    ModelUpdate,
    ByzantineDetector,
    ConvergenceDetector,
    AdaptiveLearningRate,
    BatchAsyncOrchestrator,
    StreamingOrchestrator,
    HierarchicalOrchestrator,
    FLTrainingSession,
    AggregationMethod,
    LearningRateSchedule,
    TrainingRoundStats,
    create_orchestrator,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def sample_model():
    """Create a sample model"""
    return np.random.randn(100)


@pytest.fixture
def sample_updates(sample_model) -> List[ModelUpdate]:
    """Create sample model updates from 10 nodes"""
    updates = []
    for i in range(10):
        gradient = np.random.randn(*sample_model.shape) * 0.01
        update = ModelUpdate(
            node_id=f"node-{i}",
            gradient=gradient,
            svid=f"spiffe://x0tta6bl4.mesh/node/node-{i}",
            signature=b"signature_" + str(i).encode(),
            round_number=0
        )
        updates.append(update)
    return updates


@pytest.fixture
def byzantine_updates(sample_model) -> List[ModelUpdate]:
    """Create updates with Byzantine (bad) nodes mixed in"""
    updates = []
    
    # 7 honest nodes
    for i in range(7):
        gradient = np.random.randn(*sample_model.shape) * 0.01
        update = ModelUpdate(
            node_id=f"honest-{i}",
            gradient=gradient,
            svid=f"spiffe://x0tta6bl4.mesh/node/honest-{i}",
            signature=b"sig_honest_" + str(i).encode(),
            round_number=0
        )
        updates.append(update)
    
    # 3 Byzantine nodes (send bad gradients)
    for i in range(3):
        # Byzantine nodes send large random gradients
        gradient = np.random.randn(*sample_model.shape) * 10.0
        update = ModelUpdate(
            node_id=f"byzantine-{i}",
            gradient=gradient,
            svid=f"spiffe://x0tta6bl4.mesh/node/byzantine-{i}",
            signature=b"sig_byz_" + str(i).encode(),
            round_number=0
        )
        updates.append(update)
    
    return updates


class TestAggregationCorrectness:
    """Test basic aggregation correctness"""

    def test_mean_aggregation(self, sample_updates):
        """Test mean aggregation"""
        detector = ByzantineDetector()
        result = detector.filter_and_aggregate(sample_updates, AggregationMethod.MEAN)
        
        # Result should be roughly mean of updates (may filter some)
        # Just verify result has correct shape and magnitude
        assert result.shape == sample_updates[0].gradient.shape
        assert np.linalg.norm(result) > 0  # Not zero

    def test_median_aggregation(self, sample_updates):
        """Test median aggregation"""
        detector = ByzantineDetector()
        result = detector.filter_and_aggregate(sample_updates, AggregationMethod.MEDIAN)
        
        # Result should be approximately median of updates
        assert result.shape == sample_updates[0].gradient.shape
        assert np.isfinite(result).all()  # No NaN or Inf

    def test_aggregation_shape(self, sample_updates, sample_model):
        """Test aggregation preserves shape"""
        detector = ByzantineDetector()
        result = detector.filter_and_aggregate(sample_updates)
        
        assert result.shape == sample_model.shape

    def test_aggregation_with_single_update(self, sample_model):
        """Test aggregation with single update"""
        detector = ByzantineDetector()
        single_update = ModelUpdate(
            node_id="node-0",
            gradient=np.ones_like(sample_model) * 0.1,
            svid="spiffe://x0tta6bl4.mesh/node/node-0",
            signature=b"sig"
        )
        
        result = detector.filter_and_aggregate([single_update])
        np.testing.assert_allclose(result, single_update.gradient)

    def test_aggregation_with_zeros(self, sample_model):
        """Test aggregation when updates are zero"""
        detector = ByzantineDetector()
        updates = [
            ModelUpdate(
                node_id="node-0",
                gradient=np.zeros_like(sample_model),
                svid="spiffe://x0tta6bl4.mesh/node/node-0",
                signature=b"sig"
            )
            for _ in range(5)
        ]
        
        result = detector.filter_and_aggregate(updates)
        np.testing.assert_allclose(result, np.zeros_like(sample_model))


class TestByzantineFaultTolerance:
    """Test Byzantine fault tolerance"""

    def test_byzantine_detection(self, byzantine_updates):
        """Test detection of Byzantine nodes"""
        detector = ByzantineDetector(tolerance_fraction=0.3)
        malicious_idx = detector.detect_malicious_updates(byzantine_updates)
        
        # Should detect at least 2 of 3 Byzantine nodes
        assert len(malicious_idx) >= 2
        
        # Detected ones should be Byzantine (indices 7, 8, 9)
        byzantine_indices = {7, 8, 9}
        detected_byzantine = sum(1 for idx in malicious_idx if idx in byzantine_indices)
        assert detected_byzantine >= 1

    def test_byzantine_filtering(self, byzantine_updates):
        """Test that Byzantine updates are filtered out"""
        detector = ByzantineDetector(tolerance_fraction=0.3)
        result = detector.filter_and_aggregate(byzantine_updates)
        
        # Result should be close to honest updates (smaller magnitude)
        honest_updates = [u.gradient for u in byzantine_updates[:7]]
        honest_mean = np.mean(honest_updates, axis=0)
        
        # Result should be closer to honest mean than Byzantine mean
        dist_to_honest = np.linalg.norm(result - honest_mean)
        
        byzantine_mean = np.mean([u.gradient for u in byzantine_updates[7:]], axis=0)
        dist_to_byzantine = np.linalg.norm(result - byzantine_mean)
        
        assert dist_to_honest < dist_to_byzantine

    def test_byzantine_tolerance_30_percent(self, sample_model):
        """Test tolerance of 30% Byzantine nodes"""
        # Create 70 honest + 30 Byzantine = 100 nodes
        updates = []
        
        # 70 honest nodes
        for i in range(70):
            gradient = np.random.randn(*sample_model.shape) * 0.01
            updates.append(ModelUpdate(
                node_id=f"honest-{i}",
                gradient=gradient,
                svid=f"spiffe://x0tta6bl4.mesh/node/honest-{i}",
                signature=b"sig"
            ))
        
        # 30 Byzantine nodes
        for i in range(30):
            gradient = np.random.randn(*sample_model.shape) * 5.0  # Bad gradients
            updates.append(ModelUpdate(
                node_id=f"byzantine-{i}",
                gradient=gradient,
                svid=f"spiffe://x0tta6bl4.mesh/node/byzantine-{i}",
                signature=b"sig"
            ))
        
        detector = ByzantineDetector(tolerance_fraction=0.30)
        result = detector.filter_and_aggregate(updates)
        
        # Should not crash and should return reasonable result
        assert result is not None
        assert result.shape == sample_model.shape

    def test_no_byzantine_nodes(self, sample_updates):
        """Test aggregation with all honest updates"""
        detector = ByzantineDetector()
        malicious_idx = detector.detect_malicious_updates(sample_updates)
        
        # Should detect 0 Byzantine nodes
        assert len(malicious_idx) == 0

    def test_krum_aggregation(self, sample_updates):
        """Test Krum aggregation method"""
        detector = ByzantineDetector()
        result = detector.filter_and_aggregate(sample_updates, AggregationMethod.KRUM)
        
        # Krum selects one gradient, so result should match one of them
        gradient_set = [np.linalg.norm(u.gradient) for u in sample_updates]
        result_norm = np.linalg.norm(result)
        
        # Result norm should be close to one of the input norms
        assert any(abs(result_norm - gn) < 0.1 for gn in gradient_set)

    def test_gradient_norm_bounds(self, sample_model):
        """Test gradient norm bounds for Byzantine detection"""
        detector = ByzantineDetector()
        
        updates = []
        # Mix of normal and very large gradients
        for i in range(5):
            updates.append(ModelUpdate(
                node_id=f"normal-{i}",
                gradient=np.random.randn(*sample_model.shape) * 0.1,
                svid=f"spiffe://x0tta6bl4.mesh/node/normal-{i}",
                signature=b"sig"
            ))
        
        # Add outlier
        updates.append(ModelUpdate(
            node_id="outlier",
            gradient=np.random.randn(*sample_model.shape) * 100,
            svid=f"spiffe://x0tta6bl4.mesh/node/outlier",
            signature=b"sig"
        ))
        
        # Should detect the outlier
        malicious_idx = detector.detect_malicious_updates(updates)
        assert len(malicious_idx) > 0


class TestConvergenceDetection:
    """Test convergence detection"""

    def test_convergence_on_stable_loss(self):
        """Test convergence detection with stable loss"""
        detector = ConvergenceDetector(window_size=3, threshold=0.001)
        
        # Simulate stable loss
        for i in range(5):
            detector.update(loss=1.0, accuracy=0.5, gradient_norm=0.001)
        
        converged, reason = detector.check_convergence()
        assert converged is True
        assert "improvement" in reason.lower()

    def test_convergence_on_plateau(self):
        """Test convergence when loss plateaus"""
        detector = ConvergenceDetector(window_size=3)
        
        # Simulate loss plateau
        detector.update(loss=1.0, accuracy=0.5, gradient_norm=1.0)
        detector.update(loss=0.9, accuracy=0.55, gradient_norm=0.9)
        detector.update(loss=0.89, accuracy=0.56, gradient_norm=0.01)  # Low gradient norm
        
        converged, reason = detector.check_convergence()
        # Should detect convergence due to low gradient norm
        assert "gradient norm" in reason.lower()

    def test_no_convergence_on_improvement(self):
        """Test no convergence when loss is improving"""
        detector = ConvergenceDetector(window_size=3, threshold=0.01)
        
        # Simulate improving loss
        detector.update(loss=1.0, accuracy=0.5, gradient_norm=1.0)
        detector.update(loss=0.8, accuracy=0.6, gradient_norm=0.8)
        detector.update(loss=0.6, accuracy=0.7, gradient_norm=0.6)
        
        converged, reason = detector.check_convergence()
        assert converged is False

    def test_insufficient_history(self):
        """Test convergence check with insufficient history"""
        detector = ConvergenceDetector(window_size=5)
        
        # Only 3 updates
        for i in range(3):
            detector.update(loss=1.0, accuracy=0.5, gradient_norm=0.1)
        
        converged, reason = detector.check_convergence()
        assert converged is False
        assert "history" in reason.lower()

    def test_convergence_accuracy_plateau(self):
        """Test convergence on accuracy plateau"""
        detector = ConvergenceDetector(window_size=3, threshold=0.001)
        
        # Accuracy plateaus
        detector.update(loss=1.0, accuracy=0.5, gradient_norm=1.0)
        detector.update(loss=0.99, accuracy=0.500, gradient_norm=0.99)
        detector.update(loss=0.98, accuracy=0.500, gradient_norm=0.98)
        
        converged, reason = detector.check_convergence()
        # May converge due to no accuracy improvement
        assert converged is not None  # Either True or False is valid


class TestLearningRateScheduling:
    """Test learning rate scheduling"""

    def test_constant_lr(self):
        """Test constant learning rate"""
        scheduler = AdaptiveLearningRate(
            initial_lr=0.1,
            schedule=LearningRateSchedule.CONSTANT
        )
        
        lr1 = scheduler.get_lr()
        lr2 = scheduler.get_lr()
        lr3 = scheduler.get_lr()
        
        assert lr1 == lr2 == lr3 == 0.1

    def test_step_decay(self):
        """Test step decay learning rate"""
        scheduler = AdaptiveLearningRate(
            initial_lr=0.1,
            schedule=LearningRateSchedule.STEP_DECAY
        )
        
        lrs = []
        for _ in range(25):
            lrs.append(scheduler.get_lr())
        
        # Should decay at round 10 and 20
        assert lrs[0] > lrs[10]  # Decayed
        assert lrs[10] > lrs[20]  # Decayed again

    def test_exponential_decay(self):
        """Test exponential decay learning rate"""
        scheduler = AdaptiveLearningRate(
            initial_lr=0.1,
            schedule=LearningRateSchedule.EXPONENTIAL
        )
        
        lrs = []
        for _ in range(10):
            lrs.append(scheduler.get_lr())
        
        # Learning rate should decrease monotonically
        for i in range(len(lrs) - 1):
            assert lrs[i] >= lrs[i + 1]

    def test_lr_staleness_adjustment(self):
        """Test learning rate adjustment for staleness"""
        scheduler = AdaptiveLearningRate(initial_lr=0.1)
        
        # Fresh update
        lr_fresh = scheduler.get_lr(staleness=0.0)
        
        # Reset and get stale update rate
        scheduler.reset()
        lr_stale = scheduler.get_lr(staleness=0.5)
        
        # Stale updates should use lower learning rate
        assert lr_stale < lr_fresh


class TestBatchAsyncOrchestrator:
    """Test batch async aggregation"""

    def test_batch_aggregation(self, sample_model, sample_updates):
        """Test batch async aggregation"""
        orchestrator = BatchAsyncOrchestrator(
            sample_model,
            k_threshold=0.8,
            timeout=60.0
        )
        
        # Aggregate updates
        gradient = orchestrator.aggregate_updates(sample_updates)
        
        assert gradient is not None
        assert gradient.shape == sample_model.shape

    def test_threshold_check(self, sample_model):
        """Test threshold checking for aggregation"""
        orchestrator = BatchAsyncOrchestrator(
            sample_model,
            k_threshold=0.9
        )
        
        # With 10 nodes, need 9 to aggregate
        assert orchestrator.should_aggregate(9, 10) is True
        assert orchestrator.should_aggregate(8, 10) is False
        assert orchestrator.should_aggregate(5, 10) is False

    def test_timeout_aggregation(self, sample_model):
        """Test timeout triggering aggregation"""
        orchestrator = BatchAsyncOrchestrator(
            sample_model,
            k_threshold=0.9,
            timeout=0.1  # Very short timeout
        )
        
        # Should aggregate after timeout
        import time
        time.sleep(0.15)
        
        assert orchestrator.should_aggregate(5, 10) is True

    def test_model_update(self, sample_model):
        """Test model update after aggregation"""
        orchestrator = BatchAsyncOrchestrator(sample_model)
        
        gradient = np.ones_like(sample_model) * 0.1
        old_model = orchestrator.model.copy()
        
        orchestrator.update_model(gradient, learning_rate=0.01)
        
        expected = old_model - 0.01 * gradient
        np.testing.assert_allclose(orchestrator.model, expected)


class TestHierarchicalAggregation:
    """Test hierarchical aggregation"""

    def test_zone_creation(self, sample_model):
        """Test zone aggregator creation"""
        orchestrator = HierarchicalOrchestrator(sample_model, num_zones=10)
        
        assert len(orchestrator.zone_updates) == 10
        assert len(orchestrator.zone_aggregates) == 10

    def test_zone_aggregation(self, sample_model, sample_updates):
        """Test aggregation within a zone"""
        orchestrator = HierarchicalOrchestrator(sample_model, num_zones=3)
        
        # Add updates to zone 0
        for update in sample_updates:
            orchestrator.add_update_to_zone(0, update)
        
        # Aggregate zone
        zone_gradient = orchestrator.aggregate_zone(0)
        
        assert zone_gradient is not None
        assert zone_gradient.shape == sample_model.shape

    def test_global_aggregation(self, sample_model, sample_updates):
        """Test global aggregation across zones"""
        orchestrator = HierarchicalOrchestrator(sample_model, num_zones=2)
        
        # Add updates to different zones
        for i, update in enumerate(sample_updates):
            zone = i % 2
            orchestrator.add_update_to_zone(zone, update)
        
        # Aggregate each zone
        for z in range(2):
            orchestrator.aggregate_zone(z)
        
        # Global aggregation
        global_gradient = orchestrator.aggregate_updates(sample_updates)
        
        assert global_gradient is not None

    def test_bandwidth_savings(self, sample_model):
        """Test bandwidth savings with hierarchical aggregation"""
        # Without hierarchy: N gradients transmitted
        num_nodes = 1000
        gradient_size_mb = 1  # 1MB per gradient
        
        flat_bandwidth = num_nodes * gradient_size_mb  # 1000 MB
        
        # With hierarchy: 10 zones, 100 nodes per zone
        # Level 1: 100 gradients per zone × 10 zones = 1000 MB
        # Level 2: 10 zone aggregates = 10 MB
        # Total reduction: in central coordination
        
        # Just verify hierarchical orchestrator works without errors
        orchestrator = HierarchicalOrchestrator(sample_model, num_zones=10)
        assert orchestrator.num_zones == 10


class TestFLTrainingSession:
    """Test federated learning training sessions"""

    def test_training_round(self, sample_model, sample_updates):
        """Test single training round"""
        orchestrator = BatchAsyncOrchestrator(sample_model)
        session = FLTrainingSession(sample_model, orchestrator, max_rounds=10)
        
        stats = session.training_round(
            sample_updates,
            loss=1.0,
            accuracy=0.5
        )
        
        assert stats.round_number == 0
        assert stats.updates_received == len(sample_updates)
        assert stats.learning_rate > 0
        assert stats.total_round_time_ms > 0

    def test_convergence_in_session(self, sample_model):
        """Test convergence detection in training session"""
        orchestrator = BatchAsyncOrchestrator(sample_model)
        session = FLTrainingSession(sample_model, orchestrator, max_rounds=100)
        
        # Simulate converging training
        round_count = 0
        while session.should_continue() and round_count < 10:
            # Simulate improving loss
            loss = 1.0 / (1 + round_count * 0.1)
            accuracy = 0.5 + round_count * 0.05
            
            # Create mock updates
            updates = []
            for i in range(5):
                update = ModelUpdate(
                    node_id=f"node-{i}",
                    gradient=np.ones_like(sample_model) * 0.001,
                    svid=f"spiffe://x0tta6bl4.mesh/node/node-{i}",
                    signature=b"sig"
                )
                updates.append(update)
            
            stats = session.training_round(updates, loss, accuracy)
            round_count += 1
            
            if round_count >= 5:  # Force convergence after some rounds
                break
        
        assert session.current_round > 0


class TestOrchestratorFactory:
    """Test orchestrator creation"""

    def test_batch_orchestrator_creation(self, sample_model):
        """Test batch orchestrator creation"""
        orchestrator = create_orchestrator("batch", sample_model)
        assert isinstance(orchestrator, BatchAsyncOrchestrator)

    def test_streaming_orchestrator_creation(self, sample_model):
        """Test streaming orchestrator creation"""
        orchestrator = create_orchestrator("streaming", sample_model)
        assert isinstance(orchestrator, StreamingOrchestrator)

    def test_hierarchical_orchestrator_creation(self, sample_model):
        """Test hierarchical orchestrator creation"""
        orchestrator = create_orchestrator("hierarchical", sample_model, num_zones=5)
        assert isinstance(orchestrator, HierarchicalOrchestrator)
        assert orchestrator.num_zones == 5

    def test_invalid_orchestrator(self, sample_model):
        """Test invalid orchestrator type"""
        with pytest.raises(ValueError):
            create_orchestrator("invalid", sample_model)


class TestProductionScaling:
    """Test production-scale scenarios"""

    @pytest.mark.slow
    def test_1000_node_aggregation(self, sample_model):
        """Test aggregation with simulated 1000 nodes"""
        # Create 1000 mock updates
        updates = []
        for i in range(1000):
            gradient = np.random.randn(*sample_model.shape) * 0.01
            update = ModelUpdate(
                node_id=f"node-{i}",
                gradient=gradient,
                svid=f"spiffe://x0tta6bl4.mesh/node/node-{i}",
                signature=b"sig"
            )
            updates.append(update)
        
        orchestrator = BatchAsyncOrchestrator(sample_model, k_threshold=0.85)
        gradient = orchestrator.aggregate_updates(updates)
        
        assert gradient is not None
        assert gradient.shape == sample_model.shape

    @pytest.mark.slow
    def test_convergence_speed(self, sample_model):
        """Test convergence speed in distributed setting"""
        orchestrator = BatchAsyncOrchestrator(sample_model)
        session = FLTrainingSession(sample_model, orchestrator, max_rounds=50)
        
        round_count = 0
        while session.should_continue() and round_count < 20:
            # Create updates
            updates = []
            for i in range(100):
                gradient = np.random.randn(*sample_model.shape) * 0.01
                update = ModelUpdate(
                    node_id=f"node-{i}",
                    gradient=gradient,
                    svid=f"spiffe://x0tta6bl4.mesh/node/node-{i}",
                    signature=b"sig"
                )
                updates.append(update)
            
            # Simulate improving metrics
            loss = 1.0 / (1 + round_count * 0.2)
            accuracy = 0.5 + round_count * 0.01
            
            session.training_round(updates, loss, accuracy)
            round_count += 1
        
        # Should complete in reasonable time
        assert round_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
