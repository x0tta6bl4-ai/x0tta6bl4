"""
Planner phase for MAPE-K Self-Healing.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from src.core.mape_k.interfaces import PlannerInterface

class MAPEKPlanner(PlannerInterface):
    """
    Planner phase with feedback loop support.
    """

    def __init__(self, knowledge: Optional[Any] = None):
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
            "Transport Layer Mismatch": "Restart service",
        }

    def plan(self, issue: str) -> str:
        """Plan recovery strategy with feedback from Knowledge base."""
        if "AI-Analysis" in issue:
            for category, strategy in self.ai_strategies.items():
                if category in issue:
                    return strategy

        if self.knowledge:
            recommended = self.knowledge.get_recommended_action(issue)
            if recommended:
                return recommended

        return self.default_strategies.get(issue, "No action needed")
