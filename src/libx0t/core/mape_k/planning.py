"""
Planning Phase for MAPE-K.

Phase 3: Plans solutions and optimizes reasoning process.
"""
import logging
from typing import Any, Dict, List, Optional

from .models import ReasoningApproach

logger = logging.getLogger(__name__)


class PlanningPhase:
    """
    Planning phase component.
    
    Plans solutions and optimizes reasoning process.
    Integrates Reverse Planning and First Principles.
    """

    def __init__(
        self,
        mape_k_loop=None,
        reverse_planner=None,
        first_principles=None,
        think_aloud=None,
    ):
        """
        Initialize Planning Phase.
        
        Args:
            mape_k_loop: MAPE-K loop for system planning
            reverse_planner: Reverse planning tool
            first_principles: First Principles decomposer
            think_aloud: Think-aloud logger
        """
        self.mape_k = mape_k_loop
        self.reverse_planner = reverse_planner
        self.first_principles = first_principles
        self.think_aloud = think_aloud

    async def execute(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute planning phase.
        
        Args:
            analysis: Results from analysis phase
        
        Returns:
            Dictionary with recovery_plan and reasoning_optimization
        """
        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log("Начинаю планирование решения...")

        # System planning (MAPE-K)
        recovery_plan = await self._plan_recovery(analysis)

        # Reverse planning
        reverse_plan = self._plan_reverse(recovery_plan)

        # First Principles planning
        first_principles_plan = self._plan_first_principles(recovery_plan)

        # Reasoning optimization
        reasoning_optimization = self._optimize_reasoning(analysis)

        # Validate plan through meta-analysis
        if not await self._validate_plan(recovery_plan, reasoning_optimization):
            logger.warning("⚠️ Plan failed meta-validation, replanning...")
            return await self.execute(analysis)

        return {
            "recovery_plan": recovery_plan,
            "reasoning_optimization": reasoning_optimization,
            "reverse_plan": reverse_plan,
            "first_principles_plan": first_principles_plan,
            "think_aloud_log": self._get_thoughts(),
        }

    async def _plan_recovery(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Plan recovery via MAPE-K."""
        if not self.mape_k:
            return {}

        try:
            system_metrics = analysis.get("system_analysis", {}).get("system_metrics", {})
            consciousness_metrics = self.mape_k._analyze(system_metrics)
            plan = self.mape_k._plan(consciousness_metrics)

            if self.think_aloud:
                self.think_aloud.log(
                    f"План создан: {len(plan.get('steps', []))} шагов"
                )

            return plan

        except Exception as e:
            logger.warning(f"⚠️ MAPE-K plan failed: {e}")
            if self.think_aloud:
                self.think_aloud.log(f"⚠️ Ошибка планирования: {e}")
            return {}

    def _plan_reverse(self, recovery_plan: Dict[str, Any]) -> Optional[List[str]]:
        """Plan using reverse planning."""
        if not self.reverse_planner or "goal" not in recovery_plan:
            return None

        try:
            plan = self.reverse_planner.plan(recovery_plan["goal"])
            if self.think_aloud:
                self.think_aloud.log(
                    f"Обратное планирование: {len(plan)} шагов от цели"
                )
            return plan
        except Exception as e:
            logger.warning(f"⚠️ Reverse planning failed: {e}")
            return None

    def _plan_first_principles(
        self, recovery_plan: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Plan using First Principles."""
        if not self.first_principles:
            return None

        try:
            decomposition = self.first_principles.decompose(recovery_plan)
            plan = self.first_principles.build_from_scratch(decomposition)

            if self.think_aloud:
                self.think_aloud.log(
                    f"First Principles: {len(decomposition.fundamentals)} элементов"
                )

            return plan.__dict__ if hasattr(plan, "__dict__") else plan
        except Exception as e:
            logger.warning(f"⚠️ First principles planning failed: {e}")
            return None

    def _optimize_reasoning(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize reasoning process."""
        return {
            "approach_selection": self._select_best_approach(analysis),
            "time_allocation": self._optimize_time(analysis),
            "checkpoints": self._define_checkpoints(),
        }

    def _select_best_approach(self, analysis: Dict[str, Any]) -> str:
        """Select best reasoning approach."""
        reasoning_analysis = analysis.get("reasoning_analysis", {})
        if reasoning_analysis.get("anomaly_detected"):
            return ReasoningApproach.COMBINED_ALL.value
        return ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value

    def _optimize_time(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Optimize time allocation."""
        return {
            "planning": 0.2,
            "execution": 0.6,
            "analysis": 0.2,
        }

    def _define_checkpoints(self) -> List[Dict[str, Any]]:
        """Define meta-checkpoints."""
        return [
            {"name": "approach_selection", "metric": "success_probability > 0.9"},
            {"name": "rag_search", "metric": "similarity > 0.7"},
            {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
        ]

    async def _validate_plan(
        self,
        recovery_plan: Dict[str, Any],
        reasoning_optimization: Dict[str, Any]
    ) -> bool:
        """Validate plan through meta-analysis."""
        # Simplified validation
        return True

    def _get_thoughts(self) -> list:
        """Get think-aloud thoughts."""
        if self.think_aloud:
            return self.think_aloud.get_thoughts()
        return []
