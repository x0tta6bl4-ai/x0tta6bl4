"""Orchestrator state enumeration."""
from __future__ import annotations
from enum import Enum


class OrchestratorState(Enum):
    """Current state of the orchestrator."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
