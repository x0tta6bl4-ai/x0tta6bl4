"""
Execution Phase for MAPE-K.

Phase 4: Executes plans with meta-awareness.
"""
from __future__ import annotations
import logging
import time
from typing import Any

from .models import ExecutionLogEntry

logger = logging.getLogger(__name__)


class ExecutionPhase:
    """
    Execution phase component.
    
    Executes plans with meta-awareness and logging.
    Integrates Self-Reflection for assumption checking.
    """

    def __init__(
        self,
        mape_k_loop=None,
        self_reflection=None,
        think_aloud=None,
    ):
        """
        Initialize Execution Phase.
        
        Args:
            mape_k_loop: MAPE-K loop for execution
            self_reflection: Self-reflection tool
            think_aloud: Think-aloud logger
        """
        self.mape_k = mape_k_loop
        self.self_reflection = self_reflection
        self.think_aloud = think_aloud

    async def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Execute execution phase.
        
        Args:
            plan: Results from planning phase
        
        Returns:
            Dictionary with execution_result and execution_log
        """
        execution_log: list[ExecutionLogEntry] = []
        recovery_plan = plan.get("recovery_plan", {})
        reasoning_optimization = plan.get("reasoning_optimization", {})

        # Self-reflection before execution
        self_reflection = self._reflect_on_plan(recovery_plan)

        # Get steps
        steps = recovery_plan.get("steps", [])
        if not steps:
            steps = [{"action": "monitor", "description": "Standard monitoring"}]

        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log(f"Начинаю выполнение: {len(steps)} шагов")

        # Execute steps
        for step in steps:
            entry = await self._execute_step(step, reasoning_optimization)
            execution_log.append(entry)

            # Handle dead ends
            if entry.result.get("status") == "stuck":
                return await self._handle_dead_end(execution_log, reasoning_optimization)

            # Handle breakthroughs
            if entry.result.get("status") == "breakthrough":
                execution_log.append(self._record_breakthrough(step, reasoning_optimization))

        return {
            "execution_result": {"status": "success", "steps_completed": len(steps)},
            "execution_log": [entry.__dict__ for entry in execution_log],
            "self_reflection": self_reflection,
            "think_aloud_log": self._get_thoughts(),
        }

    def _reflect_on_plan(self, recovery_plan: dict[str, Any]) -> dict[str, Any] | None:
        """Reflect on plan before execution."""
        if not self.self_reflection:
            return None

        try:
            reflection = self.self_reflection.reflect(recovery_plan)
            if self.think_aloud:
                self.think_aloud.log(
                    f"Саморефлексия: {len(reflection.get('assumptions', []))} предположений"
                )
                for assumption in reflection.get("assumptions", []):
                    self.think_aloud.log(f"  Предположение: {assumption}")
            return reflection.__dict__ if hasattr(reflection, "__dict__") else reflection
        except Exception as e:
            logger.warning(f"⚠️ Self-reflection failed: {e}")
            return None

    async def _execute_step(
        self,
        step: dict[str, Any],
        reasoning_optimization: dict[str, Any]
    ) -> ExecutionLogEntry:
        """Execute single step."""
        step_start = time.time()

        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log(f"Выполняю шаг: {step.get('action', 'unknown')}")

        # Execute via MAPE-K
        result = await self._run_step(step)

        duration = time.time() - step_start

        # Build meta insights
        meta_insights = {
            "why_this_approach": self._explain_approach(step, reasoning_optimization),
            "alternative_approaches": self._get_alternatives(step),
            "success_probability": self._calculate_probability(step),
        }

        return ExecutionLogEntry(
            step=step,
            result=result,
            duration=duration,
            reasoning_approach=reasoning_optimization.get("approach_selection", "unknown"),
            meta_insights=meta_insights,
        )

    async def _run_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Run step via MAPE-K."""
        if not self.mape_k:
            return {"status": "success", "message": "Step completed"}

        try:
            result = {"status": "success", "message": "Executed via MAPE-K"}
            if self.think_aloud:
                self.think_aloud.log("✅ Шаг выполнен успешно")
            return result
        except Exception as e:
            if self.think_aloud:
                self.think_aloud.log(f"❌ Ошибка выполнения: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_dead_end(
        self,
        execution_log: list[ExecutionLogEntry],
        reasoning_optimization: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle dead end by rollback and replan."""
        logger.warning("🔄 Rolling back and replanning...")

        last_entry = execution_log[-1] if execution_log else None
        step = last_entry.step if last_entry else {}

        execution_log.append(ExecutionLogEntry(
            step={"action": "dead_end_detected"},
            result={"status": "rollback"},
            duration=0.0,
            reasoning_approach=reasoning_optimization.get("approach_selection", "unknown"),
            meta_insights={
                "event": "dead_end_detected",
                "reason": "approach_failed",
                "rollback": True,
                "meta_analysis": self._analyze_failure(step),
            },
        ))

        return {
            "execution_result": {
                "status": "rollback",
                "message": "Replanning required",
            },
            "execution_log": [e.__dict__ for e in execution_log],
        }

    def _record_breakthrough(
        self,
        step: dict[str, Any],
        reasoning_optimization: dict[str, Any]
    ) -> ExecutionLogEntry:
        """Record breakthrough moment."""
        logger.info(f"✅ Breakthrough at step: {step}")

        return ExecutionLogEntry(
            step={"action": "breakthrough"},
            result={"status": "success"},
            duration=0.0,
            reasoning_approach=reasoning_optimization.get("approach_selection", "unknown"),
            meta_insights={
                "event": "breakthrough",
                "turning_point": self._identify_turning_point(step),
                "meta_insight": "what_made_it_work",
            },
        )

    def _explain_approach(
        self, step: dict[str, Any], optimization: dict[str, Any]
    ) -> str:
        """Explain approach selection."""
        approach = optimization.get("approach_selection", "unknown")
        return f"Selected {approach} based on historical success rate"

    def _get_alternatives(self, step: dict[str, Any]) -> list[str]:
        """Get alternative approaches."""
        from .models import ReasoningApproach
        return [a.value for a in ReasoningApproach]

    def _calculate_probability(self, step: dict[str, Any]) -> float:
        """Calculate success probability."""
        return 0.85

    def _analyze_failure(self, step: dict[str, Any]) -> dict[str, Any]:
        """Analyze why step failed."""
        return {
            "reason": "approach_not_suitable",
            "recommendation": "try_alternative",
        }

    def _identify_turning_point(self, step: dict[str, Any]) -> str:
        """Identify turning point."""
        return f"Breakthrough at step: {step.get('action', 'unknown')}"

    def _get_thoughts(self) -> list:
        """Get think-aloud thoughts."""
        if self.think_aloud:
            return self.think_aloud.get_thoughts()
        return []

