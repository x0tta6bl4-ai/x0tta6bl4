"""
MAPE-K Core for x0tta6bl4.
Consolidated facade for Monitor, Analyze, Plan, Execute, Knowledge modules.
"""
from typing import Any, Dict, Optional

from src.core.agent_thinking import AgentThinkingCoach

from .monitor import MAPEKMonitor
from .analyzer import MAPEKAnalyzer
from .planner import MAPEKPlanner
from .executor import MAPEKExecutor
from .knowledge import MAPEKKnowledge
from . import manager as _manager


class SelfHealingManager(_manager.SelfHealingManager):
    """Compatibility facade for the split MAPE-K package."""

    def __init__(self, *args, **kwargs):
        _manager.MAPEKExecutor = MAPEKExecutor
        super().__init__(*args, **kwargs)
        self.thinking_coach = AgentThinkingCoach(
            agent_id="self-healing-mapek-manager-facade",
            role="healing",
            capabilities=("mape_k", "zero-trust", "self-healing"),
        )
        self.last_thinking_context: Dict[str, Any] = {}
        self._record_thinking(
            "mapek_self_healing_manager_initialized",
            "initialize MAPE-K compatibility facade without readiness overclaiming",
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "constraints": {
                "facade_state_is_not_recovery_proof": True,
                "do_not_claim_dataplane_delivery": True,
                "do_not_claim_production_readiness": True,
            },
            "safety_boundary": (
                "The MAPE-K manager facade exposes local orchestration state only; "
                "it does not prove recovery execution, dataplane delivery, or "
                "production readiness."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose facade thinking state and nested analyzer status when present."""
        status: Dict[str, Any] = {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }
        analyzer = getattr(self, "analyzer", None)
        if hasattr(analyzer, "get_thinking_status"):
            status["analyzer"] = analyzer.get_thinking_status()
        return status

__all__ = [
    "MAPEKMonitor",
    "MAPEKAnalyzer",
    "MAPEKPlanner",
    "MAPEKExecutor",
    "MAPEKKnowledge",
    "SelfHealingManager",
]
