"""MAPE-K quality integration — stubs for test compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityThresholds:
    """Quality thresholds stub."""
    min_coverage: float = 0.8
    max_complexity: int = 10


@dataclass
class QualityImprovement:
    """Quality improvement stub."""
    file_path: str = ""
    score_before: float = 0.0
    score_after: float = 0.0


class MAPEKQualityMonitor:
    """MAPE-K quality monitor stub."""
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze(self, repo_path: str) -> list[QualityImprovement]:
        return []

    def get_thresholds(self) -> QualityThresholds:
        return QualityThresholds()
