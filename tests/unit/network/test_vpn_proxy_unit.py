import os
import struct

import pytest

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
