"""Unit tests for MaaS compatibility terminate EventBus evidence."""

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
            source_agent="maas-compat-terminate",
            limit=10,
        )
    ]


def _mesh(*, mesh_id: str, owner_id: str):
    return SimpleNamespace(
        mesh_id=mesh_id,
        owner_id=owner_id,
        status="active",
        node_instances={
            f"{mesh_id}-secret-node-1": {"status": "healthy"},
            f"{mesh_id}-secret-node-2": {"status": "healthy"},
        },
    )


def test_compat_terminate_success_publishes_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-terminate"
    owner_id = "owner-secret-compat-terminate"
    reason = "private customer offboarding reason"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    instance = _mesh(mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: instance if candidate == mesh_id else None,
    )

    async def _terminate_mesh(*, mesh_id, user, reason):
        return {"mesh_id": mesh_id, "status": "terminated", "reason": reason}

    monkeypatch.setattr(compat_mod.modular_mesh, "terminate_mesh", _terminate_mesh)

    result = asyncio.run(
        compat_mod.terminate_mesh_alias(
            mesh_id,
            request,
            http_response=http_response,
            reason=reason,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["mesh_id"] == mesh_id
    assert result["status"] == "terminated"
    assert result["reason"] == reason
    assert (
        result["compat_lifecycle_control_claim_gate"]["surface"]
        == "maas_compat.lifecycle_control.terminate"
    )
    assert result["compat_lifecycle_control_claim_gate"][
        "local_registry_mutation_claim_allowed"
    ] is True
    assert result["compat_lifecycle_control_claim_gate"][
        "delegated_modular_lifecycle_claim_allowed"
    ] is True
    assert result["compat_lifecycle_control_claim_gate"][
        "external_node_shutdown_claim_allowed"
    ] is False
    assert result["compat_lifecycle_control_claim_gate"][
        "restored_dataplane_claim_allowed"
    ] is False
    assert result["compat_lifecycle_control_claim_gate"][
        "production_readiness_claim_allowed"
    ] is False
    assert result["cross_plane_claim_gate"]["surface"] == (
        "maas_compat.lifecycle_control.terminate"
    )
    assert result["cross_plane_claim_gate"]["allowed"] is False
    assert http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"] == (
        "x0tta6bl4.maas_compat_lifecycle_control_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle_control.terminate"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Delegated-Modular-Lifecycle-Claim-Allowed"
    ] == "true"
    assert http_response.headers[
        "X-X0TTA6BL4-External-Node-Shutdown-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
    ] == "false"

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mesh_terminate"
    assert payload["service_name"] == "maas-compat-terminate"
    assert payload["source_alias"] == "maas-compat-terminate"
    assert payload["layer"] == "api_compat_lifecycle_control_action"
    assert payload["stage"] == "terminate_applied"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["request_summary"] == {
        "reason_present": True,
        "reason_length": len(reason),
    }
    assert payload["previous_status"] == "active"
    assert payload["previous_node_count"] == 2
    assert payload["delegated_to_modular"] is True
    assert payload["registry_mutated"] is True
    assert payload["result_summary"] == {
        "status": "terminated",
        "reason_present": True,
        "result_field_count": 5,
        "compat_lifecycle_control_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
    }
    assert payload["read_only"] is False
    assert payload["control_action"] is True
    assert payload["safe_actuator"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, reason, f"{mesh_id}-secret-node-1"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_terminate_http_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-terminate-denied"
    actor_id = "actor-secret-compat-terminate-denied"
    reason = "private denied reason"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    monkeypatch.setattr(compat_mod.maas_registry, "get_mesh", lambda _mesh_id: None)

    async def _terminate_mesh(*, mesh_id, user, reason):
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")

    monkeypatch.setattr(compat_mod.modular_mesh, "terminate_mesh", _terminate_mesh)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.terminate_mesh_alias(
                mesh_id,
                request,
                reason=reason,
                current_user=SimpleNamespace(id=actor_id, role="admin"),
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
    assert payload["delegated_to_modular"] is True
    assert payload["registry_mutated"] is False
    assert payload["read_only"] is True
    assert payload["control_action"] is True
    assert payload["reason"] == "http_404"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, actor_id, reason):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_terminate_unexpected_failure_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-terminate-failed"
    owner_id = "owner-secret-compat-terminate-failed"
    reason = "private failure reason"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _mesh(mesh_id=mesh_id, owner_id=owner_id)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: instance if candidate == mesh_id else None,
    )

    async def _terminate_mesh(*, mesh_id, user, reason):
        raise RuntimeError("private terminate failure should not leak")

    monkeypatch.setattr(compat_mod.modular_mesh, "terminate_mesh", _terminate_mesh)

    with pytest.raises(RuntimeError):
        asyncio.run(
            compat_mod.terminate_mesh_alias(
                mesh_id,
                request,
                reason=reason,
                current_user=SimpleNamespace(id=owner_id, role="admin"),
            )
        )

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "terminate_failed"
    assert payload["status"] == "failed"
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["previous_status"] == "active"
    assert payload["previous_node_count"] == 2
    assert payload["delegated_to_modular"] is True
    assert payload["registry_mutated"] is False
    assert payload["reason"] == "RuntimeError"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        reason,
        "private terminate failure should not leak",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
