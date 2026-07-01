"""Stub: MLOps Manager (purged in honest mode).

Original module was removed during honest-mode cleanup.
This stub allows dependent integration tests to import successfully.
"""

from __future__ import annotations

from typing import Any


class ModelMetadata:
    def __init__(self, version: int = 1, round_num: int = 1, participants: list[str] | None = None,
                 aggregation_method: str = "fedavg", num_samples: int = 100) -> None:
        self.version = version
        self.round_num = round_num
        self.participants = participants or []
        self.aggregation_method = aggregation_method
        self.num_samples = num_samples


class MLOpsManager:
    """Stub — was removed during honest-mode cleanup."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    async def log_metrics(self, metrics: dict) -> None:
        pass

    async def get_metrics(self) -> dict:
        return {}
