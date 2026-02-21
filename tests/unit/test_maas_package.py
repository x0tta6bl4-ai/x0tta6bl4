"""
Unit tests for src/api/maas package decomposition.

This suite validates the new package-level contracts:
- constants
- models
- mesh_instance
- registry
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.maas import constants as maas_constants
from src.api.maas import models as maas_models
from src.api.maas.mesh_instance import MeshInstance
from src.api.maas.registry import (
    add_mapek_event,
    add_mesh_policy,
    add_pending_node,
    add_reissue_token,
    audit_sync,
    find_mesh_for_node,
    get_audit_log,
    get_mapek_events,
    get_mesh,
    get_mesh_policies,
    get_node_telemetry,
    get_pending_nodes,
    get_reissue_token,
    get_revoked_node,
    is_node_revoked,
    register_mesh,
    remove_pending_node,
    revoke_node,
    unregister_mesh,
    update_node_telemetry,
)


class TestConstants:
    def test_profiles_have_expected_device_classes(self):
        profiles = maas_constants.PQC_SEGMENT_PROFILES
        for key in ("sensor", "edge", "robot", "drone", "gateway", "server"):
            assert key in profiles

    def test_profile_shape(self):
        for profile in maas_constants.PQC_SEGMENT_PROFILES.values():
            assert "kem" in profile
            assert "sig" in profile
            assert "security_level" in profile

    def test_get_pqc_profile_fallback(self):
        fallback = maas_constants.get_pqc_profile("unknown-device")
        assert fallback == maas_constants.PQC_DEFAULT_PROFILE

    def test_plan_aliases_and_limits(self):
        assert maas_constants.PLAN_ALIASES["free"] == "starter"
        assert maas_constants.PLAN_ALIASES["pro"] == "pro"
        assert maas_constants.PLAN_REQUEST_LIMITS["enterprise"] > maas_constants.PLAN_REQUEST_LIMITS["starter"]

    def test_billing_webhook_events(self):
        assert "plan.upgraded" in maas_constants.BILLING_WEBHOOK_EVENTS
        assert "subscription.deleted" in maas_constants.BILLING_WEBHOOK_EVENTS


class TestModels:
    def test_mesh_deploy_request_defaults(self):
        req = maas_models.MeshDeployRequest(name="test-mesh")
        assert req.nodes == 5
        assert req.billing_plan == "starter"
        assert req.pqc_enabled is True

    def test_mesh_deploy_request_validates_plan(self):
        with pytest.raises(ValidationError):
            maas_models.MeshDeployRequest(name="test-mesh", billing_plan="invalid")

    def test_node_register_defaults(self):
        req = maas_models.NodeRegisterRequest(enrollment_token="x" * 32)
        assert req.device_class == "edge"
        assert req.labels == {}
        assert req.public_keys == {}

    def test_scale_request_accepts_expected_actions(self):
        up = maas_models.ScaleRequest(action="scale_up", count=2)
        down = maas_models.ScaleRequest(action="scale_down", count=1)
        assert up.action == "scale_up"
        assert down.action == "scale_down"

    def test_scale_request_rejects_invalid_action(self):
        with pytest.raises(ValidationError):
            maas_models.ScaleRequest(action="grow", count=2)


@pytest.mark.asyncio
class TestMeshInstance:
    async def test_provision_and_terminate(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        inst = MeshInstance(
            mesh_id=mesh_id,
            name="unit-test-mesh",
            owner_id="owner-1",
            nodes=3,
        )
        assert inst.status == "provisioning"

        await inst.provision()
        assert inst.status == "active"
        assert len(inst.node_instances) == 3

        await inst.terminate()
        assert inst.status == "terminated"
        assert len(inst.node_instances) == 0

    async def test_scale_and_metrics(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        inst = MeshInstance(
            mesh_id=mesh_id,
            name="scale-mesh",
            owner_id="owner-2",
            nodes=2,
            obfuscation="xor",
            traffic_profile="gaming",
        )
        await inst.provision()

        up_nodes = inst.scale("scale_up", 3)
        assert up_nodes == 5

        down_nodes = inst.scale("scale_down", 4)
        assert down_nodes >= 1

        c = inst.get_consciousness_metrics()
        assert "phi_ratio" in c
        assert "state" in c
        assert "nodes_total" in c

        m = inst.get_mape_k_state()
        assert "phase" in m
        assert "directives" in m

        n = inst.get_network_metrics()
        assert n["obfuscation_mode"] == "xor"
        assert n["traffic_profile"] == "gaming"


@pytest.mark.asyncio
class TestRegistry:
    async def test_register_get_unregister_mesh(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        inst = MeshInstance(
            mesh_id=mesh_id,
            name="registry-mesh",
            owner_id="owner-3",
            nodes=1,
        )
        register_mesh(inst)
        assert get_mesh(mesh_id) is inst
        assert unregister_mesh(mesh_id) is True
        assert get_mesh(mesh_id) is None

    async def test_pending_nodes_and_telemetry(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        node_id = f"node-{uuid4().hex[:6]}"

        add_pending_node(mesh_id, node_id, {"device_class": "edge"})
        pending = get_pending_nodes(mesh_id)
        assert node_id in pending

        removed = remove_pending_node(mesh_id, node_id)
        assert removed is not None
        assert node_id not in get_pending_nodes(mesh_id)

        update_node_telemetry(node_id, {"cpu": 10.0})
        telemetry = get_node_telemetry(node_id)
        assert telemetry is not None
        assert telemetry["cpu"] == 10.0

    async def test_policy_mapek_revocation_and_reissue_token(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        node_id = f"node-{uuid4().hex[:6]}"

        add_mesh_policy(mesh_id, {"id": "p1", "action": "allow"})
        policies = get_mesh_policies(mesh_id)
        assert len(policies) >= 1
        assert policies[-1]["id"] == "p1"

        add_mapek_event(mesh_id, {"event": "monitor"})
        events = get_mapek_events(mesh_id)
        assert len(events) >= 1
        assert events[-1]["event"] == "monitor"

        revoke_node(mesh_id, node_id, {"reason": "manual"})
        assert is_node_revoked(mesh_id, node_id) is True
        assert get_revoked_node(mesh_id, node_id)["reason"] == "manual"

        token = f"tok-{uuid4().hex[:10]}"
        add_reissue_token(mesh_id, token, {"node_id": node_id, "used": False})
        assert get_reissue_token(mesh_id, token)["node_id"] == node_id

    async def test_audit_log_and_find_mesh_for_node(self):
        mesh_id = f"mesh-{uuid4().hex[:8]}"
        node_id = f"node-{uuid4().hex[:6]}"
        inst = MeshInstance(
            mesh_id=mesh_id,
            name="audit-mesh",
            owner_id="owner-4",
            nodes=1,
        )
        register_mesh(inst)
        try:
            await inst.provision()
            # Ensure node exists for reverse lookup.
            inst.node_instances[node_id] = {"status": "healthy"}

            audit_sync(mesh_id, actor="test", event="deploy", details="ok")
            log = get_audit_log(mesh_id)
            assert len(log) >= 1
            assert log[-1]["event"] == "deploy"

            assert find_mesh_for_node(node_id) == mesh_id
        finally:
            unregister_mesh(mesh_id)
