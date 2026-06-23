"""Unit tests for MaaS compatibility scale EventBus evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import src.api.maas_compat as compat_mod
import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _Mesh:
    def __init__(self, *, mesh_id: str, owner_id: str):
        self.mesh_id = mesh_id
        self.owner_id = owner_id
        self.status = "active"
        self.node_instances = {
            f"{mesh_id}-secret-node-1": {"status": "healthy"},
        }

    def scale(self, action: str, count: int) -> int:
        if action == "scale_up":
            for index in range(count):
                self.node_instances[f"{self.mesh_id}-secret-added-{index}"] = {
                    "status": "healthy",
                }
        elif action == "scale_down":
            for key in list(self.node_instances.keys())[:count]:
                self.node_instances.pop(key, None)
        return len(self.node_instances)


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-compat-scale",
            limit=10,
        )
    ]


def _install_mesh(monkeypatch, instance: _Mesh):
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: instance if candidate == instance.mesh_id else None,
    )


def test_compat_scale_success_publishes_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-scale"
    owner_id = "owner-secret-compat-scale"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    _install_mesh(monkeypatch, instance)
    audit_calls = []
    mapek_calls = []

    async def _record_audit_log(*args):
        audit_calls.append(args)

    monkeypatch.setattr(compat_mod.maas_registry, "record_audit_log", _record_audit_log)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "add_mapek_event",
        lambda *args: mapek_calls.append(args),
    )

    result = asyncio.run(
        compat_mod.scale_mesh_alias(
            mesh_id,
            legacy_mod.ScaleRequest(action="scale_up", count=2),
            request,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["mesh_id"] == mesh_id
    assert result["previous_nodes"] == 1
    assert result["current_nodes"] == 3
    assert (
        result["compat_lifecycle_control_claim_gate"]["surface"]
        == "maas_compat.lifecycle_control.scale"
    )
    assert result["compat_lifecycle_control_claim_gate"][
        "local_registry_mutation_claim_allowed"
    ] is True
    assert result["compat_lifecycle_control_claim_gate"][
        "local_audit_log_append_claim_allowed"
    ] is True
    assert result["compat_lifecycle_control_claim_gate"][
        "local_mapek_event_append_claim_allowed"
    ] is True
    assert result["compat_lifecycle_control_claim_gate"][
        "external_node_deployment_claim_allowed"
    ] is False
    assert result["compat_lifecycle_control_claim_gate"][
        "restored_dataplane_claim_allowed"
    ] is False
    assert result["compat_lifecycle_control_claim_gate"][
        "production_readiness_claim_allowed"
    ] is False
    assert result["cross_plane_claim_gate"]["surface"] == (
        "maas_compat.lifecycle_control.scale"
    )
    assert result["cross_plane_claim_gate"]["allowed"] is False
    assert http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"] == (
        "x0tta6bl4.maas_compat_lifecycle_control_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle_control.scale"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Local-Registry-Mutation-Claim-Allowed"
    ] == "true"
    assert http_response.headers[
        "X-X0TTA6BL4-External-Node-Deployment-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
    ] == "false"
    assert len(audit_calls) == 1
    assert len(mapek_calls) == 1

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mesh_scale"
    assert payload["service_name"] == "maas-compat-scale"
    assert payload["source_alias"] == "maas-compat-scale"
    assert payload["layer"] == "api_compat_lifecycle_control_action"
    assert payload["stage"] == "scale_applied"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["request_summary"] == {"action": "scale_up", "count": 2}
    assert payload["previous_nodes"] == 1
    assert payload["current_nodes"] == 3
    assert payload["delta_nodes"] == 2
    assert payload["registry_mutated"] is True
    assert payload["audit_log_recorded"] is True
    assert payload["mapek_event_recorded"] is True
    assert payload["compat_lifecycle_control_claim_gate_present"] is True
    assert payload["cross_plane_claim_gate_present"] is True
    assert payload["read_only"] is False
    assert payload["control_action"] is True
    assert payload["safe_actuator"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, f"{mesh_id}-secret-node-1"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_scale_access_denial_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-scale-denied"
    owner_id = "owner-secret-compat-scale-denied"
    actor_id = "actor-secret-compat-scale-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    _install_mesh(monkeypatch, instance)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.scale_mesh_alias(
                mesh_id,
                legacy_mod.ScaleRequest(action="scale_up", count=1),
                request,
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
    assert payload["registry_mutated"] is False
    assert payload["read_only"] is True
    assert payload["control_action"] is True
    assert payload["reason"] == "http_404"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, actor_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_scale_side_effect_failure_records_partial_local_mutation(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-compat-scale-failure"
    owner_id = "owner-secret-compat-scale-failure"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    _install_mesh(monkeypatch, instance)

    async def _record_audit_log(*_args):
        raise RuntimeError("private audit failure should not leak")

    monkeypatch.setattr(compat_mod.maas_registry, "record_audit_log", _record_audit_log)

    with pytest.raises(RuntimeError):
        asyncio.run(
            compat_mod.scale_mesh_alias(
                mesh_id,
                legacy_mod.ScaleRequest(action="scale_up", count=1),
                request,
                current_user=SimpleNamespace(id=owner_id, role="admin"),
            )
        )

    assert len(instance.node_instances) == 2
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "side_effect_failed"
    assert payload["status"] == "failed"
    assert payload["previous_nodes"] == 1
    assert payload["current_nodes"] == 2
    assert payload["registry_mutated"] is True
    assert payload["audit_log_recorded"] is False
    assert payload["mapek_event_recorded"] is False
    assert payload["reason"] == "RuntimeError"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, "private audit failure should not leak"):
        assert raw_value not in serialized
        assert raw_value not in raw_log
