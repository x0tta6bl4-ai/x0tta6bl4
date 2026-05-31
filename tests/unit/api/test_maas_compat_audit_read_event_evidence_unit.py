"""Unit tests for MaaS compatibility audit-log read EventBus evidence."""

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
            source_agent="maas-compat-audit-read",
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


def test_compat_audit_log_read_publishes_redacted_evidence(monkeypatch, tmp_path):
    mesh_id = "mesh-secret-compat-audit"
    owner_id = "owner-secret-compat-audit"
    actor_secret = "audit-actor-secret"
    details_secret = "scaled because private customer signal"
    unknown_event_secret = "custom.secret.audit.event"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_audit_log",
        lambda candidate: [
            {
                "timestamp": "2026-05-30T00:00:00",
                "actor": actor_secret,
                "event": "mesh.scale",
                "details": details_secret,
            },
            {
                "timestamp": "2026-05-30T00:01:00",
                "actor": f"{actor_secret}-two",
                "event": unknown_event_secret,
                "details": "another private detail",
            },
        ]
        if candidate == mesh_id
        else [],
    )

    result = asyncio.run(
        compat_mod.get_audit_logs_alias(
            mesh_id,
            request,
            limit=10,
            current_user=SimpleNamespace(id=owner_id, role="admin", permissions=""),
        )
    )

    assert result["mesh_id"] == mesh_id
    assert result["count"] == 2
    assert result["events"][0]["actor"] == actor_secret
    assert result["events"][1]["event"] == unknown_event_secret

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_audit_log_read"
    assert payload["service_name"] == "maas-compat-audit-read"
    assert payload["source_alias"] == "maas-compat-audit-read"
    assert payload["layer"] == "api_compat_audit_observed_state"
    assert payload["stage"] == "audit_log_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["stored_event_count"] == 2
    assert payload["returned_event_count"] == 2
    assert payload["result_summary"]["event_name_counts"] == {
        "mesh.scale": 1,
        "other": 1,
    }
    assert payload["result_summary"]["actor_mentions"] == 2
    assert payload["result_summary"]["details_present_count"] == 2
    assert (
        payload["result_summary"]["compat_read_list_claim_boundary_headers_present"]
        is True
    )
    assert payload["result_summary"]["claim_surface"] == "maas_compat.audit_logs"
    assert (
        payload["result_summary"]["local_audit_log_observation_claim_allowed"]
        is True
    )
    assert payload["result_summary"]["dataplane_delivery_claim_allowed"] is False
    assert (
        payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
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
        actor_secret,
        details_secret,
        unknown_event_secret,
        "another private detail",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_audit_log_alias_sets_claim_boundary_headers(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-compat-audit-headers"
    owner_id = "owner-compat-audit-headers"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(compat_mod.maas_registry, "get_audit_log", lambda _id: [])

    result = asyncio.run(
        compat_mod.get_audit_logs_alias(
            mesh_id,
            request,
            limit=10,
            http_response=http_response,
            current_user=SimpleNamespace(
                id=owner_id,
                role="admin",
                permissions="",
            ),
        )
    )

    assert result["count"] == 0
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_read_list_claim_boundary_headers.v1"
    )
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Surface"]
        == "maas_compat.audit_logs"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed"
        ]
        == "true"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Durable-Audit-Persistence-Claim-Allowed"
        ]
        == "false"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
        ]
        == "false"
    )


def test_compat_audit_log_permission_denial_publishes_redacted_evidence(tmp_path):
    mesh_id = "mesh-secret-compat-permission-denied"
    actor_id = "actor-secret-compat-permission-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.get_audit_logs_alias(
                mesh_id,
                request,
                limit=5,
                current_user=SimpleNamespace(id=actor_id, role="user", permissions=""),
            )
        )

    assert exc.value.status_code == 403
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "permission_denied"
    assert payload["status"] == "denied"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(actor_id)
    assert payload["owner_id_hash"] is None
    assert payload["ownership_checked"] is False
    assert payload["returned_event_count"] == 0
    assert payload["reason"] == "missing_audit_view_permission"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, actor_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_audit_log_access_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-access-denied"
    owner_id = "owner-secret-compat-access-denied"
    actor_id = "actor-secret-compat-access-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    _install_mesh(monkeypatch, mesh_id=mesh_id, owner_id=owner_id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.get_audit_logs_alias(
                mesh_id,
                request,
                limit=5,
                current_user=SimpleNamespace(
                    id=actor_id,
                    role="user",
                    permissions="audit:view",
                ),
            )
        )

    assert exc.value.status_code == 404
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
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
