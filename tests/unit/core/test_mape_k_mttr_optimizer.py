"""
Unit tests for MAPE-K MTTR Optimizer.

Tests MTTR optimization including parallel execution, priority queuing,
and adaptive monitoring intervals.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.mape_k_mttr_optimizer import (ActionPriority,
                                            AdaptiveMonitoringIntervals,
                                            MTTROptimizer,
                                            ParallelMAPEKExecutor,
                                            RecoveryPhase,
                                            calculate_mttr_improvement)


class TestActionPriority:
    """Test action priority data structure"""

    def test_action_priority_creation(self):
        """Test creating action priority"""
        action = ActionPriority(
            action_id="test_action",
            action_type="critical",
            estimated_mttr_reduction=5.0,
        )

        assert action.action_id == "test_action"
        assert action.action_type == "critical"
        assert action.estimated_mttr_reduction == 5.0
        assert action.executed is False

    def test_action_priority_with_dependencies(self):
        """Test action with dependencies"""
        action = ActionPriority(
            action_id="dependent_action",
            action_type="high",
            estimated_mttr_reduction=3.0,
            dependencies=["action1", "action2"],
        )

        assert len(action.dependencies) == 2
        assert "action1" in action.dependencies


class TestParallelMAPEKExecutor:
    """Test parallel MAPE-K execution"""

    @pytest.fixture
    def executor(self):
        return ParallelMAPEKExecutor(max_parallel_tasks=8)

    @pytest.mark.asyncio
    async def test_sequential_execution(self, executor):
        """Test sequential phase execution"""
        # Mock tasks
        monitor = AsyncMock(return_value={"cpu": 50})
        analyze = AsyncMock(return_value={"state": "healthy"})
        plan = AsyncMock(return_value={"actions": []})
        execute = AsyncMock(return_value={"executed": 0})
        knowledge = AsyncMock(return_value={"logged": True})

        result = await executor.execute_parallel(
            monitor, analyze, plan, execute, knowledge
        )

        assert "monitor" in result
        assert "analyze" in result
        assert "timings" in result
        assert result["monitor"]["cpu"] == 50

    @pytest.mark.asyncio
    async def test_parallel_execution_during_recovery(self, executor):
        """Test parallel Plan and Execute during recovery"""
        # Mock tasks
        monitor = AsyncMock(return_value={"cpu": 95})
        analyze = AsyncMock(
            return_value={
                "state": "critical",
                "is_critical": True,
                "is_degraded": True,
                "recovery_in_progress": True,
            }
        )
        plan = AsyncMock(return_value={"actions": ["restart", "isolate"]})
        execute = AsyncMock(return_value={"executed": 2})
        knowledge = AsyncMock(return_value={"logged": True})

        result = await executor.execute_parallel(
            monitor, analyze, plan, execute, knowledge
        )

        assert result["analyze"]["is_critical"] is True
        assert "timings" in result
        assert result["timings"]["total"] > 0

    @pytest.mark.asyncio
    async def test_recovery_state_detection(self, executor):
        """Test recovery state detection"""
        # Test healthy state
        healthy = {"is_degraded": False, "is_critical": False}
        assert executor._is_recovery_state(healthy) is False

        # Test critical state
        critical = {"is_degraded": True, "is_critical": True}
        assert executor._is_recovery_state(critical) is True

        # Test recovery in progress
        recovering = {"recovery_in_progress": True}
        assert executor._is_recovery_state(recovering) is True


class TestMTTROptimizer:
    """Test MTTR optimization"""

    @pytest.fixture
    def optimizer(self):
        return MTTROptimizer()

    def test_mttr_optimizer_initialization(self, optimizer):
        """Test MTTR optimizer initialization"""
        assert optimizer.current_recovery is None
        assert len(optimizer.recovery_history) == 0
        assert "transient_error" in optimizer.mttr_targets

    def test_start_recovery_tracking(self, optimizer):
        """Test starting recovery tracking"""
        optimizer.start_recovery_tracking("service_failure")

        assert optimizer.current_recovery is not None
        assert optimizer.current_recovery.phase == RecoveryPhase.DETECTION
        assert optimizer.current_recovery.actions_executed == 0

    def test_recovery_phase_progression(self, optimizer):
        """Test recovery phases progress correctly"""
        optimizer.start_recovery_tracking("network_issue")
        assert optimizer.current_recovery.phase == RecoveryPhase.DETECTION

        optimizer.record_diagnosis_complete()
        assert optimizer.current_recovery.phase == RecoveryPhase.DIAGNOSIS

        optimizer.record_first_action()
        assert optimizer.current_recovery.phase == RecoveryPhase.ACTION

        optimizer.record_recovery_complete(success=True)
        assert optimizer.current_recovery is None
        assert len(optimizer.recovery_history) == 1

    def test_recovery_timing_metrics(self, optimizer):
        """Test recovery timing metrics are recorded"""
        optimizer.start_recovery_tracking("service_failure")

        # Simulate delays
        time.sleep(0.01)
        optimizer.record_diagnosis_complete()

        time.sleep(0.01)
        optimizer.record_first_action()

        time.sleep(0.01)
        optimizer.record_recovery_complete(success=True)

        # Verify metrics
        recovery = optimizer.recovery_history[0]
        assert recovery.diagnosis_time > recovery.detection_time
        assert recovery.first_action_time > recovery.diagnosis_time
        assert recovery.recovery_complete_time > recovery.first_action_time
        assert recovery.recovery_success_rate == 1.0

    def test_action_priority_execution(self, optimizer):
        """Test priority-based action execution"""
        actions = [
            ActionPriority("low_action", "low", 1.0),
            ActionPriority("critical_action", "critical", 5.0),
            ActionPriority("high_action", "high", 3.0),
        ]

        executed, exec_time = optimizer.execute_action_priority_queue(actions)

        # Critical should execute first
        assert executed[0].action_type == "critical"
        assert executed[1].action_type == "high"
        assert executed[2].action_type == "low"

    def test_action_dependency_handling(self, optimizer):
        """Test action dependency resolution"""
        actions = [
            ActionPriority("action1", "critical", 5.0),
            ActionPriority("action2", "high", 3.0, dependencies=["action1"]),
            ActionPriority(
                "action3", "medium", 2.0, dependencies=["action1", "action2"]
            ),
        ]

        executed, _ = optimizer.execute_action_priority_queue(actions)

        # All should execute in dependency order
        assert len(executed) == 3
        # action1 should execute first
        assert executed[0].action_id == "action1"

    def test_mttr_statistics_empty(self, optimizer):
        """Test MTTR statistics with no history"""
        stats = optimizer.get_mttr_statistics()
        assert stats["total_recoveries"] == 0

    def test_mttr_statistics_with_history(self, optimizer):
        """Test MTTR statistics with recovery history"""
        # Record multiple recoveries
        for i in range(3):
            optimizer.start_recovery_tracking("test_issue")
            time.sleep(0.01)
            optimizer.record_diagnosis_complete()
            optimizer.record_first_action()
            optimizer.record_recovery_complete(success=True)

        stats = optimizer.get_mttr_statistics()
        assert stats["total_recoveries"] == 3
        assert "average_mttr" in stats
        assert "success_rate" in stats
        assert stats["success_rate"] == 1.0

    def test_recovery_failure_tracking(self, optimizer):
        """Test tracking failed recoveries"""
        optimizer.start_recovery_tracking("network_issue")
        time.sleep(0.01)
        optimizer.record_recovery_complete(success=False)

        recovery = optimizer.recovery_history[0]
        assert recovery.recovery_success_rate == 0.0

        stats = optimizer.get_mttr_statistics()
        assert stats["success_rate"] == 0.0


class TestAdaptiveMonitoringIntervals:
    """Test adaptive monitoring interval adjustment"""

    @pytest.fixture
    def intervals(self):
        return AdaptiveMonitoringIntervals()

    def test_initialization(self, intervals):
        """Test initialization with default intervals"""
        assert intervals.current_state == "healthy"
        assert intervals.get_interval() == 60.0

    def test_state_transition_healthy_to_degraded(self, intervals):
        """Test transition from healthy to degraded"""
        interval = intervals.update_state("degraded")
        assert interval == 15.0
        assert intervals.current_state == "degraded"

    def test_state_transition_to_critical(self, intervals):
        """Test transition to critical state"""
        interval = intervals.update_state("critical")
        assert interval == 3.0
        assert intervals.current_state == "critical"

    def test_recovery_state_interval(self, intervals):
        """Test recovery state has appropriate interval"""
        interval = intervals.update_state("recovering")
        assert interval == 5.0

    def test_invalid_state_ignored(self, intervals):
        """Test that invalid states are ignored"""
        original_interval = intervals.get_interval()
        intervals.update_state("invalid_state")

        # Should remain unchanged
        assert intervals.get_interval() == original_interval

    def test_interval_statistics(self, intervals):
        """Test interval statistics"""
        intervals.update_state("critical")
        stats = intervals.get_statistics()

        assert stats["current_state"] == "critical"
        assert stats["current_interval"] == 3.0
        assert "configured_intervals" in stats


class TestMTTRImprovement:
    """Test MTTR improvement calculations"""

    def test_calculate_improvement_baseline(self):
        """Test calculating improvement from baseline"""
        improvement = calculate_mttr_improvement(
            baseline_mttr=30.0, optimized_mttr=10.0
        )

        assert improvement["time_saved_seconds"] == 20.0
        assert improvement["percent_improvement"] == pytest.approx(66.67, rel=0.01)
        assert improvement["speedup_factor"] == 3.0

    def test_calculate_improvement_no_improvement(self):
        """Test when there's no improvement"""
        improvement = calculate_mttr_improvement(
            baseline_mttr=10.0, optimized_mttr=10.0
        )

        assert improvement["time_saved_seconds"] == 0.0
        assert improvement["percent_improvement"] == 0.0
        assert improvement["speedup_factor"] == 1.0

    def test_calculate_improvement_worse_case(self):
        """Test when optimization makes things worse"""
        improvement = calculate_mttr_improvement(
            baseline_mttr=10.0, optimized_mttr=20.0
        )

        assert improvement["time_saved_seconds"] == -10.0
        assert improvement["percent_improvement"] == -100.0
        assert improvement["speedup_factor"] == 0.5


