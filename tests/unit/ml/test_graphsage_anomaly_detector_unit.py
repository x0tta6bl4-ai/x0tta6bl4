"""
Comprehensive unit tests for src/ml/graphsage_anomaly_detector.py

Covers:
- AnomalyPrediction dataclass
- GraphSAGEAnomalyDetector: __init__, train, predict (trained & untrained paths),
  predict_with_causal, explain_anomaly, save_model, load_model, train_from_telemetry
- GraphSAGEAnomalyDetectorV2: forward, prepare_for_quantization, convert_to_int8
- Private helpers: _features_to_tensor, _edges_to_tensor, _generate_labels, _score_to_severity
- create_graphsage_detector_for_mapek factory
- Edge cases: empty data, missing features, no-torch fallback, error paths
"""

import time
from dataclasses import asdict
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.ml.graphsage_anomaly_detector import (
    AnomalyPrediction,
    GraphSAGEAnomalyDetector,
    create_graphsage_detector_for_mapek,
    is_torch_available,
    is_quantization_available,
    get_model_class)

def get_torch():
    import torch
    return torch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normal_features():
    """Return healthy node features (all within normal ranges)."""
    return {
        "rssi": -50.0,
        "snr": 20.0,
        "loss_rate": 0.01,
        "link_age": 3600.0,
        "latency": 10.0,
        "throughput": 80.0,
        "cpu": 0.3,
        "memory": 0.4,
    }


def _anomalous_features():
    """Return clearly anomalous node features that trigger multiple signals."""
    return {
        "rssi": -92.0,
        "snr": 3.0,
        "loss_rate": 0.55,
        "link_age": 5.0,
        "latency": 250.0,
        "throughput": 1.0,
        "cpu": 0.96,
        "memory": 0.97,
    }


def _make_detector(**kwargs):
    """Create detector without quantization for faster tests."""
    kwargs.setdefault("use_quantization", False)
    return GraphSAGEAnomalyDetector(**kwargs)


def _make_neighbors(count=3):
    """Create a list of (neighbor_id, features) tuples with normal values."""
    neighbors = []
    for i in range(count):
        neighbors.append(
            (
                f"neighbor-{i}",
                {
                    "rssi": -55.0 - i,
                    "snr": 18.0 - i,
                    "loss_rate": 0.02 + 0.01 * i,
                    "link_age": 3000.0,
                    "latency": 12.0,
                    "throughput": 70.0,
                    "cpu": 0.35,
                    "memory": 0.45,
                },
            )
        )
    return neighbors


def _train_detector_briefly(det, epochs=3):
    """Train a detector with minimal data so is_trained becomes True."""
    features = [_normal_features(), _anomalous_features(), _normal_features()]
    edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
    det.train(node_features=features, edge_index=edges, epochs=epochs)
    return det


# ---------------------------------------------------------------------------
# AnomalyPrediction dataclass
# ---------------------------------------------------------------------------


class TestAnomalyPredictionDataclass:
    def test_create_anomaly_prediction(self):
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=0.85,
            confidence=0.70,
            node_id="node-1",
            features={"rssi": -60.0},
            inference_time_ms=4.5,
        )
        assert pred.is_anomaly is True
        assert pred.anomaly_score == 0.85
        assert pred.confidence == 0.70
        assert pred.node_id == "node-1"
        assert pred.features == {"rssi": -60.0}
        assert pred.inference_time_ms == 4.5

    def test_create_normal_prediction(self):
        pred = AnomalyPrediction(
            is_anomaly=False,
            anomaly_score=0.15,
            confidence=0.70,
            node_id="node-2",
            features={},
            inference_time_ms=2.1,
        )
        assert pred.is_anomaly is False
        assert pred.anomaly_score < 0.5

    def test_asdict_conversion(self):
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=0.9,
            confidence=0.8,
            node_id="x",
            features={"cpu": 0.95},
            inference_time_ms=1.0,
        )
        d = asdict(pred)
        assert isinstance(d, dict)
        assert d["node_id"] == "x"
        assert d["is_anomaly"] is True
        assert d["anomaly_score"] == 0.9

    def test_boundary_score_zero(self):
        pred = AnomalyPrediction(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=1.0,
            node_id="z",
            features={},
            inference_time_ms=0.1,
        )
        assert pred.anomaly_score == 0.0

    def test_boundary_score_one(self):
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=1.0,
            confidence=1.0,
            node_id="max",
            features={},
            inference_time_ms=0.1,
        )
        assert pred.anomaly_score == 1.0

    def test_prediction_with_empty_features(self):
        pred = AnomalyPrediction(
            is_anomaly=False,
            anomaly_score=0.2,
            confidence=0.6,
            node_id="empty",
            features={},
            inference_time_ms=0.5,
        )
        assert pred.features == {}

    def test_prediction_with_many_features(self):
        features = {f"feat_{i}": float(i) for i in range(20)}
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=0.7,
            confidence=0.4,
            node_id="multi",
            features=features,
            inference_time_ms=3.2,
        )
        assert len(pred.features) == 20


# ---------------------------------------------------------------------------
# GraphSAGEAnomalyDetector initialization
# ---------------------------------------------------------------------------


