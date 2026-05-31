"""
Types and definitions for Swarm Intelligence.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid

from ..consensus_integration import ConsensusMode

MAPEK_CLAIM_BOUNDARY = (
    "Swarm MAPE-K execution event only. It records local identity, policy, "
    "consensus, and safe actuator state; it is not production rollout or "
    "external settlement evidence."
)


class DecisionPriority(str, Enum):
    """Priority levels for decisions."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionType(str, Enum):
    """Types of decisions the swarm can make."""
    ROUTING = "routing"
    SCALING = "scaling"
    HEALING = "healing"
    CONFIGURATION = "configuration"
    RESOURCE_ALLOCATION = "resource_allocation"
    FAULT_TOLERANCE = "fault_tolerance"
    LOAD_BALANCING = "load_balancing"
    CUSTOM = "custom"


class ConsensusStatus(str, Enum):
    """Status of the consensus system."""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class DecisionContext:
    """Context for a swarm decision."""
    topic: str
    description: str = ""
    decision_type: DecisionType = DecisionType.CUSTOM
    priority: DecisionPriority = DecisionPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    options: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "description": self.description,
            "decision_type": self.decision_type.value,
            "priority": self.priority.value,
            "data": self.data,
            "options": self.options,
            "metadata": self.metadata,
        }


@dataclass
class SwarmAction:
    """An action proposed to the swarm."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    proposer_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    requires_consensus: bool = True
    timeout_ms: int = 100
    priority: DecisionPriority = DecisionPriority.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "parameters": self.parameters,
            "proposer_id": self.proposer_id,
            "created_at": self.created_at.isoformat(),
            "requires_consensus": self.requires_consensus,
            "timeout_ms": self.timeout_ms,
            "priority": self.priority.value,
        }


@dataclass
class DecisionResult:
    """Result of a swarm decision."""
    decision_id: str
    approved: bool
    context: DecisionContext
    consensus_mode: ConsensusMode
    latency_ms: float
    participation_rate: float = 0.0
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    winner: Optional[Any] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "approved": self.approved,
            "context": self.context.to_dict(),
            "consensus_mode": self.consensus_mode.value,
            "latency_ms": self.latency_ms,
            "participation_rate": self.participation_rate,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "votes_abstain": self.votes_abstain,
            "winner": self.winner,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SwarmNodeInfo:
    """Information about a node in the swarm."""
    node_id: str
    name: str = ""
    is_leader: bool = False
    is_active: bool = True
    capabilities: Set[str] = field(default_factory=set)
    weight: float = 1.0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "is_leader": self.is_leader,
            "is_active": self.is_active,
            "capabilities": list(self.capabilities),
            "weight": self.weight,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }
