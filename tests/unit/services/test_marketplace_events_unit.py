"""Unit tests for marketplace escrow EventBus publication."""

import json

from src.coordination.events import EventBus, EventType
from src.services.marketplace_events import publish_marketplace_escrow_event


def test_publish_marketplace_escrow_event_records_canonical_identity(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_marketplace_escrow_event(
        transition="released",
        source_agent="maas-test",
        escrow_id="esc-1",
        listing_id="lst-1",
        renter_id=42,
        actor_id="operator-1",
        currency="X0T",
        status="released",
        node_id="node-1",
        mesh_id="mesh-1",
        spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/marketplace",
        did="did:mesh:pqc:renter-42",
        wallet_address="0x" + "a" * 40,
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
        "escrow_id": "esc-1",
        "listing_id": "lst-1",
        "renter_id": "42",
        "actor_id": "operator-1",
        "node_id": "node-1",
        "mesh_id": "mesh-1",
        "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/marketplace",
        "did": "did:mesh:pqc:renter-42",
        "wallet_address": "0x" + "a" * 40,
    }
    assert event.data["spiffe_id"] == "spiffe://mesh.x0tta6bl4.mesh/workload/marketplace"
    assert event.data["did"] == "did:mesh:pqc:renter-42"
    assert event.data["wallet_address"] == "0x" + "a" * 40
    assert event.data["currency"] == "X0T"
    assert event.data["amount_token"] == 12.5
    assert event.data["reason"] == "unit-test"

    log_path = tmp_path / ".agent_coordination" / "events.log"
    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["event_id"] == event_id
    assert payload["event_type"] == EventType.MARKETPLACE_ESCROW_RELEASED.value


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
