"""
MAPE-K Cycle Coordinator.

Coordinates all MAPE-K phases into a complete cycle.
"""
import logging
from typing import Any, Dict, Optional

from .models import MAPEKCycleResult, SolutionSpace, ReasoningPath
from .meta_planning import MetaPlanner
from .monitoring import MonitoringPhase
from .analysis import AnalysisPhase
from .planning import PlanningPhase
from .execution import ExecutionPhase
from .knowledge import KnowledgePhase

logger = logging.getLogger(__name__)


class MAPEKCoordinator:
    """
    MAPE-K Cycle Coordinator.
    
    Coordinates all phases into a complete MAPE-K cycle:
    - Phase 0: Meta-Planning
    - Phase 1: Monitoring
    - Phase 2: Analysis
    - Phase 3: Planning
    - Phase 4: Execution
    - Phase 5: Knowledge
    """

    def __init__(
        self,
        meta_planner: MetaPlanner,
        monitoring: MonitoringPhase,
        analysis: AnalysisPhase,
        planning: PlanningPhase,
        execution: ExecutionPhase,
        knowledge: KnowledgePhase,
        node_id: str = "default",
    ):
        """
        Initialize MAPE-K Coordinator.
        
        Args:
            meta_planner: Meta-planning phase component
            monitoring: Monitoring phase component
            analysis: Analysis phase component
            planning: Planning phase component
            execution: Execution phase component
            knowledge: Knowledge phase component
            node_id: Node identifier
        """
        self.meta_planner = meta_planner
        self.monitoring = monitoring
        self.analysis = analysis
        self.planning = planning
        self.execution = execution
        self.knowledge = knowledge
        self.node_id = node_id

        # History and statistics
        self.reasoning_history: list = []
        self.execution_logs: list = []
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
        }

    async def run_full_cycle(
        self, task: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run complete MAPE-K cycle.
        
        Args:
            task: Task description (optional)
        
        Returns:
            Complete cycle result
        """
        if task is None:
            task = {"type": "standard_cycle", "description": "Standard MAPE-K cycle"}

        logger.info("=" * 60)
        logger.info("🧠 Starting Meta-Cognitive MAPE-K Cycle")
        logger.info("=" * 60)

        try:
            # Phase 0: Meta-Planning
            solution_space, reasoning_path = await self.meta_planner.execute(task)

            # Phase 1: Monitoring
            metrics = await self.monitoring.execute()

            # Phase 2: Analysis
            analysis_result = await self.analysis.execute(metrics)

            # Phase 3: Planning
            plan = await self.planning.execute(analysis_result)

            # Phase 4: Execution
            execution_log = await self.execution.execute(plan)

            # Phase 5: Knowledge
            knowledge = await self.knowledge.execute(
                execution_log, self.reasoning_history, self.stats
            )

            logger.info("=" * 60)
            logger.info("✅ Meta-Cognitive MAPE-K Cycle Complete")
            logger.info("=" * 60)

            return {
                "meta_plan": {
                    "solution_space": solution_space.__dict__,
                    "reasoning_path": reasoning_path.__dict__,
                },
                "metrics": {
                    "system_metrics": metrics.get("system_metrics", {}),
                    "reasoning_metrics": (
                        metrics.get("reasoning_metrics", {}).__dict__
                        if hasattr(metrics.get("reasoning_metrics"), "__dict__")
                        else metrics.get("reasoning_metrics", {})
                    ),
                },
                "analysis": analysis_result,
                "plan": plan,
                "execution_log": execution_log,
                "knowledge": knowledge,
            }

        except Exception as e:
            logger.error(f"❌ Meta-Cognitive MAPE-K Cycle failed: {e}", exc_info=True)
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, int]:
        """Get cycle statistics."""
        return self.stats.copy()

    def get_history(self) -> list:
        """Get reasoning history."""
        return self.reasoning_history.copy()
