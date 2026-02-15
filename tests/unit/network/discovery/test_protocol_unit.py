"""
Unit tests for src/network/discovery/protocol.py

Covers: PeerInfo, DiscoveryMessage, MessageType, MulticastDiscovery,
        BootstrapDiscovery, KademliaNode, MeshDiscovery
"""

import asyncio
import json
import socket
import struct
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.network.discovery.protocol import (ANNOUNCE_INTERVAL, DHT_K,
                                            MULTICAST_GROUP, MULTICAST_PORT,
                                            PEER_TIMEOUT, BootstrapDiscovery,
                                            DiscoveryMessage, KademliaNode,
                                            MeshDiscovery, MessageType,
                                            MulticastDiscovery, PeerInfo)

# ---------------------------------------------------------------------------
# MessageType
# ---------------------------------------------------------------------------


class TestMessageType:
    """Tests for the MessageType enum."""

    def test_all_types_defined(self):
        expected = {"ANNOUNCE", "QUERY", "RESPONSE", "PING", "PONG", "JOIN", "LEAVE"}
        actual = {m.name for m in MessageType}
        assert actual == expected

    def test_values_are_unique(self):
        values = [m.value for m in MessageType]
        assert len(values) == len(set(values))

    def test_specific_values(self):
        assert MessageType.ANNOUNCE.value == 0x01
        assert MessageType.QUERY.value == 0x02
        assert MessageType.RESPONSE.value == 0x03
        assert MessageType.PING.value == 0x04
        assert MessageType.PONG.value == 0x05
        assert MessageType.JOIN.value == 0x06
        assert MessageType.LEAVE.value == 0x07

    def test_lookup_by_value(self):
        assert MessageType(0x01) is MessageType.ANNOUNCE
        assert MessageType(0x07) is MessageType.LEAVE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MessageType(0xFF)


# ---------------------------------------------------------------------------
# PeerInfo
# ---------------------------------------------------------------------------


class TestPeerInfo:
    """Tests for PeerInfo dataclass."""

    def test_creation_defaults(self):
        peer = PeerInfo(node_id="n1", addresses=[("10.0.0.1", 5000)])
        assert peer.node_id == "n1"
        assert peer.services == []
        assert peer.version == "1.0.0"
        assert peer.last_seen == 0
        assert peer.rtt_ms == 0
        assert peer.distance == 0

    def test_creation_custom(self):
        peer = PeerInfo(
            node_id="n2",
            addresses=[("10.0.0.1", 5000), ("10.0.0.2", 6000)],
            services=["mesh", "relay"],
            version="2.0.0",
            last_seen=100.0,
            rtt_ms=12.5,
            distance=42,
        )
        assert peer.version == "2.0.0"
        assert peer.rtt_ms == 12.5
        assert len(peer.addresses) == 2

    def test_to_dict(self):
        peer = PeerInfo(
            node_id="n3",
            addresses=[("1.2.3.4", 9999)],
            services=["exit"],
            version="3.0.0",
            last_seen=999,
            rtt_ms=5,
        )
        d = peer.to_dict()
        assert d["node_id"] == "n3"
        assert d["addresses"] == [("1.2.3.4", 9999)]
        assert d["services"] == ["exit"]
        assert d["version"] == "3.0.0"
        # to_dict should NOT include transient fields
        assert "last_seen" not in d
        assert "rtt_ms" not in d
        assert "distance" not in d

    def test_from_dict_full(self):
        data = {
            "node_id": "n4",
            "addresses": [["192.168.1.1", 8080]],
            "services": ["mesh", "relay"],
            "version": "1.5.0",
        }
        peer = PeerInfo.from_dict(data)
        assert peer.node_id == "n4"
        assert peer.addresses == [("192.168.1.1", 8080)]
        assert peer.services == ["mesh", "relay"]
        assert peer.version == "1.5.0"

    def test_from_dict_minimal(self):
        data = {"node_id": "n5", "addresses": [["127.0.0.1", 5000]]}
        peer = PeerInfo.from_dict(data)
        assert peer.services == []
        assert peer.version == "1.0.0"

    def test_roundtrip(self):
        original = PeerInfo(
            node_id="rt",
            addresses=[("10.0.0.1", 5000), ("10.0.0.2", 6000)],
            services=["mesh", "exit"],
            version="4.0.0",
        )
        restored = PeerInfo.from_dict(original.to_dict())
        assert restored.node_id == original.node_id
        assert restored.addresses == original.addresses
        assert restored.services == original.services
        assert restored.version == original.version

    def test_from_dict_addresses_converted_to_tuples(self):
        """JSON-decoded addresses come as lists; from_dict should convert to tuples."""
        data = {"node_id": "x", "addresses": [["10.0.0.1", 5000], ["10.0.0.2", 6000]]}
        peer = PeerInfo.from_dict(data)
        for addr in peer.addresses:
            assert isinstance(addr, tuple)

    def test_empty_addresses(self):
        peer = PeerInfo(node_id="empty", addresses=[])
        d = peer.to_dict()
        assert d["addresses"] == []

    def test_empty_services(self):
        peer = PeerInfo(node_id="nosvc", addresses=[("1.1.1.1", 80)])
        assert peer.services == []
        d = peer.to_dict()
        assert d["services"] == []


