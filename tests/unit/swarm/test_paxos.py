"""
Unit Tests for Paxos Consensus Algorithm

Tests the Paxos implementation including:
- Proposal number generation and comparison
- Phase 1 (Prepare/Promise)
- Phase 2 (Accept/Accepted)
- Commit handling
- Event-based quorum waiting
"""

import asyncio
import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.swarm.paxos import (
    PaxosPhase,
    ProposalNumber,
    PaxosMessage,
    PaxosInstance,
    PaxosNode,
    MultiPaxos,
)


# ==================== Fixtures ====================

@pytest.fixture
def proposal_number():
    """Create a sample proposal number."""
    return ProposalNumber(round=1, proposer_id="node-1")


@pytest.fixture
def paxos_instance():
    """Create a sample Paxos instance."""
    return PaxosInstance(instance_id="test-instance")


@pytest.fixture
def paxos_node():
    """Create a Paxos node for testing."""
    return PaxosNode(
        node_id="node-1",
        peers={"node-2", "node-3"},
    )


@pytest.fixture
def paxos_cluster():
    """Create a 3-node Paxos cluster for testing."""
    nodes = {}
    for i in range(1, 4):
        node_id = f"node-{i}"
        peers = {f"node-{j}" for j in range(1, 4) if j != i}
        nodes[node_id] = PaxosNode(node_id=node_id, peers=peers)
    return nodes


# ==================== ProposalNumber Tests ====================

class TestProposalNumber:
    """Tests for ProposalNumber class."""
    
    def test_creation(self):
        """Test proposal number creation."""
        pn = ProposalNumber(round=5, proposer_id="node-1")
        assert pn.round == 5
        assert pn.proposer_id == "node-1"
    
    def test_comparison_by_round(self):
        """Test comparison based on round number."""
        pn1 = ProposalNumber(round=1, proposer_id="node-1")
        pn2 = ProposalNumber(round=2, proposer_id="node-1")
        
        assert pn1 < pn2
        assert pn2 > pn1
        assert pn1 <= pn2
        assert pn2 >= pn1
    
    def test_comparison_by_proposer_id(self):
        """Test comparison based on proposer ID when rounds are equal."""
        pn1 = ProposalNumber(round=1, proposer_id="node-1")
        pn2 = ProposalNumber(round=1, proposer_id="node-2")
        
        assert pn1 < pn2  # "node-1" < "node-2" lexicographically
        assert pn2 > pn1
    
    def test_equality(self):
        """Test equality comparison."""
        pn1 = ProposalNumber(round=1, proposer_id="node-1")
        pn2 = ProposalNumber(round=1, proposer_id="node-1")
        pn3 = ProposalNumber(round=2, proposer_id="node-1")
        
        assert pn1 == pn2
        assert pn1 != pn3
    
    def test_hash(self):
        """Test that proposal numbers are hashable."""
        pn1 = ProposalNumber(round=1, proposer_id="node-1")
        pn2 = ProposalNumber(round=1, proposer_id="node-1")
        
        # Equal objects should have equal hashes
        assert hash(pn1) == hash(pn2)
        
        # Can be used in sets
        s = {pn1, pn2}
        assert len(s) == 1
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        pn = ProposalNumber(round=5, proposer_id="node-1")
        data = pn.to_dict()
        
        assert data["round"] == 5
        assert data["proposer_id"] == "node-1"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {"round": 5, "proposer_id": "node-1"}
        pn = ProposalNumber.from_dict(data)
        
        assert pn.round == 5
        assert pn.proposer_id == "node-1"


# ==================== PaxosMessage Tests ====================

class TestPaxosMessage:
    """Tests for PaxosMessage class."""
    
    def test_creation(self, proposal_number):
        """Test message creation."""
        msg = PaxosMessage(
            msg_type="prepare",
            proposal_number=proposal_number,
            instance_id="instance-1",
            sender_id="node-1",
        )
        
        assert msg.msg_type == "prepare"
        assert msg.proposal_number == proposal_number
        assert msg.instance_id == "instance-1"
        assert msg.sender_id == "node-1"
        assert msg.value is None
    
    def test_to_dict(self, proposal_number):
        """Test message serialization."""
        msg = PaxosMessage(
            msg_type="accept",
            proposal_number=proposal_number,
            instance_id="instance-1",
            sender_id="node-1",
            value={"key": "value"},
        )
        
        data = msg.to_dict()
        
        assert data["type"] == "accept"
        assert data["proposal_number"]["round"] == 1
        assert data["instance_id"] == "instance-1"
        assert data["sender_id"] == "node-1"
        assert data["value"] == {"key": "value"}
        assert "timestamp" in data


# ==================== PaxosInstance Tests ====================

