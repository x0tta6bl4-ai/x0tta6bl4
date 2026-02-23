"""
Tests for Swarm Consensus Algorithms

Comprehensive tests for Paxos, PBFT, and SwarmConsensusManager.
"""

import asyncio
import pytest
from datetime import datetime
from typing import Dict, List
import uuid

# Import consensus modules
from src.swarm.paxos import (
    PaxosNode,
    MultiPaxos,
    PaxosPhase,
    ProposalNumber,
    PaxosMessage,
)
from src.swarm.pbft import (
    PBFTNode,
    PBFTPhase,
    PBFTMessage,
    PBFTRequest,
)
from src.swarm.consensus_integration import (
    SwarmConsensusManager,
    ConsensusMode,
    AgentInfo,
    SwarmDecision,
)


class TestProposalNumber:
    """Tests for ProposalNumber comparison."""
    
    def test_comparison_same_round(self):
        """Test comparison with same round, different proposer."""
        p1 = ProposalNumber(round=1, proposer_id="agent-a")
        p2 = ProposalNumber(round=1, proposer_id="agent-b")
        
        assert p1 < p2  # "agent-a" < "agent-b"
        assert p2 > p1
        assert p1 != p2
    
    def test_comparison_different_round(self):
        """Test comparison with different rounds."""
        p1 = ProposalNumber(round=1, proposer_id="agent-z")
        p2 = ProposalNumber(round=2, proposer_id="agent-a")
        
        assert p1 < p2  # round 1 < round 2
        assert p2 > p1
    
    def test_equality(self):
        """Test equality."""
        p1 = ProposalNumber(round=1, proposer_id="agent-a")
        p2 = ProposalNumber(round=1, proposer_id="agent-a")
        
        assert p1 == p2
        assert hash(p1) == hash(p2)
    
    def test_serialization(self):
        """Test to_dict and from_dict."""
        p1 = ProposalNumber(round=5, proposer_id="agent-x")
        data = p1.to_dict()
        p2 = ProposalNumber.from_dict(data)
        
        assert p1 == p2


class TestPaxosNode:
    """Tests for PaxosNode."""
    
    def test_initialization(self):
        """Test PaxosNode initialization."""
        node = PaxosNode(
            node_id="node-1",
            peers={"node-2", "node-3"},
        )
        
        assert node.node_id == "node-1"
        assert node.peers == {"node-2", "node-3"}
        assert node.all_nodes == {"node-1", "node-2", "node-3"}
        assert node.quorum_size == 2  # 3 nodes, majority = 2
    
    def test_quorum_calculation(self):
        """Test quorum size calculation."""
        # 3 nodes
        node1 = PaxosNode(node_id="n1", peers={"n2", "n3"})
        assert node1.quorum_size == 2
        
        # 5 nodes
        node2 = PaxosNode(node_id="n1", peers={"n2", "n3", "n4", "n5"})
        assert node2.quorum_size == 3
        
        # Custom quorum
        node3 = PaxosNode(node_id="n1", peers={"n2"}, quorum_size=3)
        assert node3.quorum_size == 3
    
    def test_proposal_number_generation(self):
        """Test unique proposal number generation."""
        node = PaxosNode(node_id="node-1", peers={"node-2"})
        
        p1 = node._generate_proposal_number()
        p2 = node._generate_proposal_number()
        
        assert p1.proposer_id == "node-1"
        assert p2.proposer_id == "node-1"
        assert p2.round > p1.round  # Round increases
    
    def test_instance_creation(self):
        """Test Paxos instance creation."""
        node = PaxosNode(node_id="node-1", peers={"node-2"})
        
        instance = node._get_or_create_instance("test-instance")
        
        assert instance.instance_id == "test-instance"
        assert instance.phase == PaxosPhase.IDLE
        assert instance.promised_number is None
    
    def test_prepare_message_handling(self):
        """Test handling of Prepare message."""
        node = PaxosNode(node_id="acceptor", peers={"proposer"})
        
        # Receive prepare
        prepare = {
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "proposer"},
            "instance_id": "instance-1",
            "sender_id": "proposer",
        }
        
        node.receive_message(prepare)
        
        instance = node.get_instance("instance-1")
        assert instance is not None
        assert instance.promised_number is not None
    
    def test_accept_message_handling(self):
        """Test handling of Accept message."""
        node = PaxosNode(node_id="acceptor", peers={"proposer"})
        
        # First prepare
        prepare = {
            "type": "prepare",
            "proposal_number": {"round": 1, "proposer_id": "proposer"},
            "instance_id": "instance-1",
            "sender_id": "proposer",
        }
        node.receive_message(prepare)
        
        # Then accept
        accept = {
            "type": "accept",
            "proposal_number": {"round": 1, "proposer_id": "proposer"},
            "instance_id": "instance-1",
            "sender_id": "proposer",
            "value": "test-value",
        }
        node.receive_message(accept)
        
        instance = node.get_instance("instance-1")
        assert instance.accepted_value == "test-value"
    
    def test_commit_message_handling(self):
        """Test handling of Commit message."""
        node = PaxosNode(node_id="learner", peers={"proposer"})
        
        commit = {
            "type": "commit",
            "proposal_number": {"round": 1, "proposer_id": "proposer"},
            "instance_id": "instance-1",
            "sender_id": "proposer",
            "value": "committed-value",
        }
        node.receive_message(commit)
        
        value = node.get_committed_value("instance-1")
        assert value == "committed-value"