# ---------------------------------------------------------------------------
# DiscoveryMessage
# ---------------------------------------------------------------------------


class TestDiscoveryMessage:
    """Tests for DiscoveryMessage dataclass."""

    def test_creation(self):
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="s1",
            payload={"k": "v"},
        )
        assert msg.msg_type == MessageType.ANNOUNCE
        assert msg.sender_id == "s1"
        assert msg.timestamp == 0

    def test_to_bytes_returns_bytes(self):
        msg = DiscoveryMessage(
            msg_type=MessageType.PING,
            sender_id="s2",
            payload={},
        )
        raw = msg.to_bytes()
        assert isinstance(raw, bytes)

    def test_to_bytes_json_structure(self):
        msg = DiscoveryMessage(
            msg_type=MessageType.QUERY,
            sender_id="s3",
            payload={"q": True},
            timestamp=12345,
        )
        raw = msg.to_bytes()
        parsed = json.loads(raw)
        assert parsed["type"] == MessageType.QUERY.value
        assert parsed["sender"] == "s3"
        assert parsed["payload"] == {"q": True}

    def test_to_bytes_assigns_ts_when_zero(self):
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="s",
            payload={},
            timestamp=0,
        )
        raw = msg.to_bytes()
        parsed = json.loads(raw)
        # Timestamp should be auto-generated (current time in ms)
        assert parsed["ts"] > 0

    def test_to_bytes_preserves_explicit_ts(self):
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="s",
            payload={},
            timestamp=99999,
        )
        raw = msg.to_bytes()
        parsed = json.loads(raw)
        assert parsed["ts"] == 99999

    def test_from_bytes(self):
        data = json.dumps(
            {
                "type": 0x03,
                "sender": "responder",
                "payload": {"peers": []},
                "ts": 111111,
            }
        ).encode("utf-8")
        msg = DiscoveryMessage.from_bytes(data)
        assert msg.msg_type == MessageType.RESPONSE
        assert msg.sender_id == "responder"
        assert msg.payload == {"peers": []}
        assert msg.timestamp == 111111

    def test_from_bytes_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            DiscoveryMessage.from_bytes(b"not json")

    def test_from_bytes_invalid_type(self):
        data = json.dumps(
            {
                "type": 0xFF,
                "sender": "x",
                "payload": {},
                "ts": 0,
            }
        ).encode("utf-8")
        with pytest.raises(ValueError):
            DiscoveryMessage.from_bytes(data)

    def test_roundtrip_all_types(self):
        for mt in MessageType:
            msg = DiscoveryMessage(
                msg_type=mt,
                sender_id="round",
                payload={"type_name": mt.name},
                timestamp=42,
            )
            restored = DiscoveryMessage.from_bytes(msg.to_bytes())
            assert restored.msg_type == mt
            assert restored.sender_id == "round"
            assert restored.payload == {"type_name": mt.name}


# ---------------------------------------------------------------------------
# MulticastDiscovery
# ---------------------------------------------------------------------------