class TestPaxosInstance:
    """Tests for PaxosInstance class."""
    
    def test_creation(self):
        """Test instance creation."""
        instance = PaxosInstance(instance_id="test-instance")
        
        assert instance.instance_id == "test-instance"
        assert instance.phase == PaxosPhase.IDLE
        assert instance.promised_number is None
        assert instance.accepted_number is None
        assert instance.committed_value is None
    
    def test_get_promises_event(self, paxos_instance):
        """Test that promises event is created lazily."""
        event1 = paxos_instance.get_promises_event()
        assert event1 is not None
        assert isinstance(event1, asyncio.Event)
        
        # Same event returned on subsequent calls
        event2 = paxos_instance.get_promises_event()
        assert event1 is event2
    
    def test_get_accepts_event(self, paxos_instance):
        """Test that accepts event is created lazily."""
        event1 = paxos_instance.get_accepts_event()
        assert event1 is not None
        assert isinstance(event1, asyncio.Event)
        
        # Same event returned on subsequent calls
        event2 = paxos_instance.get_accepts_event()
        assert event1 is event2
    
    def test_events_not_set_initially(self, paxos_instance):
        """Test that events are not set initially."""
        promises_event = paxos_instance.get_promises_event()
        accepts_event = paxos_instance.get_accepts_event()
        
        assert not promises_event.is_set()
        assert not accepts_event.is_set()


# ==================== PaxosNode Tests ====================

class TestPaxosNode:
    """Tests for PaxosNode class."""
    
    def test_creation(self):
        """Test node creation."""
        node = PaxosNode(
            node_id="node-1",
            peers={"node-2", "node-3"},
        )
        
        assert node.node_id == "node-1"
        assert node.peers == {"node-2", "node-3"}
        assert node.all_nodes == {"node-1", "node-2", "node-3"}
        assert node.quorum_size == 2  # (3 // 2) + 1
    
    def test_custom_quorum_size(self):
        """Test custom quorum size."""
        node = PaxosNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4", "node-5"},
            quorum_size=3,
        )
        
        assert node.quorum_size == 3
    
    def test_generate_proposal_number(self, paxos_node):
        """Test proposal number generation."""
        pn1 = paxos_node._generate_proposal_number()
        pn2 = paxos_node._generate_proposal_number()
        
        # Each proposal number should be unique
        assert pn1 != pn2
        
        # Round should increment
        assert pn2.round > pn1.round
        
        # Proposer ID should be the node's ID
        assert pn1.proposer_id == paxos_node.node_id
        assert pn2.proposer_id == paxos_node.node_id
    
    def test_get_or_create_instance(self, paxos_node):
        """Test instance creation and retrieval."""
        instance1 = paxos_node._get_or_create_instance("instance-1")
        
        assert instance1.instance_id == "instance-1"
        
        # Same instance returned on subsequent calls
        instance2 = paxos_node._get_or_create_instance("instance-1")
        assert instance1 is instance2
        
        # Different instance for different ID
        instance3 = paxos_node._get_or_create_instance("instance-2")
        assert instance1 is not instance3


class TestPaxosNodeProposer:
    """Tests for PaxosNode proposer role."""
    
    @pytest.mark.asyncio
    async def test_propose_returns_early_if_committed(self, paxos_node):
        """Test that propose returns early if instance already committed."""
        instance = paxos_node._get_or_create_instance("instance-1")
        instance.phase = PaxosPhase.COMMITTED
        instance.committed_value = "already-decided"
        
        success, value = await paxos_node.propose("new-value", "instance-1")
        
        assert success is True
        assert value == "already-decided"
    
    @pytest.mark.asyncio
    async def test_propose_timeout_on_promises(self, paxos_node):
        """Test that propose times out if no promises received."""
        # No messages will be sent or received
        paxos_node.set_callbacks(send_message=lambda t, m: None)
        
        success, value = await paxos_node.propose("test-value")
        
        assert success is False
        assert value is None
    
    @pytest.mark.asyncio
    async def test_propose_success_with_quorum(self, paxos_node):
        """Test successful proposal with quorum."""
        messages_sent = []
        
        def capture_message(target, msg):
            messages_sent.append((target, msg))
        
        paxos_node.set_callbacks(send_message=capture_message)
        
        # Simulate receiving promises from peers
        async def simulate_promises():
            await asyncio.sleep(0.05)  # Small delay
            
            instance_id = None
            for target, msg in messages_sent:
                if msg["type"] == "prepare":
                    instance_id = msg["instance_id"]
                    break
            
            if instance_id:
                instance = paxos_node._get_or_create_instance(instance_id)
                # Simulate promises from 2 peers (quorum)
                for peer in paxos_node.peers:
                    instance.promises_received.add(peer)
                    instance.promise_values[peer] = (None, None)
                instance.get_promises_event().set()
                
                # Wait for accept phase
                await asyncio.sleep(0.05)
                
                # Simulate accepts from 2 peers
                for peer in paxos_node.peers:
                    instance.accepts_received.add(peer)
                instance.get_accepts_event().set()
        
        # Run simulation concurrently with propose
        propose_task = asyncio.create_task(paxos_node.propose("test-value"))
        simulate_task = asyncio.create_task(simulate_promises())
        
        success, value = await propose_task
        await simulate_task
        
        assert success is True
        assert value == "test-value"