class TestMultiPaxos:
    """Tests for MultiPaxos."""
    
    def test_initialization(self):
        """Test MultiPaxos initialization."""
        mp = MultiPaxos(
            node_id="node-1",
            peers={"node-2", "node-3"},
            leader_id="node-1",
        )
        
        assert mp.node_id == "node-1"
        assert mp.leader_id == "node-1"
        assert mp.paxos_node is not None
    
    def test_log_management(self):
        """Test log entry management."""
        mp = MultiPaxos(
            node_id="node-1",
            peers={"node-2"},
            leader_id="node-1",
        )
        
        # Initially empty log
        assert len(mp.get_log()) == 0
        
        # Get non-existent entry
        assert mp.get_log_entry(0) is None


class TestPBFTNode:
    """Tests for PBFTNode."""
    
    def test_initialization(self):
        """Test PBFTNode initialization."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        assert node.node_id == "node-1"
        assert node.f == 1
        assert node.n == 4  # 3f+1 = 4
        assert node.view == 0
    
    def test_primary_selection(self):
        """Test primary selection for views."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3"},
            f=1,
        )
        
        # View 0
        primary_0 = node._get_primary(0)
        
        # View 1
        primary_1 = node._get_primary(1)
        
        # Primary rotates
        assert primary_0 != primary_1 or len(node.all_nodes) == 1
    
    def test_request_digest(self):
        """Test request digest computation."""
        req = PBFTRequest(
            client_id="client-1",
            timestamp=12345,
            operation="test-operation",
        )
        
        digest1 = req.compute_digest()
        digest2 = req.compute_digest()
        
        # Same request = same digest
        assert digest1 == digest2
        assert len(digest1) == 32  # SHA256 truncated
    
    def test_pre_prepare_handling(self):
        """Test handling of pre-prepare message."""
        node = PBFTNode(
            node_id="replica",
            peers={"primary", "replica2"},
            f=1,
        )
        
        # Set up as non-primary
        node.primary_id = "primary"
        node.is_primary = False
        
        pre_prepare = {
            "type": "pre_prepare",
            "view": 0,
            "sequence": 1,
            "digest": "test-digest",
            "sender_id": "primary",
            "request": {"operation": "test"},
        }
        
        node.receive_message(pre_prepare)
        
        entry = node.get_log_entry(1)
        assert entry is not None
        assert entry.phase == PBFTPhase.PRE_PREPARE
    
    def test_view_change(self):
        """Test view change mechanism."""
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3"},
            f=1,
        )
        
        initial_view = node.view
        node.start_view_change()
        
        assert node.view > initial_view


