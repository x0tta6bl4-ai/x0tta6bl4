from __future__ import annotations

from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import (
    get_service_event_history,
    get_service_event_replay,
    service_event_trace_history,
    service_event_trace_filter,
)
from src.services.service_identity_registry import KNOWN_EVENT_TRACE_SERVICES


def _source_agent(service: dict[str, str]) -> str:
    return service.get("source_agent") or service["service_name"]


def test_service_event_trace_filter_maps_layer_to_registered_source_agents():
    trace_filter = service_event_trace_filter(layer="dao_to_control_plane")

    expected = sorted(
        _source_agent(service)
        for service in KNOWN_EVENT_TRACE_SERVICES
        if service["layer"] == "dao_to_control_plane"
    )
    assert trace_filter["status"] == "ok"
    assert trace_filter["redacted"] is True
    assert trace_filter["source_agents"] == expected
    assert trace_filter["services_total"] == len(expected)


def test_service_event_trace_filter_reports_unknown_without_values():
    trace_filter = service_event_trace_filter(service_name="missing-service")

    assert trace_filter["status"] == "unknown_filter"
    assert trace_filter["source_agents"] == []
    assert trace_filter["services"] == []


def test_service_event_trace_filter_includes_route_only_marketplace_api():
    trace_filter = service_event_trace_filter(service_name="maas-marketplace")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-marketplace"]
    assert trace_filter["services"][0]["layer"] == "api_to_commerce"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_marketplace.py"
    assert trace_filter["services"][0]["identity_source"] == "request_user_identity"


def test_service_event_trace_filter_uses_source_agent_alias():
    trace_filter = service_event_trace_filter(service_name="pqc-zero-trust-executor")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["pqc-zero-trust-healer"]
    assert trace_filter["services"][0]["service_name"] == "pqc-zero-trust-executor"
    assert trace_filter["services"][0]["source_agent"] == "pqc-zero-trust-healer"


def test_service_event_history_and_replay_use_registry_filters(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    consensus = bus.publish(
        EventType.PIPELINE_STAGE_START,
        "swarm-pbft",
        {"stage": "consensus"},
        target_agents={"agent-b"},
    )
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "pqc-rotator",
        {"stage": "rotation"},
        target_agents={"agent-b"},
    )
    bus.publish(
        EventType.SYSTEM_ALERT,
        "unregistered-service",
        {"stage": "noise"},
        target_agents={"agent-b"},
    )

    history = get_service_event_history(
        bus,
        service_name="swarm-pbft",
        limit=10,
    )
    assert [event.event_id for event in history] == [consensus.event_id]

    replay = get_service_event_replay(
        bus,
        "agent-b",
        layer="swarm_consensus_to_control_plane",
    )
    assert [event.event_id for event in replay] == [consensus.event_id]


def test_service_event_history_uses_source_agent_alias(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "pqc-zero-trust-healer",
        {"stage": "action_completed"},
    )

    history = get_service_event_history(
        bus,
        service_name="pqc-zero-trust-executor",
        limit=10,
    )

    assert [item.event_id for item in history] == [event.event_id]


def test_service_event_trace_history_redacts_identity_values(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_START,
        "swarm-pbft",
        {
            "spiffe_id": "spiffe://secret/workload",
            "did": "did:mesh:secret",
            "wallet_address": "0xffffffffffffffffffffffffffffffffffffffff",
            "identity": {
                "spiffe_id": "spiffe://secret/nested",
                "api_token": "secret-value-that-must-not-leak",
                "node_id": "node-1",
            },
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="swarm-pbft",
        limit=10,
    )
    text = str(payload)

    assert payload["events_total"] == 1
    assert payload["events"][0]["data"]["spiffe_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["spiffe_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["api_token"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["node_id"] == "node-1"
    assert "spiffe://secret" not in text
    assert "did:mesh:secret" not in text
    assert "secret-value-that-must-not-leak" not in text
    assert "0xffff" not in text
