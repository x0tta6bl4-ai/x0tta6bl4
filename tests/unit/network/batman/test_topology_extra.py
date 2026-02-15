from datetime import datetime, timedelta

from src.network.batman.topology import (LinkQuality, MeshLink, MeshNode,
                                         MeshTopology, NodeState)


def test_topology_routing_and_prune():
    topo = MeshTopology(mesh_id="m1", local_node_id="A")
    # Add nodes
    for nid in ["A", "B", "C", "D"]:
        topo.add_node(
            MeshNode(
                node_id=nid,
                mac_address=f"mac-{nid}",
                ip_address=f"10.0.0.{nid}",
                state=NodeState.ONLINE,
            )
        )
    # Add links (A-B, B-C, C-D) chain
    topo.add_link(
        MeshLink("A", "B", LinkQuality.GOOD, throughput_mbps=100, latency_ms=10)
    )
    topo.add_link(
        MeshLink("B", "C", LinkQuality.GOOD, throughput_mbps=100, latency_ms=12)
    )
    topo.add_link(
        MeshLink("C", "D", LinkQuality.EXCELLENT, throughput_mbps=120, latency_ms=8)
    )

    # Compute shortest path A->D
    path = topo.compute_shortest_path("A", "D")
    assert path == ["A", "B", "C", "D"]

    updated = topo.update_routing_table()
    assert updated >= 1
    stats = topo.get_topology_stats()
    assert stats["total_nodes"] == 4
    assert stats["mesh_diameter"] >= 3

    # Force node B dead by modifying last_seen
    topo.nodes["B"].last_seen = datetime.now() - timedelta(seconds=999)
    pruned = topo.prune_dead_nodes(timeout=300)
    assert pruned == 1
    assert "B" not in topo.nodes


def test_topology_get_neighbors_quality_filter():
    topo = MeshTopology(mesh_id="m2", local_node_id="A")
    topo.add_node(MeshNode("A", "macA", "10.0.0.1", state=NodeState.ONLINE))
    topo.add_node(MeshNode("B", "macB", "10.0.0.2", state=NodeState.ONLINE))
    topo.add_node(MeshNode("C", "macC", "10.0.0.3", state=NodeState.ONLINE))
    # FAIR and GOOD links; expect only GOOD in neighbors due to quality threshold
    topo.add_link(
        MeshLink("A", "B", LinkQuality.GOOD, throughput_mbps=50, latency_ms=15)
    )
    topo.add_link(
        MeshLink("A", "C", LinkQuality.POOR, throughput_mbps=10, latency_ms=40)
    )
    neigh = topo.get_neighbors("A")
    assert "B" in neigh and "C" not in neigh
