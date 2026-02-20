"""Unit tests for src/api/maas.py — MaaS endpoint.

Updated for v3.3.0 with lifecycle endpoints (status, scale, metrics, terminate).
"""

from __future__ import annotations

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(plan: str = "pro", api_key: str = "test-key-0123456789ab", user_id: str = "test-user-1"):
    user = MagicMock()
    user.plan = plan
    user.api_key = api_key
    user.id = user_id
    user.email = "test@example.com"
    user.company = "TestCo"
    user.full_name = "Test User"
    user.requests_count = 0
    user.requests_limit = 1000
    return user


# ---------------------------------------------------------------------------
# MeshProvisioner
# ---------------------------------------------------------------------------

class TestMeshProvisioner:
    @pytest.mark.asyncio
    async def test_create_returns_mesh_instance(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        instance = await prov.create(name="test", nodes=3)
        assert instance.mesh_id.startswith("mesh-")
        assert len(instance.mesh_id) == 13  # "mesh-" + 8 hex chars
        assert instance.status == "active"
        assert len(instance.node_instances) == 3

    @pytest.mark.asyncio
    async def test_create_with_user_object(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        user = _mock_user()
        instance = await prov.create(user=user, name="test", nodes=2)
        assert instance.owner_id == user.id
        assert instance.mesh_id.startswith("mesh-")

    @pytest.mark.asyncio
    async def test_create_with_pqc_disabled(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        instance = await prov.create(name="test", nodes=1, pqc_enabled=False)
        assert instance.mesh_id.startswith("mesh-")
        assert instance.pqc_enabled is False

    @pytest.mark.asyncio
    async def test_terminate_removes_instance(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        instance = await prov.create(name="test", nodes=2)
        mesh_id = instance.mesh_id
        assert prov.get(mesh_id) is not None
        terminated = await prov.terminate(mesh_id)
        assert terminated is True
        assert prov.get(mesh_id) is None

    @pytest.mark.asyncio
    async def test_terminate_nonexistent_returns_false(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        terminated = await prov.terminate("mesh-nonexistent")
        assert terminated is False

    @pytest.mark.asyncio
    async def test_list_for_owner(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        await prov.create(name="m1", nodes=1, owner_id="owner-1")
        await prov.create(name="m2", nodes=1, owner_id="owner-1")
        await prov.create(name="m3", nodes=1, owner_id="owner-2")
        meshes = prov.list_for_owner("owner-1")
        assert len(meshes) >= 2


# ---------------------------------------------------------------------------
# MeshInstance — lifecycle & metrics
# ---------------------------------------------------------------------------

class TestMeshInstance:
    @pytest.mark.asyncio
    async def test_scale_up(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 3)
        await instance.provision()
        assert len(instance.node_instances) == 3
        new_total = instance.scale("scale_up", 2)
        assert new_total == 5

    @pytest.mark.asyncio
    async def test_scale_down_keeps_minimum_one(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 2)
        await instance.provision()
        new_total = instance.scale("scale_down", 10)  # Try removing more than exist
        assert new_total >= 1

    @pytest.mark.asyncio
    async def test_health_score_all_healthy(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 5)
        await instance.provision()
        assert instance.get_health_score() == 1.0

    @pytest.mark.asyncio
    async def test_health_score_empty(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 0)
        await instance.provision()
        assert instance.get_health_score() == 0.0

    @pytest.mark.asyncio
    async def test_consciousness_metrics(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 5)
        await instance.provision()
        metrics = instance.get_consciousness_metrics()
        assert "phi_ratio" in metrics
        assert "entropy" in metrics
        assert "harmony" in metrics
        assert "state" in metrics
        assert metrics["state"] == "TRANSCENDENT"

    @pytest.mark.asyncio
    async def test_mape_k_state(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 5)
        await instance.provision()
        state = instance.get_mape_k_state()
        assert state["phase"] == "MONITOR"
        assert "directives" in state
        assert state["directives"]["self_healing_aggressiveness"] == "low"

    @pytest.mark.asyncio
    async def test_terminate(self):
        from src.api.maas import MeshInstance
        instance = MeshInstance("mesh-test", "test", "owner", 3)
        await instance.provision()
        assert instance.status == "active"
        await instance.terminate()
        assert instance.status == "terminated"
        assert len(instance.node_instances) == 0


# ---------------------------------------------------------------------------
# BillingService
# ---------------------------------------------------------------------------

class TestBillingService:
    def test_check_quota_within_limit(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="pro")
        assert svc.check_quota(user, 500, requested_plan="pro") is True

    def test_check_quota_exceeds_limit(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="starter")
        with pytest.raises(Exception, match="Quota exceeded"):
            svc.check_quota(user, 100, requested_plan="starter")

    def test_check_quota_enterprise(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="enterprise")
        assert svc.check_quota(user, 5000, requested_plan="enterprise") is True

    def test_check_quota_unknown_plan_defaults_to_starter(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="custom")
        with pytest.raises(Exception, match="Quota exceeded"):
            svc.check_quota(user, 30, requested_plan="starter")

    def test_plan_escalation_blocked(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="starter")
        with pytest.raises(Exception, match="Plan escalation blocked"):
            svc.check_quota(user, 1, requested_plan="enterprise")


# ---------------------------------------------------------------------------
# validate_customer
# ---------------------------------------------------------------------------

class TestValidateCustomer:
    def test_valid_api_key(self):
        from src.api.maas import validate_customer
        user = _mock_user()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        result = validate_customer("test-key-0123456789ab", db)
        assert result is user

    def test_invalid_api_key_raises_401(self):
        from src.api.maas import validate_customer
        from fastapi import HTTPException
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            validate_customer("bad-key-0123456789xx", db)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# MeshDeployRequest validation
# ---------------------------------------------------------------------------

class TestMeshDeployRequest:
    def test_valid_request(self):
        from src.api.maas import MeshDeployRequest
        req = MeshDeployRequest(
            name="my-mesh",
            nodes=10,
            billing_plan="pro",
        )
        assert req.name == "my-mesh"
        assert req.nodes == 10
        assert req.pqc_enabled is True

    def test_name_too_short(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="ab")

    def test_nodes_below_minimum(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test", nodes=0)

    def test_invalid_billing_plan(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test", billing_plan="invalid")

    def test_obfuscation_modes(self):
        from src.api.maas import MeshDeployRequest
        req = MeshDeployRequest(name="test", obfuscation="xor")
        assert req.obfuscation == "xor"

    def test_traffic_profiles(self):
        from src.api.maas import MeshDeployRequest
        req = MeshDeployRequest(name="test", traffic_profile="gaming")
        assert req.traffic_profile == "gaming"


# ---------------------------------------------------------------------------
# deploy_mesh endpoint
# ---------------------------------------------------------------------------

class TestDeployMeshEndpoint:
    @pytest.mark.asyncio
    async def test_deploy_success(self):
        from src.api.maas import deploy_mesh, MeshDeployRequest
        req = MeshDeployRequest(
            name="test-mesh",
            nodes=5,
            billing_plan="pro",
        )
        user = _mock_user(plan="pro")
        db = MagicMock()

        result = await deploy_mesh(req, user, db)

        assert result.mesh_id.startswith("mesh-")
        assert result.status == "active"
        assert "token" in result.join_config
        assert len(result.join_config["token"]) > 20

    @pytest.mark.asyncio
    async def test_deploy_quota_exceeded(self):
        from src.api.maas import deploy_mesh, MeshDeployRequest
        from fastapi import HTTPException
        req = MeshDeployRequest(
            name="test-mesh",
            nodes=100,
            billing_plan="pro",
        )
        user = _mock_user(plan="free")
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await deploy_mesh(req, user, db)
        assert exc_info.value.status_code == 402


# ---------------------------------------------------------------------------
# Security: join_config token is cryptographically random
# ---------------------------------------------------------------------------

class TestSecurityJoinToken:
    @pytest.mark.asyncio
    async def test_join_token_is_unique_per_call(self):
        from src.api.maas import deploy_mesh, MeshDeployRequest
        req = MeshDeployRequest(
            name="test-mesh",
            nodes=1,
            billing_plan="pro",
        )
        user = _mock_user(plan="pro")
        db = MagicMock()

        r1 = await deploy_mesh(req, user, db)
        r2 = await deploy_mesh(req, user, db)

        assert r1.join_config["token"] != r2.join_config["token"]


class TestNodeApprovalFlow:
    @pytest.mark.asyncio
    async def test_register_and_approve_node(self):
        from src.api.maas import (MeshProvisioner, NodeApproveRequest,
                                  NodeRegisterRequest, approve_node,
                                  register_node)

        user = _mock_user(plan="pro")
        provisioner = MeshProvisioner()
        instance = await provisioner.create(user=user, name="approval-mesh", nodes=1)

        registration = await register_node(
            instance.mesh_id,
            NodeRegisterRequest(
                node_id="robot-edge-1",
                enrollment_token=instance.join_token,
                device_class="robot",
                labels={"zone": "a1"},
                public_keys={"sig_pub": "abc", "kem_pub": "def"},
            ),
        )
        assert registration.node_id == "robot-edge-1"
        assert registration.status == "pending_approval"

        approved = await approve_node(
            instance.mesh_id,
            registration.node_id,
            NodeApproveRequest(acl_profile="strict", tags=["robot", "warehouse"]),
            user,
        )
        assert approved.status == "approved"
        assert approved.join_token["token"]
        assert approved.join_token["signature"]

    @pytest.mark.asyncio
    async def test_approve_unknown_node_raises(self):
        from src.api.maas import MeshProvisioner, NodeApproveRequest, approve_node

        user = _mock_user(plan="pro")
        provisioner = MeshProvisioner()
        instance = await provisioner.create(user=user, name="approval-mesh", nodes=1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await approve_node(
                instance.mesh_id,
                "missing-node",
                NodeApproveRequest(),
                user,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_reissue_and_re_register(self):
        from fastapi import HTTPException
        from src.api.maas import (
            MeshProvisioner,
            NodeApproveRequest,
            NodeRegisterRequest,
            NodeReissueTokenRequest,
            NodeRevokeRequest,
            approve_node,
            register_node,
            reissue_node_token,
            revoke_node,
        )

        user = _mock_user(plan="pro")
        provisioner = MeshProvisioner()
        instance = await provisioner.create(user=user, name="revoke-mesh", nodes=1)

        await register_node(
            instance.mesh_id,
            NodeRegisterRequest(
                node_id="robot-007",
                enrollment_token=instance.join_token,
                device_class="robot",
            ),
        )
        await approve_node(
            instance.mesh_id,
            "robot-007",
            NodeApproveRequest(acl_profile="strict", tags=["robot"]),
            user,
        )

        revoked = await revoke_node(
            instance.mesh_id,
            "robot-007",
            NodeRevokeRequest(node_id="robot-007", reason="key_rotation"),
            user,
        )
        assert revoked.status == "revoked"

        reissued = await reissue_node_token(
            instance.mesh_id,
            "robot-007",
            NodeReissueTokenRequest(ttl_seconds=600),
            user,
        )
        assert reissued.join_token["token"]
        assert reissued.join_token["signature"]

        # Re-register with one-time reissue token.
        pending = await register_node(
            instance.mesh_id,
            NodeRegisterRequest(
                node_id="robot-007",
                enrollment_token=reissued.join_token["token"],
                device_class="robot",
            ),
        )
        assert pending.status == "pending_approval"

        # Token is one-time and must not be reusable.
        with pytest.raises(HTTPException) as exc_info:
            await register_node(
                instance.mesh_id,
                NodeRegisterRequest(
                    node_id="robot-007",
                    enrollment_token=reissued.join_token["token"],
                    device_class="robot",
                ),
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_node_config_applies_tag_acl(self):
        from src.api.maas import (
            MeshProvisioner,
            NodeApproveRequest,
            NodeRegisterRequest,
            PolicyRequest,
            approve_node,
            create_policy,
            get_node_config,
            register_node,
        )

        user = _mock_user(plan="pro")
        provisioner = MeshProvisioner()
        instance = await provisioner.create(user=user, name="acl-mesh", nodes=1)

        for node_id, device_class, tags in [
            ("robot-a", "robot", ["robot"]),
            ("server-a", "server", ["server"]),
            ("camera-a", "sensor", ["camera"]),
        ]:
            await register_node(
                instance.mesh_id,
                NodeRegisterRequest(
                    node_id=node_id,
                    enrollment_token=instance.join_token,
                    device_class=device_class,
                ),
            )
            await approve_node(
                instance.mesh_id,
                node_id,
                NodeApproveRequest(acl_profile="strict", tags=tags),
                user,
            )

        await create_policy(
            instance.mesh_id,
            PolicyRequest(source_tag="robot", target_tag="server", action="allow"),
            user,
        )
        await create_policy(
            instance.mesh_id,
            PolicyRequest(source_tag="robot", target_tag="camera", action="deny"),
            user,
        )

        config = get_node_config(instance.mesh_id, "robot-a")
        assert "server-a" in config["allowed_peers"]
        assert "camera-a" in config["denied_peers"]
        assert config["policy_decisions"]["server-a"]["action"] == "allow"
        assert config["policy_decisions"]["camera-a"]["action"] == "deny"


# ---------------------------------------------------------------------------
# MaaS Security Layer
# ---------------------------------------------------------------------------

class TestMaasSecurity:
    def test_api_key_generation(self):
        from src.api.maas_security import ApiKeyManager
        key = ApiKeyManager.generate()
        assert key.startswith("x0t_")
        assert len(key) >= 16

    def test_api_key_format_validation(self):
        from src.api.maas_security import ApiKeyManager
        assert ApiKeyManager.is_valid_format("x0t_abc123def456789") is True
        assert ApiKeyManager.is_valid_format("short") is False
        assert ApiKeyManager.is_valid_format("") is False

    def test_rate_limiter_allows_within_limits(self):
        from src.api.maas_security import RateLimiter
        limiter = RateLimiter(requests_per_minute=60, burst=10)
        for _ in range(10):
            assert limiter.check("test-key") is True

    def test_rate_limiter_blocks_excess(self):
        from src.api.maas_security import RateLimiter
        from fastapi import HTTPException
        limiter = RateLimiter(requests_per_minute=60, burst=3)
        for _ in range(3):
            limiter.check("test-key")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("test-key")
        assert exc_info.value.status_code == 429

    def test_token_signer_produces_signature(self):
        from src.api.maas_security import PQCTokenSigner
        signer = PQCTokenSigner()
        result = signer.sign_token("test-token", "mesh-123")
        assert "token" in result
        assert "algorithm" in result
        assert "signature" in result
