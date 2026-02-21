"""
Knowledge Phase for MAPE-K.

Phase 5: Accumulates knowledge and generates meta-insights.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from .models import ReasoningAnalytics

logger = logging.getLogger(__name__)


class KnowledgePhase:
    """
    Knowledge phase component.
    
    Accumulates knowledge about solutions and reasoning process.
    Integrates Three Questions reflection method.
    """

    def __init__(
        self,
        knowledge_base=None,
        three_questions=None,
        think_aloud=None,
        node_id: str = "default",
    ):
        """
        Initialize Knowledge Phase.
        
        Args:
            knowledge_base: Knowledge storage
            three_questions: Three Questions reflection tool
            think_aloud: Think-aloud logger
            node_id: Node identifier
        """
        self.knowledge_base = knowledge_base
        self.three_questions = three_questions
        self.think_aloud = think_aloud
        self.node_id = node_id

    async def execute(
        self,
        execution_log: Dict[str, Any],
        reasoning_history: List[Dict[str, Any]],
        stats: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Execute knowledge phase.
        
        Args:
            execution_log: Results from execution phase
            reasoning_history: Reference to reasoning history
            stats: Reference to cycle statistics
        
        Returns:
            Dictionary with incident_record, reasoning_analytics and meta_insight
        """
        # Build incident record
        incident_record = self._build_incident_record(execution_log)

        # Build reasoning analytics
        execution_entries = execution_log.get("execution_log", [])
        reasoning_analytics = self._build_analytics(execution_entries)

        # Generate meta-insight
        meta_insight = self._generate_meta_insight(reasoning_analytics, execution_entries)
        reasoning_analytics.meta_insight = meta_insight

        # Three Questions reflection
        three_questions = self._run_three_questions(execution_log)

        # Store in knowledge base
        await self._store_incident(incident_record, reasoning_analytics, meta_insight)

        # Update history and stats
        self._update_history(reasoning_history, reasoning_analytics, meta_insight)
        self._update_stats(stats, reasoning_analytics.success)

        return {
            "incident_record": incident_record,
            "reasoning_analytics": reasoning_analytics.__dict__,
            "meta_insight": meta_insight,
            "three_questions": three_questions,
            "think_aloud_log": self._get_thoughts(),
        }

    def _build_incident_record(self, execution_log: Dict[str, Any]) -> Dict[str, Any]:
        """Build incident record."""
        return {
            "timestamp": time.time(),
            "node_id": self.node_id,
            "execution_result": execution_log.get("execution_result", {}),
            "steps": execution_log.get("execution_log", []),
        }

    def _build_analytics(self, execution_entries: List[Dict[str, Any]]) -> ReasoningAnalytics:
        """Build reasoning analytics."""
        return ReasoningAnalytics(
            algorithm_used=(
                execution_entries[0].get("reasoning_approach", "unknown")
                if execution_entries else "unknown"
            ),
            reasoning_time=sum(e.get("duration", 0.0) for e in execution_entries),
            approaches_tried=len(
                set(e.get("reasoning_approach", "unknown") for e in execution_entries)
            ),
            dead_ends=sum(
                1 for e in execution_entries
                if e.get("meta_insights", {}).get("event") == "dead_end_detected"
            ),
            breakthrough_moment=self._extract_breakthrough(execution_entries),
            success=self._check_success(execution_entries),
        )

    def _check_success(self, execution_entries: List[Dict[str, Any]]) -> bool:
        """Check if execution was successful."""
        # Simplified check
        return len(execution_entries) > 0

    def _extract_breakthrough(self, execution_entries: List[Dict[str, Any]]) -> Optional[str]:
        """Extract breakthrough moment."""
        for entry in execution_entries:
            if entry.get("meta_insights", {}).get("event") == "breakthrough":
                return entry.get("meta_insights", {}).get("turning_point")
        return None

    def _generate_meta_insight(
        self,
        analytics: ReasoningAnalytics,
        execution_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate meta-insight based on success/failure."""
        if analytics.success:
            return {
                "effective_algorithm": analytics.algorithm_used,
                "why_it_worked": self._analyze_why_worked(analytics),
                "key_factors": self._extract_success_factors(execution_entries),
            }
        else:
            return {
                "failed_algorithm": analytics.algorithm_used,
                "why_it_failed": self._analyze_why_failed(analytics),
                "what_to_do_differently": self._suggest_alternative(analytics),
            }

    def _analyze_why_worked(self, analytics: ReasoningAnalytics) -> str:
        """Analyze why algorithm worked."""
        return f"Algorithm {analytics.algorithm_used} worked due to high confidence and low dead ends"

    def _extract_success_factors(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Extract key success factors."""
        return ["high_confidence", "low_dead_ends", "efficient_reasoning"]

    def _analyze_why_failed(self, analytics: ReasoningAnalytics) -> str:
        """Analyze why algorithm failed."""
        return f"Algorithm {analytics.algorithm_used} failed due to too many dead ends ({analytics.dead_ends})"

    def _suggest_alternative(self, analytics: ReasoningAnalytics) -> str:
        """Suggest alternative approach."""
        return "Try combined approach with RAG + GraphSAGE for better results"

    def _run_three_questions(self, execution_log: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run Three Questions reflection."""
        if not self.three_questions:
            return None

        try:
            reflection = self.three_questions.reflect(execution_log)
            if self.think_aloud:
                self.think_aloud.log("Метод трёх вопросов:")
                self.think_aloud.log(
                    f"  Что удачно: {len(reflection.what_worked)} пунктов"
                )
                self.think_aloud.log(
                    f"  Что улучшить: {len(reflection.what_improve)} пунктов"
                )
                self.think_aloud.log(
                    f"  Что выучить: {len(reflection.what_learn)} уроков"
                )
            return reflection.__dict__ if hasattr(reflection, "__dict__") else reflection
        except Exception as e:
            logger.warning(f"⚠️ Three questions reflection failed: {e}")
            return None

    async def _store_incident(
        self,
        incident_record: Dict[str, Any],
        analytics: ReasoningAnalytics,
        meta_insight: Dict[str, Any]
    ) -> None:
        """Store incident in knowledge base."""
        if not self.knowledge_base:
            return

        try:
            incident_id = await self.knowledge_base.store_incident(
                {
                    "incident": incident_record,
                    "reasoning_analytics": analytics.__dict__,
                    "meta_insight": meta_insight,
                },
                self.node_id,
            )
            logger.info(f"✅ Stored incident with reasoning analytics: {incident_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to store in knowledge base: {e}")

    def _update_history(
        self,
        reasoning_history: List[Dict[str, Any]],
        analytics: ReasoningAnalytics,
        meta_insight: Dict[str, Any]
    ) -> None:
        """Update reasoning history."""
        reasoning_history.append({
            "timestamp": time.time(),
            "reasoning_analytics": analytics.__dict__,
            "meta_insight": meta_insight,
            "success": analytics.success,
        })

    def _update_stats(self, stats: Dict[str, int], success: bool) -> None:
        """Update cycle statistics."""
        stats["total"] = stats.get("total", 0) + 1
        if success:
            stats["successful"] = stats.get("successful", 0) + 1
        else:
            stats["failed"] = stats.get("failed", 0) + 1

    def _get_thoughts(self) -> list:
        """Get think-aloud thoughts."""
        if self.think_aloud:
            return self.think_aloud.get_thoughts()
        return []
