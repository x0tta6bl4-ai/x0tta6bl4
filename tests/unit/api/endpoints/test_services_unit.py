"""Unit tests for src/api/maas/services.py.

Covers: BillingService, MeshProvisioner, UsageMeteringService.
All tests run without Redis, real DB, or network access.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.api.maas.registry as reg
from src.api.maas.services import (
    BillingService,
    MeshProvisioner,
    UsageMeteringService,
    _SharedStateStore,
    _env_flag,
    _env_value,
)


# ---------------------------------------------------------------------------
# Registry isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    stores = [
        "_mesh_registry",
        "_pending_nodes",
        "_node_telemetry",
        "_mesh_policies",
        "_mesh_audit_log",
        "_mesh_mapek_events",
        "_revoked_nodes",
        "_mesh_reissue_tokens",
    ]
    for s in stores:
        getattr(reg, s).clear()
    yield
    for s in stores:
        getattr(reg, s).clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_billing(secret: str = "test-secret-key") -> BillingService:
    """BillingService with disabled shared state (no Redis)."""
    return BillingService(webhook_secret=secret, shared_state={})


def _sign(payload: bytes, secret: str, prefix: bool = True) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}" if prefix else digest


def _sign_ts(payload: bytes, secret: str, ts: Optional[int] = None) -> str:
    """Provider-style signature: t=<ts>,v1=<hex>."""
    ts = ts or int(time.time())
    message = f"{ts}.".encode() + payload
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


# ---------------------------------------------------------------------------
# _SharedStateStore
# ---------------------------------------------------------------------------


class TestSharedStateStore:
    def test_disabled_returns_none_on_get(self):
        store = _SharedStateStore()
        assert store.get_json("k") is None

    def test_disabled_set_returns_false(self):
        store = _SharedStateStore()
        assert store.set_json("k", {"x": 1}) is False

    def test_disabled_delete_returns_false(self):
        store = _SharedStateStore()
        assert store.delete("k") is False

    def test_enabled_with_mock_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"val": 42}'
        store = _SharedStateStore(mock_redis)
        assert store.enabled is True
        result = store.get_json("some_key")
        assert result == {"val": 42}

    def test_set_with_ttl_uses_setex(self):
        mock_redis = MagicMock()
        store = _SharedStateStore(mock_redis)
        store.set_json("k", {"a": 1}, ttl_seconds=300)
        mock_redis.setex.assert_called_once()

    def test_set_without_ttl(self):
        mock_redis = MagicMock()
        store = _SharedStateStore(mock_redis)
        store.set_json("k", {"a": 1})
        mock_redis.set.assert_called_once()

    def test_delete_propagates(self):
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        store = _SharedStateStore(mock_redis)
        assert store.delete("k") is True

    def test_redis_exception_returns_none(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("connection refused")
        store = _SharedStateStore(mock_redis)
        assert store.get_json("k") is None


# ---------------------------------------------------------------------------
# _env_flag and _env_value helpers
# ---------------------------------------------------------------------------


class TestEnvHelpers:
    def test_env_flag_true_values(self, monkeypatch):
        for val in ("1", "true", "yes", "on", "TRUE", "Yes"):
            monkeypatch.setenv("TEST_FLAG", val)
            assert _env_flag("TEST_FLAG") is True

    def test_env_flag_false_values(self, monkeypatch):
        for val in ("0", "false", "no", "off", "FALSE"):
            monkeypatch.setenv("TEST_FLAG", val)
            assert _env_flag("TEST_FLAG") is False

    def test_env_flag_unset_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert _env_flag("TEST_FLAG", default=True) is True
        assert _env_flag("TEST_FLAG", default=False) is False

    def test_env_flag_unknown_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FLAG", "maybe")
        assert _env_flag("TEST_FLAG", default=False) is False

    def test_env_value_returns_stripped_string(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "  hello  ")
        assert _env_value("TEST_VAL") == "hello"

    def test_env_value_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_VAL", raising=False)
        assert _env_value("TEST_VAL", "default") == "default"


# ---------------------------------------------------------------------------
# BillingService — webhook signature verification
# ---------------------------------------------------------------------------


class TestBillingServiceWebhookSignature:
    def test_valid_plain_signature(self):
        svc = _make_billing("my-secret")
        body = b'{"event": "test"}'
        sig = _sign(body, "my-secret", prefix=False)
        assert svc.verify_webhook_signature(body, sig) is True

    def test_valid_sha256_prefixed_signature(self):
        svc = _make_billing("my-secret")
        body = b'{"event": "test"}'
        sig = _sign(body, "my-secret", prefix=True)
        assert svc.verify_webhook_signature(body, sig) is True

    def test_invalid_signature_rejected(self):
        svc = _make_billing("my-secret")
        body = b'{"event": "test"}'
        assert svc.verify_webhook_signature(body, "sha256=deadbeef") is False

    def test_empty_signature_rejected(self):
        svc = _make_billing("my-secret")
        assert svc.verify_webhook_signature(b"payload", "") is False

    def test_valid_provider_style_signature(self):
        svc = _make_billing("my-secret")
        body = b'{"id": "evt_1"}'
        sig = _sign_ts(body, "my-secret")
        assert svc.verify_webhook_signature(body, sig) is True

    def test_provider_style_replayed_signature_rejected(self):
        svc = _make_billing("my-secret")
        body = b'{"id": "evt_1"}'
        old_ts = int(time.time()) - 400  # 6+ minutes ago
        sig = _sign_ts(body, "my-secret", ts=old_ts)
        assert svc.verify_webhook_signature(body, sig) is False

    def test_future_timestamp_outside_skew_rejected(self):
        svc = _make_billing("my-secret")
        body = b'{"id": "evt_2"}'
        future_ts = int(time.time()) + 400
        sig = _sign_ts(body, "my-secret", ts=future_ts)
        assert svc.verify_webhook_signature(body, sig) is False

    def test_timestamp_within_skew_accepted(self):
        svc = _make_billing("my-secret")
        body = b'{"data": 1}'
        recent_ts = int(time.time()) - 60  # 1 minute ago — within 5min window
        sig = _sign_ts(body, "my-secret", ts=recent_ts)
        assert svc.verify_webhook_signature(body, sig) is True

    def test_non_integer_timestamp_rejected(self):
        svc = _make_billing("my-secret")
        body = b"body"
        sig = "t=not-a-number,v1=deadbeef"
        assert svc.verify_webhook_signature(body, sig) is False

    def test_wrong_secret_rejected(self):
        svc = _make_billing("correct-secret")
        body = b"payload"
        sig = _sign(body, "wrong-secret")
        assert svc.verify_webhook_signature(body, sig) is False


# ---------------------------------------------------------------------------
# BillingService — _parse_signature_header
# ---------------------------------------------------------------------------


class TestParseSignatureHeader:
    def _svc(self):
        return _make_billing()

    def test_plain_hex(self):
        ts, candidates = self._svc()._parse_signature_header("abcdef1234")
        assert ts is None
        assert "abcdef1234" in candidates

    def test_sha256_prefix(self):
        # Fast-path: no comma/v1=/t= → returned verbatim; strip happens in verify_webhook_signature
        ts, candidates = self._svc()._parse_signature_header("sha256=deadbeef")
        assert ts is None
        assert "sha256=deadbeef" in candidates

    def test_provider_style_with_timestamp(self):
        ts, candidates = self._svc()._parse_signature_header("t=1700000000,v1=hexhex")
        assert ts == "1700000000"
        assert "hexhex" in candidates

    def test_multiple_v1_candidates(self):
        _, candidates = self._svc()._parse_signature_header(
            "t=123,v1=sig1,v1=sig2"
        )
        assert "sig1" in candidates
        assert "sig2" in candidates

    def test_empty_string(self):
        ts, candidates = self._svc()._parse_signature_header("")
        assert ts is None
        assert candidates == []


# ---------------------------------------------------------------------------
# BillingService — _normalize_event_type
# ---------------------------------------------------------------------------


class TestNormalizeEventType:
    def _svc(self):
        return _make_billing()

    def test_alias_plan_upgraded(self):
        assert self._svc()._normalize_event_type("plan.upgraded") == "customer.subscription.updated"

    def test_alias_subscription_canceled(self):
        assert self._svc()._normalize_event_type("subscription.canceled") == "customer.subscription.deleted"

    def test_passthrough_known_canonical(self):
        assert self._svc()._normalize_event_type("invoice.paid") == "invoice.paid"

    def test_passthrough_unknown(self):
        assert self._svc()._normalize_event_type("some.custom.event") == "some.custom.event"

    def test_case_and_whitespace(self):
        # strip + lowercase → alias lookup applies
        result = self._svc()._normalize_event_type("  Plan.Upgraded  ")
        assert result == "customer.subscription.updated"


# ---------------------------------------------------------------------------
# BillingService — process_webhook
# ---------------------------------------------------------------------------


class TestBillingServiceProcessWebhook:
    def _svc(self):
        return _make_billing()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_unknown_event_type_returns_ignored(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook("custom.event", {}, "evt-001")
        )
        assert result["status"] == "ignored"
        assert result["reason"] == "unknown_event_type"

    def test_invoice_payment_failed_processed(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "invoice.payment_failed",
                {"customer_id": "cus_123", "attempt": 2},
                "evt-002",
            )
        )
        assert result["status"] == "processed"
        assert result["action"] == "payment_retry_scheduled"
        assert result["customer_id"] == "cus_123"
        assert result["attempt"] == 2

    def test_subscription_updated_processed(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "customer.subscription.updated",
                {"customer_id": "cus_456", "plan": "enterprise"},
                "evt-003",
            )
        )
        assert result["status"] == "processed"
        assert result["action"] == "plan_updated"
        assert result["new_plan"] == "enterprise"

    def test_subscription_deleted_processed(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "customer.subscription.deleted",
                {"customer_id": "cus_789"},
                "evt-004",
            )
        )
        assert result["status"] == "processed"
        assert result["action"] == "termination_scheduled"

    def test_subscription_created_processed(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "customer.subscription.created",
                {"customer_id": "cus_new"},
                "evt-005",
            )
        )
        assert result["status"] == "processed"
        assert result["action"] == "subscription_created"

    def test_alias_event_type_normalized(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "plan.upgraded",
                {"customer_id": "cus_x", "plan": "pro"},
                "evt-006",
            )
        )
        assert result["status"] == "processed"
        assert result["action"] == "plan_updated"

    def test_idempotency_returns_cached_result(self):
        svc = self._svc()
        result1 = self._run(
            svc.process_webhook(
                "invoice.payment_failed",
                {"customer_id": "c1", "attempt": 1},
                "evt-idem-1",
            )
        )
        result2 = self._run(
            svc.process_webhook(
                "invoice.payment_failed",
                {"customer_id": "c1", "attempt": 1},
                "evt-idem-1",  # same event_id
            )
        )
        assert result1 == result2

    def test_idempotency_metadata_flag(self):
        svc = self._svc()
        self._run(
            svc.process_webhook(
                "invoice.payment_failed", {"customer_id": "c2"}, "evt-meta-1",
                include_idempotency_metadata=True,
            )
        )
        result = self._run(
            svc.process_webhook(
                "invoice.payment_failed", {"customer_id": "c2"}, "evt-meta-1",
                include_idempotency_metadata=True,
            )
        )
        assert result.get("_idempotent") is True

    def test_invoice_paid_without_user_id_acknowledges(self):
        svc = self._svc()
        result = self._run(
            svc.process_webhook(
                "invoice.paid",
                {"customer_id": "cus_paid", "metadata": {}},  # no user_id
                "evt-paid-1",
            )
        )
        # No user_id in metadata → acknowledges without DB
        assert result["status"] == "processed"
        assert result["action"] == "subscription_extended"


# ---------------------------------------------------------------------------
# BillingService — get_plan_limits
# ---------------------------------------------------------------------------


class TestBillingServicePlanLimits:
    def _svc(self):
        return _make_billing()

    def test_free_plan_limits(self):
        # "free" is aliased to "starter" via PLAN_ALIASES
        limits = self._svc().get_plan_limits("free")
        assert limits["plan"] == "starter"
        assert limits["max_nodes"] == 3   # _get_max_nodes("starter") defaults to 3
        assert limits["max_meshes"] == 1  # _get_max_meshes("starter") defaults to 1

    def test_pro_plan_limits(self):
        limits = self._svc().get_plan_limits("pro")
        assert limits["max_nodes"] == 20
        assert limits["max_meshes"] == 5

    def test_enterprise_plan_limits(self):
        limits = self._svc().get_plan_limits("enterprise")
        assert limits["max_nodes"] == 100
        assert limits["max_meshes"] == 50

    def test_alias_resolution(self):
        limits = self._svc().get_plan_limits("starter")
        # starter → free via PLAN_ALIASES
        assert limits["plan"] in ("free", "starter")

    def test_unknown_plan_falls_back_to_minimum(self):
        limits = self._svc().get_plan_limits("ultra_premium_x99")
        assert limits["max_nodes"] == 3  # default
        assert limits["max_meshes"] == 1


# ---------------------------------------------------------------------------
# BillingService — verify_crypto_payment edge cases
# ---------------------------------------------------------------------------


class TestVerifyCryptoPayment:
    def _svc(self):
        return _make_billing()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_invalid_hash_not_hex(self):
        svc = self._svc()
        bad_hash = "0x" + "z" * 64
        with pytest.raises(ValueError, match="valid hexadecimal"):
            self._run(svc.verify_crypto_payment(bad_hash, 29.0))

    def test_invalid_hash_wrong_length(self):
        svc = self._svc()
        with pytest.raises(ValueError, match="66 characters"):
            self._run(svc.verify_crypto_payment("0x" + "a" * 60, 29.0))

    def test_invalid_hash_no_prefix(self):
        svc = self._svc()
        with pytest.raises(ValueError, match="0x-prefixed"):
            self._run(svc.verify_crypto_payment("a" * 64, 29.0))

    def test_invalid_hash_empty(self):
        svc = self._svc()
        with pytest.raises(ValueError, match="non-empty string"):
            self._run(svc.verify_crypto_payment("", 29.0))

    def test_no_deposit_address_raises(self, monkeypatch):
        svc = self._svc()
        monkeypatch.delenv("CRYPTO_DEPOSIT_ADDRESS", raising=False)
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)
        valid_hash = "0x" + "a" * 64
        with pytest.raises(RuntimeError):
            self._run(svc.verify_crypto_payment(valid_hash, 29.0))

    def test_stub_mode_enabled(self, monkeypatch):
        svc = self._svc()
        monkeypatch.setenv("CRYPTO_DEPOSIT_ADDRESS", "0x" + "b" * 40)
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)
        monkeypatch.setenv("STUB_CRYPTO_ENABLED", "true")
        monkeypatch.delenv("PRODUCTION", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        valid_hash = "0x" + "a" * 64
        result = self._run(svc.verify_crypto_payment(valid_hash, 29.0))
        assert result is True

    def test_stub_blocked_in_production(self, monkeypatch):
        svc = self._svc()
        monkeypatch.setenv("CRYPTO_DEPOSIT_ADDRESS", "0x" + "b" * 40)
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)
        monkeypatch.setenv("STUB_CRYPTO_ENABLED", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")
        valid_hash = "0x" + "a" * 64
        with pytest.raises(RuntimeError, match="BLOCKED in production"):
            self._run(svc.verify_crypto_payment(valid_hash, 29.0))


# ---------------------------------------------------------------------------
# BillingService — _validate_transaction
# ---------------------------------------------------------------------------


class TestValidateTransaction:
    def _svc(self):
        return _make_billing()

    def test_success_status_and_correct_recipient(self):
        svc = self._svc()
        tx = {
            "status": "0x1",
            "to": "0xabc123",
            "value": hex(int(0.1 * 1e18)),
        }
        assert svc._validate_transaction(tx, 29.0, "0xABC123", 3) is True

    def test_failed_transaction_rejected(self):
        svc = self._svc()
        tx = {"status": "0x0", "to": "0xabc123", "value": "0x0"}
        assert svc._validate_transaction(tx, 29.0, "0xabc123", 3) is False

    def test_wrong_recipient_rejected(self):
        svc = self._svc()
        tx = {"status": "0x1", "to": "0xwrongaddr", "value": "0x0"}
        assert svc._validate_transaction(tx, 29.0, "0xcorrect", 3) is False


# ---------------------------------------------------------------------------
# MeshProvisioner
# ---------------------------------------------------------------------------


def _mock_mesh_instance(mesh_id: str = "mesh-test", nodes: int = 3) -> MagicMock:
    inst = MagicMock()
    inst.mesh_id = mesh_id
    inst.owner_id = "owner-1"
    inst.plan = "pro"
    inst.region = "us-east-1"
    inst.nodes = nodes
    inst.node_instances = {}
    inst.provision = AsyncMock()
    inst.terminate = AsyncMock()
    inst.scale = MagicMock()
    inst.add_node = MagicMock()
    inst.remove_node = MagicMock()
    return inst


class TestMeshProvisioner:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_provisioner(self):
        billing = _make_billing()
        return MeshProvisioner(billing_service=billing)

    def test_provision_mesh_success(self):
        provisioner = self._make_provisioner()
        mock_inst = _mock_mesh_instance()

        with patch("src.api.maas.services.MeshInstance", return_value=mock_inst):
            result = self._run(
                provisioner.provision_mesh(
                    owner_id="owner-1",
                    plan="pro",
                    region="us-east-1",
                    node_count=5,
                )
            )
        assert result is mock_inst
        mock_inst.provision.assert_awaited_once()

    def test_provision_mesh_exceeds_node_limit_raises(self):
        provisioner = self._make_provisioner()
        with pytest.raises(ValueError, match="exceeds plan limit"):
            self._run(
                provisioner.provision_mesh(
                    owner_id="owner-1",
                    plan="free",   # max 3 nodes
                    node_count=50,
                )
            )

    def test_provision_mesh_registers_in_registry(self):
        provisioner = self._make_provisioner()
        mock_inst = _mock_mesh_instance("mesh-reg-1")

        with patch("src.api.maas.services.MeshInstance", return_value=mock_inst):
            self._run(provisioner.provision_mesh(owner_id="o1", plan="pro", node_count=2))

        assert reg.get_mesh("mesh-reg-1") is mock_inst

    def test_scale_mesh_not_found_raises(self):
        provisioner = self._make_provisioner()
        with pytest.raises(ValueError, match="not found"):
            self._run(provisioner.scale_mesh("ghost-mesh", 5, "actor"))

    def test_scale_mesh_exceeds_limit_raises(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-scale-1")
        inst.plan = "free"  # max 3 nodes
        inst.node_instances = {}
        reg.register_mesh(inst)

        with pytest.raises(ValueError, match="exceeds plan limit"):
            self._run(provisioner.scale_mesh("mesh-scale-1", 10, "actor"))

    def test_scale_mesh_up(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-up-1")
        inst.plan = "pro"
        inst.node_instances = {"n1": {}, "n2": {}}  # 2 nodes
        reg.register_mesh(inst)

        result = self._run(provisioner.scale_mesh("mesh-up-1", 5, "actor"))
        assert result["action"] == "scale_up"
        assert result["previous_count"] == 2
        inst.scale.assert_called_once_with("scale_up", 3)

    def test_scale_mesh_down(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-down-1")
        inst.plan = "pro"
        inst.node_instances = {"n1": {}, "n2": {}, "n3": {}, "n4": {}}
        reg.register_mesh(inst)

        result = self._run(provisioner.scale_mesh("mesh-down-1", 2, "actor"))
        assert result["action"] == "scale_down"
        inst.scale.assert_called_once_with("scale_down", 2)

    def test_scale_mesh_no_change(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-nc-1")
        inst.plan = "pro"
        inst.node_instances = {"n1": {}, "n2": {}}
        reg.register_mesh(inst)

        result = self._run(provisioner.scale_mesh("mesh-nc-1", 2, "actor"))
        assert result["action"] == "no_change"
        inst.scale.assert_not_called()

    def test_terminate_mesh_success(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-term-1")
        reg.register_mesh(inst)

        result = self._run(provisioner.terminate_mesh("mesh-term-1", "actor"))
        assert result["status"] == "terminated"
        inst.terminate.assert_awaited_once()
        assert reg.get_mesh("mesh-term-1") is None

    def test_terminate_mesh_not_found_raises(self):
        provisioner = self._make_provisioner()
        with pytest.raises(ValueError, match="not found"):
            self._run(provisioner.terminate_mesh("ghost", "actor"))

    def test_approve_node_success(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-appr-1")
        reg.register_mesh(inst)
        reg.add_pending_node("mesh-appr-1", "node-X", {"ip": "10.0.0.1"})

        result = self._run(provisioner.approve_node("mesh-appr-1", "node-X", "admin"))
        assert result["status"] == "approved"
        inst.add_node.assert_called_once_with("node-X", {"ip": "10.0.0.1"})
        # node removed from pending
        assert "node-X" not in reg.get_pending_nodes("mesh-appr-1")

    def test_approve_node_mesh_not_found_raises(self):
        provisioner = self._make_provisioner()
        with pytest.raises(ValueError, match="not found"):
            self._run(provisioner.approve_node("ghost", "node-1", "admin"))

    def test_approve_node_not_pending_raises(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-np-1")
        reg.register_mesh(inst)

        with pytest.raises(ValueError, match="not in pending"):
            self._run(provisioner.approve_node("mesh-np-1", "node-Z", "admin"))

    def test_approve_revoked_node_raises(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-rev-1")
        reg.register_mesh(inst)
        reg.add_pending_node("mesh-rev-1", "bad-node", {})
        reg.revoke_node("mesh-rev-1", "bad-node", {"reason": "security"})

        with pytest.raises(ValueError, match="revoked"):
            self._run(provisioner.approve_node("mesh-rev-1", "bad-node", "admin"))

    def test_revoke_node_success(self):
        provisioner = self._make_provisioner()
        inst = _mock_mesh_instance("mesh-rvk-1")
        reg.register_mesh(inst)

        result = self._run(
            provisioner.revoke_node("mesh-rvk-1", "node-bad", "admin", "compromised")
        )
        assert result["status"] == "revoked"
        assert result["reason"] == "compromised"
        assert reg.is_node_revoked("mesh-rvk-1", "node-bad") is True
        inst.remove_node.assert_called_once_with("node-bad")

    def test_revoke_node_mesh_not_found_raises(self):
        provisioner = self._make_provisioner()
        with pytest.raises(ValueError, match="not found"):
            self._run(provisioner.revoke_node("ghost", "n1", "admin", "reason"))

    def test_metrics_recorded_on_provision(self):
        mock_metrics = MagicMock()
        provisioner = MeshProvisioner(
            billing_service=_make_billing(),
            metrics=mock_metrics,
        )
        mock_inst = _mock_mesh_instance("mesh-metrics-1")

        with patch("src.api.maas.services.MeshInstance", return_value=mock_inst):
            self._run(provisioner.provision_mesh(owner_id="o1", plan="pro", node_count=2))

        mock_metrics.record_meter.assert_called_with(
            "mesh.provisioned", 1, {"plan": "pro", "region": "global"}
        )


# ---------------------------------------------------------------------------
# UsageMeteringService
# ---------------------------------------------------------------------------


class TestUsageMeteringService:
    def _svc(self):
        return UsageMeteringService(shared_state={})

    def test_record_request_increments(self):
        svc = self._svc()
        svc.record_request("mesh-1", "/api/nodes", 12.5)
        svc.record_request("mesh-1", "/api/nodes", 8.0)
        report = svc.get_usage_report("mesh-1")
        assert report["requests"] == 2

    def test_record_bandwidth_accumulates(self):
        svc = self._svc()
        svc.record_bandwidth("mesh-1", bytes_in=1024, bytes_out=2048)
        svc.record_bandwidth("mesh-1", bytes_in=512, bytes_out=512)
        report = svc.get_usage_report("mesh-1")
        assert report["bandwidth_bytes"] == 4096

    def test_record_storage_overwrites(self):
        svc = self._svc()
        svc.record_storage("mesh-1", 500)
        svc.record_storage("mesh-1", 900)
        report = svc.get_usage_report("mesh-1")
        assert report["storage_bytes"] == 900

    def test_get_usage_report_fields(self):
        svc = self._svc()
        report = svc.get_usage_report("mesh-new")
        assert report["mesh_id"] == "mesh-new"
        assert report["requests"] == 0
        assert "report_time" in report

    def test_reset_usage_clears_counters(self):
        svc = self._svc()
        svc.record_request("mesh-r", "/x", 5.0)
        svc.record_bandwidth("mesh-r", 100, 200)
        svc.reset_usage("mesh-r")
        report = svc.get_usage_report("mesh-r")
        assert report["requests"] == 0
        assert report["bandwidth_bytes"] == 0

    def test_separate_meshes_isolated(self):
        svc = self._svc()
        svc.record_request("mesh-A", "/a", 1.0)
        svc.record_request("mesh-A", "/a", 1.0)
        svc.record_request("mesh-B", "/b", 1.0)
        assert svc.get_usage_report("mesh-A")["requests"] == 2
        assert svc.get_usage_report("mesh-B")["requests"] == 1

    def test_is_within_limits_true_when_under_quota(self):
        svc = self._svc()
        # No usage recorded → definitely within limits
        assert svc.is_within_limits("mesh-q1", "pro") is True

    def test_is_within_limits_false_when_requests_exceeded(self):
        svc = self._svc()
        # "free" aliases to "starter"; resolve the actual limit correctly
        from src.api.maas.constants import PLAN_ALIASES, PLAN_REQUEST_LIMITS
        normalized = PLAN_ALIASES.get("free", "free")
        limit = PLAN_REQUEST_LIMITS.get(normalized, 1000)
        svc._usage_cache["mesh-limit"] = {
            "requests": limit + 1,
            "bandwidth_bytes": 0,
            "storage_bytes": 0,
        }
        assert svc.is_within_limits("mesh-limit", "free") is False

    def test_metrics_recorded_on_request(self):
        mock_metrics = MagicMock()
        svc = UsageMeteringService(metrics=mock_metrics, shared_state={})
        svc.record_request("mesh-m", "/ep", 25.0)
        assert mock_metrics.record_meter.call_count == 2  # api.request + api.latency

    def test_metrics_recorded_on_bandwidth(self):
        mock_metrics = MagicMock()
        svc = UsageMeteringService(metrics=mock_metrics, shared_state={})
        svc.record_bandwidth("mesh-bw", 100, 200)
        mock_metrics.record_meter.assert_called_with(
            "network.bandwidth", 300, {"mesh_id": "mesh-bw"}
        )
