"""Unit tests for src/api/billing.py

Tests _verify_stripe_signature (HMAC-SHA256), _get_env, _require_env,
billing_config, checkout-session, webhook email extraction, and event filtering.
"""

import asyncio
import hashlib
import hmac
import importlib
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not available")


# ---------------------------------------------------------------------------
# Import billing module
# ---------------------------------------------------------------------------

try:
    import src.api.billing as billing_mod
    from src.coordination.events import EventBus, EventType
    from src.services.service_event_trace import event_trace_evidence_summary
    from src.api.billing import (
        CheckoutSessionRequest,
        _get_env,
        _require_env,
        _verify_stripe_signature,
        billing_config,
        create_checkout_session,
        router,
        stripe_webhook,
    )

    BILLING_AVAILABLE = True
except ImportError:
    BILLING_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not BILLING_AVAILABLE, reason="billing module not available"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signature(payload: bytes, secret: str, timestamp: int) -> str:
    """Build a valid Stripe-Signature header value."""
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _raw(fn):
    return getattr(fn, "__wrapped__", fn)


class _DummyRequest:
    def __init__(self, payload: bytes = b"", event_bus=None):
        self._payload = payload
        if event_bus is not None:
            self.state = SimpleNamespace(event_bus=event_bus)

    async def body(self) -> bytes:
        return self._payload


class _StripeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


# ===========================================================================
# TestGetEnv
# ===========================================================================


class TestGetEnv:

    def test_returns_value(self, monkeypatch):
        monkeypatch.setenv("TEST_BILLING_KEY", "hello")
        assert _get_env("TEST_BILLING_KEY") == "hello"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TEST_BILLING_KEY", "  spaced  ")
        assert _get_env("TEST_BILLING_KEY") == "spaced"

    def test_returns_none_for_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_BILLING_MISSING", raising=False)
        assert _get_env("TEST_BILLING_MISSING") is None

    def test_returns_none_for_empty_string(self, monkeypatch):
        monkeypatch.setenv("TEST_BILLING_KEY", "")
        assert _get_env("TEST_BILLING_KEY") is None

    def test_returns_none_for_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("TEST_BILLING_KEY", "   ")
        assert _get_env("TEST_BILLING_KEY") is None


# ===========================================================================
# TestRequireEnv
# ===========================================================================


class TestRequireEnv:

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_REQ_KEY", "value")
        assert _require_env("TEST_REQ_KEY") == "value"

    def test_raises_503_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_REQ_MISSING", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            _require_env("TEST_REQ_MISSING")
        assert exc_info.value.status_code == 503
        assert "TEST_REQ_MISSING" in exc_info.value.detail


# ===========================================================================
# TestVerifyStripeSignature
# ===========================================================================


class TestVerifyStripeSignature:

    def test_valid_signature_passes(self):
        payload = b'{"type":"checkout.session.completed"}'
        secret = "whsec_test_secret"
        ts = int(time.time())
        sig_header = _make_signature(payload, secret, ts)
        # Should not raise
        _verify_stripe_signature(payload, sig_header, secret)

    def test_invalid_signature_raises_400(self):
        payload = b'{"type":"test"}'
        secret = "whsec_test"
        ts = int(time.time())
        sig_header = f"t={ts},v1=badsignature"
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(payload, sig_header, secret)
        assert exc_info.value.status_code == 400
        assert "Invalid signature" in exc_info.value.detail

    def test_missing_timestamp_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(b"data", "v1=abc123", "secret")
        assert exc_info.value.status_code == 400

    def test_missing_v1_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(b"data", "t=12345", "secret")
        assert exc_info.value.status_code == 400

    def test_expired_timestamp_raises_400(self):
        payload = b'{"type":"test"}'
        secret = "whsec_test"
        ts = int(time.time()) - 600  # 10 min ago, tolerance is 5 min
        sig_header = _make_signature(payload, secret, ts)
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(payload, sig_header, secret)
        assert exc_info.value.status_code == 400
        assert "tolerance" in exc_info.value.detail.lower()

    def test_invalid_timestamp_format_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(b"data", "t=notanumber,v1=abc", "secret")
        assert exc_info.value.status_code == 400

    def test_custom_tolerance(self):
        """With a very tight tolerance, even a recent timestamp fails."""
        payload = b"data"
        secret = "s"
        ts = int(time.time()) - 10  # 10 sec ago
        sig_header = _make_signature(payload, secret, ts)
        with pytest.raises(HTTPException):
            _verify_stripe_signature(payload, sig_header, secret, tolerance_seconds=5)

    def test_future_timestamp_within_tolerance(self):
        """A timestamp a few seconds in the future is still valid."""
        payload = b"data"
        secret = "s"
        ts = int(time.time()) + 5
        sig_header = _make_signature(payload, secret, ts)
        _verify_stripe_signature(payload, sig_header, secret)