class TestDetectorInit:
    def test_default_parameters(self):
        det = _make_detector()
        assert det.input_dim == 8
        assert det.hidden_dim == 64
        assert det.num_layers == 2
        assert det.anomaly_threshold == 0.6

    def test_custom_parameters(self):
        det = _make_detector(
            input_dim=16,
            hidden_dim=128,
            num_layers=3,
            anomaly_threshold=0.75,
        )
        assert det.input_dim == 16
        assert det.hidden_dim == 128
        assert det.num_layers == 3
        assert det.anomaly_threshold == 0.75

    def test_recall_precision_defaults(self):
        det = _make_detector()
        assert det.recall == 0.96
        assert det.precision == 0.98

    def test_device_is_cpu(self):
        det = _make_detector()
        det._init_model_if_needed()
        assert det.device is not None
        assert str(det.device) == "cpu"

    def test_model_initially_none(self):
        det = _make_detector()
        assert det.model is None

    def test_model_is_initialized_lazy(self):
        det = _make_detector()
        det._init_model_if_needed()
        assert det.model is not None
        # Check if it has forward method (base nn.Module check)
        assert hasattr(det.model, 'forward')

    def test_is_trained_false_initially(self):
        det = _make_detector()
        assert det.is_trained is False

    def test_no_torch_fallback(self):
        """When torch is not available, model and device are None."""
        with patch("src.ml.graphsage_anomaly_detector.is_torch_available", return_value=False):
            det = GraphSAGEAnomalyDetector()
            assert det.model is None
            assert det.device is None

    def test_quantization_disabled_explicitly(self):
        det = _make_detector(use_quantization=False)
        assert det.use_quantization is False

    def test_quantization_enabled(self):
        det = GraphSAGEAnomalyDetector(use_quantization=True)
        assert det.use_quantization is True

    def test_quantization_disabled_when_not_available(self):
        """use_quantization=True but is_quantization_available()=False -> False."""
        with patch("src.ml.graphsage_anomaly_detector.is_quantization_available", return_value=False):
            det = GraphSAGEAnomalyDetector(use_quantization=True)
            assert det.use_quantization is False

    def test_causal_engine_initialized_when_available(self):
        """When CAUSAL_ANALYSIS_AVAILABLE is True, causal_engine should be set."""
        det = _make_detector()
        # In our test environment, causal analysis may or may not be available;
        # just check the attribute exists
        assert hasattr(det, "causal_engine")

    def test_causal_engine_none_when_not_available(self):
        with patch(
            "src.ml.graphsage_anomaly_detector._ensure_causal", return_value=False
        ):
            det = _make_detector()
            assert det.causal_engine is None

    def test_causal_engine_error_handled(self):
        """If CausalAnalysisEngine init raises, causal_engine is None."""
        with (
            patch("src.ml.graphsage_anomaly_detector._ensure_causal", return_value=True),
            patch(
                "src.ml.causal_analysis.CausalAnalysisEngine",
                side_effect=RuntimeError("init failed"),
            ),
        ):
            det = _make_detector()
            assert det.causal_engine is None


# ---------------------------------------------------------------------------
# _features_to_tensor
# ---------------------------------------------------------------------------


class TestFeaturesToTensor:
    def test_full_features(self):
        det = _make_detector()
        tensor = det._features_to_tensor([_normal_features()])
        assert tensor.shape == (1, 8)
        assert tensor.dtype == get_torch().float

    def test_missing_features_default_to_zero(self):
        det = _make_detector()
        tensor = det._features_to_tensor([{"rssi": -60.0}])
        assert tensor.shape == (1, 8)
        assert tensor[0][0].item() == -60.0
        for i in range(1, 8):
            assert tensor[0][i].item() == 0.0

    def test_empty_features_dict(self):
        det = _make_detector()
        tensor = det._features_to_tensor([{}])
        assert tensor.shape == (1, 8)
        assert get_torch().all(tensor == 0.0)

    def test_multiple_nodes(self):
        det = _make_detector()
        tensor = det._features_to_tensor([_normal_features(), _anomalous_features()])
        assert tensor.shape == (2, 8)

    def test_extra_features_ignored(self):
        det = _make_detector()
        features = _normal_features()
        features["extra_field"] = 999.0
        tensor = det._features_to_tensor([features])
        assert tensor.shape == (1, 8)

    def test_feature_ordering(self):
        """Features follow canonical order: rssi, snr, loss_rate, link_age, latency, throughput, cpu, memory."""
        det = _make_detector()
        features = {
            "rssi": 1.0,
            "snr": 2.0,
            "loss_rate": 3.0,
            "link_age": 4.0,
            "latency": 5.0,
            "throughput": 6.0,
            "cpu": 7.0,
            "memory": 8.0,
        }
        tensor = det._features_to_tensor([features])
        for i in range(8):
            assert tensor[0][i].item() == float(i + 1)

    def test_empty_list_returns_empty_tensor(self):
        det = _make_detector()
        tensor = det._features_to_tensor([])
        assert tensor.numel() == 0

    def test_torch_none_returns_none(self):
        """When torch is None, _features_to_tensor returns None."""
        det = _make_detector()
        with patch("src.ml.graphsage_anomaly_detector._ensure_torch", return_value={"available": False}):
            result = det._features_to_tensor([_normal_features()])
            assert result is None


# ---------------------------------------------------------------------------
# _edges_to_tensor
# ---------------------------------------------------------------------------


class TestEdgesToTensor:
    def test_basic_edges(self):
        det = _make_detector()
        tensor = det._edges_to_tensor([(0, 1), (1, 0)])
        assert tensor.shape == (2, 2)
        assert tensor.dtype == get_torch().long

    def test_empty_edges(self):
        det = _make_detector()
        tensor = det._edges_to_tensor([])
        assert tensor.shape == (2, 0)

    def test_single_edge(self):
        det = _make_detector()
        tensor = det._edges_to_tensor([(0, 1)])
        assert tensor.shape == (2, 1)
        assert tensor[0][0].item() == 0
        assert tensor[1][0].item() == 1

    def test_multiple_edges_transposed_correctly(self):
        det = _make_detector()
        edges = [(0, 1), (0, 2), (1, 2)]
        tensor = det._edges_to_tensor(edges)
        assert tensor.shape == (2, 3)
        assert tensor[0].tolist() == [0, 0, 1]
        assert tensor[1].tolist() == [1, 2, 2]

    def test_torch_none_returns_none(self):
        det = _make_detector()
        with patch("src.ml.graphsage_anomaly_detector._ensure_torch", return_value={"available": False}):
            result = det._edges_to_tensor([(0, 1)])
            assert result is None


