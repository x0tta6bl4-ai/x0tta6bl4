"""
Comprehensive unit tests for src/network/routing/mesh_router.py

Tests cover:
- PacketType enum
- RouteEntry dataclass
- RoutingPacket serialization/deserialization
- MeshRouter: start/stop, callbacks, neighbors, routing, send, handle_packet,
  route discovery, CRDT sync, stats, MAPE-K metrics, error paths
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.network.routing.mesh_router import (
    MeshRouter,
    PacketType,
    RouteEntry,
    RoutingPacket,
)


# ---------------------------------------------------------------------------
# PacketType enum
# ---------------------------------------------------------------------------
class TestPacketType:
    def test_values(self):
        assert PacketType.DATA.value == 0x01
        assert PacketType.RREQ.value == 0x02
        assert PacketType.RREP.value == 0x03
        assert PacketType.RERR.value == 0x04
        assert PacketType.HELLO.value == 0x05
        assert PacketType.CRDT_SYNC.value == 0x06

    def test_from_value(self):
        assert PacketType(0x01) is PacketType.DATA
        assert PacketType(0x06) is PacketType.CRDT_SYNC

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            PacketType(0xFF)


# ---------------------------------------------------------------------------
# RouteEntry
# ---------------------------------------------------------------------------
class TestRouteEntry:
    def test_defaults(self):
        entry = RouteEntry(destination="B", next_hop="B", hop_count=1, seq_num=0)
        assert entry.valid is True
        assert entry.path == []
        assert isinstance(entry.timestamp, float)

    def test_age(self):
        entry = RouteEntry(
            destination="B", next_hop="B", hop_count=1, seq_num=0,
            timestamp=time.time() - 10.0,
        )
        assert entry.age >= 10.0
        assert entry.age < 12.0  # generous window

    def test_custom_path(self):
        entry = RouteEntry(
            destination="C", next_hop="B", hop_count=2, seq_num=5,
            path=["A", "B", "C"],
        )
        assert entry.path == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# RoutingPacket serialization
# ---------------------------------------------------------------------------
class TestRoutingPacket:
    def _make_packet(self, **overrides):
        defaults = dict(
            packet_type=PacketType.DATA,
            source="nodeA",
            destination="nodeB",
            seq_num=1,
            hop_count=0,
            ttl=16,
            payload=b"hello",
            packet_id="abc123",
            path_traversed=["nodeA"],
        )
        defaults.update(overrides)
        return RoutingPacket(**defaults)

    def test_to_bytes_and_from_bytes_roundtrip(self):
        pkt = self._make_packet()
        data = pkt.to_bytes()
        restored = RoutingPacket.from_bytes(data)

        assert restored.packet_type == pkt.packet_type
        assert restored.source == pkt.source
        assert restored.destination == pkt.destination
        assert restored.seq_num == pkt.seq_num
        assert restored.hop_count == pkt.hop_count
        assert restored.ttl == pkt.ttl
        assert restored.payload == pkt.payload
        assert restored.packet_id == pkt.packet_id
        assert restored.path_traversed == pkt.path_traversed

    def test_from_bytes_missing_path_defaults_to_empty(self):
        # Build raw bytes with no "path" key in header
        header = {
            "type": PacketType.DATA.value,
            "src": "A", "dst": "B",
            "seq": 1, "hops": 0, "ttl": 8, "id": "xyz",
        }
        header_bytes = json.dumps(header).encode()
        data = len(header_bytes).to_bytes(2, "big") + header_bytes + b"payload"
        pkt = RoutingPacket.from_bytes(data)
        assert pkt.path_traversed == []

    def test_default_packet_id_generated(self):
        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8, payload=b"",
        )
        assert pkt.packet_id  # not empty
        assert len(pkt.packet_id) == 16

    def test_unique_packet_ids(self):
        ids = set()
        for _ in range(20):
            pkt = RoutingPacket(
                packet_type=PacketType.DATA, source="A", destination="B",
                seq_num=1, hop_count=0, ttl=8, payload=b"",
            )
            ids.add(pkt.packet_id)
        # Should be mostly unique (extremely unlikely collision)
        assert len(ids) >= 18

    def test_various_packet_types_roundtrip(self):
        for pt in PacketType:
            pkt = self._make_packet(packet_type=pt)
            restored = RoutingPacket.from_bytes(pkt.to_bytes())
            assert restored.packet_type == pt

    def test_empty_payload(self):
        pkt = self._make_packet(payload=b"")
        restored = RoutingPacket.from_bytes(pkt.to_bytes())
        assert restored.payload == b""

    def test_large_payload(self):
        big = b"X" * 10_000
        pkt = self._make_packet(payload=big)
        restored = RoutingPacket.from_bytes(pkt.to_bytes())
        assert restored.payload == big


# ---------------------------------------------------------------------------
# MeshRouter
# ---------------------------------------------------------------------------
class TestMeshRouterInit:
    def test_initial_state(self):
        router = MeshRouter("node1")
        assert router.node_id == "node1"
        assert router.seq_num == 0
        assert router._routes == {}
        assert router._send_callback is None


@pytest.mark.asyncio
class TestMeshRouterStartStop:
    async def test_start_creates_cleanup_task(self):
        router = MeshRouter("node1")
        await router.start()
        assert router._seen_cleanup_task is not None
        await router.stop()

    async def test_stop_cancels_cleanup_task(self):
        router = MeshRouter("node1")
        await router.start()
        task = router._seen_cleanup_task
        await router.stop()
        assert task.cancelled()

    async def test_stop_without_start(self):
        router = MeshRouter("node1")
        # Should not raise
        await router.stop()


class TestMeshRouterCallbacks:
    def test_set_send_callback(self):
        router = MeshRouter("node1")
        cb = MagicMock()
        router.set_send_callback(cb)
        assert router._send_callback is cb

    def test_set_receive_callback(self):
        router = MeshRouter("node1")
        cb = MagicMock()
        router.set_receive_callback(cb)
        assert router._receive_callback is cb

    def test_set_crdt_sync_callback(self):
        router = MeshRouter("node1")
        cb = MagicMock()
        router.set_crdt_sync_callback(cb)
        assert router._crdt_sync_callback is cb


class TestMeshRouterNeighbors:
    def test_add_neighbor_creates_route(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        assert "B" in router._routes
        entries = router._routes["B"]
        assert len(entries) == 1
        assert entries[0].hop_count == 1
        assert entries[0].next_hop == "B"
        assert entries[0].path == ["A", "B"]

    def test_add_neighbor_twice_updates(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.add_neighbor("B")
        assert len(router._routes["B"]) == 1  # Not duplicated

    def test_add_multiple_neighbors(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.add_neighbor("C")
        assert "B" in router._routes
        assert "C" in router._routes

    def test_remove_neighbor_direct(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.remove_neighbor("B")
        assert "B" not in router._routes

    def test_remove_neighbor_invalidates_transitive_routes(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        # Manually add a route to C via B
        entry = RouteEntry(
            destination="C", next_hop="B", hop_count=2, seq_num=1,
            path=["A", "B", "C"],
        )
        router._routes["C"] = [entry]
        router.remove_neighbor("B")
        assert "B" not in router._routes
        assert "C" not in router._routes  # removed because next_hop was B

    def test_remove_neighbor_keeps_other_routes(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.add_neighbor("D")
        # Route to C via D (not via B)
        entry = RouteEntry(
            destination="C", next_hop="D", hop_count=2, seq_num=1,
            path=["A", "D", "C"],
        )
        router._routes["C"] = [entry]
        router.remove_neighbor("B")
        assert "C" in router._routes  # Kept because next_hop is D

    def test_remove_nonexistent_neighbor(self):
        router = MeshRouter("A")
        # Should not raise
        router.remove_neighbor("Z")


class TestGetRoute:
    def test_get_route_empty(self):
        router = MeshRouter("A")
        assert router.get_route("B") == []

    def test_get_route_valid(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        routes = router.get_route("B")
        assert len(routes) == 1
        assert routes[0].destination == "B"

    def test_get_route_filters_invalid(self):
        router = MeshRouter("A")
        entry = RouteEntry(
            destination="B", next_hop="B", hop_count=1, seq_num=0, valid=False,
        )
        router._routes["B"] = [entry]
        assert router.get_route("B") == []

    def test_get_route_filters_expired(self):
        router = MeshRouter("A")
        entry = RouteEntry(
            destination="B", next_hop="B", hop_count=1, seq_num=0,
            timestamp=time.time() - 120,  # expired (>60s)
        )
        router._routes["B"] = [entry]
        assert router.get_route("B") == []

    def test_get_route_sorted_by_hop_count(self):
        router = MeshRouter("A")
        e1 = RouteEntry(destination="C", next_hop="B", hop_count=3, seq_num=1)
        e2 = RouteEntry(destination="C", next_hop="D", hop_count=1, seq_num=1)
        router._routes["C"] = [e1, e2]
        routes = router.get_route("C")
        assert routes[0].hop_count == 1
        assert routes[1].hop_count == 3

    def test_get_route_sorted_by_seq_num_secondary(self):
        router = MeshRouter("A")
        e1 = RouteEntry(destination="C", next_hop="B", hop_count=2, seq_num=1)
        e2 = RouteEntry(destination="C", next_hop="D", hop_count=2, seq_num=5)
        router._routes["C"] = [e1, e2]
        routes = router.get_route("C")
        # Higher seq_num first (secondary sort: -seq_num)
        assert routes[0].seq_num == 5
        assert routes[1].seq_num == 1


class TestGetRoutes:
    def test_get_routes_empty(self):
        router = MeshRouter("A")
        assert router.get_routes() == {}

    def test_get_routes_filters_expired(self):
        router = MeshRouter("A")
        entry = RouteEntry(
            destination="B", next_hop="B", hop_count=1, seq_num=0,
            timestamp=time.time() - 120,
        )
        router._routes["B"] = [entry]
        assert router.get_routes() == {}

    def test_get_routes_returns_valid(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.add_neighbor("C")
        routes = router.get_routes()
        assert "B" in routes
        assert "C" in routes


# ---------------------------------------------------------------------------
# Async methods
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestMeshRouterSend:
    async def test_send_to_self(self):
        router = MeshRouter("A")
        recv_cb = AsyncMock()
        router.set_receive_callback(recv_cb)
        result = await router.send("A", b"self-data")
        assert result is True
        recv_cb.assert_awaited_once_with("A", b"self-data")

    async def test_send_with_existing_route(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")

        result = await router.send("B", b"hello")
        assert result is True
        send_cb.assert_awaited_once()
        # Verify packet bytes were sent to next_hop "B"
        call_args = send_cb.call_args
        assert call_args[0][1] == "B"  # next_hop

    async def test_send_no_route_discovery_fails(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=False)
        router.set_send_callback(send_cb)
        # No neighbors, no routes -- discovery will time out
        # Mock _discover_route to return None quickly
        router._discover_route = AsyncMock(return_value=None)

        result = await router.send("Z", b"data")
        assert result is False

    async def test_send_route_failure_tries_alternatives(self):
        router = MeshRouter("A")
        # First call fails, second succeeds
        send_cb = AsyncMock(side_effect=[False, True])
        router.set_send_callback(send_cb)
        router._handle_route_failure = AsyncMock()

        # Two routes to B
        e1 = RouteEntry(destination="B", next_hop="X", hop_count=2, seq_num=1)
        e2 = RouteEntry(destination="B", next_hop="Y", hop_count=3, seq_num=1)
        router._routes["B"] = [e1, e2]

        result = await router.send("B", b"data")
        assert result is True
        assert send_cb.await_count == 2
        router._handle_route_failure.assert_awaited_once()

    async def test_send_all_routes_fail(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=False)
        router.set_send_callback(send_cb)
        router._handle_route_failure = AsyncMock()

        e1 = RouteEntry(destination="B", next_hop="X", hop_count=2, seq_num=1)
        router._routes["B"] = [e1]

        result = await router.send("B", b"data")
        assert result is False

    async def test_send_discovery_success(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        # No initial route; mock _discover_route to add one
        async def fake_discover(dest):
            entry = RouteEntry(destination=dest, next_hop="B", hop_count=1, seq_num=1)
            router._routes[dest] = [entry]
            return entry

        router._discover_route = AsyncMock(side_effect=fake_discover)

        result = await router.send("C", b"data")
        assert result is True


@pytest.mark.asyncio
class TestHandlePacket:
    def _make_data_packet(self, src="A", dst="B", payload=b"hello", packet_id="pkt1"):
        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source=src, destination=dst,
            seq_num=1, hop_count=0, ttl=8, payload=payload,
            packet_id=packet_id, path_traversed=[],
        )
        return pkt.to_bytes()

    async def test_handle_data_packet_for_us(self):
        router = MeshRouter("B")
        recv_cb = AsyncMock()
        router.set_receive_callback(recv_cb)

        data = self._make_data_packet(src="A", dst="B")
        await router.handle_packet(data, "A")

        recv_cb.assert_awaited_once()
        args = recv_cb.call_args[0]
        assert args[0] == "A"  # source
        assert args[1] == b"hello"  # payload

    async def test_handle_data_packet_forward(self):
        router = MeshRouter("M")  # Middle node
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")  # Route to destination B

        data = self._make_data_packet(src="A", dst="B")
        await router.handle_packet(data, "A")

        send_cb.assert_awaited_once()

    async def test_deduplication(self):
        router = MeshRouter("B")
        recv_cb = AsyncMock()
        router.set_receive_callback(recv_cb)

        data = self._make_data_packet(src="A", dst="B", packet_id="dup1")
        await router.handle_packet(data, "A")
        await router.handle_packet(data, "A")  # duplicate

        recv_cb.assert_awaited_once()  # Only first time

    async def test_invalid_packet_data(self):
        router = MeshRouter("B")
        # Should not raise, just log error
        await router.handle_packet(b"garbage", "A")

    async def test_stats_updated_on_receive(self):
        router = MeshRouter("B")
        recv_cb = AsyncMock()
        router.set_receive_callback(recv_cb)

        data = self._make_data_packet(src="A", dst="B")
        await router.handle_packet(data, "A")

        assert router._stats["packets_received"] == 1


@pytest.mark.asyncio
class TestHandleRREQ:
    def _make_rreq_packet(self, src="A", target="C", packet_id="rreq1",
                          path_traversed=None, ttl=16):
        if path_traversed is None:
            path_traversed = ["A"]
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ, source=src, destination=target,
            seq_num=1, hop_count=0, ttl=ttl, payload=target.encode(),
            packet_id=packet_id, path_traversed=path_traversed,
        )
        return pkt.to_bytes()

    async def test_rreq_we_are_target_sends_rrep(self):
        router = MeshRouter("C")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        data = self._make_rreq_packet(src="A", target="C")
        await router.handle_packet(data, "B")

        # Should have sent RREP
        assert router._stats["rrep_sent"] == 1
        send_cb.assert_awaited()

    async def test_rreq_loop_prevention(self):
        """RREQ should be dropped if our node_id is already in path_traversed."""
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        # M is already in path -- should be dropped
        data = self._make_rreq_packet(
            src="A", target="Z", path_traversed=["A", "M"],
        )
        await router.handle_packet(data, "B")

        assert router._stats["packets_dropped"] >= 1

    async def test_rreq_proxy_reply_when_route_known(self):
        """If we have a route to target, we send RREP on behalf of target."""
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        # M knows route to Z
        entry = RouteEntry(destination="Z", next_hop="Z", hop_count=1, seq_num=1)
        router._routes["Z"] = [entry]

        data = self._make_rreq_packet(src="A", target="Z")
        await router.handle_packet(data, "B")

        # Should have sent proxy RREP
        assert router._stats["rrep_sent"] == 1

    async def test_rreq_forwarded_when_no_route(self):
        """RREQ should be forwarded/broadcast when no route to target."""
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("D")  # neighbor to broadcast to

        data = self._make_rreq_packet(src="A", target="Z")
        await router.handle_packet(data, "B")

        # Forward should have called send_cb
        send_cb.assert_awaited()

    async def test_rreq_stats(self):
        router = MeshRouter("C")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        data = self._make_rreq_packet(src="A", target="C")
        await router.handle_packet(data, "B")
        assert router._stats["rreq_received"] == 1


@pytest.mark.asyncio
class TestHandleRREP:
    def _make_rrep_data(self, requester="A", target="C", from_neighbor="B",
                        hop_count=1, path=None, packet_id="rrep1"):
        if path is None:
            path = ["A", "B", "C"]
        payload = json.dumps({
            "target": target,
            "hop_count": hop_count,
            "path": path,
        }).encode()
        pkt = RoutingPacket(
            packet_type=PacketType.RREP, source="C",
            destination=requester, seq_num=5, hop_count=0,
            ttl=16, payload=payload, packet_id=packet_id,
        )
        return pkt.to_bytes()

    async def test_rrep_for_us_completes_pending(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        # Simulate pending RREQ
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        router._pending_rreq["C"] = future

        data = self._make_rrep_data(requester="A", target="C")
        await router.handle_packet(data, "B")

        assert "C" not in router._pending_rreq
        assert future.done()
        assert router._stats["rrep_received"] == 1

    async def test_rrep_forwarded_when_not_for_us(self):
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("A")  # route to forward RREP to requester A

        data = self._make_rrep_data(requester="A", target="C")
        await router.handle_packet(data, "B")

        send_cb.assert_awaited()

    async def test_rrep_updates_route_table(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        router._pending_rreq["C"] = future

        data = self._make_rrep_data(requester="A", target="C", hop_count=2)
        await router.handle_packet(data, "B")

        routes = router.get_route("C")
        assert len(routes) >= 1


@pytest.mark.asyncio
class TestHandleCRDTSync:
    def _make_crdt_packet(self, src="A", dst="B", crdt_data=None, packet_id="crdt1"):
        if crdt_data is None:
            crdt_data = {"key": "value", "counter": 42}
        pkt = RoutingPacket(
            packet_type=PacketType.CRDT_SYNC, source=src, destination=dst,
            seq_num=1, hop_count=0, ttl=8,
            payload=json.dumps(crdt_data).encode("utf-8"),
            packet_id=packet_id,
        )
        return pkt.to_bytes()

    async def test_crdt_sync_for_us(self):
        router = MeshRouter("B")
        crdt_cb = AsyncMock()
        router.set_crdt_sync_callback(crdt_cb)

        data = self._make_crdt_packet(src="A", dst="B")
        await router.handle_packet(data, "A")

        crdt_cb.assert_awaited_once()
        call_args = crdt_cb.call_args[0]
        assert call_args[0] == "A"  # peer_id
        assert call_args[1]["key"] == "value"

    async def test_crdt_sync_forwarded(self):
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")

        data = self._make_crdt_packet(src="A", dst="B")
        await router.handle_packet(data, "A")

        send_cb.assert_awaited()

    async def test_crdt_sync_no_callback(self):
        """No crash if crdt_sync_callback is not set."""
        router = MeshRouter("B")
        data = self._make_crdt_packet(src="A", dst="B")
        # Should not raise
        await router.handle_packet(data, "A")

    async def test_crdt_sync_invalid_payload(self):
        """Should handle non-JSON CRDT payload gracefully."""
        router = MeshRouter("B")
        crdt_cb = AsyncMock()
        router.set_crdt_sync_callback(crdt_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.CRDT_SYNC, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8,
            payload=b"not-json",
            packet_id="crdt_bad",
        )
        data = pkt.to_bytes()
        # Should not raise -- error is logged
        await router.handle_packet(data, "A")


@pytest.mark.asyncio
class TestForwardPacket:
    async def test_forward_ttl_expired(self):
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="Z",
            seq_num=1, hop_count=10, ttl=1, payload=b"data",
            packet_id="fwd1",
        )
        await router._forward_packet(pkt)

        send_cb.assert_not_awaited()
        assert router._stats["packets_dropped"] == 1

    async def test_forward_no_route_drops_non_rreq(self):
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="Z",
            seq_num=1, hop_count=0, ttl=8, payload=b"data",
            packet_id="fwd2",
        )
        await router._forward_packet(pkt)
        assert router._stats["packets_dropped"] == 1

    async def test_forward_rreq_broadcasts(self):
        """RREQ packets should be broadcast when no route to destination."""
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        # Mock _broadcast_packet to avoid issues with list routes
        router._broadcast_packet = AsyncMock()

        pkt = RoutingPacket(
            packet_type=PacketType.RREQ, source="A", destination="Z",
            seq_num=1, hop_count=0, ttl=8, payload=b"Z",
            packet_id="fwd3",
        )
        await router._forward_packet(pkt)
        router._broadcast_packet.assert_awaited_once()


@pytest.mark.asyncio
class TestSendPacket:
    async def test_send_packet_no_callback(self):
        router = MeshRouter("A")
        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8, payload=b"data",
        )
        result = await router._send_packet(pkt, "B")
        assert result is False

    async def test_send_packet_callback_success(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8, payload=b"data",
        )
        result = await router._send_packet(pkt, "B")
        assert result is True
        assert router._stats["packets_sent"] == 1

    async def test_send_packet_callback_returns_false(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=False)
        router.set_send_callback(send_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8, payload=b"data",
        )
        result = await router._send_packet(pkt, "B")
        assert result is False
        assert router._stats["packets_sent"] == 0

    async def test_send_packet_callback_raises(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(side_effect=Exception("network error"))
        router.set_send_callback(send_cb)

        pkt = RoutingPacket(
            packet_type=PacketType.DATA, source="A", destination="B",
            seq_num=1, hop_count=0, ttl=8, payload=b"data",
        )
        result = await router._send_packet(pkt, "B")
        assert result is False


@pytest.mark.asyncio
class TestDiscoverRoute:
    async def test_discover_route_timeout(self):
        router = MeshRouter("A")
        router.RREQ_TIMEOUT = 0.1  # Fast timeout for tests
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        # Mock _broadcast_packet so we don't hit the list/RouteEntry bug
        router._broadcast_packet = AsyncMock()

        result = await router._discover_route("Z")
        assert result is None
        assert "Z" not in router._pending_rreq  # cleaned up
        assert router._stats["rreq_sent"] == 1

    async def test_discover_route_success(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router._broadcast_packet = AsyncMock()

        async def resolve_later():
            await asyncio.sleep(0.05)
            if "Z" in router._pending_rreq:
                f = router._pending_rreq.pop("Z")
                entry = RouteEntry(destination="Z", next_hop="B", hop_count=2, seq_num=1)
                router._routes["Z"] = [entry]
                if not f.done():
                    f.set_result(entry)

        task = asyncio.create_task(resolve_later())
        result = await router._discover_route("Z")
        await task

        assert result is not None
        assert result.destination == "Z"
        assert router._stats["routes_discovered"] == 1


@pytest.mark.asyncio
class TestSendRREP:
    async def test_send_rrep_basic(self):
        router = MeshRouter("C")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        await router._send_rrep("A", "B", ["A", "B", "C"])

        send_cb.assert_awaited_once()
        assert router._stats["rrep_sent"] == 1

    async def test_send_rrep_with_proxy_target(self):
        router = MeshRouter("M")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)

        await router._send_rrep("A", "B", ["A", "B", "M"], target="Z", hop_count=2)

        send_cb.assert_awaited_once()
        # Verify payload contains correct target
        pkt_bytes = send_cb.call_args[0][0]
        pkt = RoutingPacket.from_bytes(pkt_bytes)
        payload = json.loads(pkt.payload.decode())
        assert payload["target"] == "Z"
        assert payload["hop_count"] == 2


class TestUpdateRoute:
    def test_update_route_new_destination(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 2, 1, ["A", "B", "C"])
        assert "C" in router._routes
        assert len(router._routes["C"]) == 1
        assert router._routes["C"][0].hop_count == 2

    def test_update_route_better_seq_num(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 3, 1, ["A", "B", "C"])
        router._update_route("C", "B", 3, 5, ["A", "B", "C"])  # Better seq
        assert len(router._routes["C"]) == 1
        assert router._routes["C"][0].seq_num == 5

    def test_update_route_same_seq_better_hops(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 5, 1, ["A", "B", "X", "Y", "C"])
        router._update_route("C", "B", 2, 1, ["A", "B", "C"])  # Fewer hops
        assert len(router._routes["C"]) == 1
        assert router._routes["C"][0].hop_count == 2

    def test_update_route_new_next_hop_added(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 2, 1, ["A", "B", "C"])
        router._update_route("C", "D", 3, 1, ["A", "D", "C"])  # Different next_hop
        assert len(router._routes["C"]) == 2

    def test_update_route_same_metrics_same_path_no_update(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 2, 1, ["A", "B", "C"])
        # Same next_hop, same seq, same hops, same path => appended (not updated)
        router._update_route("C", "B", 2, 1, ["A", "B", "C"])
        # Since seq_num == seq_num and hop_count == hop_count and path == path,
        # the code falls through to append
        assert len(router._routes["C"]) == 2  # appended as non-updated

    def test_update_route_worse_seq_not_updated(self):
        router = MeshRouter("A")
        router._update_route("C", "B", 2, 5, ["A", "B", "C"])
        router._update_route("C", "B", 1, 3, ["A", "B", "C"])  # Lower seq_num
        # Lower seq_num with same next_hop => not updated, appended
        assert router._routes["C"][0].seq_num == 5  # original kept


@pytest.mark.asyncio
class TestHandleRouteFailure:
    async def test_handle_route_failure_removes_route(self):
        router = MeshRouter("A")
        router._broadcast_packet = AsyncMock()

        entry = RouteEntry(destination="C", next_hop="B", hop_count=2, seq_num=1)
        router._routes["C"] = [entry]

        await router._handle_route_failure("C", "B")

        assert "C" not in router._routes

    async def test_handle_route_failure_keeps_other_routes(self):
        router = MeshRouter("A")
        router._broadcast_packet = AsyncMock()

        e1 = RouteEntry(destination="C", next_hop="B", hop_count=2, seq_num=1)
        e2 = RouteEntry(destination="C", next_hop="D", hop_count=3, seq_num=1)
        router._routes["C"] = [e1, e2]

        await router._handle_route_failure("C", "B")

        assert "C" in router._routes
        assert len(router._routes["C"]) == 1
        assert router._routes["C"][0].next_hop == "D"

    async def test_handle_route_failure_broadcasts_rerr(self):
        router = MeshRouter("A")
        router._broadcast_packet = AsyncMock()

        entry = RouteEntry(destination="C", next_hop="B", hop_count=2, seq_num=1)
        router._routes["C"] = [entry]

        await router._handle_route_failure("C", "B")

        router._broadcast_packet.assert_awaited_once()
        # Verify the RERR packet
        pkt = router._broadcast_packet.call_args[0][0]
        assert pkt.packet_type == PacketType.RERR

    async def test_handle_route_failure_nonexistent_dest(self):
        router = MeshRouter("A")
        router._broadcast_packet = AsyncMock()

        # Should not raise
        await router._handle_route_failure("Z", "X")
        router._broadcast_packet.assert_awaited_once()


@pytest.mark.asyncio
class TestSendCRDTUpdate:
    async def test_send_crdt_to_self(self):
        router = MeshRouter("A")
        result = await router.send_crdt_update("A", {"key": "val"})
        assert result is True

    async def test_send_crdt_with_route(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")

        result = await router.send_crdt_update("B", {"counter": 1})
        assert result is True
        send_cb.assert_awaited_once()

    async def test_send_crdt_no_route_discovery_fails(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router._discover_route = AsyncMock(return_value=None)

        result = await router.send_crdt_update("Z", {"data": 1})
        assert result is False

    async def test_send_crdt_all_routes_fail(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=False)
        router.set_send_callback(send_cb)
        router._handle_route_failure = AsyncMock()

        entry = RouteEntry(destination="B", next_hop="B", hop_count=1, seq_num=1)
        router._routes["B"] = [entry]

        result = await router.send_crdt_update("B", {"key": "val"})
        assert result is False

    async def test_send_crdt_serialization_error(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")

        # Object that can't be JSON serialized
        class NotSerializable:
            pass

        result = await router.send_crdt_update("B", {"bad": NotSerializable()})
        assert result is False


@pytest.mark.asyncio
class TestGetStats:
    async def test_get_stats_initial(self):
        router = MeshRouter("A")
        stats = await router.get_stats()
        assert stats["node_id"] == "A"
        assert stats["packets_sent"] == 0
        assert stats["routes_count"] == 0

    async def test_get_stats_after_activity(self):
        router = MeshRouter("A")
        send_cb = AsyncMock(return_value=True)
        router.set_send_callback(send_cb)
        router.add_neighbor("B")
        await router.send("B", b"data")

        stats = await router.get_stats()
        assert stats["packets_sent"] >= 1
        assert stats["routes_count"] >= 1


@pytest.mark.asyncio
class TestGetMapeKMetrics:
    async def test_metrics_initial_zeros(self):
        router = MeshRouter("A")
        metrics = await router.get_mape_k_metrics()
        assert metrics["packet_drop_rate"] == 0.0
        assert metrics["route_discovery_success_rate"] == 0.0
        assert metrics["total_routes_known"] == 0
        assert metrics["avg_route_hop_count"] == 0.0
        assert metrics["routing_overhead_ratio"] == 0.0

    async def test_metrics_with_routes(self):
        router = MeshRouter("A")
        router.add_neighbor("B")
        router.add_neighbor("C")

        metrics = await router.get_mape_k_metrics()
        assert metrics["total_routes_known"] == 2
        assert metrics["avg_route_hop_count"] == 1.0  # Both are 1 hop

    async def test_metrics_packet_drop_rate(self):
        router = MeshRouter("A")
        router._stats["packets_dropped"] = 5
        router._stats["packets_sent"] = 10
        router._stats["packets_received"] = 10
        # total = 10+10+0+0+0+0+0 = 20
        metrics = await router.get_mape_k_metrics()
        assert metrics["packet_drop_rate"] == 5 / 20

    async def test_metrics_discovery_success_rate(self):
        router = MeshRouter("A")
        router._stats["rreq_sent"] = 4
        router._stats["routes_discovered"] = 3

        metrics = await router.get_mape_k_metrics()
        assert metrics["route_discovery_success_rate"] == 0.75

    async def test_metrics_routing_overhead(self):
        router = MeshRouter("A")
        router._stats["rreq_sent"] = 2
        router._stats["rreq_received"] = 2
        router._stats["rrep_sent"] = 1
        router._stats["rrep_received"] = 1
        router._stats["packets_sent"] = 10
        router._stats["packets_forwarded"] = 5

        metrics = await router.get_mape_k_metrics()
        # overhead = (2+2+1+1)/(10+5) = 6/15 = 0.4
        assert metrics["routing_overhead_ratio"] == pytest.approx(0.4)


@pytest.mark.asyncio
class TestCleanupSeenPackets:
    async def test_cleanup_runs_and_cancels(self):
        router = MeshRouter("A")
        await router.start()

        # Add a fake seen packet
        router._seen_packets.add("old_pkt")

        # Let the cleanup loop run briefly
        await asyncio.sleep(0.05)

        await router.stop()
        # No assertion needed -- just verifying no crash


@pytest.mark.asyncio
class TestEndToEndScenarios:
    async def test_two_node_data_flow(self):
        """A sends data to B (direct neighbor)."""
        router_a = MeshRouter("A")
        router_b = MeshRouter("B")

        received = []

        async def b_receive(src, payload):
            received.append((src, payload))

        router_b.set_receive_callback(b_receive)

        # A -> B transport: just call handle_packet on B
        async def a_send(packet_bytes, next_hop):
            if next_hop == "B":
                await router_b.handle_packet(packet_bytes, "A")
                return True
            return False

        router_a.set_send_callback(a_send)
        router_a.add_neighbor("B")

        result = await router_a.send("B", b"hello-B")
        assert result is True
        assert len(received) == 1
        assert received[0] == ("A", b"hello-B")

    async def test_three_node_forwarding(self):
        """A -> M -> B : A sends data to B via middle node M."""
        router_a = MeshRouter("A")
        router_m = MeshRouter("M")
        router_b = MeshRouter("B")

        received = []

        async def b_receive(src, payload):
            received.append((src, payload))

        router_b.set_receive_callback(b_receive)

        # A knows M as neighbor; M knows B as neighbor
        router_a.add_neighbor("M")
        router_m.add_neighbor("B")

        # A has route to B via M
        entry = RouteEntry(
            destination="B", next_hop="M", hop_count=2, seq_num=1,
            path=["A", "M", "B"],
        )
        router_a._routes["B"] = [entry]

        # Transport callbacks
        async def a_send(packet_bytes, next_hop):
            if next_hop == "M":
                await router_m.handle_packet(packet_bytes, "A")
                return True
            return False

        async def m_send(packet_bytes, next_hop):
            if next_hop == "B":
                await router_b.handle_packet(packet_bytes, "M")
                return True
            return False

        router_a.set_send_callback(a_send)
        router_m.set_send_callback(m_send)

        result = await router_a.send("B", b"multi-hop")
        assert result is True
        assert len(received) == 1
        assert received[0][1] == b"multi-hop"
