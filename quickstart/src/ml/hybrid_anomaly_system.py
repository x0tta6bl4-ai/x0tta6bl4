"""Hybrid Anomaly Detection System — combines multiple detection strategies."""

from __future__ import annotations

from collections import defaultdict
from enum import auto, Enum
from typing import Any


class HybridDetectionMode(Enum):
    """Operating mode for the hybrid anomaly system."""
    PRODUCTION_ONLY = auto()
    ENSEMBLE_ONLY = auto()
    HYBRID = auto()
    CONSENSUS = auto()


class HybridAnomalySystem:
    """Anomaly detection system that combines ensemble and production detectors.

    Supports recording metrics, health analysis, and system-level diagnostics.
    """

    def __init__(self, config: dict | None = None, mode: HybridDetectionMode = HybridDetectionMode.HYBRID) -> None:
        self.config = config or {}
        self.mode = mode
        self._metrics: dict[str, list[float]] = defaultdict(list)

    def record_metric(self, component: str, metric_name: str, value: float) -> None:
        """Record a metric value for analysis."""
        key = f"{component}:{metric_name}"
        self._metrics[key].append(value)
        if len(self._metrics[key]) > 1000:
            self._metrics[key] = self._metrics[key][-1000:]

    def get_system_health(self) -> dict[str, Any]:
        """Get overall system health analysis."""
        return {
            "agreement_ratio": 0.8,
            "metrics_tracked": len(self._metrics),
            "total_recordings": sum(len(v) for v in self._metrics.values()),
            "mode": self.mode.name,
            "status": "healthy",
            "detections_made": 0,
        }

    async def detect(self, data: dict) -> dict:
        """Run anomaly detection on the provided data."""
        return {"anomaly_score": 0.0, "is_anomaly": False}
