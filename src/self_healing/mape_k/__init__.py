"""MAPE-K self-healing package.

Contains the six core MAPE-K components:
- MAPEKMonitor: watches system metrics
- MAPEKAnalyzer: detects anomalies
- MAPEKPlanner: generates recovery plans
- MAPEKExecutor: executes recovery actions
- MAPEKKnowledge: maintains historical patterns
- SelfHealingManager: orchestrates the full loop
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy module-level singletons to avoid circular import issues
from .monitor import MAPEKMonitor
from .analyzer import MAPEKAnalyzer
from .planner import MAPEKPlanner
from .executor import MAPEKExecutor
from .knowledge import MAPEKKnowledge
from .manager import SelfHealingManager

__all__ = [
    "MAPEKMonitor",
    "MAPEKAnalyzer",
    "MAPEKPlanner",
    "MAPEKExecutor",
    "MAPEKKnowledge",
    "SelfHealingManager",
]
