"""Unit tests for MAPE-K Execution Phase."""
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.mape_k.execution import ExecutionPhase
from src.core.mape_k.models import ExecutionLogEntry


class TestExecutionPhaseInit:
    def test_init_no_args(self):
        ep = ExecutionPhase()
        assert ep.mape_k is None
        assert ep.self_reflection is None
        assert ep.think_aloud is None

    def test_init_with_dependencies(self):
        mock_loop = MagicMock()
        mock_reflect = MagicMock()
        mock_think = MagicMock()
        ep = ExecutionPhase(
            mape_k_loop=mock_loop,
            self_reflection=mock_reflect,
            think_aloud=mock_think,
        )
        assert ep.mape_k is mock_loop
        assert ep.self_reflection is mock_reflect
        assert ep.think_aloud is mock_think


class TestExecutionPhaseExecute:
    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        ep = ExecutionPhase()
        result = await ep.execute({"recovery_plan": {}})
        assert result["execution_result"]["status"] == "success"
        assert result["execution_result"]["steps_completed"] == 1  # default monitor step

    @pytest.mark.asyncio
    async def test_execute_with_steps(self):
        ep = ExecutionPhase()
        plan = {
            "recovery_plan": {
                "steps": [
                    {"action": "restart", "description": "Restart service"},
                    {"action": "verify", "description": "Verify health"},
                ]
            },
            "reasoning_optimization": {"approach_selection": "mape_k_only"},
        }
        result = await ep.execute(plan)
        assert result["execution_result"]["status"] == "success"
        assert result["execution_result"]["steps_completed"] == 2

    @pytest.mark.asyncio
    async def test_execute_with_think_aloud(self):
        mock_think = MagicMock()
        mock_think.get_thoughts.return_value = ["thought1"]
        ep = ExecutionPhase(think_aloud=mock_think)
        result = await ep.execute({"recovery_plan": {"steps": [{"action": "test"}]}})
        mock_think.log.assert_called()

    @pytest.mark.asyncio
    async def test_execute_with_self_reflection(self):
        mock_reflect = MagicMock()
        mock_reflect.reflect.return_value = {"assumptions": ["a1"]}
        ep = ExecutionPhase(self_reflection=mock_reflect)
        result = await ep.execute({"recovery_plan": {"steps": [{"action": "test"}]}})
        assert result["self_reflection"] == {"assumptions": ["a1"]}


class TestExecutionPhaseDeadEnd:
    @pytest.mark.asyncio
    async def test_handle_dead_end(self):
        ep = ExecutionPhase()
        # Monkey-patch _run_step to return "stuck"
        async def _stuck_step(step, opt):
            return ExecutionLogEntry(
                step=step, result={"status": "stuck"}, duration=0.1,
                reasoning_approach="test", meta_insights={},
            )
        ep._execute_step = _stuck_step
        result = await ep.execute({
            "recovery_plan": {"steps": [{"action": "fail"}]},
            "reasoning_optimization": {"approach_selection": "test"},
        })
        assert result["execution_result"]["status"] == "rollback"


class TestExecutionPhaseHelpers:
    def test_explain_approach(self):
        ep = ExecutionPhase()
        explanation = ep._explain_approach(
            {"action": "test"}, {"approach_selection": "mape_k_only"}
        )
        assert "mape_k_only" in explanation

    def test_get_alternatives(self):
        ep = ExecutionPhase()
        alts = ep._get_alternatives({"action": "test"})
        assert len(alts) > 0

    def test_calculate_probability(self):
        ep = ExecutionPhase()
        prob = ep._calculate_probability({"action": "test"})
        assert 0.0 <= prob <= 1.0

    def test_get_thoughts_no_think_aloud(self):
        ep = ExecutionPhase()
        assert ep._get_thoughts() == []
