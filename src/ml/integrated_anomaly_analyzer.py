"""Integrated anomaly analyzer — stub for ML tests."""

from __future__ import annotations

from typing import Any


class IntegratedAnomalyAnalyzer:
    """Stub for IntegratedAnomalyAnalyzer."""
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze(self, data: Any) -> dict:
        return {"anomaly_score": 0.0, "is_anomaly": False}
