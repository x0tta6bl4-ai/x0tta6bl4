"""
ML Ensemble Anomaly Detection

Advanced anomaly detection using ensemble of algorithms:
- Isolation Forest (tree-based outlier detection)
- Local Outlier Factor (density-based)
- Interquartile Range (IQR) method
- Moving Average Deviation
- Weighted voting aggregation
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

logger = logging.getLogger(__name__)


class EnsembleVotingStrategy(Enum):
    """Voting strategies for ensemble"""
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    CONSENSUS = "consensus"
    AVERAGE_CONFIDENCE = "average_confidence"


@dataclass
class EnsembleDetectionResult:
    """Result from ensemble detection"""
    timestamp: datetime
    metric_name: str
    value: float
    is_anomaly: bool
    confidence: float
    algorithm_votes: Dict[str, bool] = field(default_factory=dict)
    algorithm_scores: Dict[str, float] = field(default_factory=dict)
    consensus_level: float = 0.0
    detection_reason: str = ""


class IsolationForestDetector:
    """Isolation Forest for anomaly detection"""
    
    def __init__(self, contamination: float = 0.1, n_trees: int = 10):
        self.contamination = contamination
        self.n_trees = n_trees
        self.training_data: List[float] = []
        self.trees: List[Dict[str, Any]] = []
        self.threshold: float = 0.0
    
    def fit(self, data: List[float]) -> None:
        """Train isolation forest"""
        if len(data) < 10:
            return
        
        self.training_data = list(data)
        data_arr = np.array(data)
        
        self.trees = []
        for _ in range(self.n_trees):
            tree = self._build_tree(data_arr, depth=0)
            self.trees.append(tree)
        
        mean_depth = self._compute_average_depth()
        self.threshold = -0.5 + (2 ** (-mean_depth / len(self.trees)))
    
    def _build_tree(self, data: np.ndarray, depth: int) -> Dict[str, Any]:
        """Build single isolation tree"""
        if len(data) <= 1 or depth > np.log2(len(data)):
            return {"type": "leaf", "size": len(data)}
        
        feature_val = np.random.choice(data)
        threshold = np.random.uniform(data.min(), data.max())
        
        left_data = data[data <= threshold]
        right_data = data[data > threshold]
        
        return {
            "type": "node",
            "feature": feature_val,
            "threshold": threshold,
            "left": self._build_tree(left_data, depth + 1) if len(left_data) > 0 else None,
            "right": self._build_tree(right_data, depth + 1) if len(right_data) > 0 else None
        }
    
    def _compute_average_depth(self) -> float:
        """Compute average tree depth"""
        depths = []
        for tree in self.trees:
            depth = self._get_tree_depth(tree, 0)
            depths.append(depth)
        return float(np.mean(depths)) if depths else 0.0
    
    def _get_tree_depth(self, tree: Dict[str, Any], current_depth: int) -> int:
        """Get depth of tree"""
        if tree["type"] == "leaf":
            return current_depth
        
        left_depth = self._get_tree_depth(tree["left"], current_depth + 1) if tree["left"] else current_depth
        right_depth = self._get_tree_depth(tree["right"], current_depth + 1) if tree["right"] else current_depth
        
        return max(left_depth, right_depth)
    
    def predict(self, value: float) -> Tuple[bool, float]:
        """Predict if value is anomaly"""
        if not self.trees:
            return False, 0.0
        
        anomaly_scores = []
        for tree in self.trees:
            score = self._path_length(tree, value, 0)
            anomaly_scores.append(score)
        
        avg_score = np.mean(anomaly_scores)
        is_anomaly = bool(avg_score > self.threshold)
        confidence = float(min(1.0, abs(avg_score - self.threshold) * 2))

        return is_anomaly, confidence
    
    def _path_length(self, tree: Dict[str, Any], value: float, current_depth: int) -> float:
        """Compute path length in tree"""
        if tree["type"] == "leaf":
            return current_depth + np.log2(max(1, tree["size"]))
        
        if value <= tree["threshold"]:
            if tree["left"]:
                return self._path_length(tree["left"], value, current_depth + 1)
        else:
            if tree["right"]:
                return self._path_length(tree["right"], value, current_depth + 1)
        
        return current_depth


class LocalOutlierFactorDetector:
    """Local Outlier Factor for density-based detection"""
    
    def __init__(self, k_neighbors: int = 20, contamination: float = 0.1):
        self.k_neighbors = k_neighbors
        self.contamination = contamination
        self.training_data: List[float] = []
        self.lof_scores: Dict[float, float] = {}
    
    def fit(self, data: List[float]) -> None:
        """Train LOF"""
        if len(data) < self.k_neighbors:
            return
        
        self.training_data = list(data)
        self.lof_scores = {}
        
        for point in self.training_data:
            lof_score = self._compute_lof(point)
            self.lof_scores[point] = lof_score
    
    def _compute_lof(self, point: float) -> float:
        """Compute LOF score for point"""
        distances = [abs(point - p) for p in self.training_data if p != point]
        
        if len(distances) < self.k_neighbors:
            return 1.0
        
        distances.sort()
        k_distance = distances[self.k_neighbors - 1]
        
        if k_distance == 0:
            return 1.0
        
        reachability_dists = []
        for i, dist in enumerate(distances[:self.k_neighbors]):
            reach_dist = max(dist, k_distance)
            reachability_dists.append(reach_dist)
        
        local_reachability = len(reachability_dists) / max(sum(reachability_dists), 1e-10)
        
        lof_scores_neighbors = [self.lof_scores.get(self.training_data[i], 1.0) 
                               for i in range(min(self.k_neighbors, len(self.training_data)))]
        
        mean_lof_neighbors = np.mean(lof_scores_neighbors) if lof_scores_neighbors else 1.0
        
        lof = mean_lof_neighbors / max(local_reachability, 1e-10)
        
        return float(lof)
    
    def predict(self, value: float) -> Tuple[bool, float]:
        """Predict if value is anomaly"""
        if not self.training_data:
            return False, 0.0
        
        lof_score = self._compute_lof(value)
        threshold = np.mean(list(self.lof_scores.values())) if self.lof_scores else 1.0
        
        is_anomaly = bool(lof_score > threshold * 1.5)
        confidence = float(min(1.0, (lof_score / threshold - 1.0) / 2.0)) if threshold > 0 else 0.0

        return is_anomaly, confidence


class IQRDetector:
    """Interquartile Range based detection"""
    
    def __init__(self, k: float = 1.5):
        self.k = k
        self.q1: float = 0.0
        self.q3: float = 0.0
        self.iqr: float = 0.0
    
    def fit(self, data: List[float]) -> None:
        """Train IQR"""
        if len(data) < 4:
            return
        
        data_arr = np.array(data)
        self.q1 = float(np.percentile(data_arr, 25))
        self.q3 = float(np.percentile(data_arr, 75))
        self.iqr = self.q3 - self.q1
    
    def predict(self, value: float) -> Tuple[bool, float]:
        """Predict if value is anomaly"""
        if self.iqr == 0:
            return False, 0.0
        
        lower_bound = self.q1 - self.k * self.iqr
        upper_bound = self.q3 + self.k * self.iqr
        
        is_anomaly = value < lower_bound or value > upper_bound
        
        if is_anomaly:
            if value < lower_bound:
                deviation = (lower_bound - value) / max(abs(self.q1), 1.0)
            else:
                deviation = (value - upper_bound) / max(abs(self.q3), 1.0)
            confidence = min(1.0, deviation / 5.0)
        else:
            confidence = 0.0
        
        return is_anomaly, confidence


class MovingAverageDetector:
    """Moving Average + Standard Deviation detection"""
    
    def __init__(self, window_size: int = 20, threshold_std: float = 3.0):
        self.window_size = window_size
        self.threshold_std = threshold_std
        self.values: deque = deque(maxlen=window_size * 2)
    
    def fit(self, data: List[float]) -> None:
        """Train MA detector"""
        self.values = deque(list(data)[-self.window_size*2:], maxlen=self.window_size * 2)
    
    def predict(self, value: float) -> Tuple[bool, float]:
        """Predict if value is anomaly"""
        self.values.append(value)
        
        if len(self.values) < self.window_size:
            return False, 0.0
        
        recent = list(self.values)[-self.window_size:]
        ma = np.mean(recent)
        std = np.std(recent)
        
        if std == 0:
            return False, 0.0
        
        z_score = abs((value - ma) / std)
        is_anomaly = bool(z_score > self.threshold_std)
        confidence = float(min(1.0, z_score / (self.threshold_std * 2)))

        return is_anomaly, confidence


class EnsembleAnomalyDetector:
    """Ensemble of multiple anomaly detectors with voting"""
    
    def __init__(self, voting_strategy: EnsembleVotingStrategy = EnsembleVotingStrategy.WEIGHTED):
        self.voting_strategy = voting_strategy
        self.detectors = {
            "isolation_forest": IsolationForestDetector(),
            "lof": LocalOutlierFactorDetector(),
            "iqr": IQRDetector(),
            "moving_average": MovingAverageDetector()
        }
        self.algorithm_weights = {
            "isolation_forest": 0.3,
            "lof": 0.25,
            "iqr": 0.25,
            "moving_average": 0.2
        }
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def fit(self, metric_name: str, data: List[float]) -> None:
        """Train all detectors"""
        if len(data) < 20:
            logger.warning(f"Insufficient data for ensemble training: {len(data)} samples")
            return
        
        self.metric_history[metric_name] = deque(list(data)[-1000:], maxlen=1000)
        
        for detector in self.detectors.values():
            try:
                detector.fit(data)
            except Exception as e:
                logger.error(f"Failed to train detector: {e}")
    
    def predict(self, metric_name: str, value: float) -> EnsembleDetectionResult:
        """Predict using ensemble voting"""
        timestamp = datetime.utcnow()
        self.metric_history[metric_name].append(value)
        
        if len(self.metric_history[metric_name]) < 20:
            self.fit(metric_name, list(self.metric_history[metric_name]))
        
        algorithm_votes = {}
        algorithm_scores = {}
        
        for name, detector in self.detectors.items():
            try:
                is_anomaly, confidence = detector.predict(value)
                algorithm_votes[name] = is_anomaly
                algorithm_scores[name] = confidence
            except Exception as e:
                logger.error(f"Error in {name} detector: {e}")
                algorithm_votes[name] = False
                algorithm_scores[name] = 0.0
        
        is_anomaly, consensus_level, reason = self._aggregate_votes(algorithm_votes, algorithm_scores)
        
        final_confidence = self._calculate_confidence(algorithm_scores, is_anomaly)
        
        return EnsembleDetectionResult(
            timestamp=timestamp,
            metric_name=metric_name,
            value=value,
            is_anomaly=is_anomaly,
            confidence=final_confidence,
            algorithm_votes=algorithm_votes,
            algorithm_scores=algorithm_scores,
            consensus_level=consensus_level,
            detection_reason=reason
        )
    
    def _aggregate_votes(self, votes: Dict[str, bool], 
                        scores: Dict[str, float]) -> Tuple[bool, float, str]:
        """Aggregate votes from all detectors"""
        
        if self.voting_strategy == EnsembleVotingStrategy.MAJORITY:
            anomaly_count = sum(1 for v in votes.values() if v)
            is_anomaly = anomaly_count > len(votes) / 2
            consensus = anomaly_count / len(votes) if votes else 0.0
            reason = f"{anomaly_count}/{len(votes)} detectors voted anomaly"
        
        elif self.voting_strategy == EnsembleVotingStrategy.WEIGHTED:
            weighted_score = sum(scores[k] * self.algorithm_weights[k] 
                               for k in scores.keys())
            is_anomaly = weighted_score > 0.5
            consensus = weighted_score
            reason = f"Weighted score: {weighted_score:.3f}"
        
        elif self.voting_strategy == EnsembleVotingStrategy.CONSENSUS:
            all_anomaly = all(votes.values())
            is_anomaly = all_anomaly
            consensus = 1.0 if all_anomaly else (sum(1 for v in votes.values() if v) / len(votes))
            reason = "Consensus: all detectors must agree" if is_anomaly else "No consensus"
        
        else:  # AVERAGE_CONFIDENCE
            avg_confidence = np.mean(list(scores.values()))
            is_anomaly = avg_confidence > 0.5
            consensus = avg_confidence
            reason = f"Average confidence: {avg_confidence:.3f}"
        
        return is_anomaly, consensus, reason
    
    def _calculate_confidence(self, scores: Dict[str, float], 
                             is_anomaly: bool) -> float:
        """Calculate final confidence score"""
        if not scores:
            return 0.0
        
        if is_anomaly:
            return float(np.mean(list(scores.values())))
        else:
            return float(1.0 - np.mean(list(scores.values())))
    
    def get_detector_health(self) -> Dict[str, Any]:
        """Get health status of ensemble"""
        return {
            "detectors": list(self.detectors.keys()),
            "voting_strategy": self.voting_strategy.value,
            "weights": self.algorithm_weights,
            "metrics_trained": len(self.metric_history),
            "timestamp": datetime.utcnow().isoformat()
        }


_ensemble = None

def get_ensemble_detector() -> EnsembleAnomalyDetector:
    """Get or create singleton ensemble detector"""
    global _ensemble
    if _ensemble is None:
        _ensemble = EnsembleAnomalyDetector(EnsembleVotingStrategy.WEIGHTED)
    return _ensemble


__all__ = [
    "EnsembleVotingStrategy",
    "EnsembleDetectionResult",
    "IsolationForestDetector",
    "LocalOutlierFactorDetector",
    "IQRDetector",
    "MovingAverageDetector",
    "EnsembleAnomalyDetector",
    "get_ensemble_detector",
]
