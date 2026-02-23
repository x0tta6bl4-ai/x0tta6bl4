"""
Agent Coordination System for MaaS x0tta6bl4

Provides automatic coordination between multiple AI agents working simultaneously.
"""

from .state import AgentState, AgentCoordinator, CoordinationLock
from .events import Event, EventBus, EventType
from .tasks import TaskQueue, Task, TaskStatus, TaskPriority
from .conflicts import ConflictDetector, ConflictResolution

__all__ = [
    "AgentState",
    "AgentCoordinator", 
    "CoordinationLock",
    "Event",
    "EventBus",
    "EventType",
    "TaskQueue",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "ConflictDetector",
    "ConflictResolution",
]

__version__ = "1.0.0"
