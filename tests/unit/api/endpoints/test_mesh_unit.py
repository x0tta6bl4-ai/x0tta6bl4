"""Unit tests for src/api/maas/endpoints/mesh.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import mesh as mod
from src.api.maas.models import MeshDeployRequest, MeshScaleRequest
from src.api.maas.registry import _mesh_registry, _registry_lock


def _build_instance(mesh_id: str, owner_id: str, nodes: int) -> SimpleNamespace:
    now = datetime.utcnow()
    return SimpleNamespace(
        mesh_id=mesh_id,
        name="unit-mesh",
        owner_id=owner_id,
        plan="pro",
        status="active",
        join_token=f"token-{uuid.uuid4().hex}",
        join_token_expires_at=now + timedelta(hours=1),
        created_at=now,
        target_nodes=nodes,
        pqc_profile="edge",
        pqc_enabled=True,
        obfuscation="none",
        traffic_profile="none",
        region="global",
    )


class _Provisioner:
    def __init__(self, instance: SimpleNamespace):
        self._instance = instance

    async def provision_mesh(self, **_kwargs):
        return self._instance


@pytest.mark.asyncio
async def test_deploy_mesh_persists_mesh_instance_to_db(monkeypatch):
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    instance = _build_instance(mesh_id=mesh_id, owner_id="owner-1", nodes=7)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    # Bypass tenant quota enforcement for unit test
    from src.services.tenant_quota_service import TenantQuotaService
    monkeypatch.setattr(TenantQuotaService, "_get_tenant_plan", lambda self, tid: "enterprise")

    request = MeshDeployRequest(name="mesh-unit", nodes=7, billing_plan="pro")
    user = UserContext(user_id="owner-1", plan="pro")
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0

    response = await mod.deploy_mesh(request, user, db)

    db.add.assert_called_once()
    db.commit.assert_called_once()

    persisted = db.add.call_args.args[0]
    assert persisted.id == mesh_id
    assert persisted.owner_id == "owner-1"
    assert persisted.plan == "pro"
    assert persisted.nodes == 7
    assert persisted.pqc_profile == "edge"
    assert persisted.region == "global"

    assert response.mesh_id == mesh_id
    assert response.status == "active"
    assert response.join_config["enrollment_token"] == instance.join_token


def _make_user(user_id: str = "owner-1") -> UserContext:
    return UserContext(user_id=user_id, plan="pro")


def _build_instance_with_nodes(
    mesh_id: str,
    owner_id: str,
    node_statuses: List[str] | None = None,
) -> SimpleNamespace:
    """Build instance with optional node_instances dict."""
    inst = _build_instance(mesh_id=mesh_id, owner_id=owner_id, nodes=len(node_statuses or []))
    if node_statuses:
        inst.node_instances = {
            f"node-{i}": {"status": s} for i, s in enumerate(node_statuses)
        }
    else:
        inst.node_instances = {}
    return inst


# ---------------------------------------------------------------------------
# list_meshes
# ---------------------------------------------------------------------------

class TestListMeshes:
    @pytest.mark.asyncio
    async def test_returns_only_owner_meshes(self, monkeypatch):
        mid1 = f"mesh-{uuid.uuid4().hex[:8]}"
        mid2 = f"mesh-{uuid.uuid4().hex[:8]}"
        inst1 = _build_instance(mesh_id=mid1, owner_id="owner-1", nodes=2)
        inst2 = _build_instance(mesh_id=mid2, owner_id="owner-2", nodes=1)
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid1: inst1, mid2: inst2})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=False)

        assert len(result) == 1
        assert result[0].mesh_id == mid1

    @pytest.mark.asyncio
    async def test_excludes_terminated_by_default(self, monkeypatch):
        mid1 = f"mesh-{uuid.uuid4().hex[:8]}"
        mid2 = f"mesh-{uuid.uuid4().hex[:8]}"
        inst1 = _build_instance(mesh_id=mid1, owner_id="owner-1", nodes=2)
        inst2 = _build_instance(mesh_id=mid2, owner_id="owner-1", nodes=1)
        inst2.status = "terminated"
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid1: inst1, mid2: inst2})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=False)

        assert len(result) == 1
        assert result[0].mesh_id == mid1

    @pytest.mark.asyncio
    async def test_includes_terminated_when_flag_set(self, monkeypatch):
        mid1 = f"mesh-{uuid.uuid4().hex[:8]}"
        mid2 = f"mesh-{uuid.uuid4().hex[:8]}"
        inst1 = _build_instance(mesh_id=mid1, owner_id="owner-1", nodes=2)
        inst2 = _build_instance(mesh_id=mid2, owner_id="owner-1", nodes=1)
        inst2.status = "terminated"
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid1: inst1, mid2: inst2})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=True)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_owned_meshes(self, monkeypatch):
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {})

        result = await mod.list_meshes(user=_make_user("owner-x"), include_terminated=False)

        assert result == []

    @pytest.mark.asyncio
    async def test_response_shape(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy", "healthy"])
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid: inst})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=False)

        r = result[0]
        assert r.mesh_id == mid
        assert r.nodes_total == 2
        assert r.nodes_healthy == 2
        assert 0.0 <= r.health_score <= 1.0
        assert isinstance(r.peers, list)


# ---------------------------------------------------------------------------
# get_mesh_status
# ---------------------------------------------------------------------------

class TestGetMeshStatus:
    @pytest.mark.asyncio
    async def test_returns_status_for_owner(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy"])
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.mesh_id == mid
        assert result.status == "active"
        assert result.nodes_total == 1
        assert result.nodes_healthy == 1

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        with pytest.raises(HTTPException) as exc:
            await mod.get_mesh_status(mesh_id="missing-mesh", user=_make_user())

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_health_score_zero_with_no_nodes(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", [])
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.health_score == 0.0
        assert result.nodes_total == 0

    @pytest.mark.asyncio
    async def test_degraded_node_reduces_healthy_count(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy", "degraded", "healthy"])
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.nodes_total == 3
        assert result.nodes_healthy == 2

    @pytest.mark.asyncio
    async def test_uptime_seconds_non_negative(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", [])
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.uptime_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_custom_get_uptime_method_used(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", [])
        inst.get_uptime = lambda: 999.0
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.uptime_seconds == 999.0


# ---------------------------------------------------------------------------
# get_mesh_metrics
# ---------------------------------------------------------------------------

class TestGetMeshMetrics:
    @pytest.mark.asyncio
    async def test_returns_default_metrics_for_plain_instance(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=3)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_metrics(mesh_id=mid, user=_make_user("owner-1"))

        assert result.mesh_id == mid
        assert "phi_ratio" in result.consciousness
        assert "phase" in result.mape_k
        assert "nodes_active" in result.network
        assert result.timestamp  # non-empty string

    @pytest.mark.asyncio
    async def test_uses_get_consciousness_metrics_if_available(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=2)
        inst.get_consciousness_metrics = lambda: {"phi_ratio": 0.42, "state": "FLOW"}
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_metrics(mesh_id=mid, user=_make_user("owner-1"))

        assert result.consciousness == {"phi_ratio": 0.42, "state": "FLOW"}

    @pytest.mark.asyncio
    async def test_uses_get_mape_k_state_if_available(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=2)
        inst.get_mape_k_state = lambda: {"phase": "EXECUTE", "directives": {"scale": True}}
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_metrics(mesh_id=mid, user=_make_user("owner-1"))

        assert result.mape_k["phase"] == "EXECUTE"

    @pytest.mark.asyncio
    async def test_uses_get_network_metrics_if_available(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=2)
        inst.get_network_metrics = lambda: {"nodes_active": 5, "avg_latency_ms": 12.3}
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        result = await mod.get_mesh_metrics(mesh_id=mid, user=_make_user("owner-1"))

        assert result.network["avg_latency_ms"] == 12.3

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        with pytest.raises(HTTPException) as exc:
            await mod.get_mesh_metrics(mesh_id="ghost", user=_make_user())

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# scale_mesh
# ---------------------------------------------------------------------------

class TestScaleMesh:
    @pytest.mark.asyncio
    async def test_scale_returns_provisioner_result(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=3)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        scale_result = {"mesh_id": mid, "target_count": 5, "status": "scaling"}

        class _Prov:
            async def scale_mesh(self, mesh_id, target_count, actor):
                return scale_result

        monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())

        request = MeshScaleRequest(target_count=5)
        result = await mod.scale_mesh(mesh_id=mid, request=request, user=_make_user("owner-1"))

        assert result == scale_result

    @pytest.mark.asyncio
    async def test_scale_value_error_returns_400(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=3)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        class _Prov:
            async def scale_mesh(self, mesh_id, target_count, actor):
                raise ValueError("exceeds plan limit")

        monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())

        request = MeshScaleRequest(target_count=999)
        with pytest.raises(HTTPException) as exc:
            await mod.scale_mesh(mesh_id=mid, request=request, user=_make_user("owner-1"))

        assert exc.value.status_code == 400
        assert "exceeds plan limit" in exc.value.detail

    @pytest.mark.asyncio
    async def test_scale_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        request = MeshScaleRequest(target_count=3)
        with pytest.raises(HTTPException) as exc:
            await mod.scale_mesh(mesh_id="ghost", request=request, user=_make_user())

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# terminate_mesh
# ---------------------------------------------------------------------------

class TestTerminateMesh:
    @pytest.mark.asyncio
    async def test_terminate_returns_provisioner_result(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=2)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        term_result = {"mesh_id": mid, "status": "terminated", "actor": "owner-1"}

        class _Prov:
            async def terminate_mesh(self, mesh_id, actor, reason):
                return term_result

        monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())

        result = await mod.terminate_mesh(
            mesh_id=mid, user=_make_user("owner-1"), reason="user_request"
        )
        assert result["status"] == "terminated"

    @pytest.mark.asyncio
    async def test_terminate_value_error_returns_404(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=2)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        class _Prov:
            async def terminate_mesh(self, mesh_id, actor, reason):
                raise ValueError("mesh not found in provisioner")

        monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())

        with pytest.raises(HTTPException) as exc:
            await mod.terminate_mesh(mesh_id=mid, user=_make_user("owner-1"), reason="test")

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_terminate_passes_reason_to_provisioner(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)

        captured: Dict[str, Any] = {}

        class _Prov:
            async def terminate_mesh(self, mesh_id, actor, reason):
                captured["reason"] = reason
                return {"status": "terminated"}

        monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())

        await mod.terminate_mesh(
            mesh_id=mid, user=_make_user("owner-1"), reason="billing_suspend"
        )
        assert captured["reason"] == "billing_suspend"

    @pytest.mark.asyncio
    async def test_terminate_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        with pytest.raises(HTTPException) as exc:
            await mod.terminate_mesh(mesh_id="ghost", user=_make_user(), reason="test")

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# get_mesh_audit
# ---------------------------------------------------------------------------

class TestGetMeshAudit:
    @pytest.mark.asyncio
    async def test_returns_audit_log(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        log = [
            {"timestamp": "2026-03-08T10:00:00", "actor": "owner-1", "event": "deploy", "details": "ok"},
            {"timestamp": "2026-03-08T10:05:00", "actor": "owner-1", "event": "scale", "details": "ok"},
        ]
        monkeypatch.setattr(mod, "get_audit_log", lambda _id: log)

        result = await mod.get_mesh_audit(mesh_id=mid, user=_make_user("owner-1"), limit=100)

        assert result == log

    @pytest.mark.asyncio
    async def test_limit_trims_to_last_n_entries(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        log = [{"event": f"e{i}"} for i in range(10)]
        monkeypatch.setattr(mod, "get_audit_log", lambda _id: log)

        result = await mod.get_mesh_audit(mesh_id=mid, user=_make_user("owner-1"), limit=3)

        assert len(result) == 3
        assert result[0] == {"event": "e7"}
        assert result[-1] == {"event": "e9"}

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_audit_events(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "get_audit_log", lambda _id: [])

        result = await mod.get_mesh_audit(mesh_id=mid, user=_make_user("owner-1"), limit=100)

        assert result == []

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        with pytest.raises(HTTPException) as exc:
            await mod.get_mesh_audit(mesh_id="ghost", user=_make_user(), limit=100)

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# get_mesh_mapek
# ---------------------------------------------------------------------------

class TestGetMeshMapek:
    @pytest.mark.asyncio
    async def test_returns_mapek_events(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        events = [
            {"timestamp": "2026-03-08T10:00:00", "phase": "MONITOR", "metric": "cpu", "value": 0.3},
            {"timestamp": "2026-03-08T10:01:00", "phase": "ANALYZE", "anomaly": True},
        ]
        monkeypatch.setattr(mod, "get_mapek_events", lambda _id: events)

        result = await mod.get_mesh_mapek(mesh_id=mid, user=_make_user("owner-1"), limit=100)

        assert result == events

    @pytest.mark.asyncio
    async def test_limit_trims_to_last_n_entries(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        events = [{"phase": f"p{i}"} for i in range(20)]
        monkeypatch.setattr(mod, "get_mapek_events", lambda _id: events)

        result = await mod.get_mesh_mapek(mesh_id=mid, user=_make_user("owner-1"), limit=5)

        assert len(result) == 5
        assert result[0] == {"phase": "p15"}
        assert result[-1] == {"phase": "p19"}

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_events(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "get_mapek_events", lambda _id: [])

        result = await mod.get_mesh_mapek(mesh_id=mid, user=_make_user("owner-1"), limit=100)

        assert result == []

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_mesh(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
        monkeypatch.setattr(mod, "require_mesh_access", AsyncMock(return_value=None))

        with pytest.raises(HTTPException) as exc:
            await mod.get_mesh_mapek(mesh_id="ghost", user=_make_user(), limit=100)

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# _build_mesh_status_response helper
# ---------------------------------------------------------------------------

class TestBuildMeshStatusResponse:
    def test_health_score_clamped_to_unit_interval(self):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy"])
        inst.get_health_score = lambda: 5.0  # out-of-bounds

        result = mod._build_mesh_status_response(inst)

        assert result.health_score == 1.0

    def test_health_score_clamped_floor(self):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy"])
        inst.get_health_score = lambda: -1.0

        result = mod._build_mesh_status_response(inst)

        assert result.health_score == 0.0

    def test_peers_list_contains_node_ids(self):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy", "degraded"])

        result = mod._build_mesh_status_response(inst)

        node_ids = {p["node_id"] for p in result.peers}
        assert "node-0" in node_ids
        assert "node-1" in node_ids

    def test_peers_status_reflects_node_status(self):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy", "degraded"])

        result = mod._build_mesh_status_response(inst)

        statuses = {p["node_id"]: p["status"] for p in result.peers}
        assert statuses["node-0"] == "healthy"
        assert statuses["node-1"] == "degraded"


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deploy_mesh_db_failure_rolls_back_registry_and_returns_http_500(monkeypatch):
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    instance = _build_instance(mesh_id=mesh_id, owner_id="owner-2", nodes=3)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    async with _registry_lock:
        _mesh_registry[mesh_id] = instance

    from src.services.tenant_quota_service import TenantQuotaService
    monkeypatch.setattr(TenantQuotaService, "_get_tenant_plan", lambda self, tid: "enterprise")

    request = MeshDeployRequest(name="mesh-unit-fail", nodes=3, billing_plan="pro")
    user = UserContext(user_id="owner-2", plan="pro")
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    db.commit.side_effect = RuntimeError("db write failed")

    with pytest.raises(HTTPException) as exc:
        await mod.deploy_mesh(request, user, db)

    assert exc.value.status_code == 500
    assert "database persistence error" in str(exc.value.detail).lower()
    db.rollback.assert_called_once()

    async with _registry_lock:
        assert mesh_id not in _mesh_registry

