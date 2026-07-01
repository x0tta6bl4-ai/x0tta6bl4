"""Production Anomaly Detector — real-time adaptive threshold anomaly detection for monitoring.

Uses adaptive thresholds, seasonality detection, and correlation analysis
to identify metric anomalies in production mesh environments.
"""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import auto, Enum
from typing import Any


class AnomalySeverity(Enum):
    """Severity levels for detected anomalies."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class Baseline:
    """Statistical baseline for a metric."""
    mean: float = 0.0
    std: float = 1.0


@dataclass
class AnomalyEvent:
    """Record of a detected anomaly."""
    component: str
    metric_name: str
    value: float
    baseline: Baseline
    z_score: float
    severity: AnomalySeverity
    timestamp: float = field(default_factory=time.time)
    suppressed: bool = False


class AdaptiveThresholdCalculator:
    """Computes adaptive thresholds using rolling window statistics.

    Attributes:
        window_size: Number of samples to keep per metric.
    """

    def __init__(self, window_size: int = 300, z_threshold: float = 3.0) -> None:
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._data: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window_size))

    def update(self, metric: str, value: float) -> None:
        """Record a new metric value."""
        self._data[metric].append(value)

    def get_baseline(self, metric: str) -> Baseline | None:
        """Get statistical baseline for a metric, or None if insufficient data."""
        values = list(self._data.get(metric, []))
        if len(values) < 2:
            return None
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 1.0
        if std < 1e-10:
            std = 1.0
        return Baseline(mean=mean, std=std)

    def is_anomalous(self, metric: str, value: float) -> tuple[bool, float]:
        """Check if a value is anomalous for the given metric.

        Returns:
            Tuple of (is_anomalous, z_score).
        """
        baseline = self.get_baseline(metric)
        if baseline is None:
            return False, 0.0
        z_score = abs(value - baseline.mean) / baseline.std if baseline.std > 0 else 0.0
        return z_score > self.z_threshold, z_score


class SeasonalityDetector:
    """Detects seasonal patterns in metric data."""

    def __init__(self, period: int = 10, min_periods: int = 3) -> None:
        self.period = period
        self.min_periods = min_periods
        self._patterns: dict[str, list[float]] = {}

    def detect_pattern(self, metric: str, values: list[float]) -> dict[str, Any] | None:
        """Detect a seasonal pattern in the given values.
        
        Returns a dict with keys like 'period', 'amplitude' if pattern found,
        or None if insufficient data.
        """
        if len(values) < self.period * self.min_periods:
            return None
        # Simple pattern detection via autocorrelation
        n = len(values)
        mean = statistics.mean(values)
        pattern_strength = 0.0
        for offset in range(self.period, min(self.period * 2, n)):
            corr = sum((values[i] - mean) * (values[i + self.period] - mean)
                       for i in range(n - self.period))
            pattern_strength = max(pattern_strength, abs(corr))
        return {
            "period": self.period,
            "min_periods": self.min_periods,
            "strength": pattern_strength,
            "samples": len(values),
        }


class CorrelationAnalyzer:
    """Analyzes correlations between multiple metrics."""

    def __init__(self, window_size: int = 50) -> None:
        self.window_size = window_size
        self._data: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window_size))

    def update(self, metrics: dict[str, float]) -> None:
        """Record a snapshot of multiple metrics."""
        for name, value in metrics.items():
            self._data[name].append(value)

    def compute_correlations(self) -> dict[tuple[str, str], float]:
        """Compute Pearson correlation between all metric pairs."""
        names = list(self._data.keys())
        correlations: dict[tuple[str, str], float] = {}
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = list(self._data[names[i]])
                b = list(self._data[names[j]])
                if len(a) < 2 or len(b) < 2:
                    continue
                n = min(len(a), len(b))
                a, b = a[:n], b[:n]
                mean_a = statistics.mean(a)
                mean_b = statistics.mean(b)
                num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
                den = math.sqrt(sum((x - mean_a)**2 for x in a)) * math.sqrt(sum((y - mean_b)**2 for y in b))
                if abs(den) < 1e-10:
                    continue
                correlations[(names[i], names[j])] = num / den
        return correlations


class ProductionAnomalyDetector:
    """Production-grade anomaly detector for mesh metrics.

    Provides adaptive thresholding, anomaly event tracking,
    component health analysis, and suppression windows.

    Attributes:
        sensitivity: Z-score threshold for anomaly detection (default 2.0).
        min_history: Minimum samples before anomaly detection activates.
        suppression_window: Duration to suppress duplicate alerts.
    """

    def __init__(self, sensitivity: float = 2.0, min_history: int = 50) -> None:
        self.sensitivity = sensitivity
        self.min_history = min_history
        self.suppression_window = timedelta(seconds=10)
        self._threshold_calc = AdaptiveThresholdCalculator(z_threshold=sensitivity)
        self._events: list[AnomalyEvent] = []
        self._last_alert_time: dict[tuple[str, str], float] = {}

    @property
    def window_size(self) -> int:
        return self._threshold_calc.window_size

    def record_metric(self, component: str, metric_name: str, value: float) -> AnomalyEvent | None:
        """Record a metric value and return an AnomalyEvent if anomalous.

        Returns None if the value is within normal range.
        """
        full_metric = f"{component}:{metric_name}"
        self._threshold_calc.update(full_metric, value)

        baseline = self._threshold_calc.get_baseline(full_metric)
        if baseline is None:
            return None

        # Check if we have enough history
        values = list(self._threshold_calc._data.get(full_metric, []))
        if len(values) < self.min_history:
            return None

        is_anom, z_score = self._threshold_calc.is_anomalous(full_metric, value)
        if not is_anom:
            return None

        severity = self._calculate_severity(z_score, len(values))
        event = AnomalyEvent(
            component=component,
            metric_name=metric_name,
            value=value,
            baseline=baseline,
            z_score=z_score,
            severity=severity,
        )

        # Suppression check
        alert_key = (component, metric_name)
        now = time.time()
        last_time = self._last_alert_time.get(alert_key, 0.0)
        if now - last_time < self.suppression_window.total_seconds():
            event.suppressed = True
            self._events.append(event)
            return None

        self._last_alert_time[alert_key] = now
        self._events.append(event)
        return event

    def get_recent_anomalies(self, minutes: int = 1) -> list[AnomalyEvent]:
        """Get anomalies detected within the last N minutes."""
        cutoff = time.time() - minutes * 60
        return [e for e in self._events if e.timestamp >= cutoff]

    def analyze_component_health(self, component: str) -> dict[str, Any]:
        """Analyze overall health of a component based on its anomaly history."""
        component_events = [e for e in self._events if e.component == component]
        recent = [e for e in component_events if e.timestamp > time.time() - 300]
        health_score = max(0.0, 1.0 - len(recent) * 0.2)
        return {
            "component": component,
            "health_score": health_score,
            "total_anomalies": len(component_events),
            "recent_anomalies": len(recent),
            "status": "healthy" if health_score > 0.7 else "degraded" if health_score > 0.3 else "critical",
        }

    def _calculate_severity(self, z_score: float, history_len: int) -> AnomalySeverity:
        """Map z-score to severity level."""
        if z_score > 6.0:
            return AnomalySeverity.CRITICAL
        elif z_score > 4.0:
            return AnomalySeverity.HIGH
        elif z_score > self.sensitivity:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def get_anomaly_summary(self) -> dict[str, Any]:
        """Get a summary of all tracked anomalies and metrics."""
        return {
            "total_anomalies": len(self._events),
            "metrics_tracked": len(self._threshold_calc._data),
            "severity_counts": {
                s.name: sum(1 for e in self._events if e.severity == s)
                for s in AnomalySeverity
            },
            "components_affected": len(set(e.component for e in self._events)),
        }

    def get_thinking_status(self) -> dict[str, Any]:
        """Get redacted status for AI thinking/logging."""
        return {
            "thinking": {
                "profile": {"role": "monitoring"},
                "state": "active",
                "recent_events": len(self.get_recent_anomalies(5)),
            }
        }


_SINGLETON_INSTANCE: ProductionAnomalyDetector | None = None


def get_production_anomaly_detector(config: dict | None = None) -> ProductionAnomalyDetector:
    """Get or create the singleton ProductionAnomalyDetector."""
    global _SINGLETON_INSTANCE
    if _SINGLETON_INSTANCE is None:
        _SINGLETON_INSTANCE = ProductionAnomalyDetector(
            sensitivity=(config or {}).get("sensitivity", 2.0),
            min_history=(config or {}).get("min_history", 50),
        )
    return _SINGLETON_INSTANCE
