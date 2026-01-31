"""
PARL (Parallel-Agent Reinforcement Learning) Module
=====================================================

Provides up to 1500 parallel steps with 4.5x speedup.
"""

from src.swarm.parl.controller import (
    PARLController,
    PARLConfig,
    PARLMetrics,
    TaskScheduler,
    AgentWorker,
    Experience,
    execute_with_parl,
)

__all__ = [
    "PARLController",
    "PARLConfig",
    "PARLMetrics",
    "TaskScheduler",
    "AgentWorker",
    "Experience",
    "execute_with_parl",
]