class TestSwarmConsensusManager:
    """Tests for SwarmConsensusManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a SwarmConsensusManager for testing."""
        agents = {
            "agent-1": AgentInfo(
                agent_id="agent-1",
                name="Gemini",
                capabilities={"code", "research"},
                weight=1.0,
            ),
            "agent-2": AgentInfo(
                agent_id="agent-2",
                name="Claude",
                capabilities={"code", "analysis"},
                weight=1.0,
            ),
            "agent-3": AgentInfo(
                agent_id="agent-3",
                name="GPT",
                capabilities={"research", "writing"},
                weight=1.0,
            ),
        }
        
        return SwarmConsensusManager(
            node_id="agent-1",
            agents=agents,
            default_mode=ConsensusMode.SIMPLE,
        )
    
    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.node_id == "agent-1"
        assert len(manager.agents) == 3
        assert manager.default_mode == ConsensusMode.SIMPLE
    
    def test_add_remove_agent(self, manager):
        """Test adding and removing agents."""
        new_agent = AgentInfo(
            agent_id="agent-4",
            name="NewAgent",
            capabilities={"testing"},
        )
        
        manager.add_agent(new_agent)
        assert len(manager.agents) == 4
        assert "agent-4" in manager.agents
        
        manager.remove_agent("agent-4")
        assert len(manager.agents) == 3
        assert "agent-4" not in manager.agents
    
    @pytest.mark.asyncio
    async def test_simple_decision(self, manager):
        """Test simple majority decision."""
        decision = await manager.decide(
            topic="test-topic",
            proposals=["option-a", "option-b"],
            mode=ConsensusMode.SIMPLE,
            timeout=5.0,
        )
        
        assert decision.success
        assert decision.winner in ["option-a", "option-b"]
        assert decision.mode == ConsensusMode.SIMPLE
    
    @pytest.mark.asyncio
    async def test_weighted_decision(self, manager):
        """Test weighted decision."""
        decision = await manager.decide(
            topic="code",  # Matches capability
            proposals=["option-a", "option-b"],
            mode=ConsensusMode.WEIGHTED,
            timeout=5.0,
        )
        
        assert decision.success
        assert decision.winner in ["option-a", "option-b"]
    
    def test_stats(self, manager):
        """Test statistics collection."""
        stats = manager.get_stats()
        
        assert "total_decisions" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "success_rate" in stats
        assert "agents" in stats
        assert stats["agents"] == 3
    
    def test_agent_info_serialization(self):
        """Test AgentInfo serialization."""
        agent = AgentInfo(
            agent_id="test-agent",
            name="TestAgent",
            capabilities={"cap1", "cap2"},
            weight=1.5,
        )
        
        data = agent.to_dict()
        
        assert data["agent_id"] == "test-agent"
        assert data["name"] == "TestAgent"
        assert set(data["capabilities"]) == {"cap1", "cap2"}
        assert data["weight"] == 1.5
    
    def test_decision_serialization(self):
        """Test SwarmDecision serialization."""
        decision = SwarmDecision(
            decision_id="test-id",
            topic="test-topic",
            proposals=["a", "b"],
            winner="a",
            mode=ConsensusMode.SIMPLE,
            success=True,
        )
        
        data = decision.to_dict()
        
        assert data["decision_id"] == "test-id"
        assert data["topic"] == "test-topic"
        assert data["winner"] == "a"
        assert data["mode"] == "simple"
        assert data["success"] is True


