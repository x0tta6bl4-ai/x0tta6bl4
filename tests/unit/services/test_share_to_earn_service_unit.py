"""Unit tests for share-to-earn reward event publication."""

import sqlite3
from decimal import Decimal

import pytest

from src.coordination.events import EventBus, EventType
from src.services import share_to_earn_service as service


def test_publish_share_to_earn_reward_event_attaches_identity(monkeypatch):
    calls = []

    def _publish(**kwargs):
        calls.append(kwargs)
        return "evt-share-to-earn"

    monkeypatch.setenv("SHARE_TO_EARN_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn")
    monkeypatch.setenv("SHARE_TO_EARN_DID", "did:mesh:pqc:share-to-earn")
    monkeypatch.setenv("SHARE_TO_EARN_WALLET_ADDRESS", "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
    monkeypatch.setattr(service, "publish_reward_settlement_event", _publish)

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.05"),
        packets=500,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
    )

    assert event_id == "evt-share-to-earn"
    assert len(calls) == 1
    payload = calls[0]
    assert payload["transition"] == "recorded"
    assert payload["source_agent"] == "share-to-earn"
    assert payload["node_id"] == "node-earn-1"
    assert payload["node_address"] == "0xffffffffffffffffffffffffffffffffffffffff"
    assert payload["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn"
    assert payload["did"] == "did:mesh:pqc:share-to-earn"
    assert payload["wallet_address"] == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    assert payload["packets"] == 500
    assert payload["amount"] == "0.05"
    assert payload["submitted_transaction"] is False
    assert payload["simulated"] is True
    assert payload["settlement_recorded"] is False
    assert payload["local_accounting_recorded"] is True


def test_publish_share_to_earn_reward_event_falls_back_to_reward_address(monkeypatch):
    calls = []

    monkeypatch.delenv("SHARE_TO_EARN_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("X0TTA6BL4_SERVICE_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("SERVICE_WALLET_ADDRESS", raising=False)
    monkeypatch.delenv("GHOST_WALLET_ADDRESS", raising=False)
    monkeypatch.setattr(service, "publish_reward_settlement_event", lambda **kwargs: calls.append(kwargs) or "evt")

    service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.01"),
        packets=100,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
    )

    assert calls[0]["wallet_address"] == "0xffffffffffffffffffffffffffffffffffffffff"


def test_publish_share_to_earn_reward_event_skips_zero_amount(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "publish_reward_settlement_event", lambda **kwargs: calls.append(kwargs))

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0"),
        packets=0,
        simulation_enabled=False,
        status="OBSERVE_ONLY",
    )

    assert event_id is None
    assert calls == []


def test_publish_share_to_earn_reward_event_uses_injected_event_bus(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setenv(
        "SHARE_TO_EARN_SPIFFE_ID",
        "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn",
    )
    monkeypatch.setenv("SHARE_TO_EARN_DID", "did:mesh:pqc:share-to-earn")
    monkeypatch.setenv(
        "SHARE_TO_EARN_WALLET_ADDRESS",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    )

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.05"),
        packets=500,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
        evidence_metadata={
            "referral_count": 2,
            "referral_db_path": "/tmp/private/access.db",
            "mesh_stats": {
                "source_path": ".tmp/mesh_stats.json",
                "pulse_coherence": 0.99,
            },
        },
        event_bus=bus,
    )

    events = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)
    assert event_id == events[-1].event_id
    payload = events[-1].data
    assert events[-1].source_agent == "share-to-earn"
    assert payload["node_id"] == "node-earn-1"
    assert payload["spiffe_id"] == (
        "spiffe://mesh.x0tta6bl4.mesh/workload/share-to-earn"
    )
    assert payload["did"] == "did:mesh:pqc:share-to-earn"
    assert payload["wallet_address"] == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    assert payload["packets"] == 500
    assert payload["amount"] == "0.05"
    assert payload["local_accounting_recorded"] is True
    assert payload["claim_boundary"]
    metadata = payload["evidence_metadata"]
    metadata_text = str(metadata)
    assert metadata["component"] == "services.share_to_earn_service"
    assert metadata["calculator"] == "share_to_earn.local_accounting"
    assert metadata["referral_count"] == 2
    assert metadata["referral_db_path"].startswith("sha256:")
    assert metadata["mesh_stats"]["source_path"].startswith("sha256:")
    assert metadata["mesh_stats"]["pulse_coherence"] == 0.99
    assert metadata["node_address_hash"] == service._hash_value(
        "0xffffffffffffffffffffffffffffffffffffffff"
    )
    assert metadata["mesh_upstream_evidence"]["status"] == "missing"
    assert metadata["mesh_upstream_evidence"]["events_total"] == 0
    assert metadata["mesh_upstream_evidence"]["event_ids_redacted"] is True
    assert payload["upstream_evidence"]["events_total"] == 0
    assert payload["evidence_metadata_values_redacted"] is True
    assert "/tmp/private/access.db" not in metadata_text
    assert ".tmp/mesh_stats.json" not in metadata_text