# ---------------------------------------------------------------------------
# _generate_labels (multi-signal scoring)
# ---------------------------------------------------------------------------


class TestGenerateLabels:
    def test_healthy_node_label_zero(self):
        det = _make_detector()
        labels = det._generate_labels([_normal_features()])
        assert labels == [0.0]

    def test_anomalous_node_label_one(self):
        det = _make_detector()
        labels = det._generate_labels([_anomalous_features()])
        assert labels == [1.0]

    def test_mixed_nodes(self):
        det = _make_detector()
        labels = det._generate_labels([_normal_features(), _anomalous_features()])
        assert labels == [0.0, 1.0]

    def test_empty_list(self):
        det = _make_detector()
        assert det._generate_labels([]) == []

    def test_empty_dict_uses_defaults_healthy(self):
        det = _make_detector()
        assert det._generate_labels([{}]) == [0.0]

    def test_weak_rssi_alone_not_anomaly(self):
        """RSSI < -80 adds 0.30 but alone is not enough (need >= 0.50)."""
        det = _make_detector()
        f = _normal_features()
        f["rssi"] = -85.0
        assert det._generate_labels([f]) == [0.0]

    def test_moderate_rssi_adds_small_score(self):
        """RSSI between -80 and -70 adds 0.10."""
        det = _make_detector()
        f = _normal_features()
        f["rssi"] = -75.0
        assert det._generate_labels([f]) == [0.0]

    def test_low_snr_alone_not_anomaly(self):
        """SNR < 8 adds 0.25 alone."""
        det = _make_detector()
        f = _normal_features()
        f["snr"] = 5.0
        assert det._generate_labels([f]) == [0.0]

    def test_moderate_snr_adds_small_score(self):
        """SNR between 8 and 12 adds 0.10."""
        det = _make_detector()
        f = _normal_features()
        f["snr"] = 10.0
        assert det._generate_labels([f]) == [0.0]

    def test_high_loss_rate_alone_not_anomaly(self):
        """loss_rate > 0.15 adds 0.35 alone."""
        det = _make_detector()
        f = _normal_features()
        f["loss_rate"] = 0.20
        assert det._generate_labels([f]) == [0.0]

    def test_moderate_loss_rate(self):
        """loss_rate between 0.05 and 0.15 adds 0.15."""
        det = _make_detector()
        f = _normal_features()
        f["loss_rate"] = 0.10
        assert det._generate_labels([f]) == [0.0]

    def test_resource_exhaustion_cpu(self):
        """CPU > 0.85 adds 0.25."""
        det = _make_detector()
        f = _normal_features()
        f["cpu"] = 0.90
        assert det._generate_labels([f]) == [0.0]

    def test_resource_exhaustion_memory(self):
        """Memory > 0.85 adds 0.25."""
        det = _make_detector()
        f = _normal_features()
        f["memory"] = 0.90
        assert det._generate_labels([f]) == [0.0]

    def test_latency_spike_high(self):
        """Latency > 100 adds 0.25."""
        det = _make_detector()
        f = _normal_features()
        f["latency"] = 150.0
        assert det._generate_labels([f]) == [0.0]

    def test_latency_spike_moderate(self):
        """Latency between 40 and 100 adds 0.10."""
        det = _make_detector()
        f = _normal_features()
        f["latency"] = 50.0
        assert det._generate_labels([f]) == [0.0]

    def test_throughput_collapse(self):
        """Throughput < 2 adds 0.20."""
        det = _make_detector()
        f = _normal_features()
        f["throughput"] = 1.0
        assert det._generate_labels([f]) == [0.0]

    def test_link_flapping(self):
        """Link age < 10 adds 0.15."""
        det = _make_detector()
        f = _normal_features()
        f["link_age"] = 5.0
        assert det._generate_labels([f]) == [0.0]

    def test_correlated_interference_pattern(self):
        """SNR < 15 + throughput < 30 + RSSI > -75 adds bonus 0.15."""
        det = _make_detector()
        f = _normal_features()
        f["snr"] = 10.0  # < 15 (also < 12: +0.10)
        f["throughput"] = 20.0  # < 30
        f["rssi"] = -50.0  # > -75
        # Score: snr < 12 = 0.10, correlated = 0.15, total 0.25 < 0.50
        assert det._generate_labels([f]) == [0.0]

    def test_cascade_pattern(self):
        """Latency > 30 + loss_rate > 0.03 adds bonus 0.10."""
        det = _make_detector()
        f = _normal_features()
        f["latency"] = 50.0  # > 30 and > 40: +0.10
        f["loss_rate"] = 0.10  # > 0.03 and > 0.05: +0.15
        # Score: 0.10 + 0.15 + 0.10 = 0.35 < 0.50
        assert det._generate_labels([f]) == [0.0]

    def test_combined_anomaly_triggers(self):
        """Multiple signals together cross the 0.50 threshold."""
        det = _make_detector()
        features = {
            "rssi": -85.0,  # 0.30
            "snr": 5.0,  # 0.25
            "loss_rate": 0.20,  # 0.35
            "link_age": 5.0,  # 0.15
            "latency": 150.0,  # 0.25
            "throughput": 1.0,  # 0.20
            "cpu": 0.90,  # 0.25
            "memory": 0.40,  # 0
        }
        assert det._generate_labels([features]) == [1.0]

    def test_just_above_threshold(self):
        """Features that produce score exactly at 0.50 should be anomalous."""
        det = _make_detector()
        # rssi < -80 = 0.30, loss_rate > 0.15 = 0.35 -> 0.65 >= 0.50
        features = _normal_features()
        features["rssi"] = -85.0
        features["loss_rate"] = 0.20
        assert det._generate_labels([features]) == [1.0]

    def test_just_below_threshold(self):
        """Features that produce score just under 0.50."""
        det = _make_detector()
        # rssi < -80 = 0.30, throughput < 2 = 0.20 -> 0.50... wait that's exactly 0.50
        # Actually: >=0.50 is anomaly, so 0.50 = anomaly. Use 0.45 instead.
        # rssi < -80 = 0.30, link_age < 10 = 0.15 -> 0.45 < 0.50
        features = _normal_features()
        features["rssi"] = -85.0
        features["link_age"] = 5.0
        assert det._generate_labels([features]) == [0.0]

    def test_many_nodes(self):
        det = _make_detector()
        nodes = [_normal_features() for _ in range(50)]
        labels = det._generate_labels(nodes)
        assert len(labels) == 50
        assert all(l == 0.0 for l in labels)


