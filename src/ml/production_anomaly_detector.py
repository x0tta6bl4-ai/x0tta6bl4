"""
Production-Grade ML Anomaly Detection Integration

Advanced anomaly detection system with:
- Real-time metric analysis
- Adaptive thresholds
- Forecast-based detection
- Pattern recognition
- Distributed system awareness
"""

import hashlib
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


class AnomalySeverity(Enum):
    """Anomaly severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyEvent:
    """Detected anomaly event"""

    timestamp: datetime
    component: str
    metric_name: str
    current_value: float
    expected_value: float
    deviation_percent: float
    severity: AnomalySeverity
    confidence: float
    description: str


@dataclass
class MetricBaseline:
    """Baseline statistics for a metric"""

    metric_name: str
    mean: float = 0.0
    stddev: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class AdaptiveThresholdCalculator:
    """Calculates adaptive anomaly thresholds"""

    def __init__(self, window_size: int = 300):
        self.window_size = window_size
        self.metric_windows: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self.baselines: Dict[str, MetricBaseline] = {}

    def update(self, metric_name: str, value: float) -> None:
        """Update metric value"""
        self.metric_windows[metric_name].append(value)
        self._update_baseline(metric_name)

    def _update_baseline(self, metric_name: str) -> None:
        """Recalculate baseline for metric"""
        window = self.metric_windows[metric_name]
        if len(window) < 10:
            return

        values = list(window)
        values_arr = np.array(values)

        self.baselines[metric_name] = MetricBaseline(
            metric_name=metric_name,
            mean=float(np.mean(values_arr)),
            stddev=float(np.std(values_arr)),
            p50=float(np.percentile(values_arr, 50)),
            p95=float(np.percentile(values_arr, 95)),
            p99=float(np.percentile(values_arr, 99)),
            min_val=float(np.min(values_arr)),
            max_val=float(np.max(values_arr)),
            last_updated=datetime.utcnow(),
        )

    def get_baseline(self, metric_name: str) -> Optional[MetricBaseline]:
        """Get baseline for metric"""
        return self.baselines.get(metric_name)

    def is_anomalous(
        self, metric_name: str, value: float, sensitivity: float = 2.0
    ) -> Tuple[bool, float]:
        """
        Check if value is anomalous using adaptive threshold.

        Args:
            metric_name: Metric name
            value: Current value
            sensitivity: Number of stddevs (default 2.0 = 95% confidence)

        Returns:
            (is_anomalous, z_score)
        """
        baseline = self.baselines.get(metric_name)
        if not baseline or baseline.stddev == 0:
            return False, 0.0

        z_score = abs((value - baseline.mean) / baseline.stddev)
        is_anomalous = z_score > sensitivity

        return is_anomalous, z_score


class SeasonalityDetector:
    """Detects and accounts for seasonal patterns"""

    def __init__(self, period: int = 3600, min_periods: int = 3):
        self.period = period
        self.min_periods = min_periods
        self.patterns: Dict[str, List[float]] = defaultdict(list)

    def detect_pattern(
        self, metric_name: str, values: List[float]
    ) -> Optional[np.ndarray]:
        """Detect seasonal pattern"""
        if len(values) < self.period * self.min_periods:
            return None

        values_arr = np.array(values)
        seasonal = np.zeros(self.period)

        for i in range(self.period):
            indices = list(range(i, len(values), self.period))
            if indices:
                seasonal[i] = np.mean(
                    [values_arr[idx] for idx in indices if idx < len(values_arr)]
                )

        return seasonal

    def deseasonalize(self, metric_name: str, values: List[float]) -> List[float]:
        """Remove seasonal component from values"""
        pattern = self.detect_pattern(metric_name, values)
        if pattern is None:
            return values

        deseasonalized = []
        for i, val in enumerate(values):
            seasonal_idx = i % len(pattern)
            deseasonalized.append(val - pattern[seasonal_idx])

        return deseasonalized


class CorrelationAnalyzer:
    """Analyzes correlations between metrics"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metric_windows: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def update(self, metrics: Dict[str, float]) -> None:
        """Update metric values"""
        for metric_name, value in metrics.items():
            self.metric_windows[metric_name].append(value)

    def compute_correlations(self) -> Dict[Tuple[str, str], float]:
        """Compute pairwise correlations between metrics"""
        correlations = {}
        metric_names = list(self.metric_windows.keys())

        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                window1 = np.array(list(self.metric_windows[metric1]))
                window2 = np.array(list(self.metric_windows[metric2]))

                if len(window1) > 1 and len(window2) > 1:
                    corr = float(np.corrcoef(window1, window2)[0, 1])
                    if not np.isnan(corr):
                        correlations[(metric1, metric2)] = corr

        return correlations

    def find_anomalous_correlations(
        self, threshold: float = 0.1
    ) -> List[Tuple[str, str, float]]:
        """Find metrics with unexpected correlation changes"""
        current_corrs = self.compute_correlations()
        anomalous = []

        for (metric1, metric2), corr in current_corrs.items():
            if abs(corr) > threshold and np.isfinite(corr):
                anomalous.append((metric1, metric2, corr))

        return anomalous


