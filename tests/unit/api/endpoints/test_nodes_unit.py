"""Unit tests for src/api/maas/endpoints/nodes.py."""

import json
import secrets
from datetime import datetime
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import nodes as mod
from src.api.maas.models import NodeHeartbeatRequest, NodeRegisterRequest
from src.api.maas_nodes import MeshPermission, _ensure_owner_or_admin_access
from src.coordination.events import EventBus, EventType
from src.database import Base, MeshInstance, User
from src.services.service_event_trace import event_trace_evidence_summary


def test_to_optional_float_handles_valid_and_invalid_values():
    assert mod._to_optional_float(12) == 12.0
    assert mod._to_optional_float("3.5") == 3.5
    assert mod._to_optional_float(None) is None
    assert mod._to_optional_float("not-a-number") is None


def test_build_external_telemetry_payload_uses_fallbacks_and_filters_negative_metrics():
    request = NodeHeartbeatRequest(
        mesh_id="mesh-1",
        node_id="node-1",
        cpu_usage=55.0,
        memory_usage=44.0,
        neighbors_count=7,
        custom_metrics={"latency_ms": "-1", "traffic_mbps": "12.5"},
    )

    payload = mod._build_external_telemetry_payload(request, "2026-01-01T00:00:00Z")

    assert payload["cpu_percent"] == 55.0
    assert payload["memory_percent"] == 44.0
    assert payload["active_connections"] == 7
    assert "latency_ms" not in payload
    assert payload["traffic_mbps"] == 12.5


def test_export_external_telemetry_returns_false_when_not_configured(monkeypatch):
    monkeypatch.setattr(mod, "_set_external_telemetry", None)
    assert mod._export_external_telemetry("node-1", {"x": 1}) is False


def test_export_external_telemetry_handles_export_errors(monkeypatch):
    def _boom(_node_id, _payload):
        raise RuntimeError("broken")

    monkeypatch.setattr(mod, "_set_external_telemetry", _boom)
    assert mod._export_external_telemetry("node-1", {"x": 1}) is False


def test_export_external_telemetry_returns_true_on_success(monkeypatch):
    captured = {}

    def _ok(node_id, payload):
        captured["node_id"] = node_id
        captured["payload"] = payload

    monkeypatch.setattr(mod, "_set_external_telemetry", _ok)

    assert mod._export_external_telemetry("node-1", {"x": 1}) is True
    assert captured == {"node_id": "node-1", "payload": {"x": 1}}


class _NodeEvidenceRequest:
    def __init__(self, bus: EventBus):
        self.state = SimpleNamespace(event_bus=bus)


def _node_event_payloads(bus: EventBus, source_agent: str) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=20,
        )
    ]


@pytest.mark.asyncio
async def test_resolve_mesh_for_user_requires_acl_when_owner_differs(monkeypatch):
    instance = SimpleNamespace(owner_id="owner-1")
    calls = {"require": 0}

    monkeypatch.setattr(mod, "get_mesh", lambda _mesh_id: instance)

    async def _require(_mesh_id, _user):
        calls["require"] += 1

    monkeypatch.setattr(mod, "require_mesh_access", _require)
    user = UserContext(user_id="other-user", plan="starter")

    resolved = await mod._resolve_mesh_for_user("mesh-1", user)
    assert resolved is instance
    assert calls["require"] == 1


@pytest.mark.asyncio
async def test_resolve_mesh_for_user_skips_acl_for_owner(monkeypatch):
    instance = SimpleNamespace(owner_id="owner-1")
    calls = {"require": 0}

    monkeypatch.setattr(mod, "get_mesh", lambda _mesh_id: instance)

    async def _require(_mesh_id, _user):
        calls["require"] += 1

    monkeypatch.setattr(mod, "require_mesh_access", _require)
    user = UserContext(user_id="owner-1", plan="starter")

    resolved = await mod._resolve_mesh_for_user("mesh-1", user)
    assert resolved is instance
    assert calls["require"] == 0


