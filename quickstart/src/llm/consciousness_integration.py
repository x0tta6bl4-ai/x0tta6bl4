"""LLM Consciousness Integration — bridges LLM gateway with consciousness analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemAnalysis:
    """Result of a system analysis by the LLM."""
    summary: str = ""
    confidence: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class HealingDecision:
    """Decision produced by the LLM healing process."""
    action: str = "noop"
    reason: str = ""


class ConsciousnessLLMIntegration:
    """Integrates an LLM with the consciousness analysis pipeline."""

    def __init__(self, llm: Any, config: dict | None = None) -> None:
        self.llm = llm
        self.config = config or {}

    async def analyze(self, context: dict) -> SystemAnalysis:
        """Analyze system context and produce a structured analysis."""
        if hasattr(self.llm, "generate"):
            prompt = f"Analyze this context: {context}"
            result = await self.llm.generate(prompt) if hasattr(self.llm.generate, "__await__") else self.llm.generate(prompt)
            return SystemAnalysis(summary=str(result), confidence=0.8, details={"raw": str(result)})
        return SystemAnalysis()

    async def decide(self, analysis: SystemAnalysis) -> HealingDecision:
        """Decide on a healing action based on analysis."""
        return HealingDecision(action="monitor", reason=f"Analysis: {analysis.summary}")


def create_consciousness_integration(config: dict | None = None) -> ConsciousnessLLMIntegration:
    """Factory: create a ConsciousnessLLMIntegration with default mock LLM."""
    return ConsciousnessLLMIntegration(None, config)
