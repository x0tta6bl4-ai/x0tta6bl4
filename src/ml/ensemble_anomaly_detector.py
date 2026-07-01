"""Ensemble anomaly detector — stub for test compatibility."""

from __future__ import annotations

from enum import Enum
from typing import Any


class EnsembleVotingStrategy(Enum):
    """Voting strategies for ensemble detectors."""
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    CONSENSUS = "consensus"


class IQRDetector:
    """IQR-based anomaly detector stub."""
    def __init__(self, threshold: float = 1.5):
        self.threshold = threshold

    def fit(self, X: Any) -> "IQRDetector":
        return self

    def predict(self, X: Any) -> list[int]:
        return [0] * len(X)


class IsolationForestDetector:
    """Isolation Forest anomaly detector stub."""
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination

    def fit(self, X: Any) -> "IsolationForestDetector":
        return self

    def predict(self, X: Any) -> list[int]:
        return [0] * len(X)


class LocalOutlierFactorDetector:
    """LOF anomaly detector stub."""
    def __init__(self, n_neighbors: int = 20):
        self.n_neighbors = n_neighbors

    def fit(self, X: Any) -> "LocalOutlierFactorDetector":
        return self

    def predict(self, X: Any) -> list[int]:
        return [0] * len(X)


class MovingAverageDetector:
    """Moving average anomaly detector stub."""
    def __init__(self, window: int = 10, threshold: float = 2.0):
        self.window = window
        self.threshold = threshold

    def fit(self, X: Any) -> "MovingAverageDetector":
        return self

    def predict(self, X: Any) -> list[int]:
        return [0] * len(X)


class EnsembleAnomalyDetector:
    """Ensemble anomaly detector stub."""
    def __init__(self, detectors: list[Any] | None = None, strategy: EnsembleVotingStrategy = EnsembleVotingStrategy.MAJORITY):
        self.detectors = detectors or []
        self.strategy = strategy

    def fit(self, X: Any) -> "EnsembleAnomalyDetector":
        for d in self.detectors:
            d.fit(X)
        return self

    def predict(self, X: Any) -> list[int]:
        return [0] * len(X)


def get_ensemble_detector(strategy: str = "majority") -> EnsembleAnomalyDetector:
    """Factory function stub."""
    return EnsembleAnomalyDetector()
