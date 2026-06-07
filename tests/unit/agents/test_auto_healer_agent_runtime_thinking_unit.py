"""Runtime-thinking checks for AutoHealerAgent metric collection."""

import pytest

from src.agents.healing.auto_healer_agent import AutoHealerAgent


@pytest.mark.asyncio
async def test_auto_healer_collect_metrics_uses_real_local_sources_not_mock():
    agent = AutoHealerAgent(config={"enabled": False})

    metrics = await agent._collect_metrics()

    assert metrics["mock_metrics"] is False
    assert metrics["synthetic_metrics"] is False
    assert metrics["metric_source"] in {"psutil", "stdlib"}
    assert metrics["cpu_observed"] or metrics["memory_observed"]
    assert metrics["packet_loss_observed"] is False
    assert metrics["latency_observed"] is False
    assert metrics["error_rate_observed"] is False
    assert "not network-health proof" in metrics["metric_claim_boundary"]

    status = agent.thinking_coach.status()
    techniques = set(status["techniques"])
    assert status["profile"]["role"] == "healing"
    assert "mape_k" in techniques
    assert "mind_maps" in techniques
    assert "causal_analysis" in techniques
    assert "graphsage" in techniques
    assert "zero_trust_review" in techniques
    assert "reverse_planning" in techniques

    context = agent.last_thinking_context
    assert context["applied"]["framing"]["problem"] == (
        "auto_healer_metric_collection"
    )
    constraints = context["applied"]["framing"]["constraints"]
    assert constraints["mock_metrics"] is False
    assert constraints["synthetic_metrics"] is False
    assert constraints["packet_loss_requires_external_telemetry"] is True
    assert constraints["latency_requires_external_telemetry"] is True
    assert constraints["error_rate_requires_external_telemetry"] is True
