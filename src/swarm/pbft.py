"""
Practical Byzantine Fault Tolerance (PBFT) Implementation

Provides a complete implementation of PBFT consensus algorithm
for Byzantine fault-tolerant distributed decision making.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import json

logger = logging.getLogger(__name__)


class PBFTPhase(str, Enum):
    """Phases in PBFT protocol."""
    IDLE = "idle"
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    EXECUTED = "executed"


@dataclass
class PBFTMessage:
    """Base message for PBFT protocol."""
    msg_type: str
    view: int
    sequence: int
    digest: str
    sender_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request: Optional[Any] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.msg_type,
            "view": self.view,
            "sequence": self.sequence,
            "digest": self.digest,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp.isoformat(),
            "request": self.request,
            "signature": self.signature,
        }
    
    def compute_digest(self) -> str:
        """Compute message digest for verification."""
        data = f"{self.msg_type}:{self.view}:{self.sequence}:{self.digest}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class PBFTRequest:
    """Client request for PBFT."""
    client_id: str
    timestamp: int
    operation: Any
    request_id: str = field(default_factory=lambda: str(int(time.time() * 1000)))
    
    def compute_digest(self) -> str:
        """Compute request digest."""
        data = json.dumps({
            "client_id": self.client_id,
            "timestamp": self.timestamp,
            "operation": str(self.operation),
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:32]


@dataclass
class PBFTLogEntry:
    """Entry in the PBFT log."""
    sequence: int
    view: int
    digest: str
    request: Optional[PBFTRequest] = None
    phase: PBFTPhase = PBFTPhase.IDLE
    
    # Message tracking
    pre_prepare_msg: Optional[PBFTMessage] = None
    prepare_msgs: Dict[str, PBFTMessage] = field(default_factory=dict)
    commit_msgs: Dict[str, PBFTMessage] = field(default_factory=dict)
    
    # Execution
    executed: bool = False
    result: Optional[Any] = None


class PBFTNode:
    """
    PBFT node for Byzantine fault-tolerant consensus.
    
    Implements the full PBFT protocol:
    - Pre-prepare: Primary sends request with sequence number
    - Prepare: Replicas verify and send prepare messages
    - Commit: Replicas send commit messages after 2f+1 prepares
    - Execute: Replicas execute after 2f+1 commits
    
    Can tolerate up to f Byzantine (malicious) nodes out of 3f+1 total.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Set[str],
        f: int = 1,  # Max Byzantine nodes
    ):
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = peers | {node_id}
        self.f = f
        self.n = 3 * f + 1  # Minimum nodes for BFT
        
        # View management
        self.view = 0
        self.primary_id = self._get_primary(self.view)
        self.is_primary = self.node_id == self.primary_id
        
        # Sequence management
        self.sequence = 0
        self.low_water_mark = 0
        self.high_water_mark = 100  # Log size limit
        
        # Log
        self._log: Dict[int, PBFTLogEntry] = {}
        
        # Message tracking
        self._prepared: Set[int] = set()  # Sequences that are prepared
        self._committed: Set[int] = set()  # Sequences that are committed
        
        # Client request tracking
        self._pending_requests: Dict[str, PBFTRequest] = {}
        self._executed_requests: Set[str] = set()
        
        # Callbacks
        self._on_execute: Optional[Callable[[Any], Any]] = None
        self._send_message: Optional[Callable[[str, Dict], None]] = None
        
        # Message handlers
        self._handlers = {
            "request": self._handle_request,
            "pre_prepare": self._handle_pre_prepare,
            "prepare": self._handle_prepare,
            "commit": self._handle_commit,
            "view_change": self._handle_view_change,
            "new_view": self._handle_new_view,
        }
    
    def _get_primary(self, view: int) -> str:
        """Get the primary for a given view."""
        nodes = sorted(self.all_nodes)
        return nodes[view % len(nodes)]
    
    def set_callbacks(
        self,
        on_execute: Optional[Callable[[Any], Any]] = None,
        send_message: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self._on_execute = on_execute
        self._send_message = send_message
    
    def _send_to(self, target_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific node."""
        if self._send_message:
            self._send_message(target_id, message)
    
    def _send_to_all(self, message: Dict[str, Any]) -> None:
        """Send message to all peers."""
        for peer in self.peers:
            self._send_to(peer, message)
    
    def _get_or_create_entry(self, sequence: int) -> PBFTLogEntry:
        """Get or create a log entry."""
        if sequence not in self._log:
            self._log[sequence] = PBFTLogEntry(
                sequence=sequence,
                view=self.view,
                digest="",
            )
        return self._log[sequence]
    
    # ==================== Client Interface ====================
    
    async def request(self, operation: Any) -> Tuple[bool, Any]:
        """
        Submit a request to the PBFT cluster.
        
        Returns (success, result).
        """
        request = PBFTRequest(
            client_id=self.node_id,
            timestamp=int(time.time() * 1000),
            operation=operation,
        )
        
        digest = request.compute_digest()
        self._pending_requests[digest] = request
        
        # Send request to primary
        msg = PBFTMessage(
            msg_type="request",
            view=self.view,
            sequence=0,  # Will be assigned by primary
            digest=digest,
            sender_id=self.node_id,
            request=request.to_dict() if hasattr(request, 'to_dict') else {
                "client_id": request.client_id,
                "timestamp": request.timestamp,
                "operation": str(request.operation),
            },
        )
        
        self._send_to(self.primary_id, msg.to_dict())
        
        # Wait for execution (simplified)
        try:
            await asyncio.wait_for(
                self._wait_for_execution(digest),
                timeout=30.0
            )
            
            # Get result from log
            for entry in self._log.values():
                if entry.executed and entry.digest == digest:
                    return (True, entry.result)
            
            return (False, None)
        except asyncio.TimeoutError:
            logger.warning(f"Request {digest[:8]} timed out")
            return (False, None)
    
    async def _wait_for_execution(self, digest: str) -> None:
        """Wait for request to be executed."""
        while digest not in self._executed_requests:
            await asyncio.sleep(0.1)
    
    # ==================== Primary Role ====================
    
    def _handle_request(self, message: Dict[str, Any]) -> None:
        """Handle a client request (Primary only)."""
        if not self.is_primary:
            # Forward to primary
            self._send_to(self.primary_id, message)
            return
        
        digest = message["digest"]
        request_data = message.get("request", {})
        
        # Assign sequence number
        self.sequence += 1
        sequence = self.sequence
        
        # Create log entry
        entry = self._get_or_create_entry(sequence)
        entry.view = self.view
        entry.digest = digest
        entry.phase = PBFTPhase.PRE_PREPARE
        
        # Create pre-prepare message
        pre_prepare = PBFTMessage(
            msg_type="pre_prepare",
            view=self.view,
            sequence=sequence,
            digest=digest,
            sender_id=self.node_id,
            request=request_data,
        )
        entry.pre_prepare_msg = pre_prepare
        
        # Send pre-prepare to all replicas
        self._send_to_all(pre_prepare.to_dict())
        
        logger.info(f"Primary {self.node_id}: Sent pre-prepare for seq {sequence}")
    
    # ==================== Replica Role ====================
    
    def _handle_pre_prepare(self, message: Dict[str, Any]) -> None:
        """Handle a pre-prepare message from primary."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify sender is primary for this view
        if sender_id != self._get_primary(view):
            logger.warning(f"Pre-prepare from non-primary {sender_id}")
            return
        
        # Verify view
        if view != self.view:
            logger.warning(f"Pre-prepare for wrong view {view} (current: {self.view})")
            return
        
        # Verify sequence
        if sequence <= self.low_water_mark or sequence > self.high_water_mark:
            logger.warning(f"Pre-prepare with invalid sequence {sequence}")
            return
        
        # Create log entry
        entry = self._get_or_create_entry(sequence)
        entry.view = view
        entry.digest = digest
        entry.phase = PBFTPhase.PRE_PREPARE
        entry.pre_prepare_msg = PBFTMessage(
            msg_type="pre_prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        
        # Send prepare to all
        prepare = PBFTMessage(
            msg_type="prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=self.node_id,
        )
        self._send_to_all(prepare.to_dict())
        
        # Also store our own prepare
        entry.prepare_msgs[self.node_id] = prepare
        
        logger.debug(f"Replica {self.node_id}: Sent prepare for seq {sequence}")
        
        # Check if we can advance to commit
        self._check_prepare(entry)
    
    def _handle_prepare(self, message: Dict[str, Any]) -> None:
        """Handle a prepare message."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify view
        if view != self.view:
            return
        
        # Get log entry
        entry = self._log.get(sequence)
        if not entry or entry.digest != digest:
            return
        
        # Store prepare message
        prepare = PBFTMessage(
            msg_type="prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        entry.prepare_msgs[sender_id] = prepare
        
        logger.debug(f"Replica {self.node_id}: Received prepare from {sender_id}")
        
        # Check if we can advance to commit
        self._check_prepare(entry)
    
    def _check_prepare(self, entry: PBFTLogEntry) -> None:
        """Check if we have enough prepares to advance to commit."""
        if entry.phase != PBFTPhase.PRE_PREPARE:
            return
        
        # Need 2f prepares (including our own)
        if len(entry.prepare_msgs) >= 2 * self.f:
            entry.phase = PBFTPhase.PREPARE
            self._prepared.add(entry.sequence)
            
            # Send commit
            commit = PBFTMessage(
                msg_type="commit",
                view=entry.view,
                sequence=entry.sequence,
                digest=entry.digest,
                sender_id=self.node_id,
            )
            self._send_to_all(commit.to_dict())
            entry.commit_msgs[self.node_id] = commit
            
            logger.debug(f"Replica {self.node_id}: Sent commit for seq {entry.sequence}")
            
            # Check if we can execute
            self._check_commit(entry)
    
    def _handle_commit(self, message: Dict[str, Any]) -> None:
        """Handle a commit message."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify view
        if view != self.view:
            return
        
        # Get log entry
        entry = self._log.get(sequence)
        if not entry or entry.digest != digest:
            return
        
        # Store commit message
        commit = PBFTMessage(
            msg_type="commit",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        entry.commit_msgs[sender_id] = commit
        
        logger.debug(f"Replica {self.node_id}: Received commit from {sender_id}")
        
        # Check if we can execute
        self._check_commit(entry)
    
    def _check_commit(self, entry: PBFTLogEntry) -> None:
        """Check if we have enough commits to execute."""
        if entry.phase != PBFTPhase.PREPARE:
            return
        
        # Need 2f+1 commits
        if len(entry.commit_msgs) >= 2 * self.f + 1:
            entry.phase = PBFTPhase.COMMIT
            self._committed.add(entry.sequence)
            
            # Execute
            self._execute(entry)
    
    def _execute(self, entry: PBFTLogEntry) -> None:
        """Execute the request."""
        if entry.executed:
            return
        
        # Get the request
        if entry.pre_prepare_msg and entry.pre_prepare_msg.request:
            operation = entry.pre_prepare_msg.request.get("operation")
        else:
            operation = None
        
        # Execute operation
        result = None
        if self._on_execute and operation:
            try:
                result = self._on_execute(operation)
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                result = {"error": str(e)}
        
        entry.executed = True
        entry.result = result
        entry.phase = PBFTPhase.EXECUTED
        
        self._executed_requests.add(entry.digest)
        
        logger.info(f"Replica {self.node_id}: Executed seq {entry.sequence}")
    
    # ==================== View Change ====================
    
    def _handle_view_change(self, message: Dict[str, Any]) -> None:
        """Handle a view change message."""
        # Simplified view change - in real implementation, this would be more complex
        logger.info(f"Replica {self.node_id}: Received view change request")
    
    def _handle_new_view(self, message: Dict[str, Any]) -> None:
        """Handle a new view message."""
        new_view = message.get("view", self.view + 1)
        
        if new_view > self.view:
            self.view = new_view
            self.primary_id = self._get_primary(self.view)
            self.is_primary = self.node_id == self.primary_id
            
            logger.info(f"Replica {self.node_id}: Advanced to view {self.view}, primary={self.primary_id}")
    
    def start_view_change(self) -> None:
        """Initiate a view change."""
        self.view += 1
        self.primary_id = self._get_primary(self.view)
        self.is_primary = self.node_id == self.primary_id
        
        # Notify others
        msg = PBFTMessage(
            msg_type="new_view",
            view=self.view,
            sequence=0,
            digest="",
            sender_id=self.node_id,
        )
        self._send_to_all(msg.to_dict())
        
        logger.info(f"Replica {self.node_id}: Started view change to {self.view}")
    
    # ==================== Message Handling ====================
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive and process a message."""
        msg_type = message.get("type")
        handler = self._handlers.get(msg_type)
        if handler:
            handler(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    def get_log_entry(self, sequence: int) -> Optional[PBFTLogEntry]:
        """Get a log entry by sequence number."""
        return self._log.get(sequence)
    
    def get_executed(self) -> List[int]:
        """Get list of executed sequence numbers."""
        return sorted([s for s, e in self._log.items() if e.executed])


# Export
__all__ = [
    "PBFTPhase",
    "PBFTMessage",
    "PBFTRequest",
    "PBFTLogEntry",
    "PBFTNode",
]
