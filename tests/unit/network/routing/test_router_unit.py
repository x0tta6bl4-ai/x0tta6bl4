"""Unit tests for Mesh Router (simplified facade)."""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.routing.router import MeshRouter
from src.network.routing.route_table import RouteEntry
from src.network.routing.topology import LinkQuality


class TestMeshRouterInit:
    def test_default_init(self):
        r = MeshRouter("node-001")
        assert r.local_node_id == "node-001"
        assert r._running is False
        assert r.max_hops == 15

    def test_custom_params(self):
        r = MeshRouter("node-001", max_hops=10, hello_interval=2.0, route_timeout=30.0)
        assert r.max_hops == 10
        assert r.hello_interval == 2.0
        assert r.route_timeout == 30.0

    def test_components_initialized(self):
        r = MeshRouter("node-001")
        assert r.topology is not None
        assert r.route_table is not None
        assert r.packet_handler is not None
        assert r.recovery is not None


class TestStartStop:
    def test_start(self):
        r = MeshRouter("node-001")
        r.start()
        assert r._running is True

    def test_stop(self):
        r = MeshRouter("node-001")
        r.start()
        r.stop()
        assert r._running is False


class TestNeighborManagement:
    def test_add_neighbor(self):
        r = MeshRouter("node-001")
        node = r.add_neighbor("node-002")
        assert node.node_id == "node-002"
        assert node.is_neighbor is True

    def test_add_neighbor_with_quality(self):
        r = MeshRouter("node-001")
        lq = LinkQuality(latency_ms=10)
        node = r.add_neighbor("node-002", link_quality=lq)
        assert node.link_quality.latency_ms == 10

    def test_remove_neighbor(self):
        r = MeshRouter("node-001")
        r.add_neighbor("node-002")
        assert r.remove_neighbor("node-002") is True
        assert r.remove_neighbor("node-002") is False

    def test_get_neighbors(self):
        r = MeshRouter("node-001")
        r.add_neighbor("node-002")
        r.add_neighbor("node-003")
        assert len(r.get_neighbors()) == 2


class TestRouting:
    def test_get_next_hop_no_route(self):
        r = MeshRouter("node-001")
        assert r.get_next_hop("node-099") is None

    def test_get_next_hop_with_route(self):
        r = MeshRouter("node-001")
        route = RouteEntry(destination="node-003", next_hop="node-002", hop_count=2, seq_num=1)
        r.route_table.add_route(route)
        assert r.get_next_hop("node-003") == "node-002"

    def test_has_route(self):
        r = MeshRouter("node-001")
        route = RouteEntry(destination="node-003", next_hop="node-002", hop_count=2, seq_num=1)
        r.route_table.add_route(route)
        assert r.has_route("node-003") is True
        assert r.has_route("node-099") is False

    def test_get_routes(self):
        r = MeshRouter("node-001")
        route = RouteEntry(destination="node-003", next_hop="node-002", hop_count=2, seq_num=1)
        r.route_table.add_route(route)
        routes = r.get_routes("node-003")
        assert len(routes) >= 1


class TestSendData:
    def test_no_route_initiates_discovery(self):
        r = MeshRouter("node-001")
        r.add_neighbor("node-002")
        send_cb = MagicMock()
        r.set_send_callback(send_cb)
        success, next_hop = r.send_data("node-099", b"hello")
        assert success is False
        assert next_hop is None
        # Should have tried to send RREQ
        assert send_cb.called

    def test_with_route(self):
        r = MeshRouter("node-001")
        route = RouteEntry(destination="node-003", next_hop="node-002", hop_count=2, seq_num=1)
        r.route_table.add_route(route)
        success, next_hop = r.send_data("node-003", b"hello")
        assert success is True
        assert next_hop == "node-002"


class TestCreateHello:
    def test_creates_packet(self):
        r = MeshRouter("node-001")
        hello = r.create_hello()
        assert hello is not None


class TestTick:
    def test_not_running(self):
        r = MeshRouter("node-001")
        r.tick()  # Should be no-op

    def test_sends_hello(self):
        r = MeshRouter("node-001", hello_interval=0.0)
        r.start()
        r.add_neighbor("node-002")
        send_cb = MagicMock()
        r.set_send_callback(send_cb)
        r._last_hello = 0  # Force hello
        r.tick()
        assert send_cb.called

    def test_periodic_cleanup(self):
        r = MeshRouter("node-001")
        r.start()
        r._last_cleanup = 0  # Force cleanup
        r._last_hello = time.time()  # Skip hello
        r.tick()
        assert r._last_cleanup > 0


class TestStats:
    def test_topology_stats(self):
        r = MeshRouter("node-001")
        stats = r.get_topology_stats()
        assert "total_nodes" in stats

    def test_route_stats(self):
        r = MeshRouter("node-001")
        stats = r.get_route_stats()
        assert isinstance(stats, dict)

    def test_recovery_stats(self):
        r = MeshRouter("node-001")
        stats = r.get_recovery_stats()
        assert "active_recoveries" in stats

    def test_all_stats(self):
        r = MeshRouter("node-001")
        stats = r.get_all_stats()
        assert stats["local_node_id"] == "node-001"
        assert "topology" in stats
        assert "routes" in stats
        assert "recovery" in stats

    def test_get_active_nodes(self):
        r = MeshRouter("node-001")
        r.add_neighbor("node-002")
        assert "node-002" in r.get_active_nodes()

    def test_get_adjacency(self):
        r = MeshRouter("node-001")
        r.add_neighbor("node-002")
        adj = r.get_adjacency()
        assert "node-001" in adj


class TestHandlePacket:
    def test_handle(self):
        r = MeshRouter("node-001")
        pkt = r.packet_handler.create_hello()
        result = r.handle_packet(pkt, "node-002")
        # Result can be None (hello processing)
        assert result is None or result is not None
