"""
Unit tests for SwarmOrchestrator.
"""

import pytest

from src.swarm.orchestrator import SwarmOrchestrator


def test_swarm_orchestrator_init():
    """Test SwarmOrchestrator initialization."""
    orchestrator = SwarmOrchestrator(node_id="test-node", peers={"peer1", "peer2"})
    
    assert orchestrator.node_id == "test-node"
    assert orchestrator.peers == {"peer1", "peer2"}
    assert orchestrator._pending_decisions == {}
    assert orchestrator._decision_history == []


def test_swarm_orchestrator_add_node():
    """Test adding a node to the orchestrator."""
    orchestrator = SwarmOrchestrator(node_id="test-node", peers=set())
    
    orchestrator.add_node("new-peer")
    
    assert "new-peer" in orchestrator.peers


def test_swarm_orchestrator_remove_node():
    """Test removing a node from the orchestrator."""
    orchestrator = SwarmOrchestrator(node_id="test-node", peers={"peer1", "peer2"})
    
    orchestrator.remove_node("peer1")
    
    assert "peer1" not in orchestrator.peers
    assert "peer2" in orchestrator.peers


def test_swarm_orchestrator_get_active_nodes():
    """Test getting active nodes."""
    orchestrator = SwarmOrchestrator(node_id="test-node", peers={"peer1", "peer2"})
    
    active = orchestrator.get_active_nodes()
    
    # In this simple test, all peers are considered active
    assert len(active) == 2
    assert "peer1" in active
    assert "peer2" in active
