"""
Consensus Transport Layer

Integrates consensus algorithms with the coordination layer for
real inter-process communication in distributed swarm decisions.

This module provides:
- File-based message passing between consensus nodes
- Integration with AgentCoordinator for node discovery
- Async message queue for consensus protocols
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import hashlib
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ConsensusMessage:
    """A message for consensus protocol."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_node: str = ""
    target_node: str = ""  # Empty = broadcast
    message_type: str = ""  # prepare, promise, accept, accepted, commit, etc.
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsensusMessage":
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())[:8]),
            source_node=data["source_node"],
            target_node=data["target_node"],
            message_type=data["message_type"],
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.utcnow(),
            ttl_seconds=data.get("ttl_seconds", 60),
        )
    
    def is_expired(self) -> bool:
        return (datetime.utcnow() - self.timestamp) > timedelta(seconds=self.ttl_seconds)


class ConsensusTransport:
    """
    File-based transport layer for consensus messages.
    
    Uses the coordination directory structure for message passing:
    - .agent_coordination/consensus/{node_id}/inbox/ - incoming messages
    - .agent_coordination/consensus/{node_id}/outbox/ - outgoing messages
    
    This allows multiple processes on the same machine to communicate
    without requiring network sockets.
    
    For cross-machine communication, this can be extended with:
    - HTTP/gRPC endpoints
    - Message queues (Redis, RabbitMQ)
    - WebSocket connections
    """
    
    BASE_DIR = ".agent_coordination/consensus"
    MESSAGE_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 0.01  # 10ms polling for low latency
    
    def __init__(
        self,
        node_id: str,
        project_root: str = ".",
        poll_interval: float = None,
    ):
        self.node_id = node_id
        self.project_root = Path(project_root)
        self.base_dir = self.project_root / self.BASE_DIR
        self.poll_interval = poll_interval or self.POLL_INTERVAL_SECONDS
        
        # Node directories
        self.inbox_dir = self.base_dir / node_id / "inbox"
        self.outbox_dir = self.base_dir / node_id / "outbox"
        
        # Ensure directories exist
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        
        # Message handlers by type
        self._handlers: Dict[str, Callable[[ConsensusMessage], None]] = {}
        
        # Background polling task
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Message deduplication
        self._processed_messages: Set[str] = set()
        self._max_processed_cache = 1000
        
        # Statistics
        self._messages_sent = 0
        self._messages_received = 0
        
        logger.info(f"ConsensusTransport initialized for node {node_id}")
    
    def register_handler(
        self,
        message_type: str,
        handler: Callable[[ConsensusMessage], None],
    ) -> None:
        """Register a handler for a message type."""
        self._handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")
    
    async def start(self) -> None:
        """Start the message polling loop."""
        if self._running:
            return
        
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"ConsensusTransport started for node {self.node_id}")
    
    async def stop(self) -> None:
        """Stop the message polling loop."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info(f"ConsensusTransport stopped for node {self.node_id}")
    
    async def send(self, message: ConsensusMessage) -> bool:
        """
        Send a message to target node(s).
        
        If target_node is empty, broadcasts to all known nodes.
        """
        if not message.source_node:
            message.source_node = self.node_id
        
        if message.target_node:
            # Direct message to specific node
            return await self._send_to_node(message, message.target_node)
        else:
            # Broadcast to all nodes
            return await self._broadcast(message)
    
    async def _send_to_node(self, message: ConsensusMessage, target_node: str) -> bool:
        """Send message to a specific node's inbox."""
        target_inbox = self.base_dir / target_node / "inbox"
        
        if not target_inbox.exists():
            logger.warning(f"Target node inbox does not exist: {target_node}")
            # Create it for testing purposes
            target_inbox.mkdir(parents=True, exist_ok=True)
        
        # Write message file
        message_file = target_inbox / f"{message.message_id}.json"
        
        try:
            # Atomic write using temp file
            temp_file = message_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(message.to_dict(), f)
            temp_file.rename(message_file)
            
            self._messages_sent += 1
            logger.debug(f"Sent message {message.message_id} to {target_node}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {target_node}: {e}")
            return False
    
    async def _broadcast(self, message: ConsensusMessage) -> bool:
        """Broadcast message to all known nodes."""
        # Find all node directories
        known_nodes = self._discover_nodes()
        
        success = True
        for node_id in known_nodes:
            if node_id != self.node_id:  # Don't send to self
                msg_copy = ConsensusMessage(
                    message_id=message.message_id,
                    source_node=message.source_node,
                    target_node=node_id,
                    message_type=message.message_type,
                    payload=message.payload,
                    timestamp=message.timestamp,
                    ttl_seconds=message.ttl_seconds,
                )
                if not await self._send_to_node(msg_copy, node_id):
                    success = False
        
        return success
    
    def _discover_nodes(self) -> Set[str]:
        """Discover all nodes with inbox directories."""
        nodes = set()
        if self.base_dir.exists():
            for node_dir in self.base_dir.iterdir():
                if node_dir.is_dir() and (node_dir / "inbox").exists():
                    nodes.add(node_dir.name)
        return nodes
    
    async def _poll_loop(self) -> None:
        """Background loop to poll for incoming messages."""
        while self._running:
            try:
                await self._process_inbox()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                await asyncio.sleep(0.1)  # Back off on error
    
    async def _process_inbox(self) -> None:
        """Process all messages in inbox."""
        if not self.inbox_dir.exists():
            return
        
        for message_file in list(self.inbox_dir.glob("*.json")):
            try:
                # Read and parse message
                with open(message_file, "r") as f:
                    data = json.load(f)
                
                message = ConsensusMessage.from_dict(data)
                
                # Skip if already processed
                if message.message_id in self._processed_messages:
                    message_file.unlink(missing_ok=True)
                    continue
                
                # Skip if expired
                if message.is_expired():
                    message_file.unlink(missing_ok=True)
                    continue
                
                # Dispatch to handler
                handler = self._handlers.get(message.message_type)
                if handler:
                    handler(message)
                    self._messages_received += 1
                    logger.debug(f"Processed message {message.message_id} of type {message.message_type}")
                
                # Mark as processed
                self._processed_messages.add(message.message_id)
                if len(self._processed_messages) > self._max_processed_cache:
                    # Trim cache
                    self._processed_messages = set(list(self._processed_messages)[-self._max_processed_cache:])
                
                # Remove processed message file
                message_file.unlink(missing_ok=True)
                
            except Exception as e:
                logger.error(f"Error processing message file {message_file}: {e}")
                # Remove corrupted file
                message_file.unlink(missing_ok=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics."""
        return {
            "node_id": self.node_id,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "known_nodes": list(self._discover_nodes()),
            "running": self._running,
        }


class DistributedConsensusNode:
    """
    A consensus node that uses ConsensusTransport for communication.
    
    This class bridges the gap between the consensus algorithms
    (Raft, Paxos, PBFT) and the transport layer.
    
    Example:
        >>> transport = ConsensusTransport(node_id="node-1")
        >>> node = DistributedConsensusNode(
        ...     node_id="node-1",
        ...     transport=transport,
        ... )
        >>> await node.start()
        >>> 
        >>> # Now the node can participate in distributed consensus
        >>> decision = await node.propose("topic-1", {"action": "heal"})
    """
    
    def __init__(
        self,
        node_id: str,
        transport: Optional[ConsensusTransport] = None,
        peers: Optional[Set[str]] = None,
    ):
        self.node_id = node_id
        self.transport = transport or ConsensusTransport(node_id=node_id)
        self.peers = peers or set()
        
        # Pending proposals
        self._pending: Dict[str, asyncio.Future] = {}
        
        # Consensus state
        self._current_term = 0
        self._voted_for: Optional[str] = None
        self._log: List[Dict[str, Any]] = []
        
        # Register message handlers
        self.transport.register_handler("prepare", self._handle_prepare)
        self.transport.register_handler("promise", self._handle_promise)
        self.transport.register_handler("accept", self._handle_accept)
        self.transport.register_handler("accepted", self._handle_accepted)
        self.transport.register_handler("commit", self._handle_commit)
        self.transport.register_handler("vote_request", self._handle_vote_request)
        self.transport.register_handler("vote_response", self._handle_vote_response)
    
    async def start(self) -> None:
        """Start the distributed consensus node."""
        await self.transport.start()
        logger.info(f"DistributedConsensusNode {self.node_id} started")
    
    async def stop(self) -> None:
        """Stop the distributed consensus node."""
        await self.transport.stop()
        logger.info(f"DistributedConsensusNode {self.node_id} stopped")
    
    async def propose(self, topic: str, value: Any, timeout: float = 5.0) -> tuple:
        """
        Propose a value for consensus.
        
        Returns (success, result) tuple.
        """
        proposal_id = str(uuid.uuid4())[:8]
        
        # Create future for result
        future: asyncio.Future = asyncio.Future()
        self._pending[proposal_id] = future
        
        try:
            # Broadcast prepare message
            prepare = ConsensusMessage(
                source_node=self.node_id,
                message_type="prepare",
                payload={
                    "proposal_id": proposal_id,
                    "topic": topic,
                    "value": value,
                    "term": self._current_term,
                },
            )
            
            await self.transport.send(prepare)
            
            # Wait for quorum
            result = await asyncio.wait_for(future, timeout=timeout)
            return (True, result)
            
        except asyncio.TimeoutError:
            logger.warning(f"Proposal {proposal_id} timed out")
            return (False, None)
        finally:
            self._pending.pop(proposal_id, None)
    
    # Message handlers (simplified for prototype)
    
    def _handle_prepare(self, message: ConsensusMessage) -> None:
        """Handle a prepare message from a proposer."""
        logger.debug(f"Node {self.node_id} received prepare from {message.source_node}")
        # Send promise back
        promise = ConsensusMessage(
            source_node=self.node_id,
            target_node=message.source_node,
            message_type="promise",
            payload={
                "proposal_id": message.payload.get("proposal_id"),
                "term": self._current_term,
            },
        )
        asyncio.create_task(self.transport.send(promise))
    
    def _handle_promise(self, message: ConsensusMessage) -> None:
        """Handle a promise message from an acceptor."""
        proposal_id = message.payload.get("proposal_id")
        logger.debug(f"Node {self.node_id} received promise for {proposal_id}")
        # In full implementation, track promises and proceed to accept phase
    
    def _handle_accept(self, message: ConsensusMessage) -> None:
        """Handle an accept message."""
        logger.debug(f"Node {self.node_id} received accept from {message.source_node}")
        # Send accepted back
        accepted = ConsensusMessage(
            source_node=self.node_id,
            target_node=message.source_node,
            message_type="accepted",
            payload=message.payload,
        )
        asyncio.create_task(self.transport.send(accepted))
    
    def _handle_accepted(self, message: ConsensusMessage) -> None:
        """Handle an accepted message."""
        proposal_id = message.payload.get("proposal_id")
        logger.debug(f"Node {self.node_id} received accepted for {proposal_id}")
        # In full implementation, track accepts and commit
    
    def _handle_commit(self, message: ConsensusMessage) -> None:
        """Handle a commit message."""
        proposal_id = message.payload.get("proposal_id")
        value = message.payload.get("value")
        logger.info(f"Node {self.node_id} received commit for {proposal_id}")
        
        # Complete pending future
        if proposal_id in self._pending:
            future = self._pending[proposal_id]
            if not future.done():
                future.set_result(value)
    
    def _handle_vote_request(self, message: ConsensusMessage) -> None:
        """Handle a vote request (Raft leader election)."""
        term = message.payload.get("term", 0)
        candidate_id = message.source_node
        
        vote_granted = False
        if term > self._current_term:
            self._current_term = term
            self._voted_for = candidate_id
            vote_granted = True
        elif term == self._current_term and self._voted_for in (None, candidate_id):
            self._voted_for = candidate_id
            vote_granted = True
        
        response = ConsensusMessage(
            source_node=self.node_id,
            target_node=candidate_id,
            message_type="vote_response",
            payload={
                "term": self._current_term,
                "vote_granted": vote_granted,
            },
        )
        asyncio.create_task(self.transport.send(response))
    
    def _handle_vote_response(self, message: ConsensusMessage) -> None:
        """Handle a vote response."""
        logger.debug(f"Node {self.node_id} received vote response from {message.source_node}")


# Export
__all__ = [
    "ConsensusMessage",
    "ConsensusTransport",
    "DistributedConsensusNode",
]
