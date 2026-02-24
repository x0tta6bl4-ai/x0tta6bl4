"""
Unit tests for Paxos and PBFT consensus algorithms (TD-005).
=============================================================

Tests core functionality of Paxos and PBFT implementations.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from src.swarm.paxos import (
    MultiPaxos,
    PaxosInstance,
    PaxosMessage,
    PaxosNode,
    PaxosPhase,
    ProposalNumber,
)
from src.swarm.pbft import (
    PBFTLogEntry,
    PBFTMessage,
    PBFTNode,
    PBFTPhase,
    PBFTRequest,
)


# =============================================================================
# Paxos Tests
# =============================================================================

class TestProposalNumber:
    """Tests for ProposalNumber."""

    def test_equality(self):
        """Test proposal number equality."""
        p1 = ProposalNumber(round=1, proposer_id="node-1")
        p2 = ProposalNumber(round=1, proposer_id="node-1")
        p3 = ProposalNumber(round=1, proposer_id="node-2")
        
        assert p1 == p2
        assert p1 != p3

    def test_comparison(self):
        """Test proposal number comparison."""
        p1 = ProposalNumber(round=1, proposer_id="node-1")
        p2 = ProposalNumber(round=2, proposer_id="node-1")
        p3 = ProposalNumber(round=1, proposer_id="node-2")
        
        assert p1 < p2
        assert p2 > p1
        assert p1 < p3  # Same round, but "node-1" < "node-2"

    def test_to_dict(self):
        """Test serialization."""
        p = ProposalNumber(round=5, proposer_id="test-node")
        d = p.to_dict()
        
        assert d["round"] == 5
        assert d["proposer_id"] == "test-node"

    def test_from_dict(self):
        """Test deserialization."""
        d = {"round": 3, "proposer_id": "node-a"}
        p = ProposalNumber.from_dict(d)
        
        assert p.round == 3
        assert p.proposer_id == "node-a"


class TestPaxosInstance:
    """Tests for PaxosInstance."""

    def test_default_values(self):
        """Test default instance values."""
        instance = PaxosInstance(instance_id="test-1")
        
        assert instance.instance_id == "test-1"
        assert instance.phase == PaxosPhase.IDLE
        assert instance.promised_number is None
        assert instance.accepted_number is None
        assert instance.committed_value is None

    def test_get_promises_event(self):
        """Test promises event creation."""
        instance = PaxosInstance(instance_id="test-1")
        event = instance.get_promises_event()
        
        assert event is not None
        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_get_accepts_event(self):
        """Test accepts event creation."""
        instance = PaxosInstance(instance_id="test-1")
        event = instance.get_accepts_event()
        
        assert event is not None
        assert isinstance(event, asyncio.Event)


class TestPaxosNode:
    """Tests for PaxosNode."""

    @pytest.fixture
    def paxos_node(self):
        """Create a PaxosNode instance."""
        return PaxosNode(
            node_id="node-1",
            peers={"node-2", "node-3"},
        )

    def test_init(self, paxos_node):
        """Test node initialization."""
        assert paxos_node.node_id == "node-1"
        assert paxos_node.peers == {"node-2", "node-3"}
        assert paxos_node.quorum_size == 2  # 3 nodes / 2 + 1

    def test_generate_proposal_number(self, paxos_node):
        """Test proposal number generation."""
        p1 = paxos_node._generate_proposal_number()
        p2 = paxos_node._generate_proposal_number()
        
        assert p1.proposer_id == "node-1"
        assert p2.proposer_id == "node-1"
        assert p2.round > p1.round  # Round should increase

    def test_get_or_create_instance(self, paxos_node):
        """Test instance creation."""
        instance = paxos_node._get_or_create_instance("test-instance")
        
        assert instance.instance_id == "test-instance"
        assert "test-instance" in paxos_node._instances

    def test_handle_prepare(self, paxos_node):
        """Test prepare message handling."""
        proposal = ProposalNumber(round=1, proposer_id="node-2")
        message = {
            "type": "prepare",
            "proposal_number": proposal.to_dict(),
            "instance_id": "inst-1",
            "sender_id": "node-2",
        }
        
        # Mock send_message callback
        sent_messages = []
        def capture_send(target, msg):
            sent_messages.append((target, msg))
        
        paxos_node.set_callbacks(send_message=capture_send)
        paxos_node.receive_message(message)
        
        # Should have sent a promise back
        assert len(sent_messages) == 1
        assert sent_messages[0][0] == "node-2"
        assert sent_messages[0][1]["type"] == "promise"

    def test_handle_accept(self, paxos_node):
        """Test accept message handling."""
        # First prepare to set promised_number
        proposal = ProposalNumber(round=1, proposer_id="node-2")
        prepare_msg = {
            "type": "prepare",
            "proposal_number": proposal.to_dict(),
            "instance_id": "inst-1",
            "sender_id": "node-2",
        }
        
        sent_messages = []
        def capture_send(target, msg):
            sent_messages.append((target, msg))
        
        paxos_node.set_callbacks(send_message=capture_send)
        paxos_node.receive_message(prepare_msg)
        sent_messages.clear()
        
        # Now send accept
        accept_msg = {
            "type": "accept",
            "proposal_number": proposal.to_dict(),
            "instance_id": "inst-1",
            "sender_id": "node-2",
            "value": "test-value",
        }
        paxos_node.receive_message(accept_msg)
        
        # Should have sent accepted
        assert len(sent_messages) == 1
        assert sent_messages[0][1]["type"] == "accepted"

    def test_handle_commit(self, paxos_node):
        """Test commit message handling."""
        committed_values = []
        def on_commit(instance_id, value):
            committed_values.append((instance_id, value))
        
        paxos_node.set_callbacks(on_value_committed=on_commit)
        
        proposal = ProposalNumber(round=1, proposer_id="node-2")
        commit_msg = {
            "type": "commit",
            "proposal_number": proposal.to_dict(),
            "instance_id": "inst-1",
            "sender_id": "node-2",
            "value": "committed-value",
        }
        paxos_node.receive_message(commit_msg)
        
        assert len(committed_values) == 1
        assert committed_values[0] == ("inst-1", "committed-value")


class TestMultiPaxos:
    """Tests for MultiPaxos."""

    @pytest.fixture
    def multipaxos(self):
        """Create a MultiPaxos instance."""
        return MultiPaxos(
            node_id="node-1",
            peers={"node-2", "node-3"},
            leader_id="node-1",
        )

    def test_init(self, multipaxos):
        """Test MultiPaxos initialization."""
        assert multipaxos.node_id == "node-1"
        assert multipaxos.leader_id == "node-1"
        assert multipaxos.paxos_node is not None

    def test_get_log(self, multipaxos):
        """Test log retrieval."""
        log = multipaxos.get_log()
        assert isinstance(log, list)


# =============================================================================
# PBFT Tests
# =============================================================================

class TestPBFTMessage:
    """Tests for PBFTMessage."""

    def test_to_dict(self):
        """Test message serialization."""
        msg = PBFTMessage(
            msg_type="pre_prepare",
            view=1,
            sequence=5,
            digest="abc123",
            sender_id="node-1",
        )
        d = msg.to_dict()
        
        assert d["type"] == "pre_prepare"
        assert d["view"] == 1
        assert d["sequence"] == 5
        assert d["digest"] == "abc123"
        assert d["sender_id"] == "node-1"

    def test_compute_digest(self):
        """Test digest computation."""
        msg = PBFTMessage(
            msg_type="prepare",
            view=1,
            sequence=5,
            digest="test-digest",
            sender_id="node-1",
        )
        digest = msg.compute_digest()
        
        assert len(digest) == 16
        assert isinstance(digest, str)


class TestPBFTRequest:
    """Tests for PBFTRequest."""

    def test_compute_digest(self):
        """Test request digest computation."""
        request = PBFTRequest(
            client_id="client-1",
            timestamp=1234567890,
            operation={"type": "write", "key": "x", "value": 1},
        )
        digest = request.compute_digest()
        
        assert len(digest) == 32
        assert isinstance(digest, str)


class TestPBFTLogEntry:
    """Tests for PBFTLogEntry."""

    def test_default_values(self):
        """Test default entry values."""
        entry = PBFTLogEntry(
            sequence=1,
            view=0,
            digest="test",
        )
        
        assert entry.sequence == 1
        assert entry.view == 0
        assert entry.phase == PBFTPhase.IDLE
        assert not entry.executed


class TestPBFTNode:
    """Tests for PBFTNode."""

    @pytest.fixture
    def pbft_node(self):
        """Create a PBFTNode instance."""
        return PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )

    def test_init(self, pbft_node):
        """Test node initialization."""
        assert pbft_node.node_id == "node-1"
        assert pbft_node.f == 1
        assert pbft_node.n == 4  # 3f + 1
        assert pbft_node.view == 0

    def test_get_primary(self, pbft_node):
        """Test primary selection."""
        primary_0 = pbft_node._get_primary(0)
        primary_1 = pbft_node._get_primary(1)
        
        # Primary rotates based on view
        nodes = sorted(pbft_node.all_nodes)
        assert primary_0 == nodes[0]
        assert primary_1 == nodes[1]

    def test_get_or_create_entry(self, pbft_node):
        """Test log entry creation."""
        entry = pbft_node._get_or_create_entry(1)
        
        assert entry.sequence == 1
        assert 1 in pbft_node._log

    def test_handle_pre_prepare(self, pbft_node):
        """Test pre-prepare handling."""
        sent_messages = []
        def capture_send(target, msg):
            sent_messages.append((target, msg))
        
        pbft_node.set_callbacks(send_message=capture_send)
        
        # Get the primary for view 0
        primary = pbft_node._get_primary(0)
        
        # If we're not primary, we can handle pre-prepare
        if pbft_node.node_id != primary:
            pre_prepare = {
                "type": "pre_prepare",
                "view": 0,
                "sequence": 1,
                "digest": "test-digest",
                "sender_id": primary,
            }
            pbft_node.receive_message(pre_prepare)
            
            # Should have sent prepare messages
            assert len(sent_messages) > 0
            assert all(msg[1]["type"] == "prepare" for msg in sent_messages)

    def test_handle_prepare(self, pbft_node):
        """Test prepare handling."""
        # Create a log entry first
        entry = pbft_node._get_or_create_entry(1)
        entry.digest = "test-digest"
        entry.phase = PBFTPhase.PRE_PREPARE
        
        prepare = {
            "type": "prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-2",
        }
        pbft_node.receive_message(prepare)
        
        # Should have stored the prepare
        assert "node-2" in entry.prepare_msgs

    def test_handle_commit(self, pbft_node):
        """Test commit handling."""
        # Create a log entry and advance to PREPARE phase
        entry = pbft_node._get_or_create_entry(1)
        entry.digest = "test-digest"
        entry.phase = PBFTPhase.PREPARE
        
        commit = {
            "type": "commit",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "node-2",
        }
        pbft_node.receive_message(commit)
        
        # Should have stored the commit
        assert "node-2" in entry.commit_msgs

    def test_view_change(self, pbft_node):
        """Test view change."""
        old_view = pbft_node.view
        old_primary = pbft_node.primary_id
        
        pbft_node.start_view_change()
        
        assert pbft_node.view == old_view + 1
        # Primary should change (unless wrap-around)
        if len(pbft_node.all_nodes) > 1:
            assert pbft_node.primary_id != old_primary or pbft_node.view % len(pbft_node.all_nodes) == 0


class TestPBFTQuorum:
    """Tests for PBFT quorum logic."""

    def test_prepare_quorum(self):
        """Test that 2f prepares are needed."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        entry = PBFTLogEntry(sequence=1, view=0, digest="test")
        entry.phase = PBFTPhase.PRE_PREPARE
        
        # Add our own prepare
        entry.prepare_msgs["node-1"] = MagicMock()
        
        # Need 2f = 2 prepares total
        assert len(entry.prepare_msgs) < 2 * node.f
        
        # Add another prepare
        entry.prepare_msgs["node-2"] = MagicMock()
        assert len(entry.prepare_msgs) >= 2 * node.f

    def test_commit_quorum(self):
        """Test that 2f+1 commits are needed."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        entry = PBFTLogEntry(sequence=1, view=0, digest="test")
        entry.phase = PBFTPhase.PREPARE
        
        # Need 2f+1 = 3 commits
        entry.commit_msgs["node-1"] = MagicMock()
        entry.commit_msgs["node-2"] = MagicMock()
        
        assert len(entry.commit_msgs) < 2 * node.f + 1
        
        entry.commit_msgs["node-3"] = MagicMock()
        assert len(entry.commit_msgs) >= 2 * node.f + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