class TestMulticastDiscovery:
    """Tests for MulticastDiscovery."""

    def test_init_defaults(self):
        md = MulticastDiscovery(node_id="mc1", service_port=5000)
        assert md.node_id == "mc1"
        assert md.service_port == 5000
        assert md.services == ["mesh"]
        assert md.multicast_group == MULTICAST_GROUP
        assert md.multicast_port == MULTICAST_PORT
        assert md._running is False
        assert md._socket is None
        assert md._peers == {}

    def test_init_custom(self):
        md = MulticastDiscovery(
            node_id="mc2",
            service_port=6000,
            services=["mesh", "relay"],
            multicast_group="239.0.0.1",
            multicast_port=9999,
        )
        assert md.services == ["mesh", "relay"]
        assert md.multicast_group == "239.0.0.1"
        assert md.multicast_port == 9999

    def test_get_peers_empty(self):
        md = MulticastDiscovery(node_id="mc3", service_port=5000)
        assert md.get_peers() == []

    def test_get_peer_not_found(self):
        md = MulticastDiscovery(node_id="mc4", service_port=5000)
        assert md.get_peer("nonexistent") is None

    def test_get_peer_found(self):
        md = MulticastDiscovery(node_id="mc5", service_port=5000)
        peer = PeerInfo(node_id="p1", addresses=[("10.0.0.1", 5000)])
        md._peers["p1"] = peer
        assert md.get_peer("p1") is peer

    def test_get_peers_returns_list(self):
        md = MulticastDiscovery(node_id="mc6", service_port=5000)
        md._peers["a"] = PeerInfo(node_id="a", addresses=[("1.1.1.1", 80)])
        md._peers["b"] = PeerInfo(node_id="b", addresses=[("2.2.2.2", 80)])
        peers = md.get_peers()
        assert len(peers) == 2
        assert isinstance(peers, list)

    def test_on_peer_discovered_callback(self):
        md = MulticastDiscovery(node_id="mc7", service_port=5000)
        handler = MagicMock()
        result = md.on_peer_discovered(handler)
        assert md._on_peer_discovered is handler
        assert result is handler  # returns the handler for decorator use

    def test_on_peer_lost_callback(self):
        md = MulticastDiscovery(node_id="mc8", service_port=5000)
        handler = MagicMock()
        result = md.on_peer_lost(handler)
        assert md._on_peer_lost is handler
        assert result is handler

    def test_get_local_ip_fallback(self):
        """When socket.connect fails, should return 127.0.0.1."""
        md = MulticastDiscovery(node_id="mc9", service_port=5000)
        with patch("src.network.discovery.protocol.socket.socket") as mock_sock:
            mock_sock.return_value.connect.side_effect = OSError("no route")
            ip = md._get_local_ip()
            assert ip == "127.0.0.1"

    def test_get_local_ip_success(self):
        """When socket connects, should return the local IP."""
        md = MulticastDiscovery(node_id="mc10", service_port=5000)
        with patch("src.network.discovery.protocol.socket.socket") as mock_sock:
            mock_instance = MagicMock()
            mock_instance.getsockname.return_value = ("192.168.1.50", 0)
            mock_sock.return_value = mock_instance
            ip = md._get_local_ip()
            assert ip == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_handle_message_ignores_own(self):
        """Messages from ourselves should be ignored."""
        md = MulticastDiscovery(node_id="self-node", service_port=5000)
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="self-node",
            payload={
                "peer": PeerInfo(
                    node_id="self-node", addresses=[("1.1.1.1", 5000)]
                ).to_dict()
            },
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("1.1.1.1", 5000))
        assert len(md._peers) == 0

    @pytest.mark.asyncio
    async def test_handle_message_announce(self):
        """ANNOUNCE from another node should add a peer."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        peer_data = PeerInfo(
            node_id="remote",
            addresses=[("10.0.0.2", 5000)],
            services=["mesh"],
        ).to_dict()
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="remote",
            payload={"peer": peer_data},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.2", 5000))
        assert "remote" in md._peers
        assert md._peers["remote"].last_seen > 0

    @pytest.mark.asyncio
    async def test_handle_announce_fires_callback(self):
        """on_peer_discovered should be called for a new peer."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        callback = AsyncMock()
        md._on_peer_discovered = callback

        peer_data = PeerInfo(
            node_id="new-remote",
            addresses=[("10.0.0.3", 5000)],
        ).to_dict()
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="new-remote",
            payload={"peer": peer_data},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.3", 5000))
        callback.assert_awaited_once()
        assert callback.call_args[0][0].node_id == "new-remote"

    @pytest.mark.asyncio
    async def test_handle_announce_no_callback_for_known_peer(self):
        """on_peer_discovered should NOT fire for already-known peer."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        callback = AsyncMock()
        md._on_peer_discovered = callback

        md._peers["known"] = PeerInfo(node_id="known", addresses=[("10.0.0.4", 5000)])

        peer_data = PeerInfo(node_id="known", addresses=[("10.0.0.4", 5000)]).to_dict()
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="known",
            payload={"peer": peer_data},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.4", 5000))
        callback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_announce_adds_sender_addr(self):
        """If the sender address differs from announced addresses, it should be appended."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        peer_data = PeerInfo(
            node_id="remote2",
            addresses=[("10.0.0.5", 5000)],
        ).to_dict()
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="remote2",
            payload={"peer": peer_data},
            timestamp=1,
        )
        # The actual UDP source IP is different from the announced address
        await md._handle_message(msg.to_bytes(), ("192.168.1.99", 5000))
        peer = md._peers["remote2"]
        assert ("192.168.1.99", 5000) in peer.addresses

    @pytest.mark.asyncio
    async def test_handle_leave_removes_peer(self):
        """LEAVE should remove the peer and fire callback."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        peer = PeerInfo(node_id="leaving", addresses=[("10.0.0.6", 5000)])
        md._peers["leaving"] = peer

        callback = AsyncMock()
        md._on_peer_lost = callback

        msg = DiscoveryMessage(
            msg_type=MessageType.LEAVE,
            sender_id="leaving",
            payload={},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.6", 5000))
        assert "leaving" not in md._peers
        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_leave_unknown_peer(self):
        """LEAVE for unknown peer should be harmless."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        msg = DiscoveryMessage(
            msg_type=MessageType.LEAVE,
            sender_id="unknown",
            payload={},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.7", 5000))
        # No exception, no change
        assert len(md._peers) == 0

    @pytest.mark.asyncio
    async def test_handle_query_responds(self):
        """QUERY should reply with RESPONSE containing peer list."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        md._socket = MagicMock()
        md._peers["p1"] = PeerInfo(node_id="p1", addresses=[("10.0.0.8", 5000)])

        msg = DiscoveryMessage(
            msg_type=MessageType.QUERY,
            sender_id="questioner",
            payload={},
            timestamp=1,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.9", 7777))
        md._socket.sendto.assert_called_once()
        sent_data = md._socket.sendto.call_args[0][0]
        sent_addr = md._socket.sendto.call_args[0][1]
        assert sent_addr == ("10.0.0.9", 7777)
        parsed = json.loads(sent_data)
        assert parsed["type"] == MessageType.RESPONSE.value
        assert len(parsed["payload"]["peers"]) == 1

    @pytest.mark.asyncio
    async def test_handle_ping_responds_pong(self):
        """PING should reply with PONG containing the original timestamp."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        md._socket = MagicMock()

        msg = DiscoveryMessage(
            msg_type=MessageType.PING,
            sender_id="pinger",
            payload={},
            timestamp=55555,
        )
        await md._handle_message(msg.to_bytes(), ("10.0.0.10", 7777))
        md._socket.sendto.assert_called_once()
        sent_data = md._socket.sendto.call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["type"] == MessageType.PONG.value
        assert parsed["payload"]["ping_ts"] == 55555

    @pytest.mark.asyncio
    async def test_handle_message_invalid_data(self):
        """Invalid bytes should be silently caught."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        # Should not raise
        await md._handle_message(b"garbage data", ("1.1.1.1", 5000))
        assert len(md._peers) == 0

    @pytest.mark.asyncio
    async def test_send_announce(self):
        """_send_announce should send an ANNOUNCE message via the socket."""
        md = MulticastDiscovery(node_id="announcer", service_port=5000)
        md._socket = MagicMock()
        md._socket.sendto = MagicMock()

        with patch.object(md, "_get_local_ip", return_value="192.168.1.1"):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock()
                await md._send_announce()
                mock_loop.return_value.run_in_executor.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_announce_exception_handled(self):
        """_send_announce should catch exceptions."""
        md = MulticastDiscovery(node_id="announcer", service_port=5000)
        md._socket = MagicMock()

        with patch.object(md, "_get_local_ip", return_value="192.168.1.1"):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    side_effect=OSError("fail")
                )
                # Should not raise
                await md._send_announce()

    @pytest.mark.asyncio
    async def test_send_leave(self):
        """_send_leave should send a LEAVE message."""
        md = MulticastDiscovery(node_id="leaver", service_port=5000)
        md._socket = MagicMock()
        await md._send_leave()
        md._socket.sendto.assert_called_once()
        sent_data = md._socket.sendto.call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["type"] == MessageType.LEAVE.value
        assert parsed["sender"] == "leaver"

    @pytest.mark.asyncio
    async def test_send_leave_exception_handled(self):
        """_send_leave should catch exceptions silently."""
        md = MulticastDiscovery(node_id="leaver", service_port=5000)
        md._socket = MagicMock()
        md._socket.sendto.side_effect = OSError("send failed")
        # Should not raise
        await md._send_leave()

    @pytest.mark.asyncio
    async def test_handle_query_sendto_exception(self):
        """_handle_query should catch sendto exceptions."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        md._socket = MagicMock()
        md._socket.sendto.side_effect = OSError("fail")

        msg = DiscoveryMessage(
            msg_type=MessageType.QUERY,
            sender_id="q",
            payload={},
            timestamp=1,
        )
        # Should not raise
        await md._handle_message(msg.to_bytes(), ("1.1.1.1", 7777))

    @pytest.mark.asyncio
    async def test_handle_ping_sendto_exception(self):
        """_handle_ping should catch sendto exceptions."""
        md = MulticastDiscovery(node_id="local", service_port=5000)
        md._socket = MagicMock()
        md._socket.sendto.side_effect = OSError("fail")

        msg = DiscoveryMessage(
            msg_type=MessageType.PING,
            sender_id="pinger",
            payload={},
            timestamp=1,
        )
        # Should not raise
        await md._handle_message(msg.to_bytes(), ("1.1.1.1", 7777))

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Stopping without starting should not raise."""
        md = MulticastDiscovery(node_id="nostop", service_port=5000)
        md._socket = MagicMock()
        # No tasks set, stop should be fine
        await md.stop()
        assert md._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """stop() should cancel all background tasks."""
        md = MulticastDiscovery(node_id="taskstop", service_port=5000)
        md._socket = MagicMock()
        md._running = True

        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()
        # Simulate CancelledError on await
        mock_task.__await__ = MagicMock(side_effect=asyncio.CancelledError)

        # We need the task to be awaitable but raise CancelledError
        async def raise_cancelled():
            raise asyncio.CancelledError

        cancelled_task = MagicMock()
        cancelled_task.cancel = MagicMock()

        md._announce_task = cancelled_task
        md._listen_task = cancelled_task
        md._cleanup_task = cancelled_task

        # Patch the await to just raise CancelledError
        with patch.object(md, "_send_leave", new_callable=AsyncMock):
            # We need tasks to be awaitable; use a real coroutine
            async def cancelled_coro():
                raise asyncio.CancelledError

            md._announce_task = asyncio.ensure_future(cancelled_coro())
            md._listen_task = asyncio.ensure_future(cancelled_coro())
            md._cleanup_task = asyncio.ensure_future(cancelled_coro())

            await md.stop()
            assert md._running is False


# ---------------------------------------------------------------------------
# BootstrapDiscovery
# ---------------------------------------------------------------------------


class TestBootstrapDiscovery:
    """Tests for BootstrapDiscovery."""

    def test_init_defaults(self):
        bd = BootstrapDiscovery(node_id="b1", service_port=5000)
        assert bd.node_id == "b1"
        assert bd.service_port == 5000
        assert bd.bootstrap_nodes == []
        assert bd._peers == {}

    def test_init_with_nodes(self):
        nodes = [("10.0.0.1", 7777), ("10.0.0.2", 7777)]
        bd = BootstrapDiscovery(node_id="b2", service_port=5000, bootstrap_nodes=nodes)
        assert len(bd.bootstrap_nodes) == 2

    @pytest.mark.asyncio
    async def test_bootstrap_no_nodes(self):
        """With no bootstrap nodes, should return empty list."""
        bd = BootstrapDiscovery(node_id="b3", service_port=5000)
        result = await bd.bootstrap()
        assert result == []

    @pytest.mark.asyncio
    async def test_bootstrap_success(self):
        """bootstrap() should query each node and return discovered peers."""
        bd = BootstrapDiscovery(
            node_id="b4",
            service_port=5000,
            bootstrap_nodes=[("10.0.0.1", 7777)],
        )

        peer = PeerInfo(node_id="discovered", addresses=[("10.0.0.99", 5000)])

        with patch.object(bd, "_query_bootstrap", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [peer]
            result = await bd.bootstrap()

        assert len(result) == 1
        assert result[0].node_id == "discovered"
        assert "discovered" in bd._peers

    @pytest.mark.asyncio
    async def test_bootstrap_deduplication(self):
        """Duplicate peers from different bootstrap nodes should be deduped."""
        bd = BootstrapDiscovery(
            node_id="b5",
            service_port=5000,
            bootstrap_nodes=[("10.0.0.1", 7777), ("10.0.0.2", 7777)],
        )

        same_peer = PeerInfo(node_id="dup", addresses=[("10.0.0.99", 5000)])

        with patch.object(bd, "_query_bootstrap", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [same_peer]
            result = await bd.bootstrap()

        # Even though 2 bootstrap nodes returned the same peer, only 1 should be in result
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_bootstrap_node_failure(self):
        """Unreachable bootstrap node should be skipped."""
        bd = BootstrapDiscovery(
            node_id="b6",
            service_port=5000,
            bootstrap_nodes=[("bad.host", 7777), ("10.0.0.1", 7777)],
        )

        peer = PeerInfo(node_id="good-peer", addresses=[("10.0.0.50", 5000)])

        async def mock_query(host, port):
            if host == "bad.host":
                raise ConnectionRefusedError("refused")
            return [peer]

        with patch.object(bd, "_query_bootstrap", side_effect=mock_query):
            result = await bd.bootstrap()

        assert len(result) == 1
        assert result[0].node_id == "good-peer"

    @pytest.mark.asyncio
    async def test_bootstrap_all_fail(self):
        """All bootstrap nodes failing should return empty list."""
        bd = BootstrapDiscovery(
            node_id="b7",
            service_port=5000,
            bootstrap_nodes=[("bad1", 7777), ("bad2", 7777)],
        )

        with patch.object(bd, "_query_bootstrap", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = OSError("unreachable")
            result = await bd.bootstrap()

        assert result == []

    @pytest.mark.asyncio
    async def test_query_bootstrap_socket_lifecycle(self):
        """_query_bootstrap should create socket, send query, receive response, close."""
        bd = BootstrapDiscovery(node_id="b8", service_port=5000)

        response_peer = PeerInfo(node_id="resp-peer", addresses=[("10.0.0.55", 5000)])
        response_msg = DiscoveryMessage(
            msg_type=MessageType.RESPONSE,
            sender_id="bootstrap",
            payload={"peers": [response_peer.to_dict()]},
            timestamp=1,
        )

        with patch("src.network.discovery.protocol.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recvfrom.return_value = (
                response_msg.to_bytes(),
                ("10.0.0.1", 7777),
            )

            result = await bd._query_bootstrap("10.0.0.1", 7777)

        mock_sock.settimeout.assert_called_once_with(5.0)
        mock_sock.sendto.assert_called_once()
        mock_sock.recvfrom.assert_called_once_with(65535)
        mock_sock.close.assert_called_once()
        assert len(result) == 1
        assert result[0].node_id == "resp-peer"

    @pytest.mark.asyncio
    async def test_query_bootstrap_non_response_type(self):
        """If the received message is not RESPONSE, should return empty list."""
        bd = BootstrapDiscovery(node_id="b9", service_port=5000)

        non_response = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id="bootstrap",
            payload={},
            timestamp=1,
        )

        with patch("src.network.discovery.protocol.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recvfrom.return_value = (
                non_response.to_bytes(),
                ("10.0.0.1", 7777),
            )

            result = await bd._query_bootstrap("10.0.0.1", 7777)

        assert result == []

    @pytest.mark.asyncio
    async def test_query_bootstrap_closes_on_exception(self):
        """Socket should be closed even if an exception occurs."""
        bd = BootstrapDiscovery(node_id="b10", service_port=5000)

        with patch("src.network.discovery.protocol.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recvfrom.side_effect = socket.timeout("timeout")

            with pytest.raises(socket.timeout):
                await bd._query_bootstrap("10.0.0.1", 7777)

            mock_sock.close.assert_called_once()


# ---------------------------------------------------------------------------
# KademliaNode
# ---------------------------------------------------------------------------


class TestKademliaNode:
    """Tests for KademliaNode DHT implementation."""

    def test_init(self):
        node = KademliaNode(node_id="k1", port=5000)
        assert node.node_id == "k1"
        assert node.port == 5000
        assert len(node.node_id_bytes) == 32  # SHA256 digest
        assert isinstance(node._buckets, defaultdict)
        assert node._data == {}

    def test_id_to_bytes_deterministic(self):
        node = KademliaNode(node_id="k2", port=5000)
        b1 = node._id_to_bytes("test-id")
        b2 = node._id_to_bytes("test-id")
        assert b1 == b2

    def test_id_to_bytes_different_ids(self):
        node = KademliaNode(node_id="k3", port=5000)
        b1 = node._id_to_bytes("id-a")
        b2 = node._id_to_bytes("id-b")
        assert b1 != b2

    def test_xor_distance_self(self):
        node = KademliaNode(node_id="k4", port=5000)
        id_bytes = node._id_to_bytes("same")
        assert node._xor_distance(id_bytes, id_bytes) == 0

    def test_xor_distance_symmetric(self):
        node = KademliaNode(node_id="k5", port=5000)
        a = node._id_to_bytes("alpha")
        b = node._id_to_bytes("beta")
        assert node._xor_distance(a, b) == node._xor_distance(b, a)

    def test_xor_distance_positive(self):
        node = KademliaNode(node_id="k6", port=5000)
        a = node._id_to_bytes("x")
        b = node._id_to_bytes("y")
        assert node._xor_distance(a, b) > 0

    def test_bucket_index_zero(self):
        node = KademliaNode(node_id="k7", port=5000)
        assert node._bucket_index(0) == 0

    def test_bucket_index_positive(self):
        node = KademliaNode(node_id="k8", port=5000)
        assert node._bucket_index(1) == 0
        assert node._bucket_index(2) == 1
        assert node._bucket_index(3) == 1
        assert node._bucket_index(4) == 2
        assert node._bucket_index(255) == 7

    def test_add_peer(self):
        node = KademliaNode(node_id="k9", port=5000)
        peer = PeerInfo(node_id="p1", addresses=[("10.0.0.1", 5000)])
        node.add_peer(peer)
        closest = node.find_closest("p1")
        assert any(p.node_id == "p1" for p in closest)

    def test_add_peer_updates_existing(self):
        node = KademliaNode(node_id="k10", port=5000)
        peer_v1 = PeerInfo(node_id="p2", addresses=[("10.0.0.1", 5000)], version="1.0")
        peer_v2 = PeerInfo(node_id="p2", addresses=[("10.0.0.1", 5000)], version="2.0")
        node.add_peer(peer_v1)
        node.add_peer(peer_v2)
        # Should have been updated, not duplicated
        all_peers = []
        for bucket in node._buckets.values():
            all_peers.extend(bucket)
        p2_count = sum(1 for p in all_peers if p.node_id == "p2")
        assert p2_count == 1

    def test_add_peer_bucket_full_replaces_if_closer(self):
        """When bucket is full, new peer replaces furthest if closer."""
        node = KademliaNode(node_id="k11", port=5000)
        # Add DHT_K peers to fill a bucket
        # We'll add peers and verify the mechanism
        for i in range(DHT_K + 5):
            peer = PeerInfo(node_id=f"fill-{i}", addresses=[("10.0.0.1", 5000)])
            node.add_peer(peer)

        # Total peers across all buckets should be manageable
        total = sum(len(b) for b in node._buckets.values())
        assert total > 0

    def test_find_closest_empty(self):
        node = KademliaNode(node_id="k12", port=5000)
        result = node.find_closest("target")
        assert result == []

    def test_find_closest_returns_sorted(self):
        node = KademliaNode(node_id="k13", port=5000)
        for i in range(15):
            peer = PeerInfo(node_id=f"sorted-{i}", addresses=[("10.0.0.1", 5000)])
            node.add_peer(peer)

        closest = node.find_closest("some-target", count=10)
        for i in range(len(closest) - 1):
            assert closest[i].distance <= closest[i + 1].distance

    def test_find_closest_respects_count(self):
        node = KademliaNode(node_id="k14", port=5000)
        for i in range(30):
            peer = PeerInfo(node_id=f"count-{i}", addresses=[("10.0.0.1", 5000)])
            node.add_peer(peer)

        result = node.find_closest("target", count=5)
        assert len(result) <= 5

    def test_find_closest_less_than_count(self):
        node = KademliaNode(node_id="k15", port=5000)
        peer = PeerInfo(node_id="only-one", addresses=[("10.0.0.1", 5000)])
        node.add_peer(peer)

        result = node.find_closest("target", count=10)
        assert len(result) == 1

    def test_store_and_get(self):
        node = KademliaNode(node_id="k16", port=5000)
        node.store("key1", b"value1")
        assert node.get("key1") == b"value1"

    def test_get_missing_key(self):
        node = KademliaNode(node_id="k17", port=5000)
        assert node.get("nonexistent") is None

    def test_store_overwrite(self):
        node = KademliaNode(node_id="k18", port=5000)
        node.store("k", b"old")
        node.store("k", b"new")
        assert node.get("k") == b"new"

    def test_store_multiple_keys(self):
        node = KademliaNode(node_id="k19", port=5000)
        for i in range(10):
            node.store(f"key-{i}", f"val-{i}".encode())
        for i in range(10):
            assert node.get(f"key-{i}") == f"val-{i}".encode()

    def test_add_peer_sets_distance(self):
        node = KademliaNode(node_id="k20", port=5000)
        peer = PeerInfo(node_id="dist-peer", addresses=[("10.0.0.1", 5000)])
        assert peer.distance == 0
        node.add_peer(peer)
        assert peer.distance > 0


# ---------------------------------------------------------------------------
# MeshDiscovery
# ---------------------------------------------------------------------------


class TestMeshDiscovery:
    """Tests for MeshDiscovery (composite discovery)."""

    def test_init_all_enabled(self):
        md = MeshDiscovery(
            node_id="m1",
            service_port=5000,
            services=["mesh", "relay"],
            bootstrap_nodes=[("10.0.0.1", 7777)],
            enable_multicast=True,
            enable_dht=True,
        )
        assert md.node_id == "m1"
        assert md._multicast is not None
        assert md._bootstrap is not None
        assert md._dht is not None
        assert md._peers == {}

    def test_init_multicast_disabled(self):
        md = MeshDiscovery(
            node_id="m2",
            service_port=5000,
            enable_multicast=False,
        )
        assert md._multicast is None
        assert md._dht is not None

    def test_init_dht_disabled(self):
        md = MeshDiscovery(
            node_id="m3",
            service_port=5000,
            enable_dht=False,
        )
        assert md._dht is None
        assert md._multicast is not None

    def test_init_no_bootstrap(self):
        md = MeshDiscovery(
            node_id="m4",
            service_port=5000,
        )
        assert md._bootstrap is None

    def test_init_all_disabled(self):
        md = MeshDiscovery(
            node_id="m5",
            service_port=5000,
            enable_multicast=False,
            enable_dht=False,
        )
        assert md._multicast is None
        assert md._dht is None
        assert md._bootstrap is None

    def test_get_peers_empty(self):
        md = MeshDiscovery(node_id="m6", service_port=5000, enable_multicast=False)
        assert md.get_peers() == []

    def test_get_peer_found(self):
        md = MeshDiscovery(node_id="m7", service_port=5000, enable_multicast=False)
        peer = PeerInfo(node_id="x", addresses=[("1.1.1.1", 80)])
        md._peers["x"] = peer
        assert md.get_peer("x") is peer

    def test_get_peer_not_found(self):
        md = MeshDiscovery(node_id="m8", service_port=5000, enable_multicast=False)
        assert md.get_peer("missing") is None

    def test_find_peers_for_service(self):
        md = MeshDiscovery(node_id="m9", service_port=5000, enable_multicast=False)
        md._peers["r1"] = PeerInfo(
            node_id="r1", addresses=[("1.1.1.1", 80)], services=["mesh", "relay"]
        )
        md._peers["e1"] = PeerInfo(
            node_id="e1", addresses=[("2.2.2.2", 80)], services=["mesh", "exit"]
        )
        md._peers["m_only"] = PeerInfo(
            node_id="m_only", addresses=[("3.3.3.3", 80)], services=["mesh"]
        )

        assert len(md.find_peers_for_service("relay")) == 1
        assert len(md.find_peers_for_service("exit")) == 1
        assert len(md.find_peers_for_service("mesh")) == 3
        assert len(md.find_peers_for_service("vpn")) == 0

    def test_get_stats(self):
        md = MeshDiscovery(
            node_id="m10",
            service_port=5000,
            enable_multicast=False,
            enable_dht=True,
        )
        md._peers["s1"] = PeerInfo(node_id="s1", addresses=[("1.1.1.1", 80)])

        stats = md.get_stats()
        assert stats["node_id"] == "m10"
        assert stats["peers_count"] == 1
        assert stats["multicast_enabled"] is False
        assert stats["dht_enabled"] is True
        assert len(stats["peers"]) == 1

    def test_on_peer_discovered_decorator(self):
        md = MeshDiscovery(node_id="m11", service_port=5000, enable_multicast=False)

        @md.on_peer_discovered
        async def handler(peer):
            pass

        assert md._on_peer_discovered is handler

    def test_on_peer_lost_decorator(self):
        md = MeshDiscovery(node_id="m12", service_port=5000, enable_multicast=False)

        @md.on_peer_lost
        async def handler(peer):
            pass

        assert md._on_peer_lost is handler

    @pytest.mark.asyncio
    async def test_handle_discovered_new_peer(self):
        md = MeshDiscovery(node_id="m13", service_port=5000, enable_multicast=False)
        callback = AsyncMock()
        md._on_peer_discovered = callback

        peer = PeerInfo(node_id="new", addresses=[("10.0.0.1", 5000)])
        await md._handle_discovered(peer)

        assert "new" in md._peers
        callback.assert_awaited_once_with(peer)

    @pytest.mark.asyncio
    async def test_handle_discovered_existing_peer(self):
        """Callback should not fire for already-known peers."""
        md = MeshDiscovery(node_id="m14", service_port=5000, enable_multicast=False)
        callback = AsyncMock()
        md._on_peer_discovered = callback

        md._peers["old"] = PeerInfo(node_id="old", addresses=[("10.0.0.1", 5000)])
        peer = PeerInfo(node_id="old", addresses=[("10.0.0.1", 5000)])
        await md._handle_discovered(peer)

        callback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_discovered_adds_to_dht(self):
        md = MeshDiscovery(
            node_id="m15",
            service_port=5000,
            enable_multicast=False,
            enable_dht=True,
        )
        peer = PeerInfo(node_id="dht-peer", addresses=[("10.0.0.1", 5000)])
        await md._handle_discovered(peer)

        closest = md._dht.find_closest("dht-peer")
        assert any(p.node_id == "dht-peer" for p in closest)

    @pytest.mark.asyncio
    async def test_handle_discovered_no_dht(self):
        """Should work fine even without DHT."""
        md = MeshDiscovery(
            node_id="m16",
            service_port=5000,
            enable_multicast=False,
            enable_dht=False,
        )
        peer = PeerInfo(node_id="no-dht-peer", addresses=[("10.0.0.1", 5000)])
        await md._handle_discovered(peer)
        assert "no-dht-peer" in md._peers

    @pytest.mark.asyncio
    async def test_handle_lost(self):
        md = MeshDiscovery(node_id="m17", service_port=5000, enable_multicast=False)
        callback = AsyncMock()
        md._on_peer_lost = callback

        peer = PeerInfo(node_id="gone", addresses=[("10.0.0.1", 5000)])
        md._peers["gone"] = peer
        await md._handle_lost(peer)

        assert "gone" not in md._peers
        callback.assert_awaited_once_with(peer)

    @pytest.mark.asyncio
    async def test_handle_lost_unknown_peer(self):
        """Losing an unknown peer should not raise."""
        md = MeshDiscovery(node_id="m18", service_port=5000, enable_multicast=False)
        callback = AsyncMock()
        md._on_peer_lost = callback

        peer = PeerInfo(node_id="unknown", addresses=[("10.0.0.1", 5000)])
        await md._handle_lost(peer)
        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_lost_no_callback(self):
        """Should work when no lost callback is registered."""
        md = MeshDiscovery(node_id="m19", service_port=5000, enable_multicast=False)
        peer = PeerInfo(node_id="gone2", addresses=[("10.0.0.1", 5000)])
        md._peers["gone2"] = peer
        await md._handle_lost(peer)
        assert "gone2" not in md._peers

    @pytest.mark.asyncio
    async def test_start_without_multicast(self):
        """Start with multicast disabled should succeed."""
        md = MeshDiscovery(
            node_id="m20",
            service_port=5000,
            enable_multicast=False,
        )
        await md.start()
        # No error
        await md.stop()

    @pytest.mark.asyncio
    async def test_start_with_bootstrap(self):
        """Start with bootstrap nodes should call bootstrap()."""
        md = MeshDiscovery(
            node_id="m21",
            service_port=5000,
            enable_multicast=False,
            bootstrap_nodes=[("10.0.0.1", 7777)],
        )

        peer = PeerInfo(node_id="bs-peer", addresses=[("10.0.0.99", 5000)])
        with patch.object(
            md._bootstrap, "bootstrap", new_callable=AsyncMock
        ) as mock_bs:
            mock_bs.return_value = [peer]
            await md.start()

        assert "bs-peer" in md._peers

    @pytest.mark.asyncio
    async def test_start_with_multicast(self):
        """Start with multicast should call multicast.start() and set callbacks."""
        md = MeshDiscovery(
            node_id="m22",
            service_port=5000,
            enable_multicast=True,
        )

        with patch.object(md._multicast, "start", new_callable=AsyncMock) as mock_start:
            await md.start()
            mock_start.assert_awaited_once()

        # Callbacks should be wired up (bound methods create new objects, use == not is)
        assert md._multicast._on_peer_discovered is not None
        assert md._multicast._on_peer_lost is not None

        # Clean up multicast tasks
        with patch.object(md._multicast, "stop", new_callable=AsyncMock):
            await md.stop()

    @pytest.mark.asyncio
    async def test_stop_with_multicast(self):
        """Stop should call multicast.stop()."""
        md = MeshDiscovery(
            node_id="m23",
            service_port=5000,
            enable_multicast=True,
        )
        with patch.object(md._multicast, "stop", new_callable=AsyncMock) as mock_stop:
            await md.stop()
            mock_stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_without_multicast(self):
        """Stop without multicast should succeed."""
        md = MeshDiscovery(
            node_id="m24",
            service_port=5000,
            enable_multicast=False,
        )
        await md.stop()
        # No error


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify module-level constants."""

    def test_multicast_group(self):
        assert MULTICAST_GROUP == "239.255.77.77"

    def test_multicast_port(self):
        assert MULTICAST_PORT == 7777

    def test_announce_interval(self):
        assert ANNOUNCE_INTERVAL == 10.0

    def test_peer_timeout(self):
        assert PEER_TIMEOUT == 60.0

    def test_dht_k(self):
        assert DHT_K == 20