@pytest.mark.asyncio
class TestMTTREndToEnd:
    """End-to-end tests for MTTR optimization"""

    async def test_complete_recovery_cycle(self):
        """Test complete recovery cycle with MTTR tracking"""
        executor = ParallelMAPEKExecutor()
        optimizer = MTTROptimizer()

        # Start recovery
        optimizer.start_recovery_tracking("service_failure")

        # Mock MAPE-K tasks
        monitor = AsyncMock(return_value={"error_rate": 95})
        analyze = AsyncMock(return_value={"state": "critical", "is_critical": True})
        plan = AsyncMock(return_value={"actions": ["restart_service", "clear_cache"]})
        execute = AsyncMock(return_value={"executed": 2})
        knowledge = AsyncMock(return_value={"learned": True})

        # Record phases
        optimizer.record_diagnosis_complete()

        # Execute parallel MAPE-K
        result = await executor.execute_parallel(
            monitor, analyze, plan, execute, knowledge
        )

        optimizer.record_first_action()

        # Simulate recovery
        time.sleep(0.01)
        optimizer.record_recovery_complete(success=True)

        # Verify metrics
        assert len(optimizer.recovery_history) == 1
        recovery = optimizer.recovery_history[0]
        assert recovery.recovery_success_rate == 1.0
        assert recovery.actions_executed == 0  # Not incremented in this test
