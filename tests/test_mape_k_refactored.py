"""
Tests for refactored MAPE-K module.

Tests the decomposed MAPE-K components.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio


class TestMAPEKModels:
    """Tests for MAPE-K data models."""

    def test_reasoning_approach_enum(self):
        """Test ReasoningApproach enum values."""
        from src.core.mape_k.models import ReasoningApproach

        assert ReasoningApproach.MAPE_K_ONLY.value == "mape_k_only"
        assert ReasoningApproach.COMBINED_ALL.value == "combined_all"

    def test_solution_space_creation(self):
        """Test SolutionSpace creation."""
        from src.core.mape_k.models import SolutionSpace

        space = SolutionSpace(
            approaches=[{"name": "test", "probability": 0.9}],
            selected_approach="test",
        )

        assert len(space.approaches) == 1
        assert space.selected_approach == "test"
        assert space.failure_history == []

    def test_reasoning_path_creation(self):
        """Test ReasoningPath creation."""
        from src.core.mape_k.models import ReasoningPath

        path = ReasoningPath(
            first_step="monitor",
            dead_ends_to_avoid=["bad_approach"],
            checkpoints=[{"name": "cp1", "metric": "test"}],
        )

        assert path.first_step == "monitor"
        assert len(path.dead_ends_to_avoid) == 1
        assert len(path.checkpoints) == 1

    def test_reasoning_metrics(self):
        """Test ReasoningMetrics creation."""
        from src.core.mape_k.models import ReasoningMetrics

        metrics = ReasoningMetrics(
            approaches_tried=5,
            dead_ends_encountered=2,
            confidence_level=0.85,
        )

        assert metrics.approaches_tried == 5
        assert metrics.dead_ends_encountered == 2
        assert metrics.confidence_level == 0.85

    def test_execution_log_entry(self):
        """Test ExecutionLogEntry creation."""
        from src.core.mape_k.models import ExecutionLogEntry

        entry = ExecutionLogEntry(
            step={"action": "test"},
            result={"status": "success"},
            duration=0.5,
            reasoning_approach="combined",
            meta_insights={"key": "value"},
        )

        assert entry.step["action"] == "test"
        assert entry.result["status"] == "success"
        assert entry.duration == 0.5


class TestMetaPlanner:
    """Tests for Meta-Planner component."""

    @pytest.mark.asyncio
    async def test_meta_planner_basic(self):
        """Test basic meta-planning execution."""
        from src.core.mape_k.meta_planning import MetaPlanner

        planner = MetaPlanner()
        solution_space, reasoning_path = await planner.execute({"type": "test"})

        assert solution_space is not None
        assert reasoning_path is not None
        assert len(solution_space.approaches) > 0

    @pytest.mark.asyncio
    async def test_meta_planner_with_knowledge_base(self):
        """Test meta-planning with knowledge base."""
        from src.core.mape_k.meta_planning import MetaPlanner

        mock_kb = AsyncMock()
        mock_kb.search_incidents.return_value = []

        planner = MetaPlanner(knowledge_base=mock_kb)
        solution_space, reasoning_path = await planner.execute({"type": "test"})

        assert solution_space.failure_history == []

    def test_build_approaches(self):
        """Test approach building."""
        from src.core.mape_k.meta_planning import MetaPlanner

        planner = MetaPlanner()
        approaches = planner._build_approaches(None, None)

        assert len(approaches) >= 6  # Base approaches


class TestMonitoringPhase:
    """Tests for Monitoring Phase component."""

    @pytest.mark.asyncio
    async def test_monitoring_basic(self):
        """Test basic monitoring execution."""
        from src.core.mape_k.monitoring import MonitoringPhase

        monitoring = MonitoringPhase()
        result = await monitoring.execute()

        assert "system_metrics" in result
        assert "reasoning_metrics" in result

    @pytest.mark.asyncio
    async def test_monitoring_with_mape_k(self):
        """Test monitoring with MAPE-K loop."""
        from src.core.mape_k.monitoring import MonitoringPhase

        mock_mape_k = Mock()
        mock_mape_k._monitor = AsyncMock(return_value={"cpu_percent": 50})

        monitoring = MonitoringPhase(mape_k_loop=mock_mape_k)
        result = await monitoring.execute()

        assert result["system_metrics"]["cpu_percent"] == 50


class TestAnalysisPhase:
    """Tests for Analysis Phase component."""

    @pytest.mark.asyncio
    async def test_analysis_basic(self):
        """Test basic analysis execution."""
        from src.core.mape_k.analysis import AnalysisPhase
        from src.core.mape_k.models import ReasoningMetrics

        analysis = AnalysisPhase()
        metrics = {
            "system_metrics": {},
            "reasoning_metrics": ReasoningMetrics(),
        }
        result = await analysis.execute(metrics)

        assert "system_analysis" in result
        assert "reasoning_analysis" in result

    def test_assess_efficiency(self):
        """Test efficiency assessment."""
        from src.core.mape_k.analysis import AnalysisPhase
        from src.core.mape_k.models import ReasoningMetrics

        analysis = AnalysisPhase()

        # High efficiency (low dead ends ratio)
        metrics_high = ReasoningMetrics(
            approaches_tried=10,
            dead_ends_encountered=1,
            reasoning_time=1.0,  # Non-zero to avoid early return
        )
        efficiency_high = analysis._assess_efficiency(metrics_high)
        assert efficiency_high > 0.8

        # Low efficiency (high dead ends ratio)
        metrics_low = ReasoningMetrics(
            approaches_tried=10,
            dead_ends_encountered=8,
            reasoning_time=1.0,  # Non-zero to avoid early return
        )
        efficiency_low = analysis._assess_efficiency(metrics_low)
        assert efficiency_low < 0.3


class TestPlanningPhase:
    """Tests for Planning Phase component."""

    @pytest.mark.asyncio
    async def test_planning_basic(self):
        """Test basic planning execution."""
        from src.core.mape_k.planning import PlanningPhase

        planning = PlanningPhase()
        analysis = {"system_analysis": {}, "reasoning_analysis": {}}
        result = await planning.execute(analysis)

        assert "recovery_plan" in result
        assert "reasoning_optimization" in result

    def test_select_best_approach(self):
        """Test approach selection."""
        from src.core.mape_k.planning import PlanningPhase

        planning = PlanningPhase()

        # Normal case
        analysis_normal = {"reasoning_analysis": {"anomaly_detected": False}}
        approach = planning._select_best_approach(analysis_normal)
        assert approach == "combined_rag_graphsage"

        # Anomaly case
        analysis_anomaly = {"reasoning_analysis": {"anomaly_detected": True}}
        approach = planning._select_best_approach(analysis_anomaly)
        assert approach == "combined_all"


class TestExecutionPhase:
    """Tests for Execution Phase component."""

    @pytest.mark.asyncio
    async def test_execution_basic(self):
        """Test basic execution."""
        from src.core.mape_k.execution import ExecutionPhase

        execution = ExecutionPhase()
        plan = {
            "recovery_plan": {"steps": [{"action": "test"}]},
            "reasoning_optimization": {"approach_selection": "test"},
        }
        result = await execution.execute(plan)

        assert "execution_result" in result
        assert "execution_log" in result

    @pytest.mark.asyncio
    async def test_execution_empty_plan(self):
        """Test execution with empty plan."""
        from src.core.mape_k.execution import ExecutionPhase

        execution = ExecutionPhase()
        result = await execution.execute({})

        assert result["execution_result"]["status"] == "success"


class TestKnowledgePhase:
    """Tests for Knowledge Phase component."""

    @pytest.mark.asyncio
    async def test_knowledge_basic(self):
        """Test basic knowledge accumulation."""
        from src.core.mape_k.knowledge import KnowledgePhase

        knowledge = KnowledgePhase()
        execution_log = {
            "execution_result": {"status": "success"},
            "execution_log": [],
        }
        reasoning_history = []
        stats = {"total": 0, "successful": 0, "failed": 0}

        result = await knowledge.execute(execution_log, reasoning_history, stats)

        assert "incident_record" in result
        assert "reasoning_analytics" in result
        assert "meta_insight" in result

    def test_build_analytics(self):
        """Test analytics building."""
        from src.core.mape_k.knowledge import KnowledgePhase

        knowledge = KnowledgePhase()
        entries = [
            {"reasoning_approach": "test", "duration": 0.5},
            {"reasoning_approach": "test", "duration": 0.3},
        ]

        analytics = knowledge._build_analytics(entries)

        assert analytics.algorithm_used == "test"
        assert analytics.reasoning_time == 0.8


class TestMAPEKCoordinator:
    """Tests for MAPE-K Coordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_basic(self):
        """Test basic coordinator execution."""
        from src.core.mape_k.coordinator import MAPEKCoordinator
        from src.core.mape_k.meta_planning import MetaPlanner
        from src.core.mape_k.monitoring import MonitoringPhase
        from src.core.mape_k.analysis import AnalysisPhase
        from src.core.mape_k.planning import PlanningPhase
        from src.core.mape_k.execution import ExecutionPhase
        from src.core.mape_k.knowledge import KnowledgePhase

        coordinator = MAPEKCoordinator(
            meta_planner=MetaPlanner(),
            monitoring=MonitoringPhase(),
            analysis=AnalysisPhase(),
            planning=PlanningPhase(),
            execution=ExecutionPhase(),
            knowledge=KnowledgePhase(),
        )

        result = await coordinator.run_full_cycle({"type": "test"})

        assert "meta_plan" in result
        assert "metrics" in result
        assert "analysis" in result
        assert "plan" in result
        assert "execution_log" in result
        assert "knowledge" in result

    @pytest.mark.asyncio
    async def test_coordinator_stats(self):
        """Test coordinator statistics."""
        from src.core.mape_k.coordinator import MAPEKCoordinator
        from src.core.mape_k.meta_planning import MetaPlanner
        from src.core.mape_k.monitoring import MonitoringPhase
        from src.core.mape_k.analysis import AnalysisPhase
        from src.core.mape_k.planning import PlanningPhase
        from src.core.mape_k.execution import ExecutionPhase
        from src.core.mape_k.knowledge import KnowledgePhase

        coordinator = MAPEKCoordinator(
            meta_planner=MetaPlanner(),
            monitoring=MonitoringPhase(),
            analysis=AnalysisPhase(),
            planning=PlanningPhase(),
            execution=ExecutionPhase(),
            knowledge=KnowledgePhase(),
        )

        await coordinator.run_full_cycle()
        stats = coordinator.get_stats()

        assert "total" in stats
        assert stats["total"] == 1


class TestMAPEKModuleAPI:
    """Tests for MAPE-K module public API."""

    def test_module_imports(self):
        """Test that all public API exports are importable."""
        from src.core.mape_k import (
            ReasoningApproach,
            SolutionSpace,
            ReasoningPath,
            ReasoningMetrics,
            ReasoningAnalytics,
            ExecutionLogEntry,
            MAPEKCycleResult,
            MetaPlanner,
            MonitoringPhase,
            AnalysisPhase,
            PlanningPhase,
            ExecutionPhase,
            KnowledgePhase,
            MAPEKCoordinator,
        )

        assert ReasoningApproach.MAPE_K_ONLY.value == "mape_k_only"
        assert SolutionSpace is not None
        assert MetaPlanner is not None
        assert MAPEKCoordinator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
