"""Unit tests for MAPE-K Planning Phase."""
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.mape_k.planning import PlanningPhase
from src.core.mape_k.models import ReasoningApproach


class TestPlanningPhaseInit:
    def test_init_defaults(self):
        pp = PlanningPhase()
        assert pp.mape_k is None
        assert pp.reverse_planner is None
        assert pp.first_principles is None
        assert pp.think_aloud is None

    def test_init_with_deps(self):
        mock = MagicMock()
        pp = PlanningPhase(mape_k_loop=mock, think_aloud=mock)
        assert pp.mape_k is mock


class TestPlanningPhaseExecute:
    @pytest.mark.asyncio
    async def test_execute_no_mape_k(self):
        pp = PlanningPhase()
        result = await pp.execute({"system_analysis": {}})
        assert "recovery_plan" in result
        assert "reasoning_optimization" in result

    @pytest.mark.asyncio
    async def test_execute_with_think_aloud(self):
        mock_think = MagicMock()
        mock_think.get_thoughts.return_value = ["planning..."]
        pp = PlanningPhase(think_aloud=mock_think)
        result = await pp.execute({})
        assert result["think_aloud_log"] == ["planning..."]


class TestReasoningOptimization:
    def test_select_best_approach_anomaly(self):
        pp = PlanningPhase()
        analysis = {"reasoning_analysis": {"anomaly_detected": True}}
        approach = pp._select_best_approach(analysis)
        assert approach == ReasoningApproach.COMBINED_ALL.value

    def test_select_best_approach_normal(self):
        pp = PlanningPhase()
        analysis = {"reasoning_analysis": {}}
        approach = pp._select_best_approach(analysis)
        assert approach == ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value

    def test_optimize_time(self):
        pp = PlanningPhase()
        alloc = pp._optimize_time({})
        assert sum(alloc.values()) == pytest.approx(1.0)

    def test_define_checkpoints(self):
        pp = PlanningPhase()
        cps = pp._define_checkpoints()
        assert len(cps) == 3
        assert all("name" in cp and "metric" in cp for cp in cps)


class TestReversePlanning:
    def test_reverse_plan_no_planner(self):
        pp = PlanningPhase()
        assert pp._plan_reverse({"goal": "fix"}) is None

    def test_reverse_plan_no_goal(self):
        mock = MagicMock()
        pp = PlanningPhase(reverse_planner=mock)
        assert pp._plan_reverse({}) is None

    def test_reverse_plan_with_planner(self):
        mock = MagicMock()
        mock.plan.return_value = ["step3", "step2", "step1"]
        pp = PlanningPhase(reverse_planner=mock)
        result = pp._plan_reverse({"goal": "recover"})
        assert result == ["step3", "step2", "step1"]


class TestFirstPrinciplesPlanning:
    def test_no_first_principles(self):
        pp = PlanningPhase()
        assert pp._plan_first_principles({}) is None

    def test_with_first_principles(self):
        mock_fp = MagicMock()
        mock_decomp = MagicMock()
        mock_decomp.fundamentals = ["f1", "f2"]
        mock_fp.decompose.return_value = mock_decomp
        mock_fp.build_from_scratch.return_value = {"rebuilt": True}
        pp = PlanningPhase(first_principles=mock_fp)
        result = pp._plan_first_principles({"steps": []})
        assert result == {"rebuilt": True}


class TestPlanValidation:
    @pytest.mark.asyncio
    async def test_validate_plan_always_true(self):
        pp = PlanningPhase()
        assert await pp._validate_plan({}, {}) is True
