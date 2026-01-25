import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


@dataclass
class CardinalityMetric:
    metric_name: str
    label_combinations: Set[str] = field(default_factory=set)
    recorded_samples: int = 0
    peak_cardinality: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def current_cardinality(self) -> int:
        return len(self.label_combinations)
    
    def record_sample(self, label_str: str) -> None:
        self.label_combinations.add(label_str)
        self.recorded_samples += 1
        current = self.current_cardinality
        if current > self.peak_cardinality:
            self.peak_cardinality = current
    
    def get_cardinality_growth_rate(self) -> float:
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        if elapsed < 1:
            return 0.0
        return self.current_cardinality / elapsed


@dataclass
class CardinalityAlert:
    timestamp: datetime
    metric_name: str
    alert_type: str
    current_cardinality: int
    threshold: int
    message: str


class CardinalityLimiter:
    def __init__(self, default_limit: int = 10000):
        self.default_limit = default_limit
        self.metric_limits: Dict[str, int] = {}
        self.label_limits: Dict[str, Dict[str, int]] = defaultdict(dict)
    
    def set_metric_limit(self, metric_name: str, limit: int) -> None:
        self.metric_limits[metric_name] = limit
        logger.info(f"Set cardinality limit for {metric_name}: {limit}")
    
    def set_label_limit(self, metric_name: str, label_name: str, limit: int) -> None:
        self.label_limits[metric_name][label_name] = limit
        logger.info(f"Set label limit {metric_name}.{label_name}: {limit}")
    
    def get_limit_for_metric(self, metric_name: str) -> int:
        return self.metric_limits.get(metric_name, self.default_limit)
    
    def get_label_limit(self, metric_name: str, label_name: str) -> Optional[int]:
        return self.label_limits.get(metric_name, {}).get(label_name)
    
    def is_within_limits(self, metric_name: str, current_cardinality: int,
                        label_name: str = None, unique_values: int = None) -> bool:
        if current_cardinality > self.get_limit_for_metric(metric_name):
            return False
        if label_name and unique_values:
            label_limit = self.get_label_limit(metric_name, label_name)
            if label_limit and unique_values > label_limit:
                return False
        return True


class LabelAggregator:
    def __init__(self):
        self.aggregation_rules: Dict[str, Dict[str, str]] = {}
        self.regex_rules: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    
    def add_aggregation_rule(self, metric_name: str, label_name: str,
                           original_value: str, aggregated_value: str) -> None:
        key = f"{metric_name}.{label_name}"
        if key not in self.aggregation_rules:
            self.aggregation_rules[key] = {}
        self.aggregation_rules[key][original_value] = aggregated_value
    
    def add_regex_rule(self, metric_name: str, label_name: str,
                      pattern: str, replacement: str) -> None:
        key = f"{metric_name}.{label_name}"
        self.regex_rules[key].append((pattern, replacement))
    
    def aggregate_label(self, metric_name: str, label_name: str, value: str) -> str:
        key = f"{metric_name}.{label_name}"
        if key in self.aggregation_rules:
            if value in self.aggregation_rules[key]:
                return self.aggregation_rules[key][value]
        if key in self.regex_rules:
            for pattern, replacement in self.regex_rules[key]:
                result = re.sub(pattern, replacement, value)
                if result != value:
                    return result
        return value


class SamplingStrategy:
    def __init__(self):
        self.sampling_rates: Dict[str, float] = {}
        self.sample_counters: Dict[str, int] = defaultdict(int)
    
    def set_sampling_rate(self, metric_name: str, rate: float) -> None:
        if not 0 < rate <= 1.0:
            raise ValueError(f"Sampling rate must be between 0 and 1, got {rate}")
        self.sampling_rates[metric_name] = rate
    
    def should_sample(self, metric_name: str) -> bool:
        if metric_name not in self.sampling_rates:
            return True
        rate = self.sampling_rates[metric_name]
        count = self.sample_counters[metric_name]
        sampled = (count % int(1 / rate)) == 0
        self.sample_counters[metric_name] += 1
        return sampled


