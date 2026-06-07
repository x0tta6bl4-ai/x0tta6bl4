"""Unit tests for shared agent thinking support."""

from __future__ import annotations

import pytest
import numpy as np

from src.core.agent_thinking import (
    ALL_THINKING_TECHNIQUES,
    AgentThinkingCoach,
    build_agent_thinking_profile,
)
from src.ai.fl_orchestrator_scaling import BatchAsyncOrchestrator
from src.core.enhanced_thinking_techniques import ReversePlanner
from src.federated_learning.ppo_agent import PPOAgent
from src.federated_learning.scalable_orchestrator import ScalableFLOrchestrator
from src.parl.types import Policy, Task
from src.parl.worker import AgentWorker
from src.swarm.agent import Agent, AgentCapability
from src.swarm.agents.pricing_agent import DynamicPricingAgent


def test_catalog_contains_runtime_and_prompt_techniques():
    technique_ids = {item.technique_id for item in ALL_THINKING_TECHNIQUES}

    assert len(technique_ids) >= 20
    assert "six_thinking_hats" in technique_ids
    assert "first_principles" in technique_ids
    assert "lateral_thinking" in technique_ids
    assert "mind_maps" in technique_ids
    assert "reverse_planning" in technique_ids
    assert "scamper" in technique_ids
    assert "lotus_blossom" in technique_ids
    assert "stride_threat_modeling" in technique_ids
    assert "weighted_decision_matrix" in technique_ids


def test_role_profile_selects_base_and_role_specific_techniques():
    profile = build_agent_thinking_profile(
        agent_id="security-1",
        role="security",
        capabilities=("zero-trust",),
    )

    assert "think_aloud" in profile.techniques
    assert "framing" in profile.techniques
    assert "stride_threat_modeling" in profile.techniques
    assert "zero_trust_review" in profile.techniques
    assert "weighted_decision_matrix" in profile.techniques


def test_reverse_planner_does_not_loop_on_generic_goal():
    plan = ReversePlanner().plan("format KPI report with clear signal")

    assert len(plan) <= 9
    assert plan[-1] == "Начальное состояние"


def test_agent_thinking_coach_prepares_serializable_context():
    coach = AgentThinkingCoach(
        agent_id="healer-1",
        role="healing",
        capabilities=("mape_k", "recovery"),
    )

    context = coach.prepare_task(
        {
            "type": "healing",
            "goal": "recover service",
            "complexity": 0.8,
            "metrics": {"packet_loss_percent": 7.0},
        }
    )

    assert context["agent_id"] == "healer-1"
    assert "six_thinking_hats" in context["applied"]
    assert "first_principles" in context["applied"]
    assert "reverse_planning" in context["applied"]
    assert "mape_k" in {item["technique_id"] for item in context["documented_guidance"]}


@pytest.mark.asyncio
async def test_swarm_agent_exposes_thinking_profile_and_task_context():
    agent = Agent(
        agent_id="monitor-1",
        swarm_id="monitoring",
        capabilities=[AgentCapability(name="monitoring")],
    )

    result = await agent.execute_task(
        {
            "task_id": "task-1",
            "task_type": "monitoring",
            "payload": {"node_id": "node-1"},
        }
    )

    assert result.success is True
    assert result.thinking_context["role"] == "monitoring"
    assert "mind_maps" in result.thinking_context["techniques"]
    assert "thinking" in agent.get_status()


@pytest.mark.asyncio
async def test_pricing_agent_returns_thinking_techniques_without_mutating_policy_input():
    calls: list[dict] = []

    async def policy(payload):
        calls.append(dict(payload))
        return {
            "suggested_price": 0.031,
            "multiplier": 3.1,
            "confidence": 0.97,
            "pricing_model": "test_policy",
        }

    agent = DynamicPricingAgent("pricing-1", pricing_policy=policy)
    result = await agent.execute_task("task-1", {"node_id": "node-a"})

    assert calls == [{"node_id": "node-a"}]
    assert result["pricing_model"] == "test_policy"
    assert "six_thinking_hats" in result["thinking_techniques"]
    assert "weighted_decision_matrix" in result["thinking_techniques"]


def test_ppo_agent_records_thinking_context_for_action_and_update():
    agent = PPOAgent(state_dim=4, action_dim=2)

    action, log_prob, value = agent.get_action([0.1, 0.2, 0.3, 0.4], deterministic=True)

    assert action in {0, 1}
    assert isinstance(log_prob, float)
    assert isinstance(value, float)
    assert agent.last_thinking_context["role"] == "fl"
    assert "weighted_decision_matrix" in agent.last_thinking_context["techniques"]

    metrics = agent.update()

    assert metrics == {"loss": 0.0}
    assert agent.last_thinking_context["applied"]["framing"]["problem"] == "ppo_policy_update"


@pytest.mark.asyncio
async def test_scalable_fl_orchestrator_records_thinking_context():
    orchestrator = ScalableFLOrchestrator(
        orchestrator_id="fl-test",
        num_coordinators=1,
        max_nodes_per_coordinator=10,
    )

    task = await orchestrator.start_training_round(
        round_number=7,
        target_participants=3,
    )

    status = orchestrator.get_status()

    assert task.task_id == "round-7"
    assert status["thinking"]["profile"]["role"] == "fl"
    assert status["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "adaptive_fl_node_selection"
    )


def test_batch_fl_orchestrator_records_thinking_context_without_changing_shape():
    orchestrator = BatchAsyncOrchestrator(np.array([1.0, 2.0, 3.0]))

    result = orchestrator.aggregate_updates([])

    np.testing.assert_array_equal(result, np.array([0.0, 0.0, 0.0]))
    assert orchestrator.last_thinking_context["role"] == "fl"
    assert orchestrator.last_thinking_context["applied"]["framing"]["problem"] == (
        "batch_async_fl_aggregation"
    )


@pytest.mark.asyncio
async def test_parl_agent_worker_records_thinking_context():
    worker = AgentWorker(
        worker_id="worker-thinking",
        policy=Policy(policy_id="policy-thinking"),
    )

    result = await worker.execute_step(Task(task_type="health_check", payload={}))
    status = worker.get_status()

    assert result.success is True
    assert status["thinking"]["profile"]["role"] == "coordinator"
    assert status["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "health_check"
    )