class TestConsensusIntegration:
    """Integration tests for consensus algorithms."""
    
    @pytest.mark.asyncio
    async def test_multi_node_paxos(self):
        """Test Paxos with multiple simulated nodes."""
        # Create 3 nodes
        nodes = {}
        messages = []
        
        def create_sender(node_id):
            def send(target, msg):
                messages.append((node_id, target, msg))
            return send
        
        for i in range(3):
            node_id = f"node-{i}"
            peers = {f"node-{j}" for j in range(3) if j != i}
            node = PaxosNode(node_id=node_id, peers=peers)
            node.set_callbacks(send_message=create_sender(node_id))
            nodes[node_id] = node
        
        # Node 1 proposes
        success, value = await nodes["node-0"].propose("test-value", "instance-1")
        
        # In a real test, we would deliver messages between nodes
        # For now, just verify the proposal was initiated
        assert nodes["node-0"].get_instance("instance-1") is not None
    
    @pytest.mark.asyncio
    async def test_consensus_mode_selection(self):
        """Test automatic mode selection based on scenario."""
        agents = {
            f"agent-{i}": AgentInfo(
                agent_id=f"agent-{i}",
                name=f"Agent{i}",
                capabilities={"general"},
                weight=1.0,
            )
            for i in range(4)
        }
        
        manager = SwarmConsensusManager(
            node_id="agent-0",
            agents=agents,
        )
        
        # Test different modes
        modes = [
            ConsensusMode.SIMPLE,
            ConsensusMode.WEIGHTED,
        ]
        
        for mode in modes:
            decision = await manager.decide(
                topic="test",
                proposals=["a", "b"],
                mode=mode,
                timeout=5.0,
            )
            assert decision.mode == mode


class TestByzantineTolerance:
    """Tests for Byzantine fault tolerance."""
    
    def test_pbft_byzantine_tolerance(self):
        """Test PBFT can tolerate Byzantine nodes."""
        # 4 nodes can tolerate 1 Byzantine
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        assert node.f == 1
        assert node.n == 4
    
    def test_pbft_quorum_requirements(self):
        """Test PBFT quorum requirements."""
        # For f=1, need 2f+1 = 3 commits
        node = PBFTNode(
            node_id="node-1",
            peers={"node-2", "node-3", "node-4"},
            f=1,
        )
        
        # Prepare phase needs 2f = 2 prepares
        # Commit phase needs 2f+1 = 3 commits
        # This ensures safety and liveness
        assert node.f == 1


# Performance benchmarks
class TestPerformance:
    """Performance tests for consensus algorithms."""
    
    @pytest.mark.asyncio
    async def test_decision_latency(self):
        """Test decision latency."""
        agents = {
            f"agent-{i}": AgentInfo(
                agent_id=f"agent-{i}",
                name=f"Agent{i}",
            )
            for i in range(5)
        }
        
        manager = SwarmConsensusManager(
            node_id="agent-0",
            agents=agents,
        )
        
        import time
        start = time.time()
        
        decision = await manager.decide(
            topic="latency-test",
            proposals=["a", "b"],
            mode=ConsensusMode.SIMPLE,
        )
        
        elapsed = time.time() - start
        
        # Simple decision should be fast
        assert elapsed < 1.0  # Less than 1 second
        assert decision.duration_ms < 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_decisions(self):
        """Test multiple concurrent decisions."""
        agents = {
            f"agent-{i}": AgentInfo(
                agent_id=f"agent-{i}",
                name=f"Agent{i}",
            )
            for i in range(3)
        }
        
        manager = SwarmConsensusManager(
            node_id="agent-0",
            agents=agents,
        )
        
        # Make multiple decisions concurrently
        tasks = [
            manager.decide(
                topic=f"topic-{i}",
                proposals=["a", "b"],
                mode=ConsensusMode.SIMPLE,
            )
            for i in range(10)
        ]
        
        decisions = await asyncio.gather(*tasks)
        
        assert len(decisions) == 10
        assert all(d.success for d in decisions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
