"""MAPE-K Planner component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MAPEKPlanner:
    """
    Planner phase with feedback loop support.

    Uses historical success patterns from Knowledge base to
    select optimal recovery strategies.
    """

    def __init__(self, knowledge: Optional["MAPEKKnowledge"] = None):
        self.knowledge = knowledge
        self.default_strategies = {
            "High CPU": "Restart service",
            "High Memory": "Clear cache",
            "Network Loss": "Switch route",
            "Predicted Peak": "Scale up",
        }
        self.ai_strategies = {
            "Network Link Failure": "Switch route",
            "Proxy Configuration Error": "Restart service",
            "Censorship Interference": "Switch protocol",
            "Byzantine Attack": "Quarantine node",
            "Resource Exhaustion": "Clear cache",
            "Transport Layer Mismatch": "Restart service"
        }

    def plan(self, issue: str) -> str:
        """
        Plan recovery strategy with feedback from Knowledge base.

        Uses most successful historical action for this issue type.
        Falls back to default strategy if no history available.
        """
        # Handle AI Analysis format: "AI-Analysis (Category): reasoning"
        if "AI-Analysis" in issue:
            for category, strategy in self.ai_strategies.items():
                if category in issue:
                    logger.info(f"🤖 AI-Planner: Selected strategy '{strategy}' for category '{category}'")
                    return strategy

        # Try to get recommended action from knowledge base
        if self.knowledge:
            recommended = self.knowledge.get_recommended_action(issue)
            if recommended:
                logger.debug(f"Using recommended action from knowledge: {recommended}")
                return recommended

        # Fallback to default strategies
        return self.default_strategies.get(issue, "No action needed")


