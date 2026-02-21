"""
Unit tests for src/network/routing/packet_handler.py

Tests cover:
- PacketType enum values
- RoutingPacket dataclass: to_bytes/from_bytes roundtrip, increment_hop
- PacketHandler.__init__
- next_seq_num: increments and wraps at 0xFFFFFFFF
- create_rreq: correct packet fields, pending request tracking
- create_rrep: correct packet fields
- create_rerr: correct packet fields
- create_hello: correct packet fields
- process_packet: deduplication, dispatches to handlers
- _handle_rreq: returns RREP if destination, None if hop limit exceeded
- set_callbacks: wires up all four callbacks
- check_pending_requests: timeout and retry logic, gives up after max retries
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.routing.packet_handler import (
    PacketHandler,
    PacketType,
    RoutingPacket,
)


# ---------------------------------------------------------------------------
# PacketType enum
# ---------------------------------------------------------------------------

class TestPacketType:
    def test_rreq_value(self):
        assert PacketType.RREQ == 1

    def test_rrep_value(self):
        assert PacketType.RREP == 2

    def test_rerr_value(self):
        assert PacketType.RERR == 3

    def test_hello_value(self):
        assert PacketType.HELLO == 4

    def test_data_value(self):
        assert PacketType.DATA == 5

    def test_from_int(self):
        assert PacketType(1) is PacketType.RREQ
        assert PacketType(5) is PacketType.DATA

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PacketType(99)

    def test_is_int_enum(self):
        # IntEnum members compare equal to their integer values
        assert PacketType.RREQ == 1
        assert PacketType.HELLO != PacketType.DATA


# ---------------------------------------------------------------------------
# RoutingPacket
# ---------------------------------------------------------------------------

class TestRoutingPacket:
    def _make_packet(self, **overrides):
        defaults = dict(
            packet_type=PacketType.DATA,
            source="nodeA",
            destination="nodeB",
            seq_num=42,
            hop_count=3,
            flags=0,
            payload=b"hello",
        )
        defaults.update(overrides)
        return RoutingPacket(**defaults)

    def test_to_bytes_returns_bytes(self):
        pkt = self._make_packet()
        data = pkt.to_bytes()
        assert isinstance(data, bytes)
        assert len(data) >= 41  # header is 41 bytes

    def test_roundtrip_basic(self):
        pkt = self._make_packet()
        data = pkt.to_bytes()
        restored = RoutingPacket.from_bytes(data)

        assert restored.packet_type == pkt.packet_type
        assert restored.source == pkt.source
        assert restored.destination == pkt.destination
        assert restored.seq_num == pkt.seq_num
        assert restored.hop_count == pkt.hop_count
        assert restored.flags == pkt.flags
        assert restored.payload == pkt.payload

    def test_roundtrip_empty_payload(self):
        pkt = self._make_packet(payload=b"")
        restored = RoutingPacket.from_bytes(pkt.to_bytes())
        assert restored.payload == b""

    def test_roundtrip_large_payload(self):
        big = b"X" * 5000
        pkt = self._make_packet(payload=big)
        restored = RoutingPacket.from_bytes(pkt.to_bytes())
        assert restored.payload == big

    def test_roundtrip_all_packet_types(self):
        for pt in PacketType:
            pkt = self._make_packet(packet_type=pt)
            restored = RoutingPacket.from_bytes(pkt.to_bytes())
            assert restored.packet_type == pt

    def test_from_bytes_too_short_raises(self):
        # Header is 43 bytes; anything shorter must raise
        with pytest.raises(ValueError, match="Packet too short"):
            RoutingPacket.from_bytes(b"\x00" * 42)

    def test_from_bytes_integer_packet_type_coerced(self):
        # __post_init__ converts int to PacketType
        pkt = RoutingPacket(
            packet_type=1,  # type: ignore[arg-type]
            source="A",
            destination="B",
            seq_num=1,
        )
        assert pkt.packet_type is PacketType.RREQ

    def test_increment_hop_creates_copy(self):
        pkt = self._make_packet(hop_count=5)
        incremented = pkt.increment_hop()

        assert incremented is not pkt
        assert incremented.hop_count == 6
        assert pkt.hop_count == 5  # original unchanged

    def test_increment_hop_preserves_fields(self):
        pkt = self._make_packet(
            packet_type=PacketType.RREQ,
            source="src",
            destination="dst",
            seq_num=7,
            flags=3,
            payload=b"data",
            origin="orig",
        )
        incremented = pkt.increment_hop()

        assert incremented.packet_type == PacketType.RREQ
        assert incremented.source == "src"
        assert incremented.destination == "dst"
        assert incremented.seq_num == 7
        assert incremented.flags == 3
        assert incremented.payload == b"data"
        assert incremented.origin == "orig"

    def test_default_timestamp_is_float(self):
        pkt = self._make_packet()
        assert isinstance(pkt.timestamp, float)
        assert pkt.timestamp > 0


# ---------------------------------------------------------------------------
# PacketHandler.__init__
# ---------------------------------------------------------------------------

class TestPacketHandlerInit:
    def test_local_node_id_stored(self):
        handler = PacketHandler("node-X")
        assert handler.local_node_id == "node-X"

    def test_seq_num_starts_at_zero(self):
        handler = PacketHandler("node-X")
        assert handler._seq_num == 0

    def test_pending_requests_empty(self):
        handler = PacketHandler("node-X")
        assert handler._pending_requests == {}

    def test_seen_packets_empty(self):
        handler = PacketHandler("node-X")
        assert handler._seen_packets == {}

    def test_callbacks_none_initially(self):
        handler = PacketHandler("node-X")
        assert handler._on_route_request is None
        assert handler._on_route_reply is None
        assert handler._on_route_error is None
        assert handler._on_hello is None


# ---------------------------------------------------------------------------
# next_seq_num
# ---------------------------------------------------------------------------

class TestNextSeqNum:
    def test_increments_from_zero(self):
        handler = PacketHandler("A")
        assert handler.next_seq_num() == 1
        assert handler.next_seq_num() == 2
        assert handler.next_seq_num() == 3

    def test_wraps_at_max(self):
        handler = PacketHandler("A")
        handler._seq_num = 0xFFFFFFFF
        # Next should wrap to 1 (increments then masks)
        assert handler.next_seq_num() == 0

    def test_wrap_then_continues(self):
        handler = PacketHandler("A")
        handler._seq_num = 0xFFFFFFFF
        handler.next_seq_num()  # => 0
        assert handler.next_seq_num() == 1

    def test_returns_new_value_each_call(self):
        handler = PacketHandler("A")
        nums = [handler.next_seq_num() for _ in range(10)]
        assert nums == list(range(1, 11))


# ---------------------------------------------------------------------------
# create_rreq
# ---------------------------------------------------------------------------

class TestCreateRREQ:
    def test_packet_type_is_rreq(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.packet_type == PacketType.RREQ

    def test_source_is_local_node(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.source == "node-A"

    def test_destination_is_target(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.destination == "node-Z"

    def test_origin_is_local_node(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.origin == "node-A"

    def test_hop_count_zero(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.hop_count == 0

    def test_seq_num_increments(self):
        handler = PacketHandler("node-A")
        pkt1 = handler.create_rreq("node-Z")
        pkt2 = handler.create_rreq("node-W")
        assert pkt2.seq_num == pkt1.seq_num + 1

    def test_pending_request_tracked(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rreq("node-Z")
        assert pkt.seq_num in handler._pending_requests
        dest, ts, retries = handler._pending_requests[pkt.seq_num]
        assert dest == "node-Z"
        assert retries == 0
        assert abs(ts - time.time()) < 2.0


# ---------------------------------------------------------------------------
# create_rrep
# ---------------------------------------------------------------------------

class TestCreateRREP:
    def _make_rreq(self, source="node-A", destination="node-B", origin="node-A", seq_num=10):
        return RoutingPacket(
            packet_type=PacketType.RREQ,
            source=source,
            destination=destination,
            seq_num=seq_num,
            hop_count=2,
            origin=origin,
        )

    def test_packet_type_is_rrep(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq()
        rrep = handler.create_rrep(rreq, hop_count=3)
        assert rrep.packet_type == PacketType.RREP

    def test_source_is_local_node(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq()
        rrep = handler.create_rrep(rreq, hop_count=3)
        assert rrep.source == "node-B"

    def test_destination_is_rreq_origin(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq(origin="node-A")
        rrep = handler.create_rrep(rreq, hop_count=3)
        assert rrep.destination == "node-A"

    def test_origin_is_rreq_destination(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq(destination="node-B")
        rrep = handler.create_rrep(rreq, hop_count=3)
        assert rrep.origin == "node-B"

    def test_hop_count_set(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq()
        rrep = handler.create_rrep(rreq, hop_count=5)
        assert rrep.hop_count == 5

    def test_seq_num_is_new(self):
        handler = PacketHandler("node-B")
        rreq = self._make_rreq(seq_num=99)
        rrep = handler.create_rrep(rreq, hop_count=1)
        # RREP gets its own sequence number from handler
        assert rrep.seq_num == 1


# ---------------------------------------------------------------------------
# create_rerr
# ---------------------------------------------------------------------------

class TestCreateRERR:
    def test_packet_type_is_rerr(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rerr("node-X", seq_num=7)
        assert pkt.packet_type == PacketType.RERR

    def test_source_is_local_node(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rerr("node-X", seq_num=7)
        assert pkt.source == "node-A"

    def test_destination_is_empty_broadcast(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rerr("node-X", seq_num=7)
        assert pkt.destination == ""

    def test_seq_num_passed_through(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rerr("node-X", seq_num=42)
        assert pkt.seq_num == 42

    def test_payload_contains_unreachable_node(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_rerr("node-X", seq_num=1)
        # payload is the unreachable node encoded and padded to 16 bytes
        unreachable = pkt.payload.rstrip(b"\x00").decode()
        assert unreachable == "node-X"


# ---------------------------------------------------------------------------
# create_hello
# ---------------------------------------------------------------------------

class TestCreateHello:
    def test_packet_type_is_hello(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_hello()
        assert pkt.packet_type == PacketType.HELLO

    def test_source_is_local_node(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_hello()
        assert pkt.source == "node-A"

    def test_destination_is_empty_broadcast(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_hello()
        assert pkt.destination == ""

    def test_hop_count_zero(self):
        handler = PacketHandler("node-A")
        pkt = handler.create_hello()
        assert pkt.hop_count == 0

    def test_seq_num_increments(self):
        handler = PacketHandler("node-A")
        h1 = handler.create_hello()
        h2 = handler.create_hello()
        assert h2.seq_num == h1.seq_num + 1


# ---------------------------------------------------------------------------
# process_packet: deduplication and dispatch
# ---------------------------------------------------------------------------

class TestProcessPacket:
    def _make_packet(self, packet_type, seq_num, source="node-X", destination="node-A"):
        return RoutingPacket(
            packet_type=packet_type,
            source=source,
            destination=destination,
            seq_num=seq_num,
        )

    def test_deduplication_returns_none_on_second_call(self):
        handler = PacketHandler("node-A")
        pkt = self._make_packet(PacketType.HELLO, seq_num=100)
        handler.process_packet(pkt, "neighbor-1")
        result = handler.process_packet(pkt, "neighbor-1")
        assert result is None

    def test_seen_packet_recorded_after_first_process(self):
        handler = PacketHandler("node-A")
        pkt = self._make_packet(PacketType.HELLO, seq_num=200)
        handler.process_packet(pkt, "neighbor-1")
        assert 200 in handler._seen_packets

    def test_hello_dispatches_to_hello_callback(self):
        handler = PacketHandler("node-A")
        cb = MagicMock()
        handler.set_callbacks(on_hello=cb)
        pkt = self._make_packet(PacketType.HELLO, seq_num=300, source="neighbor-1")
        handler.process_packet(pkt, "neighbor-1")
        cb.assert_called_once()

    def test_rrep_dispatches_to_rrep_callback(self):
        handler = PacketHandler("node-A")
        cb = MagicMock()
        handler.set_callbacks(on_route_reply=cb)
        pkt = self._make_packet(PacketType.RREP, seq_num=400)
        handler.process_packet(pkt, "neighbor-1")
        cb.assert_called_once()

    def test_rerr_dispatches_to_rerr_callback(self):
        handler = PacketHandler("node-A")
        cb = MagicMock()
        handler.set_callbacks(on_route_error=cb)
        pkt = RoutingPacket(
            packet_type=PacketType.RERR,
            source="neighbor-1",
            destination="",
            seq_num=500,
            payload=b"node-X\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        )
        handler.process_packet(pkt, "neighbor-1")
        cb.assert_called_once_with("node-X", "neighbor-1")

    def test_rreq_addressed_to_us_returns_rrep(self):
        handler = PacketHandler("node-A")
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-X",
            destination="node-A",
            seq_num=600,
            hop_count=2,
            origin="node-X",
        )
        result = handler.process_packet(pkt, "node-X")
        assert result is not None
        assert result.packet_type == PacketType.RREP

    def test_process_returns_none_for_rrep(self):
        handler = PacketHandler("node-A")
        pkt = self._make_packet(PacketType.RREP, seq_num=700)
        result = handler.process_packet(pkt, "neighbor-1")
        assert result is None

    def test_process_returns_none_for_rerr(self):
        handler = PacketHandler("node-A")
        pkt = RoutingPacket(
            packet_type=PacketType.RERR,
            source="X",
            destination="",
            seq_num=800,
            payload=b"node-X\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        )
        result = handler.process_packet(pkt, "X")
        assert result is None


# ---------------------------------------------------------------------------
# _handle_rreq
# ---------------------------------------------------------------------------

class TestHandleRREQ:
    def test_returns_rrep_when_we_are_destination(self):
        handler = PacketHandler("node-B")
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-A",
            destination="node-B",
            seq_num=1,
            hop_count=3,
            origin="node-A",
        )
        result = handler._handle_rreq(pkt, "node-A")
        assert result is not None
        assert result.packet_type == PacketType.RREP

    def test_rrep_hop_count_is_rreq_hop_count_plus_one(self):
        handler = PacketHandler("node-B")
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-A",
            destination="node-B",
            seq_num=1,
            hop_count=4,
            origin="node-A",
        )
        result = handler._handle_rreq(pkt, "node-A")
        assert result is not None
        assert result.hop_count == 5

    def test_returns_none_when_hop_limit_exceeded(self):
        handler = PacketHandler("node-B")
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-A",
            destination="node-Z",
            seq_num=1,
            hop_count=PacketHandler.MAX_HOPS,  # == 15
        )
        result = handler._handle_rreq(pkt, "node-A")
        assert result is None

    def test_returns_none_when_not_destination_and_under_limit(self):
        handler = PacketHandler("node-M")
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-A",
            destination="node-Z",
            seq_num=1,
            hop_count=3,
        )
        result = handler._handle_rreq(pkt, "node-A")
        assert result is None

    def test_calls_on_route_request_callback_when_forwarding(self):
        handler = PacketHandler("node-M")
        cb = MagicMock()
        handler.set_callbacks(on_route_request=cb)
        pkt = RoutingPacket(
            packet_type=PacketType.RREQ,
            source="node-A",
            destination="node-Z",
            seq_num=1,
            hop_count=3,
        )
        handler._handle_rreq(pkt, "node-A")
        cb.assert_called_once_with(pkt, "node-A")


# ---------------------------------------------------------------------------
# set_callbacks
# ---------------------------------------------------------------------------

class TestSetCallbacks:
    def test_set_on_route_request(self):
        handler = PacketHandler("A")
        cb = MagicMock()
        handler.set_callbacks(on_route_request=cb)
        assert handler._on_route_request is cb

    def test_set_on_route_reply(self):
        handler = PacketHandler("A")
        cb = MagicMock()
        handler.set_callbacks(on_route_reply=cb)
        assert handler._on_route_reply is cb

    def test_set_on_route_error(self):
        handler = PacketHandler("A")
        cb = MagicMock()
        handler.set_callbacks(on_route_error=cb)
        assert handler._on_route_error is cb

    def test_set_on_hello(self):
        handler = PacketHandler("A")
        cb = MagicMock()
        handler.set_callbacks(on_hello=cb)
        assert handler._on_hello is cb

    def test_set_all_callbacks_at_once(self):
        handler = PacketHandler("A")
        cb1, cb2, cb3, cb4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        handler.set_callbacks(
            on_route_request=cb1,
            on_route_reply=cb2,
            on_route_error=cb3,
            on_hello=cb4,
        )
        assert handler._on_route_request is cb1
        assert handler._on_route_reply is cb2
        assert handler._on_route_error is cb3
        assert handler._on_hello is cb4

    def test_none_does_not_overwrite_existing(self):
        handler = PacketHandler("A")
        cb = MagicMock()
        handler.set_callbacks(on_hello=cb)
        # Passing None for on_hello should NOT overwrite
        handler.set_callbacks(on_hello=None)
        assert handler._on_hello is cb


# ---------------------------------------------------------------------------
# check_pending_requests: timeout and retry logic
# ---------------------------------------------------------------------------

class TestCheckPendingRequests:
    def test_no_pending_returns_empty(self):
        handler = PacketHandler("A")
        result = handler.check_pending_requests()
        assert result == []

    def test_pending_not_yet_timed_out_not_returned(self):
        handler = PacketHandler("A")
        # Set pending request with current timestamp (not expired)
        handler._pending_requests[1] = ("node-Z", time.time(), 0)
        result = handler.check_pending_requests()
        assert result == []

    def test_timed_out_pending_added_to_retry_list(self):
        handler = PacketHandler("A")
        # Timestamp in the past beyond RREQ_TIMEOUT
        old_ts = time.time() - (PacketHandler.RREQ_TIMEOUT + 1.0)
        handler._pending_requests[1] = ("node-Z", old_ts, 0)
        result = handler.check_pending_requests()
        assert len(result) == 1
        dest, retries = result[0]
        assert dest == "node-Z"
        assert retries == 1

    def test_retry_count_incremented_in_pending(self):
        handler = PacketHandler("A")
        old_ts = time.time() - (PacketHandler.RREQ_TIMEOUT + 1.0)
        handler._pending_requests[1] = ("node-Z", old_ts, 0)
        handler.check_pending_requests()
        # Still in pending, retry count now 1
        assert 1 in handler._pending_requests
        _, _, retries = handler._pending_requests[1]
        assert retries == 1

    def test_gives_up_after_max_retries(self):
        handler = PacketHandler("A")
        old_ts = time.time() - (PacketHandler.RREQ_TIMEOUT + 1.0)
        # Already at max retries
        handler._pending_requests[1] = ("node-Z", old_ts, PacketHandler.RREQ_RETRIES)
        result = handler.check_pending_requests()
        # Should NOT be in retry list
        assert result == []
        # Should be removed from pending
        assert 1 not in handler._pending_requests

    def test_multiple_pending_mixed_expiry(self):
        handler = PacketHandler("A")
        now = time.time()
        old_ts = now - (PacketHandler.RREQ_TIMEOUT + 1.0)
        handler._pending_requests[10] = ("node-X", old_ts, 0)   # expired
        handler._pending_requests[20] = ("node-Y", now, 0)       # not expired
        result = handler.check_pending_requests()
        destinations = [d for d, _ in result]
        assert "node-X" in destinations
        assert "node-Y" not in destinations

    def test_get_stats_reflects_pending_count(self):
        handler = PacketHandler("A")
        handler._pending_requests[1] = ("node-Z", time.time(), 0)
        stats = handler.get_stats()
        assert stats["pending_requests"] == 1
        assert stats["sequence_number"] == 0

    def test_get_stats_seen_packets_cache(self):
        handler = PacketHandler("A")
        handler._seen_packets[99] = time.time()
        handler._seen_packets[100] = time.time()
        stats = handler.get_stats()
        assert stats["seen_packets_cache"] == 2
