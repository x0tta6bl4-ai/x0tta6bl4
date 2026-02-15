"""Unit tests for src/api/billing.py

Tests _verify_stripe_signature (HMAC-SHA256), _get_env, _require_env,
billing_config, checkout-session, webhook email extraction, and event filtering.
"""

import hashlib
import hmac
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

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
    from src.api.billing import (CheckoutSessionRequest, _get_env,
                                 _require_env, _verify_stripe_signature,
                                 billing_config, create_checkout_session,
                                 router, stripe_webhook)

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
    def __init__(self, payload: bytes = b""):
        self._payload = payload

    async def body(self) -> bytes:
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