# ===========================================================================
# TestBillingConfig (endpoint)
# ===========================================================================


class TestBillingConfig:
    @pytest.mark.asyncio
    async def test_config_not_configured(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
        body = await billing_config()
        assert body["configured"] is False

    @pytest.mark.asyncio
    async def test_config_configured(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_123")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_123")
        body = await billing_config()
        assert body["configured"] is True
        assert body["publishable_key"] == "pk_test_123"
        assert body["price_id"] == "price_123"

    @pytest.mark.asyncio
    async def test_config_event_redacts_provider_keys(self, monkeypatch, tmp_path):
        bus = EventBus(str(tmp_path))
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_private")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_private")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_private")

        body = await billing_config(request=_DummyRequest(event_bus=bus))
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=billing_mod._BILLING_CONFIG_SOURCE_AGENT,
            limit=10,
        )
        payload = events[-1].data
        payload_text = str(payload)

        assert body["configured"] is True
        assert body["claim_gate"]["local_billing_lifecycle_claim_allowed"] is True
        assert body["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert body["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert body["claim_gate"]["dataplane_delivery_claim_allowed"] is False
        assert body["claim_gate"]["production_readiness_claim_allowed"] is False
        assert body["cross_plane_claim_gate"]["surface"] == "billing_api.config"
        assert body["cross_plane_claim_gate"]["allowed"] is False
        assert payload["observed_state"] is True
        assert payload["configured"] is True
        assert payload["raw_publishable_key_redacted"] is True
        assert payload["raw_price_id_redacted"] is True
        assert payload["settlement_evidence"]["settlement_action"] == "config_observation_only"
        assert payload["settlement_evidence"]["provider"] == "local_config"
        assert payload["settlement_evidence"]["dataplane_confirmed"] is False
        assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
        assert "sk_test_private" not in payload_text
        assert "price_private" not in payload_text
        assert "pk_test_private" not in payload_text


# ===========================================================================
# TestBillingReadiness
# ===========================================================================


def _model_with_attrs(**attrs):
    return type("Model", (), attrs)


def _force_billing_api_dependencies_ready(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        billing_mod,
        "httpx",
        SimpleNamespace(AsyncClient=object),
    )
    monkeypatch.setattr(
        billing_mod,
        "stripe_circuit",
        SimpleNamespace(call=lambda operation: operation()),
    )
    monkeypatch.setattr(
        billing_mod,
        "generate_vless_link",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        billing_mod,
        "_billing_api_provisioning_imports_available",
        lambda: True,
    )
    monkeypatch.setattr(
        billing_mod,
        "BillingWebhookEvent",
        _model_with_attrs(
            event_id="",
            event_type="",
            payload_hash="",
            status="",
            response_json="",
            created_at="",
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "User",
        _model_with_attrs(
            email="",
            plan="",
            vpn_uuid="",
            stripe_customer_id="",
            stripe_subscription_id="",
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "License",
        _model_with_attrs(token="", user_id="", tier="", is_active=""),
    )
    monkeypatch.setattr(
        billing_mod,
        "Payment",
        _model_with_attrs(status="", amount=0),
    )
    monkeypatch.setattr(
        billing_mod,
        "Invoice",
        _model_with_attrs(status="", total_amount=0),
    )


class TestBillingReadiness:
    def test_router_has_readiness_route(self):
        route_paths = [r.path for r in router.routes]
        assert "/api/v1/billing/readiness" in route_paths

    def test_ready_when_local_dependencies_are_available(self, monkeypatch):
        _force_billing_api_dependencies_ready(monkeypatch)
        db = MagicMock(spec=["query", "add", "commit", "rollback"])

        payload = billing_mod._billing_api_readiness_status(db)

        assert payload["status"] == "ready"
        assert payload["billing_api_runtime_ready"] is True
        assert payload["billing_api_db_ready"] is True
        assert payload["stripe_checkout_config_ready"] is True
        assert payload["stripe_webhook_config_ready"] is True
        assert payload["stripe_transport_ready"] is True
        assert payload["billing_models_ready"] is True
        assert payload["vless_link_ready"] is True
        assert payload["provisioning_imports_ready"] is True
        assert payload["cross_plane_claim_gate"]["allowed"] is False
        assert payload["cross_plane_claim_gate"]["requested_claim_ids"] == [
            "production_readiness",
            "settlement_finality",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
        ]
        assert payload["degraded_dependencies"] == []

    def test_degraded_when_dependencies_are_missing(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr(billing_mod, "httpx", SimpleNamespace(AsyncClient=None))
        monkeypatch.setattr(billing_mod, "stripe_circuit", SimpleNamespace(call=None))
        monkeypatch.setattr(billing_mod, "generate_vless_link", None)
        monkeypatch.setattr(
            billing_mod,
            "_billing_api_provisioning_imports_available",
            lambda: False,
        )
        monkeypatch.setattr(
            billing_mod,
            "BillingWebhookEvent",
            _model_with_attrs(event_id=""),
        )

        payload = billing_mod._billing_api_readiness_status(SimpleNamespace())

        assert payload["status"] == "degraded"
        assert payload["billing_api_runtime_ready"] is False
        assert payload["degraded_dependencies"] == [
            "database",
            "stripe_checkout_config",
            "stripe_webhook_config",
            "stripe_transport",
            "billing_models",
            "vless_link_generator",
            "provisioning_imports",
        ]
        assert "does not call Stripe" in payload["claim_boundary"]

    def test_endpoint_marks_degraded_dependencies(self, monkeypatch):
        _force_billing_api_dependencies_ready(monkeypatch)
        request = SimpleNamespace(state=SimpleNamespace())

        payload = asyncio.run(
            billing_mod.billing_api_readiness(request, db=SimpleNamespace())
        )

        assert payload["status"] == "degraded"
        assert request.state.degraded_dependencies == {"database"}


# ===========================================================================
# TestWebhookEmailExtraction
# ===========================================================================


class TestWebhookEmailExtraction:
    @pytest.fixture
    def webhook_secret(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        return "whsec_test"

    async def _webhook_request(self, event: dict, secret="whsec_test", db=None):
        payload = json.dumps(event).encode("utf-8")
        ts = int(time.time())
        sig = _make_signature(payload, secret, ts)
        return await _raw(stripe_webhook)(
            request=_DummyRequest(payload),
            db=db or MagicMock(),
            stripe_signature=sig,
        )

    @pytest.mark.asyncio
    async def test_webhook_missing_signature_returns_400(self, webhook_secret):
        with pytest.raises(HTTPException) as exc_info:
            await _raw(stripe_webhook)(
                request=_DummyRequest(b"{}"),
                db=MagicMock(),
                stripe_signature=None,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_valid_returns_received(self, webhook_secret):
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"customer_email": "test@example.com"}},
        }
        resp = await self._webhook_request(event, db=MagicMock())
        assert resp["received"] is True
        assert resp["claim_gate"]["webhook_lifecycle_claim_allowed"] is True
        assert resp["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert resp["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert resp["claim_gate"]["customer_access_claim_allowed"] is False
        assert resp["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert resp["claim_gate"]["production_readiness_claim_allowed"] is False
        assert resp["cross_plane_claim_gate"]["surface"] == "billing_api.webhook"
        assert resp["cross_plane_claim_gate"]["allowed"] is False

    @pytest.mark.asyncio
    async def test_webhook_extracts_email_from_customer_details(self, webhook_secret):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "user@example.com"},
                    "customer": "cus_123",
                }
            },
        }
        resp = await self._webhook_request(event, db=MagicMock())
        assert resp["received"] is True

    @pytest.mark.asyncio
    async def test_webhook_extracts_email_from_metadata(self, webhook_secret):
        event = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "metadata": {"user_email": "meta@example.com"},
                }
            },
        }
        resp = await self._webhook_request(event, db=MagicMock())
        assert resp["received"] is True

    @pytest.mark.asyncio
    async def test_webhook_ignores_unknown_event_type(self, webhook_secret):
        event = {
            "type": "balance.available",
            "data": {"object": {"customer_email": "ignored@example.com"}},
        }
        resp = await self._webhook_request(event, db=MagicMock())
        assert resp["received"] is True

    @pytest.mark.asyncio
    async def test_invalid_signature_event_redacts_payload_and_signature(
        self, webhook_secret, tmp_path
    ):
        bus = EventBus(str(tmp_path))
        event = {
            "id": "evt_private",
            "type": "checkout.session.completed",
            "data": {"object": {"customer_email": "private@example.com"}},
        }
        payload = json.dumps(event).encode("utf-8")

        with pytest.raises(HTTPException) as exc_info:
            await _raw(stripe_webhook)(
                request=_DummyRequest(payload, event_bus=bus),
                db=MagicMock(),
                stripe_signature="t=123,v1=private_signature",
            )

        events = bus.get_event_history(
            event_type=EventType.TASK_BLOCKED,
            source_agent=billing_mod._BILLING_WEBHOOK_SOURCE_AGENT,
            limit=10,
        )
        evidence = events[-1].data
        evidence_text = str(evidence)

        assert exc_info.value.status_code == 400
        assert evidence["signature_verified"] is False
        assert evidence["payload_size_bytes"] == len(payload)
        assert evidence["raw_payload_redacted"] is True
        assert evidence["raw_signature_redacted"] is True
        assert evidence["settlement_evidence"]["source_quality"] == (
            "local_webhook_preflight_or_rejected"
        )
        assert evidence["settlement_evidence"]["settlement_action"] == (
            "webhook_local_lifecycle_only"
        )
        assert evidence["settlement_evidence"]["dataplane_confirmed"] is False
        assert evidence["settlement_evidence"]["live_provider_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["bank_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["chain_finality_confirmed"] is False
        gate = evidence["settlement_evidence"]["claim_gate"]
        assert gate["decision"] == "blocked_or_unconfirmed_billing_lifecycle"
        assert gate["local_billing_lifecycle_claim_allowed"] is False
        assert gate["payment_provider_settlement_claim_allowed"] is False
        assert gate["bank_settlement_claim_allowed"] is False
        assert gate["customer_dataplane_delivery_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False
        assert "private@example.com" not in evidence_text
        assert "evt_private" not in evidence_text
        assert "private_signature" not in evidence_text

    @pytest.mark.asyncio
    async def test_webhook_links_vpn_provisioning_evidence_without_raw_access(
        self,
        monkeypatch,
        webhook_secret,
        tmp_path,
    ):
        bus = EventBus(str(tmp_path))

        class _Query:
            def __init__(self, result=None):
                self._result = result

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return self._result

        class _DB:
            def __init__(self):
                self.added = []
                self.commits = 0

            def query(self, model):
                if model is billing_mod.User:
                    return _Query(None)
                return _Query(None)

            def add(self, item):
                self.added.append(item)

            def commit(self):
                self.commits += 1

            def rollback(self):
                pass

        class _FakeProvisioningService:
            async def provision_vpn_user(self, **kwargs):
                assert kwargs["event_bus"] is bus
                return SimpleNamespace(
                    success=True,
                    vpn_uuid="uuid-private",
                    error=None,
                )

            def get_last_event_evidence(self):
                return {
                    "event_id": "evt-vpn-provision",
                    "source_agent": "vpn-provisioning-service",
                    "layer": "service_vpn_provisioning_control_action",
                    "operation": "provision_vpn_user",
                    "stage": "vpn_provision",
                    "status": "success",
                    "control_action": True,
                    "claim_boundary": "bounded vpn provisioning evidence",
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                }

        from src.sales import telegram_bot as telegram_bot_mod

        provisioning_mod = importlib.import_module("src.services.provisioning_service")
        monkeypatch.setattr(
            provisioning_mod,
            "provisioning_service",
            _FakeProvisioningService(),
        )
        monkeypatch.setattr(
            telegram_bot_mod.TokenGenerator,
            "generate",
            staticmethod(lambda tier: "license-private"),
        )

        event = {
            "id": "evt_private",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "private@example.com"},
                    "customer": "cus_private",
                    "subscription": "sub_private",
                    "payment_status": "paid",
                }
            },
        }
        payload = json.dumps(event).encode("utf-8")
        sig = _make_signature(payload, webhook_secret, int(time.time()))

        response = await _raw(stripe_webhook)(
            request=_DummyRequest(payload, event_bus=bus),
            db=_DB(),
            stripe_signature=sig,
        )

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=billing_mod._BILLING_WEBHOOK_SOURCE_AGENT,
            limit=10,
        )
        evidence = events[-1].data
        evidence_text = str(evidence)
        provision_ref = evidence["vpn_provision_event_reference"]
        settlement_ref = evidence["settlement_evidence"]["output_summary"][
            "vpn_provision_evidence"
        ]

        assert response["received"] is True
        assert response["claim_gate"]["webhook_lifecycle_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_access_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "billing_api.webhook"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert evidence["vpn_provision_attempted"] is True
        assert evidence["vpn_provision_success"] is True
        assert provision_ref["event_id"] == "evt-vpn-provision"
        assert provision_ref["source_agent"] == "vpn-provisioning-service"
        assert settlement_ref["available"] is True
        assert settlement_ref["event_id"] == "evt-vpn-provision"
        assert evidence["settlement_evidence"]["dataplane_confirmed"] is False
        gate = evidence["settlement_evidence"]["claim_gate"]
        assert gate["decision"] == "local_billing_lifecycle_only"
        assert gate["local_billing_lifecycle_claim_allowed"] is True
        assert gate["webhook_lifecycle_claim_allowed"] is True
        assert gate["vpn_provision_reference_present"] is True
        assert gate["customer_access_claim_allowed"] is False
        assert gate["customer_dataplane_delivery_claim_allowed"] is False
        assert gate["payment_provider_settlement_claim_allowed"] is False
        for raw_value in [
            "private@example.com",
            "uuid-private",
            "license-private",
            "cus_private",
            "sub_private",
            "evt_private",
        ]:
            assert raw_value not in evidence_text


# ===========================================================================
# TestCheckoutSession
# ===========================================================================


class TestCheckoutSession:
    @pytest.mark.asyncio
    async def test_invalid_email_returns_400(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_123")
        with pytest.raises(HTTPException) as exc_info:
            await _raw(create_checkout_session)(
                request=_DummyRequest(),
                payload=CheckoutSessionRequest(email="noemail", plan="pro"),
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_stripe_key_returns_503(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            await _raw(create_checkout_session)(
                request=_DummyRequest(),
                payload=CheckoutSessionRequest(email="user@example.com", plan="pro"),
            )
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_checkout_event_redacts_email_secret_and_checkout_url(
        self, monkeypatch, tmp_path
    ):
        bus = EventBus(str(tmp_path))
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_private")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_private")

        class _CheckoutClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, *_args, **_kwargs):
                return _StripeResponse(
                    200,
                    {
                        "id": "cs_private",
                        "url": "https://checkout.stripe.test/private",
                    },
                )

        monkeypatch.setattr(
            billing_mod,
            "httpx",
            SimpleNamespace(AsyncClient=lambda **_kwargs: _CheckoutClient()),
        )
        monkeypatch.setattr(
            billing_mod,
            "stripe_circuit",
            SimpleNamespace(call=lambda operation: operation()),
        )

        response = await _raw(create_checkout_session)(
            request=_DummyRequest(event_bus=bus),
            payload=CheckoutSessionRequest(email="buyer@example.com", plan="pro"),
        )
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=billing_mod._BILLING_CHECKOUT_SOURCE_AGENT,
            limit=10,
        )
        evidence = events[-1].data
        evidence_text = str(evidence)

        assert response["id"] == "cs_private"
        assert response["claim_gate"]["checkout_intent_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_access_claim_allowed"] is False
        assert response["claim_gate"]["dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "billing_api.checkout_session"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert "checkout-intent" in response["claim_boundary"]
        assert evidence["control_action"] is True
        assert evidence["checkout_url_present"] is True
        assert evidence["stripe_http_status"] == 200
        assert evidence["source_quality"] == "stripe_checkout_session_api_response"
        assert evidence["settlement_evidence"]["settlement_action"] == (
            "checkout_session_intent_only"
        )
        assert evidence["settlement_evidence"]["provider"] == "stripe"
        assert evidence["settlement_evidence"]["dataplane_confirmed"] is False
        assert evidence["settlement_evidence"]["live_provider_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["bank_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["chain_finality_confirmed"] is False
        assert evidence["settlement_evidence"]["db_write_evidence"]["committed"] is False
        gate = evidence["settlement_evidence"]["claim_gate"]
        assert gate["decision"] == "local_billing_lifecycle_only"
        assert gate["checkout_intent_claim_allowed"] is True
        assert gate["payment_provider_settlement_claim_allowed"] is False
        assert gate["bank_settlement_claim_allowed"] is False
        assert gate["customer_access_claim_allowed"] is False
        assert gate["dataplane_delivery_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False

        trace_summary = event_trace_evidence_summary(evidence)
        settlement_summary = trace_summary["settlement_evidence"]
        assert settlement_summary["present"] is True
        assert settlement_summary["source_quality"] == (
            "stripe_checkout_session_api_response"
        )
        assert settlement_summary["settlement_action"] == (
            "checkout_session_intent_only"
        )
        assert settlement_summary["provider"] == "stripe"
        assert settlement_summary["live_provider_settlement_confirmed"] is False
        assert settlement_summary["claim_gate"]["present"] is True
        assert settlement_summary["claim_gate"]["decision"] == (
            "local_billing_lifecycle_only"
        )
        assert settlement_summary["claim_gate"]["traffic_delivery_claim_allowed"] is False
        assert (
            settlement_summary["claim_gate"]["external_settlement_finality_claim_allowed"]
            is False
        )
        assert (
            settlement_summary["claim_gate"]["production_readiness_claim_allowed"]
            is False
        )
        assert "buyer@example.com" not in evidence_text
        assert "sk_test_private" not in evidence_text
        assert "price_private" not in evidence_text
        assert "cs_private" not in evidence_text
        assert "checkout.stripe.test/private" not in evidence_text


class TestOrderStatusAndRevenueEvidence:
    @pytest.mark.asyncio
    async def test_order_status_event_redacts_session_email_and_vless_link(
        self, monkeypatch, tmp_path
    ):
        bus = EventBus(str(tmp_path))
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_private")

        class _OrderStatusClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def get(self, *_args, **_kwargs):
                return _StripeResponse(
                    200,
                    {
                        "payment_status": "paid",
                        "customer_details": {"email": "buyer@example.com"},
                    },
                )

        class _Query:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return SimpleNamespace(
                    plan="pro",
                    vpn_uuid="vpn-private-uuid",
                )

        monkeypatch.setattr(
            billing_mod,
            "httpx",
            SimpleNamespace(AsyncClient=lambda *_, **__: _OrderStatusClient()),
        )
        monkeypatch.setattr(
            billing_mod,
            "generate_vless_link",
            lambda *_args, **_kwargs: "vless://vpn-private-uuid@private-host",
        )

        response = await billing_mod.get_order_status(
            "cs_private",
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _Query()),
            request=_DummyRequest(event_bus=bus),
        )
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=billing_mod._BILLING_ORDER_STATUS_SOURCE_AGENT,
            limit=10,
        )
        evidence = events[-1].data
        evidence_text = str(evidence)

        assert response["status"] == "paid"
        assert response["claim_gate"]["stripe_status_observation_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_access_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "billing_api.order_status"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert "customer dataplane delivery" in response["claim_boundary"]
        assert evidence["observed_state"] is True
        assert evidence["vless_link_present"] is True
        assert evidence["settlement_evidence"]["settlement_action"] == (
            "order_status_observation_only"
        )
        assert evidence["settlement_evidence"]["provider"] == "stripe"
        assert evidence["settlement_evidence"]["payment_status"] == "paid"
        assert evidence["settlement_evidence"]["live_provider_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["bank_settlement_confirmed"] is False
        assert evidence["settlement_evidence"]["chain_finality_confirmed"] is False
        gate = evidence["settlement_evidence"]["claim_gate"]
        assert gate["stripe_status_observation_claim_allowed"] is True
        assert gate["payment_provider_settlement_claim_allowed"] is False
        assert gate["customer_dataplane_delivery_claim_allowed"] is False
        assert evidence["raw_session_id_redacted"] is True
        assert "cs_private" not in evidence_text
        assert "buyer@example.com" not in evidence_text
        assert "vpn-private-uuid" not in evidence_text
        assert "vless://vpn-private-uuid@private-host" not in evidence_text

    @pytest.mark.asyncio
    async def test_revenue_metrics_event_uses_bounded_aggregate_metadata(
        self, tmp_path
    ):
        bus = EventBus(str(tmp_path))

        class _Query:
            def __init__(self, *, rows=None, count_value=0):
                self.rows = rows or []
                self.count_value = count_value

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return self.rows

            def count(self):
                return self.count_value

        def _query(model):
            if model is billing_mod.Payment:
                return _Query(
                    rows=[
                        SimpleNamespace(amount=100),
                        SimpleNamespace(amount=250),
                    ]
                )
            if model is billing_mod.Invoice:
                return _Query(rows=[SimpleNamespace(total_amount=1000)])
            return _Query(count_value=2)

        response = await billing_mod.get_revenue_metrics(
            db=SimpleNamespace(query=_query),
            request=_DummyRequest(event_bus=bus),
        )
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=billing_mod._BILLING_REVENUE_METRICS_SOURCE_AGENT,
            limit=10,
        )
        evidence = events[-1].data

        assert response["total_revenue_rub"] == 350
        assert response["claim_gate"]["local_billing_lifecycle_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert response["claim_gate"]["external_settlement_finality_claim_allowed"] is False
        assert response["claim_gate"]["dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "billing_api.revenue_metrics"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert evidence["read_only"] is True
        assert evidence["total_verified_payments"] == 2
        assert evidence["total_paid_invoices"] == 1
        assert evidence["active_paying_users"] == 2
        assert evidence["raw_payment_rows_redacted"] is True
        assert evidence["raw_invoice_rows_redacted"] is True
        assert evidence["settlement_evidence"]["settlement_action"] == (
            "revenue_metrics_observation_only"
        )
        assert evidence["settlement_evidence"]["provider"] == "local_db"
        assert evidence["settlement_evidence"]["dataplane_confirmed"] is False
        assert evidence["settlement_evidence"]["live_provider_settlement_confirmed"] is False