@pytest.mark.asyncio
async def test_resolve_mesh_for_user_retries_lookup_after_acl_check(monkeypatch):
    instance = SimpleNamespace(owner_id="owner-1")
    calls = {"get": 0, "require": 0}

    def _get_mesh(_mesh_id):
        calls["get"] += 1
        if calls["get"] == 1:
            return None
        return instance

    async def _require(_mesh_id, _user):
        calls["require"] += 1

    monkeypatch.setattr(mod, "get_mesh", _get_mesh)
    monkeypatch.setattr(mod, "require_mesh_access", _require)
    user = UserContext(user_id="owner-1", plan="starter")

    resolved = await mod._resolve_mesh_for_user("mesh-1", user)
    assert resolved is instance
    assert calls["require"] == 1
    assert calls["get"] == 2


@pytest.mark.asyncio
async def test_resolve_mesh_for_user_raises_404_when_not_found_after_acl_check(monkeypatch):
    monkeypatch.setattr(mod, "get_mesh", lambda _mesh_id: None)

    async def _require(_mesh_id, _user):
        return None

    monkeypatch.setattr(mod, "require_mesh_access", _require)
    user = UserContext(user_id="user-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod._resolve_mesh_for_user("mesh-404", user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_register_node_requires_mesh_id():
    request = NodeRegisterRequest(mesh_id=None, node_id="node-1")
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.register_node(request, user)

    assert exc.value.status_code == 400
    assert exc.value.detail == "mesh_id is required"


@pytest.mark.asyncio
async def test_register_node_requires_node_id():
    request = NodeRegisterRequest(mesh_id="mesh-1", node_id=None)
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.register_node(request, user)

    assert exc.value.status_code == 400
    assert exc.value.detail == "node_id is required"


@pytest.mark.asyncio
async def test_register_node_success_adds_pending(monkeypatch):
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "is_node_revoked", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        mod,
        "add_pending_node",
        lambda mesh_id, node_id, data: captured.update(
            {"mesh_id": mesh_id, "node_id": node_id, "data": data}
        ),
    )

    request = NodeRegisterRequest(
        mesh_id="mesh-1",
        node_id="node-1",
        device_class="edge",
        public_key="legacy-key",
        public_keys={"pqc": "pqc-key"},
        capabilities=["edge", "routing"],
        metadata={"region": "us"},
        labels={"tier": "prod"},
        hardware_id="hw-1",
    )
    user = UserContext(user_id="owner-1", plan="starter")

    response = await mod.register_node(request, user)
    assert response.status == "pending"
    assert captured["mesh_id"] == "mesh-1"
    assert captured["node_id"] == "node-1"
    assert captured["data"]["public_key"] == "legacy-key"
    assert captured["data"]["requested_by"] == "owner-1"


@pytest.mark.asyncio
async def test_register_node_uses_pqc_public_key_when_legacy_key_missing(monkeypatch):
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "is_node_revoked", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        mod,
        "add_pending_node",
        lambda mesh_id, node_id, data: captured.update(
            {"mesh_id": mesh_id, "node_id": node_id, "data": data}
        ),
    )

    request = NodeRegisterRequest(
        mesh_id="mesh-1",
        node_id="node-1",
        public_key=None,
        public_keys={"pqc": "pqc-only-key"},
    )
    user = UserContext(user_id="owner-1", plan="starter")

    await mod.register_node(request, user)
    assert captured["data"]["public_key"] == "pqc-only-key"


@pytest.mark.asyncio
async def test_register_node_defaults_capability_to_device_class(monkeypatch):
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "is_node_revoked", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        mod,
        "add_pending_node",
        lambda mesh_id, node_id, data: captured.update(
            {"mesh_id": mesh_id, "node_id": node_id, "data": data}
        ),
    )

    request = NodeRegisterRequest(
        mesh_id="mesh-1",
        node_id="node-1",
        device_class="gateway",
    )
    user = UserContext(user_id="owner-1", plan="starter")

    await mod.register_node(request, user)

    assert captured["data"]["capabilities"] == ["gateway"]


