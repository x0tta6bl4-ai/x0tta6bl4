import os
from decimal import Decimal
from types import SimpleNamespace

import pytest

import src.network.mesh_vpn_bridge as bridge_mod


class _FakeRewards:
    def __init__(self, contract_address=""):
        self.contract_address = contract_address
        self.balance = Decimal("1000.0")
        self.daily_earnings = Decimal("0.0")
        self.calls = []

    def reward_relay(self, node_id, packets):
        self.calls.append((node_id, packets))


class _FakeWriter:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True


class _FakeReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def _patch_init_deps(monkeypatch):
    monkeypatch.setattr(
        bridge_mod, "MeshNodeConfig", lambda **kw: SimpleNamespace(**kw)
    )
    monkeypatch.setattr(
        bridge_mod, "MeshNode", lambda config: SimpleNamespace(config=config)
    )
    monkeypatch.setattr(
        bridge_mod,
        "MeshRouter",
        lambda node_id, socks_port: SimpleNamespace(
            peers={},
            pqc=None,
            get_stats=lambda: {"ok": True},
            start=lambda: None,
        ),
    )
    monkeypatch.setattr(bridge_mod, "PQCCrypto", lambda: object())
    monkeypatch.setattr(bridge_mod, "TokenRewards", _FakeRewards)


def test_init_parses_exit_nodes_and_mode(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.setenv("NODE_ID", "node-vps-1")
    monkeypatch.setenv("EXIT_NODES", "1.1.1.1:443:5,2.2.2.2:80:10")
    b = bridge_mod.MeshVPNBridge(socks_port=1080)
    assert b.is_exit_node is True
    assert b.use_mesh_routing is False
    assert len(b.exit_nodes) == 2
    assert b.exit_nodes[0]["ip"] == "1.1.1.1"


def test_parse_socks_request_ipv4_domain_default(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.delenv("NODE_ID", raising=False)
    b = bridge_mod.MeshVPNBridge()

    ipv4 = b"\x05\x01\x00\x01" + bytes([1, 2, 3, 4]) + (8080).to_bytes(2, "big")
    host, port = b._parse_socks_request(ipv4)
    assert host == "1.2.3.4"
    assert port == 8080

    domain = b"\x05\x01\x00\x03\x0bexample.com" + (443).to_bytes(2, "big")
    host2, port2 = b._parse_socks_request(domain)
    assert host2 == "example.com"
    assert port2 == 443

    fallback = b"\x05\x01\x00\x09"
    host3, port3 = b._parse_socks_request(fallback)
    assert host3 == "google.com"
    assert port3 == 80


def test_select_exit_node(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.setenv("EXIT_NODES", "1.1.1.1:443:5")
    b = bridge_mod.MeshVPNBridge()
    monkeypatch.setattr(bridge_mod.random, "choices", lambda nodes, weights: [nodes[0]])
    chosen = b._select_exit_node()
    assert chosen["ip"] == "1.1.1.1"


@pytest.mark.asyncio
async def test_relay_stream_updates_metrics_and_rewards(monkeypatch):
    _patch_init_deps(monkeypatch)
    b = bridge_mod.MeshVPNBridge()
    b.mesh.config.node_id = "node-1"
    b.packets_relayed = 99
    reader = _FakeReader([b"abc", b""])
    writer = _FakeWriter()

    await b._relay_stream(reader, writer, direction="upstream", peer_id=None)
    assert b.bytes_relayed >= 3
    assert b.packets_relayed == 100
    assert writer.writes[0] == b"abc"
    assert b.rewards.calls == [("node-1", 100)]
