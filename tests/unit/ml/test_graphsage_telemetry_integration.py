"""
Integration tests: GraphSAGE + MeshTelemetry + MAPE-K wiring.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.ml.graphsage_anomaly_detector import (
    GraphSAGEAnomalyDetector,
    create_graphsage_detector_for_mapek,
)
from src.ml.mesh_telemetry import (
    MeshTelemetryGenerator,
    ScenarioType,
    generate_training_data,
    FEATURE_NAMES,
)


class TestTrainFromTelemetry:
    """Tests for GraphSAGEAnomalyDetector.train_from_telemetry()."""

    def test_train_from_telemetry_runs_without_error(self):
        detector = GraphSAGEAnomalyDetector()
        # Should not raise even if torch is not available (falls back gracefully)
        detector.train_from_telemetry(
            num_snapshots=10,
            nodes_per_snapshot=5,
            epochs=2,
            seed=42,
        )

    def test_labels_provided_from_telemetry(self):
        """Telemetry provides ground truth labels, not rule-based fallback."""
        features, edges, labels = generate_training_data(
            num_snapshots=20, nodes_per_snapshot=10, anomaly_ratio=0.3, seed=42
        )
        # Labels come from telemetry generator, should have some anomalies
        assert any(l > 0.5 for l in labels)
        assert any(l <= 0.5 for l in labels)
        assert len(features) == 200
        assert len(labels) == 200


class TestCreateDetectorForMapek:
    def test_factory_returns_detector(self):
        detector = create_graphsage_detector_for_mapek()
        assert isinstance(detector, GraphSAGEAnomalyDetector)
        assert detector.input_dim == 8
        assert detector.hidden_dim == 64
        assert detector.anomaly_threshold == 0.6

    def test_factory_no_pretrain_by_default(self):
        detector = create_graphsage_detector_for_mapek()
        # Without pretrain, is_trained should be False (or model is None in fallback)
        if detector.model is not None:
            assert detector.is_trained is False

    def test_factory_pretrain_flag(self):
        # With pretrain=True, training runs (may set is_trained if torch available)
        detector = create_graphsage_detector_for_mapek(
            pretrain=True, num_snapshots=5, epochs=1
        )
        assert isinstance(detector, GraphSAGEAnomalyDetector)


class TestGenerateLabelsQuality:
    """Tests that the rule-based labeler has reasonable quality."""

    def setup_method(self):
        self.detector = GraphSAGEAnomalyDetector()
        self.gen = MeshTelemetryGenerator(seed=42)

    def test_normal_low_false_positive_rate(self):
        """Normal scenario should have < 10% FPR."""
        snapshots = [self.gen._generate_snapshot(20, ScenarioType.NORMAL) for _ in range(50)]
        fp = sum(
            1 for snap in snapshots
            for pred, actual in zip(self.detector._generate_labels(snap.node_features), snap.labels)
            if pred > 0.5 and actual <= 0.5
        )
        total_normal = sum(
            1 for snap in snapshots for l in snap.labels if l <= 0.5
        )
        fpr = fp / total_normal if total_normal > 0 else 0.0
        assert fpr < 0.10, f"Normal FPR too high: {fpr:.1%}"

    def test_partition_high_recall(self):
        """Partition anomalies should be detected with high recall."""
        snapshots = [self.gen._generate_snapshot(20, ScenarioType.PARTITION) for _ in range(50)]
        tp = fn = 0
        for snap in snapshots:
            predicted = self.detector._generate_labels(snap.node_features)
            for pred, actual in zip(predicted, snap.labels):
                if actual > 0.5:
                    if pred > 0.5:
                        tp += 1
                    else:
                        fn += 1
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert recall >= 0.90, f"Partition recall too low: {recall:.1%}"

    def test_node_overload_high_recall(self):
        """Node overload should be detected with high recall."""
        snapshots = [self.gen._generate_snapshot(20, ScenarioType.NODE_OVERLOAD) for _ in range(50)]
        tp = fn = 0
        for snap in snapshots:
            predicted = self.detector._generate_labels(snap.node_features)
            for pred, actual in zip(predicted, snap.labels):
                if actual > 0.5:
                    if pred > 0.5:
                        tp += 1
                    else:
                        fn += 1
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert recall >= 0.80, f"Node overload recall too low: {recall:.1%}"

    def test_interference_detected(self):
        """Interference scenario should have non-zero recall."""
        snapshots = [self.gen._generate_snapshot(20, ScenarioType.INTERFERENCE) for _ in range(50)]
        tp = fn = 0
        for snap in snapshots:
            predicted = self.detector._generate_labels(snap.node_features)
            for pred, actual in zip(predicted, snap.labels):
                if actual > 0.5:
                    if pred > 0.5:
                        tp += 1
                    else:
                        fn += 1
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert recall > 0.30, f"Interference recall too low: {recall:.1%}"


class TestMapekDispatcherWiring:
    """Test that MAPE-K execute phase dispatches DAO actions."""

    @pytest.mark.asyncio
    async def test_execute_dispatches_dao_actions(self):
        from src.dao.governance import ActionDispatcher, ActionResult

        dispatcher = ActionDispatcher()
        # Mock a minimal MAPEKLoop-like execute
        dao_actions = [
            {"type": "restart_node", "node_id": "node-5"},
            {"type": "rotate_keys", "scope": "all"},
        ]
        results = []
        for action in dao_actions:
            result = dispatcher.dispatch(action)
            results.append(result)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True

    @pytest.mark.asyncio
    async def test_mapek_loop_accepts_dispatcher(self):
        """MAPEKLoop constructor accepts action_dispatcher parameter."""
        from src.dao.governance import ActionDispatcher

        # Patch all dependencies
        with patch("src.core.mape_k_loop.ConsciousnessEngine"), \
             patch("src.core.mape_k_loop.MeshNetworkManager"), \
             patch("src.core.mape_k_loop.PrometheusExporter"), \
             patch("src.core.mape_k_loop.ZeroTrustValidator"):
            from src.core.mape_k_loop import MAPEKLoop
            loop = MAPEKLoop(
                consciousness_engine=MagicMock(),
                mesh_manager=MagicMock(),
                prometheus=MagicMock(),
                zero_trust=MagicMock(),
                action_dispatcher=ActionDispatcher(),
            )
            assert loop.action_dispatcher is not None
