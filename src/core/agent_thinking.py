"""Agent thinking coach — stub for test compatibility."""

from __future__ import annotations


class AgentThinkingCoach:
    """Agent thinking coach stub."""
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze(self, context: dict) -> dict:
        return {"recommendation": "monitor", "confidence": 0.5}
