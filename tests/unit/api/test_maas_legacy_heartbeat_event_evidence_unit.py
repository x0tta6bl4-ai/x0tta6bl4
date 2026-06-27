"""Unit tests for legacy MaaS heartbeat EventBus evidence."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _heartbeat(node_id: str):
    return legacy_mod.NodeHeartbeatRequest(
        node_id=node_id,
        cpu_usage=12.5,
        memory_usage=45.0,
        neighbors_count=3,
        routing_table_size=10,
        uptime=3600.0,
        pheromones={"dest-secret": {"next-hop-secret": 0.8}},
    )


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-legacy-heartbeat",
            limit=10,
        )
    ]


def test_legacy_heartbeat_accept_and_denials_publish_redacted_evidence(
    tmp_path,
    monkeypatch,
):
    owner_id = "owner-secret-heartbeat"
    other_user_id = "other-secret-heartbeat"
    mesh_id = "mesh-secret-heartbeat"
    node_id = "node-secret-heartbeat"
    unknown_node_id = "node-secret-unknown"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    monkeypatch.setattr(
        legacy_mod,
        "_mesh_registry",
        {
            mesh_id: SimpleNamespace(
                owner_id=owner_id,
                node_instances={node_id: {"status": "healthy"}},
            )
        },
    )
    monkeypatch.setattr(legacy_mod, "_node_telemetry", {})
    monkeypatch.setattr(legacy_mod, "_mesh_mapek_events", {})

    accepted = legacy_mod.heartbeat(
        _heartbeat(node_id),
        current_user=SimpleNamespace(id=owner_id, role="user"),
        request=request,
    )

    assert accepted["status"] == "ack"
    assert accepted["mesh_id"] == mesh_id

    with pytest.raises(HTTPException) as unknown_exc:
        legacy_mod.heartbeat(
            _heartbeat(unknown_node_id),
            current_user=SimpleNamespace(id=owner_id, role="user"),
            request=request,
        )
    assert unknown_exc.value.status_code == 404

    with pytest.raises(HTTPException) as owner_exc:
        legacy_mod.heartbeat(
            _heartbeat(node_id),
            current_user=SimpleNamespace(id=other_user_id, role="user"),
            request=request,
        )
    assert owner_exc.value.status_code == 404

    payloads = _payloads(bus)
    assert [payload["stage"] for payload in payloads] == [
        "accepted",
        "denied",
        "denied",
    ]

    accepted_payload = payloads[0]
    assert accepted_payload["operation"] == "legacy_heartbeat"
    assert accepted_payload["service_name"] == "maas-legacy-heartbeat"
    assert accepted_payload["source_alias"] == "maas-legacy-heartbeat"
    assert accepted_payload["layer"] == "api_legacy_heartbeat_observed_state"
    assert accepted_payload["status"] == "success"
    assert accepted_payload["node_found"] is True
    assert accepted_payload["owner_checked"] is True
    assert accepted_payload["authorized"] is True
    assert accepted_payload["stored_telemetry"] is True
    assert accepted_payload["mapek_event_recorded"] is True
    assert accepted_payload["duration_ms"] >= 0
    assert accepted_payload["storage_backend"] == "legacy_in_memory"
    assert accepted_payload["source_quality"] == "legacy_in_memory_telemetry_and_mapek"
    assert accepted_payload["dataplane_confirmed"] is False
    assert accepted_payload["read_only"] is False
    assert accepted_payload["raw_identifiers_redacted"] is True
    assert accepted_payload["payloads_redacted"] is True
    assert accepted_payload["node_id_hash"] == legacy_mod._redacted_sha256_prefix(
        node_id
    )
    assert accepted_payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(
        mesh_id
    )
    assert accepted_payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(
        owner_id
    )
    assert accepted_payload["heartbeat_summary"]["has_pheromones"] is True
    assert accepted_payload["heartbeat_summary"]["pheromone_destination_count"] == 1
    assert accepted_payload["heartbeat_summary"]["raw_metric_values_redacted"] is True
    assert accepted_payload["heartbeat_summary"]["payloads_redacted"] is True
    assert accepted_payload["telemetry_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": True,
        "current_node_stored": True,
        "stored_nodes_total": 1,
    }
    assert accepted_payload["mapek_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": True,
        "event_recorded": True,
        "mesh_event_count_after": 1,
        "buffer_limit": legacy_mod._MAPEK_EVENT_BUFFER_SIZE,
        "event_type": "node.heartbeat",
    }

    unknown_payload = payloads[1]
    assert unknown_payload["status"] == "denied"
    assert unknown_payload["reason"] == "node_not_found"
    assert unknown_payload["node_found"] is False
    assert unknown_payload["authorized"] is False
    assert unknown_payload["duration_ms"] >= 0
    assert unknown_payload["source_quality"] == "denied_before_state_mutation"
    assert unknown_payload["dataplane_confirmed"] is False
    assert unknown_payload["read_only"] is True
    assert unknown_payload["telemetry_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": False,
        "current_node_stored": False,
        "stored_nodes_total": 1,
    }
    assert unknown_payload["mapek_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": False,
        "event_recorded": False,
        "mesh_event_count_after": 0,
        "buffer_limit": legacy_mod._MAPEK_EVENT_BUFFER_SIZE,
        "event_type": None,
    }

    owner_payload = payloads[2]
    assert owner_payload["status"] == "denied"
    assert owner_payload["reason"] == "owner_mismatch"
    assert owner_payload["node_found"] is True
    assert owner_payload["owner_checked"] is True
    assert owner_payload["authorized"] is False
    assert owner_payload["duration_ms"] >= 0
    assert owner_payload["source_quality"] == "denied_before_state_mutation"
    assert owner_payload["dataplane_confirmed"] is False
    assert owner_payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert owner_payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(
        other_user_id
    )
    assert owner_payload["telemetry_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": False,
        "current_node_stored": True,
        "stored_nodes_total": 1,
    }
    assert owner_payload["mapek_store_summary"] == {
        "storage_backend": "legacy_in_memory",
        "mutation_attempted": False,
        "event_recorded": False,
        "mesh_event_count_after": 1,
        "buffer_limit": legacy_mod._MAPEK_EVENT_BUFFER_SIZE,
        "event_type": None,
    }

    serialized_payloads = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        owner_id,
        other_user_id,
        mesh_id,
        node_id,
        unknown_node_id,
        "dest-secret",
        "next-hop-secret",
    ):
        assert raw_value not in serialized_payloads
        assert raw_value not in raw_log