class TestPaxosNodeAcceptor:
    """Tests for PaxosNode acceptor role."""
    
    def test_handle_prepare_promises(self, paxos_node):
        """Test handling prepare message."""
        messages_sent = []
        paxos_node.set_callbacks(send_message=lambda t, m: messages_sent.append((t, m)))
        
        prepare_msg = {
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
        }
        
        paxos_node.receive_message(prepare_msg)
        
        # Should send promise back
        assert len(messages_sent) == 1
        target, msg = messages_sent[0]
        assert target == "node-2"
        assert msg["type"] == "promise"
    
    def test_handle_prepare_rejects_lower_proposal(self, paxos_node):
        """Test that acceptor rejects lower proposal numbers."""
        messages_sent = []
        paxos_node.set_callbacks(send_message=lambda t, m: messages_sent.append((t, m)))
        
        # First prepare with round 2
        paxos_node.receive_message({
            "type": "prepare",
            "proposal_number": {"round": 2, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
        })
        messages_sent.clear()
        
        # Second prepare with round 1 (should be rejected)
        paxos_node.receive_message({
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "node-3"},
            "instance_id": "instance-1",
            "sender_id": "node-3",
        })
        
        # Should not send promise for lower proposal
        assert len(messages_sent) == 0
    
    def test_handle_accept(self, paxos_node):
        """Test handling accept message."""
        messages_sent = []
        paxos_node.set_callbacks(send_message=lambda t, m: messages_sent.append((t, m)))
        
        # First prepare to set promised_number
        paxos_node.receive_message({
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
        })
        messages_sent.clear()
        
        # Then accept
        paxos_node.receive_message({
            "type": "accept",
            "proposal_number": {"round": 1, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": "test-value",
        })
        
        # Should send accepted back
        assert len(messages_sent) == 1
        target, msg = messages_sent[0]
        assert target == "node-2"
        assert msg["type"] == "accepted"
        
        # Value should be accepted
        instance = paxos_node.get_instance("instance-1")
        assert instance.accepted_value == "test-value"


class TestPaxosNodeLearner:
    """Tests for PaxosNode learner role."""
    
    def test_handle_promise(self, paxos_node):
        """Test handling promise message."""
        paxos_node.receive_message({
            "type": "promise",
            "proposal_number": {"round": 1, "proposer_id": "node-1"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": None,
        })
        
        instance = paxos_node.get_instance("instance-1")
        assert "node-2" in instance.promises_received
    
    def test_handle_promise_signals_event_at_quorum(self, paxos_node):
        """Test that promise handler signals event when quorum reached."""
        instance = paxos_node._get_or_create_instance("instance-1")
        event = instance.get_promises_event()
        
        # Add promises up to quorum (2 for 3 nodes)
        instance.promises_received.add("node-1")  # Self
        
        # This should trigger the event
        paxos_node.receive_message({
            "type": "promise",
            "proposal_number": {"round": 1, "proposer_id": "node-1"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": None,
        })
        
        assert event.is_set()
    
    def test_handle_accepted(self, paxos_node):
        """Test handling accepted message."""
        paxos_node.receive_message({
            "type": "accepted",
            "proposal_number": {"round": 1, "proposer_id": "node-1"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": "test-value",
        })
        
        instance = paxos_node.get_instance("instance-1")
        assert "node-2" in instance.accepts_received
    
    def test_handle_accepted_signals_event_at_quorum(self, paxos_node):
        """Test that accepted handler signals event when quorum reached."""
        instance = paxos_node._get_or_create_instance("instance-1")
        event = instance.get_accepts_event()
        
        # Add accepts up to quorum
        instance.accepts_received.add("node-1")  # Self
        
        # This should trigger the event
        paxos_node.receive_message({
            "type": "accepted",
            "proposal_number": {"round": 1, "proposer_id": "node-1"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": "test-value",
        })
        
        assert event.is_set()
    
    def test_handle_commit(self, paxos_node):
        """Test handling commit message."""
        committed_values = []
        paxos_node.set_callbacks(
            on_value_committed=lambda iid, val: committed_values.append((iid, val))
        )
        
        paxos_node.receive_message({
            "type": "commit",
            "proposal_number": {"round": 1, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
            "value": "committed-value",
        })
        
        instance = paxos_node.get_instance("instance-1")
        assert instance.phase == PaxosPhase.COMMITTED
        assert instance.committed_value == "committed-value"
        assert len(committed_values) == 1


# ==================== MultiPaxos Tests ====================

class TestMultiPaxos:
    """Tests for MultiPaxos class."""
    
    def test_creation(self):
        """Test MultiPaxos creation."""
        mp = MultiPaxos(
            node_id="node-1",
            peers={"node-2", "node-3"},
            leader_id="node-1",
        )
        
        assert mp.node_id == "node-1"
        assert mp.leader_id == "node-1"
        assert mp.paxos_node is not None
    
    @pytest.mark.asyncio
    async def test_propose_non_leader(self):
        """Test that non-leader cannot propose."""
        mp = MultiPaxos(
            node_id="node-2",
            peers={"node-1", "node-3"},
            leader_id="node-1",
        )
        
        success, value = await mp.propose("test-value")
        
        assert success is False
        assert value is None
    
    def test_receive_message_forwards_to_paxos_node(self):
        """Test that messages are forwarded to underlying PaxosNode."""
        mp = MultiPaxos(node_id="node-1", peers={"node-2", "node-3"})
        
        # This should not raise
        mp.receive_message({
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "node-2"},
            "instance_id": "instance-1",
            "sender_id": "node-2",
        })
    
    def test_get_log(self):
        """Test getting the committed log."""
        mp = MultiPaxos(node_id="node-1", peers={"node-2", "node-3"})
        
        # Simulate committed values
        mp._on_value_committed("instance-1", "value-1")
        mp._on_value_committed("instance-2", "value-2")
        
        log = mp.get_log()
        
        assert len(log) == 2
        assert log[0] == ("instance-1", "value-1")
        assert log[1] == ("instance-2", "value-2")
    
    def test_get_log_entry(self):
        """Test getting a specific log entry."""
        mp = MultiPaxos(node_id="node-1", peers={"node-2", "node-3"})
        
        mp._on_value_committed("instance-1", "value-1")
        mp._on_value_committed("instance-2", "value-2")
        
        assert mp.get_log_entry(0) == "value-1"
        assert mp.get_log_entry(1) == "value-2"
        assert mp.get_log_entry(99) is None  # Out of bounds


# ==================== Event-Based Waiting Tests ====================

class TestEventBasedWaiting:
    """Tests for the event-based quorum waiting mechanism."""
    
    @pytest.mark.asyncio
    async def test_wait_for_promises_quorum(self, paxos_node):
        """Test waiting for promises quorum with events."""
        instance = paxos_node._get_or_create_instance("test-instance")
        
        async def signal_after_delay():
            await asyncio.sleep(0.05)
            instance.promises_received.add("node-2")
            instance.promises_received.add("node-3")
            instance.get_promises_event().set()
        
        # Start waiting and signaling concurrently
        signal_task = asyncio.create_task(signal_after_delay())
        
        start = asyncio.get_event_loop().time()
        await paxos_node._wait_for_quorum(instance, "promises")
        elapsed = asyncio.get_event_loop().time() - start
        
        await signal_task
        
        # Should complete quickly (not busy-wait)
        assert elapsed < 0.2
        assert len(instance.promises_received) >= paxos_node.quorum_size
    
    @pytest.mark.asyncio
    async def test_wait_for_accepts_quorum(self, paxos_node):
        """Test waiting for accepts quorum with events."""
        instance = paxos_node._get_or_create_instance("test-instance")
        
        async def signal_after_delay():
            await asyncio.sleep(0.05)
            instance.accepts_received.add("node-2")
            instance.accepts_received.add("node-3")
            instance.get_accepts_event().set()
        
        signal_task = asyncio.create_task(signal_after_delay())
        
        start = asyncio.get_event_loop().time()
        await paxos_node._wait_for_quorum(instance, "accepts")
        elapsed = asyncio.get_event_loop().time() - start
        
        await signal_task
        
        assert elapsed < 0.2
        assert len(instance.accepts_received) >= paxos_node.quorum_size
    
    @pytest.mark.asyncio
    async def test_immediate_return_if_quorum_already_reached(self, paxos_node):
        """Test that waiting returns immediately if quorum already reached."""
        instance = paxos_node._get_or_create_instance("test-instance")
        
        # Pre-populate promises
        instance.promises_received.add("node-2")
        instance.promises_received.add("node-3")
        
        start = asyncio.get_event_loop().time()
        await paxos_node._wait_for_quorum(instance, "promises")
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should return immediately
        assert elapsed < 0.01


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
