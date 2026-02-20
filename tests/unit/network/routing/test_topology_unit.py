"""Unit tests for Topology Manager."""
import os
import time
import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.routing.topology import LinkQuality, NodeInfo, TopologyManager


class TestLinkQuality:
    def test_defaults(self):
        lq = LinkQuality()
        assert lq.latency_ms == 0.0
        assert lq.throughput_mbps == 0.0
        assert lq.loss_rate == 0.0
        assert lq.rssi == -60.0
        assert lq.snr == 25.0

    def test_quality_score_perfect(self):
        lq = LinkQuality(latency_ms=0, throughput_mbps=50, loss_rate=0, rssi=-50)
        score = lq.quality_score
        assert 0.8 <= score <= 1.0

    def test_quality_score_poor(self):
        lq = LinkQuality(latency_ms=300, throughput_mbps=0, loss_rate=15, rssi=-95)
        score = lq.quality_score
        assert score < 0.3

    def test_quality_score_moderate(self):
        lq = LinkQuality(latency_ms=50, throughput_mbps=20, loss_rate=2, rssi=-70)
        score = lq.quality_score
        assert 0.3 <= score <= 0.8

    def test_custom_values(self):
        lq = LinkQuality(latency_ms=10, throughput_mbps=100, loss_rate=0.5, rssi=-55, snr=30)
        assert lq.latency_ms == 10
        assert lq.snr == 30


class TestNodeInfo:
    def test_defaults(self):
        n = NodeInfo(node_id="n1")
        assert n.node_id == "n1"
        assert n.is_neighbor is False
        assert n.hop_count == 1
        assert n.is_active is True

    def test_age(self):
        n = NodeInfo(node_id="n1", last_seen=time.time() - 5.0)
        assert n.age >= 5.0

    def test_custom(self):
        lq = LinkQuality(latency_ms=10)
        n = NodeInfo(node_id="n1", is_neighbor=True, hop_count=2, link_quality=lq)
        assert n.is_neighbor is True
        assert n.link_quality.latency_ms == 10


class TestTopologyManagerInit:
    def test_init(self):
        tm = TopologyManager("local")
        assert tm.local_node_id == "local"
        assert len(tm._nodes) == 0

    def test_cannot_add_self(self):
        tm = TopologyManager("local")
        with pytest.raises(ValueError, match="local node"):
            tm.add_node("local")


class TestAddNode:
    def test_basic_add(self):
        tm = TopologyManager("local")
        node = tm.add_node("n1")
        assert node.node_id == "n1"
        assert node.is_active is True

    def test_add_neighbor_with_quality(self):
        tm = TopologyManager("local")
        lq = LinkQuality(latency_ms=10)
        node = tm.add_node("n1", is_neighbor=True, link_quality=lq)
        assert node.is_neighbor is True
        assert "local" in tm._links
        assert "n1" in tm._links["local"]

    def test_overwrite_existing(self):
        tm = TopologyManager("local")
        tm.add_node("n1", hop_count=3)
        tm.add_node("n1", hop_count=2)
        assert tm.get_node("n1").hop_count == 2


class TestRemoveNode:
    def test_remove_existing(self):
        tm = TopologyManager("local")
        tm.add_node("n1")
        assert tm.remove_node("n1") is True
        assert tm.get_node("n1") is None

    def test_remove_nonexistent(self):
        tm = TopologyManager("local")
        assert tm.remove_node("n1") is False

    def test_remove_cleans_links(self):
        tm = TopologyManager("local")
        tm.add_node("n1", is_neighbor=True, link_quality=LinkQuality())
        tm.remove_node("n1")
        for links in tm._links.values():
            assert "n1" not in links


class TestUpdateLinkQuality:
    def test_update(self):
        tm = TopologyManager("local")
        tm.add_node("n1")
        lq = LinkQuality(latency_ms=5)
        tm.update_link_quality("local", "n1", lq)
        assert tm._links["local"]["n1"].latency_ms == 5

    def test_updates_node_info(self):
        tm = TopologyManager("local")
        tm.add_node("n1")
        old_seen = tm.get_node("n1").last_seen
        time.sleep(0.01)
        tm.update_link_quality("local", "n1", LinkQuality())
        assert tm.get_node("n1").last_seen >= old_seen


class TestGetNeighbors:
    def test_empty(self):
        tm = TopologyManager("local")
        assert tm.get_neighbors() == []

    def test_with_neighbors(self):
        tm = TopologyManager("local")
        tm.add_node("n1", is_neighbor=True)
        tm.add_node("n2", is_neighbor=True)
        tm.add_node("n3", is_neighbor=False)
        neighbors = tm.get_neighbors()
        assert "n1" in neighbors
        assert "n2" in neighbors
        assert "n3" not in neighbors

    def test_excludes_inactive(self):
        tm = TopologyManager("local")
        node = tm.add_node("n1", is_neighbor=True)
        node.is_active = False
        assert "n1" not in tm.get_neighbors()


class TestGetActiveNodes:
    def test_all_active(self):
        tm = TopologyManager("local")
        tm.add_node("n1")
        tm.add_node("n2")
        assert len(tm.get_active_nodes()) == 2

    def test_excludes_inactive(self):
        tm = TopologyManager("local")
        tm.add_node("n1").is_active = False
        tm.add_node("n2")
        assert tm.get_active_nodes() == ["n2"]


class TestGetLinkQuality:
    def test_exists(self):
        tm = TopologyManager("local")
        tm.add_node("n1", is_neighbor=True, link_quality=LinkQuality(latency_ms=10))
        lq = tm.get_link_quality("local", "n1")
        assert lq.latency_ms == 10

    def test_not_exists(self):
        tm = TopologyManager("local")
        assert tm.get_link_quality("local", "n1") is None


class TestCleanupStaleNodes:
    def test_no_stale(self):
        tm = TopologyManager("local")
        tm.add_node("n1")
        assert tm.cleanup_stale_nodes() == 0

    def test_removes_stale(self):
        tm = TopologyManager("local")
        node = tm.add_node("n1")
        node.last_seen = time.time() - 200  # Well past timeout
        removed = tm.cleanup_stale_nodes()
        assert removed == 1
        assert tm.get_node("n1") is None


class TestGetTopologyStats:
    def test_empty(self):
        tm = TopologyManager("local")
        stats = tm.get_topology_stats()
        assert stats["total_nodes"] == 0
        assert stats["neighbor_count"] == 0
        assert stats["average_link_quality"] == 0.0

    def test_with_nodes(self):
        tm = TopologyManager("local")
        tm.add_node("n1", is_neighbor=True, link_quality=LinkQuality(latency_ms=10, throughput_mbps=20))
        tm.add_node("n2", is_neighbor=False)
        stats = tm.get_topology_stats()
        assert stats["total_nodes"] == 2
        assert stats["neighbor_count"] == 1
        assert stats["average_link_quality"] > 0


class TestBuildAdjacency:
    def test_empty(self):
        tm = TopologyManager("local")
        adj = tm.build_adjacency()
        assert "local" in adj
        assert adj["local"] == []

    def test_with_neighbors(self):
        tm = TopologyManager("local")
        tm.add_node("n1", is_neighbor=True)
        tm.add_node("n2", is_neighbor=True)
        adj = tm.build_adjacency()
        assert "n1" in adj["local"]
        assert "n2" in adj["local"]
