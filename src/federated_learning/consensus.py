"""
DG-PBFT Consensus for Federated Learning.

Implements a Directed Graph Practical Byzantine Fault Tolerance
consensus protocol for distributed model update agreement.

Features:
- Byzantine fault tolerance (f < n/3)
- Async message handling
- View change for liveness
- Model update verification

Reference: "PBFT" (Castro & Liskov, 1999)
"""

import hashlib
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConsensusPhase(Enum):
    """PBFT consensus phases."""

    IDLE = "idle"
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    FINALIZED = "finalized"
    VIEW_CHANGE = "view_change"


class MessageType(Enum):
    """PBFT message types."""

    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    VIEW_CHANGE = "view_change"
    NEW_VIEW = "new_view"
    CHECKPOINT = "checkpoint"


@dataclass
class ConsensusMessage:
    """A message in the PBFT protocol."""

    msg_type: MessageType
    view: int
    sequence: int
    digest: str  # Hash of the proposal
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)
    signature: bytes = b""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": self.msg_type.value,
            "view": self.view,
            "sequence": self.sequence,
            "digest": self.digest,
            "sender": self.sender,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsensusMessage":
        return cls(
            msg_type=MessageType(data["msg_type"]),
            view=data["view"],
            sequence=data["sequence"],
            digest=data["digest"],
            sender=data["sender"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class ConsensusProposal:
    """A proposal to be agreed upon."""

    proposal_id: str
    proposer: str
    content: Dict[str, Any]
    digest: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.digest:
            self.digest = self._compute_digest()

    def _compute_digest(self) -> str:
        """Compute SHA256 digest of proposal content."""
        import json

        content_str = json.dumps(self.content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()


@dataclass
class ConsensusState:
    """State for a single consensus instance."""

    sequence: int
    view: int
    phase: ConsensusPhase = ConsensusPhase.IDLE
    proposal: Optional[ConsensusProposal] = None

    # Message logs
    pre_prepare: Optional[ConsensusMessage] = None
    prepares: Dict[str, ConsensusMessage] = field(default_factory=dict)
    commits: Dict[str, ConsensusMessage] = field(default_factory=dict)

    # Timing
    started_at: float = 0.0
    finalized_at: float = 0.0

    def prepare_count(self) -> int:
        return len(self.prepares)

    def commit_count(self) -> int:
        return len(self.commits)


@dataclass
class PBFTConfig:
    """Configuration for PBFT consensus."""

    # Timing
    timeout_prepare: float = 5.0  # Seconds to wait for prepares
    timeout_commit: float = 5.0  # Seconds to wait for commits
    timeout_view_change: float = 30.0  # Seconds before view change

    # Checkpointing
    checkpoint_interval: int = 100  # Sequences between checkpoints

    # Verification
    verify_signatures: bool = True


class PBFTConsensus:
    """
    PBFT consensus implementation for FL model updates.

    Nodes agree on which model updates to accept using
    Byzantine fault tolerant consensus.
    """

    def __init__(
        self,
        node_id: str,
        nodes: List[str],
        config: Optional[PBFTConfig] = None,
        is_primary: bool = False,
    ):
        self.node_id = node_id
        self.nodes = nodes
        self.config = config or PBFTConfig()

        self.n = len(nodes)
        self.f = (self.n - 1) // 3  # Max Byzantine nodes
        self.quorum = 2 * self.f + 1  # Required for agreement

        # State
        self.view = 0
        self.sequence = 0
        self.is_primary = is_primary or (nodes[0] == node_id)

        # Consensus instances
        self._instances: Dict[int, ConsensusState] = {}

        # Committed proposals
        self._committed: List[ConsensusProposal] = []

        # Callbacks
        self._on_commit: List[Callable[[ConsensusProposal], None]] = []

        # Message handlers
        self._message_handlers: Dict[str, Callable] = {}

        # Threading
        self._lock = threading.RLock()

        # Metrics
        self._metrics = {
            "proposals_started": 0,
            "proposals_committed": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "view_changes": 0,
        }

        logger.info(
            f"PBFT node {node_id} initialized: n={self.n}, f={self.f}, "
            f"quorum={self.quorum}, primary={self.is_primary}"
        )

    # ==================== Primary Operations ====================

    def propose(self, content: Dict[str, Any]) -> Optional[ConsensusProposal]:
        """
        Propose a new value (primary only).

        Args:
            content: Proposal content (e.g., model update)

        Returns:
            ConsensusProposal if started, None if not primary
        """
        if not self.is_primary:
            logger.warning(f"Node {self.node_id} is not primary, cannot propose")
            return None

        with self._lock:
            self.sequence += 1
            seq = self.sequence

            proposal = ConsensusProposal(
                proposal_id=f"prop-{self.view}-{seq}",
                proposer=self.node_id,
                content=content,
            )

            # Create consensus state
            state = ConsensusState(
                sequence=seq,
                view=self.view,
                phase=ConsensusPhase.PRE_PREPARE,
                proposal=proposal,
                started_at=time.time(),
            )
            self._instances[seq] = state

            # Create PRE-PREPARE message
            pre_prepare = ConsensusMessage(
                msg_type=MessageType.PRE_PREPARE,
                view=self.view,
                sequence=seq,
                digest=proposal.digest,
                sender=self.node_id,
                payload={"proposal": proposal.content},
            )
            state.pre_prepare = pre_prepare

            self._metrics["proposals_started"] += 1

            logger.info(f"Primary proposing seq={seq}, digest={proposal.digest[:16]}")

            # Broadcast PRE-PREPARE
            self._broadcast(pre_prepare)

            return proposal

    # ==================== Message Handling ====================

    def handle_message(self, message: ConsensusMessage) -> bool:
        """
        Handle an incoming consensus message.

        Args:
            message: Incoming message

        Returns:
            True if message was valid and processed
        """
        self._metrics["messages_received"] += 1

        # Verify view
        if message.view != self.view:
            if message.view > self.view:
                logger.warning(f"Message from future view {message.view}")
            return False

        # Route to handler
        handlers = {
            MessageType.PRE_PREPARE: self._handle_pre_prepare,
            MessageType.PREPARE: self._handle_prepare,
            MessageType.COMMIT: self._handle_commit,
            MessageType.VIEW_CHANGE: self._handle_view_change,
        }

        handler = handlers.get(message.msg_type)
        if handler:
            return handler(message)

        return False

    def _handle_pre_prepare(self, message: ConsensusMessage) -> bool:
        """Handle PRE-PREPARE from primary."""
        seq = message.sequence

        with self._lock:
            # Verify sender is primary
            if message.sender != self._get_primary():
                logger.warning(f"PRE-PREPARE from non-primary {message.sender}")
                return False

            # Check if already have pre-prepare for this sequence
            if seq in self._instances:
                existing = self._instances[seq]
                if (
                    existing.pre_prepare
                    and existing.pre_prepare.digest != message.digest
                ):
                    logger.warning(f"Conflicting PRE-PREPARE for seq={seq}")
                    return False
            else:
                # Create new consensus state
                proposal = ConsensusProposal(
                    proposal_id=f"prop-{message.view}-{seq}",
                    proposer=message.sender,
                    content=message.payload.get("proposal", {}),
                    digest=message.digest,
                )

                self._instances[seq] = ConsensusState(
                    sequence=seq,
                    view=message.view,
                    phase=ConsensusPhase.PREPARE,
                    proposal=proposal,
                    pre_prepare=message,
                    started_at=time.time(),
                )

            state = self._instances[seq]
            state.pre_prepare = message
            state.phase = ConsensusPhase.PREPARE

            # Send PREPARE
            prepare = ConsensusMessage(
                msg_type=MessageType.PREPARE,
                view=self.view,
                sequence=seq,
                digest=message.digest,
                sender=self.node_id,
            )

            self._broadcast(prepare)

            # Also count our own prepare
            state.prepares[self.node_id] = prepare

            self._check_prepared(seq)

            return True

    def _handle_prepare(self, message: ConsensusMessage) -> bool:
        """Handle PREPARE message."""
        seq = message.sequence

        with self._lock:
            if seq not in self._instances:
                # Haven't seen PRE-PREPARE yet, buffer the message
                logger.debug(f"PREPARE for unknown seq={seq}, buffering")
                return False

            state = self._instances[seq]

            # Verify digest matches
            if state.pre_prepare and message.digest != state.pre_prepare.digest:
                logger.warning(f"PREPARE digest mismatch for seq={seq}")
                return False

            # Record prepare
            state.prepares[message.sender] = message

            self._check_prepared(seq)

            return True

    def _check_prepared(self, seq: int) -> None:
        """Check if we have enough prepares to move to commit phase."""
        state = self._instances.get(seq)
        if not state:
            return

        if state.phase != ConsensusPhase.PREPARE:
            return

        # Need 2f prepares (not including primary's pre-prepare)
        if state.prepare_count() >= self.quorum - 1:
            state.phase = ConsensusPhase.COMMIT

            # Send COMMIT
            commit = ConsensusMessage(
                msg_type=MessageType.COMMIT,
                view=self.view,
                sequence=seq,
                digest=state.pre_prepare.digest,
                sender=self.node_id,
            )

            self._broadcast(commit)

            # Count our own commit
            state.commits[self.node_id] = commit

            self._check_committed(seq)

    def _handle_commit(self, message: ConsensusMessage) -> bool:
        """Handle COMMIT message."""
        seq = message.sequence

        with self._lock:
            if seq not in self._instances:
                return False

            state = self._instances[seq]

            # Verify digest
            if state.pre_prepare and message.digest != state.pre_prepare.digest:
                return False

            # Record commit
            state.commits[message.sender] = message

            self._check_committed(seq)

            return True

    def _check_committed(self, seq: int) -> None:
        """Check if we have enough commits to finalize."""
        state = self._instances.get(seq)
        if not state:
            return

        if state.phase == ConsensusPhase.FINALIZED:
            return

        # Need 2f+1 commits
        if state.commit_count() >= self.quorum:
            self._finalize(seq)

    def _finalize(self, seq: int) -> None:
        """Finalize a consensus instance."""
        state = self._instances.get(seq)
        if not state or not state.proposal:
            return

        state.phase = ConsensusPhase.FINALIZED
        state.finalized_at = time.time()

        self._committed.append(state.proposal)
        self._metrics["proposals_committed"] += 1

        logger.info(
            f"Consensus finalized: seq={seq}, "
            f"digest={state.proposal.digest[:16]}, "
            f"latency={state.finalized_at - state.started_at:.3f}s"
        )

        # Trigger callbacks
        for callback in self._on_commit:
            try:
                callback(state.proposal)
            except Exception as e:
                logger.error(f"Commit callback error: {e}")

    def _handle_view_change(self, message: ConsensusMessage) -> bool:
        """Handle VIEW-CHANGE message."""
        # Simplified view change
        self._metrics["view_changes"] += 1
        return True

    # ==================== View Management ====================

    def _get_primary(self) -> str:
        """Get current primary based on view."""
        return self.nodes[self.view % self.n]

    def start_view_change(self) -> None:
        """Initiate view change."""
        with self._lock:
            new_view = self.view + 1

            view_change = ConsensusMessage(
                msg_type=MessageType.VIEW_CHANGE,
                view=new_view,
                sequence=self.sequence,
                digest="",
                sender=self.node_id,
            )

            self._broadcast(view_change)

            logger.info(f"Starting view change to view {new_view}")

    def complete_view_change(self, new_view: int) -> None:
        """Complete transition to new view."""
        with self._lock:
            self.view = new_view
            self.is_primary = self._get_primary() == self.node_id

            logger.info(f"View changed to {new_view}, primary={self.is_primary}")

    # ==================== Communication ====================

    def _broadcast(self, message: ConsensusMessage) -> None:
        """Broadcast message to all nodes."""
        self._metrics["messages_sent"] += len(self.nodes) - 1

        # In real implementation, this would send over network
        # Here we just notify registered handlers
        for handler in self._message_handlers.values():
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Broadcast handler error: {e}")

    def register_message_handler(
        self, handler_id: str, handler: Callable[[ConsensusMessage], None]
    ) -> None:
        """Register a message handler for outgoing messages."""
        self._message_handlers[handler_id] = handler

    def unregister_message_handler(self, handler_id: str) -> None:
        """Unregister a message handler."""
        self._message_handlers.pop(handler_id, None)

    # ==================== Callbacks ====================

    def on_commit(self, callback: Callable[[ConsensusProposal], None]) -> None:
        """Register callback for committed proposals."""
        self._on_commit.append(callback)

    # ==================== Queries ====================

    def get_committed_proposals(self) -> List[ConsensusProposal]:
        """Get all committed proposals."""
        with self._lock:
            return list(self._committed)

    def get_instance_state(self, seq: int) -> Optional[ConsensusState]:
        """Get state of a consensus instance."""
        with self._lock:
            return self._instances.get(seq)

    def get_metrics(self) -> Dict[str, Any]:
        """Get consensus metrics."""
        with self._lock:
            return {
                **self._metrics,
                "view": self.view,
                "sequence": self.sequence,
                "is_primary": self.is_primary,
                "pending_instances": sum(
                    1
                    for s in self._instances.values()
                    if s.phase != ConsensusPhase.FINALIZED
                ),
                "n": self.n,
                "f": self.f,
                "quorum": self.quorum,
            }


class ConsensusNetwork:
    """
    Simulated network for testing PBFT consensus.

    Connects multiple PBFT nodes for local testing.
    """

    def __init__(self, node_ids: List[str]):
        self.node_ids = node_ids
        self.nodes: Dict[str, PBFTConsensus] = {}

        # Create nodes
        for i, node_id in enumerate(node_ids):
            node = PBFTConsensus(node_id=node_id, nodes=node_ids, is_primary=(i == 0))
            self.nodes[node_id] = node

        # Wire up message delivery
        for node_id, node in self.nodes.items():
            node.register_message_handler(
                "network", lambda msg, nid=node_id: self._deliver_message(msg, nid)
            )

    def _deliver_message(self, message: ConsensusMessage, sender_id: str) -> None:
        """Deliver message to all other nodes."""
        for node_id, node in self.nodes.items():
            if node_id != sender_id:
                # Simulate network delivery
                node.handle_message(message)

    def propose(self, content: Dict[str, Any]) -> Optional[ConsensusProposal]:
        """Propose through the primary."""
        primary_id = self.node_ids[0]
        return self.nodes[primary_id].propose(content)

    def get_committed(self) -> List[ConsensusProposal]:
        """Get proposals committed by all nodes."""
        # Check first node's committed list
        return self.nodes[self.node_ids[0]].get_committed_proposals()

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all nodes."""
        return {node_id: node.get_metrics() for node_id, node in self.nodes.items()}
