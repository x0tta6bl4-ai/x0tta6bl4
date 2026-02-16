"""Unit tests for enhanced thinking techniques module."""

from src.core.enhanced_thinking_techniques import (FirstPrinciplesThinking,
                                                   SixThinkingHats)


def test_six_thinking_hats_produces_all_sections():
    hats = SixThinkingHats()
    analysis = hats.analyze(
        {"type": "incident", "description": "packet loss", "complexity": 0.8}
    )

    assert "facts" in analysis.white
    assert "risks" in analysis.black
    assert "creative_ideas" in analysis.green
    assert analysis.blue["quality"] == "high"


def test_first_principles_decompose_and_build_from_scratch():
    fp = FirstPrinciplesThinking()
    decomposition = fp.decompose(
        {"type": "network", "goal": "reduce loss", "constraints": "latency<50"}
    )
    solution = fp.build_from_scratch(decomposition)

    assert solution["built_from_scratch"] is True
    assert isinstance(solution["fundamentals"], list)
    assert len(solution["core_truths_applied"]) > 0
