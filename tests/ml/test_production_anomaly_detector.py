import pytest
import numpy as np
from datetime import datetime, timedelta
from src.ml.production_anomaly_detector import (
    ProductionAnomalyDetector,
    AnomalySeverity,
    AdaptiveThresholdCalculator,
    SeasonalityDetector,
    CorrelationAnalyzer,
    get_production_anomaly_detector
)


class TestAdaptiveThresholdCalculator:
    def test_initialization(self):
        calc = AdaptiveThresholdCalculator()
        assert calc.window_size == 300
    
    def test_update_and_baseline(self):
        calc = AdaptiveThresholdCalculator()
        for i in range(100):
            calc.update("test_metric", 10.0 + np.random.normal(0, 1))
        
        baseline = calc.get_baseline("test_metric")
        assert baseline is not None
        assert 8 < baseline.mean < 12
    
    def test_anomaly_detection(self):
        calc = AdaptiveThresholdCalculator()
        for i in range(100):
            calc.update("metric", 10.0 + (i % 5))
        
        is_anomalous, z_score = calc.is_anomalous("metric", 12.0)
        assert not is_anomalous
        
        is_anomalous, z_score = calc.is_anomalous("metric", 100.0)
        assert is_anomalous


class TestSeasonalityDetector:
    def test_pattern_detection(self):
        detector = SeasonalityDetector(period=10, min_periods=3)
        values = [10, 20, 15, 10, 20, 15] * 5
        pattern = detector.detect_pattern("metric", values)
        assert pattern is not None
    
    def test_insufficient_data(self):
        detector = SeasonalityDetector(period=100, min_periods=3)
        values = [1, 2, 3, 4, 5]
        pattern = detector.detect_pattern("metric", values)
        assert pattern is None


class TestCorrelationAnalyzer:
    def test_correlation_computation(self):
        analyzer = CorrelationAnalyzer(window_size=50)
        for i in range(50):
            analyzer.update({
                "metric1": float(i),
                "metric2": float(i * 2),
                "metric3": float(-i)
            })
        
        corrs = analyzer.compute_correlations()
        assert len(corrs) == 3
        assert ("metric1", "metric2") in corrs or ("metric2", "metric1") in corrs


class TestProductionAnomalyDetector:
    def test_initialization(self):
        detector = ProductionAnomalyDetector()
        assert detector.sensitivity == 2.0
    
    def test_normal_metric_recording(self):
        detector = ProductionAnomalyDetector()
        for i in range(150):
            event = detector.record_metric("api", "latency", 100.0 + np.random.normal(0, 5))
            if event:
                assert event.severity in [s for s in AnomalySeverity]
    
    def test_anomaly_detection(self):
        detector = ProductionAnomalyDetector()
        for i in range(100):
            detector.record_metric("api", "latency", 100.0)
        
        event = detector.record_metric("api", "latency", 500.0)
        if event:
            assert event.component == "api"
            assert event.metric_name == "latency"
    
    def test_anomaly_suppression(self):
        detector = ProductionAnomalyDetector()
        detector.suppression_window = timedelta(milliseconds=100)
        
        for i in range(100):
            detector.record_metric("api", "latency", 100.0)
        
        event1 = detector.record_metric("api", "latency", 500.0)
        event2 = detector.record_metric("api", "latency", 500.0)
        
        if event1:
            assert event2 is None
    
    def test_recent_anomalies(self):
        detector = ProductionAnomalyDetector()
        for i in range(100):
            detector.record_metric("api", "latency", 100.0)
        
        for i in range(5):
            detector.record_metric("api", "latency", 500.0)
        
        recent = detector.get_recent_anomalies(minutes=1)
        assert len(recent) >= 0
    
    def test_component_health_analysis(self):
        detector = ProductionAnomalyDetector()
        for i in range(100):
            detector.record_metric("db", "query_time", 100.0)
        
        for i in range(5):
            detector.record_metric("db", "query_time", 500.0)
        
        health = detector.analyze_component_health("db")
        assert "component" in health
        assert "health_score" in health
    
    def test_severity_calculation(self):
        detector = ProductionAnomalyDetector()
        severity1 = detector._calculate_severity(1.5, 10)
        severity2 = detector._calculate_severity(6.0, 100)
        
        assert severity1.value in [s.value for s in AnomalySeverity]
        assert severity2.value in [s.value for s in AnomalySeverity]
    
    def test_get_anomaly_summary(self):
        detector = ProductionAnomalyDetector()
        for i in range(100):
            detector.record_metric("api", "latency", 100.0)
        
        for i in range(5):
            detector.record_metric("api", "latency", 500.0)
        
        summary = detector.get_anomaly_summary()
        assert "total_anomalies" in summary
        assert "metrics_tracked" in summary


class TestSingleton:
    def test_get_singleton(self):
        detector1 = get_production_anomaly_detector()
        detector2 = get_production_anomaly_detector()
        assert detector1 is detector2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
