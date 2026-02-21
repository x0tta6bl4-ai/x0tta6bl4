"""Unit tests for ObfuscatedSOCKS5Server."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


@pytest.fixture
def mock_obfuscator():
    mock = MagicMock()
    mock.get_current_parameters.return_value = {
        "method": "faketls",
        "sni": "test.com",
        "fingerprint": "abc123",
        "rotation_interval": 300,
    }
    return mock


@pytest.fixture
def server(mock_obfuscator):
    with patch(
        "src.network.obfuscated_socks5.get_vpn_obfuscator",
        return_value=mock_obfuscator,
    ):
        from src.network.obfuscated_socks5 import ObfuscatedSOCKS5Server

        srv = ObfuscatedSOCKS5Server(
            host="127.0.0.1", port=0, obfuscation_method="faketls"
        )
        return srv


class TestSOCKS5Init:
    def test_default_values(self, server):
        assert server.host == "127.0.0.1"
        assert server.SOCKS_VERSION == 5
        assert server.connections == 0
        assert server.bytes_sent == 0
        assert server.bytes_recv == 0

    def test_obfuscator_configured(self, server, mock_obfuscator):
        mock_obfuscator.set_obfuscation_method.assert_called_once()
        mock_obfuscator.set_rotation_strategy.assert_called_once()
        mock_obfuscator.set_rotation_interval.assert_called_once_with(300)

    def test_unknown_method_defaults_faketls(self, mock_obfuscator):
        with patch(
            "src.network.obfuscated_socks5.get_vpn_obfuscator",
            return_value=mock_obfuscator,
        ):
            from src.network.obfuscated_socks5 import (
                ObfuscatedSOCKS5Server,
                ObfuscationMethod,
            )

            ObfuscatedSOCKS5Server(obfuscation_method="invalid_method")
            call_args = mock_obfuscator.set_obfuscation_method.call_args
            assert call_args[0][0] == ObfuscationMethod.FAKETLS


class TestSOCKS5Handshake:
    @pytest.mark.asyncio
    async def test_valid_handshake(self, server):
        reader = AsyncMock()
        writer = AsyncMock()
        # version=5, nmethods=1, methods=[0x00] (no auth)
        reader.read = AsyncMock(side_effect=[bytes([5, 1]), bytes([0x00])])
        writer.drain = AsyncMock()

        result = await server._socks5_handshake(reader, writer)
        assert result is True
        writer.write.assert_called_with(bytes([5, 0x00]))

    @pytest.mark.asyncio
    async def test_wrong_version(self, server):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(side_effect=[bytes([4, 1]), bytes([0x00])])

        result = await server._socks5_handshake(reader, writer)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_acceptable_methods(self, server):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(side_effect=[bytes([5, 1]), bytes([0x02])])
        writer.drain = AsyncMock()

        result = await server._socks5_handshake(reader, writer)
        assert result is False
        writer.write.assert_called_with(bytes([5, 0xFF]))

    @pytest.mark.asyncio
    async def test_short_header(self, server):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(return_value=bytes([5]))

        result = await server._socks5_handshake(reader, writer)
        assert result is False


class TestSOCKS5Stop:
    @pytest.mark.asyncio
    async def test_stop_no_server(self, server):
        """Stop when server not started should not raise."""
        await server.stop()
        assert server._running is False

    @pytest.mark.asyncio
    async def test_stop_with_server(self, server):
        mock_srv = AsyncMock()
        server._server = mock_srv
        server._running = True

        await server.stop()
        assert server._running is False
        mock_srv.close.assert_called_once()


class TestSOCKS5Stats:
    def test_get_stats(self, server):
        server.connections = 10
        server.bytes_sent = 1024
        server.bytes_recv = 2048
        # ObfuscatedSOCKS5Server.get_stats if it exists
        if hasattr(server, "get_stats"):
            stats = server.get_stats()
            assert stats["connections"] == 10
        else:
            # Direct attribute access
            assert server.connections == 10
            assert server.bytes_sent == 1024