class ProductionAnomalyDetector:
    """Production-grade anomaly detection for system monitoring"""

    def __init__(self, sensitivity: float = 2.0, min_history: int = 100):
        self.sensitivity = sensitivity
        self.min_history = min_history
        self.threshold_calc = AdaptiveThresholdCalculator()
        self.seasonality_det = SeasonalityDetector()
        self.correlation_analyzer = CorrelationAnalyzer()

        self.anomalies: List[AnomalyEvent] = []
        self.metric_history: Dict[str, List[float]] = defaultdict(list)
        self.last_anomaly_time: Dict[str, datetime] = {}
        self.suppression_window: timedelta = timedelta(seconds=60)
        self.thinking_coach = AgentThinkingCoach(
            agent_id="production-anomaly-detector",
            role="monitoring",
            capabilities=("healing", "quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "production_anomaly_detector_init",
                "goal": "Initialize anomaly detection without exposing metric labels",
                "signals": {
                    "sensitivity_band": _safe_number_band(sensitivity),
                    "min_history_bucket": _safe_count_bucket(min_history),
                    "suppression_window_seconds": int(
                        self.suppression_window.total_seconds()
                    ),
                },
                "safety_boundary": (
                    "Keep component names, metric names, raw metric values, and "
                    "anomaly descriptions out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_component_names": True,
                    "redact_metric_names": True,
                    "redact_raw_metric_values": True,
                    "redact_descriptions": True,
                    "preserve_anomaly_decision": True,
                },
                "safety_boundary": (
                    "Use hashes, counts, value bands, severity, and confidence bands."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def record_metric(
        self, component: str, metric_name: str, value: float
    ) -> Optional[AnomalyEvent]:
        """
        Record a metric and check for anomalies.

        Args:
            component: Component name
            metric_name: Metric name
            value: Metric value

        Returns:
            AnomalyEvent if detected, None otherwise
        """
        full_name = f"{component}_{metric_name}"

        self.threshold_calc.update(full_name, value)
        self.metric_history[full_name].append(value)

        if len(self.metric_history[full_name]) > 10000:
            self.metric_history[full_name] = self.metric_history[full_name][-10000:]

        is_anomalous, z_score = self.threshold_calc.is_anomalous(
            full_name, value, self.sensitivity
        )

        if is_anomalous:
            event = self._create_anomaly_event(component, metric_name, value, z_score)
            self._record_thinking(
                "production_metric_recorded",
                "Record metric and anomaly decision",
                {
                    "component_hash": _safe_hash(component),
                    "metric_hash": _safe_hash(metric_name),
                    "value_band": _safe_number_band(value),
                    "history_count_bucket": _safe_count_bucket(
                        len(self.metric_history[full_name])
                    ),
                    "z_score_band": _safe_number_band(z_score),
                    "is_anomalous": True,
                    "event_created": event is not None,
                },
            )
            return event

        self._record_thinking(
            "production_metric_recorded",
            "Record metric and confirm normal range",
            {
                "component_hash": _safe_hash(component),
                "metric_hash": _safe_hash(metric_name),
                "value_band": _safe_number_band(value),
                "history_count_bucket": _safe_count_bucket(
                    len(self.metric_history[full_name])
                ),
                "z_score_band": _safe_number_band(z_score),
                "is_anomalous": False,
            },
        )
        return None

    def _create_anomaly_event(
        self, component: str, metric_name: str, value: float, z_score: float
    ) -> Optional[AnomalyEvent]:
        """Create anomaly event with suppression check"""
        full_name = f"{component}_{metric_name}"
        now = datetime.utcnow()

        last_time = self.last_anomaly_time.get(full_name)
        if last_time and (now - last_time) < self.suppression_window:
            self._record_thinking(
                "production_anomaly_event",
                "Suppress repeated anomaly within suppression window",
                {
                    "component_hash": _safe_hash(component),
                    "metric_hash": _safe_hash(metric_name),
                    "value_band": _safe_number_band(value),
                    "z_score_band": _safe_number_band(z_score),
                    "suppressed": True,
                },
            )
            return None

        baseline = self.threshold_calc.get_baseline(full_name)
        if not baseline:
            self._record_thinking(
                "production_anomaly_event",
                "Skip anomaly event without baseline",
                {
                    "component_hash": _safe_hash(component),
                    "metric_hash": _safe_hash(metric_name),
                    "value_band": _safe_number_band(value),
                    "z_score_band": _safe_number_band(z_score),
                    "has_baseline": False,
                },
            )
            return None

        expected = baseline.mean
        deviation = ((value - expected) / expected * 100) if expected != 0 else 0

        severity = self._calculate_severity(z_score, abs(deviation))
        confidence = min(1.0, abs(z_score) / 5.0)

        event = AnomalyEvent(
            timestamp=now,
            component=component,
            metric_name=metric_name,
            current_value=value,
            expected_value=expected,
            deviation_percent=deviation,
            severity=severity,
            confidence=confidence,
            description=f"Anomaly detected in {metric_name}: "
            f"expected {expected:.2f}, got {value:.2f} "
            f"({deviation:+.1f}%)",
        )

        self.anomalies.append(event)
        self.last_anomaly_time[full_name] = now

        self._record_thinking(
            "production_anomaly_event",
            "Create anomaly event from baseline deviation",
            {
                "component_hash": _safe_hash(component),
                "metric_hash": _safe_hash(metric_name),
                "value_band": _safe_number_band(value),
                "expected_band": _safe_number_band(expected),
                "deviation_band": _safe_number_band(abs(deviation)),
                "z_score_band": _safe_number_band(z_score),
                "severity": severity.value,
                "confidence_band": _safe_number_band(confidence),
                "total_anomalies_bucket": _safe_count_bucket(len(self.anomalies)),
            },
        )
        logger.warning(f"Anomaly detected: {event.description}")

        return event

    def _calculate_severity(
        self, z_score: float, deviation_percent: float
    ) -> AnomalySeverity:
        """Calculate anomaly severity"""
        severity_score = abs(z_score) + (abs(deviation_percent) / 100)

        if severity_score > 5.0:
            return AnomalySeverity.CRITICAL
        elif severity_score > 3.5:
            return AnomalySeverity.HIGH
        elif severity_score > 2.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def get_recent_anomalies(
        self, minutes: int = 60, severity: Optional[AnomalySeverity] = None
    ) -> List[AnomalyEvent]:
        """Get recent anomalies"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        recent = [a for a in self.anomalies if a.timestamp > cutoff]

        if severity:
            recent = [a for a in recent if a.severity == severity]

        self._record_thinking(
            "production_recent_anomalies",
            "Filter recent anomalies by time and optional severity",
            {
                "minutes": minutes,
                "severity": severity.value if severity else None,
                "recent_count_bucket": _safe_count_bucket(len(recent)),
            },
        )
        return recent

    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get anomaly detection summary"""
        recent_anomalies = self.get_recent_anomalies(minutes=60)

        by_severity = defaultdict(int)
        for anomaly in recent_anomalies:
            by_severity[anomaly.severity.value] += 1

        summary = {
            "total_anomalies": len(self.anomalies),
            "recent_60min": len(recent_anomalies),
            "by_severity": dict(by_severity),
            "metrics_tracked": len(self.metric_history),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._record_thinking(
            "production_anomaly_summary",
            "Summarize anomaly detector state",
            {
                "total_anomalies_bucket": _safe_count_bucket(len(self.anomalies)),
                "recent_count_bucket": _safe_count_bucket(len(recent_anomalies)),
                "severity_counts": dict(by_severity),
                "metrics_tracked_bucket": _safe_count_bucket(len(self.metric_history)),
            },
        )
        return summary

    def analyze_component_health(self, component: str) -> Dict[str, Any]:
        """Analyze health of a specific component"""
        component_anomalies = [
            a for a in self.get_recent_anomalies(minutes=60) if a.component == component
        ]

        health_score = 100 - (len(component_anomalies) * 10)
        health_score = max(0, min(100, health_score))

        status = (
            "healthy"
            if health_score >= 80
            else "warning" if health_score >= 60 else "critical"
        )
        result = {
            "component": component,
            "health_score": health_score,
            "anomaly_count": len(component_anomalies),
            "status": status,
            "recent_anomalies": [
                {
                    "metric": a.metric_name,
                    "severity": a.severity.value,
                    "deviation": a.deviation_percent,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in component_anomalies
            ],
        }
        self._record_thinking(
            "production_component_health",
            "Analyze component health from recent anomalies",
            {
                "component_hash": _safe_hash(component),
                "health_score_band": _safe_number_band(health_score),
                "anomaly_count_bucket": _safe_count_bucket(len(component_anomalies)),
                "status": status,
            },
        )
        return result


_detector = None


def get_production_anomaly_detector(
    sensitivity: Optional[float] = None,
    min_history: Optional[int] = None,
) -> ProductionAnomalyDetector:
    """Get or create singleton detector"""
    global _detector
    if sensitivity is not None or min_history is not None:
        return ProductionAnomalyDetector(
            sensitivity=sensitivity if sensitivity is not None else 2.5,
            min_history=min_history if min_history is not None else 100,
        )
    if _detector is None:
        _detector = ProductionAnomalyDetector(sensitivity=2.5)
    return _detector


__all__ = [
    "AnomalySeverity",
    "AnomalyEvent",
    "MetricBaseline",
    "AdaptiveThresholdCalculator",
    "SeasonalityDetector",
    "CorrelationAnalyzer",
    "ProductionAnomalyDetector",
    "get_production_anomaly_detector",
]
