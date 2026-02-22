"""Unit tests for src.network.routing.mesh.forwarding."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

forwarding_mod = pytest.importorskip("src.network.routing.mesh.forwarding")
models_mod = pytest.importorskip("src.network.routing.mesh.models")
DeduplicationManager = forwarding_mod.DeduplicationManager
PacketForwarder = forwarding_mod.PacketForwarder
PacketType = models_mod.PacketType
RouteEntry = models_mod.RouteEntry
RoutingPacket = models_mod.RoutingPacket


def _make_packet(packet_type: PacketType = PacketType.DATA, ttl: int = 5) -> RoutingPacket:
    return RoutingPacket(
        packet_type=packet_type,
        source="node-a",
        destination="node-z",
        seq_num=1,
        hop_count=0,
        ttl=ttl,
        payload=b"payload",
        packet_id="pkt-1",
    )


@pytest.mark.asyncio
async def test_forward_ttl_expired_drops_packet():
    table = MagicMock()
    security = MagicMock()
    stats = MagicMock()
    stats.increment = AsyncMock()
    forwarder = PacketForwarder("self", table, security, stats)

    result = await forwarder.forward(_make_packet(ttl=1))
    assert result is False
    stats.increment.assert_awaited_once_with("packets_dropped")


@pytest.mark.asyncio
async def test_forward_no_route_non_rreq_is_dropped():
    table = MagicMock()
    table.get_route.return_value = []
    security = MagicMock()
    stats = MagicMock()
    stats.increment = AsyncMock()
    forwarder = PacketForwarder("self", table, security, stats)

    result = await forwarder.forward(_make_packet(packet_type=PacketType.DATA, ttl=6))
    assert result is False
    stats.increment.assert_awaited_once_with("packets_dropped")


@pytest.mark.asyncio
async def test_forward_no_route_rreq_triggers_broadcast():
    table = MagicMock()
    table.get_route.return_value = []
    security = MagicMock()
    stats = MagicMock()
    stats.increment = AsyncMock()
    forwarder = PacketForwarder("self", table, security, stats)
    forwarder.broadcast = AsyncMock()

    packet = _make_packet(packet_type=PacketType.RREQ, ttl=6)
    result = await forwarder.forward(packet)

    assert result is True
    forwarder.broadcast.assert_awaited_once_with(packet)


@pytest.mark.asyncio
async def test_forward_route_success_increments_sent_and_forwarded():
    table = MagicMock()
    table.get_route.return_value = [RouteEntry("node-z", "next-hop", 2, 1)]
    security = MagicMock()
    security.sign.return_value = b"signed-data"
    stats = MagicMock()
    stats.increment = AsyncMock()
    send_callback = AsyncMock(return_value=True)

    forwarder = PacketForwarder("self", table, security, stats)
    forwarder.set_send_callback(send_callback)

    result = await forwarder.forward(_make_packet(ttl=4))
    assert result is True
    send_callback.assert_awaited_once_with(b"signed-data", "next-hop")
    assert stats.increment.await_args_list[-2].args == ("packets_sent",)
    assert stats.increment.await_args_list[-1].args == ("packets_forwarded",)


@pytest.mark.asyncio
async def test_forward_route_send_failure_counts_drop():
    table = MagicMock()
    table.get_route.return_value = [RouteEntry("node-z", "next-hop", 2, 1)]
    security = MagicMock()
    security.sign.return_value = b"signed"
    stats = MagicMock()
    stats.increment = AsyncMock()
    send_callback = AsyncMock(return_value=False)

    forwarder = PacketForwarder("self", table, security, stats)
    forwarder.set_send_callback(send_callback)

    result = await forwarder.forward(_make_packet(ttl=4))
    assert result is False
    assert stats.increment.await_args_list[-1].args == ("packets_dropped",)


@pytest.mark.asyncio
async def test_send_packet_without_callback_returns_false():
    table = MagicMock()
    security = MagicMock()
    stats = MagicMock()
    stats.increment = AsyncMock()
    forwarder = PacketForwarder("self", table, security, stats)

    result = await forwarder._send_packet(_make_packet(), "next-hop")
    assert result is False


@pytest.mark.asyncio
async def test_send_packet_exception_is_handled():
    table = MagicMock()
    security = MagicMock()
    security.sign.side_effect = RuntimeError("sign failed")
    stats = MagicMock()
    stats.increment = AsyncMock()
    send_callback = AsyncMock(return_value=True)

    forwarder = PacketForwarder("self", table, security, stats)
    forwarder.set_send_callback(send_callback)

    result = await forwarder._send_packet(_make_packet(), "next-hop")
    assert result is False


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_direct_neighbors():
    table = MagicMock()
    table.get_direct_neighbors.return_value = ["n1", "n2", "n3"]
    security = MagicMock()
    security.sign.return_value = b"signed"
    stats = MagicMock()
    stats.increment = AsyncMock()
    send_callback = AsyncMock(return_value=True)

    forwarder = PacketForwarder("self", table, security, stats)
    forwarder.set_send_callback(send_callback)
    await forwarder.broadcast(_make_packet(ttl=5))

    assert send_callback.await_count == 3


@pytest.mark.asyncio
async def test_deduplication_manager_cleanup_loop():
    manager = DeduplicationManager(cleanup_interval=0.01)
    manager.mark_seen("pkt-1")
    assert manager.is_seen("pkt-1") is True

    await manager.start()
    await asyncio.sleep(0.03)
    assert manager.is_seen("pkt-1") is False
    await manager.stop()


@pytest.mark.asyncio
async def test_deduplication_manager_stop_without_start():
    manager = DeduplicationManager()
    await manager.stop()
    assert manager.is_seen("missing") is False
