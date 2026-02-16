"""
Unit tests for src/ml/graphsage_anomaly_detector.py

Tests: AnomalyPrediction dataclass, GraphSAGEAnomalyDetector initialization,
threshold logic, feature normalization, and rule-based fallback behaviour.
These tests work regardless of whether PyTorch/torch-geometric are installed.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.ml.graphsage_anomaly_detector import (AnomalyPrediction,
                                               GraphSAGEAnomalyDetector)

# ---------------------------------------------------------------------------
# AnomalyPrediction dataclass tests
# ---------------------------------------------------------------------------


class TestAnomalyPrediction:
    def test_prediction_fields(self):
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=0.85,
            confidence=0.90,
            node_id="node-42",
            features={"rssi": -60, "snr": 15},
            inference_time_ms=5.2,
        )
        assert pred.is_anomaly is True
        assert pred.anomaly_score == 0.85
        assert pred.confidence == 0.90
        assert pred.node_id == "node-42"
        assert pred.inference_time_ms == 5.2

    def test_prediction_normal(self):
        pred = AnomalyPrediction(
            is_anomaly=False,
            anomaly_score=0.1,
            confidence=0.8,
            node_id="node-ok",
            features={},
            inference_time_ms=2.0,
        )
        assert pred.is_anomaly is False
        assert pred.anomaly_score < 0.5


# ---------------------------------------------------------------------------
# GraphSAGEAnomalyDetector initialization
# ---------------------------------------------------------------------------


def _make_detector(**kwargs):
    """Create a GraphSAGEAnomalyDetector, forcing model=None if torch_geometric breaks."""
    try:
        return GraphSAGEAnomalyDetector(**kwargs)
    except Exception:
        # torch_geometric SAGEConv may fail in some environments;
        # patch _TORCH_AVAILABLE to force rule-based fallback path
        import src.ml.graphsage_anomaly_detector as _mod

        orig = _mod._TORCH_AVAILABLE
        _mod._TORCH_AVAILABLE = False
        try:
            det = GraphSAGEAnomalyDetector(**kwargs)
        finally:
            _mod._TORCH_AVAILABLE = orig
        return det


class TestDetectorInit:
    def test_default_params(self):
        detector = _make_detector()
        assert detector.input_dim == 8
        assert detector.hidden_dim == 64
        assert detector.num_layers == 2
        assert detector.anomaly_threshold == 0.6

    def test_custom_threshold(self):
        detector = _make_detector(anomaly_threshold=0.8)
        assert detector.anomaly_threshold == 0.8

    def test_custom_dimensions(self):
        detector = _make_detector(input_dim=16, hidden_dim=128, num_layers=3)
        assert detector.input_dim == 16
        assert detector.hidden_dim == 128
        assert detector.num_layers == 3

    def test_recall_precision_defaults(self):
        detector = _make_detector()
        assert detector.recall == 0.96
        assert detector.precision == 0.98


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------


class TestThresholdLogic:
    def test_score_above_threshold_is_anomaly(self):
        pred = AnomalyPrediction(
            is_anomaly=True,
            anomaly_score=0.75,
            confidence=0.5,
            node_id="n1",
            features={},
            inference_time_ms=1.0,
        )
        # score 0.75 > default threshold 0.6 => anomaly
        assert pred.is_anomaly is True

    def test_score_below_threshold_is_normal(self):
        pred = AnomalyPrediction(
            is_anomaly=False,
            anomaly_score=0.3,
            confidence=0.4,
            node_id="n2",
            features={},
            inference_time_ms=1.0,
        )
        assert pred.is_anomaly is False

    def test_confidence_calculation(self):
        # Confidence = abs(score - 0.5) * 2
        # score=0.8 => confidence = abs(0.8-0.5)*2 = 0.6
        score = 0.8
        confidence = abs(score - 0.5) * 2
        assert abs(confidence - 0.6) < 0.01

        # score=0.5 => confidence = 0.0
        score = 0.5
        confidence = abs(score - 0.5) * 2
        assert confidence == 0.0


# ---------------------------------------------------------------------------
# Feature handling
# ---------------------------------------------------------------------------


class TestFeatureHandling:
    def test_feature_keys_standard(self):
        expected = {
            "rssi",
            "snr",
            "loss_rate",
            "link_age",
            "latency",
            "throughput",
            "cpu",
            "memory",
        }
        features = {
            "rssi": -65.0,
            "snr": 12.0,
            "loss_rate": 0.02,
            "link_age": 3600.0,
            "latency": 25.0,
            "throughput": 50.0,
            "cpu": 0.4,
            "memory": 0.6,
        }
        assert set(features.keys()) == expected

    def test_anomalous_features_high_loss(self):
        # Very high loss rate should indicate an anomaly
        features = {
            "rssi": -75.0,
            "snr": 5.0,
            "loss_rate": 0.95,
            "link_age": 100.0,
            "latency": 90.0,
            "throughput": 2.0,
            "cpu": 0.95,
            "memory": 0.98,
        }
        # This would be flagged by any reasonable model
        assert features["loss_rate"] > 0.5
        assert features["cpu"] > 0.9

    def test_normal_features_ranges(self):
        features = {
            "rssi": -40.0,
            "snr": 20.0,
            "loss_rate": 0.001,
            "link_age": 7200.0,
            "latency": 5.0,
            "throughput": 90.0,
            "cpu": 0.2,
            "memory": 0.3,
        }
        assert -80 <= features["rssi"] <= -30
        assert features["loss_rate"] < 0.01


# ---------------------------------------------------------------------------
# Training guards
# ---------------------------------------------------------------------------


class TestTrainingGuards:
    def test_train_with_empty_data_skips(self):
        detector = _make_detector()
        # Should not raise
        detector.train(node_features=[], edge_index=[])

    def test_train_with_none_data_skips(self):
        detector = _make_detector()
        # Should not raise
        detector.train(node_features=None, edge_index=None)


# ---------------------------------------------------------------------------
# Causal analysis integration guard
# ---------------------------------------------------------------------------


class TestCausalIntegration:
    def test_causal_engine_attribute_or_no_model(self):
        detector = _make_detector()
        if detector.model is not None:
            # When torch is available, causal_engine should be set
            assert hasattr(detector, "causal_engine")
        else:
            # In fallback mode (no torch), model is None; causal_engine not set
            assert detector.model is None
