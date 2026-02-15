"""
Unit tests for src/network/routing/mesh_router.py AODV-like mesh routing.

Tests: route entry lifecycle, packet serialization, routing table management,
neighbor add/remove, TTL handling, route expiry, statistics.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from src.network.routing.mesh_router import (MeshRouter, PacketType,
                                             RouteEntry, RoutingPacket)

# ---------------------------------------------------------------------------
# RouteEntry tests
# ---------------------------------------------------------------------------


class TestRouteEntry:
    def test_route_entry_creation(self):
        entry = RouteEntry(
            destination="node-b",
            next_hop="node-a",
            hop_count=2,
            seq_num=1,
            path=["node-x", "node-a", "node-b"],
        )
        assert entry.destination == "node-b"
        assert entry.next_hop == "node-a"
        assert entry.hop_count == 2
        assert entry.valid is True

    def test_route_entry_age(self):
        entry = RouteEntry(
            destination="d",
            next_hop="n",
            hop_count=1,
            seq_num=0,
            timestamp=time.time() - 10,
            path=[],
        )
        assert entry.age >= 10

    def test_route_entry_default_valid(self):
        entry = RouteEntry(
            destination="d", next_hop="n", hop_count=1, seq_num=0, path=[]
        )
        assert entry.valid is True


# ---------------------------------------------------------------------------
# RoutingPacket tests
# ---------------------------------------------------------------------------


class TestRoutingPacket:
    def test_packet_creation_auto_id(self):
        pkt = RoutingPacket(
            packet_type=PacketType.DATA,
            source="src",
            destination="dst",
            seq_num=1,
            hop_count=0,
            ttl=16,
            payload=b"hello",
        )
        assert pkt.packet_id  # auto-generated
        assert pkt.packet_type == PacketType.DATA

    def test_packet_serialization_roundtrip(self):
        original = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-1",
            destination="node-5",
            seq_num=42,
            hop_count=3,
            ttl=10,
            payload=b"node-5",
            path_traversed=["node-1", "node-2", "node-3"],
        )
        raw = original.to_bytes()
        restored = RoutingPacket.from_bytes(raw)

        assert restored.packet_type == PacketType.RREQ
        assert restored.source == "node-1"
        assert restored.destination == "node-5"
        assert restored.seq_num == 42
        assert restored.hop_count == 3
        assert restored.ttl == 10
        assert restored.path_traversed == ["node-1", "node-2", "node-3"]

    def test_packet_types_enum(self):
        assert PacketType.DATA.value == 0x01
        assert PacketType.RREQ.value == 0x02
        assert PacketType.RREP.value == 0x03
        assert PacketType.RERR.value == 0x04
        assert PacketType.HELLO.value == 0x05


# ---------------------------------------------------------------------------
# MeshRouter tests
# ---------------------------------------------------------------------------


class TestMeshRouter:
    def test_init(self):
        router = MeshRouter("node-0")
        assert router.node_id == "node-0"
        assert router.seq_num == 0

    def test_add_neighbor(self):
        router = MeshRouter("node-0")
        router.add_neighbor("node-1")

        routes = router.get_route("node-1")
        assert len(routes) == 1
        assert routes[0].next_hop == "node-1"
        assert routes[0].hop_count == 1

    def test_add_multiple_neighbors(self):
        router = MeshRouter("node-0")
        router.add_neighbor("node-1")
        router.add_neighbor("node-2")
        router.add_neighbor("node-3")

        all_routes = router.get_routes()
        assert "node-1" in all_routes
        assert "node-2" in all_routes
        assert "node-3" in all_routes

    def test_remove_neighbor(self):
        router = MeshRouter("node-0")
        router.add_neighbor("node-1")
        router.add_neighbor("node-2")

        router.remove_neighbor("node-1")
        assert len(router.get_route("node-1")) == 0
        assert len(router.get_route("node-2")) == 1

    def test_remove_neighbor_invalidates_transitive_routes(self):
        router = MeshRouter("node-0")
        router.add_neighbor("node-1")
        # Add a route through node-1 to node-3
        router._update_route("node-3", "node-1", 2, 1, ["node-0", "node-1", "node-3"])

        router.remove_neighbor("node-1")
        assert len(router.get_route("node-3")) == 0

    def test_get_route_sorted_by_hops(self):
        router = MeshRouter("node-0")
        # Add two routes to node-5: one via node-1 (3 hops), one via node-2 (2 hops)
        router._update_route(
            "node-5", "node-1", 3, 1, ["node-0", "node-1", "x", "node-5"]
        )
        router._update_route("node-5", "node-2", 2, 1, ["node-0", "node-2", "node-5"])

        routes = router.get_route("node-5")
        assert len(routes) == 2
        assert routes[0].hop_count <= routes[1].hop_count

    def test_route_expiry(self):
        router = MeshRouter("node-0")
        # Create an expired route
        entry = RouteEntry(
            destination="old-node",
            next_hop="n",
            hop_count=1,
            seq_num=0,
            timestamp=time.time() - router.ROUTE_TIMEOUT - 1,
            path=["node-0", "old-node"],
        )
        router._routes["old-node"] = [entry]

        # Expired route should not be returned
        routes = router.get_route("old-node")
        assert len(routes) == 0

    @pytest.mark.asyncio
    async def test_send_to_self(self):
        router = MeshRouter("node-0")
        received = []

        async def on_receive(source, payload):
            received.append((source, payload))

        router.set_receive_callback(on_receive)
        result = await router.send("node-0", b"self-message")

        assert result is True
        assert len(received) == 1
        assert received[0] == ("node-0", b"self-message")

    @pytest.mark.asyncio
    async def test_stats_initial(self):
        router = MeshRouter("node-0")
        stats = await router.get_stats()
        assert stats["packets_sent"] == 0
        assert stats["packets_received"] == 0
        assert stats["packets_dropped"] == 0

    @pytest.mark.asyncio
    async def test_send_no_route_drops_packet(self):
        router = MeshRouter("node-0")
        # No neighbors, no routes, no send callback
        result = await router.send("unreachable", b"data")
        assert result is False

        stats = await router.get_stats()
        assert stats["packets_dropped"] >= 1
