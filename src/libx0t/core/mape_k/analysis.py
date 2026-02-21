"""
Analysis Phase for MAPE-K.

Phase 2: Analyzes problems and reasoning process.
"""
import logging
from typing import Any, Dict, Optional

from .models import ReasoningMetrics

logger = logging.getLogger(__name__)


class AnalysisPhase:
    """
    Analysis phase component.
    
    Analyzes both problems and reasoning process.
    Integrates Lateral Thinking for alternative approaches.
    """

    def __init__(
        self,
        mape_k_loop=None,
        knowledge_base=None,
        lateral_thinking=None,
        think_aloud=None,
        node_id: str = "default",
    ):
        """
        Initialize Analysis Phase.
        
        Args:
            mape_k_loop: MAPE-K loop for system analysis
            knowledge_base: Knowledge storage
            lateral_thinking: Lateral Thinking generator
            think_aloud: Think-aloud logger
            node_id: Node identifier
        """
        self.mape_k = mape_k_loop
        self.knowledge_base = knowledge_base
        self.lateral_thinking = lateral_thinking
        self.think_aloud = think_aloud
        self.node_id = node_id

    async def execute(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute analysis phase.
        
        Args:
            metrics: Metrics from monitoring phase
        
        Returns:
            Dictionary with system_analysis and reasoning_analysis
        """
        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log("Начинаю анализ метрик...")

        # System analysis (MAPE-K)
        system_analysis = await self._analyze_system(metrics.get("system_metrics", {}))

        # Lateral thinking for alternatives
        lateral_approaches = self._generate_lateral_approaches(
            metrics.get("system_metrics", {})
        )

        # Reasoning analysis
        reasoning_metrics = metrics.get("reasoning_metrics", ReasoningMetrics())
        reasoning_analysis = self._analyze_reasoning(reasoning_metrics)

        # Store reasoning failure if detected
        if reasoning_analysis.get("anomaly_detected"):
            await self._store_reasoning_failure(reasoning_analysis)

        return {
            "system_analysis": system_analysis,
            "reasoning_analysis": reasoning_analysis,
            "lateral_approaches": lateral_approaches,
            "think_aloud_log": self._get_thoughts(),
        }

    async def _analyze_system(
        self, system_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze system metrics via MAPE-K."""
        if not self.mape_k:
            return {}

        try:
            consciousness_metrics = self.mape_k._analyze(system_metrics)
            
            analysis = {
                "consciousness_state": (
                    consciousness_metrics.state.value
                    if hasattr(consciousness_metrics, "state")
                    else "UNKNOWN"
                ),
                "phi_ratio": (
                    consciousness_metrics.phi_ratio
                    if hasattr(consciousness_metrics, "phi_ratio")
                    else 0.0
                ),
                "anomaly_detected": (
                    consciousness_metrics.phi_ratio < 0.5
                    if hasattr(consciousness_metrics, "phi_ratio")
                    else False
                ),
            }

            if self.think_aloud:
                self.think_aloud.log(
                    f"Состояние сознания: {analysis['consciousness_state']}"
                )

            return analysis

        except Exception as e:
            logger.warning(f"⚠️ MAPE-K analyze failed: {e}")
            if self.think_aloud:
                self.think_aloud.log(f"⚠️ Ошибка анализа: {e}")
            return {}

    def _generate_lateral_approaches(
        self, system_metrics: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate lateral thinking approaches."""
        if not self.lateral_thinking:
            return None

        try:
            approaches = self.lateral_thinking.generate(system_metrics)
            if self.think_aloud:
                self.think_aloud.log(
                    f"Латеральное мышление: {len(approaches.alternative_approaches)} альтернатив"
                )
            return approaches.__dict__ if hasattr(approaches, "__dict__") else approaches
        except Exception as e:
            logger.warning(f"⚠️ Lateral thinking failed: {e}")
            return None

    def _analyze_reasoning(self, metrics: ReasoningMetrics) -> Dict[str, Any]:
        """Analyze reasoning process."""
        analysis = {
            "efficiency": self._assess_efficiency(metrics),
            "anomaly_detected": metrics.dead_ends_encountered > 3,
            "insights": None,
        }

        if analysis["anomaly_detected"]:
            analysis["insights"] = {
                "issue": "reasoning_process_inefficient",
                "root_cause": "too_many_approaches_tried",
                "recommendation": "focus_on_single_approach",
            }

        return analysis

    def _assess_efficiency(self, metrics: ReasoningMetrics) -> float:
        """Assess reasoning efficiency."""
        if metrics.reasoning_time == 0:
            return 1.0

        efficiency = 1.0 - (
            metrics.dead_ends_encountered / max(metrics.approaches_tried, 1)
        )
        return max(0.0, min(1.0, efficiency))

    async def _store_reasoning_failure(
        self, reasoning_analysis: Dict[str, Any]
    ) -> None:
        """Store reasoning failure in knowledge base."""
        if not self.knowledge_base:
            return

        try:
            import time
            await self.knowledge_base.store_incident(
                {
                    "type": "reasoning_failure",
                    "meta_insight": reasoning_analysis.get("insights"),
                    "timestamp": time.time(),
                    "node_id": self.node_id,
                },
                self.node_id,
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to store reasoning failure: {e}")

    def _get_thoughts(self) -> list:
        """Get think-aloud thoughts."""
        if self.think_aloud:
            return self.think_aloud.get_thoughts()
        return []
