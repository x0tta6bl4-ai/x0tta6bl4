"""Stub: Hybrid Anomaly System (purged in honest mode).

Original module was removed during honest-mode cleanup.
This stub allows dependent integration tests to import successfully.
"""

from __future__ import annotations

from enum import auto, Enum
from typing import Any


class HybridDetectionMode(Enum):
    PRODUCTION_ONLY = auto()
    ENSEMBLE_ONLY = auto()
    HYBRID = auto()


class HybridAnomalySystem:
    """Stub — was removed during honest-mode cleanup."""

    def __init__(self, config: dict | None = None, mode: HybridDetectionMode = HybridDetectionMode.HYBRID) -> None:
        self.config = config or {}
        self.mode = mode

    async def detect(self, data: dict) -> dict:
        return {"anomaly_score": 0.0, "is_anomaly": False}
