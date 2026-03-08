"""
Unit tests for MeshProvisioner and UsageMeteringService in src/api/maas/services.py.

All tests use monkeypatching to avoid global registry state pollution.
No network, no DB, no disk I/O.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.maas.services import MeshProvisioner, UsageMeteringService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_billing_svc(max_nodes: int = 10) -> MagicMock:
    """Return a mock BillingService that allows up to max_nodes."""
    billing = MagicMock()
    billing.get_plan_limits.return_value = {
        "plan": "pro",
        "requests_per_minute": 500,
        "max_nodes": max_nodes,
        "max_meshes": 5,
    }
    return billing


def _make_instance(mesh_id: str = "mesh-test", nodes: int = 2) -> MagicMock:
    """Build a MeshInstance-like mock with provisioned nodes."""
    inst = MagicMock()
    inst.mesh_id = mesh_id
    inst.plan = "pro"
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(nodes)}
    inst.provision = AsyncMock()
    inst.terminate = AsyncMock()
    return inst


# ---------------------------------------------------------------------------
# MeshProvisioner — provision_mesh
# ---------------------------------------------------------------------------

class TestMeshProvisionerProvision:
    @pytest.mark.asyncio
    async def test_provision_returns_mesh_instance(self, monkeypatch):
        prov = MeshProvisioner(billing_service=_make_billing_svc())

        created = MagicMock()
        created.mesh_id = "mesh-abc"
        created.plan = "pro"
        created.join_token = None
        created.node_instances = {"n1": {}}
        created.provision = AsyncMock()

        with (
            patch("src.api.maas.services.MeshInstance", return_value=created),
            patch("src.api.maas.services.register_mesh"),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            result = await prov.provision_mesh(owner_id="u-1", node_count=2)

        assert result.mesh_id == "mesh-abc"

    @pytest.mark.asyncio
    async def test_provision_raises_when_node_count_exceeds_limit(self):
        billing = _make_billing_svc(max_nodes=3)
        prov = MeshProvisioner(billing_service=billing)

        with pytest.raises(ValueError, match="exceeds plan limit"):
            await prov.provision_mesh(owner_id="u-1", node_count=10)

    @pytest.mark.asyncio
    async def test_provision_calls_register_mesh(self, monkeypatch):
        prov = MeshProvisioner(billing_service=_make_billing_svc())

        created = MagicMock()
        created.mesh_id = "mesh-reg"
        created.plan = "pro"
        created.join_token = None
        created.node_instances = {}

        registry_calls = []
        created.provision = AsyncMock()

        with (
            patch("src.api.maas.services.MeshInstance", return_value=created),
            patch("src.api.maas.services.register_mesh", side_effect=lambda m: registry_calls.append(m)),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            await prov.provision_mesh(owner_id="u-1", node_count=2)

        assert len(registry_calls) == 1
        assert registry_calls[0].mesh_id == "mesh-reg"

    @pytest.mark.asyncio
    async def test_provision_records_audit_log(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        created = MagicMock()
        created.mesh_id = "mesh-audit"
        created.plan = "pro"
        created.join_token = None
        created.node_instances = {}

        audit_calls = []
        created.provision = AsyncMock()
        async def _fake_audit(mesh_id, actor, event, details):
            audit_calls.append((mesh_id, actor, event, details))

        with (
            patch("src.api.maas.services.MeshInstance", return_value=created),
            patch("src.api.maas.services.register_mesh"),
            patch("src.api.maas.services.record_audit_log", side_effect=_fake_audit),
        ):
            await prov.provision_mesh(owner_id="u-audit", node_count=2)

        assert any("mesh.provision" in call[2] for call in audit_calls)

    @pytest.mark.asyncio
    async def test_provision_uses_plan_alias(self):
        """Plan alias 'free' → 'starter' should be resolved before limit check."""
        billing = MagicMock()
        billing.get_plan_limits.return_value = {
            "plan": "starter",
            "requests_per_minute": 100,
            "max_nodes": 5,
            "max_meshes": 1,
        }
        prov = MeshProvisioner(billing_service=billing)

        created = MagicMock()
        created.mesh_id = "mesh-alias"
        created.plan = "starter"
        created.join_token = None
        created.node_instances = {}

        created.provision = AsyncMock()
        with (
            patch("src.api.maas.services.MeshInstance", return_value=created),
            patch("src.api.maas.services.register_mesh"),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            result = await prov.provision_mesh(owner_id="u-1", node_count=3, plan="free")

        assert result is created

    @pytest.mark.asyncio
    async def test_provision_records_metrics_when_provided(self):
        metrics = MagicMock()
        prov = MeshProvisioner(billing_service=_make_billing_svc(), metrics=metrics)

        created = MagicMock()
        created.mesh_id = "mesh-m"
        created.plan = "pro"
        created.join_token = None
        created.node_instances = {}

        created.provision = AsyncMock()
        with (
            patch("src.api.maas.services.MeshInstance", return_value=created),
            patch("src.api.maas.services.register_mesh"),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            await prov.provision_mesh(owner_id="u-m", node_count=2)

        metrics.record_meter.assert_called_once()
        call_args = metrics.record_meter.call_args
        assert call_args[0][0] == "mesh.provisioned"


# ---------------------------------------------------------------------------
# MeshProvisioner — scale_mesh
# ---------------------------------------------------------------------------

class TestMeshProvisionerScale:
    @pytest.mark.asyncio
    async def test_scale_up(self):
        billing = _make_billing_svc(max_nodes=20)
        prov = MeshProvisioner(billing_service=billing)
        inst = _make_instance("mesh-1", nodes=2)

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
            patch("src.api.maas.services.add_mapek_event"),
        ):
            result = await prov.scale_mesh("mesh-1", target_count=5, actor="u-1")

        assert result["action"] == "scale_up"
        inst.scale.assert_called_once_with("scale_up", 3)

    @pytest.mark.asyncio
    async def test_scale_down(self):
        billing = _make_billing_svc(max_nodes=20)
        prov = MeshProvisioner(billing_service=billing)
        inst = _make_instance("mesh-1", nodes=5)

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
            patch("src.api.maas.services.add_mapek_event"),
        ):
            result = await prov.scale_mesh("mesh-1", target_count=2, actor="u-1")

        assert result["action"] == "scale_down"
        inst.scale.assert_called_once_with("scale_down", 3)

    @pytest.mark.asyncio
    async def test_scale_no_change(self):
        billing = _make_billing_svc(max_nodes=20)
        prov = MeshProvisioner(billing_service=billing)
        inst = _make_instance("mesh-1", nodes=3)

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
            patch("src.api.maas.services.add_mapek_event"),
        ):
            result = await prov.scale_mesh("mesh-1", target_count=3, actor="u-1")

        assert result["action"] == "no_change"
        inst.scale.assert_not_called()

    @pytest.mark.asyncio
    async def test_scale_raises_when_mesh_not_found(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with patch("src.api.maas.services.get_mesh", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await prov.scale_mesh("ghost", target_count=3, actor="u-1")

    @pytest.mark.asyncio
    async def test_scale_raises_when_target_exceeds_plan_limit(self):
        billing = _make_billing_svc(max_nodes=5)
        prov = MeshProvisioner(billing_service=billing)
        inst = _make_instance("mesh-1", nodes=2)

        with patch("src.api.maas.services.get_mesh", return_value=inst):
            with pytest.raises(ValueError, match="exceeds plan limit"):
                await prov.scale_mesh("mesh-1", target_count=10, actor="u-1")

    @pytest.mark.asyncio
    async def test_scale_adds_mapek_event(self):
        billing = _make_billing_svc(max_nodes=20)
        prov = MeshProvisioner(billing_service=billing)
        inst = _make_instance("mesh-1", nodes=2)
        mapek_calls = []

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
            patch("src.api.maas.services.add_mapek_event", side_effect=lambda mid, ev: mapek_calls.append((mid, ev))),
        ):
            await prov.scale_mesh("mesh-1", target_count=4, actor="u-1")

        assert len(mapek_calls) == 1
        assert mapek_calls[0][0] == "mesh-1"
        assert mapek_calls[0][1]["type"] == "scale"


# ---------------------------------------------------------------------------
# MeshProvisioner — terminate_mesh
# ---------------------------------------------------------------------------

class TestMeshProvisionerTerminate:
    @pytest.mark.asyncio
    async def test_terminate_success(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        inst = _make_instance("mesh-term")

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.unregister_mesh") as unreg,
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            result = await prov.terminate_mesh("mesh-term", actor="u-1")

        inst.terminate.assert_awaited_once()
        unreg.assert_called_once_with("mesh-term")
        assert result["status"] == "terminated"
        assert result["mesh_id"] == "mesh-term"

    @pytest.mark.asyncio
    async def test_terminate_uses_custom_reason(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        inst = _make_instance("mesh-reason")

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.unregister_mesh"),
            patch("src.api.maas.services.record_audit_log", new=AsyncMock()),
        ):
            result = await prov.terminate_mesh("mesh-reason", actor="admin", reason="billing_lapse")

        assert result["reason"] == "billing_lapse"

    @pytest.mark.asyncio
    async def test_terminate_raises_when_mesh_not_found(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with patch("src.api.maas.services.get_mesh", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await prov.terminate_mesh("ghost", actor="u-1")


# ---------------------------------------------------------------------------
# MeshProvisioner — approve_node
# ---------------------------------------------------------------------------

class TestMeshProvisionerApproveNode:
    @pytest.mark.asyncio
    async def test_approve_node_success(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        inst = MagicMock()
        inst.add_node = MagicMock()

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.get_pending_nodes", return_value={"n-new": {"ip": "10.0.0.1"}}),
            patch("src.api.maas.services.is_node_revoked", return_value=False),
            patch("src.api.maas.services.remove_pending_node"),
            patch("src.api.maas.services.audit_sync"),
        ):
            result = await prov.approve_node("mesh-1", "n-new", actor="u-1")

        assert result["node_id"] == "n-new"
        assert result["status"] == "approved"
        inst.add_node.assert_called_once_with("n-new", {"ip": "10.0.0.1"})

    @pytest.mark.asyncio
    async def test_approve_node_raises_when_mesh_not_found(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with patch("src.api.maas.services.get_mesh", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await prov.approve_node("ghost", "n-1", actor="u-1")

    @pytest.mark.asyncio
    async def test_approve_node_raises_when_not_pending(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with (
            patch("src.api.maas.services.get_mesh", return_value=MagicMock()),
            patch("src.api.maas.services.get_pending_nodes", return_value={}),
        ):
            with pytest.raises(ValueError, match="not in pending"):
                await prov.approve_node("mesh-1", "n-ghost", actor="u-1")

    @pytest.mark.asyncio
    async def test_approve_node_raises_when_revoked(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with (
            patch("src.api.maas.services.get_mesh", return_value=MagicMock()),
            patch("src.api.maas.services.get_pending_nodes", return_value={"n-rev": {}}),
            patch("src.api.maas.services.is_node_revoked", return_value=True),
        ):
            with pytest.raises(ValueError, match="revoked"):
                await prov.approve_node("mesh-1", "n-rev", actor="u-1")


# ---------------------------------------------------------------------------
# MeshProvisioner — revoke_node
# ---------------------------------------------------------------------------

class TestMeshProvisionerRevokeNode:
    @pytest.mark.asyncio
    async def test_revoke_node_success(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        inst = MagicMock()
        inst.remove_node = MagicMock(return_value=True)

        with (
            patch("src.api.maas.services.get_mesh", return_value=inst),
            patch("src.api.maas.services.mark_node_revoked"),
            patch("src.api.maas.services.audit_sync"),
        ):
            result = await prov.revoke_node("mesh-1", "n-bad", actor="admin", reason="policy_violation")

        assert result["node_id"] == "n-bad"
        assert result["status"] == "revoked"
        assert result["reason"] == "policy_violation"
        inst.remove_node.assert_called_once_with("n-bad")

    @pytest.mark.asyncio
    async def test_revoke_node_raises_when_mesh_not_found(self):
        prov = MeshProvisioner(billing_service=_make_billing_svc())
        with patch("src.api.maas.services.get_mesh", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await prov.revoke_node("ghost", "n-1", actor="u-1", reason="test")


# ---------------------------------------------------------------------------
# UsageMeteringService
# ---------------------------------------------------------------------------

class TestUsageMeteringService:
    def test_record_request_increments_counter(self):
        svc = UsageMeteringService()
        svc.record_request("mesh-1", "/api/nodes", 12.5)
        svc.record_request("mesh-1", "/api/nodes", 8.0)
        report = svc.get_usage_report("mesh-1")
        assert report["requests"] == 2

    def test_record_bandwidth_accumulates(self):
        svc = UsageMeteringService()
        svc.record_bandwidth("mesh-1", bytes_in=1000, bytes_out=500)
        svc.record_bandwidth("mesh-1", bytes_in=200, bytes_out=300)
        report = svc.get_usage_report("mesh-1")
        assert report["bandwidth_bytes"] == 2000

    def test_record_storage_overwrites(self):
        svc = UsageMeteringService()
        svc.record_storage("mesh-1", bytes_used=1_000_000)
        svc.record_storage("mesh-1", bytes_used=2_000_000)
        report = svc.get_usage_report("mesh-1")
        assert report["storage_bytes"] == 2_000_000

    def test_reset_usage_zeros_counters(self):
        svc = UsageMeteringService()
        svc.record_request("mesh-1", "/x", 1.0)
        svc.record_bandwidth("mesh-1", 100, 200)
        svc.reset_usage("mesh-1")
        report = svc.get_usage_report("mesh-1")
        assert report["requests"] == 0
        assert report["bandwidth_bytes"] == 0

    def test_get_usage_report_contains_mesh_id(self):
        svc = UsageMeteringService()
        report = svc.get_usage_report("mesh-xyz")
        assert report["mesh_id"] == "mesh-xyz"
        assert "report_time" in report

    def test_separate_meshes_have_independent_counters(self):
        svc = UsageMeteringService()
        svc.record_request("mesh-a", "/x", 1.0)
        svc.record_request("mesh-a", "/x", 1.0)
        svc.record_request("mesh-b", "/x", 1.0)
        assert svc.get_usage_report("mesh-a")["requests"] == 2
        assert svc.get_usage_report("mesh-b")["requests"] == 1

    def test_record_request_calls_metrics_collector(self):
        metrics = MagicMock()
        svc = UsageMeteringService(metrics=metrics)
        svc.record_request("mesh-m", "/api/nodes", 5.0)
        assert metrics.record_meter.call_count == 2  # api.request + api.latency

    def test_record_bandwidth_calls_metrics_collector(self):
        metrics = MagicMock()
        svc = UsageMeteringService(metrics=metrics)
        svc.record_bandwidth("mesh-m", 1000, 500)
        metrics.record_meter.assert_called_once_with(
            "network.bandwidth", 1500, {"mesh_id": "mesh-m"}
        )

    def test_record_storage_calls_metrics_collector(self):
        metrics = MagicMock()
        svc = UsageMeteringService(metrics=metrics)
        svc.record_storage("mesh-m", 512)
        metrics.record_meter.assert_called_once_with(
            "storage.used", 512, {"mesh_id": "mesh-m"}
        )

    def test_is_within_limits_returns_true_initially(self):
        svc = UsageMeteringService()
        assert svc.is_within_limits("mesh-fresh", "pro") is True

    def test_is_within_limits_returns_false_after_quota_exceeded(self):
        svc = UsageMeteringService()
        # Override usage cache directly to simulate quota exhaustion
        from src.api.maas.constants import PLAN_REQUEST_LIMITS, PLAN_ALIASES
        plan = PLAN_ALIASES.get("pro", "pro")
        limit = PLAN_REQUEST_LIMITS.get(plan, 1000)
        svc._usage_cache["mesh-over"] = {"requests": limit, "bandwidth_bytes": 0, "storage_bytes": 0}
        assert svc.is_within_limits("mesh-over", "pro") is False

    def test_is_within_limits_resolves_plan_alias(self):
        """'free' plan alias → 'starter' limits are respected."""
        svc = UsageMeteringService()
        from src.api.maas.constants import PLAN_REQUEST_LIMITS, PLAN_ALIASES
        plan = PLAN_ALIASES.get("free", "free")
        limit = PLAN_REQUEST_LIMITS.get(plan, 1000)
        svc._usage_cache["mesh-free"] = {"requests": limit, "bandwidth_bytes": 0, "storage_bytes": 0}
        assert svc.is_within_limits("mesh-free", "free") is False

    def test_usage_report_zero_for_unknown_mesh(self):
        svc = UsageMeteringService()
        report = svc.get_usage_report("mesh-new")
        assert report["requests"] == 0
        assert report["bandwidth_bytes"] == 0
        assert report["storage_bytes"] == 0


# ---------------------------------------------------------------------------
# _SharedStateStore
# ---------------------------------------------------------------------------

from src.api.maas.services import _SharedStateStore


class TestSharedStateStore:
    def test_disabled_store_enabled_is_false(self):
        store = _SharedStateStore()
        assert store.enabled is False

    def test_disabled_store_get_json_returns_none(self):
        store = _SharedStateStore()
        assert store.get_json("any-key") is None

    def test_disabled_store_set_json_returns_false(self):
        store = _SharedStateStore()
        assert store.set_json("k", {"v": 1}) is False

    def test_disabled_store_delete_returns_false(self):
        store = _SharedStateStore()
        assert store.delete("k") is False

    def test_dict_redis_client_is_disabled(self):
        """Passing a plain dict as redis_client disables the store."""
        store = _SharedStateStore({})
        assert store.enabled is False

    def test_enabled_store_get_set_delete(self):
        redis = MagicMock()
        redis.get.return_value = '{"x": 42}'
        redis.set.return_value = True
        redis.delete.return_value = 1

        store = _SharedStateStore(redis)
        assert store.enabled is True

        result = store.get_json("k")
        assert result == {"x": 42}

        ok = store.set_json("k", {"x": 42})
        assert ok is True

        deleted = store.delete("k")
        assert deleted is True

    def test_enabled_store_setex_for_ttl(self):
        redis = MagicMock()
        spec_has_setex = hasattr(redis, "setex")
        redis.setex = MagicMock(return_value=True)

        store = _SharedStateStore(redis)
        store.set_json("k", {"v": 1}, ttl_seconds=60)
        redis.setex.assert_called_once()

    def test_enabled_store_bytes_decoded(self):
        redis = MagicMock()
        redis.get.return_value = b'{"decoded": true}'
        store = _SharedStateStore(redis)
        result = store.get_json("k")
        assert result == {"decoded": True}

    def test_enabled_store_get_json_returns_none_on_empty(self):
        redis = MagicMock()
        redis.get.return_value = None
        store = _SharedStateStore(redis)
        assert store.get_json("k") is None

    def test_enabled_store_suppresses_exception_on_get(self):
        redis = MagicMock()
        redis.get.side_effect = ConnectionError("redis down")
        store = _SharedStateStore(redis)
        assert store.get_json("k") is None

    def test_enabled_store_suppresses_exception_on_set(self):
        redis = MagicMock()
        redis.set.side_effect = ConnectionError("redis down")
        store = _SharedStateStore(redis)
        assert store.set_json("k", {"v": 1}) is False

    def test_enabled_store_suppresses_exception_on_delete(self):
        redis = MagicMock()
        redis.delete.side_effect = ConnectionError("redis down")
        store = _SharedStateStore(redis)
        assert store.delete("k") is False
