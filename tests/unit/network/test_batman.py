"""
Unit tests for Batman-adv mesh components
"""

from datetime import datetime, timedelta

import pytest

from src.network.batman.node_manager import (AttestationStrategy,
                                             HealthMonitor, NodeManager,
                                             NodeMetrics)
from src.network.batman.topology import (LinkQuality, MeshLink, MeshNode,
                                         MeshTopology, NodeState)

# ============================================================================
# MeshNode Tests
# ============================================================================


def test_mesh_node_creation():
    """Test creating a mesh node"""
    node = MeshNode(
        node_id="node1",
        mac_address="00:11:22:33:44:55",
        ip_address="10.0.0.1",
    )
    assert node.node_id == "node1"
    assert node.state == NodeState.INITIALIZING


def test_mesh_node_is_alive():
    """Test node alive check"""
    node = MeshNode(
        node_id="node1",
        mac_address="00:11:22:33:44:55",
        ip_address="10.0.0.1",
        last_seen=datetime.now(),
    )
    assert node.is_alive(timeout=300)

    # Set last_seen to past
    node.last_seen = datetime.now() - timedelta(seconds=400)
    assert not node.is_alive(timeout=300)


def test_mesh_node_with_spiffe():
    """Test node with SPIFFE identity"""
    node = MeshNode(
        node_id="node1",
        mac_address="00:11:22:33:44:55",
        ip_address="10.0.0.1",
        spiffe_id="spiffe://example.com/mesh/node1",
    )
    assert node.spiffe_id.startswith("spiffe://")


# ============================================================================
# MeshLink Tests
# ============================================================================


def test_mesh_link_quality_score():
    """Test link quality score calculation"""
    link = MeshLink(
        source="node1",
        destination="node2",
        quality=LinkQuality.GOOD,
        throughput_mbps=100.0,
        latency_ms=10.0,
        packet_loss_percent=0.5,
    )
    score = link.quality_score()
    assert 50 < score < 100  # GOOD quality


def test_mesh_link_poor_quality():
    """Test poor quality link"""
    link = MeshLink(
        source="node1",
        destination="node2",
        quality=LinkQuality.POOR,
        throughput_mbps=50.0,
        latency_ms=100.0,
        packet_loss_percent=5.0,
    )
    score = link.quality_score()
    assert 0 <= score < 50


# ============================================================================
# MeshTopology Tests
# ============================================================================


def test_topology_add_node():
    """Test adding nodes to topology"""
    topo = MeshTopology("mesh1", "local_node")
    node = MeshNode("node1", "00:11:22:33:44:55", "10.0.0.1")

    assert topo.add_node(node)
    assert "node1" in topo.nodes


def test_topology_add_duplicate_node():
    """Test that duplicate nodes are rejected"""
    topo = MeshTopology("mesh1", "local_node")
    node = MeshNode("node1", "00:11:22:33:44:55", "10.0.0.1")

    assert topo.add_node(node)
    assert not topo.add_node(node)  # Duplicate


def test_topology_add_link():
    """Test adding links to topology"""
    topo = MeshTopology("mesh1", "local_node")
    node1 = MeshNode("node1", "00:11:22:33:44:55", "10.0.0.1")
    node2 = MeshNode("node2", "00:11:22:33:44:66", "10.0.0.2")

    topo.add_node(node1)
    topo.add_node(node2)

    link = MeshLink("node1", "node2", LinkQuality.GOOD, 100.0, 10.0)
    assert topo.add_link(link)


def test_topology_get_neighbors():
    """Test getting node neighbors"""
    topo = MeshTopology("mesh1", "local_node")
    node1 = MeshNode("node1", "00:11:22:33:44:55", "10.0.0.1")
    node2 = MeshNode("node2", "00:11:22:33:44:66", "10.0.0.2")
    node3 = MeshNode("node3", "00:11:22:33:44:77", "10.0.0.3")

    topo.add_node(node1)
    topo.add_node(node2)
    topo.add_node(node3)

    topo.add_link(MeshLink("node1", "node2", LinkQuality.GOOD, 100.0, 10.0))
    topo.add_link(MeshLink("node1", "node3", LinkQuality.FAIR, 50.0, 20.0))

    neighbors = topo.get_neighbors("node1")
    assert "node2" in neighbors
    assert "node3" in neighbors


def test_topology_shortest_path():
    """Test shortest path computation"""
    topo = MeshTopology("mesh1", "local_node")

    # Create linear topology: node1 -> node2 -> node3
    for i in range(1, 4):
        node = MeshNode(f"node{i}", f"00:11:22:33:44:{44+i:02x}", f"10.0.0.{i}")
        topo.add_node(node)

    topo.add_link(MeshLink("node1", "node2", LinkQuality.EXCELLENT, 100.0, 10.0))
    topo.add_link(MeshLink("node2", "node3", LinkQuality.EXCELLENT, 100.0, 10.0))

    path = topo.compute_shortest_path("node1", "node3")
    assert path == ["node1", "node2", "node3"]


