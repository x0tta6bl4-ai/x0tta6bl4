"""
MAPE-K Core for x0tta6bl4.
Consolidated facade for Monitor, Analyze, Plan, Execute, Knowledge modules.
"""
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

__all__ = [
    "MAPEKMonitor",
    "MAPEKAnalyzer",
    "MAPEKPlanner",
    "MAPEKExecutor",
    "MAPEKKnowledge",
    "SelfHealingManager",
]
