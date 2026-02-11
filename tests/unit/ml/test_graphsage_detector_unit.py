"""
Unit tests for src/ml/graphsage_anomaly_detector.py

Covers:
- AnomalyPrediction dataclass
- GraphSAGEAnomalyDetector __init__, train, predict, predict_with_causal,
  explain_anomaly, save_model, load_model, train_from_telemetry
- GraphSAGEAnomalyDetectorV2 forward, prepare_for_quantization, convert_to_int8
- _features_to_tensor, _edges_to_tensor, _generate_labels, _score_to_severity
- create_graphsage_detector_for_mapek factory
- Edge cases: empty data, missing features, no torch fallback
"""

import time
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, mock_open, call
from dataclasses import asdict

import torch

from src.ml.graphsage_anomaly_detector import (
    AnomalyPrediction,
    GraphSAGEAnomalyDetector,
    GraphSAGEAnomalyDetectorV2,
    create_graphsage_detector_for_mapek,
    _TORCH_AVAILABLE,
    _QUANTIZATION_AVAILABLE,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _normal_features():
    """Return healthy node features."""
    return {
        "rssi": -50.0, "snr": 20.0, "loss_rate": 0.01,
        "link_age": 3600.0, "latency": 10.0, "throughput": 80.0,
        "cpu": 0.3, "memory": 0.4,
    }


def _anomalous_features():
    """Return clearly anomalous node features."""
    return {
        "rssi": -92.0, "snr": 3.0, "loss_rate": 0.55,
        "link_age": 5.0, "latency": 250.0, "throughput": 1.0,
        "cpu": 0.96, "memory": 0.97,
    }


def _make_detector(**kwargs):
    """Create detector without quantization for faster tests."""
    kwargs.setdefault("use_quantization", False)
    return GraphSAGEAnomalyDetector(**kwargs)


def _make_neighbors(count=3):
    """Create a list of neighbor (id, features) tuples."""
    neighbors = []
    for i in range(count):
        neighbors.append((
            f"neighbor-{i}",
            {"rssi": -55.0 - i, "snr": 18.0 - i, "loss_rate": 0.02 + 0.01 * i,
             "link_age": 3000.0, "latency": 12.0, "throughput": 70.0,
             "cpu": 0.35, "memory": 0.45}
        ))
    return neighbors


# -----------------------------------------------------------------------
# AnomalyPrediction dataclass
# -----------------------------------------------------------------------

class TestAnomalyPredictionDataclass:
    def test_create_prediction(self):
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

    def test_normal_prediction(self):
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

    def test_asdict(self):
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


# -----------------------------------------------------------------------
# GraphSAGEAnomalyDetector initialization
# -----------------------------------------------------------------------

class TestDetectorInitialization:
    def test_default_parameters(self):
        det = _make_detector()
        assert det.input_dim == 8
        assert det.hidden_dim == 64
        assert det.num_layers == 2
        assert det.anomaly_threshold == 0.6

    def test_custom_parameters(self):
        det = _make_detector(
            input_dim=16, hidden_dim=128, num_layers=3, anomaly_threshold=0.75,
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
        assert det.device is not None
        assert str(det.device) == "cpu"

    def test_model_initialized(self):
        det = _make_detector()
        assert det.model is not None
        assert isinstance(det.model, GraphSAGEAnomalyDetectorV2)

    def test_is_trained_false_initially(self):
        det = _make_detector()
        assert det.is_trained is False

    def test_no_torch_fallback(self):
        """When _TORCH_AVAILABLE is False, model and device are None."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            assert det.model is None
            assert det.device is None

    def test_quantization_disabled(self):
        det = _make_detector(use_quantization=False)
        assert det.use_quantization is False

    def test_quantization_enabled_with_available(self):
        det = GraphSAGEAnomalyDetector(use_quantization=True)
        # _QUANTIZATION_AVAILABLE is True in our environment
        assert det.use_quantization is True


# -----------------------------------------------------------------------
# _features_to_tensor
# -----------------------------------------------------------------------

class TestFeaturesToTensor:
    def test_full_features(self):
        det = _make_detector()
        features = [_normal_features()]
        tensor = det._features_to_tensor(features)
        assert tensor.shape == (1, 8)
        assert tensor.dtype == torch.float

    def test_missing_features_default_to_zero(self):
        det = _make_detector()
        tensor = det._features_to_tensor([{"rssi": -60.0}])
        assert tensor.shape == (1, 8)
        # rssi is first feature
        assert tensor[0][0].item() == -60.0
        # remaining should be 0.0
        for i in range(1, 8):
            assert tensor[0][i].item() == 0.0

    def test_empty_features_dict(self):
        det = _make_detector()
        tensor = det._features_to_tensor([{}])
        assert tensor.shape == (1, 8)
        assert torch.all(tensor == 0.0)

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
        """Feature names must follow the canonical order."""
        det = _make_detector()
        features = {
            "rssi": 1.0, "snr": 2.0, "loss_rate": 3.0, "link_age": 4.0,
            "latency": 5.0, "throughput": 6.0, "cpu": 7.0, "memory": 8.0,
        }
        tensor = det._features_to_tensor([features])
        for i in range(8):
            assert tensor[0][i].item() == float(i + 1)


# -----------------------------------------------------------------------
# _edges_to_tensor
# -----------------------------------------------------------------------

class TestEdgesToTensor:
    def test_basic_edges(self):
        det = _make_detector()
        edges = [(0, 1), (1, 0)]
        tensor = det._edges_to_tensor(edges)
        assert tensor.shape == (2, 2)
        assert tensor.dtype == torch.long

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

    def test_multiple_edges_transposed(self):
        det = _make_detector()
        edges = [(0, 1), (0, 2), (1, 2)]
        tensor = det._edges_to_tensor(edges)
        assert tensor.shape == (2, 3)
        # Row 0 = sources, Row 1 = targets
        assert tensor[0].tolist() == [0, 0, 1]
        assert tensor[1].tolist() == [1, 2, 2]


# -----------------------------------------------------------------------
# _generate_labels
# -----------------------------------------------------------------------

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
        assert labels[0] == 0.0
        assert labels[1] == 1.0

    def test_empty_list(self):
        det = _make_detector()
        labels = det._generate_labels([])
        assert labels == []

    def test_default_values_healthy(self):
        """Empty dict uses defaults which should be healthy."""
        det = _make_detector()
        labels = det._generate_labels([{}])
        assert labels == [0.0]

    def test_weak_rssi_signal(self):
        """RSSI < -80 adds 0.30 to score."""
        det = _make_detector()
        features = _normal_features()
        features["rssi"] = -85.0
        labels = det._generate_labels([features])
        # Just weak RSSI alone (0.30) isn't enough for anomaly (need >= 0.50)
        assert labels == [0.0]

    def test_moderate_rssi_signal(self):
        """RSSI between -80 and -70 adds 0.10."""
        det = _make_detector()
        features = _normal_features()
        features["rssi"] = -75.0
        labels = det._generate_labels([features])
        assert labels == [0.0]

    def test_low_snr_adds_score(self):
        """SNR < 8 adds 0.25."""
        det = _make_detector()
        features = _normal_features()
        features["snr"] = 5.0
        labels = det._generate_labels([features])
        # snr < 8 = 0.25. Also triggers correlated pattern:
        # snr < 15 and throughput < 30 ... but throughput=80 so not triggered
        assert labels == [0.0]

    def test_high_loss_rate_strong_signal(self):
        """loss_rate > 0.15 adds 0.35."""
        det = _make_detector()
        features = _normal_features()
        features["loss_rate"] = 0.20
        labels = det._generate_labels([features])
        # 0.35 alone < 0.50 threshold
        assert labels == [0.0]

    def test_resource_exhaustion(self):
        """CPU or memory > 0.85 adds 0.25."""
        det = _make_detector()
        features = _normal_features()
        features["cpu"] = 0.90
        labels = det._generate_labels([features])
        assert labels == [0.0]

    def test_latency_spike(self):
        """Latency > 100 adds 0.25."""
        det = _make_detector()
        features = _normal_features()
        features["latency"] = 150.0
        labels = det._generate_labels([features])
        assert labels == [0.0]

    def test_throughput_collapse(self):
        """Throughput < 2 adds 0.20."""
        det = _make_detector()
        features = _normal_features()
        features["throughput"] = 1.0
        labels = det._generate_labels([features])
        assert labels == [0.0]

    def test_link_flapping(self):
        """Link age < 10 adds 0.15."""
        det = _make_detector()
        features = _normal_features()
        features["link_age"] = 5.0
        labels = det._generate_labels([features])
        assert labels == [0.0]

    def test_correlated_interference_pattern(self):
        """SNR < 15 + throughput < 30 + RSSI > -75 adds 0.15."""
        det = _make_detector()
        features = _normal_features()
        features["snr"] = 10.0       # < 15
        features["throughput"] = 20.0  # < 30
        features["rssi"] = -50.0      # > -75
        labels = det._generate_labels([features])
        # snr 10 < 12 -> 0.10, correlated -> 0.15, total 0.25 < 0.50
        assert labels == [0.0]

    def test_cascade_pattern(self):
        """Latency > 30 + loss_rate > 0.03 adds 0.10."""
        det = _make_detector()
        features = _normal_features()
        features["latency"] = 50.0    # > 30, adds 0.10 for > 40
        features["loss_rate"] = 0.10  # > 0.03, > 0.05 adds 0.15
        labels = det._generate_labels([features])
        # latency > 40 = 0.10, loss_rate > 0.05 = 0.15, cascade = 0.10 => 0.35 < 0.50
        assert labels == [0.0]

    def test_combined_anomaly_triggers(self):
        """Multiple signals together should cross threshold."""
        det = _make_detector()
        features = {
            "rssi": -85.0,      # 0.30
            "snr": 5.0,         # 0.25
            "loss_rate": 0.20,  # 0.35
            "link_age": 5.0,    # 0.15
            "latency": 150.0,   # 0.25
            "throughput": 1.0,  # 0.20
            "cpu": 0.90,        # 0.25
            "memory": 0.40,     # 0
        }
        labels = det._generate_labels([features])
        assert labels == [1.0]


# -----------------------------------------------------------------------
# _score_to_severity
# -----------------------------------------------------------------------

class TestScoreToSeverity:
    def test_critical_severity(self):
        det = _make_detector()
        result = det._score_to_severity(0.95)
        assert result is not None
        assert result.name == "CRITICAL"

    def test_high_severity(self):
        det = _make_detector()
        result = det._score_to_severity(0.75)
        assert result.name == "HIGH"

    def test_medium_severity(self):
        det = _make_detector()
        result = det._score_to_severity(0.55)
        assert result.name == "MEDIUM"

    def test_low_severity(self):
        det = _make_detector()
        result = det._score_to_severity(0.3)
        assert result.name == "LOW"

    def test_boundary_0_9(self):
        det = _make_detector()
        result = det._score_to_severity(0.9)
        assert result.name == "CRITICAL"

    def test_boundary_0_7(self):
        det = _make_detector()
        result = det._score_to_severity(0.7)
        assert result.name == "HIGH"

    def test_boundary_0_5(self):
        det = _make_detector()
        result = det._score_to_severity(0.5)
        assert result.name == "MEDIUM"

    def test_below_0_5(self):
        det = _make_detector()
        result = det._score_to_severity(0.49)
        assert result.name == "LOW"

    def test_score_to_severity_without_causal(self):
        """When CAUSAL_ANALYSIS_AVAILABLE is False, returns None."""
        with patch("src.ml.graphsage_anomaly_detector.CAUSAL_ANALYSIS_AVAILABLE", False):
            det = _make_detector()
            result = det._score_to_severity(0.95)
            assert result is None


# -----------------------------------------------------------------------
# train method
# -----------------------------------------------------------------------

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
            # When torch is unavailable, is_trained is never set (init returns early)
            assert not getattr(det, "is_trained", False)

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
        labels = [0.0, 1.0]
        det.train(node_features=features, edge_index=edges, labels=labels, epochs=2)
        assert det.is_trained is True

    def test_train_with_auto_labels(self):
        """When labels=None, _generate_labels is used."""
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


# -----------------------------------------------------------------------
# predict method
# -----------------------------------------------------------------------

class TestPredictMethod:
    def test_predict_returns_anomaly_prediction(self):
        det = _make_detector()
        pred = det.predict(
            node_id="test-node",
            node_features=_normal_features(),
            neighbors=_make_neighbors(2),
        )
        assert isinstance(pred, AnomalyPrediction)
        assert pred.node_id == "test-node"
        assert 0.0 <= pred.anomaly_score <= 1.0
        assert 0.0 <= pred.confidence <= 1.0
        assert pred.inference_time_ms >= 0.0

    def test_predict_features_passed_through(self):
        det = _make_detector()
        features = _normal_features()
        pred = det.predict(
            node_id="n1", node_features=features, neighbors=_make_neighbors(1),
        )
        assert pred.features == features

    def test_predict_auto_generates_edge_index(self):
        det = _make_detector()
        pred = det.predict(
            node_id="n1", node_features=_normal_features(),
            neighbors=_make_neighbors(3), edge_index=None,
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_predict_with_explicit_edge_index(self):
        det = _make_detector()
        pred = det.predict(
            node_id="n1", node_features=_normal_features(),
            neighbors=_make_neighbors(2),
            edge_index=[(0, 1), (1, 0), (0, 2), (2, 0)],
        )
        assert isinstance(pred, AnomalyPrediction)

    def test_predict_no_neighbors(self):
        det = _make_detector()
        pred = det.predict(
            node_id="lone", node_features=_normal_features(),
            neighbors=[],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert pred.node_id == "lone"

    def test_predict_confidence_formula(self):
        """Confidence should be abs(score - 0.5) * 2."""
        det = _make_detector()
        pred = det.predict(
            node_id="c", node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        expected = abs(pred.anomaly_score - 0.5) * 2
        assert abs(pred.confidence - expected) < 1e-6

    def test_predict_anomaly_flag_based_on_threshold(self):
        """is_anomaly should be True iff anomaly_score >= threshold."""
        det = _make_detector()
        pred = det.predict(
            node_id="t", node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly == (pred.anomaly_score >= det.anomaly_threshold)

    def test_predict_records_metrics(self):
        """record_graphsage_inference should be called."""
        with patch("src.ml.graphsage_anomaly_detector.record_graphsage_inference") as mock_record:
            det = _make_detector()
            pred = det.predict(
                node_id="m", node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            mock_record.assert_called_once()
            args = mock_record.call_args[0]
            assert args[0] >= 0  # inference_time
            assert isinstance(args[1], bool)  # is_anomaly
            assert args[2] in ("CRITICAL", "NORMAL")


# -----------------------------------------------------------------------
# predict_with_causal method
# -----------------------------------------------------------------------

class TestPredictWithCausal:
    def test_returns_tuple(self):
        det = _make_detector()
        result = det.predict_with_causal(
            node_id="c1", node_features=_normal_features(),
            neighbors=_make_neighbors(2),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        pred, causal = result
        assert isinstance(pred, AnomalyPrediction)

    def test_no_anomaly_returns_none_causal(self):
        """When prediction is not anomaly, causal result should be None."""
        det = _make_detector()
        # Use a very high threshold so nothing is anomalous
        det.anomaly_threshold = 0.99
        pred, causal = det.predict_with_causal(
            node_id="safe", node_features=_normal_features(),
            neighbors=_make_neighbors(2),
        )
        assert causal is None

    def test_anomaly_with_causal_engine_none(self):
        """When causal_engine is None, causal result should be None."""
        det = _make_detector()
        det.causal_engine = None
        det.anomaly_threshold = 0.0  # Force anomaly
        pred, causal = det.predict_with_causal(
            node_id="no-causal", node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly is True
        assert causal is None

    def test_anomaly_with_causal_engine_error(self):
        """When causal engine raises, returns (prediction, None)."""
        det = _make_detector()
        det.anomaly_threshold = 0.0  # Force anomaly
        mock_engine = MagicMock()
        mock_engine.analyze.side_effect = RuntimeError("analysis failed")
        det.causal_engine = mock_engine
        pred, causal = det.predict_with_causal(
            node_id="err", node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly is True
        assert causal is None

    def test_anomaly_triggers_causal_analysis(self):
        """When anomaly detected and causal engine present, analysis runs."""
        det = _make_detector()
        det.anomaly_threshold = 0.0  # Force anomaly

        mock_result = MagicMock()
        mock_result.root_causes = ["cause1"]
        mock_result.confidence = 0.85

        mock_engine = MagicMock()
        mock_engine.analyze.return_value = mock_result
        det.causal_engine = mock_engine

        pred, causal = det.predict_with_causal(
            node_id="anom", node_features=_normal_features(),
            neighbors=_make_neighbors(1),
        )
        assert pred.is_anomaly is True
        assert causal is mock_result
        mock_engine.add_incident.assert_called_once()
        mock_engine.analyze.assert_called_once()

    def test_causal_not_available_returns_none(self):
        """When CAUSAL_ANALYSIS_AVAILABLE is False, no causal analysis."""
        with patch("src.ml.graphsage_anomaly_detector.CAUSAL_ANALYSIS_AVAILABLE", False):
            det = _make_detector()
            det.anomaly_threshold = 0.0
            det.causal_engine = MagicMock()
            pred, causal = det.predict_with_causal(
                node_id="nc", node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert causal is None


# -----------------------------------------------------------------------
# explain_anomaly method
# -----------------------------------------------------------------------

class TestExplainAnomaly:
    def test_shap_not_available_returns_empty(self):
        """When SHAP_AVAILABLE is False, returns empty dict."""
        with patch("src.ml.graphsage_anomaly_detector.SHAP_AVAILABLE", False):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e1", node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}

    def test_model_none_returns_empty(self):
        """When model is None, returns empty dict."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            result = det.explain_anomaly(
                node_id="e2", node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}

    def test_explain_exception_returns_empty(self):
        """When SHAP explainer raises, returns empty dict."""
        import sys
        mock_shap = MagicMock()
        mock_shap.KernelExplainer.side_effect = ValueError("shap error")
        import src.ml.graphsage_anomaly_detector as gmod
        with patch.object(gmod, "SHAP_AVAILABLE", True), \
             patch.object(gmod, "shap", mock_shap, create=True):
            det = _make_detector()
            result = det.explain_anomaly(
                node_id="e3", node_features=_normal_features(),
                neighbors=_make_neighbors(1),
            )
            assert result == {}


# -----------------------------------------------------------------------
# save_model / load_model
# -----------------------------------------------------------------------

class TestSaveLoadModel:
    def test_save_model_none_no_error(self):
        """save_model with model=None should not raise."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            det.save_model("/tmp/test_model.pt")  # should just warn

    def test_save_model_calls_torch_save(self):
        det = _make_detector()
        with patch("src.ml.graphsage_anomaly_detector.torch.save") as mock_save:
            det.save_model("/tmp/model.pt")
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            checkpoint = args[0]
            assert checkpoint["input_dim"] == 8
            assert checkpoint["hidden_dim"] == 64
            assert checkpoint["num_layers"] == 2
            assert checkpoint["anomaly_threshold"] == 0.6
            assert checkpoint["is_trained"] is False
            assert "model_state_dict" in checkpoint
            assert args[1] == "/tmp/model.pt"

    def test_load_model_restores_state(self, tmp_path):
        """Save then load should restore the detector state."""
        det = _make_detector()
        path = str(tmp_path / "model.pt")
        det.save_model(path)

        det2 = _make_detector(anomaly_threshold=0.9)
        det2.load_model(path)
        assert det2.anomaly_threshold == 0.6
        assert det2.is_trained is False

    def test_load_model_with_quantization(self, tmp_path):
        """Loading with quantization should prepare and convert."""
        det = _make_detector()
        path = str(tmp_path / "model_q.pt")
        det.save_model(path)

        det2 = GraphSAGEAnomalyDetector(use_quantization=True)
        det2.load_model(path)
        assert det2.anomaly_threshold == 0.6


# -----------------------------------------------------------------------
# train_from_telemetry
# -----------------------------------------------------------------------

class TestTrainFromTelemetry:
    def test_calls_generate_training_data(self):
        det = _make_detector()
        mock_features = [_normal_features(), _anomalous_features()]
        mock_edges = [(0, 1), (1, 0)]
        mock_labels = [0.0, 1.0]

        with patch(
            "src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector.train"
        ) as mock_train:
            with patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=(mock_features, mock_edges, mock_labels),
            ):
                det.train_from_telemetry(
                    num_snapshots=10, nodes_per_snapshot=5,
                    anomaly_ratio=0.3, epochs=2, lr=0.001, seed=42,
                )
                mock_train.assert_called_once_with(
                    mock_features, mock_edges, mock_labels, epochs=2, lr=0.001,
                )

    def test_no_torch_train_from_telemetry(self):
        """Even without torch, train_from_telemetry should not crash."""
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = GraphSAGEAnomalyDetector()
            mock_features = [_normal_features()]
            mock_edges = [(0, 1)]
            mock_labels = [0.0]
            with patch(
                "src.ml.mesh_telemetry.generate_training_data",
                return_value=(mock_features, mock_edges, mock_labels),
            ):
                det.train_from_telemetry(num_snapshots=5, epochs=2)


# -----------------------------------------------------------------------
# create_graphsage_detector_for_mapek
# -----------------------------------------------------------------------

class TestCreateDetectorForMapek:
    def test_default_creation(self):
        det = create_graphsage_detector_for_mapek(
            pretrain=False, use_quantization=False,
        )
        assert isinstance(det, GraphSAGEAnomalyDetector)
        assert det.input_dim == 8
        assert det.hidden_dim == 64
        assert det.anomaly_threshold == 0.6

    def test_no_pretrain(self):
        det = create_graphsage_detector_for_mapek(pretrain=False)
        assert det.is_trained is False

    def test_pretrain_calls_train(self):
        with patch.object(
            GraphSAGEAnomalyDetector, "train_from_telemetry"
        ) as mock_train:
            det = create_graphsage_detector_for_mapek(
                pretrain=True, num_snapshots=5, epochs=2, use_quantization=False,
            )
            mock_train.assert_called_once_with(num_snapshots=5, epochs=2)

    def test_quantization_flag_passed(self):
        det = create_graphsage_detector_for_mapek(
            pretrain=False, use_quantization=False,
        )
        assert det.use_quantization is False

    def test_pretrain_false_no_torch(self):
        with patch("src.ml.graphsage_anomaly_detector._TORCH_AVAILABLE", False):
            det = create_graphsage_detector_for_mapek(pretrain=True)
            # pretrain=True but no torch => train_from_telemetry not called
            assert det.model is None


# -----------------------------------------------------------------------
# GraphSAGEAnomalyDetectorV2 (nn.Module)
# -----------------------------------------------------------------------

class TestGraphSAGEAnomalyDetectorV2:
    def test_instantiation(self):
        model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64, num_layers=2)
        assert model.num_layers == 2
        assert len(model.convs) == 2

    def test_custom_dims(self):
        model = GraphSAGEAnomalyDetectorV2(input_dim=16, hidden_dim=128, num_layers=3)
        assert model.num_layers == 3
        assert len(model.convs) == 3

    def test_forward_output_shape(self):
        model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = torch.randn(5, 8)
        edge_index = torch.tensor([[0, 1, 2, 3], [1, 0, 3, 2]], dtype=torch.long)
        with torch.no_grad():
            out = model(x, edge_index)
        assert out.shape == (5, 1)

    def test_forward_output_range(self):
        """Output should be in [0, 1] due to Sigmoid."""
        model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = torch.randn(3, 8)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
        with torch.no_grad():
            out = model(x, edge_index)
        assert torch.all(out >= 0.0)
        assert torch.all(out <= 1.0)

    def test_forward_single_node(self):
        model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64, num_layers=2)
        model.eval()
        x = torch.randn(1, 8)
        edge_index = torch.tensor([[], []], dtype=torch.long)
        with torch.no_grad():
            out = model(x, edge_index)
        assert out.shape == (1, 1)

    def test_has_attention_layer(self):
        model = GraphSAGEAnomalyDetectorV2()
        assert hasattr(model, "attention")
        assert hasattr(model, "anomaly_predictor")

    def test_has_quant_stubs(self):
        model = GraphSAGEAnomalyDetectorV2()
        assert hasattr(model, "quant")
        assert hasattr(model, "dequant")

    def test_parameter_count_reasonable(self):
        """Model should have a reasonable number of parameters for edge deployment."""
        model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64, num_layers=2)
        total_params = sum(p.numel() for p in model.parameters())
        # Should be around ~15K parameters
        assert total_params < 100000, f"Too many params: {total_params}"
        assert total_params > 1000, f"Too few params: {total_params}"


# -----------------------------------------------------------------------
# Integration: full predict cycle after training
# -----------------------------------------------------------------------

class TestIntegrationPredictAfterTrain:
    def test_predict_after_brief_training(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features(), _normal_features()]
        edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
        det.train(node_features=features, edge_index=edges, epochs=3)

        pred = det.predict(
            node_id="trained-pred",
            node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)
        assert 0.0 <= pred.anomaly_score <= 1.0

    def test_predict_with_causal_after_training(self):
        det = _make_detector()
        features = [_normal_features(), _anomalous_features()]
        edges = [(0, 1), (1, 0)]
        det.train(node_features=features, edge_index=edges, epochs=3)

        pred, causal = det.predict_with_causal(
            node_id="pc", node_features=_normal_features(),
            neighbors=[("nb", _normal_features())],
        )
        assert isinstance(pred, AnomalyPrediction)
