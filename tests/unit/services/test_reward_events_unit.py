"""Unit tests for reward settlement EventBus publication."""

import json

from src.coordination.events import EventBus, EventType
from src.services.reward_events import publish_reward_settlement_event


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
    assert event.data["packets"] == 250
    assert event.data["amount"] == "0.0250"
    assert event.data["simulated"] is True
    assert event.data["submitted_transaction"] is False

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