# ---------------------------------------------------------------------------
# _score_to_severity
# ---------------------------------------------------------------------------


class TestScoreToSeverity:
    def test_critical_severity(self):
        det = _make_detector()
        result = det._score_to_severity(0.95)
        assert result is not None
        assert result.name == "CRITICAL"

    def test_high_severity(self):
        det = _make_detector()
        assert det._score_to_severity(0.75).name == "HIGH"

    def test_medium_severity(self):
        det = _make_detector()
        assert det._score_to_severity(0.55).name == "MEDIUM"

    def test_low_severity(self):
        det = _make_detector()
        assert det._score_to_severity(0.3).name == "LOW"

    def test_boundary_0_9(self):
        det = _make_detector()
        assert det._score_to_severity(0.9).name == "CRITICAL"

    def test_boundary_0_7(self):
        det = _make_detector()
        assert det._score_to_severity(0.7).name == "HIGH"

    def test_boundary_0_5(self):
        det = _make_detector()
        assert det._score_to_severity(0.5).name == "MEDIUM"

    def test_boundary_just_below_0_5(self):
        det = _make_detector()
        assert det._score_to_severity(0.49).name == "LOW"

    def test_score_zero(self):
        det = _make_detector()
        assert det._score_to_severity(0.0).name == "LOW"

    def test_returns_none_when_causal_not_available(self):
        with patch(
            "src.ml.graphsage_anomaly_detector._ensure_causal", return_value=False
        ):
            det = _make_detector()
            assert det._score_to_severity(0.95) is None
            assert det._score_to_severity(0.5) is None


# ---------------------------------------------------------------------------
# train method
# ---------------------------------------------------------------------------


class TestTrainMethod:
    def test_train_empty_features_returns_early(self):
        det = _make_detector()
        det.train(node_features=[], edge_index=[])
        assert det.is_trained is False

    def test_train_empty_edges_returns_early(self):
        det = _make_detector()
        det.train(node_features=[_normal_features()], edge_index=[])
        assert det.is_trained is False

    def test_train_none_data_returns_early(self):
        det = _make_detector()
        det.train(node_features=None, edge_index=None)
        assert det.is_trained is False

    def test_train_no_torch_returns_early(self):
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            det.train(
                node_features=[_normal_features()],
                edge_index=[(0, 1)],
            )
            assert not getattr(det, "is_trained", False)

    def test_train_model_none_returns_early(self):
        det = _make_detector()
        det.model = None
        det.train(
            node_features=[_normal_features()],
            edge_index=[(0, 1)],
        )
        assert det.is_trained is False

    def test_train_basic_success(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features()]
        edges = [(0, 1), (1, 0)]
        det.train(node_features=features, edge_index=edges, epochs=2, lr=0.01)
        assert det.is_trained is True

    def test_train_with_explicit_labels(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features()]
        edges = [(0, 1), (1, 0)]
        det.train(node_features=features, edge_index=edges, labels=[0.0, 1.0], epochs=2)
        assert det.is_trained is True

    def test_train_auto_labels_when_none(self):
        """When labels=None, _generate_labels is called."""
        det = _make_detector()
        features = [_normal_features(), _anomalous_features(), _normal_features()]
        edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
        det.train(node_features=features, edge_index=edges, labels=None, epochs=2)
        assert det.is_trained is True

    def test_train_with_quantization(self):
        """Quantization conversion happens after training when enabled."""
        det = GraphSAGEAnomalyDetector(use_quantization=True)
        features = [_normal_features(), _anomalous_features()]
        edges = [(0, 1), (1, 0)]
        det.train(node_features=features, edge_index=edges, epochs=2)
        assert det.is_trained is True

    def test_train_custom_lr_and_epochs(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features()]
        edges = [(0, 1), (1, 0)]
        det.train(node_features=features, edge_index=edges, epochs=5, lr=0.01)
        assert det.is_trained is True

    def test_train_three_nodes(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features(), _normal_features()]
        edges = [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)]
        det.train(node_features=features, edge_index=edges, epochs=2)
        assert det.is_trained is True


# ---------------------------------------------------------------------------
# predict method - untrained path
# ---------------------------------------------------------------------------