def test_topology_routing_table():
    """Test routing table computation"""
    topo = MeshTopology("mesh1", "node1")

    for i in range(1, 4):
        node = MeshNode(f"node{i}", f"00:11:22:33:44:{44+i:02x}", f"10.0.0.{i}")
        topo.add_node(node)

    topo.add_link(MeshLink("node1", "node2", LinkQuality.GOOD, 100.0, 10.0))
    topo.add_link(MeshLink("node2", "node3", LinkQuality.GOOD, 100.0, 10.0))

    updated = topo.update_routing_table()
    assert updated > 0
    assert "node3" in topo.routing_table


def test_topology_prune_dead_nodes():
    """Test pruning of dead nodes"""
    topo = MeshTopology("mesh1", "local_node")

    node1 = MeshNode("node1", "00:11:22:33:44:55", "10.0.0.1")
    node2 = MeshNode(
        "node2",
        "00:11:22:33:44:66",
        "10.0.0.2",
        last_seen=datetime.now() - timedelta(seconds=400),
    )

    topo.add_node(node1)
    topo.add_node(node2)

    pruned = topo.prune_dead_nodes(timeout=300)
    assert pruned == 1
    assert "node2" not in topo.nodes


# ============================================================================
# NodeManager Tests
# ============================================================================


def test_node_manager_register():
    """Test node registration"""
    manager = NodeManager("mesh1", "local_node")
    result = manager.register_node(
        "node1",
        "00:11:22:33:44:55",
        "10.0.0.1",
        spiffe_id="spiffe://example.com/mesh/node1",
    )
    assert result
    assert "node1" in manager.nodes


def test_node_manager_invalid_spiffe():
    """Test rejection of invalid SPIFFE ID"""
    manager = NodeManager("mesh1", "local_node")
    manager.attestation_strategy = AttestationStrategy.SPIFFE

    result = manager.register_node(
        "node1",
        "00:11:22:33:44:55",
        "10.0.0.1",
        spiffe_id="invalid",  # Invalid SPIFFE format
    )
    assert not result


def test_node_manager_heartbeat():
    """Test heartbeat update"""
    manager = NodeManager("mesh1", "local_node")
    manager.register_node(
        "node1",
        "00:11:22:33:44:55",
        "10.0.0.1",
        spiffe_id="spiffe://example.com/mesh/node1",
    )

    result = manager.update_heartbeat("node1")
    assert result


def test_node_manager_metrics():
    """Test node metrics update"""
    manager = NodeManager("mesh1", "local_node")
    manager.register_node(
        "node1",
        "00:11:22:33:44:55",
        "10.0.0.1",
        spiffe_id="spiffe://example.com/mesh/node1",
    )

    metrics = NodeMetrics(
        cpu_percent=50.0,
        memory_percent=60.0,
        network_sent_bytes=1000000,
        network_recv_bytes=1500000,
        packet_loss_percent=0.1,
        latency_to_gateway_ms=20.0,
    )

    assert metrics.is_healthy()
    assert manager.update_metrics("node1", metrics)


def test_node_manager_degraded_metrics():
    """Test degraded node metrics"""
    metrics = NodeMetrics(
        cpu_percent=95.0,  # Too high
        memory_percent=90.0,  # Too high
        network_sent_bytes=1000000,
        network_recv_bytes=1500000,
        packet_loss_percent=8.0,  # Too high
        latency_to_gateway_ms=600.0,  # Too high
    )

    assert not metrics.is_healthy()


def test_node_manager_get_online_nodes():
    """Test getting online nodes"""
    manager = NodeManager("mesh1", "local_node")
    manager.register_node(
        "node1",
        "00:11:22:33:44:55",
        "10.0.0.1",
        spiffe_id="spiffe://example.com/mesh/node1",
    )

    online = manager.get_online_nodes()
    assert "node1" in online


# ============================================================================
# Integration Tests
# ============================================================================


def test_batman_mesh_integration():
    """Test full Batman mesh integration"""
    # Create topology
    topo = MeshTopology("mesh1", "node1")

    # Create node manager
    manager = NodeManager("mesh1", "node1")

    # Create and register nodes
    for i in range(1, 4):
        node = MeshNode(
            f"node{i}",
            f"00:11:22:33:44:{44+i:02x}",
            f"10.0.0.{i}",
            spiffe_id=f"spiffe://example.com/mesh/node{i}",
        )
        topo.add_node(node)
        manager.register_node(
            f"node{i}",
            f"00:11:22:33:44:{44+i:02x}",
            f"10.0.0.{i}",
            spiffe_id=f"spiffe://example.com/mesh/node{i}",
        )

    # Add links
    topo.add_link(MeshLink("node1", "node2", LinkQuality.GOOD, 100.0, 10.0))
    topo.add_link(MeshLink("node2", "node3", LinkQuality.GOOD, 100.0, 10.0))

    # Verify
    stats = topo.get_topology_stats()
    assert stats["total_nodes"] == 3
    assert stats["total_links"] == 2
    assert len(manager.get_online_nodes()) == 3
