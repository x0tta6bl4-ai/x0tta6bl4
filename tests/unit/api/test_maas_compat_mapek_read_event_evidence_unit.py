"""Unit tests for MaaS compatibility MAPE-K read EventBus evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import src.api.maas_compat as compat_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-compat-mapek-read",
            limit=10,
        )
    ]


def _install_mesh(monkeypatch, *, mesh_id: str, owner_id: str):
    instance = SimpleNamespace(mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: instance if candidate == mesh_id else None,
    )
    return instance


def test_compat_mapek_event_list_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-mapek"
    owner_id = "owner-secret-compat-mapek"
    node_id = "node-secret-compat-mapek"
    custom_type = "custom.secret.mapek.event"
    custom_action = "secret-scale-action"
    secret_signal = "private-mapek-signal"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mapek_events",
        lambda candidate: [
            {
                "type": "scale",
                "action": "scale_up",
                "from": 1,
                "to": 2,
                "timestamp": "2026-05-30T00:00:00",
            },
            {
                "node_id": node_id,
                "event_type": custom_type,
                "action": custom_action,
                "phase": "secret-phase",
                "cpu_usage": 91.0,
                "private_signal": secret_signal,
            },
        ]
        if candidate == mesh_id
        else [],
    )

    result = asyncio.run(
        compat_mod.get_mapek_events_alias(
            mesh_id,
            request,
            limit=10,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["mesh_id"] == mesh_id
    assert result["count"] == 2
    assert result["events"][1]["node_id"] == node_id
    assert result["events"][1]["event_type"] == custom_type

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mapek_event_read"
    assert payload["service_name"] == "maas-compat-mapek-read"
    assert payload["source_alias"] == "maas-compat-mapek-read"
    assert payload["layer"] == "api_compat_mapek_observed_state"
    assert payload["stage"] == "mapek_event_list_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["stored_event_count"] == 2
    assert payload["returned_event_count"] == 2
    assert payload["result_summary"]["type_counts"] == {"scale": 1, "other": 1}
    assert payload["result_summary"]["action_counts"] == {"scale_up": 1, "other": 1}
    assert payload["result_summary"]["phase_counts"] == {"other": 2}
    assert payload["result_summary"]["node_id_mentions"] == 1
    assert payload["result_summary"]["known_metric_mentions"] == 1
    assert (
        payload["result_summary"]["compat_read_list_claim_boundary_headers_present"]
        is True
    )
    assert payload["result_summary"]["claim_surface"] == "maas_compat.mapek_events"
    assert (
        payload["result_summary"]["local_mapek_event_observation_claim_allowed"]
        is True
    )
    assert (
        payload["result_summary"][
            "autonomous_remediation_completion_claim_allowed"
        ]
        is False
    )
    assert payload["result_summary"]["restored_dataplane_claim_allowed"] is False
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
        custom_type,
        custom_action,
        secret_signal,
        "secret-phase",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_mapek_event_alias_sets_claim_boundary_headers(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-compat-mapek-headers"
    owner_id = "owner-compat-mapek-headers"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(compat_mod.maas_registry, "get_mapek_events", lambda _id: [])

    result = asyncio.run(
        compat_mod.get_mapek_events_alias(
            mesh_id,
            request,
            limit=10,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["count"] == 0
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Surface"]
        == "maas_compat.mapek_events"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed"
        ]
        == "true"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed"
        ]
        == "false"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed"
        ]
        == "false"
    )


def test_compat_mapek_event_list_access_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-mapek-denied"
    owner_id = "owner-secret-compat-mapek-denied"
    actor_id = "actor-secret-compat-mapek-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.get_mapek_events_alias(
                mesh_id,
                request,
                limit=5,
                current_user=SimpleNamespace(id=actor_id, role="admin"),
            )
        )

    assert exc.value.status_code == 404
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mapek_event_read"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(actor_id)
    assert payload["owner_id_hash"] is None
    assert payload["ownership_checked"] is True
    assert payload["returned_event_count"] == 0
    assert payload["reason"] == "http_404"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, actor_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log
