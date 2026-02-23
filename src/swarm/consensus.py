"""
Swarm Intelligence Phase 2 - Distributed Decision Making

Provides consensus algorithms, voting mechanisms, and distributed
decision making for swarm coordination.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar
import uuid
import random

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DecisionStatus(str, Enum):
    """Status of a decision."""
    PENDING = "pending"
    VOTING = "voting"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class VoteType(str, Enum):
    """Type of vote."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ConsensusAlgorithm(str, Enum):
    """Available consensus algorithms."""
    SIMPLE_MAJORITY = "simple_majority"      # >50% approve
    SUPERMAJORITY = "supermajority"          # >66% approve
    UNANIMOUS = "unanimous"                  # 100% approve
    WEIGHTED = "weighted"                    # Weight-based voting
    BYZANTINE = "byzantine"                  # Byzantine fault tolerant
    RAFT = "raft"                            # Raft leader-based
    PBFT = "pbft"                            # Practical Byzantine Fault Tolerance


@dataclass
class Vote:
    """A single vote in a decision."""
    voter_id: str
    vote_type: VoteType
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "vote_type": self.vote_type.value,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "signature": self.signature,
        }


@dataclass
class Decision(Generic[T]):
    """A decision to be made by the swarm."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    description: str = ""
    proposal: Optional[T] = None
    proposer_id: str = ""
    status: DecisionStatus = DecisionStatus.PENDING
    algorithm: ConsensusAlgorithm = ConsensusAlgorithm.SIMPLE_MAJORITY
    
    # Voting
    votes: Dict[str, Vote] = field(default_factory=dict)
    eligible_voters: Set[str] = field(default_factory=set)
    required_voters: int = 0
    quorum: float = 0.5  # Minimum participation
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    voting_deadline: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    
    # Result
    result: Optional[bool] = None
    result_reason: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def add_vote(self, vote: Vote) -> bool:
        """Add a vote to the decision."""
        if vote.voter_id not in self.eligible_voters:
            logger.warning(f"Voter {vote.voter_id} not eligible for decision {self.decision_id}")
            return False
        
        if vote.voter_id in self.votes:
            logger.warning(f"Voter {vote.voter_id} already voted on {self.decision_id}")
            return False
        
        self.votes[vote.voter_id] = vote
        return True
    
    def get_vote_counts(self) -> Dict[VoteType, float]:
        """Get weighted vote counts."""
        counts = {VoteType.APPROVE: 0.0, VoteType.REJECT: 0.0, VoteType.ABSTAIN: 0.0}
        for vote in self.votes.values():
            counts[vote.vote_type] += vote.weight
        return counts
    
    def get_participation(self) -> float:
        """Get participation rate."""
        if not self.eligible_voters:
            return 0.0
        return len(self.votes) / len(self.eligible_voters)
    
    def is_quorum_met(self) -> bool:
        """Check if quorum is met."""
        return self.get_participation() >= self.quorum
    
    def is_expired(self) -> bool:
        """Check if voting deadline has passed."""
        if self.voting_deadline is None:
            return False
        return datetime.utcnow() > self.voting_deadline
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "topic": self.topic,
            "description": self.description,
            "proposer_id": self.proposer_id,
            "status": self.status.value,
            "algorithm": self.algorithm.value,
            "votes": {k: v.to_dict() for k, v in self.votes.items()},
            "eligible_voters": list(self.eligible_voters),
            "quorum": self.quorum,
            "participation": self.get_participation(),
            "created_at": self.created_at.isoformat(),
            "voting_deadline": self.voting_deadline.isoformat() if self.voting_deadline else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "result": self.result,
            "result_reason": self.result_reason,
        }


@dataclass
class ConsensusResult:
    """Result of a consensus process."""
    decision_id: str
    approved: bool
    algorithm: ConsensusAlgorithm
    vote_counts: Dict[VoteType, float]
    participation: float
    quorum_met: bool
    reason: str
    decided_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "approved": self.approved,
            "algorithm": self.algorithm.value,
            "vote_counts": {k.value: v for k, v in self.vote_counts.items()},
            "participation": self.participation,
            "quorum_met": self.quorum_met,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat(),
        }


class ConsensusEngine:
    """
    Engine for distributed decision making.
    
    Supports multiple consensus algorithms and provides
    a unified interface for swarm decisions.
    """
    
    def __init__(
        self,
        default_algorithm: ConsensusAlgorithm = ConsensusAlgorithm.SIMPLE_MAJORITY,
        default_quorum: float = 0.5,
        default_timeout_seconds: int = 300,
    ):
        self.default_algorithm = default_algorithm
        self.default_quorum = default_quorum
        self.default_timeout_seconds = default_timeout_seconds
        
        # Active decisions
        self._decisions: Dict[str, Decision] = {}
        
        # Voter weights (for weighted voting)
        self._voter_weights: Dict[str, float] = {}
        
        # Decision callbacks
        self._on_decision_complete: Optional[Callable[[Decision], None]] = None
        
        # Background task for timeout checking
        self._timeout_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the consensus engine."""
        self._timeout_task = asyncio.create_task(self._check_timeouts())
        logger.info("Consensus engine started")
    
    async def stop(self) -> None:
        """Stop the consensus engine."""
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
        logger.info("Consensus engine stopped")
    
    def set_voter_weight(self, voter_id: str, weight: float) -> None:
        """Set the weight for a voter (for weighted voting)."""
        self._voter_weights[voter_id] = weight
    
    def set_decision_callback(self, callback: Callable[[Decision], None]) -> None:
        """Set callback for when decisions complete."""
        self._on_decision_complete = callback
    
    def create_decision(
        self,
        topic: str,
        description: str,
        proposal: Any,
        proposer_id: str,
        eligible_voters: Set[str],
        algorithm: Optional[ConsensusAlgorithm] = None,
        quorum: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Create a new decision."""
        decision = Decision(
            topic=topic,
            description=description,
            proposal=proposal,
            proposer_id=proposer_id,
            eligible_voters=eligible_voters,
            algorithm=algorithm or self.default_algorithm,
            quorum=quorum or self.default_quorum,
            voting_deadline=datetime.utcnow() + timedelta(
                seconds=timeout_seconds or self.default_timeout_seconds
            ),
            metadata=metadata or {},
        )
        
        self._decisions[decision.decision_id] = decision
        logger.info(f"Created decision {decision.decision_id}: {topic}")
        return decision
    
    def cast_vote(
        self,
        decision_id: str,
        voter_id: str,
        vote_type: VoteType,
        reason: Optional[str] = None,
    ) -> bool:
        """Cast a vote on a decision."""
        decision = self._decisions.get(decision_id)
        if not decision:
            logger.warning(f"Decision {decision_id} not found")
            return False
        
        if decision.status != DecisionStatus.PENDING:
            logger.warning(f"Decision {decision_id} is not pending")
            return False
        
        if decision.is_expired():
            logger.warning(f"Decision {decision_id} has expired")
            return False
        
        # Get voter weight
        weight = self._voter_weights.get(voter_id, 1.0)
        
        vote = Vote(
            voter_id=voter_id,
            vote_type=vote_type,
            weight=weight,
            reason=reason,
        )
        
        if decision.add_vote(vote):
            logger.info(f"Vote cast on {decision_id} by {voter_id}: {vote_type.value}")
            
            # Check if we can finalize
            if self._can_finalize(decision):
                self._finalize_decision(decision)
            
            return True
        
        return False
    
    def _can_finalize(self, decision: Decision) -> bool:
        """Check if a decision can be finalized."""
        if decision.is_expired():
            return True
        
        # Check if all votes are in
        if len(decision.votes) >= len(decision.eligible_voters):
            return True
        
        # For some algorithms, we can finalize early
        if decision.algorithm == ConsensusAlgorithm.UNANIMOUS:
            # Can reject early if any reject vote
            counts = decision.get_vote_counts()
            if counts[VoteType.REJECT] > 0:
                return True
        
        return False
    
    def _finalize_decision(self, decision: Decision) -> ConsensusResult:
        """Finalize a decision using the appropriate algorithm."""
        result = self._evaluate_consensus(decision)
        
        decision.result = result.approved
        decision.result_reason = result.reason
        decision.decided_at = datetime.utcnow()
        
        if result.approved:
            decision.status = DecisionStatus.ACCEPTED
        elif decision.is_expired() and not result.quorum_met:
            decision.status = DecisionStatus.TIMEOUT
        else:
            decision.status = DecisionStatus.REJECTED
        
        logger.info(
            f"Decision {decision.decision_id} finalized: "
            f"{'APPROVED' if result.approved else 'REJECTED'}"
        )
        
        # Callback
        if self._on_decision_complete:
            self._on_decision_complete(decision)
        
        return result
    
    def _evaluate_consensus(self, decision: Decision) -> ConsensusResult:
        """Evaluate consensus based on algorithm."""
        counts = decision.get_vote_counts()
        participation = decision.get_participation()
        quorum_met = decision.is_quorum_met()
        
        if decision.algorithm == ConsensusAlgorithm.SIMPLE_MAJORITY:
            return self._evaluate_simple_majority(decision, counts, quorum_met)
        elif decision.algorithm == ConsensusAlgorithm.SUPERMAJORITY:
            return self._evaluate_supermajority(decision, counts, quorum_met)
        elif decision.algorithm == ConsensusAlgorithm.UNANIMOUS:
            return self._evaluate_unanimous(decision, counts, quorum_met)
        elif decision.algorithm == ConsensusAlgorithm.WEIGHTED:
            return self._evaluate_weighted(decision, counts, quorum_met)
        else:
            return self._evaluate_simple_majority(decision, counts, quorum_met)
    
    def _evaluate_simple_majority(
        self,
        decision: Decision,
        counts: Dict[VoteType, float],
        quorum_met: bool,
    ) -> ConsensusResult:
        """Evaluate simple majority (>50% of non-abstain votes)."""
        total = counts[VoteType.APPROVE] + counts[VoteType.REJECT]
        
        if not quorum_met:
            return ConsensusResult(
                decision_id=decision.decision_id,
                approved=False,
                algorithm=decision.algorithm,
                vote_counts=counts,
                participation=decision.get_participation(),
                quorum_met=False,
                reason="Quorum not met",
            )
        
        if total == 0:
            return ConsensusResult(
                decision_id=decision.decision_id,
                approved=False,
                algorithm=decision.algorithm,
                vote_counts=counts,
                participation=decision.get_participation(),
                quorum_met=quorum_met,
                reason="No votes cast",
            )
        
        approved = counts[VoteType.APPROVE] > counts[VoteType.REJECT]
        
        return ConsensusResult(
            decision_id=decision.decision_id,
            approved=approved,
            algorithm=decision.algorithm,
            vote_counts=counts,
            participation=decision.get_participation(),
            quorum_met=quorum_met,
            reason=f"Simple majority: {counts[VoteType.APPROVE]:.1f} vs {counts[VoteType.REJECT]:.1f}",
        )
    
    def _evaluate_supermajority(
        self,
        decision: Decision,
        counts: Dict[VoteType, float],
        quorum_met: bool,
    ) -> ConsensusResult:
        """Evaluate supermajority (>66% of non-abstain votes)."""
        total = counts[VoteType.APPROVE] + counts[VoteType.REJECT]
        
        if not quorum_met:
            return ConsensusResult(
                decision_id=decision.decision_id,
                approved=False,
                algorithm=decision.algorithm,
                vote_counts=counts,
                participation=decision.get_participation(),
                quorum_met=False,
                reason="Quorum not met",
            )
        
        if total == 0:
            return ConsensusResult(
                decision_id=decision.decision_id,
                approved=False,
                algorithm=decision.algorithm,
                vote_counts=counts,
                participation=decision.get_participation(),
                quorum_met=quorum_met,
                reason="No votes cast",
            )
        
        threshold = total * 0.66
        approved = counts[VoteType.APPROVE] > threshold
        
        return ConsensusResult(
            decision_id=decision.decision_id,
            approved=approved,
            algorithm=decision.algorithm,
            vote_counts=counts,
            participation=decision.get_participation(),
            quorum_met=quorum_met,
            reason=f"Supermajority: {counts[VoteType.APPROVE]:.1f} vs threshold {threshold:.1f}",
        )
    
    def _evaluate_unanimous(
        self,
        decision: Decision,
        counts: Dict[VoteType, float],
        quorum_met: bool,
    ) -> ConsensusResult:
        """Evaluate unanimous consent (100% approve)."""
        if not quorum_met:
            return ConsensusResult(
                decision_id=decision.decision_id,
                approved=False,
                algorithm=decision.algorithm,
                vote_counts=counts,
                participation=decision.get_participation(),
                quorum_met=False,
                reason="Quorum not met",
            )
        
        approved = (
            counts[VoteType.REJECT] == 0 and
            counts[VoteType.APPROVE] > 0
        )
        
        return ConsensusResult(
            decision_id=decision.decision_id,
            approved=approved,
            algorithm=decision.algorithm,
            vote_counts=counts,
            participation=decision.get_participation(),
            quorum_met=quorum_met,
            reason=f"Unanimous: {counts[VoteType.APPROVE]:.1f} approve, {counts[VoteType.REJECT]:.1f} reject",
        )
    
    def _evaluate_weighted(
        self,
        decision: Decision,
        counts: Dict[VoteType, float],
        quorum_met: bool,
    ) -> ConsensusResult:
        """Evaluate weighted voting."""
        # Counts already include weights
        return self._evaluate_simple_majority(decision, counts, quorum_met)
    
    async def _check_timeouts(self) -> None:
        """Background task to check for decision timeouts."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                for decision in list(self._decisions.values()):
                    if decision.status == DecisionStatus.PENDING and decision.is_expired():
                        self._finalize_decision(decision)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error checking timeouts: {e}")
    
    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)
    
    def get_active_decisions(self) -> List[Decision]:
        """Get all active (pending) decisions."""
        return [
            d for d in self._decisions.values()
            if d.status == DecisionStatus.PENDING
        ]
    
    def get_decision_history(self, limit: int = 100) -> List[Decision]:
        """Get decision history."""
        decisions = sorted(
            self._decisions.values(),
            key=lambda d: d.created_at,
            reverse=True
        )
        return decisions[:limit]


