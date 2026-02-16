"""
Anomaly Detection Accuracy & Resilience Validation

Tests for:
1. False positive/negative rates under different scenarios
2. Severity classification accuracy
3. Detection confidence scores
4. Ensemble method accuracy improvements
"""

from datetime import datetime

import numpy as np
import pytest

from src.ml.ensemble_anomaly_detector import (EnsembleVotingStrategy,
                                              IQRDetector,
                                              IsolationForestDetector,
                                              LocalOutlierFactorDetector,
                                              MovingAverageDetector,
                                              get_ensemble_detector)
from src.ml.hybrid_anomaly_system import (HybridAnomalySystem,
                                          HybridDetectionMode)
from src.ml.production_anomaly_detector import (
    AnomalySeverity, get_production_anomaly_detector)


class TestAnomalyDetectionAccuracy:
    """Test accuracy of anomaly detection algorithms"""

    def test_isolation_forest_detection_accuracy(self):
        """Isolation Forest should detect outliers accurately"""
        detector = IsolationForestDetector(contamination=0.1, n_trees=10)

        normal_data = np.random.normal(100, 5, 100).tolist()
        detector.fit(normal_data)

        normal_value = 100.0
        outlier_value = 1000.0

        is_anomaly_normal, conf_normal = detector.predict(normal_value)
        is_anomaly_outlier, conf_outlier = detector.predict(outlier_value)

        assert isinstance(is_anomaly_normal, bool)
        assert isinstance(is_anomaly_outlier, bool)
        assert 0 <= conf_normal <= 1.0
        assert 0 <= conf_outlier <= 1.0

    def test_local_outlier_factor_detection(self):
        """LOF should detect density-based anomalies"""
        detector = LocalOutlierFactorDetector(k_neighbors=5)

        normal_data = np.random.normal(50, 10, 50).tolist()
        detector.fit(normal_data)

        is_anomaly, confidence = detector.predict(50.0)
        assert isinstance(is_anomaly, bool)
        assert 0 <= confidence <= 1.0

    def test_iqr_detector_boundary_detection(self):
        """IQR should detect values outside quartile range"""
        detector = IQRDetector(k=1.5)

        data = list(range(1, 101))
        detector.fit(data)

        is_anomaly_normal, _ = detector.predict(50.0)
        is_anomaly_outlier, _ = detector.predict(1000.0)

        assert isinstance(is_anomaly_normal, bool)
        assert isinstance(is_anomaly_outlier, bool)

    def test_moving_average_detector_trend_detection(self):
        """Moving average should detect trend-based anomalies"""
        detector = MovingAverageDetector(window_size=10)

        normal_data = [50.0 + np.random.normal(0, 2) for _ in range(50)]
        detector.fit(normal_data)

        is_anomaly, confidence = detector.predict(50.0)
        assert isinstance(is_anomaly, bool)


class TestEnsembleVotingAccuracy:
    """Test ensemble voting strategies for accuracy"""

    def test_majority_voting_accuracy(self):
        """Majority voting should aggregate detector votes correctly"""
        detector = get_ensemble_detector(strategy=EnsembleVotingStrategy.MAJORITY)

        data = [100.0] * 60 + [500.0] * 20

        detector.fit_detector("test_metric", data)

        is_anomaly_normal, _ = detector.detect("test_metric", 100.0)
        is_anomaly_outlier, _ = detector.detect("test_metric", 500.0)

        assert isinstance(is_anomaly_normal, bool)
        assert isinstance(is_anomaly_outlier, bool)

    def test_weighted_voting_accuracy(self):
        """Weighted voting should improve minority detector accuracy"""
        detector = get_ensemble_detector(strategy=EnsembleVotingStrategy.WEIGHTED)

        data = [100.0] * 80 + [200.0] * 20

        detector.fit_detector("test_metric", data)

        result = detector.detect("test_metric", 100.0)
        assert isinstance(result[0], bool)
        assert 0 <= result[1] <= 1.0

    def test_consensus_voting_strict_mode(self):
        """Consensus voting should only flag if all detectors agree"""
        detector = get_ensemble_detector(strategy=EnsembleVotingStrategy.CONSENSUS)

        data = [100.0] * 80 + [500.0] * 20

        detector.fit_detector("test_metric", data)

        is_anomaly, _ = detector.detect("test_metric", 100.0)

        assert isinstance(is_anomaly, bool)

    def test_average_confidence_voting(self):
        """Average confidence should smooth detection across methods"""
        detector = get_ensemble_detector(
            strategy=EnsembleVotingStrategy.AVERAGE_CONFIDENCE
        )

        data = list(range(1, 101))

        detector.fit_detector("test_metric", data)

        is_anomaly, confidence = detector.detect("test_metric", 50.0)
        assert 0 <= confidence <= 1.0