class CardinalityTracker:
    def __init__(self, max_metrics: int = 1000, alert_threshold: float = 0.9):
        self.metrics: Dict[str, CardinalityMetric] = {}
        self.max_metrics = max_metrics
        self.alert_threshold = alert_threshold
        self.alerts: List[CardinalityAlert] = []
        self.alerts_lock = threading.Lock()
        self.limiter = CardinalityLimiter()
        self.aggregator = LabelAggregator()
        self.sampler = SamplingStrategy()
    
    def record_metric(self, metric_name: str, labels: Dict[str, str]) -> bool:
        if not self.sampler.should_sample(metric_name):
            return True
        if metric_name not in self.metrics:
            if len(self.metrics) >= self.max_metrics:
                self._alert_max_metrics_exceeded(metric_name)
                return False
            self.metrics[metric_name] = CardinalityMetric(metric_name)
        
        aggregated_labels = {}
        for label_name, label_value in labels.items():
            aggregated_labels[label_name] = self.aggregator.aggregate_label(
                metric_name, label_name, label_value
            )
        
        label_str = "|".join(f"{k}={v}" for k, v in sorted(aggregated_labels.items()))
        metric = self.metrics[metric_name]
        
        if metric.current_cardinality >= self.limiter.get_limit_for_metric(metric_name):
            if label_str not in metric.label_combinations:
                self._alert_cardinality_limit(metric_name, metric.current_cardinality)
                return False
        
        metric.record_sample(label_str)
        self._check_growth_spike(metric)
        return True
    
    def _check_growth_spike(self, metric: CardinalityMetric) -> None:
        growth_rate = metric.get_cardinality_growth_rate()
        if growth_rate > 100:
            with self.alerts_lock:
                alert = CardinalityAlert(
                    timestamp=datetime.utcnow(),
                    metric_name=metric.metric_name,
                    alert_type="spike",
                    current_cardinality=metric.current_cardinality,
                    threshold=100,
                    message=f"High cardinality growth: {growth_rate:.2f} combinations/sec"
                )
                self.alerts.append(alert)
                logger.warning(f"Cardinality spike detected for {metric.metric_name}")
    
    def _alert_cardinality_limit(self, metric_name: str, current_cardinality: int) -> None:
        limit = self.limiter.get_limit_for_metric(metric_name)
        with self.alerts_lock:
            alert = CardinalityAlert(
                timestamp=datetime.utcnow(),
                metric_name=metric_name,
                alert_type="limit_exceeded",
                current_cardinality=current_cardinality,
                threshold=limit,
                message=f"Cardinality limit exceeded: {current_cardinality} > {limit}"
            )
            self.alerts.append(alert)
            logger.error(f"Cardinality limit exceeded for {metric_name}")
    
    def _alert_max_metrics_exceeded(self, metric_name: str) -> None:
        with self.alerts_lock:
            alert = CardinalityAlert(
                timestamp=datetime.utcnow(),
                metric_name=metric_name,
                alert_type="high",
                current_cardinality=len(self.metrics),
                threshold=self.max_metrics,
                message=f"Max unique metrics exceeded: {len(self.metrics)} >= {self.max_metrics}"
            )
            self.alerts.append(alert)
            logger.error(f"Max unique metrics exceeded")
    
    def get_cardinality_report(self) -> Dict:
        total_cardinality = sum(m.current_cardinality for m in self.metrics.values())
        peak_cardinality = max((m.peak_cardinality for m in self.metrics.values()), default=0)
        sorted_metrics = sorted(
            self.metrics.values(),
            key=lambda m: m.current_cardinality,
            reverse=True
        )
        return {
            "total_unique_metrics": len(self.metrics),
            "total_cardinality": total_cardinality,
            "peak_cardinality": peak_cardinality,
            "average_cardinality_per_metric": total_cardinality / len(self.metrics) if self.metrics else 0,
            "top_10_high_cardinality": [
                {
                    "metric": m.metric_name,
                    "cardinality": m.current_cardinality,
                    "peak": m.peak_cardinality,
                    "growth_rate": m.get_cardinality_growth_rate()
                }
                for m in sorted_metrics[:10]
            ],
            "alerts": [
                {
                    "timestamp": a.timestamp.isoformat(),
                    "metric": a.metric_name,
                    "type": a.alert_type,
                    "cardinality": a.current_cardinality,
                    "threshold": a.threshold,
                    "message": a.message
                }
                for a in self.alerts[-20:]
            ]
        }
    
    def get_metric_cardinality(self, metric_name: str) -> Optional[int]:
        metric = self.metrics.get(metric_name)
        return metric.current_cardinality if metric else None
    
    def cleanup_old_alerts(self, older_than_minutes: int = 60) -> None:
        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        with self.alerts_lock:
            self.alerts = [a for a in self.alerts if a.timestamp > cutoff]


class PrometheusCardinalityOptimizer:
    def __init__(self):
        self.tracker = CardinalityTracker()
        self.aggressive_mode = False
        self.lock = threading.Lock()
    
    def record_metric_sample(self, metric_name: str, labels: Dict[str, str]) -> bool:
        accepted = self.tracker.record_metric(metric_name, labels)
        if not accepted and not self.aggressive_mode:
            logger.warning(f"Switching to aggressive sampling mode for {metric_name}")
            self._enable_aggressive_mode(metric_name)
        return accepted
    
    def _enable_aggressive_mode(self, metric_name: str) -> None:
        with self.lock:
            if not self.aggressive_mode:
                self.aggressive_mode = True
                self.tracker.sampler.set_sampling_rate(metric_name, 0.5)
    
    def get_status(self) -> Dict:
        report = self.tracker.get_cardinality_report()
        return {
            "aggressive_mode": self.aggressive_mode,
            "cardinality_report": report,
            "limiter_config": {
                "default_limit": self.tracker.limiter.default_limit,
                "metric_limits": self.tracker.limiter.metric_limits,
            }
        }
    
    def configure_metric_limit(self, metric_name: str, limit: int) -> None:
        self.tracker.limiter.set_metric_limit(metric_name, limit)
    
    def configure_label_limit(self, metric_name: str, label_name: str, limit: int) -> None:
        self.tracker.limiter.set_label_limit(metric_name, label_name, limit)
    
    def add_label_aggregation(self, metric_name: str, label_name: str,
                             original_value: str, aggregated_value: str) -> None:
        self.tracker.aggregator.add_aggregation_rule(
            metric_name, label_name, original_value, aggregated_value
        )
    
    def add_label_regex_aggregation(self, metric_name: str, label_name: str,
                                   pattern: str, replacement: str) -> None:
        self.tracker.aggregator.add_regex_rule(metric_name, label_name, pattern, replacement)
    
    def get_cardinality_report(self) -> Dict:
        return self.tracker.get_cardinality_report()


_optimizer = None

def get_cardinality_optimizer() -> PrometheusCardinalityOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = PrometheusCardinalityOptimizer()
    return _optimizer


__all__ = [
    "CardinalityMetric",
    "CardinalityAlert",
    "CardinalityLimiter",
    "LabelAggregator",
    "SamplingStrategy",
    "CardinalityTracker",
    "PrometheusCardinalityOptimizer",
    "get_cardinality_optimizer",
]
