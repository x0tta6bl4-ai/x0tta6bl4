"""Unit tests for marketplace escrow EventBus publication."""

import hashlib
import json

from src.coordination.events import EventBus, EventType
from src.services.marketplace_events import (
    bridge_upstream_evidence,
    publish_marketplace_escrow_event,
)


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()[:16]


def test_publish_marketplace_escrow_event_records_redacted_canonical_identity(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    spiffe_id = "spiffe://mesh.x0tta6bl4.mesh/workload/marketplace"
    did = "did:mesh:pqc:renter-42"
    wallet_address = "0x" + "a" * 40
    event_id = publish_marketplace_escrow_event(
        transition="released",
        source_agent="maas-test",
        escrow_id="esc-1",
        listing_id="lst-1",
        renter_id="renter-42",
        actor_id="operator-1",
        currency="X0T",
        status="released",
        node_id="node-1",
        mesh_id="mesh-1",
        spiffe_id=spiffe_id,
        did=did,
        wallet_address=wallet_address,
        amount_token=12.5,
        reason="unit-test",
        event_bus=bus,
    )

    events = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_RELEASED)
    assert len(events) == 1
    event = events[0]
    assert event.event_id == event_id
    assert event.source_agent == "maas-test"
    assert event.data["identity"] == {
        "escrow_id_hash": _hash("esc-1"),
        "listing_id_hash": _hash("lst-1"),
        "renter_id_hash": _hash("renter-42"),
        "actor_id_hash": _hash("operator-1"),
        "node_id_hash": _hash("node-1"),
        "mesh_id_hash": _hash("mesh-1"),
        "spiffe_id_hash": _hash(spiffe_id),
        "did_hash": _hash(did),
        "wallet_address_hash": _hash(wallet_address),
    }
    assert event.data["component"] == "services.marketplace_events"
    assert event.data["operation"] == "marketplace_escrow_lifecycle"
    assert event.data["service_name"] == "maas-test"
    assert event.data["source_alias"] == "maas-test"
    assert event.data["layer"] == "commerce_escrow_lifecycle"
    assert event.data["escrow_id_hash"] == _hash("esc-1")
    assert event.data["spiffe_id_hash"] == _hash(spiffe_id)
    assert event.data["did_hash"] == _hash(did)
    assert event.data["wallet_address_hash"] == _hash(wallet_address)
    assert event.data["identity_fields_present"]["wallet_address"] is True
    assert event.data["raw_identifiers_redacted"] is True
    assert event.data["payloads_redacted"] is True
    assert event.data["currency"] == "X0T"
    assert event.data["amount_token"] == 12.5
    assert event.data["reason"] == "unit-test"
    assert event.data["reason_hash"] == _hash("unit-test")
    assert event.data["reason_redacted"] is False

    serialized = json.dumps(event.data, sort_keys=True)
    for raw_value in (
        "esc-1",
        "lst-1",
        "renter-42",
        "operator-1",
        "node-1",
        "mesh-1",
        spiffe_id,
        did,
        wallet_address,
    ):
        assert raw_value not in serialized

    log_path = tmp_path / ".agent_coordination" / "events.log"
    raw_log = log_path.read_text(encoding="utf-8").strip()
    payload = json.loads(raw_log)
    assert payload["event_id"] == event_id
    assert payload["event_type"] == EventType.MARKETPLACE_ESCROW_RELEASED.value
    assert spiffe_id not in raw_log
    assert wallet_address not in raw_log


def test_publish_marketplace_escrow_event_redacts_freeform_reason(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    private_reason = "manual release for escrow esc-secret-1 and node node-secret-1"

    publish_marketplace_escrow_event(
        transition="blocked",
        source_agent="maas-test",
        escrow_id="esc-secret-1",
        listing_id="lst-secret-1",
        node_id="node-secret-1",
        reason=private_reason,
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_BLOCKED)[0]
    serialized = json.dumps(event.data, sort_keys=True)
    raw_log = (
        tmp_path / ".agent_coordination" / "events.log"
    ).read_text(encoding="utf-8")

    assert event.data["reason"] == f"sha256:{_hash(private_reason)}"
    assert event.data["reason_hash"] == _hash(private_reason)
    assert event.data["reason_redacted"] is True
    assert private_reason not in serialized
    assert "esc-secret-1" not in serialized
    assert "node-secret-1" not in serialized
    assert private_reason not in raw_log
    assert "esc-secret-1" not in raw_log
    assert "node-secret-1" not in raw_log


def test_publish_marketplace_escrow_event_unknown_transition_falls_back_to_blocked(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_marketplace_escrow_event(
        transition="unexpected",
        source_agent="maas-test",
        escrow_id="esc-2",
        listing_id="lst-2",
        event_bus=bus,
    )

    events = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_BLOCKED)
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].data["transition"] == "unexpected"


