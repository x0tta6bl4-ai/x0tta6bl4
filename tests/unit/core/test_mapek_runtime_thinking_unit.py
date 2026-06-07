"""Focused tests for MAPE-K runtime thinking telemetry."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.mape_k.monitoring import MonitoringPhase
from src.core.mape_k_feedback_loops import FeedbackLoopManager
from src.core.mape_k_mttr_optimizer import (
    ActionPriority,
    AdaptiveMonitoringIntervals,
    MTTROptimizer,
    ParallelMAPEKExecutor,
)
from src.libx0t.core.mape_k.monitoring import MonitoringPhase as LibX0TMonitoringPhase
from src.libx0t.core.mape_k.coordinator import MAPEKCoordinator as LibX0TMAPEKCoordinator
from src.libx0t.core.mape_k_feedback_loops import (
    FeedbackLoopManager as LibX0TFeedbackLoopManager,
)
from src.libx0t.core.mape_orchestrator import MAPEOrchestrator as LibX0TMAPEOrchestrator
from src.libx0t.core.parl_mapek_integration import (
    MAPEKContext as LibX0TMAPEKContext,
)
from src.libx0t.core.parl_mapek_integration import (
    PARLMAPEKExecutor as LibX0TPARLMAPEKExecutor,
)
from src.libx0t.core.mape_k_mttr_optimizer import (
    ActionPriority as LibX0TActionPriority,
)
from src.libx0t.core.mape_k_mttr_optimizer import (
    AdaptiveMonitoringIntervals as LibX0TAdaptiveMonitoringIntervals,
)
from src.libx0t.core.mape_k_mttr_optimizer import (
    MTTROptimizer as LibX0TMTTROptimizer,
)
from src.libx0t.core.mape_k_mttr_optimizer import (
    ParallelMAPEKExecutor as LibX0TParallelMAPEKExecutor,
)


@pytest.mark.asyncio
async def test_monitoring_phase_thinking_redacts_system_metrics() -> None:
    mape_k = AsyncMock()
    mape_k._monitor = AsyncMock(
        return_value={
            "node_id": "node-secret",
            "cpu_percent": 90,
            "path": "/private/runtime/path",
        }
    )
    monitoring = MonitoringPhase(
        mape_k_loop=mape_k,
        reasoning_history=[
            {"success": False, "dead_end": True, "kb_hit": True, "note": "private"}
        ],
    )

    await monitoring.execute()
    status = json.dumps(monitoring.get_thinking_status(), sort_keys=True)

    assert "mape_k_monitoring_executed" in status
    assert "node-secret" not in status
    assert "/private/runtime/path" not in status
    assert "private" not in status


@pytest.mark.asyncio
async def test_libx0t_monitoring_phase_thinking_redacts_system_metrics() -> None:
    mape_k = AsyncMock()
    mape_k._monitor = AsyncMock(
        return_value={
            "node_id": "lib-node-secret",
            "memory_percent": 95,
            "path": "/private/libx0t/path",
        }
    )
    monitoring = LibX0TMonitoringPhase(mape_k_loop=mape_k)

    await monitoring.execute()
    status = json.dumps(monitoring.get_thinking_status(), sort_keys=True)

    assert "libx0t_mape_k_monitoring_executed" in status
    assert "lib-node-secret" not in status
    assert "/private/libx0t/path" not in status


def test_feedback_loop_thinking_redacts_decision_and_resource_names() -> None:
    manager = FeedbackLoopManager()

    manager.signal_decision_quality(
        "decision-secret", predicted_outcome=0.1, actual_outcome=10.0
    )
    manager.signal_resource_pressure("private-gpu-pool", 0.9)

    status = json.dumps(manager.get_thinking_status(), sort_keys=True)

    assert "feedback_loop_resource_signal" in status
    assert "decision-secret" not in status
    assert "private-gpu-pool" not in status


def test_libx0t_feedback_loop_thinking_redacts_decision_and_resource_names() -> None:
    manager = LibX0TFeedbackLoopManager()

    manager.signal_decision_quality(
        "lib-decision-secret", predicted_outcome=0.1, actual_outcome=10.0
    )
    manager.signal_resource_pressure("lib-private-gpu-pool", 0.9)

    status = json.dumps(manager.get_thinking_status(), sort_keys=True)

    assert "libx0t_feedback_loop_resource_signal" in status
    assert "lib-decision-secret" not in status
    assert "lib-private-gpu-pool" not in status


def test_mttr_optimizer_thinking_redacts_issue_and_action_ids() -> None:
    optimizer = MTTROptimizer()

    optimizer.start_recovery_tracking("secret-service-failure")
    optimizer.execute_action_priority_queue(
        [
            ActionPriority("secret-restart-action", "critical", 5.0),
            ActionPriority(
                "secret-reroute-action",
                "medium",
                2.0,
                dependencies=["secret-restart-action"],
            ),
        ]
    )

    status = json.dumps(optimizer.get_thinking_status(), sort_keys=True)

    assert "mttr_priority_queue_executed" in status
    assert "secret-service-failure" not in status
    assert "secret-restart-action" not in status
    assert "secret-reroute-action" not in status


def test_libx0t_mttr_optimizer_thinking_redacts_issue_and_action_ids() -> None:
    optimizer = LibX0TMTTROptimizer()

    optimizer.start_recovery_tracking("lib-secret-service-failure")
    optimizer.execute_action_priority_queue(
        [
            LibX0TActionPriority("lib-secret-restart-action", "critical", 5.0),
            LibX0TActionPriority(
                "lib-secret-reroute-action",
                "medium",
                2.0,
                dependencies=["lib-secret-restart-action"],
            ),
        ]
    )

    status = json.dumps(optimizer.get_thinking_status(), sort_keys=True)

    assert "libx0t_mttr_priority_queue_executed" in status
    assert "lib-secret-service-failure" not in status
    assert "lib-secret-restart-action" not in status
    assert "lib-secret-reroute-action" not in status


@pytest.mark.asyncio
async def test_parallel_mapek_executor_thinking_redacts_phase_payloads() -> None:
    executor = ParallelMAPEKExecutor()

    await executor.execute_parallel(
        AsyncMock(return_value={"node_id": "node-secret"}),
        AsyncMock(return_value={"is_critical": True, "private": "analysis-secret"}),
        AsyncMock(return_value={"actions": ["secret-plan-action"]}),
        AsyncMock(return_value={"executed": ["secret-execute-action"]}),
        AsyncMock(return_value={"learned": "secret-knowledge"}),
    )

    status = json.dumps(executor.get_thinking_status(), sort_keys=True)

    assert "parallel_mapek_executed" in status
    assert "node-secret" not in status
    assert "analysis-secret" not in status
    assert "secret-plan-action" not in status
    assert "secret-execute-action" not in status
    assert "secret-knowledge" not in status


@pytest.mark.asyncio
async def test_libx0t_parallel_mapek_executor_thinking_redacts_phase_payloads() -> None:
    executor = LibX0TParallelMAPEKExecutor()

    await executor.execute_parallel(
        AsyncMock(return_value={"node_id": "lib-node-secret"}),
        AsyncMock(return_value={"is_critical": True, "private": "lib-analysis-secret"}),
        AsyncMock(return_value={"actions": ["lib-secret-plan-action"]}),
        AsyncMock(return_value={"executed": ["lib-secret-execute-action"]}),
        AsyncMock(return_value={"learned": "lib-secret-knowledge"}),
    )

    status = json.dumps(executor.get_thinking_status(), sort_keys=True)

    assert "libx0t_parallel_mapek_executed" in status
    assert "lib-node-secret" not in status
    assert "lib-analysis-secret" not in status
    assert "lib-secret-plan-action" not in status
    assert "lib-secret-execute-action" not in status
    assert "lib-secret-knowledge" not in status


def test_adaptive_monitoring_intervals_thinking_redacts_unknown_state() -> None:
    intervals = AdaptiveMonitoringIntervals()

    intervals.update_state("private-state-name")
    status = json.dumps(intervals.get_thinking_status(), sort_keys=True)

    assert "adaptive_monitoring_interval_unchanged" in status
    assert "private-state-name" not in status


def test_libx0t_adaptive_monitoring_intervals_thinking_redacts_unknown_state() -> None:
    intervals = LibX0TAdaptiveMonitoringIntervals()

    intervals.update_state("lib-private-state-name")
    status = json.dumps(intervals.get_thinking_status(), sort_keys=True)

    assert "libx0t_adaptive_monitoring_interval_unchanged" in status
    assert "lib-private-state-name" not in status


@pytest.mark.asyncio
async def test_libx0t_mapek_coordinator_thinking_redacts_task_and_node() -> None:
    solution_space = MagicMock()
    solution_space.__dict__ = {"selected": "private-solution"}
    reasoning_path = MagicMock()
    reasoning_path.__dict__ = {"first_step": "private-step"}

    meta_planner = MagicMock()
    meta_planner.execute = AsyncMock(return_value=(solution_space, reasoning_path))
    monitoring = MagicMock()
    monitoring.execute = AsyncMock(return_value={"system_metrics": {"node_id": "n"}})
    analysis = MagicMock()
    analysis.execute = AsyncMock(return_value={"issue": "private-analysis"})
    planning = MagicMock()
    planning.execute = AsyncMock(return_value={"plan": "private-plan"})
    execution = MagicMock()
    execution.execute = AsyncMock(return_value={"result": "private-execution"})
    knowledge = MagicMock()
    knowledge.execute = AsyncMock(return_value={"stored": True})

    coordinator = LibX0TMAPEKCoordinator(
        meta_planner,
        monitoring,
        analysis,
        planning,
        execution,
        knowledge,
        node_id="coordinator-node-secret",
    )

    await coordinator.run_full_cycle(
        {"type": "private-task-type", "description": "private-task-description"}
    )
    status = json.dumps(coordinator.get_thinking_status(), sort_keys=True)

    assert "libx0t_mapek_full_cycle_completed" in status
    assert "coordinator-node-secret" not in status
    assert "private-task-description" not in status
    assert "private-analysis" not in status
    assert "private-plan" not in status
    assert "private-execution" not in status


@pytest.mark.asyncio
async def test_libx0t_mape_orchestrator_thinking_redacts_metrics_and_plan_details() -> None:
    prometheus = MagicMock()
    prometheus.query = AsyncMock(
        return_value={
            "latency_p95_value": 99,
            "node_id": "mape-node-secret",
            "private_path": "/private/mape/path",
        }
    )
    mesh = MagicMock()
    mesh.apply_routing = AsyncMock()
    dao = MagicMock()
    dao.log_event = AsyncMock()
    ipfs = MagicMock()
    ipfs.snapshot = AsyncMock()

    orchestrator = LibX0TMAPEOrchestrator(prometheus, mesh, dao, ipfs)
    metrics = await orchestrator.monitor_cycle()
    plan = await orchestrator.analyze_cycle(metrics)
    plan["target"] = "private-route-target"
    await orchestrator.execute_cycle(plan)

    status = json.dumps(orchestrator.get_thinking_status(), sort_keys=True)

    assert "libx0t_mape_execute_cycle_completed" in status
    assert "mape-node-secret" not in status
    assert "/private/mape/path" not in status
    assert "private-route-target" not in status


@pytest.mark.asyncio
async def test_libx0t_parl_mapek_thinking_redacts_cycle_and_nodes() -> None:
    executor = LibX0TPARLMAPEKExecutor()
    executor._initialized = True

    result = await executor.execute_cycle(
        LibX0TMAPEKContext(
            cycle_id="cycle-secret",
            mesh_nodes=["node-secret-a", "node-secret-b"],
            metrics={"private_metric": "secret-value"},
        )
    )
    status = json.dumps(executor.get_thinking_status(), sort_keys=True)

    assert result["success"] is True
    assert "libx0t_parl_mapek_cycle_completed" in status
    assert "cycle-secret" not in status
    assert "node-secret-a" not in status
    assert "node-secret-b" not in status
    assert "secret-value" not in status
