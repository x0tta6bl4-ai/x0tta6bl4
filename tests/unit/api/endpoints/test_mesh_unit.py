"""Unit tests for src/api/maas/endpoints/mesh.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import mesh as mod
from src.api.maas.models import MeshDeployRequest, MeshScaleRequest
from src.api.maas.registry import _mesh_registry, _registry_lock
from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import event_trace_evidence_summary


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
        mesh_provisioner_claim_gate={
            "local_mesh_instance_lifecycle_claim_allowed": True,
            "local_node_seed_claim_allowed": True,
            "external_infrastructure_provisioning_claim_allowed": False,
            "node_dataplane_join_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "production_readiness_claim_allowed": False,
        },
        cross_plane_claim_gate={
            "surface": "maas_services.mesh_provisioner.provision_mesh",
            "allowed": False,
            "requested_claim_ids": ["production_readiness"],
        },
    )


class _Provisioner:
    def __init__(self, instance: SimpleNamespace):
        self._instance = instance

    async def provision_mesh(self, **_kwargs):
        return self._instance


class _MeshEvidenceRequest:
    def __init__(self, bus: EventBus):
        self.state = SimpleNamespace(event_bus=bus)


def _mesh_event_payloads(bus: EventBus, source_agent: str) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=20,
        )
    ]


@pytest.mark.asyncio
async def test_deploy_mesh_persists_mesh_instance_to_db(monkeypatch):
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    instance = _build_instance(mesh_id=mesh_id, owner_id="owner-1", nodes=7)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    request = MeshDeployRequest(name="mesh-unit", nodes=7, billing_plan="pro")
    user = UserContext(user_id="owner-1", plan="pro")
    db = MagicMock()

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
    assert response.mesh_deploy_claim_gate[
        "local_mesh_provisioner_invocation_claim_allowed"
    ] is True
    assert response.mesh_deploy_claim_gate[
        "external_node_deployment_claim_allowed"
    ] is False
    assert response.mesh_deploy_claim_gate[
        "dataplane_delivery_claim_allowed"
    ] is False
    assert response.mesh_provisioner_claim_gate[
        "local_mesh_instance_lifecycle_claim_allowed"
    ] is True
    assert response.provisioner_cross_plane_claim_gate[
        "surface"
    ] == "maas_services.mesh_provisioner.provision_mesh"
    assert response.cross_plane_claim_gate["surface"] == "maas_mesh.deploy"
    assert response.cross_plane_claim_gate["allowed"] is False


@pytest.mark.asyncio
async def test_deploy_mesh_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-mesh-deploy-secret"
    mesh_id = "mesh-deploy-secret"
    mesh_name = "mesh-name-deploy-secret"
    join_token = "join-token-deploy-secret"
    instance = _build_instance(mesh_id=mesh_id, owner_id=user_id, nodes=7)
    instance.name = mesh_name
    instance.join_token = join_token
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    bus = EventBus(str(tmp_path))
    http_request = _MeshEvidenceRequest(bus)
    request = MeshDeployRequest(name=mesh_name, nodes=7, billing_plan="pro")
    user = UserContext(user_id=user_id, plan="pro")
    db = MagicMock()

    response = await mod.deploy_mesh(request, user, db, http_request=http_request)

    assert response.mesh_id == mesh_id
    assert response.join_config["enrollment_token"] == join_token

    payloads = _mesh_event_payloads(bus, mod._MODULAR_MESH_DEPLOY_SOURCE_AGENT)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "deploy_mesh"
    assert payload["layer"] == "api_modular_mesh_deploy_control_action"
    assert payload["status"] == "success"
    assert payload["return_code"] == 201
    assert payload["source_quality"] == "local_mesh_deployment_recorded"
    assert payload["actor_user_id_hash"]
    assert payload["mesh_id_hash"]
    assert payload["owner_id_hash"]
    assert payload["result_summary"]["join_token_present"] is True
    assert payload["result_summary"]["mesh_name_present"] is True
    assert payload["result_summary"]["mesh_deploy_claim_gate_present"] is True
    assert payload["result_summary"]["mesh_provisioner_claim_gate_present"] is True
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert payload["result_summary"]["dataplane_delivery_claim_allowed"] is False
    assert (
        payload["result_summary"]["external_node_deployment_claim_allowed"] is False
    )
    assert payload["result_summary"]["production_readiness_claim_allowed"] is False
    lifecycle = payload["mesh_lifecycle_evidence"]
    assert lifecycle["dataplane_confirmed"] is False
    assert lifecycle["external_node_deployment_confirmed"] is False
    assert lifecycle["agent_enrollment_confirmed"] is False
    assert lifecycle["join_token_consumed"] is False
    assert lifecycle["db_write_evidence"]["committed"] is True
    assert lifecycle["registry_mutation"]["committed"] is True

    trace_summary = event_trace_evidence_summary(payload)
    assert trace_summary["runtime_evidence"]["present"] is True
    assert "mesh_lifecycle_evidence" in trace_summary["runtime_evidence"][
        "evidence_blocks_present"
    ]

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, mesh_id, mesh_name, join_token):
        assert raw_value not in serialized
        assert raw_value not in raw_log


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

        assert len(result["meshes"]) == 1
        assert result["meshes"][0].mesh_id == mid1

    @pytest.mark.asyncio
    async def test_excludes_terminated_by_default(self, monkeypatch):
        mid1 = f"mesh-{uuid.uuid4().hex[:8]}"
        mid2 = f"mesh-{uuid.uuid4().hex[:8]}"
        inst1 = _build_instance(mesh_id=mid1, owner_id="owner-1", nodes=2)
        inst2 = _build_instance(mesh_id=mid2, owner_id="owner-1", nodes=1)
        inst2.status = "terminated"
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid1: inst1, mid2: inst2})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=False)

        assert len(result["meshes"]) == 1
        assert result["meshes"][0].mesh_id == mid1

    @pytest.mark.asyncio
    async def test_includes_terminated_when_flag_set(self, monkeypatch):
        mid1 = f"mesh-{uuid.uuid4().hex[:8]}"
        mid2 = f"mesh-{uuid.uuid4().hex[:8]}"
        inst1 = _build_instance(mesh_id=mid1, owner_id="owner-1", nodes=2)
        inst2 = _build_instance(mesh_id=mid2, owner_id="owner-1", nodes=1)
        inst2.status = "terminated"
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid1: inst1, mid2: inst2})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=True)

        assert len(result["meshes"]) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_owned_meshes(self, monkeypatch):
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {})

        result = await mod.list_meshes(user=_make_user("owner-x"), include_terminated=False)

        assert result["meshes"] == []

    @pytest.mark.asyncio
    async def test_response_shape(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy", "healthy"])
        monkeypatch.setattr(mod, "get_all_meshes", lambda: {mid: inst})

        result = await mod.list_meshes(user=_make_user("owner-1"), include_terminated=False)

        r = result["meshes"][0]
        assert r.mesh_id == mid
        assert r.nodes_total == 2
        assert r.nodes_healthy == 2
        assert 0.0 <= r.health_score <= 1.0
        assert isinstance(r.peers, list)
        assert r.mesh_lifecycle_claim_gate[
            "local_mesh_registry_read_claim_allowed"
        ] is True
        assert (
            r.mesh_lifecycle_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert r.cross_plane_claim_gate["surface"] == "maas_mesh.list"
        assert r.cross_plane_claim_gate["allowed"] is False


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
        assert result.mesh_lifecycle_claim_gate[
            "local_mesh_status_observation_claim_allowed"
        ] is True
        assert (
            result.mesh_lifecycle_claim_gate[
                "external_node_deployment_claim_allowed"
            ]
            is False
        )
        assert result.cross_plane_claim_gate["surface"] == "maas_mesh.status"
        assert result.cross_plane_claim_gate["allowed"] is False

    @pytest.mark.asyncio
    async def test_status_includes_redacted_control_policy_evidence(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance_with_nodes(mid, "owner-1", ["healthy"])
        evidence = {
            "status": "available",
            "source_agents": ["core-mapek-loop"],
            "event_ids": ["event-1"],
            "events_total": 1,
            "mesh_metric_evidence_policy": {
                "decision_basis": "estimate_or_fallback_based",
                "redacted": True,
            },
            "redacted": True,
        }
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "_maas_control_policy_evidence", lambda: evidence)

        result = await mod.get_mesh_status(mesh_id=mid, user=_make_user("owner-1"))

        assert result.control_policy_evidence == evidence
        assert "10.0.0.1" not in str(result.control_policy_evidence)

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
        assert (
            result.mesh_metrics_claim_gate[
                "local_mesh_metrics_observation_claim_allowed"
            ]
            is True
        )
        assert (
            result.mesh_metrics_claim_gate["production_readiness_claim_allowed"]
            is False
        )
        assert (
            result.mesh_metrics_claim_gate["production_slo_claim_allowed"] is False
        )
        assert (
            result.mesh_metrics_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            result.mesh_metrics_claim_gate["external_dpi_bypass_claim_allowed"]
            is False
        )
        assert (
            result.mesh_metrics_claim_gate["settlement_finality_claim_allowed"]
            is False
        )
        assert result.cross_plane_claim_gate["surface"] == "maas_mesh.metrics"
        assert result.cross_plane_claim_gate["allowed"] is False
        assert result.timestamp  # non-empty string

    @pytest.mark.asyncio
    async def test_metrics_include_redacted_control_policy_evidence(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=3)
        evidence = {
            "status": "available",
            "source_agents": ["mesh-action-enforcer"],
            "event_ids": ["event-2"],
            "events_total": 1,
            "mesh_metric_evidence_policy": {
                "decision_basis": "dataplane_confirmed",
                "redacted": True,
            },
            "redacted": True,
        }
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "_maas_control_policy_evidence", lambda: evidence)

        result = await mod.get_mesh_metrics(mesh_id=mid, user=_make_user("owner-1"))

        assert result.control_policy_evidence == evidence
        assert "10.0.0.1" not in str(result.control_policy_evidence)

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

        assert result["mesh_id"] == scale_result["mesh_id"]
        assert result["target_count"] == scale_result["target_count"]
        assert result["status"] == scale_result["status"]
        assert result["mesh_lifecycle_claim_gate"][
            "local_mesh_control_action_claim_allowed"
        ] is True
        assert (
            result["mesh_lifecycle_claim_gate"][
                "external_infrastructure_convergence_claim_allowed"
            ]
            is False
        )
        assert result["cross_plane_claim_gate"]["surface"] == "maas_mesh.scale"
        assert result["cross_plane_claim_gate"]["allowed"] is False

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


@pytest.mark.asyncio
async def test_mesh_scale_and_terminate_publish_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-mesh-control-secret"
    mesh_id = "mesh-control-secret"
    reason = "manual-secret-reason"
    inst = _build_instance(mesh_id=mesh_id, owner_id=user_id, nodes=3)
    bus = EventBus(str(tmp_path))
    http_request = _MeshEvidenceRequest(bus)

    class _Prov:
        async def scale_mesh(self, mesh_id, target_count, actor):
            return {
                "mesh_id": mesh_id,
                "target_count": target_count,
                "status": "scaling",
                "actor": actor,
            }

        async def terminate_mesh(self, mesh_id, actor, reason):
            return {
                "mesh_id": mesh_id,
                "status": "terminated",
                "actor": actor,
                "reason": reason,
            }

    monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Prov())
    user = UserContext(user_id=user_id, plan="pro")

    scale_response = await mod.scale_mesh(
        mesh_id=mesh_id,
        request=MeshScaleRequest(target_count=5),
        user=user,
        http_request=http_request,
    )
    terminate_response = await mod.terminate_mesh(
        mesh_id=mesh_id,
        user=user,
        reason=reason,
        http_request=http_request,
    )

    assert scale_response["target_count"] == 5
    assert terminate_response["status"] == "terminated"
    assert scale_response["mesh_lifecycle_claim_gate"][
        "dataplane_delivery_claim_allowed"
    ] is False
    assert terminate_response["mesh_lifecycle_claim_gate"][
        "production_readiness_claim_allowed"
    ] is False

    scale_payloads = _mesh_event_payloads(bus, mod._MODULAR_MESH_SCALE_SOURCE_AGENT)
    terminate_payloads = _mesh_event_payloads(
        bus,
        mod._MODULAR_MESH_TERMINATE_SOURCE_AGENT,
    )
    assert len(scale_payloads) == 1
    assert len(terminate_payloads) == 1

    scale_payload = scale_payloads[0]
    terminate_payload = terminate_payloads[0]
    assert scale_payload["operation"] == "scale_mesh"
    assert scale_payload["source_quality"] == "local_mesh_scale_control_action"
    assert scale_payload["target_nodes"] == 5
    assert scale_payload["mesh_lifecycle_evidence"]["registry_mutation"][
        "committed"
    ] is True
    assert scale_payload["mesh_lifecycle_evidence"][
        "durable_infrastructure_convergence_confirmed"
    ] is False
    assert scale_payload["result_summary"]["mesh_lifecycle_claim_gate_present"] is True
    assert scale_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert scale_payload["result_summary"]["dataplane_delivery_claim_allowed"] is False
    assert (
        scale_payload["result_summary"][
            "external_node_deployment_claim_allowed"
        ]
        is False
    )
    assert terminate_payload["operation"] == "terminate_mesh"
    assert terminate_payload["source_quality"] == "local_mesh_terminate_control_action"
    assert terminate_payload["result_summary"]["reason_present"] is True
    assert (
        terminate_payload["result_summary"]["mesh_lifecycle_claim_gate_present"]
        is True
    )
    assert (
        terminate_payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert terminate_payload["mesh_lifecycle_evidence"][
        "external_node_deployment_confirmed"
    ] is False
    assert terminate_payload["mesh_lifecycle_evidence"][
        "mapek_remediation_confirmed"
    ] is False

    serialized = json.dumps(scale_payloads + terminate_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, mesh_id, reason):
        assert raw_value not in serialized
        assert raw_value not in raw_log


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
    async def test_audit_sets_claim_boundary_headers(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "get_audit_log", lambda _id: [])
        http_response = Response()

        result = await mod.get_mesh_audit(
            mesh_id=mid,
            user=_make_user("owner-1"),
            limit=100,
            http_response=http_response,
        )

        assert result == []
        assert (
            http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
            == "x0tta6bl4.maas_mesh_read_list_claim_boundary_headers.v1"
        )
        assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == "maas_mesh.audit"
        assert (
            http_response.headers[
                "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"
            ]
            == "false"
        )
        assert (
            http_response.headers[
                "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
            ]
            == "false"
        )

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
    async def test_mapek_sets_claim_boundary_headers(self, monkeypatch):
        mid = f"mesh-{uuid.uuid4().hex[:8]}"
        inst = _build_instance(mesh_id=mid, owner_id="owner-1", nodes=1)
        monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
        monkeypatch.setattr(mod, "get_mapek_events", lambda _id: [])
        http_response = Response()

        result = await mod.get_mesh_mapek(
            mesh_id=mid,
            user=_make_user("owner-1"),
            limit=100,
            http_response=http_response,
        )

        assert result == []
        assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == "maas_mesh.mapek"
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


@pytest.mark.asyncio
async def test_mesh_read_routes_publish_redacted_observed_state_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "owner-mesh-read-secret"
    mesh_id = "mesh-read-secret"
    node_id = "node-read-secret"
    mesh_name = "mesh-name-read-secret"
    inst = _build_instance(mesh_id=mesh_id, owner_id=user_id, nodes=1)
    inst.name = mesh_name
    inst.node_instances = {node_id: {"status": "healthy"}}
    evidence = {
        "status": "available",
        "source_agents": ["control-policy-agent-secret"],
        "event_ids": ["control-policy-event-secret"],
        "events_total": 1,
        "mesh_metric_evidence_policy": {
            "decision_basis": "estimate_or_fallback_based",
            "redacted": True,
        },
        "redacted": True,
    }
    audit_log = [
        {
            "timestamp": "2026-03-08T10:00:00",
            "actor": user_id,
            "event": "deploy",
            "details": "audit-detail-secret",
        }
    ]
    mapek_events = [
        {
            "timestamp": "2026-03-08T10:01:00",
            "phase": "ANALYZE",
            "node_id": node_id,
            "metric": "metric-secret",
            "cpu": 0.75,
        }
    ]
    bus = EventBus(str(tmp_path))
    http_request = _MeshEvidenceRequest(bus)

    monkeypatch.setattr(mod, "get_all_meshes", lambda: {mesh_id: inst})
    monkeypatch.setattr(mod, "get_mesh", lambda _id: inst)
    monkeypatch.setattr(mod, "_maas_control_policy_evidence", lambda: evidence)
    monkeypatch.setattr(mod, "get_audit_log", lambda _id: audit_log)
    monkeypatch.setattr(mod, "get_mapek_events", lambda _id: mapek_events)
    user = UserContext(user_id=user_id, plan="pro")

    listed = await mod.list_meshes(
        user=user,
        include_terminated=False,
        http_request=http_request,
    )
    status_response = await mod.get_mesh_status(
        mesh_id=mesh_id,
        user=user,
        http_request=http_request,
    )
    metrics_response = await mod.get_mesh_metrics(
        mesh_id=mesh_id,
        user=user,
        http_request=http_request,
    )
    audit_response = await mod.get_mesh_audit(
        mesh_id=mesh_id,
        user=user,
        limit=100,
        http_request=http_request,
    )
    mapek_response = await mod.get_mesh_mapek(
        mesh_id=mesh_id,
        user=user,
        limit=100,
        http_request=http_request,
    )

    assert listed["meshes"][0].mesh_id == mesh_id
    assert status_response.control_policy_evidence == evidence
    assert listed["meshes"][0].mesh_lifecycle_claim_gate[
        "local_mesh_registry_read_claim_allowed"
    ] is True
    assert status_response.mesh_lifecycle_claim_gate[
        "local_mesh_status_observation_claim_allowed"
    ] is True
    assert metrics_response.control_policy_evidence == evidence
    assert audit_response == audit_log
    assert mapek_response == mapek_events

    payloads = _mesh_event_payloads(bus, mod._MODULAR_MESH_READ_SOURCE_AGENT)
    assert {payload["operation"] for payload in payloads} == {
        "get_mesh_audit",
        "get_mesh_mapek",
        "get_mesh_metrics",
        "get_mesh_status",
        "list_meshes",
    }
    assert all(payload["read_only"] is True for payload in payloads)
    assert all(payload["control_action"] is False for payload in payloads)

    status_payload = next(
        payload for payload in payloads if payload["operation"] == "get_mesh_status"
    )
    audit_payload = next(
        payload for payload in payloads if payload["operation"] == "get_mesh_audit"
    )
    mapek_payload = next(
        payload for payload in payloads if payload["operation"] == "get_mesh_mapek"
    )
    assert status_payload["source_quality"] == "local_mesh_status_observed_state"
    assert (
        status_payload["result_summary"]["mesh_lifecycle_claim_gate_present"]
        is True
    )
    assert status_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        status_payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    list_payload = next(
        payload for payload in payloads if payload["operation"] == "list_meshes"
    )
    assert list_payload["result_summary"]["mesh_lifecycle_claim_gate_count"] == 1
    assert list_payload["result_summary"]["cross_plane_claim_gate_count"] == 1
    assert status_payload["control_policy_evidence_summary"] == {
        "present": True,
        "status": "available",
        "events_total": 1,
        "source_agents_count": 1,
        "event_ids_count": 1,
        "decision_basis": "estimate_or_fallback_based",
        "redacted": True,
        "payloads_redacted": True,
    }
    metrics_payload = next(
        payload for payload in payloads if payload["operation"] == "get_mesh_metrics"
    )
    assert metrics_payload["result_summary"]["mesh_metrics_claim_gate_present"] is True
    assert metrics_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        metrics_payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert (
        metrics_payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    assert (
        metrics_payload["result_summary"]["external_dpi_bypass_claim_allowed"]
        is False
    )
    assert audit_payload["result_summary"]["event_counts"] == {"deploy": 1}
    assert (
        audit_payload["result_summary"][
            "mesh_read_list_claim_boundary_headers_present"
        ]
        is True
    )
    assert audit_payload["result_summary"]["claim_surface"] == "maas_mesh.audit"
    assert (
        audit_payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    assert (
        audit_payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert mapek_payload["result_summary"]["phase_counts"] == {"ANALYZE": 1}
    assert mapek_payload["result_summary"]["known_metric_mentions"] == 1
    assert (
        mapek_payload["result_summary"][
            "mesh_read_list_claim_boundary_headers_present"
        ]
        is True
    )
    assert mapek_payload["result_summary"]["claim_surface"] == "maas_mesh.mapek"
    assert (
        mapek_payload["result_summary"][
            "autonomous_remediation_completion_claim_allowed"
        ]
        is False
    )
    assert (
        mapek_payload["result_summary"]["restored_dataplane_claim_allowed"]
        is False
    )

    trace_summary = event_trace_evidence_summary(status_payload)
    assert "mesh_lifecycle_evidence" in trace_summary["runtime_evidence"][
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
        mesh_name,
        "audit-detail-secret",
        "metric-secret",
        "control-policy-agent-secret",
        "control-policy-event-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


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
        assert result.mesh_lifecycle_claim_gate[
            "production_readiness_claim_allowed"
        ] is False

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

    request = MeshDeployRequest(name="mesh-unit-fail", nodes=3, billing_plan="pro")
    user = UserContext(user_id="owner-2", plan="pro")
    db = MagicMock()
    db.commit.side_effect = RuntimeError("db write failed")

    with pytest.raises(HTTPException) as exc:
        await mod.deploy_mesh(request, user, db)

    assert exc.value.status_code == 500
    assert "database persistence error" in str(exc.value.detail).lower()
    db.rollback.assert_called_once()

    async with _registry_lock:
        assert mesh_id not in _mesh_registry
