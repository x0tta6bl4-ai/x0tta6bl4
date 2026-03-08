"""
Unit tests for src/api/maas/models.py — Pydantic validation constraints.

Focuses on required fields, regex patterns, length bounds, and default values.
No I/O, no network, no DB.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.maas.models import (
    ApiKeyRotateRequest,
    BillingWebhookRequest,
    LoginRequest,
    MeshDeployRequest,
    MeshScaleRequest,
    NodeHeartbeatRequest,
    NodeRegisterRequest,
    NodeRevokeRequest,
    NodeReissueTokenRequest,
    OIDCExchangeRequest,
    PolicyRequest,
    ScaleRequest,
    RegisterRequest,
)


# ---------------------------------------------------------------------------
# MeshDeployRequest
# ---------------------------------------------------------------------------

class TestMeshDeployRequest:
    def test_valid_minimal(self):
        m = MeshDeployRequest(name="test-mesh")
        assert m.name == "test-mesh"
        assert m.nodes == 5
        assert m.billing_plan == "starter"
        assert m.pqc_enabled is True
        assert m.obfuscation == "none"
        assert m.traffic_profile == "none"

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="ab")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="x" * 65)

    def test_nodes_must_be_at_least_1(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="valid-mesh", nodes=0)

    def test_nodes_max_1000(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="valid-mesh", nodes=1001)

    def test_billing_plan_enterprise(self):
        m = MeshDeployRequest(name="ent-mesh", billing_plan="enterprise")
        assert m.billing_plan == "enterprise"

    def test_billing_plan_invalid_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", billing_plan="free")

    def test_obfuscation_aes_valid(self):
        m = MeshDeployRequest(name="test-mesh", obfuscation="aes")
        assert m.obfuscation == "aes"

    def test_obfuscation_invalid_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", obfuscation="wireguard")

    def test_traffic_profile_gaming(self):
        m = MeshDeployRequest(name="test-mesh", traffic_profile="gaming")
        assert m.traffic_profile == "gaming"

    def test_traffic_profile_invalid_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", traffic_profile="latency_opt")

    def test_join_token_ttl_bounds(self):
        # 1 hour = 3600 minimum
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", join_token_ttl_sec=3599)
        # 30 days = 2592000 maximum
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", join_token_ttl_sec=2592001)

    def test_join_token_ttl_default(self):
        m = MeshDeployRequest(name="test-mesh")
        assert m.join_token_ttl_sec == 604800  # 7 days

    def test_optimization_mode_valid(self):
        for mode in ("standard", "ml_routing", "genetic_topo"):
            m = MeshDeployRequest(name="test-mesh", optimization_mode=mode)
            assert m.optimization_mode == mode

    def test_optimization_mode_invalid_raises(self):
        with pytest.raises(ValidationError):
            MeshDeployRequest(name="test-mesh", optimization_mode="quantum")


# ---------------------------------------------------------------------------
# ScaleRequest
# ---------------------------------------------------------------------------

class TestScaleRequest:
    def test_scale_up_valid(self):
        req = ScaleRequest(action="scale_up", count=3)
        assert req.action == "scale_up"
        assert req.count == 3

    def test_scale_down_valid(self):
        req = ScaleRequest(action="scale_down", count=1)
        assert req.action == "scale_down"

    def test_action_invalid_raises(self):
        with pytest.raises(ValidationError):
            ScaleRequest(action="nuke", count=1)

    def test_count_zero_raises(self):
        with pytest.raises(ValidationError):
            ScaleRequest(action="scale_up", count=0)

    def test_count_over_100_raises(self):
        with pytest.raises(ValidationError):
            ScaleRequest(action="scale_up", count=101)


# ---------------------------------------------------------------------------
# MeshScaleRequest
# ---------------------------------------------------------------------------

class TestMeshScaleRequest:
    def test_valid_target_count(self):
        req = MeshScaleRequest(target_count=5)
        assert req.target_count == 5

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            MeshScaleRequest(target_count=0)

    def test_over_1000_raises(self):
        with pytest.raises(ValidationError):
            MeshScaleRequest(target_count=1001)


# ---------------------------------------------------------------------------
# NodeRegisterRequest
# ---------------------------------------------------------------------------

class TestNodeRegisterRequest:
    def test_defaults(self):
        req = NodeRegisterRequest(node_id="node-1")
        assert req.device_class == "edge"
        assert req.enclave_enabled is False
        assert req.labels == {}
        assert req.capabilities == []

    def test_valid_device_classes(self):
        for dc in ("edge", "robot", "drone", "gateway", "sensor", "server"):
            req = NodeRegisterRequest(device_class=dc)
            assert req.device_class == dc

    def test_invalid_device_class_raises(self):
        with pytest.raises(ValidationError):
            NodeRegisterRequest(device_class="laptop")

    def test_enrollment_token_min_length(self):
        with pytest.raises(ValidationError):
            NodeRegisterRequest(enrollment_token="short")  # < 16 chars

    def test_enrollment_token_none_allowed(self):
        req = NodeRegisterRequest(enrollment_token=None)
        assert req.enrollment_token is None


# ---------------------------------------------------------------------------
# NodeRevokeRequest
# ---------------------------------------------------------------------------

class TestNodeRevokeRequest:
    def test_default_reason(self):
        req = NodeRevokeRequest()
        assert req.reason == "manual_revoke"

    def test_reason_too_short_raises(self):
        with pytest.raises(ValidationError):
            NodeRevokeRequest(reason="ab")

    def test_reason_too_long_raises(self):
        with pytest.raises(ValidationError):
            NodeRevokeRequest(reason="x" * 121)

    def test_custom_reason_accepted(self):
        req = NodeRevokeRequest(reason="policy_violation")
        assert req.reason == "policy_violation"


# ---------------------------------------------------------------------------
# NodeReissueTokenRequest
# ---------------------------------------------------------------------------

class TestNodeReissueTokenRequest:
    def test_default_ttl(self):
        req = NodeReissueTokenRequest()
        assert req.ttl_seconds == 900

    def test_min_ttl_60(self):
        with pytest.raises(ValidationError):
            NodeReissueTokenRequest(ttl_seconds=59)

    def test_max_ttl_86400(self):
        with pytest.raises(ValidationError):
            NodeReissueTokenRequest(ttl_seconds=86401)

    def test_valid_boundary_values(self):
        assert NodeReissueTokenRequest(ttl_seconds=60).ttl_seconds == 60
        assert NodeReissueTokenRequest(ttl_seconds=86400).ttl_seconds == 86400


# ---------------------------------------------------------------------------
# NodeHeartbeatRequest
# ---------------------------------------------------------------------------

class TestNodeHeartbeatRequest:
    def test_required_node_id(self):
        with pytest.raises(ValidationError):
            NodeHeartbeatRequest()  # node_id missing

    def test_defaults(self):
        req = NodeHeartbeatRequest(node_id="n-1")
        assert req.cpu_usage == 0.0
        assert req.memory_usage == 0.0
        assert req.neighbors_count == 0
        assert req.custom_metrics == {}

    def test_pheromones_optional(self):
        req = NodeHeartbeatRequest(
            node_id="n-1",
            pheromones={"food": {"n-2": 0.9}},
        )
        assert req.pheromones == {"food": {"n-2": 0.9}}


# ---------------------------------------------------------------------------
# PolicyRequest
# ---------------------------------------------------------------------------

class TestPolicyRequest:
    def test_allow_is_default(self):
        req = PolicyRequest(source_tag="robot", target_tag="gateway")
        assert req.action == "allow"

    def test_deny_action_valid(self):
        req = PolicyRequest(source_tag="sensor", target_tag="drone", action="deny")
        assert req.action == "deny"

    def test_invalid_action_raises(self):
        with pytest.raises(ValidationError):
            PolicyRequest(source_tag="s", target_tag="t", action="reject")

    def test_source_tag_required(self):
        with pytest.raises(ValidationError):
            PolicyRequest(target_tag="gateway")

    def test_target_tag_required(self):
        with pytest.raises(ValidationError):
            PolicyRequest(source_tag="robot")


# ---------------------------------------------------------------------------
# BillingWebhookRequest
# ---------------------------------------------------------------------------

class TestBillingWebhookRequest:
    def test_minimal_valid(self):
        req = BillingWebhookRequest(event_type="invoice.paid")
        assert req.event_type == "invoice.paid"
        assert req.plan is None
        assert req.metadata == {}

    def test_event_type_too_short_raises(self):
        with pytest.raises(ValidationError):
            BillingWebhookRequest(event_type="ab")

    def test_plan_pattern_valid(self):
        for plan in ("free", "starter", "pro", "enterprise"):
            req = BillingWebhookRequest(event_type="invoice.paid", plan=plan)
            assert req.plan == plan

    def test_plan_invalid_raises(self):
        with pytest.raises(ValidationError):
            BillingWebhookRequest(event_type="invoice.paid", plan="gold")

    def test_event_id_length_bounds(self):
        # Too short
        with pytest.raises(ValidationError):
            BillingWebhookRequest(event_type="invoice.paid", event_id="short")
        # At minimum
        req = BillingWebhookRequest(event_type="invoice.paid", event_id="evt_1234")
        assert len(req.event_id) >= 8

    def test_customer_id_min_length(self):
        with pytest.raises(ValidationError):
            BillingWebhookRequest(event_type="invoice.paid", customer_id="ab")


# ---------------------------------------------------------------------------
# OIDCExchangeRequest
# ---------------------------------------------------------------------------

class TestOIDCExchangeRequest:
    def test_valid_token(self):
        req = OIDCExchangeRequest(id_token="a" * 10)
        assert len(req.id_token) >= 10

    def test_too_short_raises(self):
        with pytest.raises(ValidationError):
            OIDCExchangeRequest(id_token="short")


# ---------------------------------------------------------------------------
# LoginRequest
# ---------------------------------------------------------------------------

class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(email="user@example.com", password="mysecretpass")
        assert req.email == "user@example.com"

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="short")

    def test_password_too_long_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="x" * 129)


# ---------------------------------------------------------------------------
# RegisterRequest
# ---------------------------------------------------------------------------

class TestRegisterRequest:
    def test_valid_with_name(self):
        req = RegisterRequest(email="a@b.com", password="validpass1", name="Alice")
        assert req.name == "Alice"

    def test_name_optional(self):
        req = RegisterRequest(email="a@b.com", password="validpass1")
        assert req.name is None

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="validpass1", name="x" * 129)


# ---------------------------------------------------------------------------
# ApiKeyRotateRequest
# ---------------------------------------------------------------------------

class TestApiKeyRotateRequest:
    def test_default_revoke_old_true(self):
        req = ApiKeyRotateRequest()
        assert req.revoke_old is True

    def test_revoke_old_false(self):
        req = ApiKeyRotateRequest(revoke_old=False)
        assert req.revoke_old is False