def test_publish_marketplace_escrow_event_links_upstream_ids_without_payload(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_marketplace_escrow_event(
        transition="released",
        source_agent="maas-test",
        escrow_id="esc-4",
        listing_id="lst-4",
        upstream_event_ids=["evt-bridge-1"],
        upstream_source_agents=["token-bridge"],
        reason="unit-test",
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_RELEASED)[0]
    upstream_text = str(event.data["upstream_evidence"])

    assert event.event_id == event_id
    assert event.data["upstream_evidence"] == {
        "source_agents": ["token-bridge"],
        "event_ids": ["evt-bridge-1"],
        "events_total": 1,
        "event_ids_limit": 10,
        "event_ids_truncated": False,
        "payloads_redacted": True,
    }
    assert "10.0.0.1" not in upstream_text


def test_publish_marketplace_escrow_event_sanitizes_request_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    idempotency_key = "idem-secret-1"
    listing_id = "listing-secret-1"
    request_scope = f"{listing_id}:mesh-secret-1:2"

    publish_marketplace_escrow_event(
        transition="held",
        source_agent="maas-marketplace",
        escrow_id="esc-secret-1",
        listing_id=listing_id,
        renter_id="renter-secret-1",
        request_evidence={
            "action": "rent_node",
            "route": "POST /rent/{listing_id}",
            "actor_role": "user",
            "db_write_ready": True,
            "idempotency_key_present": True,
            "idempotency_key_hash": _hash(idempotency_key),
            "request_scope_hash": _hash(request_scope),
            "service_identity_present": {
                "spiffe_id": True,
                "did": False,
                "wallet_address": True,
            },
            "listing_id": listing_id,
            "idempotency_key": idempotency_key,
        },
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_HELD)[0]
    evidence = event.data["request_evidence"]
    evidence_text = json.dumps(evidence, sort_keys=True)

    assert evidence["action"] == "rent_node"
    assert evidence["route"] == "POST /rent/{listing_id}"
    assert evidence["actor_role"] == "user"
    assert evidence["db_write_ready"] is True
    assert evidence["idempotency_key_present"] is True
    assert evidence["idempotency_key_hash"] == _hash(idempotency_key)
    assert evidence["request_scope_hash"] == _hash(request_scope)
    assert evidence["service_identity_present"]["spiffe_id"] is True
    assert evidence["service_identity_present"]["did"] is False
    assert evidence["service_identity_present"]["wallet_address"] is True
    assert evidence["listing_id"] == f"sha256:{_hash(listing_id)}"
    assert evidence["idempotency_key"] == f"sha256:{_hash(idempotency_key)}"
    assert evidence["raw_identifiers_redacted"] is True
    assert evidence["payloads_redacted"] is True
    assert listing_id not in evidence_text
    assert "mesh-secret-1" not in evidence_text
    assert idempotency_key not in evidence_text


def test_publish_marketplace_escrow_event_sanitizes_settlement_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_marketplace_escrow_event(
        transition="released",
        source_agent="maas-settlement",
        escrow_id="esc-settle-1",
        listing_id="lst-settle-1",
        node_id="node-secret-1",
        mesh_id="mesh-secret-1",
        settlement_evidence={
            "decision_basis": "uptime_tracker_cached_window",
            "source_quality": "telemetry_eventbus_linked_uptime_tracker",
            "settlement_action": "release",
            "duration_ms": 12.345,
            "dataplane_confirmed": "false",
            "threshold_met": True,
            "uptime_percent": 1.0,
            "uptime_threshold": 0.999,
            "measurement_window_hours": 24,
            "bridge_evidence": {
                "attempted": True,
                "status": "released",
                "source_agent": "token-bridge",
                "wallet_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "payloads_redacted": True,
            },
            "db_write_evidence": {
                "storage_backend": "sqlalchemy",
                "attempted": True,
                "committed": True,
                "escrow_id": "esc-settle-1",
                "payloads_redacted": True,
            },
            "output_summary": {
                "escrow_status_after": "released",
                "listing_status_after": "rented",
                "node_id": "node-secret-1",
            },
            "claim_gate": {
                "decision": "local_escrow_lifecycle_only",
                "local_escrow_lifecycle_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "economy_finality_claim_allowed": False,
                "bank_settlement_claim_allowed": False,
                "revenue_recognition_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_dataplane_evidence_for_delivery_claim": True,
                "requires_external_finality_evidence_for_settlement_claim": True,
                "bridge_status": "released",
                "node_id": "node-secret-1",
                "claim_boundary": "local escrow lifecycle only; not traffic delivery",
            },
            "telemetry_evidence": {
                "source_agents": ["maas-telemetry"],
                "event_ids": ["evt-telemetry-1"],
            },
            "node_id": "node-secret-1",
            "mesh_id": "mesh-secret-1",
        },
        event_bus=bus,
    )

    event = bus.get_event_history(event_type=EventType.MARKETPLACE_ESCROW_RELEASED)[0]
    evidence = event.data["settlement_evidence"]
    evidence_text = json.dumps(evidence, sort_keys=True)

    assert event.event_id == event_id
    assert evidence["decision_basis"] == "uptime_tracker_cached_window"
    assert evidence["source_quality"] == "telemetry_eventbus_linked_uptime_tracker"
    assert evidence["settlement_action"] == "release"
    assert evidence["duration_ms"] == 12.345
    assert evidence["dataplane_confirmed"] is False
    assert evidence["threshold_met"] is True
    assert evidence["uptime_percent"] == 1.0
    assert evidence["uptime_threshold"] == 0.999
    assert evidence["bridge_evidence"]["attempted"] is True
    assert evidence["bridge_evidence"]["status"] == "released"
    assert evidence["bridge_evidence"]["source_agent"] == "token-bridge"
    assert evidence["bridge_evidence"]["wallet_address"].startswith("sha256:")
    assert evidence["bridge_evidence"]["payloads_redacted"] is True
    assert evidence["db_write_evidence"]["storage_backend"] == "sqlalchemy"
    assert evidence["db_write_evidence"]["attempted"] is True
    assert evidence["db_write_evidence"]["committed"] is True
    assert evidence["db_write_evidence"]["escrow_id"].startswith("sha256:")
    assert evidence["db_write_evidence"]["payloads_redacted"] is True
    assert evidence["output_summary"]["escrow_status_after"] == "released"
    assert evidence["output_summary"]["listing_status_after"] == "rented"
    assert evidence["output_summary"]["node_id"].startswith("sha256:")
    assert evidence["claim_gate"]["decision"] == "local_escrow_lifecycle_only"
    assert evidence["claim_gate"]["local_escrow_lifecycle_claim_allowed"] is True
    assert evidence["claim_gate"]["traffic_delivery_claim_allowed"] is False
    assert evidence["claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert (
        evidence["claim_gate"]["external_settlement_finality_claim_allowed"] is False
    )
    assert evidence["claim_gate"]["economy_finality_claim_allowed"] is False
    assert evidence["claim_gate"]["bank_settlement_claim_allowed"] is False
    assert evidence["claim_gate"]["revenue_recognition_claim_allowed"] is False
    assert evidence["claim_gate"]["production_readiness_claim_allowed"] is False
    assert (
        evidence["claim_gate"]["requires_dataplane_evidence_for_delivery_claim"]
        is True
    )
    assert (
        evidence["claim_gate"][
            "requires_external_finality_evidence_for_settlement_claim"
        ]
        is True
    )
    assert evidence["claim_gate"]["bridge_status"] == "released"
    assert evidence["claim_gate"]["raw_identifiers_redacted"] is True
    assert evidence["claim_gate"]["payloads_redacted"] is True
    assert "node_id" not in evidence["claim_gate"]
    assert evidence["telemetry_evidence"]["source_agents"] == ["maas-telemetry"]
    assert evidence["telemetry_evidence"]["event_ids"] == ["evt-telemetry-1"]
    assert evidence["telemetry_evidence"]["payloads_redacted"] is True
    assert evidence["raw_identifiers_redacted"] is True
    assert "node-secret-1" not in evidence_text
    assert "mesh-secret-1" not in evidence_text
    assert "esc-settle-1" not in evidence_text
    assert "0xbbbbbb" not in evidence_text


def test_bridge_upstream_evidence_uses_last_event_ids_without_payload():
    class Bridge:
        source_agent = "token-bridge"
        last_chain_write_event_ids = ["evt-request", "evt-final"]

    assert bridge_upstream_evidence(Bridge()) == {
        "upstream_event_ids": ["evt-request", "evt-final"],
        "upstream_source_agents": ["token-bridge"],
    }


def test_publish_marketplace_escrow_event_returns_none_when_bus_unavailable():
    class BrokenBus:
        def publish(self, *args, **kwargs):
            raise RuntimeError("event store down")

    event_id = publish_marketplace_escrow_event(
        transition="held",
        source_agent="maas-test",
        escrow_id="esc-3",
        listing_id="lst-3",
        event_bus=BrokenBus(),
    )

    assert event_id is None
