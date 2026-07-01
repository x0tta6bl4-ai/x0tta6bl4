"""Stub: Decision Engine (purged in honest mode).

Original module was removed during honest-mode cleanup.
This stub allows dependent integration tests to import successfully.
"""

from __future__ import annotations

from enum import auto, IntEnum
from typing import Any


class PolicyPriority(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class Policy:
    def __init__(self, name: str, priority: PolicyPriority = PolicyPriority.MEDIUM) -> None:
        self.name = name
        self.priority = priority


class DecisionEngine:
    """Stub — was removed during honest-mode cleanup."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    async def decide(self, context: dict) -> dict:
        return {"decision": "noop", "confidence": 1.0}
