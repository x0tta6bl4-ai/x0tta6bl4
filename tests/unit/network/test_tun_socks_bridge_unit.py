"""Unit tests for TUN-SOCKS Bridge."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.tun_socks_bridge import TUNSOCKSBridge, BridgeStats


class TestBridgeStats:
    def test_defaults(self):
        stats = BridgeStats()
        assert stats.packets_read == 0
        assert stats.packets_written == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_recv == 0
        assert stats.connections_created == 0
        assert stats.errors == 0


class TestTUNSOCKSBridgeInit:
    def test_defaults(self):
        with patch("src.network.tun_socks_bridge.TUNInterface"):
            bridge = TUNSOCKSBridge()
            assert bridge.socks_host == "127.0.0.1"
            assert bridge.socks_port == 1080
            assert bridge.mtu == 1500

    def test_custom_params(self):
        with patch("src.network.tun_socks_bridge.TUNInterface"):
            bridge = TUNSOCKSBridge(
                tun_name="tun1",
                socks_host="192.168.1.1",
                socks_port=9050,
                mtu=9000,
            )
            assert bridge.socks_host == "192.168.1.1"
            assert bridge.socks_port == 9050
            assert bridge.mtu == 9000


class TestTUNSOCKSBridgeStats:
    def test_get_stats(self):
        with patch("src.network.tun_socks_bridge.TUNInterface"):
            bridge = TUNSOCKSBridge()
            stats = bridge.get_stats()
            assert isinstance(stats, dict)
            assert "packets_read" in stats or "bytes_sent" in stats


class TestTUNSOCKSBridgeStop:
    @pytest.mark.asyncio
    async def test_stop_not_started(self):
        with patch("src.network.tun_socks_bridge.TUNInterface"):
            bridge = TUNSOCKSBridge()
            # Should not raise
            await bridge.stop()
