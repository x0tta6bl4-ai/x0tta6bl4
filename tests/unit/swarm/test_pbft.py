"""
Unit Tests for PBFT (Practical Byzantine Fault Tolerance) Implementation

Tests the PBFT implementation including:
- Message handling (pre-prepare, prepare, commit)
- View changes
- Execution
- Byzantine fault tolerance
"""

import asyncio
import pytest
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
import json

from src.swarm.pbft import (
    PBFTPhase,
    PBFTMessage,
    PBFTRequest,
    PBFTLogEntry,
    PBFTNode,
)


# ==================== Fixtures ====================

@pytest.fixture
def pbft_message():
    """Create a sample PBFT message."""
    return PBFTMessage(
        msg_type="pre_prepare",
        view=0,
        sequence=1,
        digest="test-digest",
        sender_id="node-1",
    )


@pytest.fixture
def pbft_request():
    """Create a sample PBFT request."""
    return PBFTRequest(
        client_id="client-1",
        timestamp=int(datetime.utcnow().timestamp() * 1000),
        operation={"action": "test"},
    )


@pytest.fixture
def pbft_log_entry():
    """Create a sample PBFT log entry."""
    return PBFTLogEntry(
        sequence=1,
        view=0,
        digest="test-digest",
    )


@pytest.fixture
def pbft_node():
    """Create a PBFT node for testing."""
    return PBFTNode(
        node_id="node-1",
        peers={"node-2", "node-3", "node-4"},
        f=1,  # Can tolerate 1 Byzantine node
    )


@pytest.fixture
def pbft_cluster():
    """Create a 4-node PBFT cluster (minimum for f=1)."""
    nodes = {}
    for i in range(1, 5):
        node_id = f"node-{i}"
        peers = {f"node-{j}" for j in range(1, 5) if j != i}
        nodes[node_id] = PBFTNode(node_id=node_id, peers=peers, f=1)
    return nodes


# ==================== PBFTMessage Tests ====================

class TestPBFTMessage:
    """Tests for PBFTMessage class."""
    
    def test_creation(self):
        """Test message creation."""
        msg = PBFTMessage(
            msg_type="prepare",
            view=1,
            sequence=5,
            digest="abc123",
            sender_id="node-2",
        )
        
        assert msg.msg_type == "prepare"
        assert msg.view == 1
        assert msg.sequence == 5
        assert msg.digest == "abc123"
        assert msg.sender_id == "node-2"
    
    def test_to_dict(self, pbft_message):
        """Test message serialization."""
        data = pbft_message.to_dict()
        
        assert data["type"] == "pre_prepare"
        assert data["view"] == 0
        assert data["sequence"] == 1
        assert data["digest"] == "test-digest"
        assert data["sender_id"] == "node-1"
        assert "timestamp" in data
    
    def test_compute_digest(self, pbft_message):
        """Test message digest computation."""
        digest = pbft_message.compute_digest()
        
        # Should be a hash
        assert len(digest) == 16
        assert all(c in '0123456789abcdef' for c in digest)


# ==================== PBFTRequest Tests ====================

class TestPBFTRequest:
    """Tests for PBFTRequest class."""
    
    def test_creation(self):
        """Test request creation."""
        req = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"action": "transfer", "amount": 100},
        )
        
        assert req.client_id == "client-1"
        assert req.timestamp == 1234567890
        assert req.operation["action"] == "transfer"
    
    def test_compute_digest(self, pbft_request):
        """Test request digest computation."""
        digest = pbft_request.compute_digest()
        
        # Should be a 32-char hash
        assert len(digest) == 32
        assert all(c in '0123456789abcdef' for c in digest)
    
    def test_same_request_same_digest(self):
        """Test that identical requests produce identical digests."""
        req1 = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"action": "test"},
        )
        req2 = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"action": "test"},
        )
        
        assert req1.compute_digest() == req2.compute_digest()
    
    def test_different_request_different_digest(self):
        """Test that different requests produce different digests."""
        req1 = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"action": "test1"},
        )
        req2 = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"action": "test2"},
        )
        
        assert req1.compute_digest() != req2.compute_digest()


# ==================== PBFTLogEntry Tests ====================

class TestPBFTLogEntry:
    """Tests for PBFTLogEntry class."""
    
    def test_creation(self):
        """Test log entry creation."""
        entry = PBFTLogEntry(
            sequence=1,
            view=0,
            digest="test-digest",
        )
        
        assert entry.sequence == 1
        assert entry.view == 0
        assert entry.digest == "test-digest"
        assert entry.phase == PBFTPhase.IDLE
        assert not entry.executed
    
    def test_message_tracking(self, pbft_log_entry):
        """Test message tracking in log entry."""
        msg = PBFTMessage(
            msg_type="prepare",
            view=0,
            sequence=1,
            digest="test-digest",
            sender_id="node-2",
        )
        
        pbft_log_entry.prepare_msgs["node-2"] = msg
        
        assert "node-2" in pbft_log_entry.prepare_msgs
        assert pbft_log_entry.prepare_msgs["node-2"].msg_type == "prepare"


# ==================== PBFTNode Tests ====================

