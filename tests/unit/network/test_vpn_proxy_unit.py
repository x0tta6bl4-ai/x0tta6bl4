import os
import struct
from types import SimpleNamespace

import pytest

import src.network.vpn_proxy as mod
from src.network.vpn_proxy import MeshVPNProxy, SOCKS5Server

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _Reader:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    async def read(self, _n):
        if self.chunks:
            return self.chunks.pop(0)
        return b""


class _Writer:
    def __init__(self):
        self.data = b""

    def write(self, d):
        self.data += d

    async def drain(self):
        return None


class _ClientWriter(_Writer):
    def __init__(self, fail_wait=False):
        super().__init__()
        self.fail_wait = fail_wait
        self.closed = False

    def get_extra_info(self, name):
        if name == "peername":
            return ("127.0.0.1", 54321)
        return None

    def close(self):
        self.closed = True

    async def wait_closed(self):
        if self.fail_wait:
            raise RuntimeError("wait closed failed")
        return None


class _TargetWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def drain(self):
        return None


class _FakeServer:
    def __init__(self):
        self.closed = False
        self.wait_closed_called = False
        self.serve_forever_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def serve_forever(self):
        self.serve_forever_called = True

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.wait_closed_called = True


@pytest.mark.asyncio
async def test_socks5_handshake_no_auth_success():
    s = SOCKS5Server()
    reader = _Reader([bytes([5, 1]), bytes([0])])
    writer = _Writer()
    ok = await s._socks5_handshake(reader, writer)
    assert ok is True
    assert writer.data == bytes([5, 0])


@pytest.mark.asyncio
async def test_get_target_address_domain_and_ipv4():
    s = SOCKS5Server()
    writer = _Writer()

    # CONNECT + domain
    reader_domain = _Reader(
        [bytes([5, 1, 0, 3]), bytes([11]), b"example.com", struct.pack("!H", 443)]
    )
    host, port = await s._get_target_address(reader_domain, writer)
    assert host == "example.com"
    assert port == 443

    # CONNECT + ipv4
    reader_v4 = _Reader(
        [bytes([5, 1, 0, 1]), bytes([1, 2, 3, 4]), struct.pack("!H", 1080)]
    )
    host2, port2 = await s._get_target_address(reader_v4, writer)
    assert host2 == "1.2.3.4"
    assert port2 == 1080


def test_stats_and_mesh_proxy_init():
    s = SOCKS5Server()
    s.stats.connections = 2
    s.stats.active_connections = 1
    s.stats.bytes_sent = 10
    s.stats.bytes_received = 20
    stats = s.get_stats()
    assert stats["connections_total"] == 2
    assert stats["bytes_total"] == 30

    p = MeshVPNProxy(use_exit=True, exit_node="10.0.0.1:1234")
    assert p._mesh_enabled is True
    assert p.exit_host == "10.0.0.1"
    assert p.exit_port == 1234


@pytest.mark.asyncio
async def test_socks5_handshake_failure_paths():
    s = SOCKS5Server()

    short_header = await s._socks5_handshake(_Reader([b"\x05"]), _Writer())
    assert short_header is False

    bad_version = await s._socks5_handshake(_Reader([bytes([4, 1]), bytes([0])]), _Writer())
    assert bad_version is False

    no_auth_writer = _Writer()
    no_auth = await s._socks5_handshake(
        _Reader([bytes([5, 1]), bytes([2])]),
        no_auth_writer,
    )
    assert no_auth is False
    assert no_auth_writer.data == bytes([5, 0xFF])


