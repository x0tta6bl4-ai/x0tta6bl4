"""Hybrid Anomaly Detection System — combines multiple detection strategies."""

from __future__ import annotations

from enum import auto, Enum
from typing import Any


class HybridDetectionMode(Enum):
    """Operating mode for the hybrid anomaly system."""
    PRODUCTION_ONLY = auto()
    ENSEMBLE_ONLY = auto()
    HYBRID = auto()


class HybridAnomalySystem:
    """Anomaly detection system that combines ensemble and production detectors.

    Args:
        config: Optional configuration dict.
        mode: Detection mode (HYBRID, PRODUCTION_ONLY, ENSEMBLE_ONLY).
    """

    def __init__(self, config: dict | None = None, mode: HybridDetectionMode = HybridDetectionMode.HYBRID) -> None:
        self.config = config or {}
        self.mode = mode

    async def detect(self, data: dict) -> dict:
        """Run anomaly detection on the provided data.

        Returns a dict with anomaly_score and is_anomaly flag.
        """
        return {"anomaly_score": 0.0, "is_anomaly": False}
