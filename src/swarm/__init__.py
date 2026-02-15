"""
Kimi K2.5 Agent Swarm Integration
==================================

Provides:
- SwarmOrchestrator: Central coordinator for agent swarms
- Agent: Base class for swarm agents
- PARLController: Parallel-Agent RL for 4.5x speedup

Example:
    >>> from src.swarm import SwarmOrchestrator, SwarmConfig
    >>> config = SwarmConfig(name="optimizer", max_agents=50)
    >>> swarm = SwarmOrchestrator(config)
    >>> await swarm.initialize()
"""

from src.swarm.agent import (Agent, AgentCapability, AgentMessage, AgentState,
                             CapabilityScope, SpecializedAgent, TaskResult,
                             create_agent)
from src.swarm.orchestrator import (SwarmConfig, SwarmMetrics,
                                    SwarmOrchestrator, SwarmStatus, Task,
                                    create_swarm)
from src.swarm.parl.controller import (PARLConfig, PARLController, PARLMetrics,
                                       execute_with_parl)

__all__ = [
    # Orchestrator
    "SwarmOrchestrator",
    "SwarmConfig",
    "SwarmStatus",
    "SwarmMetrics",
    "Task",
    "create_swarm",
    # Agent
    "Agent",
    "AgentState",
    "AgentCapability",
    "AgentMessage",
    "TaskResult",
    "SpecializedAgent",
    "CapabilityScope",
    "create_agent",
    # PARL
    "PARLController",
    "PARLConfig",
    "PARLMetrics",
    "execute_with_parl",
]