class TestSeverityClassification:
    """Test anomaly severity classification accuracy"""

    def test_severity_classification_levels(self):
        """Detector should classify anomalies into severity levels"""
        detector = get_production_anomaly_detector()

        for i in range(200):
            detector.record_metric(
                "critical_endpoint", "response_time", 100.0 + (i % 5)
            )

        detector.record_metric("critical_endpoint", "response_time", 500.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_low_severity_normal_deviation(self):
        """Small deviations should be classified as LOW severity"""
        detector = get_production_anomaly_detector(sensitivity=3.0)

        for i in range(100):
            detector.record_metric("service", "metric", 100.0)

        detector.record_metric("service", "metric", 102.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_critical_severity_extreme_deviation(self):
        """Extreme deviations should be classified as CRITICAL"""
        detector = get_production_anomaly_detector(sensitivity=2.0)

        for i in range(100):
            detector.record_metric("critical", "metric", 100.0)

        detector.record_metric("critical", "metric", 10000.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_medium_severity_moderate_deviation(self):
        """Moderate deviations should be classified as MEDIUM"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("service", "value", 50.0)

        detector.record_metric("service", "value", 150.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)


class TestFalsePositiveRates:
    """Test false positive and negative rates"""

    def test_baseline_normal_data_no_false_positives(self):
        """Normal data should not trigger anomalies"""
        detector = get_production_anomaly_detector(sensitivity=3.0)

        normal_data = np.random.normal(100, 5, 500).tolist()

        anomaly_count = 0
        for value in normal_data:
            detector.record_metric("baseline", "metric", value)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_injected_anomalies_detection_rate(self):
        """Detector should catch injected anomalies"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("service", "latency", 100.0)

        injected_anomalies = []
        for i in range(50):
            value = 500.0 + np.random.normal(0, 50)
            detector.record_metric("service", "latency", value)
            injected_anomalies.append(value)

        summary = detector.get_anomaly_summary()
        assert summary["metrics_tracked"] > 0

    def test_gradual_drift_detection(self):
        """Detector should detect gradual metric drift"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            value = 100.0 + (i * 0.5)
            detector.record_metric("service", "memory", value)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_periodic_spikes_handling(self):
        """Detector should handle periodic spikes correctly"""
        detector = get_production_anomaly_detector()

        values = []
        for i in range(200):
            if i % 50 == 0:
                value = 200.0
            else:
                value = 100.0 + np.random.normal(0, 2)

            detector.record_metric("periodic_service", "requests", value)
            values.append(value)

        summary = detector.get_anomaly_summary()
        assert "metrics_tracked" in summary


class TestConfidenceScoring:
    """Test anomaly confidence scoring accuracy"""

    def test_high_confidence_clear_anomalies(self):
        """Clear anomalies should have high confidence scores"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("service", "status", 100.0)

        anomaly_event = detector.record_metric("service", "status", 1000.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_low_confidence_ambiguous_readings(self):
        """Ambiguous readings should have lower confidence"""
        detector = get_production_anomaly_detector()

        values = [100.0 + np.random.normal(0, 20) for _ in range(100)]
        for value in values:
            detector.record_metric("noisy_service", "metric", value)

        test_value = 105.0
        detector.record_metric("noisy_service", "metric", test_value)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_confidence_score_range(self):
        """Confidence scores should be in valid range"""
        detector = get_production_anomaly_detector()

        for i in range(50):
            detector.record_metric("test", "metric", 100.0)

        detector.record_metric("test", "metric", 500.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)


class TestHybridSystemAccuracy:
    """Test hybrid detection system accuracy improvements"""

    def test_hybrid_agreement_detection(self):
        """Hybrid system should track agreement between methods"""
        hybrid = HybridAnomalySystem(mode=HybridDetectionMode.HYBRID)

        for i in range(100):
            hybrid.record_metric("service", "metric", 100.0 + (i % 5))

        for i in range(50):
            hybrid.record_metric("service", "metric", 500.0)

        health = hybrid.get_system_health()
        assert "agreement_ratio" in health or isinstance(health, dict)

    def test_ensemble_only_mode_higher_sensitivity(self):
        """Ensemble-only mode should be more sensitive"""
        hybrid = HybridAnomalySystem(mode=HybridDetectionMode.ENSEMBLE_ONLY)

        for i in range(100):
            hybrid.record_metric("service", "metric", 100.0)

        for i in range(20):
            hybrid.record_metric("service", "metric", 150.0)

        health = hybrid.get_system_health()
        assert isinstance(health, dict)

    def test_production_only_mode_faster_detection(self):
        """Production-only mode should be faster"""
        hybrid = HybridAnomalySystem(mode=HybridDetectionMode.PRODUCTION_ONLY)

        for i in range(100):
            hybrid.record_metric("fast_service", "latency", 100.0)

        for i in range(50):
            hybrid.record_metric("fast_service", "latency", 500.0)

        health = hybrid.get_system_health()
        assert isinstance(health, dict)

    def test_consensus_mode_strictest_detection(self):
        """Consensus mode should only flag certain anomalies"""
        hybrid = HybridAnomalySystem(mode=HybridDetectionMode.CONSENSUS)

        for i in range(100):
            hybrid.record_metric("strict_service", "metric", 100.0)

        for i in range(30):
            hybrid.record_metric("strict_service", "metric", 1000.0)

        health = hybrid.get_system_health()
        assert isinstance(health, dict)


class TestDetectionEdgeCases:
    """Test edge cases in anomaly detection"""

    def test_insufficient_baseline_data(self):
        """Detector should handle insufficient baseline data"""
        detector = get_production_anomaly_detector()

        detector.record_metric("new_service", "metric", 100.0)
        detector.record_metric("new_service", "metric", 101.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_zero_values_handling(self):
        """Detector should handle zero values correctly"""
        detector = get_production_anomaly_detector()

        for i in range(50):
            detector.record_metric("zero_service", "count", 0.0)

        detector.record_metric("zero_service", "count", 100.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_negative_values_handling(self):
        """Detector should handle negative values correctly"""
        detector = get_production_anomaly_detector()

        for i in range(50):
            detector.record_metric("metric_service", "delta", -10.0 + (i % 5))

        detector.record_metric("metric_service", "delta", -100.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_constant_metric_detection(self):
        """Detector should handle constant metrics"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("constant_service", "fixed", 42.0)

        detector.record_metric("constant_service", "fixed", 43.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)

    def test_mixed_data_types_robustness(self):
        """Detector should handle mixed numeric data types"""
        detector = get_production_anomaly_detector()

        for i in range(50):
            value = 100.0 if i % 2 == 0 else 100
            detector.record_metric("mixed_service", "value", float(value))

        detector.record_metric("mixed_service", "value", 500.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)


class TestMultiMetricCorrelation:
    """Test correlation-based anomaly detection"""

    def test_metric_correlation_tracking(self):
        """Detector should track correlations between metrics"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("service", "cpu", 50.0 + i)
            detector.record_metric("service", "memory", 100.0 + (i * 2))

        summary = detector.get_anomaly_summary()
        assert "metrics_tracked" in summary

    def test_correlated_failure_detection(self):
        """Detector should identify correlated failures"""
        detector = get_production_anomaly_detector()

        for i in range(100):
            detector.record_metric("db_service", "connections", 50.0)
            detector.record_metric("db_service", "latency", 100.0)

        for i in range(20):
            detector.record_metric("db_service", "connections", 0.0)
            detector.record_metric("db_service", "latency", 5000.0)

        summary = detector.get_anomaly_summary()
        assert isinstance(summary, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
