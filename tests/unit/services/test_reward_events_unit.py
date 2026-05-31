"""Unit tests for reward settlement EventBus publication."""

import hashlib
import json

from src.coordination.events import EventBus, EventType
from src.services.reward_events import (
    REWARD_CLAIM_GATE_BOUNDARY,
    publish_reward_settlement_event,
)


def _sha256_metadata(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def test_publish_reward_settlement_event_records_canonical_identity(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_reward_settlement_event(
        transition="recorded",
        source_agent="reward-test",
        node_address="0x" + "b" * 40,
        node_id="node-1",
        spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/relay",
        did="did:mesh:pqc:node-1",
        wallet_address="0x" + "a" * 40,
        packets=250,
        amount="0.0250",
        status="local_accounting_only",
        submitted_transaction=False,
        simulated=True,
        settlement_recorded=True,
        local_accounting_recorded=True,
        transaction_hash="",
        reason="unit-test",
        event_bus=bus,
    )

    events = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)
    assert len(events) == 1
    event = events[0]
    assert event.event_id == event_id
    assert event.data["identity"] == {
        "node_id": "node-1",
        "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/relay",
        "did": "did:mesh:pqc:node-1",
        "wallet_address": "0x" + "a" * 40,
        "reward_address": "0x" + "b" * 40,
    }
    identity_metadata = event.data["identity_metadata"]
    identity_metadata_text = str(identity_metadata)
    assert identity_metadata == {
        "values_redacted": True,
        "canonical_identity_payload_retained": True,
        "node_id_present": True,
        "node_id_hash": _sha256_metadata("node-1"),
        "spiffe_id_present": True,
        "spiffe_id_hash": _sha256_metadata(
            "spiffe://mesh.x0tta6bl4.mesh/workload/relay"
        ),
        "did_present": True,
        "did_hash": _sha256_metadata("did:mesh:pqc:node-1"),
        "wallet_address_present": True,
        "wallet_address_hash": _sha256_metadata("0x" + "a" * 40),
        "reward_address_present": True,
        "reward_address_hash": _sha256_metadata("0x" + "b" * 40),
    }
    assert "node-1" not in identity_metadata_text
    assert "spiffe://mesh.x0tta6bl4.mesh/workload/relay" not in identity_metadata_text
    assert "did:mesh:pqc:node-1" not in identity_metadata_text
    assert "0x" + "a" * 40 not in identity_metadata_text
    assert "0x" + "b" * 40 not in identity_metadata_text
    assert event.data["packets"] == 250
    assert event.data["amount"] == "0.0250"
    assert event.data["simulated"] is True
    assert event.data["submitted_transaction"] is False
    assert event.data["reward_claim_gate"] == {
        "decision": "local_reward_accounting_only",
        "local_reward_accounting_claim_allowed": True,
        "pending_token_submission_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "token_settlement_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "economy_finality_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "revenue_recognition_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_upstream_dataplane_evidence_for_traffic_claim": True,
        "requires_chain_finality_evidence_for_settlement_claim": True,
        "simulated": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": REWARD_CLAIM_GATE_BOUNDARY,
    }

    log_path = tmp_path / ".agent_coordination" / "events.log"
    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["event_id"] == event_id
    assert payload["event_type"] == EventType.REWARD_RELAY_RECORDED.value


def test_publish_reward_settlement_event_unknown_transition_falls_back_to_blocked(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_reward_settlement_event(
        transition="unexpected",
        source_agent="reward-test",
        node_address="0x" + "b" * 40,
        event_bus=bus,
    )

    events = bus.get_event_history(event_type=EventType.REWARD_RELAY_BLOCKED)
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].data["transition"] == "unexpected"


def test_publish_reward_settlement_event_links_upstream_ids_without_payload(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_reward_settlement_event(
        transition="recorded",
        source_agent="reward-test",
        node_address="node-1",
        upstream_event_ids=["evt-mesh-1"],
        upstream_source_agents=["mesh-network-manager"],
        reason="unit-test",
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)[0]
    upstream_text = str(event.data["upstream_evidence"])

    assert event.event_id == event_id
    assert event.data["upstream_evidence"] == {
        "source_agents": ["mesh-network-manager"],
        "event_ids": ["evt-mesh-1"],
        "events_total": 1,
        "event_ids_limit": 10,
        "event_ids_truncated": False,
        "claim_gate_summary": {"present": False, "payloads_redacted": True},
        "cross_plane_claim_gate_summary": {
            "present": False,
            "payloads_redacted": True,
        },
        "payloads_redacted": True,
    }
    assert "10.0.0.1" not in upstream_text


def test_publish_reward_settlement_event_summarizes_upstream_claim_gates(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    publish_reward_settlement_event(
        transition="recorded",
        source_agent="reward-test",
        node_address="node-1",
        upstream_event_ids=["evt-spine-1"],
        upstream_source_agents=["integration-spine"],
        upstream_claim_gate={
            "schema": "x0tta6bl4.integration_spine.claim_gate.v1",
            "surface": "integration_spine.reward_context",
            "status": "reward_context",
            "local_spine_lifecycle_claim_allowed": True,
            "policy_decision_claim_allowed": True,
            "local_actuator_execution_claim_allowed": True,
            "local_reward_adapter_record_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_dpi_bypass_claim_allowed": False,
            "external_settlement_finality_claim_allowed": False,
            "economy_finality_claim_allowed": False,
            "bank_settlement_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
            "blocked_claim_ids": ["settlement_finality", "dataplane_delivery"],
            "raw_payload": "must-not-copy",
        },
        upstream_cross_plane_claim_gate={
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": "integration_spine.reward_context",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": ["settlement_finality", "dataplane_delivery"],
            "blockers": ["integration_spine_local_contract_only"],
            "raw_payload": "must-not-copy",
        },
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)[0]
    upstream = event.data["upstream_evidence"]

    assert upstream["claim_gate_summary"]["present"] is True
    assert upstream["claim_gate_summary"]["surface"] == "integration_spine.reward_context"
    assert upstream["claim_gate_summary"]["local_actuator_execution_claim_allowed"] is True
    assert upstream["claim_gate_summary"]["external_settlement_finality_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["economy_finality_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["bank_settlement_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["revenue_recognition_claim_allowed"] is False
    assert upstream["claim_gate_summary"]["blocked_claim_ids"] == [
        "settlement_finality",
        "dataplane_delivery",
    ]
    assert upstream["cross_plane_claim_gate_summary"]["present"] is True
    assert upstream["cross_plane_claim_gate_summary"]["allowed"] is False
    assert upstream["cross_plane_claim_gate_summary"]["requested_claim_ids"] == [
        "settlement_finality",
        "dataplane_delivery",
    ]
    assert "must-not-copy" not in str(upstream)


def test_publish_reward_settlement_event_sanitizes_evidence_metadata(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    node_address = "0x" + "f" * 40
    contract_address = "0x" + "a" * 40
    db_path = "/tmp/private/access.db"

    publish_reward_settlement_event(
        transition="recorded",
        source_agent="reward-test",
        node_address=node_address,
        evidence_metadata={
            "node_address": node_address,
            "contract_address": contract_address,
            "reward_rate_xot_per_packet": "0.0001",
            "referral_count": 3,
            "nested": {
                "db_path": db_path,
                "mesh_available": True,
            },
        },
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)[0]
    metadata = event.data["evidence_metadata"]
    metadata_text = str(metadata)

    assert event.data["evidence_metadata_values_redacted"] is True
    assert metadata["node_address"].startswith("sha256:")
    assert metadata["contract_address"].startswith("sha256:")
    assert metadata["nested"]["db_path"].startswith("sha256:")
    assert metadata["reward_rate_xot_per_packet"] == "0.0001"
    assert metadata["referral_count"] == 3
    assert metadata["nested"]["mesh_available"] is True
    assert node_address not in metadata_text
    assert contract_address not in metadata_text
    assert db_path not in metadata_text


def test_publish_reward_settlement_event_returns_none_when_bus_unavailable():
    class BrokenBus:
        def publish(self, *args, **kwargs):
            raise RuntimeError("event store down")

    event_id = publish_reward_settlement_event(
        transition="recorded",
        source_agent="reward-test",
        node_address="0x" + "b" * 40,
        event_bus=BrokenBus(),
    )

    assert event_id is None