class TestPBFTNode:
    """Tests for PBFTNode class."""
    
    def test_creation(self):
        """Test node creation."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        assert node.node_id == "node-1"
        assert len(node.peers) == 3
        assert node.f == 1
        assert node.n == 4  # 3f + 1 = 4
    
    def test_primary_selection(self, pbft_node):
        """Test primary selection based on view."""
        # View 0: node-1 is primary (sorted order: node-1, node-2, node-3, node-4)
        primary = pbft_node._get_primary(0)
        assert primary == "node-1"
        
        # View 1: node-2 is primary
        primary = pbft_node._get_primary(1)
        assert primary == "node-2"
    
    def test_is_primary(self, pbft_node):
        """Test is_primary flag."""
        # node-1 should be primary for view 0
        assert pbft_node.is_primary is True
        
        # After view change, node-1 should not be primary
        pbft_node.view = 1
        pbft_node.primary_id = pbft_node._get_primary(1)
        pbft_node.is_primary = pbft_node.node_id == pbft_node.primary_id
        
        assert pbft_node.is_primary is False
    
    def test_get_or_create_entry(self, pbft_node):
        """Test log entry creation and retrieval."""
        entry1 = pbft_node._get_or_create_entry(1)
        
        assert entry1.sequence == 1
        
        # Same entry returned on subsequent calls
        entry2 = pbft_node._get_or_create_entry(1)
        assert entry1 is entry2


class TestPBFTNodePrimary:
    """Tests for PBFTNode primary role."""
    
    def test_handle_request_as_primary(self, pbft_node):
        """Test handling client request as primary."""
        messages_sent = []
        pbft_node.set_callbacks(
            send_message=lambda t, m: messages_sent.append((t, m))
        )
        
        # node-1 is primary for view 0
        assert pbft_node.is_primary
        
        request_msg = {
            "type": "request",
            "view": 0,
            "sequence": 0,
            "digest": "test-digest",
            "sender_id": "client-1",
            "request": {
                "client_id": "client-1",
                "timestamp": 1234567890,
                "operation": {"action": "test"},
            },
        }
        
        pbft_node.receive_message(request_msg)
        
        # Should send pre-prepare to all replicas
        assert len(messages_sent) == 3  # 3 peers
        
        for target, msg in messages_sent:
            assert msg["type"] == "pre_prepare"
            assert msg["view"] == 0
    
    def test_handle_request_forwards_to_primary(self):
        """Test that non-primary forwards request to primary."""
        node = PBFTNode(
            node_id="node-2",  # Not primary for view 0
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        messages_sent = []
        node.set_callbacks(
            send_message=lambda t, m: messages_sent.append((t, m))
        )
        
        request_msg = {
            "type": "request",
            "view": 0,
            "sequence": 0,
            "digest": "test-digest",
            "sender_id": "client-1",
            "request": {
                "client_id": "client-1",
                "timestamp": 1234567890,
                "operation": {"action": "test"},
            },
        }
        
        node.receive_message(request_msg)
        
        # Should forward to primary (node-1)
        assert len(messages_sent) == 1
        target, msg = messages_sent[0]
        assert target == "node-1"


class TestPBFTNodeReplica:
    """Tests for PBFTNode replica role."""
    
    def test_handle_pre_prepare(self):
        """Test handling pre-prepare message."""
        node = PBFTNode(
            node_id="node-2",  # Not primary
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        messages_sent = []
        node.set_callbacks(
            send_message=lambda t, m: messages_sent.append((t, m))
        )
        
        pre_prepare_msg = {
            "type": "pre_prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-1",  # Primary
        }
        
        node.receive_message(pre_prepare_msg)
        
        # Should send prepare to all
        assert len(messages_sent) == 3
        
        for target, msg in messages_sent:
            assert msg["type"] == "prepare"
            assert msg["view"] == 0
            assert msg["sequence"] == 1
    
    def test_handle_pre_prepare_rejects_non_primary(self):
        """Test that pre-prepare from non-primary is rejected."""
        node = PBFTNode(
            node_id="node-2",
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        messages_sent = []
        node.set_callbacks(
            send_message=lambda t, m: messages_sent.append((t, m))
        )
        
        # Pre-prepare from node-3 (not primary for view 0)
        pre_prepare_msg = {
            "type": "pre_prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-3",  # Not primary!
        }
        
        node.receive_message(pre_prepare_msg)
        
        # Should not send any prepares
        assert len(messages_sent) == 0
    
    def test_handle_prepare(self):
        """Test handling prepare message."""
        node = PBFTNode(
            node_id="node-2",
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        # First receive pre-prepare
        node.receive_message({
            "type": "pre_prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-1",
        })
        
        entry = node.get_log_entry(1)
        initial_prepares = len(entry.prepare_msgs)
        
        # Then receive prepare from another node
        node.receive_message({
            "type": "prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-3",
        })
        
        # Should have stored the prepare
        assert len(entry.prepare_msgs) > initial_prepares
    
    def test_handle_commit(self):
        """Test handling commit message."""
        node = PBFTNode(
            node_id="node-2",
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        executed = []
        node.set_callbacks(
            on_execute=lambda op: executed.append(op)
        )
        
        # Setup: receive pre-prepare and enough prepares
        node.receive_message({
            "type": "pre_prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-1",
            "request": {"operation": "test-op"},
        })
        
        entry = node.get_log_entry(1)
        entry.phase = PBFTPhase.PREPARE  # Simulate prepare phase complete
        
        # Receive commits (need 2f+1 = 3)
        for sender in ["node-1", "node-3", "node-4"]:
            node.receive_message({
                "type": "commit",
                "view": 0,
                "sequence": 1,
                "digest": "test-digest",
                "sender_id": sender,
            })
        
        # Should have executed
        assert entry.executed


class TestPBFTNodeViewChange:
    """Tests for PBFTNode view change."""
    
    def test_start_view_change(self, pbft_node):
        """Test starting a view change."""
        messages_sent = []
        pbft_node.set_callbacks(
            send_message=lambda t, m: messages_sent.append((t, m))
        )
        
        old_view = pbft_node.view
        old_primary = pbft_node.primary_id
        
        pbft_node.start_view_change()
        
        assert pbft_node.view == old_view + 1
        assert pbft_node.primary_id != old_primary
        
        # Should send new_view message
        assert len(messages_sent) == 3  # To all peers
        for target, msg in messages_sent:
            assert msg["type"] == "new_view"
    
    def test_handle_new_view(self):
        """Test handling new_view message."""
        node = PBFTNode(
            node_id="node-2",
            peers={"node-1", "node-3", "node-4"},
            f=1,
        )
        
        initial_view = node.view
        
        node.receive_message({
            "type": "new_view",
            "view": initial_view + 1,
            "sequence": 0,
            "digest": "",
            "sender_id": "node-1",
        })
        
        assert node.view == initial_view + 1


# ==================== PBFT Consensus Flow Tests ====================

class TestPBFTConsensusFlow:
    """Tests for complete PBFT consensus flow."""
    
    @pytest.mark.asyncio
    async def test_full_consensus_flow(self):
        """Test complete PBFT consensus flow."""
        # Create 4-node cluster
        nodes = {}
        messages = {}  # node_id -> list of (target, message)
        
        for i in range(1, 5):
            node_id = f"node-{i}"
            peers = {f"node-{j}" for j in range(1, 5) if j != i}
            nodes[node_id] = PBFTNode(node_id=node_id, peers=peers, f=1)
            messages[node_id] = []
            
            # Set up message capture
            def make_capture(nid):
                def capture(target, msg):
                    messages[nid].append((target, msg))
                return capture
            
            nodes[node_id].set_callbacks(
                send_message=make_capture(node_id),
                on_execute=lambda op: None,
            )
        
        # Primary (node-1) receives request
        request = {
            "type": "request",
            "view": 0,
            "sequence": 0,
            "digest": "test-digest",
            "sender_id": "client-1",
            "request": {
                "client_id": "client-1",
                "timestamp": 1234567890,
                "operation": {"action": "test"},
            },
        }
        
        nodes["node-1"].receive_message(request)
        
        # Primary should have sent pre-prepare to all
        assert len(messages["node-1"]) == 3
        
        # Deliver pre-prepare to replicas
        for target, msg in messages["node-1"]:
            if msg["type"] == "pre_prepare":
                nodes[target].receive_message(msg)
        
        # Replicas should send prepare to all
        for nid in ["node-2", "node-3", "node-4"]:
            for target, msg in messages[nid]:
                if msg["type"] == "prepare":
                    nodes[target].receive_message(msg)
        
        # After receiving prepares, nodes should send commit
        # (This is a simplified test - real flow needs more message delivery)


# ==================== Execution Tests ====================

class TestPBFTExecution:
    """Tests for PBFT execution."""
    
    def test_execute_calls_callback(self, pbft_node):
        """Test that execution calls the callback."""
        executed = []
        pbft_node.set_callbacks(
            on_execute=lambda op: executed.append(op)
        )
        
        entry = pbft_node._get_or_create_entry(1)
        entry.phase = PBFTPhase.PREPARE
        entry.pre_prepare_msg = PBFTMessage(
            msg_type="pre_prepare",
            view=0,
            sequence=1,
            digest="test-digest",
            sender_id="node-1",
            request={"operation": "test-operation"},
        )
        
        pbft_node._execute(entry)
        
        assert entry.executed
        assert len(executed) == 1
        assert executed[0] == "test-operation"
    
    def test_execute_only_once(self, pbft_node):
        """Test that execution happens only once."""
        executed_count = [0]
        pbft_node.set_callbacks(
            on_execute=lambda op: executed_count.__setitem__(0, executed_count[0] + 1)
        )
        
        entry = pbft_node._get_or_create_entry(1)
        entry.phase = PBFTPhase.PREPARE
        entry.pre_prepare_msg = PBFTMessage(
            msg_type="pre_prepare",
            view=0,
            sequence=1,
            digest="test-digest",
            sender_id="node-1",
            request={"operation": "test"},
        )
        
        pbft_node._execute(entry)
        pbft_node._execute(entry)  # Should not execute again
        
        assert executed_count[0] == 1


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
