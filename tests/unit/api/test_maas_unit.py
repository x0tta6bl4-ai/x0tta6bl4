"""Unit tests for src/api/maas.py — MaaS endpoint."""

from __future__ import annotations

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(plan: str = "pro", api_key: str = "test-key-0123456789ab"):
    user = MagicMock()
    user.plan = plan
    user.api_key = api_key
    return user


# ---------------------------------------------------------------------------
# MeshProvisioner
# ---------------------------------------------------------------------------

class TestMeshProvisioner:
    def test_create_returns_mesh_id(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        mesh_id = prov.create(name="test", nodes=3)
        assert mesh_id.startswith("mesh-")
        assert len(mesh_id) == 13  # "mesh-" + 8 hex chars

    def test_create_with_pqc_disabled(self):
        from src.api.maas import MeshProvisioner
        prov = MeshProvisioner()
        mesh_id = prov.create(name="test", nodes=1, pqc_enabled=False)
        assert mesh_id.startswith("mesh-")


# ---------------------------------------------------------------------------
# BillingService
# ---------------------------------------------------------------------------

class TestBillingService:
    def test_check_quota_within_limit(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="pro")
        assert svc.check_quota(user, 50) is True

    def test_check_quota_exceeds_limit(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="free")
        with pytest.raises(Exception, match="Quota exceeded"):
            svc.check_quota(user, 10)

    def test_check_quota_enterprise(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="enterprise")
        assert svc.check_quota(user, 1000) is True

    def test_check_quota_unknown_plan_defaults_to_5(self):
        from src.api.maas import BillingService
        svc = BillingService()
        user = _mock_user(plan="custom")
        with pytest.raises(Exception, match="Quota exceeded"):
            svc.check_quota(user, 6)


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
            api_key="0123456789abcdef",
        )
        assert req.name == "my-mesh"
        assert req.nodes == 10

    def test_name_too_short(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="ab", api_key="0123456789abcdef")

    def test_nodes_below_minimum(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test", nodes=0, api_key="0123456789abcdef")

    def test_invalid_billing_plan(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test", billing_plan="invalid", api_key="0123456789abcdef")

    def test_api_key_too_short(self):
        from src.api.maas import MeshDeployRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test", api_key="short")


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
            api_key="0123456789abcdef",
        )
        user = _mock_user(plan="pro")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user

        result = await deploy_mesh(req, db)

        assert result["mesh_id"].startswith("mesh-")
        assert result["status"] == "provisioning"
        assert "token" in result["join_config"]
        assert len(result["join_config"]["token"]) > 20  # cryptographic token

    @pytest.mark.asyncio
    async def test_deploy_invalid_api_key(self):
        from src.api.maas import deploy_mesh, MeshDeployRequest
        from fastapi import HTTPException
        req = MeshDeployRequest(
            name="test-mesh",
            nodes=5,
            billing_plan="pro",
            api_key="0123456789abcdef",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await deploy_mesh(req, db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_deploy_quota_exceeded(self):
        from src.api.maas import deploy_mesh, MeshDeployRequest
        from fastapi import HTTPException
        req = MeshDeployRequest(
            name="test-mesh",
            nodes=100,
            billing_plan="pro",
            api_key="0123456789abcdef",
        )
        user = _mock_user(plan="free")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user

        with pytest.raises(HTTPException) as exc_info:
            await deploy_mesh(req, db)
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
            api_key="0123456789abcdef",
        )
        user = _mock_user(plan="pro")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user

        r1 = await deploy_mesh(req, db)
        r2 = await deploy_mesh(req, db)

        assert r1["join_config"]["token"] != r2["join_config"]["token"]
