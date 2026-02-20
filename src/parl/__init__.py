"""
PARL (Parallel-Agent Reinforcement Learning) Module

Key innovation from Kimi K2.5 enabling up to 1500 parallel steps with 4.5x speedup.

Components:
- PARLController: Central controller for parallel learning
- AgentWorker: Agent executor in parallel mode
- TaskScheduler: Intelligent task scheduling
- Experience: Experience tuple for RL
- Policy: Policy management
"""

from src.parl.controller import PARLController, PARLConfig, PARLStats
from src.parl.worker import AgentWorker, WorkerState
from src.parl.scheduler import TaskScheduler, Schedule, QueueStats
from src.parl.types import Task, TaskId, TaskPriority, TaskStatus
from src.parl.types import Experience, Policy, StepResult
from src.parl.types import PARLMetrics

__all__ = [
    # Controller
    "PARLController",
    "PARLConfig",
    "PARLStats",
    # Worker
    "AgentWorker",
    "WorkerState",
    # Scheduler
    "TaskScheduler",
    "Schedule",
    "QueueStats",
    # Types
    "Task",
    "TaskId",
    "TaskPriority",
    "TaskStatus",
    "Experience",
    "Policy",
    "StepResult",
    "PARLMetrics",
]
