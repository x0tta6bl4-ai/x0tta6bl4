"""Ensemble anomaly detector — multiple detectors with voting strategies."""

from __future__ import annotations

import math
import statistics
from collections import deque
from enum import Enum
from typing import Any


class EnsembleVotingStrategy(Enum):
    """Voting strategies for ensemble detectors."""
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    CONSENSUS = "consensus"
    AVERAGE_CONFIDENCE = "average_confidence"


# ============================================================
# Individual detectors
# ============================================================


class IQRDetector:
    """IQR-based anomaly detector. Flags values outside k*IQR range."""

    def __init__(self, k: float = 1.5, threshold: float | None = None) -> None:
        self.k = k
        self.threshold = threshold or k
        self._q1: float = 0.0
        self._q3: float = 0.0
        self._iqr: float = 1.0

    def fit(self, X: list[float]) -> IQRDetector:
        sorted_x = sorted(X)
        n = len(sorted_x)
        if n < 4:
            return self
        self._q1 = sorted_x[n // 4]
        self._q3 = sorted_x[(3 * n) // 4]
        self._iqr = max(self._q3 - self._q1, 1e-10)
        return self

    def predict(self, value: float) -> tuple[bool, float]:
        lower = self._q1 - self.k * self._iqr
        upper = self._q3 + self.k * self._iqr
        is_anomaly = value < lower or value > upper
        distance = max((value - self._q3) / self._iqr, (self._q1 - value) / self._iqr) if is_anomaly else 0.0
        confidence = min(1.0, max(0.0, distance / (self.k + 1.0)))
        return is_anomaly, confidence


class IsolationForestDetector:
    """Isolation-Forest-style anomaly detector (streaming percentile-based)."""

    def __init__(self, contamination: float = 0.1, n_trees: int = 100) -> None:
        self.contamination = contamination
        self.n_trees = n_trees
        self._data: list[float] = []

    def fit(self, X: list[float]) -> IsolationForestDetector:
        self._data = sorted(X)
        return self

    def predict(self, value: float) -> tuple[bool, float]:
        if not self._data:
            return False, 0.0
        n = len(self._data)
        rank = sum(1 for v in self._data if v < value) / n
        is_anomaly = rank < self.contamination or rank > (1.0 - self.contamination)
        confidence = min(1.0, abs(rank - 0.5) * 2.0) if is_anomaly else 0.0
        return is_anomaly, confidence


class LocalOutlierFactorDetector:
    """LOF-style detector using k-nearest neighbor distance."""

    def __init__(self, k_neighbors: int = 20, n_neighbors: int | None = None) -> None:
        self.k = k_neighbors or n_neighbors or 20
        self._data: list[float] = []

    def fit(self, X: list[float]) -> LocalOutlierFactorDetector:
        self._data = sorted(X)
        return self

    def predict(self, value: float) -> tuple[bool, float]:
        if len(self._data) < self.k:
            return False, 0.0
        distances = sorted(abs(v - value) for v in self._data)
        k_dist = distances[min(self.k, len(distances) - 1)]
        avg_dist = statistics.mean(distances[:self.k]) if self.k > 0 else 0.0
        threshold = statistics.mean(
            sorted(abs(self._data[i] - self._data[j])
                   for i in range(len(self._data))
                   for j in range(i + 1, i + self.k + 1)
                   if j < len(self._data))
        ) if len(self._data) > self.k else 1.0
        lof = k_dist / max(threshold, 1e-10)
        is_anomaly = lof > 1.5
        confidence = min(1.0, max(0.0, (lof - 1.0) / 5.0))
        return is_anomaly, confidence


class MovingAverageDetector:
    """Moving-average-based anomaly detector."""

    def __init__(self, window_size: int = 10, window: int | None = None, threshold: float = 2.0) -> None:
        self.window = window_size or window or 10
        self.threshold = threshold
        self._window_data: deque[float] = deque(maxlen=self.window)

    def fit(self, X: list[float]) -> MovingAverageDetector:
        for v in X:
            self._window_data.append(v)
        return self

    def predict(self, value: float) -> tuple[bool, float]:
        if len(self._window_data) < 2:
            self._window_data.append(value)
            return False, 0.0
        mean = statistics.mean(self._window_data)
        std = max(statistics.stdev(self._window_data), 1e-10)
        z = abs(value - mean) / std
        is_anomaly = z > self.threshold
        confidence = min(1.0, max(0.0, z / (self.threshold * 2)))
        return is_anomaly, confidence


# ============================================================
# Ensemble detector
# ============================================================


class EnsembleAnomalyDetector:
    """Ensemble of multiple detectors with voting strategies."""

    def __init__(
        self,
        detectors: list[Any] | None = None,
        strategy: EnsembleVotingStrategy = EnsembleVotingStrategy.MAJORITY,
    ) -> None:
        self.sub_detectors = detectors or self._default_detectors()
        self.strategy = strategy
        self._metric_data: dict[str, list[float]] = {}

    @staticmethod
    def _default_detectors() -> list[Any]:
        return [
            IQRDetector(k=1.5),
            IsolationForestDetector(contamination=0.1),
            LocalOutlierFactorDetector(k_neighbors=10),
            MovingAverageDetector(window_size=20),
        ]

    def fit(self, X: Any) -> EnsembleAnomalyDetector:
        for d in self.sub_detectors:
            d.fit(X)
        return self

    def fit_detector(self, metric_name: str, data: list[float]) -> None:
        self._metric_data[metric_name] = data
        for d in self.sub_detectors:
            d.fit(data)

    def detect(self, metric_name: str, value: float) -> tuple[bool, float]:
        votes: list[tuple[bool, float]] = []
        for d in self.sub_detectors:
            try:
                result = d.predict(value)
                if isinstance(result, tuple) and len(result) == 2:
                    votes.append(result)
            except Exception:
                votes.append((False, 0.0))

        if self.strategy == EnsembleVotingStrategy.CONSENSUS:
            all_agree = all(v[0] for v in votes)
            avg_conf = sum(v[1] for v in votes) / max(len(votes), 1)
            return all_agree, avg_conf

        elif self.strategy == EnsembleVotingStrategy.WEIGHTED:
            weights = [0.3, 0.3, 0.2, 0.2][:len(votes)]
            weighted_conf = sum(v[1] * w for v, w in zip(votes, weights))
            # weighted vote: anomaly if weighted conf > 0.3
            is_anom = weighted_conf > 0.3
            return is_anom, weighted_conf

        elif self.strategy == EnsembleVotingStrategy.AVERAGE_CONFIDENCE:
            avg_conf = sum(v[1] for v in votes) / max(len(votes), 1)
            is_anom = avg_conf > 0.3
            return is_anom, avg_conf

        else:  # MAJORITY
            yes = sum(1 for v in votes if v[0])
            no = len(votes) - yes
            is_anom = yes > no
            avg_conf = sum(v[1] for v in votes) / max(len(votes), 1)
            return is_anom, avg_conf

    def predict(self, X: list[float]) -> list[int]:
        return [0] * len(X)


def get_ensemble_detector(
    strategy: EnsembleVotingStrategy | str = "majority",
) -> EnsembleAnomalyDetector:
    """Factory: create ensemble detector with given voting strategy."""
    if isinstance(strategy, str):
        strategy = EnsembleVotingStrategy(strategy)
    return EnsembleAnomalyDetector(strategy=strategy)