class TestPredictUntrained:
    """Tests for predict when is_trained is False (uses _generate_labels fallback)."""

    def test_predict_returns_anomaly_prediction(self):
        det = _make_detector()
        assert det.is_trained is False
        pred = det.predict(
            node_id="test",
            node_features=_normal_features(),
            neighbors=_make_neighbors(2),
        )
        assert isinstance(pred, AnomalyPrediction)
        assert pred.node_id == "test"

    def test_predict_normal_features_not_anomaly(self):
        det = _make_detector()
        pred = det.predict(
            node_id="n1",
            node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly is False
        assert pred.anomaly_score == 0.0
        assert pred.confidence == 0.8

    def test_predict_anomalous_features_is_anomaly(self):
        det = _make_detector()
        pred = det.predict(
            node_id="a1",
            node_features=_anomalous_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly is True
        assert pred.anomaly_score == 1.0
        assert pred.confidence == 0.8

    def test_predict_features_passed_through(self):
        det = _make_detector()
        features = _normal_features()
        pred = det.predict(
            node_id="f1",
            node_features=features,
            neighbors=[],
        )
        assert pred.features == features

    def test_predict_inference_time_nonnegative(self):
        det = _make_detector()
        pred = det.predict(
            node_id="t1",
            node_features=_normal_features(),
            neighbors=[],
        )
        assert pred.inference_time_ms >= 0.0

    def test_predict_no_neighbors(self):
        det = _make_detector()
        pred = det.predict(
            node_id="lone",
            node_features=_normal_features(),
            neighbors=[],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert pred.node_id == "lone"

    def test_predict_does_not_call_metrics_when_untrained(self):
        """Untrained path returns before record_graphsage_inference is called."""
        with patch(
            "src.ml.graphsage_anomaly_detector.record_graphsage_inference"
        ) as mock_rec:
            det = _make_detector()
            det.predict(
                node_id="m",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            mock_rec.assert_not_called()


# ---------------------------------------------------------------------------
# predict method - no model / no torch fallback
# ---------------------------------------------------------------------------


class TestPredictNoModel:
    def test_predict_model_none_returns_fallback(self):
        """When model is None, returns non-anomaly prediction."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            pred = det.predict(
                node_id="no-model",
                node_features=_normal_features(),
                neighbors=[],
            )
            assert pred.is_anomaly is False
            assert pred.anomaly_score == 0.0
            assert pred.confidence == 0.8
            assert pred.inference_time_ms >= 0.0


# ---------------------------------------------------------------------------
# predict method - trained path
# ---------------------------------------------------------------------------


class TestPredictTrained:
    """Tests for predict after model has been trained (uses model inference)."""

    def test_predict_after_training(self):
        det = _make_detector()
        _train_detector_briefly(det)
        assert det.is_trained is True

        pred = det.predict(
            node_id="trained-pred",
            node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert 0.0 <= pred.anomaly_score <= 1.0
        assert 0.0 <= pred.confidence <= 1.0

    def test_predict_confidence_formula_trained(self):
        """Confidence = abs(score - 0.5) * 2 in trained path."""
        det = _make_detector()
        _train_detector_briefly(det)

        pred = det.predict(
            node_id="c",
            node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        expected = abs(pred.anomaly_score - 0.5) * 2
        assert abs(pred.confidence - expected) < 1e-6

    def test_predict_anomaly_flag_based_on_threshold(self):
        det = _make_detector()
        _train_detector_briefly(det)

        pred = det.predict(
            node_id="t",
            node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly == (pred.anomaly_score >= det.anomaly_threshold)

    def test_predict_records_metrics_when_trained(self):
        """record_graphsage_inference is called on the trained path."""
        with patch(
            "src.ml.graphsage_anomaly_detector.record_graphsage_inference"
        ) as mock_rec:
            det = _make_detector()
            _train_detector_briefly(det)
            det.predict(
                node_id="m",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            mock_rec.assert_called_once()
            args = mock_rec.call_args[0]
            assert args[0] >= 0  # inference_time
            assert isinstance(args[1], bool)  # is_anomaly
            assert args[2] in ("CRITICAL", "NORMAL")

    def test_predict_auto_generates_edge_index(self):
        det = _make_detector()
        _train_detector_briefly(det)
        pred = det.predict(
            node_id="n1",
            node_features=_normal_features(),
            neighbors=_make_neighbors(3),
            edge_index=None,
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_predict_with_explicit_edge_index(self):
        det = _make_detector()
        _train_detector_briefly(det)
        pred = det.predict(
            node_id="n1",
            node_features=_normal_features(),
            neighbors=_make_neighbors(2),
            edge_index=[(0, 1), (1, 0), (0, 2), (2, 0)],
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_predict_severity_critical_or_normal(self):
        """Severity string passed to record is CRITICAL if anomaly, else NORMAL."""
        with patch(
            "src.ml.graphsage_anomaly_detector.record_graphsage_inference"
        ) as mock_rec:
            det = _make_detector()
            _train_detector_briefly(det)
            det.predict(
                node_id="s",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            severity = mock_rec.call_args[0][2]
            assert severity in ("CRITICAL", "NORMAL")


# ---------------------------------------------------------------------------
# predict_with_causal
# ---------------------------------------------------------------------------


class TestPredictWithCausal:
    def test_returns_tuple_of_two(self):
        det = _make_detector()
        result = det.predict_with_causal(
            node_id="c1",
            node_features=_normal_features(),
            neighbors=_make_neighbors(2),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        pred, causal = result
        assert isinstance(pred, AnomalyPrediction)

    def test_no_anomaly_returns_none_causal(self):
        """When prediction is not anomaly, causal result is None."""
        det = _make_detector()
        with patch.object(
            det,
            "predict",
            return_value=AnomalyPrediction(
                is_anomaly=False,
                anomaly_score=0.1,
                confidence=0.8,
                node_id="safe",
                features=_normal_features(),
                inference_time_ms=1.0,
            ),
        ):
            pred, causal = det.predict_with_causal(
                node_id="safe",
                node_features=_normal_features(),
                neighbors=_make_neighbors(2),
            )
        assert pred.is_anomaly is False
        assert causal is None

    def test_anomaly_with_causal_engine_none(self):
        """When causal_engine is None, causal result is None."""
        det = _make_detector()
        det.causal_engine = None
        # Mock predict to return an anomaly
        with patch.object(
            det,
            "predict",
            return_value=AnomalyPrediction(
                is_anomaly=True,
                anomaly_score=0.9,
                confidence=0.8,
                node_id="no-causal",
                features=_anomalous_features(),
                inference_time_ms=1.0,
            ),
        ):
            pred, causal = det.predict_with_causal(
                node_id="no-causal",
                node_features=_anomalous_features(),
                neighbors=_make_neighbors(1),
            )
        assert pred.is_anomaly is True
        assert causal is None

    def test_anomaly_with_causal_engine_error(self):
        """When causal engine raises, returns (prediction, None)."""
        det = _make_detector()
        mock_engine = MagicMock()
        mock_engine.analyze.side_effect = RuntimeError("analysis failed")
        det.causal_engine = mock_engine

        with patch.object(
            det,
            "predict",
            return_value=AnomalyPrediction(
                is_anomaly=True,
                anomaly_score=0.9,
                confidence=0.8,
                node_id="err",
                features=_anomalous_features(),
                inference_time_ms=1.0,
            ),
        ):
            pred, causal = det.predict_with_causal(
                node_id="err",
                node_features=_anomalous_features(),
                neighbors=_make_neighbors(1),
            )
        assert pred.is_anomaly is True
        assert causal is None

    def test_anomaly_triggers_causal_analysis(self):
        """When anomaly detected and causal engine present, analysis runs."""
        det = _make_detector()

        mock_result = MagicMock()
        mock_result.root_causes = ["cause1"]
        mock_result.confidence = 0.85

        mock_engine = MagicMock()
        mock_engine.analyze.return_value = mock_result
        det.causal_engine = mock_engine

        with patch.object(
            det,
            "predict",
            return_value=AnomalyPrediction(
                is_anomaly=True,
                anomaly_score=0.9,
                confidence=0.8,
                node_id="anom",
                features=_anomalous_features(),
                inference_time_ms=1.0,
            ),
        ):
            pred, causal = det.predict_with_causal(
                node_id="anom",
                node_features=_anomalous_features(),
                neighbors=_make_neighbors(1),
            )
        assert pred.is_anomaly is True
        assert causal is mock_result
        mock_engine.add_incident.assert_called_once()
        mock_engine.analyze.assert_called_once()

    def test_causal_not_available_returns_none(self):
        """When causal analysis is not available, no causal analysis."""
        with patch(
            "src.ml.graphsage_anomaly_detector._ensure_causal", return_value=False
        ):
            det = _make_detector()
            det.causal_engine = MagicMock()
            with patch.object(
                det,
                "predict",
                return_value=AnomalyPrediction(
                    is_anomaly=True,
                    anomaly_score=0.9,
                    confidence=0.8,
                    node_id="nc",
                    features=_anomalous_features(),
                    inference_time_ms=1.0,
                ),
            ):
                pred, causal = det.predict_with_causal(
                    node_id="nc",
                    node_features=_anomalous_features(),
                    neighbors=_make_neighbors(1),
                )
            assert causal is None

    def test_causal_analysis_uses_score_to_severity(self):
        """Causal analysis creates IncidentEvent with severity from _score_to_severity."""
        det = _make_detector()

        mock_result = MagicMock()
        mock_result.root_causes = []
        mock_result.confidence = 0.5

        mock_engine = MagicMock()
        mock_engine.analyze.return_value = mock_result
        det.causal_engine = mock_engine

        with (
            patch.object(
                det,
                "predict",
                return_value=AnomalyPrediction(
                    is_anomaly=True,
                    anomaly_score=0.95,
                    confidence=0.9,
                    node_id="sev",
                    features=_anomalous_features(),
                    inference_time_ms=1.0,
                ),
            ),
            patch("src.ml.causal_analysis.IncidentEvent") as MockIncident,
        ):
            det.predict_with_causal(
                node_id="sev",
                node_features=_anomalous_features(),
                neighbors=[],
            )
            # Check IncidentEvent was created
            MockIncident.assert_called_once()


# ---------------------------------------------------------------------------
# explain_anomaly
# ---------------------------------------------------------------------------


class TestExplainAnomaly:
    def test_shap_not_available_returns_empty(self):
        with patch("src.ml.graphsage_anomaly_detector._ensure_shap", return_value=False):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e1",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}

    def test_model_none_returns_empty(self):
        with patch("src.ml.graphsage_anomaly_detector.is_torch_available", return_value=False):
            det = GraphSAGEAnomalyDetector()
            result = det.explain_anomaly(
                node_id="e2",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}

    def test_exception_returns_empty(self):
        """When SHAP explainer raises, returns empty dict."""
        import src.ml.graphsage_anomaly_detector as gmod

        mock_shap = MagicMock()
        mock_shap.KernelExplainer.side_effect = ValueError("shap error")
        with (
            patch.object(gmod, "SHAP_AVAILABLE", True),
            patch.object(gmod, "shap", mock_shap, create=True),
        ):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e3",
                node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}

    def test_explain_with_no_neighbors(self):
        """Explain anomaly with no neighbors uses target as background."""
        import src.ml.graphsage_anomaly_detector as gmod

        mock_shap = MagicMock()
        mock_shap.KernelExplainer.side_effect = ValueError("no neighbors shap")
        with (
            patch.object(gmod, "SHAP_AVAILABLE", True),
            patch.object(gmod, "shap", mock_shap, create=True),
        ):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e4",
                node_features=_normal_features(),
                neighbors=[],
            )
            assert result == {}

    def test_explain_with_auto_edge_index(self):
        """When edge_index is None, it's auto-generated."""
        import src.ml.graphsage_anomaly_detector as gmod

        mock_shap = MagicMock()
        mock_shap.KernelExplainer.side_effect = ValueError("auto-edge shap")
        with (
            patch.object(gmod, "SHAP_AVAILABLE", True),
            patch.object(gmod, "shap", mock_shap, create=True),
        ):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e5",
                node_features=_normal_features(),
                neighbors=_make_neighbors(2),
                edge_index=None,
            )
            assert result == {}


# ---------------------------------------------------------------------------
# save_model / load_model
# ---------------------------------------------------------------------------


class TestSaveLoadModel:
    def test_save_model_none_no_error(self):
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            det.save_model("/tmp/test_model.pt")  # should just warn

    def test_save_model_calls_torch_save(self, tmp_path):
        det = _make_detector()
        path = str(tmp_path / "model.pt")
        with patch("torch.save") as mock_save:
            det.save_model(path)
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            checkpoint = args[0]
            assert checkpoint["input_dim"] == 8
            assert checkpoint["hidden_dim"] == 64
            assert checkpoint["num_layers"] == 2
            assert checkpoint["anomaly_threshold"] == 0.6
            assert checkpoint["is_trained"] is False
            assert "model_state_dict" in checkpoint
            assert args[1].endswith("model.pt")

    def test_save_model_after_training(self, tmp_path):
        det = _make_detector()
        _train_detector_briefly(det)
        path = str(tmp_path / "trained_model.pt")
        with patch("torch.save") as mock_save:
            det.save_model(path)
            checkpoint = mock_save.call_args[0][0]
            assert checkpoint["is_trained"] is True

    def test_load_model_restores_state(self, tmp_path):
        det = _make_detector()
        path = str(tmp_path / "model.pt")
        det.save_model(path)

        det2 = _make_detector(anomaly_threshold=0.9)
        det2.load_model(path)
        assert det2.anomaly_threshold == 0.6
        assert det2.is_trained is False

    def test_load_model_with_quantization(self, tmp_path):
        det = _make_detector()
        path = str(tmp_path / "model_q.pt")
        det.save_model(path)
    
        det2 = _make_detector(use_quantization=False)
        det2.load_model(path)
        assert det2.anomaly_threshold == 0.6

    def test_load_model_restores_trained_flag(self, tmp_path):
        det = _make_detector()
        _train_detector_briefly(det)
        path = str(tmp_path / "trained_model.pt")
        det.save_model(path)

        det2 = _make_detector()
        det2.load_model(path)
        assert det2.is_trained is True

    def test_load_model_creates_new_model_instance(self, tmp_path):
        det = _make_detector()
        path = str(tmp_path / "model.pt")
        det.save_model(path)

        det2 = _make_detector(input_dim=16)  # different dims
        det2.load_model(path)
        # load_model should trigger _init_model_if_needed
        assert det2.is_trained is False
        assert det2.model is not None


# ---------------------------------------------------------------------------
# train_from_telemetry
# ---------------------------------------------------------------------------


class TestTrainFromTelemetry:
    def test_calls_generate_training_data(self):
        det = _make_detector()
        mock_features = [_normal_features(), _anomalous_features()]
        mock_edges = [(0, 1), (1, 0)]
        mock_labels = [0.0, 1.0]

        with (
            patch.object(GraphSAGEAnomalyDetector, "train") as mock_train,
            patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=(mock_features, mock_edges, mock_labels),
            ),
        ):
            det.train_from_telemetry(
                num_snapshots=10,
                nodes_per_snapshot=5,
                anomaly_ratio=0.3,
                epochs=2,
                lr=0.001,
                seed=42,
            )
            mock_train.assert_called_once_with(
                mock_features,
                mock_edges,
                mock_labels,
                epochs=2,
                lr=0.001,
            )

    def test_default_parameters(self):
        det = _make_detector()
        with (
            patch.object(GraphSAGEAnomalyDetector, "train") as mock_train,
            patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=([], [], []),
            ),
        ):
            det.train_from_telemetry()
            mock_train.assert_called_once()

    def test_no_torch_train_from_telemetry(self):
        """Even without torch, train_from_telemetry should not crash."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            with patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=([_normal_features()], [(0, 1)], [0.0]),
            ):
                det.train_from_telemetry(num_snapshots=5, epochs=2)

    def test_custom_seed(self):
        det = _make_detector()
        with (
            patch.object(GraphSAGEAnomalyDetector, "train"),
            patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=([], [], []),
            ) as mock_gen,
        ):
            det.train_from_telemetry(seed=123)
            assert mock_gen.call_args[1]["seed"] == 123


# ---------------------------------------------------------------------------
# create_graphsage_detector_for_mapek
# ---------------------------------------------------------------------------


class TestCreateDetectorForMapek:
    def test_default_creation(self):
        det = create_graphsage_detector_for_mapek(
            pretrain=False,
            use_quantization=False,
        )
        assert isinstance(det, GraphSAGEAnomalyDetector)
        assert det.input_dim == 8
        assert det.hidden_dim == 64
        assert det.anomaly_threshold == 0.6

    def test_no_pretrain(self):
        det = create_graphsage_detector_for_mapek(pretrain=False)
        assert det.is_trained is False

    def test_pretrain_calls_train_from_telemetry(self):
        with patch.object(
            GraphSAGEAnomalyDetector, "train_from_telemetry"
        ) as mock_train:
            det = create_graphsage_detector_for_mapek(
                pretrain=True,
                num_snapshots=5,
                epochs=2,
                use_quantization=False,
            )
            mock_train.assert_called_once_with(num_snapshots=5, epochs=2)

    def test_quantization_flag_passed_through(self):
        det = create_graphsage_detector_for_mapek(
            pretrain=False,
            use_quantization=False,
        )
        assert det.use_quantization is False

    def test_pretrain_true_no_torch_skips_training(self):
        with patch("src.ml.graphsage_anomaly_detector.is_torch_available", return_value=False):
            det = create_graphsage_detector_for_mapek(pretrain=True)
            assert det.model is None

    def test_default_quantization_is_true(self):
        det = create_graphsage_detector_for_mapek(pretrain=False)
        # Default use_quantization=True if is_quantization_available
        assert det.use_quantization == is_quantization_available()


# ---------------------------------------------------------------------------
# GraphSAGEAnomalyDetectorV2 (nn.Module)
# ---------------------------------------------------------------------------


class TestGraphSAGEAnomalyDetectorV2:
    def test_instantiation_defaults(self):
        ModelClass = get_model_class()
        model = ModelClass()
        assert model.num_layers == 2
        assert len(model.convs) == 2

    def test_custom_dims(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=16, hidden_dim=128, num_layers=3)
        assert model.num_layers == 3
        assert len(model.convs) == 3

    def test_single_layer(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=1)
        assert model.num_layers == 1
        assert len(model.convs) == 1

    def test_forward_output_shape(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = get_torch().randn(5, 8)
        edge_index = get_torch().tensor([[0, 1, 2, 3], [1, 0, 3, 2]], dtype=get_torch().long)
        with get_torch().no_grad():
            out = model(x, edge_index)
        assert out.shape == (5, 1)

    def test_forward_output_range_0_to_1(self):
        """Output should be in [0, 1] due to Sigmoid."""
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = get_torch().randn(3, 8)
        edge_index = get_torch().tensor([[0, 1], [1, 0]], dtype=get_torch().long)
        with get_torch().no_grad():
            out = model(x, edge_index)
        assert get_torch().all(out >= 0.0)
        assert get_torch().all(out <= 1.0)

    def test_forward_single_node_no_edges(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = get_torch().randn(1, 8)
        edge_index = get_torch().tensor([[], []], dtype=get_torch().long)
        with get_torch().no_grad():
            out = model(x, edge_index)
        assert out.shape == (1, 1)

    def test_has_attention_layer(self):
        ModelClass = get_model_class()
        model = ModelClass()
        assert hasattr(model, "attention")
        assert hasattr(model, "anomaly_predictor")

    def test_has_quant_stubs(self):
        ModelClass = get_model_class()
        model = ModelClass()
        assert hasattr(model, "quant")
        assert hasattr(model, "dequant")

    def test_parameter_count_reasonable(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=2)
        total_params = sum(p.numel() for p in model.parameters())
        assert 1000 < total_params < 100000, f"Unexpected param count: {total_params}"

    def test_forward_with_larger_graph(self):
        ModelClass = get_model_class()
        model = ModelClass(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = get_torch().randn(10, 8)
        # Create a ring topology
        sources = list(range(10))
        targets = [(i + 1) % 10 for i in range(10)]
        edge_index = get_torch().tensor(
            [sources + targets, targets + sources], dtype=get_torch().long
        )
        with get_torch().no_grad():
            out = model(x, edge_index)
        assert out.shape == (10, 1)

    def test_training_mode_enables_dropout(self):
        ModelClass = get_model_class()
        model = ModelClass(
            input_dim=8, hidden_dim=64, num_layers=2, dropout=0.5
        )
        model.train()
        assert model.training is True
        x = get_torch().randn(3, 8)
        edge_index = get_torch().tensor([[0, 1], [1, 0]], dtype=get_torch().long)
        # Just verify it runs without error in training mode
        out = model(x, edge_index)
        assert out.shape == (3, 1)

    def test_eval_mode(self):
        ModelClass = get_model_class()
        model = ModelClass()
        model.eval()
        assert model.training is False

    def test_prepare_for_quantization(self):
        ModelClass = get_model_class()
        model = ModelClass()
        model.prepare_for_quantization()
        assert model.training is False  # eval() is called
        assert hasattr(model, "qconfig")

    def test_convert_to_int8(self):
        ModelClass = get_model_class()
        model = ModelClass()
        model.prepare_for_quantization()
        # convert_to_int8 should not raise
        model.convert_to_int8()


# ---------------------------------------------------------------------------
# Integration tests: full predict cycle after training
# ---------------------------------------------------------------------------


class TestIntegrationPredictAfterTrain:
    def test_predict_after_training_returns_valid(self):
        det = _make_detector()
        _train_detector_briefly(det, epochs=3)

        pred = det.predict(
            node_id="int-pred",
            node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert 0.0 <= pred.anomaly_score <= 1.0

    def test_predict_with_causal_after_training(self):
        det = _make_detector()
        _train_detector_briefly(det, epochs=3)

        pred, causal = det.predict_with_causal(
            node_id="pc",
            node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_train_then_save_then_load_then_predict(self, tmp_path):
        """Full cycle: train, save, load, predict."""
        det = _make_detector()
        _train_detector_briefly(det, epochs=3)

        path = str(tmp_path / "full_cycle.pt")
        det.save_model(path)

        det2 = _make_detector()
        det2.load_model(path)
        # load_model should trigger _init_model_if_needed
        assert det2.is_trained is True
        assert det2.model is not None

        pred = det2.predict(
            node_id="loaded-pred",
            node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert 0.0 <= pred.anomaly_score <= 1.0


# ---------------------------------------------------------------------------
# Edge cases and error paths
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_predict_with_all_zero_features(self):
        det = _make_detector()
        pred = det.predict(
            node_id="zeros",
            node_features={
                k: 0.0
                for k in [
                    "rssi",
                    "snr",
                    "loss_rate",
                    "link_age",
                    "latency",
                    "throughput",
                    "cpu",
                    "memory",
                ]
            },
            neighbors=[],
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_predict_with_extreme_values(self):
        det = _make_detector()
        features = {
            "rssi": -200.0,
            "snr": -100.0,
            "loss_rate": 1.0,
            "link_age": 0.0,
            "latency": 99999.0,
            "throughput": 0.0,
            "cpu": 1.0,
            "memory": 1.0,
        }
        pred = det.predict(
            node_id="extreme",
            node_features=features,
            neighbors=[],
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_generate_labels_all_anomalous(self):
        det = _make_detector()
        nodes = [_anomalous_features() for _ in range(5)]
        labels = det._generate_labels(nodes)
        assert all(l == 1.0 for l in labels)

    def test_generate_labels_all_normal(self):
        det = _make_detector()
        nodes = [_normal_features() for _ in range(5)]
        labels = det._generate_labels(nodes)
        assert all(l == 0.0 for l in labels)

    def test_predict_many_neighbors(self):
        det = _make_detector()
        pred = det.predict(
            node_id="many-nb",
            node_features=_normal_features(),
            neighbors=_make_neighbors(20),
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_train_single_node(self):
        """Training with a single node should work (edge case)."""
        det = _make_detector()
        # Single node with self-loop
        det.train(
            node_features=[_normal_features()],
            edge_index=[(0, 0)],
            epochs=2,
        )
        assert det.is_trained is True
