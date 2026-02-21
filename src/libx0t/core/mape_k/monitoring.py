"""
Monitoring Phase for MAPE-K.

Phase 1: Monitors system metrics and reasoning process.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from .models import ReasoningMetrics

logger = logging.getLogger(__name__)


class MonitoringPhase:
    """
    Monitoring phase component.
    
    Monitors both system metrics and reasoning process.
    Integrates Mind Maps and Logic Gap detection.
    """

    def __init__(
        self,
        mape_k_loop=None,
        mind_maps=None,
        think_aloud=None,
        reasoning_history: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize Monitoring Phase.
        
        Args:
            mape_k_loop: MAPE-K loop for system monitoring
            mind_maps: Mind Map generator
            think_aloud: Think-aloud logger
            reasoning_history: Reference to reasoning history
        """
        self.mape_k = mape_k_loop
        self.mind_maps = mind_maps
        self.think_aloud = think_aloud
        self._reasoning_history = reasoning_history or []

    async def execute(self) -> Dict[str, Any]:
        """
        Execute monitoring phase.
        
        Returns:
            Dictionary with system_metrics and reasoning_metrics
        """
        reasoning_start = time.time()

        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log("Начинаю мониторинг системы...")

        # System monitoring (MAPE-K)
        system_metrics = await self._monitor_system()

        # Reasoning monitoring
        reasoning_metrics = self._monitor_reasoning(reasoning_start)

        # Detect reasoning anomalies
        if reasoning_metrics.dead_ends_encountered > 3:
            logger.warning("⚠️ Too many dead ends detected")

        reasoning_metrics.end_time = time.time()
        reasoning_metrics.reasoning_time = (
            reasoning_metrics.end_time - reasoning_metrics.start_time
        )

        # Generate mind map
        mind_map = self._create_mind_map(system_metrics, reasoning_metrics)

        # Detect logic gaps
        logic_gaps = self._detect_logic_gaps()

        return {
            "system_metrics": system_metrics,
            "reasoning_metrics": reasoning_metrics,
            "mind_map": mind_map,
            "logic_gaps": logic_gaps,
            "think_aloud_log": self._get_thoughts(),
        }

    async def _monitor_system(self) -> Dict[str, Any]:
        """Monitor system metrics via MAPE-K."""
        if not self.mape_k:
            return {}

        try:
            metrics = await self.mape_k._monitor()
            if self.think_aloud:
                self.think_aloud.log(
                    f"Метрики собраны: CPU={metrics.get('cpu_percent', 'N/A')}%"
                )
            return metrics
        except Exception as e:
            logger.warning(f"⚠️ MAPE-K monitor failed: {e}")
            if self.think_aloud:
                self.think_aloud.log(f"⚠️ Ошибка мониторинга: {e}")
            return {}

    def _monitor_reasoning(self, start_time: float) -> ReasoningMetrics:
        """Monitor reasoning process."""
        return ReasoningMetrics(
            start_time=start_time,
            approaches_tried=len(self._reasoning_history),
            dead_ends_encountered=sum(
                1 for h in self._reasoning_history if h.get("dead_end", False)
            ),
            confidence_level=self._assess_confidence(),
            knowledge_base_hits=self._count_kb_hits(),
            cache_hit_rate=self._calculate_cache_hit_rate(),
        )

    def _assess_confidence(self) -> float:
        """Assess confidence level from history."""
        if not self._reasoning_history:
            return 0.5

        recent = self._reasoning_history[-10:]
        success_rate = sum(1 for h in recent if h.get("success", False)) / len(recent)
        return success_rate

    def _count_kb_hits(self) -> int:
        """Count knowledge base hits."""
        return sum(1 for h in self._reasoning_history if h.get("kb_hit", False))

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if not self._reasoning_history:
            return 0.0
        return self._count_kb_hits() / len(self._reasoning_history)

    def _create_mind_map(
        self,
        system_metrics: Dict[str, Any],
        reasoning_metrics: ReasoningMetrics
    ) -> Optional[Dict[str, Any]]:
        """Create mind map for visualization."""
        if not self.mind_maps:
            return None

        try:
            mind_map = self.mind_maps.create({
                "center": "System Monitoring",
                "system_metrics": system_metrics,
                "reasoning_metrics": reasoning_metrics.__dict__,
            })
            if self.think_aloud:
                self.think_aloud.log("Интеллект-карта создана")
            return mind_map
        except Exception as e:
            logger.warning(f"⚠️ Mind map creation failed: {e}")
            return None

    def _detect_logic_gaps(self) -> List[str]:
        """Detect logic gaps in reasoning."""
        if not self.think_aloud:
            return []

        try:
            gaps = self.think_aloud.detect_logic_gaps()
            if gaps:
                logger.warning(f"⚠️ Обнаружены пробелы в логике: {gaps}")
            return gaps
        except Exception as e:
            logger.warning(f"⚠️ Logic gap detection failed: {e}")
            return []

    def _get_thoughts(self) -> List[str]:
        """Get think-aloud thoughts."""
        if self.think_aloud:
            return self.think_aloud.get_thoughts()
        return []
