"""
MAPE-K Cycle Coordinator.

Coordinates all MAPE-K phases into a complete cycle.
"""
import hashlib
import logging
from typing import Any, Dict, Optional

from src.core.agent_thinking import AgentThinkingCoach

from .meta_planning import MetaPlanner
from .monitoring import MonitoringPhase
from .analysis import AnalysisPhase
from .planning import PlanningPhase
from .execution import ExecutionPhase
from .knowledge import KnowledgePhase

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-mapek-coordinator:{_safe_hash(node_id)}",
            role="coordinator",
            capabilities=("mape_k", "healing", "quality"),
        )
        self.last_thinking_context: Dict[str, Any] = self.thinking_coach.prepare_task(
            {
                "task_type": "libx0t_mapek_coordinator_init",
                "goal": "Initialize MAPE-K phase coordinator",
                "signals": {
                    "node_hash": _safe_hash(node_id),
                    "phase_count": 6,
                },
                "safety_boundary": (
                    "Do not expose raw node ids, task payloads, or phase outputs in "
                    "coordinator thinking context."
                ),
            }
        )

        # History and statistics
        self.reasoning_history: list = []
        self.execution_logs: list = []
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
        }

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        task: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        safe_task = dict(task or {})
        signals = {
            "node_hash": _safe_hash(self.node_id),
            "input_task_type": safe_task.get("type", "unknown"),
            "task_key_count": len(safe_task),
            "task_keys_hash": _safe_hash("|".join(sorted(str(k) for k in safe_task))),
            "history_count": len(self.reasoning_history),
            "execution_log_count": len(self.execution_logs),
            "stats": dict(self.stats),
        }
        if extra:
            signals.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals,
                "constraints": {
                    "redact_node_id": True,
                    "redact_raw_task_payload": True,
                    "redact_phase_outputs": True,
                    "preserve_phase_order": True,
                },
                "safety_boundary": (
                    "Use only hashes, task key summaries, counters, phase names, and "
                    "status flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
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
        self._record_thinking(
            "libx0t_mapek_full_cycle_started",
            "Coordinate MAPE-K phases with explicit phase boundaries",
            task=task,
            extra={"status": "started"},
        )

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
            self._record_thinking(
                "libx0t_mapek_full_cycle_completed",
                "Record completed MAPE-K phase coordination",
                task=task,
                extra={
                    "status": "success",
                    "phase_outputs": [
                        "meta_plan",
                        "metrics",
                        "analysis",
                        "plan",
                        "execution_log",
                        "knowledge",
                    ],
                },
            )

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
            self._record_thinking(
                "libx0t_mapek_full_cycle_failed",
                "Capture MAPE-K phase coordination failure",
                task=task,
                extra={"status": "failed", "error_type": type(e).__name__},
            )
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, int]:
        """Get cycle statistics."""
        return self.stats.copy()

    def get_history(self) -> list:
        """Get reasoning history."""
        return self.reasoning_history.copy()