@pytest.mark.asyncio
async def test_socks5_handshake_rejects_no_auth_in_production(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")
    monkeypatch.delenv("X0TTA6BL4_ALLOW_NOAUTH_SOCKS5", raising=False)
    monkeypatch.delenv("VPN_SOCKS5_USERNAME", raising=False)
    monkeypatch.delenv("VPN_SOCKS5_PASSWORD", raising=False)

    s = SOCKS5Server()
    writer = _Writer()
    ok = await s._socks5_handshake(_Reader([bytes([5, 1]), bytes([0])]), writer)
    assert ok is False
    assert writer.data == bytes([5, 0xFF])


@pytest.mark.asyncio
async def test_socks5_handshake_username_password_auth(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")
    monkeypatch.setenv("VPN_SOCKS5_USERNAME", "demo-user")
    monkeypatch.setenv("VPN_SOCKS5_PASSWORD", "demo-pass")

    s = SOCKS5Server()
    writer = _Writer()
    reader = _Reader(
        [
            bytes([5, 1]),  # SOCKS5, 1 auth method
            bytes([2]),  # username/password method available
            bytes([1, 9]),  # auth version=1, username len=9
            b"demo-user",
            bytes([9]),  # password len=9
            b"demo-pass",
        ]
    )
    ok = await s._socks5_handshake(reader, writer)
    assert ok is True
    assert writer.data == bytes([5, 2, 1, 0])


@pytest.mark.asyncio
async def test_get_target_address_edge_paths(monkeypatch):
    s = SOCKS5Server()
    writer = _Writer()
    sent_status = []

    async def _fake_send_reply(_w, status):
        sent_status.append(status)

    monkeypatch.setattr(s, "_send_reply", _fake_send_reply)

    assert await s._get_target_address(_Reader([b"\x05\x01\x00"]), writer) is None
    assert await s._get_target_address(_Reader([bytes([4, 1, 0, 1])]), writer) is None
    assert (
        await s._get_target_address(_Reader([bytes([5, 2, 0, 1]), b"\x01\x02\x03\x04", b"\x00\x50"]), writer)
        is None
    )
    assert sent_status[-1] == 0x07

    reader_v6 = _Reader(
        [
            bytes([5, 1, 0, 4]),
            bytes.fromhex("20010db8000000000000000000000001"),
            struct.pack("!H", 8080),
        ]
    )
    host_v6, port_v6 = await s._get_target_address(reader_v6, writer)
    assert host_v6.startswith("2001:db8:")
    assert port_v6 == 8080

    assert (
        await s._get_target_address(_Reader([bytes([5, 1, 0, 9]), b"\x00\x00"]), writer)
        is None
    )
    assert sent_status[-1] == 0x08


@pytest.mark.asyncio
async def test_send_reply_and_relay_data_paths():
    s = SOCKS5Server()
    writer = _Writer()
    await s._send_reply(writer, 0x05)
    assert len(writer.data) == 10
    assert writer.data[:2] == bytes([5, 0x05])

    client_reader = _Reader([b"abc", b""])
    target_reader = _Reader([b"xy", b""])
    client_writer = _Writer()
    target_writer = _Writer()

    await s._relay_data(client_reader, client_writer, target_reader, target_writer)
    assert s.stats.bytes_sent == 3
    assert s.stats.bytes_received == 2
    assert target_writer.data == b"abc"
    assert client_writer.data == b"xy"


@pytest.mark.asyncio
async def test_relay_data_handles_connection_errors():
    s = SOCKS5Server()

    class _BrokenReader:
        async def read(self, _n):
            raise ConnectionResetError("boom")

    class _RuntimeErrorReader:
        async def read(self, _n):
            raise RuntimeError("relay failed")

    await s._relay_data(_BrokenReader(), _Writer(), _Reader([b""]), _Writer())
    await s._relay_data(_RuntimeErrorReader(), _Writer(), _Reader([b""]), _Writer())


@pytest.mark.asyncio
async def test_handle_client_paths(monkeypatch):
    s = SOCKS5Server()

    async def _false_handshake(_reader, _writer):
        return False

    monkeypatch.setattr(s, "_socks5_handshake", _false_handshake)
    writer1 = _ClientWriter()
    await s._handle_client(_Reader([]), writer1)
    assert s.stats.active_connections == 0
    assert writer1.closed is True

    async def _true_handshake(_reader, _writer):
        return True

    async def _no_target(_reader, _writer):
        return None

    monkeypatch.setattr(s, "_socks5_handshake", _true_handshake)
    monkeypatch.setattr(s, "_get_target_address", _no_target)
    writer2 = _ClientWriter(fail_wait=True)
    await s._handle_client(_Reader([]), writer2)
    assert writer2.closed is True

    async def _target(_reader, _writer):
        return ("example.com", 443)

    sent_status = []

    async def _record_reply(_writer, status):
        sent_status.append(status)

    async def _fail_open_connection(*_args, **_kwargs):
        raise OSError("connect failed")

    monkeypatch.setattr(s, "_get_target_address", _target)
    monkeypatch.setattr(s, "_send_reply", _record_reply)
    monkeypatch.setattr(mod.asyncio, "open_connection", _fail_open_connection)
    await s._handle_client(_Reader([]), _ClientWriter())
    assert sent_status[-1] == 0x05

    target_writer = _TargetWriter()

    async def _ok_open_connection(*_args, **_kwargs):
        return _Reader([b""]), target_writer

    relay_called = {"value": False}

    async def _relay(*_args, **_kwargs):
        relay_called["value"] = True

    monkeypatch.setattr(mod.asyncio, "open_connection", _ok_open_connection)
    monkeypatch.setattr(s, "_relay_data", _relay)
    await s._handle_client(_Reader([]), _ClientWriter())
    assert sent_status[-1] == 0x00
    assert relay_called["value"] is True
    assert target_writer.closed is True

    async def _raise_handshake(_reader, _writer):
        raise RuntimeError("handshake failed")

    monkeypatch.setattr(s, "_socks5_handshake", _raise_handshake)
    await s._handle_client(_Reader([]), _ClientWriter())
    assert s.stats.active_connections == 0


@pytest.mark.asyncio
async def test_server_start_stop_and_mesh_start(monkeypatch):
    fake_server = _FakeServer()

    async def _fake_start_server(*_args, **_kwargs):
        return fake_server

    monkeypatch.setattr(mod.asyncio, "start_server", _fake_start_server)
    s = SOCKS5Server()
    await s.start()
    assert s._running is True
    assert fake_server.serve_forever_called is True
    await s.stop()
    assert s._running is False
    assert fake_server.closed is True
    assert fake_server.wait_closed_called is True

    direct_proxy = MeshVPNProxy(use_exit=False)
    exit_proxy = MeshVPNProxy(use_exit=True, exit_node="10.1.2.3:5678")
    called = {"count": 0}

    async def _fake_super_start(self):
        called["count"] += 1

    monkeypatch.setattr(mod.SOCKS5Server, "start", _fake_super_start)
    await direct_proxy.start()
    await exit_proxy.start()
    assert called["count"] == 2


@pytest.mark.asyncio
async def test_main_success_and_keyboard_interrupt(monkeypatch):
    parsed = SimpleNamespace(host="127.0.0.2", port=2080, exit_node="1.1.1.1:1080", use_exit=True)
    monkeypatch.setattr(mod.argparse.ArgumentParser, "parse_args", lambda _self: parsed)

    state = {"start": 0, "stop": 0}

    class _Proxy:
        def __init__(self, host, port, exit_node, use_exit):
            assert host == parsed.host
            assert port == parsed.port
            assert exit_node == parsed.exit_node
            assert use_exit == parsed.use_exit

        async def start(self):
            state["start"] += 1

        async def stop(self):
            state["stop"] += 1

    monkeypatch.setattr(mod, "MeshVPNProxy", _Proxy)
    await mod.main()
    assert state["start"] == 1
    assert state["stop"] == 0

    class _InterruptProxy(_Proxy):
        async def start(self):
            raise KeyboardInterrupt()

        async def stop(self):
            state["stop"] += 1

    monkeypatch.setattr(mod, "MeshVPNProxy", _InterruptProxy)
    await mod.main()
    assert state["stop"] == 1