@dataclass
class RaftState:
    """State for Raft consensus."""
    current_term: int = 0
    voted_for: Optional[str] = None
    commit_index: int = 0
    last_applied: int = 0
    leader_id: Optional[str] = None
    
    # Log
    log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Leader state
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)


class RaftNode:
    """
    Raft consensus node for leader-based decisions.
    
    Simplified Raft implementation for swarm coordination.
    """
    
    class State(str, Enum):
        FOLLOWER = "follower"
        CANDIDATE = "candidate"
        LEADER = "leader"
    
    def __init__(
        self,
        node_id: str,
        peers: Set[str],
        election_timeout_ms: int = 3000,
        heartbeat_interval_ms: int = 1000,
    ):
        self.node_id = node_id
        self.peers = peers
        self.election_timeout_ms = election_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        
        self.state = self.State.FOLLOWER
        self.raft_state = RaftState()
        
        # Timers
        self._last_heartbeat = time.time()
        self._last_heartbeat_sent = 0.0
        self._election_deadline = self._new_election_deadline()
        
        # Callbacks
        self._on_leader_elected: Optional[Callable[[str], None]] = None
        self._on_entry_committed: Optional[Callable[[Dict[str, Any]], None]] = None
        self._send_heartbeat: Optional[Callable[[str, Dict], None]] = None
        self._send_message: Optional[Callable[[str, Dict], None]] = None

        # Vote tracking for elections
        self._votes_received: Set[str] = set()
    
    def _new_election_deadline(self) -> float:
        """Generate a new random election deadline."""
        timeout = random.randint(
            self.election_timeout_ms,
            self.election_timeout_ms * 2
        ) / 1000.0
        return time.time() + timeout
    
    def set_callbacks(
        self,
        on_leader_elected: Optional[Callable[[str], None]] = None,
        on_entry_committed: Optional[Callable[[Dict[str, Any]], None]] = None,
        send_heartbeat: Optional[Callable[[str, Dict], None]] = None,
        send_message: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        """Set callbacks for Raft events."""
        self._on_leader_elected = on_leader_elected
        self._on_entry_committed = on_entry_committed
        self._send_heartbeat = send_heartbeat
        self._send_message = send_message

    def receive_message(self, message: Dict[str, Any]) -> None:
        """Route an incoming message to the correct handler."""
        msg_type = message.get("type", "")
        if msg_type == "request_vote":
            granted = self.handle_vote_request(
                candidate_id=message["candidate_id"],
                term=message["term"],
                last_log_index=message.get("last_log_index", 0),
                last_log_term=message.get("last_log_term", 0),
            )
            if self._send_message:
                self._send_message(message["candidate_id"], {
                    "type": "vote_response",
                    "voter_id": self.node_id,
                    "term": self.raft_state.current_term,
                    "vote_granted": granted,
                })
        elif msg_type == "vote_response":
            self.handle_vote_response(
                voter_id=message["voter_id"],
                term=message["term"],
                vote_granted=message.get("vote_granted", False),
            )
        elif msg_type == "append_entries":
            self.handle_heartbeat(
                leader_id=message["leader_id"],
                term=message["term"],
                prev_log_index=message.get("prev_log_index", 0),
                prev_log_term=message.get("prev_log_term", 0),
                entries=message.get("entries", []),
                commit_index=message.get("commit_index", 0),
            )
        else:
            logger.warning(f"RaftNode {self.node_id} received unknown message type: {msg_type}")

    def start_election(self) -> None:
        """Start an election."""
        self.state = self.State.CANDIDATE
        self.raft_state.current_term += 1
        self.raft_state.voted_for = self.node_id

        # Reset vote tracking and add self-vote
        self._votes_received = {self.node_id}

        logger.info(f"Node {self.node_id} starting election for term {self.raft_state.current_term}")

        # Broadcast vote requests to all peers
        if self._send_message:
            vote_request = {
                "type": "request_vote",
                "candidate_id": self.node_id,
                "term": self.raft_state.current_term,
                "last_log_index": len(self.raft_state.log) - 1 if self.raft_state.log else 0,
                "last_log_term": self.raft_state.log[-1].get("term", 0) if self.raft_state.log else 0,
            }
            for peer in self.peers:
                self._send_message(peer, vote_request)
    
    def handle_vote_request(
        self,
        candidate_id: str,
        term: int,
        last_log_index: int,
        last_log_term: int,
    ) -> bool:
        """Handle a vote request from a candidate."""
        if term < self.raft_state.current_term:
            return False
        
        if term > self.raft_state.current_term:
            self.raft_state.current_term = term
            self.raft_state.voted_for = None
            self.state = self.State.FOLLOWER
        
        if self.raft_state.voted_for is None or self.raft_state.voted_for == candidate_id:
            # Check if candidate's log is at least as up-to-date
            if len(self.raft_state.log) > 0:
                my_last_term = self.raft_state.log[-1].get("term", 0)
                if last_log_term < my_last_term:
                    return False
                if last_log_term == my_last_term and last_log_index < len(self.raft_state.log) - 1:
                    return False
            
            self.raft_state.voted_for = candidate_id
            self._last_heartbeat = time.time()
            return True
        
        return False
    
    def handle_vote_response(
        self,
        voter_id: str,
        term: int,
        vote_granted: bool,
    ) -> bool:
        """Handle a vote response."""
        if self.state != self.State.CANDIDATE:
            return False
        
        if term > self.raft_state.current_term:
            self.raft_state.current_term = term
            self.state = self.State.FOLLOWER
            return False
        
        if vote_granted:
            # Track votes from peers
            self._votes_received.add(voter_id)
            
            # Check if we have majority
            majority = (len(self.peers) + 1) // 2 + 1
            if len(self._votes_received) >= majority:
                self.become_leader()
                return True
        
        return False
    
    def become_leader(self) -> None:
        """Become the leader."""
        self.state = self.State.LEADER
        self.raft_state.leader_id = self.node_id
        
        # Initialize leader state
        for peer in self.peers:
            self.raft_state.next_index[peer] = len(self.raft_state.log)
            self.raft_state.match_index[peer] = 0
        
        logger.info(f"Node {self.node_id} became leader for term {self.raft_state.current_term}")
        
        if self._on_leader_elected:
            self._on_leader_elected(self.node_id)
    
    def handle_heartbeat(
        self,
        leader_id: str,
        term: int,
        prev_log_index: int,
        prev_log_term: int,
        entries: List[Dict[str, Any]],
        commit_index: int,
    ) -> bool:
        """Handle a heartbeat from the leader."""
        if term < self.raft_state.current_term:
            return False
        
        self._last_heartbeat = time.time()
        self._election_deadline = self._new_election_deadline()
        
        if term > self.raft_state.current_term:
            self.raft_state.current_term = term
            self.raft_state.voted_for = None
        
        self.state = self.State.FOLLOWER
        self.raft_state.leader_id = leader_id
        
        # Append entries (simplified)
        for entry in entries:
            self.raft_state.log.append(entry)
        
        # Update commit index
        if commit_index > self.raft_state.commit_index:
            self.raft_state.commit_index = min(commit_index, len(self.raft_state.log) - 1)
            
            # Apply committed entries
            while self.raft_state.last_applied < self.raft_state.commit_index:
                self.raft_state.last_applied += 1
                entry = self.raft_state.log[self.raft_state.last_applied]
                if self._on_entry_committed:
                    self._on_entry_committed(entry)
        
        return True
    
    def propose(self, entry: Dict[str, Any]) -> bool:
        """Propose a new entry (leader only)."""
        if self.state != self.State.LEADER:
            return False
        
        entry["term"] = self.raft_state.current_term
        entry["index"] = len(self.raft_state.log)
        self.raft_state.log.append(entry)
        
        return True
    
    def _send_heartbeats_to_peers(self) -> None:
        """Send heartbeat (AppendEntries) to all peers."""
        if not self._send_heartbeat:
            logger.debug(f"Leader {self.node_id}: No heartbeat callback set, skipping")
            return
        
        for peer in self.peers:
            heartbeat_msg = {
                "type": "append_entries",
                "term": self.raft_state.current_term,
                "leader_id": self.node_id,
                "prev_log_index": len(self.raft_state.log) - 1 if self.raft_state.log else 0,
                "prev_log_term": self.raft_state.log[-1].get("term", 0) if self.raft_state.log else 0,
                "entries": [],
                "commit_index": self.raft_state.commit_index,
            }
            self._send_heartbeat(peer, heartbeat_msg)
        
        logger.debug(f"Leader {self.node_id}: Sent heartbeats to {len(self.peers)} peers")
    
    def tick(self) -> None:
        """Process a tick (should be called periodically)."""
        now = time.time()

        if self.state == self.State.LEADER:
            # Send heartbeats at regular intervals
            heartbeat_interval_sec = self.heartbeat_interval_ms / 1000.0
            if now - self._last_heartbeat_sent >= heartbeat_interval_sec:
                self._send_heartbeats_to_peers()
                self._last_heartbeat_sent = now
        elif now > self._election_deadline:
            # Election timeout
            self.start_election()
            self._election_deadline = self._new_election_deadline()


# Export
__all__ = [
    "DecisionStatus",
    "VoteType",
    "ConsensusAlgorithm",
    "Vote",
    "Decision",
    "ConsensusResult",
    "ConsensusEngine",
    "RaftState",
    "RaftNode",
]
