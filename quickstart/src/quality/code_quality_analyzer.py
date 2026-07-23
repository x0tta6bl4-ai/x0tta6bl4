"""Code quality analyzer — stubs for test compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityMetrics:
    """Quality metrics stub."""
    score: float = 0.0
    issues: list[dict] = field(default_factory=list)


class CodeQualityAnalyzer:
    """Code quality analyzer stub."""
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze(self, code: str) -> QualityMetrics:
        return QualityMetrics(score=0.8)

    def get_report(self, metrics: QualityMetrics) -> dict:
        return {"score": metrics.score, "issues": metrics.issues}
