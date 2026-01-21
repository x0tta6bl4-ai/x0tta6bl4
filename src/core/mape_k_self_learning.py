"""
Self-Learning MAPE-K Threshold Optimization

Automatically learns optimal thresholds from historical metrics data.
Provides anomaly detection, trend analysis, and dynamic threshold adaptation.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict, deque
from datetime import datetime, timedelta
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class ThresholdStrategy(Enum):
    """Strategies for threshold calculation"""
    PERCENTILE = "percentile"
    SIGMA = "sigma"
    IQR = "iqr"
    ADAPTIVE = "adaptive"


@dataclass
class MetricPoint:
    """Single metric measurement"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ThresholdRecommendation:
    """Threshold recommendation with confidence"""
    parameter: str
    recommended_value: float
    confidence: float
    strategy: ThresholdStrategy
    reasoning: str
    supporting_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricStatistics:
    """Statistics for a metric"""
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    p25: float
    p75: float
    p90: float
    p95: float
    p99: float
    data_points: int
    timestamp: float


class MetricsBuffer:
    """Circular buffer for metric time series"""
    
    def __init__(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def add_point(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def add_points(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(value, timestamp)
    
    def get_statistics(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def get_recent_points(self, seconds: int = 3600) -> List[MetricPoint]:
        cutoff = time.time() - seconds
        return [p for p in self.buffer if p.timestamp >= cutoff]
    
    def get_trend(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"


class SelfLearningThresholdOptimizer:
    """
    Self-learning system for MAPE-K threshold optimization.
    """
    
    def __init__(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def add_metric(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, timestamp, labels)
    
    def should_optimize(self) -> bool:
        now = time.time()
        return (now - self.last_optimization) >= self.optimization_interval
    
    def optimize_thresholds(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def _generate_recommendation(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def detect_anomalies(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def get_statistics(self, parameter: str) -> Optional[MetricStatistics]:
        if parameter not in self.buffers:
            return None
        return self.buffers[parameter].get_statistics()
    
    def get_recommendation(self, parameter: str) -> Optional[ThresholdRecommendation]:
        return self.recommendations.get(parameter)
    
    def get_all_recommendations(self) -> Dict[str, ThresholdRecommendation]:
        return self.recommendations.copy()
    
    def _record_optimization(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        return self.optimization_history.copy()
    
    def get_learning_stats(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def export_thresholds(self) -> Dict[str, float]:
        return {
            param: rec.recommended_value
            for param, rec in self.recommendations.items()
        }
    
    def import_metrics(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter not in self.buffers:
                self.buffers[parameter] = MetricsBuffer(parameter)
            self.buffers[parameter].add_points(points)
