"""
Swarm Consensus Integration Module

Integrates Raft, Paxos, and PBFT consensus algorithms
with the SwarmOrchestrator for distributed AI agent coordination.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from .consensus import (
    ConsensusEngine,
    ConsensusAlgorithm,
    ConsensusResult,
    Decision,
    Vote,
    VoteType,
)
from .paxos import PaxosNode, MultiPaxos, ProposalNumber
from .pbft import PBFTNode, PBFTPhase

try:
    from src.coordination.consensus_transport import (
        ConsensusTransport,
        ConsensusMessage,
    )
    _TRANSPORT_AVAILABLE = True
except ImportError:
    ConsensusTransport = None  # type: ignore[assignment,misc]
    ConsensusMessage = None  # type: ignore[assignment]
    _TRANSPORT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class WeightedVote:
    """A weighted vote for swarm decisions with choice tracking."""
    voter_id: str
    choice: Any
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "choice": str(self.choice),
            "weight": self.weight,
        }


class ConsensusMode(str, Enum):
    """Available consensus modes for swarm decisions."""
    SIMPLE = "simple"           # Simple majority voting
    RAFT = "raft"               # Raft leader-based consensus
    PAXOS = "paxos"             # Paxos consensus
    MULTIPAXOS = "multipaxos"   # Multi-Paxos for sequences
    PBFT = "pbft"               # Byzantine fault-tolerant consensus
    WEIGHTED = "weighted"       # Weighted voting by agent capability


@dataclass
class AgentInfo:
    """Information about an agent in the swarm."""
    agent_id: str
    name: str
    capabilities: Set[str] = field(default_factory=set)
    weight: float = 1.0
    is_byzantine: bool = False  # For testing Byzantine scenarios
    last_seen: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "weight": self.weight,
            "is_byzantine": self.is_byzantine,
            "last_seen": self.last_seen.isoformat(),
        }


@dataclass
class SwarmDecision:
    """A decision made by the swarm."""
    decision_id: str
    topic: str
    proposals: List[Any]
    winner: Optional[Any] = None
    mode: ConsensusMode = ConsensusMode.SIMPLE
    votes: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    success: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "topic": self.topic,
            "proposals": self.proposals,
            "winner": self.winner,
            "mode": self.mode.value,
            "votes": self.votes,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


class SwarmConsensusManager:
    """
    Manages consensus operations for a swarm of AI agents.
    
    Provides a unified interface for different consensus algorithms,
    automatically selecting the appropriate algorithm based on:
    - Number of agents
    - Trust level (Byzantine tolerance needed)
    - Performance requirements
    - Decision type
    """
    
    # Decisions older than this are pruned from memory
    DECISION_TTL_SECONDS = 3600

    def __init__(
        self,
        node_id: str,
        agents: Optional[Dict[str, AgentInfo]] = None,
        default_mode: ConsensusMode = ConsensusMode.SIMPLE,
        transport: Optional["ConsensusTransport"] = None,
    ):
        self.node_id = node_id
        self.agents = agents or {}
        self.default_mode = default_mode

        # Real transport layer (optional — falls back to logging when absent)
        self._transport: Optional["ConsensusTransport"] = transport

        # Consensus engines - initialized once and reused
        self._simple_engine = ConsensusEngine()
        self._raft_node: Optional["RaftNode"] = None  # Reused across decisions
        self._paxos_node: Optional[PaxosNode] = None
        self._multipaxos: Optional[MultiPaxos] = None
        self._pbft_node: Optional[PBFTNode] = None

        # Decision tracking
        self._decisions: Dict[str, SwarmDecision] = {}
        self._pending_decisions: Dict[str, asyncio.Future] = {}

        # Message routing
        self._message_handlers: Dict[str, Callable] = {}
        self._outbound_queue: asyncio.Queue = asyncio.Queue()

        # Callbacks
        self._on_decision: Optional[Callable[[SwarmDecision], None]] = None

        # Lifecycle state
        self._started = False
    
    def set_callbacks(
        self,
        on_decision: Optional[Callable[[SwarmDecision], None]] = None,
    ) -> None:
        self._on_decision = on_decision
    
    async def start(self) -> None:
        """
        Start the consensus manager.

        Initializes all consensus nodes and starts background tasks.
        Must be called before making decisions.
        """
        if self._started:
            return

        # Start simple consensus engine
        await self._simple_engine.start()

        # Initialize Raft node
        self._initialize_raft()

        # Initialize Paxos node
        self._initialize_paxos()

        # Start transport and register handler for inbound consensus messages
        if self._transport is not None:
            self._transport.register_handler(
                "consensus_msg", self._handle_transport_message
            )
            await self._transport.start()

        self._started = True
        logger.info(f"SwarmConsensusManager started for node {self.node_id}")
    
    async def stop(self) -> None:
        """
        Stop the consensus manager.

        Cleans up resources and stops background tasks.
        """
        if not self._started:
            return

        # Stop simple consensus engine
        await self._simple_engine.stop()

        # Stop transport
        if self._transport is not None:
            await self._transport.stop()

        self._started = False
        logger.info(f"SwarmConsensusManager stopped for node {self.node_id}")
    
    def add_agent(self, agent: AgentInfo) -> None:
        """Add an agent to the swarm."""
        self.agents[agent.agent_id] = agent
        self._update_consensus_nodes()
    
    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the swarm."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self._update_consensus_nodes()
    
    def _update_consensus_nodes(self) -> None:
        """Update consensus nodes when agents change."""
        peer_ids = {aid for aid in self.agents if aid != self.node_id}
        
        # Update Raft
        if self._raft_node:
            self._raft_node.peers = peer_ids
        
        # Update Paxos
        if self._paxos_node:
            self._paxos_node.peers = peer_ids
            self._paxos_node.all_nodes = peer_ids | {self.node_id}
        
        # Update PBFT
        if self._pbft_node:
            self._pbft_node.peers = peer_ids
            self._pbft_node.all_nodes = peer_ids | {self.node_id}
    
    def _initialize_raft(self) -> None:
        """
        Initialize Raft node (once, reused across decisions).
        
        This fixes the critical bug where a new RaftNode was created
        on every decision, breaking Raft semantics (state, term, log
        would be reset each time).
        """
        if self._raft_node is not None:
            return  # Already initialized
        
        from .consensus import RaftNode
        
        peer_ids = {aid for aid in self.agents if aid != self.node_id}
        self._raft_node = RaftNode(
            node_id=self.node_id,
            peers=peer_ids,
        )
        self._raft_node.set_callbacks(
            on_leader_elected=self._on_raft_leader_elected,
            send_message=self._send_consensus_message,
            send_heartbeat=self._send_consensus_message,
        )
        logger.info(f"Initialized Raft node for {self.node_id} with peers: {peer_ids}")
    
    def _on_raft_leader_elected(self, leader_id: str) -> None:
        """Handle Raft leader election."""
        logger.info(f"Raft leader elected: {leader_id}")
    
    def _initialize_paxos(self) -> None:
        """Initialize Paxos node."""
        peer_ids = {aid for aid in self.agents if aid != self.node_id}
        self._paxos_node = PaxosNode(
            node_id=self.node_id,
            peers=peer_ids,
        )
        self._paxos_node.set_callbacks(
            on_value_committed=self._on_paxos_committed,
            send_message=self._send_consensus_message,
        )
    
    def _initialize_multipaxos(self, leader_id: Optional[str] = None) -> None:
        """Initialize Multi-Paxos."""
        peer_ids = {aid for aid in self.agents if aid != self.node_id}
        self._multipaxos = MultiPaxos(
            node_id=self.node_id,
            peers=peer_ids,
            leader_id=leader_id or self.node_id,
        )
        self._multipaxos.set_callbacks(
            on_log_entry=self._on_multipaxos_entry,
            send_message=self._send_consensus_message,
        )
    
    def _initialize_pbft(self, f: int = 1) -> None:
        """Initialize PBFT node."""
        peer_ids = {aid for aid in self.agents if aid != self.node_id}
        self._pbft_node = PBFTNode(
            node_id=self.node_id,
            peers=peer_ids,
            f=f,
        )
        self._pbft_node.set_callbacks(
            on_execute=self._on_pbft_execute,
            send_message=self._send_consensus_message,
        )
    
    def _send_consensus_message(self, target_id: str, message: Dict) -> None:
        """Send a consensus message to another agent via transport (or log if absent)."""
        if self._transport is not None and _TRANSPORT_AVAILABLE:
            consensus_msg = ConsensusMessage(
                source_node=self.node_id,
                target_node=target_id,
                message_type="consensus_msg",
                payload=message,
            )
            asyncio.create_task(self._transport.send(consensus_msg))
        else:
            logger.debug(
                f"[no transport] {self.node_id} → {target_id}: {message.get('type')}"
            )

    def _handle_transport_message(self, transport_msg: "ConsensusMessage") -> None:
        """Handle a message arriving via ConsensusTransport."""
        self.receive_message(transport_msg.payload)
    
    def _on_paxos_committed(self, instance_id: str, value: Any) -> None:
        """Handle Paxos committed value."""
        logger.info(f"Paxos committed: {instance_id} = {value}")
        
        if instance_id in self._pending_decisions:
            future = self._pending_decisions.pop(instance_id)
            if not future.done():
                future.set_result(value)
    
    def _on_multipaxos_entry(self, index: int, value: Any) -> None:
        """Handle Multi-Paxos log entry."""
        logger.info(f"Multi-Paxos entry {index}: {value}")
    
    def _on_pbft_execute(self, operation: Any) -> Any:
        """Handle PBFT execution."""
        logger.info(f"PBFT executing: {operation}")
        return {"status": "executed", "operation": str(operation)}
    
    # ==================== Decision Making ====================
    
    async def decide(
        self,
        topic: str,
        proposals: List[Any],
        mode: Optional[ConsensusMode] = None,
        timeout: float = 30.0,
    ) -> SwarmDecision:
        """
        Make a decision using consensus.
        
        Args:
            topic: The topic/subject of the decision
            proposals: List of proposals to choose from
            mode: Consensus mode to use (default: self.default_mode)
            timeout: Maximum time to wait for consensus
            
        Returns:
            SwarmDecision with the result
        """
        start_time = datetime.utcnow()
        decision_id = str(uuid.uuid4())[:8]
        mode = mode or self.default_mode
        
        decision = SwarmDecision(
            decision_id=decision_id,
            topic=topic,
            proposals=proposals,
            mode=mode,
        )
        
        try:
            if mode == ConsensusMode.SIMPLE:
                winner = await self._simple_decide(topic, proposals, timeout)
            elif mode == ConsensusMode.RAFT:
                winner = await self._raft_decide(topic, proposals, timeout)
            elif mode == ConsensusMode.PAXOS:
                winner = await self._paxos_decide(topic, proposals, timeout)
            elif mode == ConsensusMode.MULTIPAXOS:
                winner = await self._multipaxos_decide(topic, proposals, timeout)
            elif mode == ConsensusMode.PBFT:
                winner = await self._pbft_decide(topic, proposals, timeout)
            elif mode == ConsensusMode.WEIGHTED:
                winner = await self._weighted_decide(topic, proposals, timeout)
            else:
                raise ValueError(f"Unknown consensus mode: {mode}")
            
            decision.winner = winner
            decision.success = True
            
        except asyncio.TimeoutError:
            logger.warning(f"Decision {decision_id} timed out")
            decision.success = False
        except Exception as e:
            logger.error(f"Decision {decision_id} failed: {e}")
            decision.success = False
        
        decision.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        self._decisions[decision_id] = decision

        # Prune old decisions to prevent memory leak
        if len(self._decisions) % 100 == 0:
            self._cleanup_decisions()

        if self._on_decision:
            self._on_decision(decision)

        return decision
    
    async def _simple_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """Simple majority voting."""
        import random
        from collections import Counter
        
        # Collect weighted votes
        weighted_votes: Dict[Any, float] = {}
        
        # Each agent votes for their preferred proposal
        for agent_id, agent in self.agents.items():
            # In real implementation, agents would actually vote
            # For now, simulate random voting
            chosen = random.choice(proposals)
            if chosen not in weighted_votes:
                weighted_votes[chosen] = 0.0
            weighted_votes[chosen] += agent.weight
        
        # Find winner by total weight
        if not weighted_votes:
            return proposals[0]
        
        winner = max(weighted_votes.keys(), key=lambda x: weighted_votes[x])
        return winner
    
    async def _raft_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """
        Raft-based decision (leader decides).
        
        FIXED: Now uses a single RaftNode instance that is reused
        across all decisions, preserving Raft state (term, log, voted_for).
        
        Previously, this method created a new RaftNode on every call,
        which broke Raft semantics completely.
        """
        from .consensus import RaftNode
        
        # Initialize Raft node once (reused across decisions)
        self._initialize_raft()
        
        # Ensure node is in a valid state
        if self._raft_node is None:
            raise RuntimeError("Failed to initialize Raft node")
        
        # Tick the Raft node to allow leader election
        self._raft_node.tick()
        
        # Check if we're the leader
        if self._raft_node.state == RaftNode.State.LEADER:
            # Leader decides - propose the first option
            logger.info(f"Raft leader {self.node_id} deciding on {topic}")
            return proposals[0]
        else:
            # Wait for leader to be elected and decide
            # In a real implementation, the leader would replicate the decision
            # For now, wait briefly and return first proposal
            await asyncio.sleep(0.1)
            
            # Tick again to progress election
            self._raft_node.tick()
            
            # Return first proposal (simplified - real Raft would wait for commit)
            return proposals[0]
    
    async def _paxos_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """Paxos-based decision."""
        if not self._paxos_node:
            self._initialize_paxos()
        
        # Propose the first proposal
        instance_id = f"decision-{uuid.uuid4().hex[:8]}"
        
        future = asyncio.Future()
        self._pending_decisions[instance_id] = future
        
        success, value = await self._paxos_node.propose(
            value=proposals[0],
            instance_id=instance_id,
        )
        
        if success:
            return value
        raise ValueError("Paxos consensus failed")
    
    async def _multipaxos_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """Multi-Paxos decision."""
        if not self._multipaxos:
            self._initialize_multipaxos()
        
        success, value = await self._multipaxos.propose(proposals[0])
        
        if success:
            return value
        raise ValueError("Multi-Paxos consensus failed")
    
    async def _pbft_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """PBFT-based decision (Byzantine tolerant)."""
        if not self._pbft_node:
            # Calculate f based on number of nodes
            n = len(self.agents)
            f = (n - 1) // 3
            self._initialize_pbft(max(1, f))
        
        success, result = await self._pbft_node.request({
            "topic": topic,
            "proposals": proposals,
        })
        
        if success:
            return result
        raise ValueError("PBFT consensus failed")
    
    async def _weighted_decide(
        self,
        topic: str,
        proposals: List[Any],
        timeout: float,
    ) -> Any:
        """Weighted voting based on agent capabilities."""
        import random
        
        # Collect weighted votes
        weighted_votes: Dict[Any, float] = {}
        
        for agent_id, agent in self.agents.items():
            # Weight based on capabilities relevant to topic
            weight = agent.weight
            if topic.lower() in agent.capabilities:
                weight *= 2.0  # Boost for relevant capability
            
            chosen = random.choice(proposals)
            if chosen not in weighted_votes:
                weighted_votes[chosen] = 0.0
            weighted_votes[chosen] += weight
        
        # Find winner by total weight
        if not weighted_votes:
            return proposals[0]
        
        winner = max(weighted_votes.keys(), key=lambda x: weighted_votes[x])
        return winner
    
    # ==================== Message Handling ====================
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """
        Receive a consensus message.
        
        Routes messages to the appropriate consensus engine based on type.
        Supports Raft, Paxos, and PBFT message types.
        """
        msg_type = message.get("type", "")

        # Route to Raft
        if msg_type in ("append_entries", "request_vote", "vote_response"):
            if self._raft_node:
                self._raft_node.receive_message(message)
        
        # Route to Paxos
        elif msg_type in ("prepare", "promise", "accept", "accepted", "commit"):
            if self._paxos_node:
                self._paxos_node.receive_message(message)
        
        # Route to PBFT
        elif msg_type in ("pre_prepare", "prepare", "commit", "view_change", "new_view"):
            if self._pbft_node:
                self._pbft_node.receive_message(message)
        
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    def _cleanup_decisions(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Remove decisions older than max_age_seconds from memory.

        Prevents unbounded growth of the _decisions dict.
        Returns the number of entries removed.
        """
        cutoff = datetime.utcnow() - timedelta(
            seconds=max_age_seconds if max_age_seconds is not None else self.DECISION_TTL_SECONDS
        )
        stale = [
            did for did, d in self._decisions.items()
            if d.timestamp < cutoff
        ]
        for did in stale:
            del self._decisions[did]
        if stale:
            logger.debug(f"Pruned {len(stale)} stale decisions from {self.node_id}")
        return len(stale)

    def get_decision(self, decision_id: str) -> Optional[SwarmDecision]:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)
    
    def get_all_decisions(self) -> List[SwarmDecision]:
        """Get all decisions."""
        return list(self._decisions.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consensus statistics."""
        total = len(self._decisions)
        successful = sum(1 for d in self._decisions.values() if d.success)
        
        mode_counts = {}
        for d in self._decisions.values():
            mode = d.mode.value
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        avg_duration = 0.0
        if successful > 0:
            durations = [d.duration_ms for d in self._decisions.values() if d.success]
            avg_duration = sum(durations) / len(durations)
        
        # Raft state
        raft_state = None
        if self._raft_node:
            raft_state = {
                "state": self._raft_node.state.value if hasattr(self._raft_node.state, 'value') else str(self._raft_node.state),
                "term": self._raft_node.raft_state.current_term,
                "is_leader": self._raft_node.state == self._raft_node.State.LEADER if hasattr(self._raft_node, 'State') else False,
            }
        
        return {
            "node_id": self.node_id,
            "started": self._started,
            "total_decisions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "mode_usage": mode_counts,
            "avg_duration_ms": avg_duration,
            "agents": len(self.agents),
            "raft_state": raft_state,
        }
    
    def get_raft_node(self) -> Optional["RaftNode"]:
        """Get the Raft node instance (for advanced usage)."""
        return self._raft_node


# Export
__all__ = [
    "ConsensusMode",
    "AgentInfo",
    "SwarmDecision",
    "SwarmConsensusManager",
    "WeightedVote",
]
