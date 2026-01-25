import pytest
import numpy as np
from src.ml.ensemble_anomaly_detector import (
    EnsembleVotingStrategy,
    IsolationForestDetector,
    LocalOutlierFactorDetector,
    IQRDetector,
    MovingAverageDetector,
    EnsembleAnomalyDetector,
    get_ensemble_detector
)


class TestIsolationForestDetector:
    def test_initialization(self):
        detector = IsolationForestDetector(contamination=0.1, n_trees=10)
        assert detector.contamination == 0.1
        assert detector.n_trees == 10
    
    def test_fit_and_predict_normal(self):
        detector = IsolationForestDetector()
        normal_data = [100.0 + np.random.normal(0, 5) for _ in range(100)]
        detector.fit(normal_data)
        
        is_anomaly, confidence = detector.predict(100.0)
        assert isinstance(is_anomaly, bool)
        assert 0 <= confidence <= 1.0
    
    def test_detect_outlier(self):
        detector = IsolationForestDetector()
        data = [100.0] * 50 + [101.0 + np.random.normal(0, 1) for _ in range(50)]
        detector.fit(data)
        
        is_anomaly_normal, _ = detector.predict(100.0)
        is_anomaly_outlier, _ = detector.predict(500.0)
        
        assert isinstance(is_anomaly_normal, bool)
        assert isinstance(is_anomaly_outlier, bool)


class TestLocalOutlierFactorDetector:
    def test_initialization(self):
        detector = LocalOutlierFactorDetector(k_neighbors=20)
        assert detector.k_neighbors == 20
    
    def test_fit_and_predict(self):
        detector = LocalOutlierFactorDetector()
        data = [100.0 + np.random.normal(0, 2) for _ in range(50)]
        detector.fit(data)
        
        is_anomaly, confidence = detector.predict(100.0)
        assert isinstance(is_anomaly, bool)
        assert 0 <= confidence <= 1.0
    
    def test_lof_score_calculation(self):
        detector = LocalOutlierFactorDetector()
        data = [100.0] * 30
        detector.fit(data)
        
        is_anomaly, confidence = detector.predict(500.0)
        assert isinstance(is_anomaly, bool)


class TestIQRDetector:
    def test_initialization(self):
        detector = IQRDetector(k=1.5)
        assert detector.k == 1.5
    
    def test_fit_and_predict(self):
        detector = IQRDetector()
        data = [100.0 + np.random.normal(0, 5) for _ in range(100)]
        detector.fit(data)
        
        is_anomaly, confidence = detector.predict(100.0)
        assert isinstance(is_anomaly, bool)
        assert 0 <= confidence <= 1.0
    
    def test_outlier_detection(self):
        detector = IQRDetector(k=1.5)
        data = list(range(90, 111))
        detector.fit(data)
        
        is_anomaly_normal, _ = detector.predict(100.0)
        is_anomaly_outlier, _ = detector.predict(1000.0)
        
        assert not is_anomaly_normal
        assert is_anomaly_outlier


class TestMovingAverageDetector:
    def test_initialization(self):
        detector = MovingAverageDetector(window_size=20)
        assert detector.window_size == 20
    
    def test_fit_and_predict(self):
        detector = MovingAverageDetector()
        data = [100.0 + np.random.normal(0, 5) for _ in range(50)]
        detector.fit(data)
        
        is_anomaly, confidence = detector.predict(100.0)
        assert isinstance(is_anomaly, bool)
        assert 0 <= confidence <= 1.0
    
    def test_detect_spike(self):
        detector = MovingAverageDetector(window_size=10, threshold_std=2.0)
        normal_data = [100.0] * 30
        detector.fit(normal_data)
        
        is_anomaly_normal, _ = detector.predict(100.0)
        is_anomaly_spike, _ = detector.predict(200.0)
        
        assert not is_anomaly_normal
        assert is_anomaly_spike


