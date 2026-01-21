"""
Extended ML Models for x0tta6bl4

Provides additional ML models beyond GraphSAGE for enhanced anomaly detection
and network intelligence.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Optional ML libraries
try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None
    nn = None

try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.cluster import DBSCAN
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False
    IsolationForest = None
    RandomForestClassifier = None
    DBSCAN = None


@dataclass
class AnomalyPredictionExtended:
    """Extended anomaly prediction with multiple model consensus"""
    is_anomaly: bool
    confidence: float
    model_scores: Dict[str, float]  # scores from different models
    consensus_score: float  # aggregated score
    explanation: Optional[str] = None


class EnsembleAnomalyDetector:
    """
    Ensemble anomaly detector combining multiple ML models.
    
    Models:
    - GraphSAGE (GNN-based)
    - Isolation Forest (unsupervised)
    - Random Forest (supervised, if labels available)
    - DBSCAN clustering (outlier detection)
    """
    
    def __init__(self):
        self.models = {}
        self.is_trained = False
        
        if _SKLEARN_AVAILABLE:
            self.models['isolation_forest'] = IsolationForest(
                contamination=0.1,
                random_state=42
            )
            self.models['dbscan'] = DBSCAN(eps=0.5, min_samples=5)
        
        logger.info(f"Ensemble Anomaly Detector initialized with {len(self.models)} models")
    
    def train(
        self,
        features: List[Dict[str, float]],
        labels: Optional[List[int]] = None
    ):
        """
        Train ensemble models.
        
        Args:
            features: List of feature dictionaries
            labels: Optional labels (0=normal, 1=anomaly)
        """
        if not features:
            logger.warning("No features provided for training")
            return
        
        # Convert to numpy array
        feature_names = ['rssi', 'snr', 'loss_rate', 'link_age', 'latency', 'throughput', 'cpu', 'memory']
        X = np.array([
            [f.get(name, 0.0) for name in feature_names]
            for f in features
        ])
        
        # Train Isolation Forest
        if 'isolation_forest' in self.models:
            try:
                self.models['isolation_forest'].fit(X)
                logger.info("Isolation Forest trained")
            except Exception as e:
                logger.error(f"Failed to train Isolation Forest: {e}")
        
        # Train Random Forest if labels available
        if labels and 'random_forest' not in self.models and _SKLEARN_AVAILABLE:
            try:
                self.models['random_forest'] = RandomForestClassifier(
                    n_estimators=100,
                    random_state=42
                )
                y = np.array(labels)
                self.models['random_forest'].fit(X, y)
                logger.info("Random Forest trained")
            except Exception as e:
                logger.error(f"Failed to train Random Forest: {e}")
        
        self.is_trained = True
        logger.info("Ensemble models training completed")
    
    def predict(self, features: Dict[str, float]) -> AnomalyPredictionExtended:
        """
        Predict anomaly using ensemble of models.
        
        Args:
            features: Feature dictionary
            
        Returns:
            AnomalyPredictionExtended with consensus prediction
        """
        feature_names = ['rssi', 'snr', 'loss_rate', 'link_age', 'latency', 'throughput', 'cpu', 'memory']
        x = np.array([[features.get(name, 0.0) for name in feature_names]])
        
        model_scores = {}
        
        # Isolation Forest prediction
        if 'isolation_forest' in self.models:
            try:
                score = self.models['isolation_forest'].score_samples(x)[0]
                # Convert to anomaly probability (lower score = more anomalous)
                anomaly_prob = 1.0 / (1.0 + np.exp(score))  # Sigmoid transformation
                model_scores['isolation_forest'] = anomaly_prob
            except Exception as e:
                logger.warning(f"Isolation Forest prediction failed: {e}")
        
        # Random Forest prediction
        if 'random_forest' in self.models:
            try:
                proba = self.models['random_forest'].predict_proba(x)[0]
                model_scores['random_forest'] = proba[1]  # Probability of anomaly class
            except Exception as e:
                logger.warning(f"Random Forest prediction failed: {e}")
        
        # Calculate consensus (weighted average)
        if model_scores:
            consensus_score = sum(model_scores.values()) / len(model_scores)
            is_anomaly = consensus_score > 0.6  # Threshold
        else:
            consensus_score = 0.5
            is_anomaly = False
        
        # Generate explanation
        explanation = self._generate_explanation(model_scores, consensus_score)
        
        return AnomalyPredictionExtended(
            is_anomaly=is_anomaly,
            confidence=abs(consensus_score - 0.5) * 2,  # 0-1 confidence
            model_scores=model_scores,
            consensus_score=consensus_score,
            explanation=explanation
        )
    
    def _generate_explanation(self, model_scores: Dict[str, float], consensus: float) -> str:
        """Generate human-readable explanation."""
        if not model_scores:
            return "No models available for prediction"
        
        explanations = []
        for model_name, score in model_scores.items():
            if score > 0.7:
                explanations.append(f"{model_name} indicates high anomaly risk ({score:.2%})")
            elif score < 0.3:
                explanations.append(f"{model_name} indicates normal behavior ({score:.2%})")
        
        if consensus > 0.6:
            return f"Anomaly detected. {', '.join(explanations)}"
        else:
            return f"Normal behavior. {', '.join(explanations)}"


class TimeSeriesAnomalyDetector:
    """
    Time-series based anomaly detector for temporal patterns.
    
    Detects anomalies in time-series data (e.g., network traffic patterns,
    latency trends, resource usage over time).
    """
    
    def __init__(self, window_size: int = 10):
        """
        Initialize time-series detector.
        
        Args:
            window_size: Size of sliding window for analysis
        """
        self.window_size = window_size
        self.history: List[float] = []
        logger.info(f"Time-series Anomaly Detector initialized (window: {window_size})")
    
    def add_observation(self, value: float):
        """Add a new observation to the time series."""
        self.history.append(value)
        if len(self.history) > self.window_size * 2:
            self.history = self.history[-self.window_size * 2:]
    
    def detect_anomaly(self) -> Tuple[bool, float]:
        """
        Detect anomaly in current time series.
        
        Returns:
            (is_anomaly, anomaly_score)
        """
        if len(self.history) < self.window_size:
            return False, 0.0
        
        # Simple statistical anomaly detection
        recent = self.history[-self.window_size:]
        historical = self.history[:-self.window_size] if len(self.history) > self.window_size else recent
        
        if not historical:
            return False, 0.0
        
        mean = np.mean(historical)
        std = np.std(historical)
        
        if std == 0:
            return False, 0.0
        
        # Check if recent values deviate significantly
        recent_mean = np.mean(recent)
        z_score = abs(recent_mean - mean) / std
        
        is_anomaly = z_score > 2.0  # 2 standard deviations
        anomaly_score = min(z_score / 3.0, 1.0)  # Normalize to 0-1
        
        return is_anomaly, anomaly_score


def create_extended_detector() -> EnsembleAnomalyDetector:
    """Create an extended ensemble anomaly detector."""
    return EnsembleAnomalyDetector()

