"""Stub: LoRA Adapter (purged in honest mode).

Original module was removed during honest-mode cleanup.
This stub allows dependent integration tests to import successfully.
"""

from __future__ import annotations

from typing import Any


class LoRAConfig:
    def __init__(self, rank: int = 8, alpha: float = 16.0) -> None:
        self.rank = rank
        self.alpha = alpha


class LoRAAdapter:
    """Stub — was removed during honest-mode cleanup."""

    def __init__(self, config: LoRAConfig | None = None) -> None:
        self.config = config or LoRAConfig()

    def apply(self, model: Any) -> Any:
        return model
