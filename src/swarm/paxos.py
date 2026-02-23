"""
Paxos Consensus Algorithm Implementation

Provides complete implementation of the Paxos consensus algorithm
for distributed decision making in the swarm.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import random

logger = logging.getLogger(__name__)


class PaxosPhase(str, Enum):
    """Phases in Paxos algorithm."""
    IDLE = "idle"
    PREPARE = "prepare"
    PROMISE = "promise"
    ACCEPT = "accept"
    COMMITTED = "committed"


@dataclass
class ProposalNumber:
    """Unique proposal number for Paxos."""
    round: int
    proposer_id: str
    
    def __lt__(self, other: "ProposalNumber") -> bool:
        if self.round != other.round:
            return self.round < other.round
        return self.proposer_id < other.proposer_id
    
    def __le__(self, other: "ProposalNumber") -> bool:
        return self == other or self < other
    
    def __gt__(self, other: "ProposalNumber") -> bool:
        return not self <= other
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProposalNumber):
            return False
        return self.round == other.round and self.proposer_id == other.proposer_id
    
    def __hash__(self) -> int:
        return hash((self.round, self.proposer_id))
    
    def to_dict(self) -> Dict[str, Any]:
        return {"round": self.round, "proposer_id": self.proposer_id}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProposalNumber":
        return cls(round=data["round"], proposer_id=data["proposer_id"])


@dataclass
class PaxosMessage:
    """Base message for Paxos protocol."""
    msg_type: str
    proposal_number: ProposalNumber
    instance_id: str
    sender_id: str
    value: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.msg_type,
            "proposal_number": self.proposal_number.to_dict(),
            "instance_id": self.instance_id,
            "sender_id": self.sender_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PaxosInstance:
    """A single Paxos instance for one consensus decision."""
    instance_id: str
    phase: PaxosPhase = PaxosPhase.IDLE
    
    # Promised proposal (highest seen)
    promised_number: Optional[ProposalNumber] = None
    
    # Accepted proposal
    accepted_number: Optional[ProposalNumber] = None
    accepted_value: Optional[Any] = None
    
    # Committed value
    committed_value: Optional[Any] = None
    committed_number: Optional[ProposalNumber] = None
    
    # Tracking
    promises_received: Set[str] = field(default_factory=set)
    accepts_received: Set[str] = field(default_factory=set)
    committed_at: Optional[datetime] = None
    
    # Track accepted values from promises (for proposer)
    # Maps sender_id -> (proposal_number, accepted_value)
    promise_values: Dict[str, Tuple[Optional[ProposalNumber], Optional[Any]]] = field(default_factory=dict)
    
    # Async events for efficient waiting (replaces busy-waiting)
    # These are set when quorum is reached for each phase
    _promises_event: Optional[asyncio.Event] = field(default=None, repr=False)
    _accepts_event: Optional[asyncio.Event] = field(default=None, repr=False)
    
    def get_promises_event(self) -> asyncio.Event:
        """Get or create the promises event."""
        if self._promises_event is None:
            self._promises_event = asyncio.Event()
        return self._promises_event
    
    def get_accepts_event(self) -> asyncio.Event:
        """Get or create the accepts event."""
        if self._accepts_event is None:
            self._accepts_event = asyncio.Event()
        return self._accepts_event


class PaxosNode:
    """
    Paxos node that can act as proposer, acceptor, and learner.
    
    Implements the full Paxos protocol:
    - Phase 1: Prepare/Promise
    - Phase 2: Accept/Accepted
    - Commit: Notify learners
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Set[str],
        quorum_size: Optional[int] = None,
    ):
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = peers | {node_id}
        self.quorum_size = quorum_size or (len(self.all_nodes) // 2 + 1)
        
        # Instance management
        self._instances: Dict[str, PaxosInstance] = {}
        self._current_instance = 0
        
        # Proposal number counter
        self._proposal_round = 0
        
        # Callbacks
        self._on_value_committed: Optional[Callable[[str, Any], None]] = None
        self._send_message: Optional[Callable[[str, Dict], None]] = None
        
        # Message handlers
        self._handlers = {
            "prepare": self._handle_prepare,
            "promise": self._handle_promise,
            "accept": self._handle_accept,
            "accepted": self._handle_accepted,
            "commit": self._handle_commit,
        }
    
    def set_callbacks(
        self,
        on_value_committed: Optional[Callable[[str, Any], None]] = None,
        send_message: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self._on_value_committed = on_value_committed
        self._send_message = send_message
    
    def _get_or_create_instance(self, instance_id: str) -> PaxosInstance:
        if instance_id not in self._instances:
            self._instances[instance_id] = PaxosInstance(instance_id=instance_id)
        return self._instances[instance_id]
    
    def _generate_proposal_number(self) -> ProposalNumber:
        """Generate a unique proposal number."""
        num = ProposalNumber(
            round=self._proposal_round,
            proposer_id=self.node_id,
        )
        self._proposal_round += 1
        return num
    
    def _send_to(self, target_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific node."""
        if self._send_message:
            self._send_message(target_id, message)
        else:
            logger.debug(f"Would send to {target_id}: {message['type']}")
    
    def _send_to_all(self, message: Dict[str, Any]) -> None:
        """Send message to all peers."""
        for peer in self.peers:
            self._send_to(peer, message)
    
    # ==================== Proposer Role ====================
    
    async def propose(self, value: Any, instance_id: Optional[str] = None) -> Tuple[bool, Any]:
        """
        Propose a value for consensus.
        
        Returns (success, committed_value).
        """
        if instance_id is None:
            instance_id = f"instance-{self._current_instance}"
            self._current_instance += 1
        
        instance = self._get_or_create_instance(instance_id)
        
        if instance.phase == PaxosPhase.COMMITTED:
            return (True, instance.committed_value)
        
        # Generate proposal number
        proposal_number = self._generate_proposal_number()
        
        instance.phase = PaxosPhase.PREPARE
        instance.promised_number = proposal_number
        
        logger.info(f"Proposer {self.node_id}: Starting proposal {proposal_number.round} for {instance_id}")
        
        # Phase 1: Send Prepare
        prepare_msg = PaxosMessage(
            msg_type="prepare",
            proposal_number=proposal_number,
            instance_id=instance_id,
            sender_id=self.node_id,
        )
        self._send_to_all(prepare_msg.to_dict())
        
        # Wait for promises
        try:
            await asyncio.wait_for(
                self._wait_for_quorum(instance, "promises"),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Proposer {self.node_id}: Timeout waiting for promises")
            instance.phase = PaxosPhase.IDLE
            return (False, None)
        
        # Phase 2: Send Accept
        instance.phase = PaxosPhase.ACCEPT
        
        # Use the value from highest promise or our proposed value
        accept_value = self._get_value_from_promises(instance) or value
        
        accept_msg = PaxosMessage(
            msg_type="accept",
            proposal_number=proposal_number,
            instance_id=instance_id,
            sender_id=self.node_id,
            value=accept_value,
        )
        self._send_to_all(accept_msg.to_dict())
        
        # Wait for accepts
        try:
            await asyncio.wait_for(
                self._wait_for_quorum(instance, "accepts"),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Proposer {self.node_id}: Timeout waiting for accepts")
            instance.phase = PaxosPhase.IDLE
            return (False, None)
        
        # Commit
        instance.phase = PaxosPhase.COMMITTED
        instance.committed_value = accept_value
        instance.committed_number = proposal_number
        instance.committed_at = datetime.utcnow()
        
        commit_msg = PaxosMessage(
            msg_type="commit",
            proposal_number=proposal_number,
            instance_id=instance_id,
            sender_id=self.node_id,
            value=accept_value,
        )
        self._send_to_all(commit_msg.to_dict())
        
        logger.info(f"Proposer {self.node_id}: Value committed for {instance_id}")
        
        if self._on_value_committed:
            self._on_value_committed(instance_id, accept_value)
        
        return (True, accept_value)
    
    async def _wait_for_quorum(self, instance: PaxosInstance, msg_type: str) -> None:
        """
        Wait for quorum of messages using asyncio.Event.
        
        This replaces the previous busy-waiting implementation that polled
        every 10ms. Now we use event-based notification for efficiency.
        """
        if msg_type == "promises":
            # Check if quorum already reached
            if len(instance.promises_received) >= self.quorum_size:
                return
            # Wait for event to be set when quorum is reached
            event = instance.get_promises_event()
            await event.wait()
        else:
            # Check if quorum already reached
            if len(instance.accepts_received) >= self.quorum_size:
                return
            # Wait for event to be set when quorum is reached
            event = instance.get_accepts_event()
            await event.wait()
    
    def _get_value_from_promises(self, instance: PaxosInstance) -> Optional[Any]:
        """
        Get the value to propose from received promises.
        
        According to Paxos, if any acceptor has already accepted a value,
        the proposer must use the value from the highest-numbered accepted proposal.
        """
        if not instance.promise_values:
            return None
        
        # Find the highest-numbered accepted proposal from all promises
        highest_proposal: Optional[ProposalNumber] = None
        highest_value: Optional[Any] = None
        
        for sender_id, (proposal_num, accepted_value) in instance.promise_values.items():
            if proposal_num is not None and accepted_value is not None:
                if highest_proposal is None or proposal_num > highest_proposal:
                    highest_proposal = proposal_num
                    highest_value = accepted_value
        
        return highest_value
    
    # ==================== Acceptor Role ====================
    
    def _handle_prepare(self, message: Dict[str, Any]) -> None:
        """Handle a Prepare message (Phase 1a)."""
        proposal_number = ProposalNumber.from_dict(message["proposal_number"])
        instance_id = message["instance_id"]
        sender_id = message["sender_id"]
        
        instance = self._get_or_create_instance(instance_id)
        
        # Check if we've already promised to a higher proposal
        if instance.promised_number and instance.promised_number >= proposal_number:
            logger.debug(f"Acceptor {self.node_id}: Rejecting prepare, already promised to higher")
            return
        
        # Promise not to accept proposals numbered less than this
        instance.promised_number = proposal_number
        
        # Send Promise
        promise_msg = PaxosMessage(
            msg_type="promise",
            proposal_number=proposal_number,
            instance_id=instance_id,
            sender_id=self.node_id,
            value=instance.accepted_value,  # Include previously accepted value
        )
        self._send_to(sender_id, promise_msg.to_dict())
        logger.debug(f"Acceptor {self.node_id}: Sent promise for {instance_id}")
    
    def _handle_accept(self, message: Dict[str, Any]) -> None:
        """Handle an Accept message (Phase 2a)."""
        proposal_number = ProposalNumber.from_dict(message["proposal_number"])
        instance_id = message["instance_id"]
        sender_id = message["sender_id"]
        value = message.get("value")
        
        instance = self._get_or_create_instance(instance_id)
        
        # Check if we've promised to a higher proposal
        if instance.promised_number and instance.promised_number > proposal_number:
            logger.debug(f"Acceptor {self.node_id}: Rejecting accept, promised to higher")
            return
        
        # Accept the value
        instance.accepted_number = proposal_number
        instance.accepted_value = value
        instance.promised_number = proposal_number  # Update promise
        
        # Send Accepted
        accepted_msg = PaxosMessage(
            msg_type="accepted",
            proposal_number=proposal_number,
            instance_id=instance_id,
            sender_id=self.node_id,
            value=value,
        )
        self._send_to(sender_id, accepted_msg.to_dict())
        logger.debug(f"Acceptor {self.node_id}: Accepted value for {instance_id}")
    
    # ==================== Learner Role ====================
    
    def _handle_promise(self, message: Dict[str, Any]) -> None:
        """Handle a Promise message (Phase 1b)."""
        instance_id = message["instance_id"]
        sender_id = message["sender_id"]
        proposal_number = ProposalNumber.from_dict(message["proposal_number"])
        accepted_value = message.get("value")
        
        instance = self._get_or_create_instance(instance_id)
        instance.promises_received.add(sender_id)
        
        # Track the accepted value from this promise (if any)
        # This is crucial for Paxos correctness - proposer must use
        # the value from the highest-numbered accepted proposal
        instance.promise_values[sender_id] = (proposal_number, accepted_value)
        
        logger.debug(f"Proposer {self.node_id}: Received promise from {sender_id}")
        
        # Signal event if quorum reached
        if len(instance.promises_received) >= self.quorum_size:
            event = instance.get_promises_event()
            if not event.is_set():
                event.set()
    
    def _handle_accepted(self, message: Dict[str, Any]) -> None:
        """Handle an Accepted message (Phase 2b)."""
        instance_id = message["instance_id"]
        sender_id = message["sender_id"]
        value = message.get("value")
        
        instance = self._get_or_create_instance(instance_id)
        instance.accepts_received.add(sender_id)
        logger.debug(f"Proposer {self.node_id}: Received accepted from {sender_id}")
        
        # Signal event if quorum reached
        if len(instance.accepts_received) >= self.quorum_size:
            event = instance.get_accepts_event()
            if not event.is_set():
                event.set()
    
    def _handle_commit(self, message: Dict[str, Any]) -> None:
        """Handle a Commit message."""
        instance_id = message["instance_id"]
        value = message.get("value")
        
        instance = self._get_or_create_instance(instance_id)
        instance.phase = PaxosPhase.COMMITTED
        instance.committed_value = value
        instance.committed_at = datetime.utcnow()
        
        logger.info(f"Learner {self.node_id}: Value committed for {instance_id}")
        
        if self._on_value_committed:
            self._on_value_committed(instance_id, value)
    
    # ==================== Message Handling ====================
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive and process a message."""
        msg_type = message.get("type")
        handler = self._handlers.get(msg_type)
        if handler:
            handler(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    def get_instance(self, instance_id: str) -> Optional[PaxosInstance]:
        """Get a Paxos instance by ID."""
        return self._instances.get(instance_id)
    
    def get_committed_value(self, instance_id: str) -> Optional[Any]:
        """Get the committed value for an instance."""
        instance = self._instances.get(instance_id)
        if instance and instance.phase == PaxosPhase.COMMITTED:
            return instance.committed_value
        return None


class MultiPaxos:
    """
    Multi-Paxos for a sequence of consensus decisions.
    
    Optimizes by using a stable leader that can skip Phase 1
    for subsequent proposals.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Set[str],
        leader_id: Optional[str] = None,
    ):
        self.node_id = node_id
        self.peers = peers
        self.leader_id = leader_id
        self.paxos_node = PaxosNode(node_id, peers)
        
        # Committed log
        self._log: List[Tuple[str, Any]] = []
        self._commit_index = 0
        
        # Callbacks
        self._on_log_entry: Optional[Callable[[int, Any], None]] = None
    
    def set_callbacks(
        self,
        on_log_entry: Optional[Callable[[int, Any], None]] = None,
        send_message: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self._on_log_entry = on_log_entry
        self.paxos_node.set_callbacks(
            on_value_committed=self._on_value_committed,
            send_message=send_message,
        )
    
    def _on_value_committed(self, instance_id: str, value: Any) -> None:
        """Handle committed value."""
        self._log.append((instance_id, value))
        
        if self._on_log_entry:
            self._on_log_entry(len(self._log) - 1, value)
    
    async def propose(self, value: Any) -> Tuple[bool, Any]:
        """Propose a value (leader only)."""
        if self.leader_id != self.node_id:
            logger.debug(f"Node {self.node_id}: Not leader, cannot propose directly")
            return (False, None)
        
        instance_id = f"log-{len(self._log)}"
        return await self.paxos_node.propose(value, instance_id)
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive and process a message."""
        self.paxos_node.receive_message(message)
    
    def get_log(self) -> List[Tuple[str, Any]]:
        """Get the committed log."""
        return self._log.copy()
    
    def get_log_entry(self, index: int) -> Optional[Any]:
        """Get a log entry by index."""
        if 0 <= index < len(self._log):
            return self._log[index][1]
        return None


# Export
__all__ = [
    "PaxosPhase",
    "ProposalNumber",
    "PaxosMessage",
    "PaxosInstance",
    "PaxosNode",
    "MultiPaxos",
]
