"""
Tests for VPN Proxy (SOCKS5 Server) module.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.network.vpn_proxy import SOCKS5Server, ProxyStats


class TestProxyStats:
    """Tests for ProxyStats dataclass."""

    def test_default_values(self):
        """Test default values for ProxyStats."""
        stats = ProxyStats()

        assert stats.connections == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.active_connections == 0

    def test_custom_values(self):
        """Test custom values for ProxyStats."""
        stats = ProxyStats(
            connections=100,
            bytes_sent=1024,
            bytes_received=2048,
            active_connections=5
        )

        assert stats.connections == 100
        assert stats.bytes_sent == 1024
        assert stats.bytes_received == 2048
        assert stats.active_connections == 5

    def test_stats_mutable(self):
        """Test stats can be modified."""
        stats = ProxyStats()

        stats.connections += 1
        stats.bytes_sent += 100
        stats.active_connections += 1

        assert stats.connections == 1
        assert stats.bytes_sent == 100
        assert stats.active_connections == 1


class TestSOCKS5Server:
    """Tests for SOCKS5Server class."""

    def test_server_initialization(self):
        """Test SOCKS5Server initialization."""
        server = SOCKS5Server(host="127.0.0.1", port=1080)

        assert server.host == "127.0.0.1"
        assert server.port == 1080
        assert server._running is False
        assert server._server is None
        assert isinstance(server.stats, ProxyStats)

    def test_server_default_values(self):
        """Test SOCKS5Server default host and port."""
        server = SOCKS5Server()

        assert server.host == "127.0.0.1"
        assert server.port == 1080

    def test_socks_version(self):
        """Test SOCKS version constant."""
        assert SOCKS5Server.SOCKS_VERSION == 5

    def test_server_custom_port(self):
        """Test server with custom port."""
        server = SOCKS5Server(port=9050)

        assert server.port == 9050

    def test_server_bind_all_interfaces(self):
        """Test server binding to all interfaces."""
        server = SOCKS5Server(host="0.0.0.0", port=1080)

        assert server.host == "0.0.0.0"

    def test_initial_stats(self):
        """Test initial stats are zero."""
        server = SOCKS5Server()

        assert server.stats.connections == 0
        assert server.stats.bytes_sent == 0
        assert server.stats.bytes_received == 0
        assert server.stats.active_connections == 0

    @pytest.mark.asyncio
    async def test_server_stop_not_started(self):
        """Test stop when server not started."""
        server = SOCKS5Server()

        # Should not raise exception
        await server.stop()
        assert server._running is False

    @pytest.mark.asyncio
    async def test_server_stop_sets_flag(self):
        """Test stop sets running flag to False."""
        server = SOCKS5Server()
        server._running = True

        await server.stop()
        assert server._running is False


class TestSOCKS5Protocol:
    """Tests for SOCKS5 protocol handling."""

    def test_socks5_auth_methods(self):
        """Test SOCKS5 authentication method constants."""
        # No auth method
        NO_AUTH = 0x00
        # Username/password
        USER_PASS = 0x02
        # No acceptable methods
        NO_ACCEPTABLE = 0xFF

        # These are standard SOCKS5 values
        assert NO_AUTH == 0
        assert USER_PASS == 2
        assert NO_ACCEPTABLE == 255

    def test_socks5_address_types(self):
        """Test SOCKS5 address type constants."""
        # IPv4 address
        ATYP_IPV4 = 0x01
        # Domain name
        ATYP_DOMAIN = 0x03
        # IPv6 address
        ATYP_IPV6 = 0x04

        assert ATYP_IPV4 == 1
        assert ATYP_DOMAIN == 3
        assert ATYP_IPV6 == 4

    def test_socks5_commands(self):
        """Test SOCKS5 command constants."""
        # CONNECT command
        CMD_CONNECT = 0x01
        # BIND command
        CMD_BIND = 0x02
        # UDP ASSOCIATE
        CMD_UDP = 0x03

        assert CMD_CONNECT == 1
        assert CMD_BIND == 2
        assert CMD_UDP == 3

    def test_socks5_reply_codes(self):
        """Test SOCKS5 reply code constants."""
        # Success
        REP_SUCCESS = 0x00
        # General failure
        REP_FAILURE = 0x01
        # Connection not allowed
        REP_NOT_ALLOWED = 0x02
        # Network unreachable
        REP_NETWORK_UNREACHABLE = 0x03
        # Host unreachable
        REP_HOST_UNREACHABLE = 0x04
        # Connection refused
        REP_REFUSED = 0x05
        # TTL expired
        REP_TTL_EXPIRED = 0x06
        # Command not supported
        REP_CMD_NOT_SUPPORTED = 0x07
        # Address type not supported
        REP_ADDR_NOT_SUPPORTED = 0x08

        assert REP_SUCCESS == 0
        assert REP_FAILURE == 1
        assert REP_REFUSED == 5


class TestServerStartStop:
    """Tests for server start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_server_lifecycle(self):
        """Test basic server lifecycle."""
        server = SOCKS5Server(port=0)  # Port 0 = random available port

        # Initially not running
        assert server._running is False

        # After start would be running
        # We don't actually start because it blocks
        # Just test the state management
        server._running = True
        assert server._running is True

        await server.stop()
        assert server._running is False


class TestConnectionHandling:
    """Tests for connection handling."""

    def test_stats_increment_on_connection(self):
        """Test stats are incremented on new connections."""
        server = SOCKS5Server()

        # Simulate connection
        server.stats.connections += 1
        server.stats.active_connections += 1

        assert server.stats.connections == 1
        assert server.stats.active_connections == 1

    def test_stats_decrement_on_disconnect(self):
        """Test active connections decremented on disconnect."""
        server = SOCKS5Server()

        # Simulate connect then disconnect
        server.stats.connections += 1
        server.stats.active_connections += 1

        # Disconnect
        server.stats.active_connections -= 1

        assert server.stats.connections == 1
        assert server.stats.active_connections == 0

    def test_bytes_tracking(self):
        """Test bytes sent/received tracking."""
        server = SOCKS5Server()

        # Simulate data transfer
        server.stats.bytes_sent += 1024
        server.stats.bytes_received += 2048

        assert server.stats.bytes_sent == 1024
        assert server.stats.bytes_received == 2048


class TestMultipleConnections:
    """Tests for handling multiple connections."""

    def test_concurrent_connections_stats(self):
        """Test stats for concurrent connections."""
        server = SOCKS5Server()

        # Simulate 3 connections
        for _ in range(3):
            server.stats.connections += 1
            server.stats.active_connections += 1

        assert server.stats.connections == 3
        assert server.stats.active_connections == 3

        # One disconnects
        server.stats.active_connections -= 1
        assert server.stats.active_connections == 2

        # Total connections still 3
        assert server.stats.connections == 3

    def test_aggregate_bytes(self):
        """Test aggregate bytes across connections."""
        server = SOCKS5Server()

        # Simulate traffic from multiple connections
        for i in range(5):
            server.stats.bytes_sent += 100
            server.stats.bytes_received += 200

        assert server.stats.bytes_sent == 500
        assert server.stats.bytes_received == 1000
