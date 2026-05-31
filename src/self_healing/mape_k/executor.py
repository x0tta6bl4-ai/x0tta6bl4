"""
Executor phase for MAPE-K Self-Healing.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from src.core.mape_k.interfaces import ExecutorInterface

class MAPEKExecutor(ExecutorInterface):
    """
    MAPE-K Executor with production-ready recovery actions.
    """

    def __init__(self, *, event_bus: Optional[Any] = None):
        self.was_simulated = False
        try:
            from src.self_healing.recovery_actions import RecoveryActionExecutor
            kwargs = {"event_bus": event_bus} if event_bus is not None else {}
            self.recovery_executor = RecoveryActionExecutor(**kwargs)
            self.use_recovery_executor = True
        except ImportError:
            self.recovery_executor = None
            self.use_recovery_executor = False
            logger.warning("RecoveryActionExecutor not available")

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Execute recovery action."""
        logger.info(f"Executing action: {action}")
        self.was_simulated = False

        if "AI-Analysis" in action and "```" in action:
            return self.execute_script(action, context)

        if self.use_recovery_executor and self.recovery_executor:
            result = self.recovery_executor.execute(action, context)
            last = getattr(self.recovery_executor, "last_result", None)
            if last and getattr(last, "details", None):
                if last.details.get("method") == "simulated":
                    self.was_simulated = True
            return result

        if self._is_noop_action(action):
            return True

        return False

    @staticmethod
    def _is_noop_action(action: str) -> bool:
        normalized = " ".join(action.lower().split())
        return normalized in {"", "no action", "no action needed", "nothing to do", "do nothing", "monitor", "monitor only"}

    def execute_script(self, script: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a custom recovery script."""
        if self.use_recovery_executor and self.recovery_executor:
            context = context or {}
            context["script"] = script
            return self.recovery_executor.execute("execute_script", context)
        return False
