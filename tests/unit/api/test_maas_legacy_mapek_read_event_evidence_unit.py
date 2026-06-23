"""Unit tests for legacy MaaS MAPE-K read EventBus evidence."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _Provisioner:
    def __init__(self, instances):
        self.instances = {instance.mesh_id: instance for instance in instances}

    def get(self, mesh_id):
        return self.instances.get(mesh_id)


class _Mesh:
    def __init__(self, *, mesh_id: str, owner_id: str):
        self.mesh_id = mesh_id
        self.owner_id = owner_id
        self.join_token = "mapek-read-token-secret"
        self.join_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.node_instances = {}


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-legacy-mapek-read",
            limit=10,
        )
    ]


def test_legacy_mapek_event_list_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-mapek-read"
    owner_id = "owner-secret-mapek-read"
    node_id = "node-secret-mapek-read"
    secret_phase = "secret-remediation-phase"
    secret_event_type = "custom.secret.event"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([instance]))
    monkeypatch.setattr(
        legacy_mod,
        "_mesh_mapek_events",
        {
            mesh_id: [
                {
                    "node_id": node_id,
                    "phase": "MONITOR",
                    "event_type": "node.heartbeat",
                    "cpu_usage": 91.0,
                    "timestamp": "2026-05-30T00:00:00",
                    "private_signal": "mapek-secret-value",
                },
                {
                    "node_id": f"{node_id}-two",
                    "phase": secret_phase,
                    "event_type": secret_event_type,
                    "memory_usage": 72.0,
                },
            ],
        },
    )

    result = legacy_mod.list_mapek_events(
        mesh_id,
        limit=10,
        current_user=SimpleNamespace(id=owner_id, role="admin"),
        request=request,
    )

    assert result["mesh_id"] == mesh_id
    assert result["count"] == 2
    assert result["events"][0]["node_id"] == node_id
    assert result["events"][1]["phase"] == secret_phase

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mapek_event_read"
    assert payload["service_name"] == "maas-legacy-mapek-read"
    assert payload["source_alias"] == "maas-legacy-mapek-read"
    assert payload["layer"] == "api_legacy_mapek_observed_state"
    assert payload["stage"] == "mapek_event_list_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["stored_event_count"] == 2
    assert payload["returned_event_count"] == 2
    assert payload["result_summary"]["phase_counts"] == {"MONITOR": 1, "other": 1}
    assert payload["result_summary"]["event_type_counts"] == {
        "node.heartbeat": 1,
        "other": 1,
    }
    assert payload["result_summary"]["node_id_mentions"] == 2
    assert payload["result_summary"]["known_metric_mentions"] == 2
    assert payload["read_only"] is True
    assert payload["control_action"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        node_id,
        secret_phase,
        secret_event_type,
        "mapek-secret-value",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_mapek_event_list_access_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-mapek-denied"
    owner_id = "owner-secret-mapek-denied"
    actor_id = "actor-secret-mapek-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([instance]))
    monkeypatch.setattr(legacy_mod, "_mesh_mapek_events", {mesh_id: []})

    with pytest.raises(HTTPException) as exc:
        legacy_mod.list_mapek_events(
            mesh_id,
            limit=5,
            current_user=SimpleNamespace(id=actor_id, role="admin"),
            request=request,
        )

    assert exc.value.status_code == 404

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mapek_event_read"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(actor_id)
    assert payload["owner_id_hash"] is None
    assert payload["returned_event_count"] == 0
    assert payload["reason"] == "http_404"
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, actor_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log
