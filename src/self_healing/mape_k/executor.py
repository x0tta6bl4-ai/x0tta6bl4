"""MAPE-K Executor component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MAPEKExecutor:
    """
    MAPE-K Executor with production-ready recovery actions.

    Uses RecoveryActionExecutor for real recovery operations.
    """

    def __init__(self):
        try:
            from src.self_healing.recovery_actions import \
                RecoveryActionExecutor

            self.recovery_executor = RecoveryActionExecutor()
            self.use_recovery_executor = True
        except ImportError:
            self.recovery_executor = None
            self.use_recovery_executor = False
            logger.warning("RecoveryActionExecutor not available; recovery actions fail closed")

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute recovery action.

        Args:
            action: Action string (e.g., "Restart service", "Switch route")
            context: Additional context for action execution

        Returns:
            True if action executed successfully
        """
        logger.info(f"Executing action: {action}")
        self.was_simulated = False

        # Handle AI Analysis format if it contains a script
        if "AI-Analysis" in action and "```" in action:
            return self.execute_script(action, context)

        if self.use_recovery_executor and self.recovery_executor:
            result = self.recovery_executor.execute(action, context)
            # Check if the action was only simulated (not real recovery)
            last = getattr(self.recovery_executor, "last_result", None)
            if last and getattr(last, "details", None):
                if last.details.get("method") == "simulated":
                    self.was_simulated = True
            return result

        if self._is_noop_action(action):
            logger.info("No recovery action required: %s", action)
            return True

        logger.error("RecoveryActionExecutor unavailable; refusing action: %s", action)
        return False

    @staticmethod
    def _is_noop_action(action: str) -> bool:
        normalized = " ".join(action.lower().split())
        return normalized in {
            "",
            "no action",
            "no action needed",
            "nothing to do",
            "do nothing",
            "monitor",
            "monitor only",
        }

    def execute_script(self, script: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute a custom recovery script.
        """
        if self.use_recovery_executor and self.recovery_executor:
            context = context or {}
            context["script"] = script
            return self.recovery_executor.execute("execute_script", context)
        return False