def test_publish_share_to_earn_reward_event_links_latest_mesh_upstream_evidence(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    mesh_event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-telemetry-collector",
        {
            "operation": "collect_once",
            "observed_state": True,
            "peer_uri": "tls://10.0.0.1:9000",
        },
    )
    monkeypatch.setenv(
        "SHARE_TO_EARN_WALLET_ADDRESS",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    )

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.05"),
        packets=500,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
        upstream_event_ids=["evt-explicit"],
        upstream_source_agents=["explicit-source"],
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)[0]
    payload = event.data
    metadata = payload["evidence_metadata"]
    payload_text = str(payload)

    assert event.event_id == event_id
    assert payload["upstream_evidence"]["event_ids"] == [
        "evt-explicit",
        mesh_event.event_id,
    ]
    assert payload["upstream_evidence"]["source_agents"] == [
        "explicit-source",
        "mesh-telemetry-collector",
    ]
    assert payload["upstream_evidence"]["events_total"] == 2
    assert metadata["mesh_upstream_evidence"]["status"] == "linked"
    assert metadata["mesh_upstream_evidence"]["source_agents"] == [
        "mesh-telemetry-collector"
    ]
    assert metadata["mesh_upstream_evidence"]["events_total"] == 1
    assert metadata["mesh_upstream_evidence"]["event_ids_redacted"] is True
    assert "tls://10.0.0.1:9000" not in payload_text


def test_publish_share_to_earn_reward_event_preserves_upstream_claim_gates(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-network-manager",
        {
            "operation": "heal_mesh",
            "claim_gate": {
                "schema": "x0tta6bl4.mesh.heal.claim_gate.v1",
                "surface": "mesh_network_manager.aggressive_heal",
                "decision": "local_healing_only",
                "dataplane_delivery_claim_allowed": False,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "blocked_claim_ids": [
                    "dataplane_delivery",
                    "traffic_delivery",
                    "production_readiness",
                ],
            },
            "cross_plane_claim_gate": {
                "schema": "x0tta6bl4.cross_plane_claim_gate.v1",
                "surface": "mesh_network_manager.aggressive_heal",
                "decision": "blocked",
                "allowed": False,
                "requested_claim_ids": [
                    "dataplane_delivery",
                    "traffic_delivery",
                ],
                "blockers": ["post_action_dataplane_claim_gate_not_allowed"],
            },
        },
    )
    monkeypatch.setenv(
        "SHARE_TO_EARN_WALLET_ADDRESS",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    )

    event_id = service.publish_share_to_earn_reward_event(
        node_id="node-earn-1",
        node_address="0xffffffffffffffffffffffffffffffffffffffff",
        amount=Decimal("0.05"),
        packets=500,
        simulation_enabled=True,
        status="SIMULATED_EARNING",
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)[0]
    payload = event.data
    upstream = payload["upstream_evidence"]
    metadata = payload["evidence_metadata"]["mesh_upstream_evidence"]

    assert event.event_id == event_id
    assert metadata["claim_gate_present"] is True
    assert metadata["cross_plane_claim_gate_present"] is True
    assert upstream["claim_gate_summary"]["present"] is True
    assert upstream["claim_gate_summary"]["surface"] == (
        "mesh_network_manager.aggressive_heal"
    )
    assert upstream["claim_gate_summary"]["dataplane_delivery_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["traffic_delivery_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["production_readiness_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["blocked_claim_ids"] == [
        "dataplane_delivery",
        "traffic_delivery",
        "production_readiness",
    ]
    assert upstream["cross_plane_claim_gate_summary"]["present"] is True
    assert upstream["cross_plane_claim_gate_summary"]["allowed"] is False
    assert upstream["cross_plane_claim_gate_summary"]["blockers"] == [
        "post_action_dataplane_claim_gate_not_allowed"
    ]
    assert payload["reward_claim_gate"]["local_reward_accounting_claim_allowed"] is True
    assert payload["reward_claim_gate"]["token_settlement_finality_claim_allowed"] is False


def test_configured_user_id_requires_explicit_positive_integer(monkeypatch):
    monkeypatch.delenv("GHOST_USER_ID", raising=False)
    with pytest.raises(RuntimeError, match="GHOST_USER_ID is required"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "not-an-int")
    with pytest.raises(RuntimeError, match="must be an integer"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "0")
    with pytest.raises(RuntimeError, match="positive integer"):
        service._configured_user_id()

    monkeypatch.setenv("GHOST_USER_ID", "42")
    assert service._configured_user_id() == 42


def test_configured_node_address_requires_env_or_identity(monkeypatch):
    monkeypatch.delenv("GHOST_WALLET_ADDRESS", raising=False)
    with pytest.raises(RuntimeError, match="wallet address is required"):
        service._configured_node_address({"wallet_address": None})

    assert service._configured_node_address(
        {"wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    ) == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    monkeypatch.setenv(
        "GHOST_WALLET_ADDRESS",
        "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    assert service._configured_node_address(
        {"wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    ) == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_referral_count_for_user_reads_database(tmp_path):
    db_path = tmp_path / "access.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE referrals (referrer_user_id INTEGER NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO referrals (referrer_user_id) VALUES (?)",
            [(7,), (7,), (8,)],
        )

    assert service.referral_count_for_user(7, str(db_path)) == 2
    assert service.referral_count_for_user(9, str(db_path)) == 0
