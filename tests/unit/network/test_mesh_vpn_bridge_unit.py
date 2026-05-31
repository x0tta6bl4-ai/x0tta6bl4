from decimal import Decimal
from types import SimpleNamespace

import pytest

import src.network.mesh_vpn_bridge as bridge_mod
from src.coordination.events import EventBus, EventType


class _FakeRewards:
    instances = []

    def __init__(self, contract_address="", **kwargs):
        self.contract_address = contract_address
        self.kwargs = dict(kwargs)
        self.balance = Decimal("1000.0")
        self.daily_earnings = Decimal("0.0")
        self.calls = []
        self.evidence_calls = []
        self.instances.append(self)

    def reward_relay(self, node_id, packets, **kwargs):
        self.calls.append((node_id, packets))
        self.evidence_calls.append(dict(kwargs))


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
    _FakeRewards.instances = []
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
    monkeypatch.setattr(bridge_mod, "get_event_bus", lambda project_root=".": "event-bus")


def test_init_parses_exit_nodes_and_mode(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.setenv("NODE_ID", "node-vps-1")
    monkeypatch.setenv("EXIT_NODES", "1.1.1.1:443:5,2.2.2.2:80:10")
    b = bridge_mod.MeshVPNBridge(socks_port=1080)
    assert b.is_exit_node is True
    assert b.use_mesh_routing is False
    assert len(b.exit_nodes) == 2
    assert b.exit_nodes[0]["ip"] == "1.1.1.1"


def test_init_wires_reward_manager_to_event_bus_and_service_identity(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.setenv("MESH_VPN_BRIDGE_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/vpn")
    monkeypatch.setenv("MESH_VPN_BRIDGE_DID", "did:mesh:pqc:vpn")
    monkeypatch.setenv("MESH_VPN_BRIDGE_WALLET_ADDRESS", "0xffffffffffffffffffffffffffffffffffffffff")
    monkeypatch.setenv("X0TTA6BL4_EVENT_PROJECT_ROOT", "/tmp/x0t-events")

    b = bridge_mod.MeshVPNBridge(node_id="node-vpn-1")

    assert b.reward_identity == {
        "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/vpn",
        "did": "did:mesh:pqc:vpn",
        "wallet_address": "0xffffffffffffffffffffffffffffffffffffffff",
    }
    rewards = _FakeRewards.instances[-1]
    assert rewards.kwargs["event_bus"] == "event-bus"
    assert rewards.kwargs["event_project_root"] == "/tmp/x0t-events"
    assert rewards.kwargs["source_agent"] == "mesh-vpn-bridge"
    assert rewards.kwargs["node_id"] == "node-vpn-1"
    assert rewards.kwargs["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/vpn"
    assert rewards.kwargs["did"] == "did:mesh:pqc:vpn"
    assert rewards.kwargs["wallet_address"] == "0xffffffffffffffffffffffffffffffffffffffff"


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


@pytest.mark.asyncio
async def test_relay_stream_rewards_configured_wallet_address(monkeypatch):
    _patch_init_deps(monkeypatch)
    monkeypatch.setenv("MESH_VPN_BRIDGE_WALLET_ADDRESS", "0xffffffffffffffffffffffffffffffffffffffff")
    b = bridge_mod.MeshVPNBridge()
    b.mesh.config.node_id = "node-1"
    b.packets_relayed = 99
    reader = _FakeReader([b"abc", b""])
    writer = _FakeWriter()

    await b._relay_stream(reader, writer, direction="upstream", peer_id=None)

    assert b.rewards.calls == [("0xffffffffffffffffffffffffffffffffffffffff", 100)]


@pytest.mark.asyncio
async def test_relay_stream_links_reward_to_redacted_relay_evidence(monkeypatch, tmp_path):
    _patch_init_deps(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(bridge_mod, "get_event_bus", lambda project_root=".": bus)
    b = bridge_mod.MeshVPNBridge(node_id="node-vpn-1")
    b.packets_relayed = 99
    reader = _FakeReader([b"abc", b""])
    writer = _FakeWriter()

    await b._relay_stream(
        reader,
        writer,
        direction="upstream",
        peer_id="peer-secret-1",
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mesh-vpn-bridge",
    )
    observed = [
        event
        for event in events
        if event.data.get("stage") == "relay_reward_observed"
    ][-1]
    payload = observed.data
    payload_text = str(payload)

    assert b.rewards.calls == [("node-vpn-1", 100)]
    assert b.rewards.evidence_calls == [
        {
            "upstream_event_ids": [observed.event_id],
            "upstream_source_agents": ["mesh-vpn-bridge"],
        }
    ]
    assert payload["component"] == "network.mesh_vpn_bridge"
    assert payload["resource"] == "network:mesh_vpn_bridge:relay_packet_threshold"
    assert payload["identity_metadata"]["values_redacted"] is True
    assert payload["identity_metadata"]["raw_identity_values_retained"] is False
    assert payload["identity_metadata"]["node_id_present"] is True
    assert payload["identity_metadata"]["node_id_hash"].startswith("sha256:")
    assert payload["direction"] == "upstream"
    assert payload["reward_packets"] == 100
    assert payload["packet_threshold"] == 100
    assert payload["packets_relayed_total"] == 100
    assert payload["bytes_relayed_total"] >= 3
    assert payload["last_chunk_bytes"] == 3
    assert payload["routing_mode"] == "mesh_peer"
    assert payload["peer_id_redacted"] is True
    assert len(payload["peer_id_hash"]) == 64
    assert len(payload["reward_address_hash"]) == 64
    assert payload["payloads_redacted"] is True
    assert payload["safe_observation"] is True
    assert payload["local_relay_counter_observed"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["customer_traffic_confirmed"] is False
    assert payload["external_reachability_confirmed"] is False
    assert payload["token_settlement_finality_confirmed"] is False
    assert payload["production_readiness_claim_allowed"] is False
    gate = payload["relay_reward_claim_gate"]
    assert gate["decision"] == "local_relay_counter_only"
    assert gate["local_relay_counter_claim_allowed"] is True
    assert gate["reward_accounting_claim_allowed"] is False
    assert gate["traffic_delivery_claim_allowed"] is False
    assert gate["dataplane_delivery_claim_allowed"] is False
    assert gate["token_settlement_finality_claim_allowed"] is False
    assert gate["production_readiness_claim_allowed"] is False
    assert "peer-secret-1" not in payload_text
    assert "node-vpn-1" not in payload_text


@pytest.mark.asyncio
async def test_relay_stream_fail_closed_on_pqc_decrypt_error(monkeypatch):
    _patch_init_deps(monkeypatch)
    b = bridge_mod.MeshVPNBridge()
    b.fail_closed = True

    class _FailingPQC:
        def has_tunnel(self, _peer_id):
            return True

        def decrypt_from_peer(self, _data, _peer_id):
            raise ValueError("decrypt failed")

    b.router.pqc = _FailingPQC()
    reader = _FakeReader([b"ciphertext", b""])
    writer = _FakeWriter()

    await b._relay_stream(reader, writer, direction="downstream", peer_id="peer-1")
    assert writer.writes == []


@pytest.mark.asyncio
async def test_relay_stream_plaintext_fallback_when_fail_closed_disabled(monkeypatch):
    _patch_init_deps(monkeypatch)
    b = bridge_mod.MeshVPNBridge()
    b.fail_closed = False

    class _FailingPQC:
        def has_tunnel(self, _peer_id):
            return True

        def decrypt_from_peer(self, _data, _peer_id):
            raise ValueError("decrypt failed")

    b.router.pqc = _FailingPQC()
    reader = _FakeReader([b"ciphertext", b""])
    writer = _FakeWriter()

    await b._relay_stream(reader, writer, direction="downstream", peer_id="peer-1")
    assert writer.writes == [b"ciphertext"]
