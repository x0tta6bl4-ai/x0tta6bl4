"""Unit tests for src/api/billing.py

Tests _verify_stripe_signature (HMAC-SHA256), _get_env, _require_env,
billing_config, checkout-session, webhook email extraction, and event filtering.
"""

import os
import time
import hmac
import hashlib
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not available")


# ---------------------------------------------------------------------------
# Import billing module
# ---------------------------------------------------------------------------

try:
    from src.api.billing import (
        _get_env,
        _require_env,
        _verify_stripe_signature,
        router,
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

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_config_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
        resp = client.get("/api/v1/billing/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False

    def test_config_configured(self, client, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_123")
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_123")
        resp = client.get("/api/v1/billing/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["publishable_key"] == "pk_test_123"
        assert body["price_id"] == "price_123"


# ===========================================================================
# TestWebhookEmailExtraction
# ===========================================================================

class TestWebhookEmailExtraction:

    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def _webhook_request(self, client, event: dict, secret="whsec_test"):
        payload = json.dumps(event).encode("utf-8")
        ts = int(time.time())
        sig = _make_signature(payload, secret, ts)
        return client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
        )

    def test_webhook_missing_signature_returns_400(self, client):
        resp = client.post(
            "/api/v1/billing/webhook",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    @patch("src.api.billing.get_db")
    def test_webhook_valid_returns_received(self, mock_get_db, client):
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"customer_email": "test@example.com"}},
        }
        resp = self._webhook_request(client, event)
        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("src.api.billing.get_db")
    def test_webhook_extracts_email_from_customer_details(self, mock_get_db, client):
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "user@example.com"},
                    "customer": "cus_123",
                }
            },
        }
        resp = self._webhook_request(client, event)
        assert resp.status_code == 200

    @patch("src.api.billing.get_db")
    def test_webhook_extracts_email_from_metadata(self, mock_get_db, client):
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        event = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "metadata": {"user_email": "meta@example.com"},
                }
            },
        }
        resp = self._webhook_request(client, event)
        assert resp.status_code == 200

    @patch("src.api.billing.get_db")
    def test_webhook_ignores_unknown_event_type(self, mock_get_db, client):
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        event = {
            "type": "balance.available",
            "data": {"object": {"customer_email": "ignored@example.com"}},
        }
        resp = self._webhook_request(client, event)
        assert resp.status_code == 200
        assert resp.json()["received"] is True


# ===========================================================================
# TestCheckoutSession
# ===========================================================================

class TestCheckoutSession:

    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.setenv("STRIPE_PRICE_ID", "price_123")
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_invalid_email_returns_400(self, client):
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={"email": "noemail", "plan": "pro"},
        )
        assert resp.status_code == 400

    def test_missing_stripe_key_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        resp = client.post(
            "/api/v1/billing/checkout-session",
            json={"email": "user@example.com", "plan": "pro"},
        )
        assert resp.status_code == 503