@pytest.mark.asyncio
async def test_register_node_rejects_revoked(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "is_node_revoked", lambda *_args, **_kwargs: True)

    request = NodeRegisterRequest(mesh_id="mesh-1", node_id="node-1")
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.register_node(request, user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_node_heartbeat_updates_registry_and_export_status(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mod,
        "update_node_telemetry",
        lambda node_id, payload: captured.update({"node_id": node_id, "payload": payload}),
    )
    monkeypatch.setattr(mod, "_export_external_telemetry", lambda *_args, **_kwargs: True)

    request = NodeHeartbeatRequest(
        mesh_id="mesh-1",
        node_id="node-1",
        cpu_usage=20.0,
        memory_usage=30.0,
        neighbors_count=4,
    )

    result = await mod.node_heartbeat(request)
    assert result["status"] == "ok"
    assert result["telemetry_exported"] is True
    assert captured["node_id"] == "node-1"
    assert captured["payload"]["active_connections"] == 4


@pytest.mark.asyncio
async def test_list_pending_nodes_returns_flat_list(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    pending = {
        "node-1": {"requested_by": "user-1"},
        "node-2": {"requested_by": "user-2"},
    }
    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_pending_nodes", lambda _mesh_id: pending)

    user = UserContext(user_id="owner-1", plan="starter")
    result = await mod.list_pending_nodes("mesh-1", user)

    assert len(result) == 2
    assert {"node_id": "node-1", "mesh_id": "mesh-1", "requested_by": "user-1"} in result
    assert {"node_id": "node-2", "mesh_id": "mesh-1", "requested_by": "user-2"} in result


@pytest.mark.asyncio
async def test_approve_node_maps_value_error_to_http_400(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    class _Provisioner:
        async def approve_node(self, **_kwargs):
            raise ValueError("bad approval request")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner())
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.approve_node("mesh-1", "node-1", user)

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad approval request"


@pytest.mark.asyncio
async def test_approve_node_success_passes_actor_and_returns_result(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    captured = {}

    class _Provisioner:
        async def approve_node(self, **kwargs):
            captured.update(kwargs)
            return {"status": "approved", "node_id": kwargs["node_id"]}

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner())
    user = UserContext(user_id="owner-1", plan="starter")

    result = await mod.approve_node("mesh-1", "node-1", user)
    assert result["status"] == "approved"
    assert captured == {
        "mesh_id": "mesh-1",
        "node_id": "node-1",
        "actor": "owner-1",
    }


@pytest.mark.asyncio
async def test_revoke_node_maps_value_error_to_http_400(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    class _Provisioner:
        async def revoke_node(self, **_kwargs):
            raise ValueError("bad revoke request")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner())
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.revoke_node("mesh-1", "node-1", user, reason="manual")

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad revoke request"


@pytest.mark.asyncio
async def test_revoke_node_success_passes_reason_and_returns_result(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    captured = {}

    class _Provisioner:
        async def revoke_node(self, **kwargs):
            captured.update(kwargs)
            return {"status": "revoked", "reason": kwargs["reason"]}

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner())
    user = UserContext(user_id="owner-1", plan="starter")

    result = await mod.revoke_node("mesh-1", "node-1", user, reason="manual")
    assert result["status"] == "revoked"
    assert captured == {
        "mesh_id": "mesh-1",
        "node_id": "node-1",
        "actor": "owner-1",
        "reason": "manual",
    }


@pytest.mark.asyncio
async def test_get_telemetry_raises_404_when_missing(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_node_telemetry", lambda _node_id: {})
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.get_telemetry("mesh-1", "node-1", user)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_telemetry_returns_payload(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    telemetry = {"cpu_percent": 12.3}
    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_node_telemetry", lambda _node_id: telemetry)
    user = UserContext(user_id="owner-1", plan="starter")

    result = await mod.get_telemetry("mesh-1", "node-1", user)
    assert result == telemetry


@pytest.mark.asyncio
async def test_get_telemetry_raises_404_on_mesh_mismatch(monkeypatch):
    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(
        mod,
        "get_node_telemetry",
        lambda _node_id: {"mesh_id": "mesh-other", "cpu_percent": 10.0},
    )
    user = UserContext(user_id="owner-1", plan="starter")

    with pytest.raises(HTTPException) as exc:
        await mod.get_telemetry("mesh-1", "node-1", user)

    assert exc.value.status_code == 404
    assert "mesh-1" in exc.value.detail


@pytest.mark.asyncio
async def test_request_reissue_persists_token_and_returns_payload(monkeypatch):
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id="owner-1")

    def _add_reissue_token(mesh_id, token, payload):
        captured["mesh_id"] = mesh_id
        captured["token"] = token
        captured["payload"] = payload

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr("src.api.maas.registry.add_reissue_token", _add_reissue_token)
    monkeypatch.setattr(secrets, "token_urlsafe", lambda _n: "fixed-token")

    user = UserContext(user_id="owner-1", plan="starter")
    result = await mod.request_reissue("mesh-1", "node-7", user)

    assert result["mesh_id"] == "mesh-1"
    assert result["node_id"] == "node-7"
    assert result["reissue_token"] == "reissue_fixed-token"
    assert result["expires_in"] == 3600

    assert captured["mesh_id"] == "mesh-1"
    assert captured["token"] == "reissue_fixed-token"
    assert captured["payload"]["node_id"] == "node-7"
    assert captured["payload"]["used"] is False
    assert captured["payload"]["issued_by"] == "owner-1"
    issued_at = datetime.fromisoformat(captured["payload"]["issued_at"])
    expires_at = datetime.fromisoformat(captured["payload"]["expires_at"])
    assert expires_at > issued_at


@pytest.mark.asyncio
async def test_register_node_publishes_redacted_registration_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-node-registration-secret"
    mesh_id = "mesh-node-registration-secret"
    node_id = "node-registration-secret"
    bus = EventBus(str(tmp_path))
    http_request = _NodeEvidenceRequest(bus)
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id=user_id)

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "is_node_revoked", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        mod,
        "add_pending_node",
        lambda mesh_id, node_id, data: captured.update(
            {"mesh_id": mesh_id, "node_id": node_id, "data": data}
        ),
    )

    request = NodeRegisterRequest(
        mesh_id=mesh_id,
        node_id=node_id,
        enrollment_token="enrollment-token-secret",
        device_class="gateway",
        public_key="legacy-public-key-secret",
        public_keys={"pqc": "pqc-public-key-secret"},
        capabilities=["edge", "routing"],
        metadata={"serial": "serial-secret"},
        labels={"tier": "prod"},
        hardware_id="hardware-secret",
        attestation_data={"quote": "attestation-secret"},
        enclave_enabled=True,
    )
    user = UserContext(user_id=user_id, plan="starter")

    response = await mod.register_node(request, user, http_request=http_request)

    assert response.status == "pending"
    assert captured["mesh_id"] == mesh_id
    assert captured["node_id"] == node_id

    payloads = _node_event_payloads(
        bus,
        mod._MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "register_node"
    assert payload["layer"] == "api_modular_node_registration_control_action"
    assert payload["status"] == "success"
    assert payload["source_quality"] == "local_pending_node_registration_recorded"
    assert payload["actor_user_id_hash"]
    assert payload["mesh_id_hash"]
    assert payload["node_id_hash"]
    assert payload["node_lifecycle_evidence"]["dataplane_confirmed"] is False
    assert payload["node_lifecycle_evidence"]["node_identity_attested"] is False
    assert payload["node_lifecycle_evidence"]["spiffe_authenticated"] is False
    assert payload["node_lifecycle_evidence"]["registry_mutation"] == {
        "attempted": True,
        "committed": True,
        "payloads_redacted": True,
    }
    assert payload["result_summary"]["capabilities"] == {
        "count": 2,
        "known": ["edge", "routing"],
    }
    assert payload["result_summary"]["attestation_present"] is True

    trace_summary = event_trace_evidence_summary(payload)
    assert trace_summary["runtime_evidence"]["present"] is True
    assert "node_lifecycle_evidence" in trace_summary["runtime_evidence"][
        "evidence_blocks_present"
    ]

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user_id,
        mesh_id,
        node_id,
        "enrollment-token-secret",
        "legacy-public-key-secret",
        "pqc-public-key-secret",
        "serial-secret",
        "hardware-secret",
        "attestation-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_node_heartbeat_publishes_redacted_observed_state_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-heartbeat-secret"
    node_id = "node-heartbeat-secret"
    bus = EventBus(str(tmp_path))
    http_request = _NodeEvidenceRequest(bus)
    captured = {}

    monkeypatch.setattr(
        mod,
        "update_node_telemetry",
        lambda node_id, payload: captured.update(
            {"node_id": node_id, "payload": payload}
        ),
    )
    monkeypatch.setattr(mod, "_export_external_telemetry", lambda *_args: True)

    request = NodeHeartbeatRequest(
        mesh_id=mesh_id,
        node_id=node_id,
        cpu_usage=20.0,
        memory_usage=30.0,
        neighbors_count=4,
        routing_table_size=9,
        custom_metrics={"latency_ms": "12.5", "secret": "metric-secret"},
    )

    result = await mod.node_heartbeat(request, http_request=http_request)

    assert result["status"] == "ok"
    assert result["telemetry_exported"] is True
    assert captured["node_id"] == node_id

    payloads = _node_event_payloads(bus, mod._MODULAR_NODE_HEARTBEAT_SOURCE_AGENT)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "node_heartbeat"
    assert payload["read_only"] is False
    assert payload["control_action"] is False
    assert payload["source_quality"] == "local_heartbeat_telemetry_recorded"
    assert payload["node_lifecycle_evidence"]["dataplane_confirmed"] is False
    assert payload["node_lifecycle_evidence"]["node_identity_attested"] is False
    assert payload["node_lifecycle_evidence"]["telemetry_store"] == {
        "attempted": True,
        "committed": True,
        "read": False,
        "payloads_redacted": True,
    }
    assert payload["result_summary"]["custom_metrics_count"] == 2
    assert payload["result_summary"]["neighbors_count"] == 4
    assert payload["result_summary"]["telemetry_exported"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, node_id, "metric-secret", "12.5"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_node_read_routes_publish_redacted_read_only_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-node-read-secret"
    mesh_id = "mesh-node-read-secret"
    node_id = "node-read-secret"
    bus = EventBus(str(tmp_path))
    http_request = _NodeEvidenceRequest(bus)

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id=user_id)

    pending = {
        node_id: {
            "requested_by": user_id,
            "hardware_id": "hardware-read-secret",
            "metadata": {"serial": "serial-read-secret"},
            "device_class": "gateway",
        }
    }
    telemetry = {
        "mesh_id": mesh_id,
        "cpu_percent": 12.3,
        "memory_percent": 45.6,
        "neighbors_count": 3,
        "custom_metrics": {"latency_ms": "11", "token": "telemetry-secret"},
    }
    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_pending_nodes", lambda _mesh_id: pending)
    monkeypatch.setattr(mod, "get_node_telemetry", lambda _node_id: telemetry)
    user = UserContext(user_id=user_id, plan="starter")

    pending_response = await mod.list_pending_nodes(
        mesh_id,
        user,
        http_request=http_request,
    )
    telemetry_response = await mod.get_telemetry(
        mesh_id,
        node_id,
        user,
        http_request=http_request,
    )

    assert pending_response[0]["node_id"] == node_id
    assert telemetry_response is telemetry

    payloads = _node_event_payloads(bus, mod._MODULAR_NODE_READ_SOURCE_AGENT)
    assert len(payloads) == 2
    pending_payload = next(
        payload for payload in payloads if payload["operation"] == "list_pending_nodes"
    )
    telemetry_payload = next(
        payload for payload in payloads if payload["operation"] == "get_telemetry"
    )
    assert pending_payload["read_only"] is True
    assert pending_payload["control_action"] is False
    assert pending_payload["source_quality"] == "local_pending_node_read"
    assert pending_payload["result_summary"]["nodes_count"] == 1
    assert telemetry_payload["read_only"] is True
    assert telemetry_payload["source_quality"] == "local_node_telemetry_observed_state"
    assert telemetry_payload["node_lifecycle_evidence"]["telemetry_store"] == {
        "attempted": True,
        "committed": False,
        "read": True,
        "payloads_redacted": True,
    }
    assert telemetry_payload["result_summary"]["custom_metrics_count"] == 2

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user_id,
        mesh_id,
        node_id,
        "hardware-read-secret",
        "serial-read-secret",
        "telemetry-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_node_lifecycle_routes_publish_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-node-lifecycle-secret"
    mesh_id = "mesh-node-lifecycle-secret"
    node_id = "node-lifecycle-secret"
    bus = EventBus(str(tmp_path))
    http_request = _NodeEvidenceRequest(bus)
    captured = {}

    async def _resolve(_mesh_id, _user):
        return SimpleNamespace(owner_id=user_id)

    class _Provisioner:
        async def approve_node(self, **kwargs):
            captured["approve"] = kwargs
            return {"status": "approved", "node_id": kwargs["node_id"]}

        async def revoke_node(self, **kwargs):
            captured["revoke"] = kwargs
            return {"status": "revoked", "node_id": kwargs["node_id"]}

    def _add_reissue_token(mesh_id, token, payload):
        captured["reissue"] = {"mesh_id": mesh_id, "token": token, "payload": payload}

    monkeypatch.setattr(mod, "_resolve_mesh_for_user", _resolve)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner())
    monkeypatch.setattr("src.api.maas.registry.add_reissue_token", _add_reissue_token)
    monkeypatch.setattr(secrets, "token_urlsafe", lambda _n: "fixed-token-secret")
    user = UserContext(user_id=user_id, plan="starter")

    approve = await mod.approve_node(
        mesh_id,
        node_id,
        user,
        http_request=http_request,
    )
    revoke = await mod.revoke_node(
        mesh_id,
        node_id,
        user,
        reason="manual-secret-reason",
        http_request=http_request,
    )
    reissue = await mod.request_reissue(
        mesh_id,
        node_id,
        user,
        http_request=http_request,
    )

    assert approve["status"] == "approved"
    assert revoke["status"] == "revoked"
    assert reissue["reissue_token"] == "reissue_fixed-token-secret"

    payloads = _node_event_payloads(bus, mod._MODULAR_NODE_LIFECYCLE_SOURCE_AGENT)
    assert len(payloads) == 3
    approve_payload = next(
        payload for payload in payloads if payload["operation"] == "approve_node"
    )
    revoke_payload = next(
        payload for payload in payloads if payload["operation"] == "revoke_node"
    )
    reissue_payload = next(
        payload for payload in payloads if payload["operation"] == "request_reissue"
    )
    assert approve_payload["source_quality"] == "local_node_approval_control_action"
    assert revoke_payload["source_quality"] == "local_node_revocation_control_action"
    assert reissue_payload["source_quality"] == "local_reissue_token_created"
    assert approve_payload["node_lifecycle_evidence"]["registry_mutation"][
        "committed"
    ] is True
    assert revoke_payload["result_summary"]["reason_present"] is True
    assert reissue_payload["result_summary"]["token_present"] is True
    assert reissue_payload["node_lifecycle_evidence"][
        "credential_installation_confirmed"
    ] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user_id,
        mesh_id,
        node_id,
        "manual-secret-reason",
        "fixed-token-secret",
        "reissue_fixed-token-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def _build_maas_nodes_db(*, role: str, create_mesh: bool, owner_is_user: bool):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(
        id=f"user-{uuid.uuid4().hex[:8]}",
        email=f"user-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="$2b$12$fakehash" + "x" * 53,
        api_key=f"key-{uuid.uuid4().hex}",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    if create_mesh:
        db.add(
            MeshInstance(
                id=mesh_id,
                name="guard-test-mesh",
                owner_id=user.id if owner_is_user else "foreign-owner",
            )
        )
        db.commit()

    return db, user, mesh_id


def test_owner_or_admin_access_allows_admin_without_mesh_when_enabled():
    db, user, _ = _build_maas_nodes_db(role="admin", create_mesh=False, owner_is_user=False)
    try:
        mesh = _ensure_owner_or_admin_access(
            "mesh-missing",
            user,
            db,
            MeshPermission.TELEMETRY_READ,
            allow_admin_without_mesh=True,
        )
        assert mesh is None
    finally:
        db.close()


def test_owner_or_admin_access_raises_404_for_operator_when_mesh_missing():
    db, user, _ = _build_maas_nodes_db(role="operator", create_mesh=False, owner_is_user=False)
    try:
        with pytest.raises(HTTPException) as exc:
            _ensure_owner_or_admin_access(
                "mesh-missing",
                user,
                db,
                MeshPermission.TELEMETRY_READ,
                allow_admin_without_mesh=True,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()


def test_owner_or_admin_access_hides_foreign_mesh_from_operator():
    db, user, mesh_id = _build_maas_nodes_db(role="operator", create_mesh=True, owner_is_user=False)
    try:
        with pytest.raises(HTTPException) as exc:
            _ensure_owner_or_admin_access(mesh_id, user, db, MeshPermission.ACL_READ)
        assert exc.value.status_code == 404
    finally:
        db.close()


def test_owner_or_admin_access_allows_owner_operator():
    db, user, mesh_id = _build_maas_nodes_db(role="operator", create_mesh=True, owner_is_user=True)
    try:
        mesh = _ensure_owner_or_admin_access(mesh_id, user, db, MeshPermission.TELEMETRY_READ)
        assert mesh is not None
        assert mesh.id == mesh_id
    finally:
        db.close()
