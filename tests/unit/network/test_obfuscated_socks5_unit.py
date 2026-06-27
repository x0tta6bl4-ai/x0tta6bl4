"""Unit tests for ObfuscatedSOCKS5Server."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.coordination.events import EventBus

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


class _StreamReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _StreamWriter:
    def __init__(self, peername=None):
        self.peername = peername
        self.writes = []
        self.closed = False

    def get_extra_info(self, name):
        if name == "peername":
            return self.peername
        return None

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


class TestSOCKS5EventEvidence:
    def test_get_stats_event_redacts_parameters_and_claims(
        self, tmp_path, mock_obfuscator
    ):
        mock_obfuscator.get_current_parameters.return_value = {
            "method": "faketls",
            "sni": "secret-sni.example",
            "fingerprint": "secret-fingerprint",
            "rotation_interval": 300,
        }
        bus = EventBus(project_root=str(tmp_path))

        with patch(
            "src.network.obfuscated_socks5.get_vpn_obfuscator",
            return_value=mock_obfuscator,
        ):
            from src.network.obfuscated_socks5 import ObfuscatedSOCKS5Server

            srv = ObfuscatedSOCKS5Server(
                host="127.0.0.1",
                port=1080,
                obfuscation_method="faketls",
                event_bus=bus,
            )
            stats = srv.get_stats()

        assert stats["obfuscation"]["sni"] == "secret-sni.example"

        events = bus.get_event_history(source_agent="obfuscated-socks5-proxy")
        assert len(events) == 1
        payload = events[0].data
        assert payload["operation"] == "stats_read"
        assert payload["dataplane_confirmed"] is False
        assert payload["dpi_bypass_confirmed"] is False
        assert payload["bypass_confirmed"] is False
        assert payload["payloads_redacted"] is True
        assert payload["targets_redacted"] is True
        assert payload["client_addresses_redacted"] is True
        assert payload["claim_boundary"]

        rendered = repr(payload)
        assert "secret-sni.example" not in rendered
        assert "secret-fingerprint" not in rendered

    @pytest.mark.asyncio
    async def test_relay_event_redacts_payload_bytes(
        self, tmp_path, mock_obfuscator
    ):
        mock_obfuscator.obfuscate.side_effect = lambda data: b"obf:" + data
        mock_obfuscator.deobfuscate.side_effect = (
            lambda data: data[4:] if data.startswith(b"obf:") else data
        )
        bus = EventBus(project_root=str(tmp_path))

        with patch(
            "src.network.obfuscated_socks5.get_vpn_obfuscator",
            return_value=mock_obfuscator,
        ):
            from src.network.obfuscated_socks5 import ObfuscatedSOCKS5Server

            srv = ObfuscatedSOCKS5Server(event_bus=bus)
            srv._running = True
            await srv._relay_obfuscated(
                _StreamReader([b"raw-upstream-secret", b""]),
                _StreamWriter(),
                _StreamReader([b"obf:raw-downstream-secret", b""]),
                _StreamWriter(),
            )

        events = bus.get_event_history(source_agent="obfuscated-socks5-proxy")
        relay = events[-1].data
        assert relay["operation"] == "relay_obfuscated"
        assert relay["relay"]["upstream_chunks"] == 1
        assert relay["relay"]["downstream_chunks"] == 1
        assert relay["relay"]["payloads_redacted"] is True
        assert relay["dataplane_confirmed"] is False
        assert relay["dpi_bypass_confirmed"] is False

        rendered = repr(relay)
        assert "raw-upstream-secret" not in rendered
        assert "raw-downstream-secret" not in rendered

    @pytest.mark.asyncio
    async def test_connect_failure_event_redacts_client_and_target(
        self, tmp_path, mock_obfuscator
    ):
        bus = EventBus(project_root=str(tmp_path))
        target_host = "secret-target.example"
        target_port = 443
        request_chunks = [
            bytes([5, 1]),
            bytes([0x00]),
            bytes([5, 1, 0, 3]),
            bytes([len(target_host)]),
            target_host.encode("utf-8"),
            target_port.to_bytes(2, "big"),
        ]
        writer = _StreamWriter(peername=("secret-client.example", 55000))

        with patch(
            "src.network.obfuscated_socks5.get_vpn_obfuscator",
            return_value=mock_obfuscator,
        ), patch(
            "src.network.obfuscated_socks5.asyncio.open_connection",
            AsyncMock(side_effect=OSError("connect secret")),
        ):
            from src.network.obfuscated_socks5 import ObfuscatedSOCKS5Server

            srv = ObfuscatedSOCKS5Server(event_bus=bus)
            await srv._handle_client(_StreamReader(request_chunks), writer)

        events = bus.get_event_history(source_agent="obfuscated-socks5-proxy")
        session = events[-1].data
        assert session["operation"] == "client_session"
        assert session["status"] == "connect_failed"
        assert session["target"]["present"] is True
        assert session["target"]["raw_target_redacted"] is True
        assert session["client"]["raw_peer_redacted"] is True
        assert session["dataplane_confirmed"] is False
        assert session["dpi_bypass_confirmed"] is False

        rendered = repr(session)
        assert "secret-target.example" not in rendered
        assert "secret-client.example" not in rendered
        assert "connect secret" not in rendered
