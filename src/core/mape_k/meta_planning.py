"""
Meta-Planning Phase for MAPE-K.

Phase 0: Creates solution space map and reasoning path.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .models import ReasoningApproach, ReasoningPath, SolutionSpace

logger = logging.getLogger(__name__)


class MetaPlanner:
    """
    Meta-Planning phase component.
    
    Creates map of solution space and plans reasoning path.
    Integrates Six Thinking Hats, First Principles, and Reverse Planning.
    """

    def __init__(
        self,
        knowledge_base=None,
        graphsage=None,
        six_hats=None,
        first_principles=None,
        reverse_planner=None,
        think_aloud=None,
    ):
        """
        Initialize Meta-Planner.
        
        Args:
            knowledge_base: Knowledge storage for failure history
            graphsage: GraphSAGE for success prediction
            six_hats: Six Thinking Hats analyzer
            first_principles: First Principles decomposer
            reverse_planner: Reverse planning tool
            think_aloud: Think-aloud logger
        """
        self.knowledge_base = knowledge_base
        self.graphsage = graphsage
        self.six_hats = six_hats
        self.first_principles = first_principles
        self.reverse_planner = reverse_planner
        self.think_aloud = think_aloud

    async def execute(
        self, task: Dict[str, Any]
    ) -> Tuple[SolutionSpace, ReasoningPath]:
        """
        Execute meta-planning phase.
        
        Args:
            task: Task description
        
        Returns:
            Tuple of (SolutionSpace, ReasoningPath)
        """
        logger.info("🧠 Meta-Planning: Mapping solution space...")

        # Think-aloud logging
        if self.think_aloud:
            self.think_aloud.log("Начинаю мета-планирование", {"task": task})

        # Six Thinking Hats analysis
        hats_analysis = self._run_six_hats(task)

        # First Principles decomposition
        first_principles = self._run_first_principles(task)

        # Build approaches
        approaches = self._build_approaches(hats_analysis, first_principles)

        # Get failure history
        failure_history = await self._get_failure_history(task)

        # Calculate success probabilities
        success_probabilities = await self._calculate_probabilities(approaches, task)

        # Select best approach
        best_approach = self._select_best_approach(approaches, success_probabilities)

        # Build solution space
        solution_space = SolutionSpace(
            approaches=approaches,
            failure_history=failure_history,
            success_probabilities=success_probabilities,
            selected_approach=best_approach["name"],
            reasoning=self._build_reasoning(best_approach, success_probabilities),
        )

        # Build reasoning path
        reasoning_path = await self._build_reasoning_path(
            task, best_approach, failure_history
        )

        # Store enhanced analysis in solution space
        solution_space.hats_analysis = hats_analysis
        solution_space.first_principles = first_principles
        solution_space.reverse_plan = reasoning_path.checkpoints

        logger.info(
            f"✅ Meta-Planning complete: Selected {best_approach['name']} "
            f"(probability: {success_probabilities.get(best_approach['name'], best_approach['probability']):.2f})"
        )

        return solution_space, reasoning_path

    def _run_six_hats(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run Six Thinking Hats analysis."""
        if not self.six_hats:
            return None

        try:
            analysis = self.six_hats.analyze(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"Six Hats анализ: {len(analysis.white.get('facts', []))} фактов найдено"
                )
            return analysis.__dict__ if hasattr(analysis, "__dict__") else analysis
        except Exception as e:
            logger.warning(f"⚠️ Six Hats analysis failed: {e}")
            return None

    def _run_first_principles(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run First Principles decomposition."""
        if not self.first_principles:
            return None

        try:
            decomposition = self.first_principles.decompose(task)
            if self.think_aloud:
                self.think_aloud.log(
                    f"First Principles: {len(decomposition.fundamentals)} фундаментальных элементов"
                )
            return decomposition.__dict__ if hasattr(decomposition, "__dict__") else decomposition
        except Exception as e:
            logger.warning(f"⚠️ First Principles failed: {e}")
            return None

    def _build_approaches(
        self,
        hats_analysis: Optional[Dict[str, Any]],
        first_principles: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build list of reasoning approaches."""
        approaches = [
            {
                "name": ReasoningApproach.MAPE_K_ONLY.value,
                "probability": 0.85,
                "description": "Стандартный MAPE-K цикл",
            },
            {
                "name": ReasoningApproach.RAG_SEARCH.value,
                "probability": 0.78,
                "description": "Поиск похожих случаев в Knowledge Base",
            },
            {
                "name": ReasoningApproach.GRAPHSAGE_PREDICTION.value,
                "probability": 0.92,
                "description": "Предсказание успеха через GraphSAGE",
            },
            {
                "name": ReasoningApproach.CAUSAL_ANALYSIS.value,
                "probability": 0.88,
                "description": "Анализ корневых причин",
            },
            {
                "name": ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value,
                "probability": 0.94,
                "description": "Комбинация RAG + GraphSAGE",
            },
            {
                "name": ReasoningApproach.COMBINED_ALL.value,
                "probability": 0.96,
                "description": "Комбинация всех подходов",
            },
        ]

        # Add Six Hats creative approach
        if hats_analysis and hats_analysis.get("green", {}).get("creative_ideas"):
            approaches.append({
                "name": "six_hats_creative",
                "probability": 0.90,
                "description": f"Креативные идеи: {', '.join(hats_analysis['green']['creative_ideas'][:2])}",
            })

        # Add First Principles approach
        if first_principles and first_principles.get("fundamentals"):
            approaches.append({
                "name": "first_principles",
                "probability": 0.88,
                "description": f"First Principles: {len(first_principles['fundamentals'])} элементов",
            })

        return approaches

    async def _get_failure_history(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get failure history from knowledge base."""
        if not self.knowledge_base:
            return []

        try:
            similar_failures = await self.knowledge_base.search_incidents(
                query=f"failed reasoning approach {task.get('type', 'unknown')}",
                k=5,
                threshold=0.6,
            )
            return [
                {
                    "approach": f.get("reasoning_analytics", {}).get("algorithm_used"),
                    "reason": f.get("meta_insight", {}).get("why_it_failed"),
                    "timestamp": f.get("timestamp"),
                }
                for f in similar_failures
            ]
        except Exception as e:
            logger.warning(f"⚠️ Failed to search failure history: {e}")
            return []

    async def _calculate_probabilities(
        self,
        approaches: List[Dict[str, Any]],
        task: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate success probabilities for each approach."""
        probabilities = {}

        if self.graphsage:
            try:
                features = self._extract_features(task)
                prediction = self.graphsage.predict(features)
                if prediction:
                    for approach in approaches:
                        probabilities[approach["name"]] = prediction.confidence
                    return probabilities
            except Exception as e:
                logger.warning(f"⚠️ GraphSAGE prediction failed: {e}")

        # Fallback to base probabilities
        for approach in approaches:
            probabilities[approach["name"]] = approach["probability"]

        return probabilities

    def _select_best_approach(
        self,
        approaches: List[Dict[str, Any]],
        probabilities: Dict[str, float]
    ) -> Dict[str, Any]:
        """Select best approach based on probabilities."""
        return max(
            approaches,
            key=lambda x: probabilities.get(x["name"], x["probability"]),
        )

    def _build_reasoning(
        self,
        approach: Dict[str, Any],
        probabilities: Dict[str, float]
    ) -> str:
        """Build reasoning string for approach selection."""
        prob = probabilities.get(approach["name"], approach["probability"])
        return f"Высокая вероятность успеха ({prob:.2f}) + исторические данные"

    async def _build_reasoning_path(
        self,
        task: Dict[str, Any],
        best_approach: Dict[str, Any],
        failure_history: List[Dict[str, Any]]
    ) -> ReasoningPath:
        """Build reasoning path with checkpoints."""
        # Reverse planning
        reverse_plan = None
        if self.reverse_planner and "goal" in task:
            try:
                reverse_plan = self.reverse_planner.plan(task["goal"])
                if self.think_aloud:
                    self.think_aloud.log(f"Обратное планирование: {len(reverse_plan)} шагов")
            except Exception as e:
                logger.warning(f"⚠️ Reverse planning failed: {e}")

        return ReasoningPath(
            first_step=best_approach["name"],
            dead_ends_to_avoid=[
                f["approach"] for f in failure_history if f.get("approach")
            ],
            checkpoints=[
                {"name": "approach_selection", "metric": "success_probability > 0.9"},
                {"name": "rag_search", "metric": "similarity > 0.7"},
                {"name": "graphsage_prediction", "metric": "confidence > 0.9"},
                {"name": "six_hats_analysis", "metric": "all_hats_analyzed"},
                {"name": "first_principles", "metric": "fundamentals_extracted"},
            ],
            estimated_time=self._estimate_time(task, best_approach),
        )

    def _extract_features(self, task: Dict[str, Any]) -> Dict[str, float]:
        """Extract features for GraphSAGE prediction."""
        return {
            "task_complexity": 0.5,
            "similarity_to_history": 0.7,
            "available_approaches": 6.0,
        }

    def _estimate_time(
        self, task: Dict[str, Any], approach: Dict[str, Any]
    ) -> float:
        """Estimate reasoning time."""
        base_time = 1.0
        complexity = task.get("complexity", 0.5)
        return base_time * (1 + complexity)
