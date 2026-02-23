"""
Kimi K2.5 Agent Swarm Integration
=================================

Provides:
- SwarmOrchestrator: Central coordinator for agent swarms
- Agent: Base class for swarm agents
- PARLController: Parallel-Agent RL for 4.5x speedup
- ConsensusEngine: Distributed decision making (Phase 2)
- RaftNode: Leader-based consensus (Phase 2)
- PaxosNode: Paxos consensus algorithm (Phase 2)
- PBFTNode: Byzantine fault-tolerant consensus (Phase 2)
- SwarmConsensusManager: Unified consensus interface (Phase 2)

Example:
    >>> from src.swarm import SwarmOrchestrator, SwarmConfig
    >>> config = SwarmConfig(name="optimizer", max_agents=50)
    >>> swarm = SwarmOrchestrator(config)
    >>> await swarm.initialize()
    
    >>> # Using consensus
    >>> from src.swarm import SwarmConsensusManager, ConsensusMode
    >>> manager = SwarmConsensusManager(node_id="agent-1")
    >>> decision = await manager.decide("topic", ["a", "b"])
"""

from src.swarm.agent import (Agent, AgentCapability, AgentMessage, AgentState,
                             CapabilityScope, SpecializedAgent, TaskResult,
                             create_agent)
from src.swarm.orchestrator import (SwarmConfig, SwarmMetrics,
                                    SwarmOrchestrator, SwarmStatus, Task,
                                    create_swarm)
from src.swarm.parl.controller import (PARLConfig, PARLController, PARLMetrics,
                                       execute_with_parl)
from src.swarm.consensus import (
    Decision, DecisionStatus, Vote, VoteType,
    ConsensusAlgorithm, ConsensusEngine, ConsensusResult,
    RaftNode, RaftState,
)
from src.swarm.paxos import (
    PaxosNode, MultiPaxos, PaxosPhase, ProposalNumber, PaxosMessage,
)
from src.swarm.pbft import (
    PBFTNode, PBFTPhase, PBFTMessage, PBFTRequest,
)
from src.swarm.consensus_integration import (
    SwarmConsensusManager, ConsensusMode, AgentInfo, SwarmDecision,
)
from src.swarm.intelligence import (
    SwarmIntelligence, DecisionContext, DecisionResult, SwarmAction,
    DecisionPriority, DecisionType, ConsensusStatus, SwarmNodeInfo,
    MAPEKIntegration, KimiK25Integration, create_swarm_intelligence,
)

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
    # Consensus (Phase 2)
    "Decision",
    "DecisionStatus",
    "Vote",
    "VoteType",
    "ConsensusAlgorithm",
    "ConsensusEngine",
    "ConsensusResult",
    "RaftNode",
    "RaftState",
    # Paxos (Phase 2)
    "PaxosNode",
    "MultiPaxos",
    "PaxosPhase",
    "ProposalNumber",
    "PaxosMessage",
    # PBFT (Phase 2)
    "PBFTNode",
    "PBFTPhase",
    "PBFTMessage",
    "PBFTRequest",
    # Consensus Integration (Phase 2)
    "SwarmConsensusManager",
    "ConsensusMode",
    "AgentInfo",
    "SwarmDecision",
    # Swarm Intelligence (Phase 2)
    "SwarmIntelligence",
    "DecisionContext",
    "DecisionResult",
    "SwarmAction",
    "DecisionPriority",
    "DecisionType",
    "ConsensusStatus",
    "SwarmNodeInfo",
    "MAPEKIntegration",
    "KimiK25Integration",
    "create_swarm_intelligence",
]
