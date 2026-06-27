from __future__ import annotations

import pytest

from src.swarm.agents.pricing_agent import DynamicPricingAgent, MarketSignalPricingPolicy


@pytest.mark.asyncio
async def test_dynamic_pricing_agent_uses_bounded_market_signals():
    agent = DynamicPricingAgent("pricing-1", base_price=0.02)

    result = await agent.execute_task(
        "task-1",
        {
            "node_id": "node-a",
            "demand_score": 0.8,
            "scarcity": 0.4,
            "utilization": 0.7,
            "reliability_score": 0.9,
            "region_cost_multiplier": 1.2,
        },
    )

    assert result["node_id"] == "node-a"
    assert result["task_id"] == "task-1"
    assert result["suggested_price"] > 0.02
    assert result["pricing_model"] == "market_signal_policy"
    assert result["signals"]["defaulted"] == []
    assert agent.completed_tasks == 1
    assert agent.metrics["tasks_completed"] == 1


@pytest.mark.asyncio
async def test_dynamic_pricing_agent_rejects_out_of_range_signals():
    agent = DynamicPricingAgent("pricing-2")

    with pytest.raises(ValueError, match="demand_score must be between"):
        await agent.execute_task(
            "task-2",
            {
                "node_id": "node-b",
                "demand_score": 1.2,
            },
        )

    assert agent.failed_tasks == 1
    assert agent.metrics["tasks_failed"] == 1


@pytest.mark.asyncio
async def test_dynamic_pricing_agent_accepts_injected_policy():
    calls = []

    async def policy(payload):
        calls.append(payload)
        return {
            "suggested_price": 0.031,
            "multiplier": 3.1,
            "confidence": 0.97,
            "pricing_model": "test_policy",
        }

    agent = DynamicPricingAgent("pricing-3", pricing_policy=policy)

    result = await agent.execute_task("task-3", {"node_id": "node-c"})

    assert calls == [{"node_id": "node-c"}]
    assert result["suggested_price"] == 0.031
    assert result["multiplier"] == 3.1
    assert result["confidence"] == 0.97
    assert result["pricing_model"] == "test_policy"


def test_market_signal_policy_rejects_missing_node_id():
    policy = MarketSignalPricingPolicy(base_price=0.01)

    with pytest.raises(ValueError, match="node_id is required"):
        policy.recommend({"demand_score": 0.4})
