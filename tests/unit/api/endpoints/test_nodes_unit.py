"""Unit tests for src/api/maas/endpoints/nodes.py."""

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
from src.database import Base, MeshInstance, User


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
