"""Tests for GraphSAGEAnomalyDetectorV3.predict_load_forecast()."""
import pytest
from src.ml.graphsage_anomaly_detector_v3_enhanced import GraphSAGEAnomalyDetectorV3


@pytest.fixture
def detector():
    return GraphSAGEAnomalyDetectorV3()


class TestPredictLoadForecast:
    def test_returns_dict_with_required_keys(self, detector):
        result = detector.predict_load_forecast("node-1", 0.5)
        assert isinstance(result, dict)
        assert "forecast_load" in result
        assert "trend" in result
        assert "scaling_recommended" in result

    def test_insufficient_history_uses_current(self, detector):
        # First call — only 1 sample, trend unknown
        result = detector.predict_load_forecast("node-new", 0.3)
        assert result["forecast_load"] == 0.3
        assert result["scaling_recommended"] is False

    def test_steady_load_no_scaling(self, detector):
        for _ in range(10):
            result = detector.predict_load_forecast("node-steady", 0.4)
        assert result["scaling_recommended"] is False

    def test_rising_high_load_triggers_scaling(self, detector):
        # Feed rising load above 0.85 with positive slope
        for i in range(15):
            detector.predict_load_forecast("node-heavy", 0.60 + i * 0.03)
        result = detector.predict_load_forecast("node-heavy", 0.97)
        assert result["scaling_recommended"] is True

    def test_forecast_clamped_to_reasonable_range(self, detector):
        for _ in range(10):
            result = detector.predict_load_forecast("node-sat", 1.0)
        assert result["forecast_load"] <= 1.2  # allows slight saturation marker

    def test_independent_history_per_node(self, detector):
        for _ in range(10):
            detector.predict_load_forecast("node-a", 0.9)
        for _ in range(10):
            detector.predict_load_forecast("node-b", 0.1)
        r_a = detector.predict_load_forecast("node-a", 0.9)
        r_b = detector.predict_load_forecast("node-b", 0.1)
        assert r_a["forecast_load"] > r_b["forecast_load"]