class TestEnsembleAnomalyDetector:
    def test_initialization(self):
        ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.WEIGHTED)
        assert ensemble.voting_strategy == EnsembleVotingStrategy.WEIGHTED
        assert len(ensemble.detectors) == 4
    
    def test_fit_and_predict(self):
        ensemble = EnsembleAnomalyDetector()
        data = [100.0 + np.random.normal(0, 5) for _ in range(100)]
        
        ensemble.fit("test_metric", data)
        result = ensemble.predict("test_metric", 100.0)
        
        assert result.metric_name == "test_metric"
        assert isinstance(result.is_anomaly, bool)
        assert 0 <= result.confidence <= 1.0
        assert len(result.algorithm_votes) == 4
        assert len(result.algorithm_scores) == 4
    
    def test_ensemble_voting_majority(self):
        ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.MAJORITY)
        data = [100.0 + i % 10 for i in range(100)]
        
        ensemble.fit("metric", data)
        result = ensemble.predict("metric", 100.0)
        
        assert isinstance(result.consensus_level, float)
        assert 0 <= result.consensus_level <= 1.0
    
    def test_ensemble_voting_weighted(self):
        ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.WEIGHTED)
        data = [100.0 + i % 10 for i in range(100)]
        
        ensemble.fit("metric", data)
        result = ensemble.predict("metric", 100.0)
        
        assert isinstance(result.consensus_level, float)
    
    def test_ensemble_voting_consensus(self):
        ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.CONSENSUS)
        data = [100.0 + i % 10 for i in range(100)]
        
        ensemble.fit("metric", data)
        result = ensemble.predict("metric", 100.0)
        
        assert isinstance(result.is_anomaly, bool)
    
    def test_ensemble_voting_average_confidence(self):
        ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.AVERAGE_CONFIDENCE)
        data = [100.0 + i % 10 for i in range(100)]
        
        ensemble.fit("metric", data)
        result = ensemble.predict("metric", 100.0)
        
        assert isinstance(result.confidence, float)
    
    def test_multiple_metrics(self):
        ensemble = EnsembleAnomalyDetector()
        
        data1 = [100.0 + np.random.normal(0, 5) for _ in range(100)]
        data2 = [50.0 + np.random.normal(0, 2) for _ in range(100)]
        
        ensemble.fit("metric1", data1)
        ensemble.fit("metric2", data2)
        
        result1 = ensemble.predict("metric1", 100.0)
        result2 = ensemble.predict("metric2", 50.0)
        
        assert result1.metric_name == "metric1"
        assert result2.metric_name == "metric2"
    
    def test_detector_health(self):
        ensemble = EnsembleAnomalyDetector()
        data = [100.0 + np.random.normal(0, 5) for _ in range(100)]
        ensemble.fit("metric", data)
        
        health = ensemble.get_detector_health()
        assert "detectors" in health
        assert "voting_strategy" in health
        assert "weights" in health
        assert health["metrics_trained"] > 0
    
    def test_insufficient_training_data(self):
        ensemble = EnsembleAnomalyDetector()
        data = [100.0, 101.0, 102.0]
        
        ensemble.fit("metric", data)
        result = ensemble.predict("metric", 100.0)
        
        assert isinstance(result.is_anomaly, bool)


class TestSingleton:
    def test_get_singleton(self):
        detector1 = get_ensemble_detector()
        detector2 = get_ensemble_detector()
        assert detector1 is detector2


class TestAlgorithmIntegration:
    def test_anomaly_detection_consistency(self):
        ensemble = EnsembleAnomalyDetector()
        
        normal_data = [100.0 + np.random.normal(0, 5) for _ in range(200)]
        ensemble.fit("metric", normal_data)
        
        normal_results = []
        for _ in range(10):
            result = ensemble.predict("metric", 100.0)
            normal_results.append(result.is_anomaly)
        
        anomalous_results = []
        for _ in range(10):
            result = ensemble.predict("metric", 1000.0)
            anomalous_results.append(result.is_anomaly)
        
        assert sum(normal_results) <= 2
        assert sum(anomalous_results) >= 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
