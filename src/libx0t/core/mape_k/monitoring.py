"""
Monitoring Phase for MAPE-K.

Phase 1: Monitors system metrics and reasoning process.
"""
import logging
import hashlib
import time
from typing import Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

from .models import ReasoningMetrics

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _score_band(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.5:
        return "medium"
    if value >= 0.3:
        return "low"
    return "very_low"


def _metrics_summary(metrics: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(str(key) for key in (metrics or {}).keys())
    return {
        "key_count": len(keys),
        "keys_hash": _safe_hash("|".join(keys)),
        "has_cpu": "cpu_percent" in metrics,
        "has_memory": "memory_percent" in metrics,
        "has_node_id": "node_id" in metrics,
    }


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-mape-k-monitoring-phase:{_safe_hash(id(self))}",
            role="monitoring",
            capabilities=("mape_k", "causal_analysis"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "libx0t_mape_k_monitoring_phase_init",
                "goal": "Initialize MAPE-K monitoring phase",
                "signals": {
                    "mape_k_available": mape_k_loop is not None,
                    "mind_maps_available": mind_maps is not None,
                    "think_aloud_available": think_aloud is not None,
                    "reasoning_history_count": len(self._reasoning_history),
                },
                "safety_boundary": (
                    "Do not expose raw system metrics, node ids, paths, or reasoning "
                    "history entries in thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_system_metrics": True,
                    "redact_node_identifiers": True,
                    "redact_paths": True,
                    "preserve_monitoring_contract": True,
                },
                "safety_boundary": (
                    "Use only metric key summaries, counts, confidence bands, and "
                    "boolean flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
        self._record_thinking(
            "libx0t_mape_k_monitoring_executed",
            "Summarize MAPE-K monitoring phase outputs",
            {
                "system_metrics": _metrics_summary(system_metrics),
                "approaches_tried_bucket": _safe_count_bucket(
                    reasoning_metrics.approaches_tried
                ),
                "dead_ends_bucket": _safe_count_bucket(
                    reasoning_metrics.dead_ends_encountered
                ),
                "confidence_band": _score_band(reasoning_metrics.confidence_level),
                "cache_hit_band": _score_band(reasoning_metrics.cache_hit_rate),
                "knowledge_base_hits_bucket": _safe_count_bucket(
                    reasoning_metrics.knowledge_base_hits
                ),
                "mind_map_created": mind_map is not None,
                "logic_gap_count": len(logic_gaps),
                "think_aloud_count": len(self._get_thoughts()),
            },
        )

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
            self._record_thinking(
                "libx0t_mape_k_monitoring_system_skipped",
                "Skip system monitoring because MAPE-K loop is unavailable",
                {"mape_k_available": False},
            )
            return {}

        try:
            metrics = await self.mape_k._monitor()
            if self.think_aloud:
                self.think_aloud.log(
                    f"Метрики собраны: CPU={metrics.get('cpu_percent', 'N/A')}%"
                )
            self._record_thinking(
                "libx0t_mape_k_monitoring_system_collected",
                "Collect system metrics from MAPE-K monitor",
                {"system_metrics": _metrics_summary(metrics)},
            )
            return metrics
        except Exception as e:
            logger.warning(f"⚠️ MAPE-K monitor failed: {e}")
            if self.think_aloud:
                self.think_aloud.log(f"⚠️ Ошибка мониторинга: {e}")
            self._record_thinking(
                "libx0t_mape_k_monitoring_system_failed",
                "Handle MAPE-K monitor failure",
                {"error_type": type(e).__name__},
            )
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
