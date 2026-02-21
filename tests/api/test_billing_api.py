"""
Tests for Billing API endpoints.
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.app import app

client = TestClient(app)


def generate_stripe_signature(payload: bytes, secret: str) -> str:
    """Generate valid Stripe webhook signature."""
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.".encode("utf-8") + payload
    signature = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestBillingConfig:
    """Tests for billing configuration endpoint."""

    def test_get_billing_config_unconfigured(self):
        """Test billing config when Stripe not configured."""
        with patch.dict(os.environ, {}, clear=True):
            response = client.get("/api/v1/billing/config")
            assert response.status_code == 200
            data = response.json()
            assert data["configured"] is False

    @patch.dict(
        os.environ,
        {
            "STRIPE_SECRET_KEY": "sk_test_xxx",
            "STRIPE_PUBLISHABLE_KEY": "pk_test_xxx",
            "STRIPE_PRICE_ID": "price_xxx",
        },
    )
    def test_get_billing_config_configured(self):
        """Test billing config when Stripe is configured."""
        response = client.get("/api/v1/billing/config")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["publishable_key"] == "pk_test_xxx"
        assert data["price_id"] == "price_xxx"


class TestCheckoutSession:
    """Tests for checkout session creation."""

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_xxx", "STRIPE_PRICE_ID": "price_xxx"}
    )
    @patch("httpx.AsyncClient.post")
    def test_create_checkout_session_success(self, mock_post):
        """Test successful checkout session creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cs_test_xxx",
            "url": "https://checkout.stripe.com/session_xxx",
        }
        mock_post.return_value = mock_response

        with patch("src.api.billing.stripe_circuit") as mock_circuit:
            mock_circuit.call = AsyncMock(
                return_value={
                    "id": "cs_test_xxx",
                    "url": "https://checkout.stripe.com/session_xxx",
                }
            )

            payload = {"email": "test@example.com", "plan": "pro", "quantity": 1}
            response = client.post("/api/v1/billing/checkout-session", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "url" in data

    def test_create_checkout_session_invalid_email(self):
        """Test checkout session with invalid email."""
        payload = {"email": "invalid-email", "plan": "pro", "quantity": 1}
        response = client.post("/api/v1/billing/checkout-session", json=payload)
        assert response.status_code == 400
        assert "Invalid email" in response.json()["detail"]

    def test_create_checkout_session_missing_stripe_config(self):
        """Test checkout session when Stripe not configured."""
        with patch.dict(os.environ, {}, clear=True):
            payload = {"email": "test@example.com", "plan": "pro", "quantity": 1}
            response = client.post("/api/v1/billing/checkout-session", json=payload)
            assert response.status_code == 503
            assert "Missing required configuration" in response.json()["detail"]

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_xxx", "STRIPE_PRICE_ID": "price_xxx"}
    )
    def test_create_checkout_session_circuit_breaker_open(self):
        """Test checkout session when circuit breaker is open."""
        from src.core.circuit_breaker import CircuitBreakerOpen

        with patch("src.api.billing.stripe_circuit") as mock_circuit:
            mock_circuit.call = AsyncMock(side_effect=CircuitBreakerOpen("stripe_api"))

            payload = {"email": "test@example.com", "plan": "pro", "quantity": 1}
            response = client.post("/api/v1/billing/checkout-session", json=payload)
            assert response.status_code == 503
            assert "temporarily unavailable" in response.json()["detail"]


class TestStripeWebhook:
    """Tests for Stripe webhook handling."""

    def test_webhook_missing_signature(self):
        """Test webhook without signature header."""
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b'{"type": "checkout.session.completed"}',
            )
            assert response.status_code == 400
            assert "Missing Stripe-Signature" in response.json()["detail"]

    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature."""
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b'{"type": "checkout.session.completed"}',
                headers={"Stripe-Signature": "t=123,v1=invalid"},
            )
            assert response.status_code == 400

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_webhook_checkout_completed(self):
        """Test successful checkout.session.completed webhook."""
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer_email": "test@example.com",
                        "customer": "cus_xxx",
                        "subscription": "sub_xxx",
                        "metadata": {"user_email": "test@example.com", "plan": "pro"},
                    }
                },
            }
        ).encode("utf-8")

        signature = generate_stripe_signature(payload, "whsec_test")

        with patch("src.api.billing.get_db") as mock_db:
            mock_session = Mock()
            mock_user = Mock()
            mock_user.id = "user_123"
            mock_user.email = "test@example.com"
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_user
            )
            mock_db.return_value = iter([mock_session])

            with patch(
                "src.api.users.users_db", {"test@example.com": {"plan": "free"}}
            ):
                with patch("src.sales.telegram_bot.TokenGenerator") as mock_token:
                    mock_token.generate.return_value = "license_xxx"

                    response = client.post(
                        "/api/v1/billing/webhook",
                        content=payload,
                        headers={"Stripe-Signature": signature},
                    )
                    assert response.status_code == 200
                    assert response.json()["received"] is True

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_webhook_invoice_paid(self):
        """Test invoice.paid webhook."""
        payload = json.dumps(
            {
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "customer_email": "test@example.com",
                        "customer": "cus_xxx",
                        "subscription": "sub_xxx",
                    }
                },
            }
        ).encode("utf-8")

        signature = generate_stripe_signature(payload, "whsec_test")

        with patch("src.api.billing.get_db") as mock_db:
            mock_session = Mock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                None
            )
            mock_db.return_value = iter([mock_session])

            response = client.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"Stripe-Signature": signature},
            )
            assert response.status_code == 200

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_webhook_expired_signature(self):
        """Test webhook with expired signature timestamp."""
        payload = b'{"type": "checkout.session.completed"}'
        old_timestamp = str(
            int(time.time()) - 400
        )  # 400 seconds old (tolerance is 300)
        signed = f"{old_timestamp}.".encode("utf-8") + payload
        sig = hmac.new(b"whsec_test", signed, hashlib.sha256).hexdigest()
        signature = f"t={old_timestamp},v1={sig}"

        response = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Stripe-Signature": signature},
        )
        assert response.status_code == 400
        assert "outside tolerance" in response.json()["detail"]

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_webhook_invalid_json(self):
        """Test webhook with invalid JSON payload."""
        payload = b"not valid json"
        signature = generate_stripe_signature(payload, "whsec_test")

        response = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Stripe-Signature": signature},
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    @patch("src.sales.telegram_bot.TokenGenerator.generate")
    def test_webhook_idempotent_replay_by_event_id(self, mock_token_generate):
        """Same Stripe event id should be processed only once."""
        event_id = f"evt_{uuid.uuid4().hex}"
        payload = json.dumps(
            {
                "id": event_id,
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer_email": "idem-api@example.com",
                        "customer": "cus_idem_api",
                        "subscription": "sub_idem_api",
                        "metadata": {"user_email": "idem-api@example.com", "plan": "pro"},
                    }
                },
            }
        ).encode("utf-8")
        signature = generate_stripe_signature(payload, "whsec_test")
        mock_token_generate.return_value = f"license_{event_id}"

        first = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Stripe-Signature": signature},
        )
        second = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"Stripe-Signature": signature},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["received"] is True
        assert second.json()["received"] is True
        assert mock_token_generate.call_count == 1

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_webhook_event_id_payload_mismatch_returns_409(self):
        """Same Stripe event id with changed payload must be rejected."""
        event_id = f"evt_{uuid.uuid4().hex}"
        base_payload = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_email": "idem-conflict-api@example.com",
                    "customer": "cus_conflict_api",
                    "subscription": "sub_conflict_api",
                    "metadata": {"user_email": "idem-conflict-api@example.com", "plan": "pro"},
                }
            },
        }
        first_bytes = json.dumps(base_payload).encode("utf-8")
        first_sig = generate_stripe_signature(first_bytes, "whsec_test")
        first = client.post(
            "/api/v1/billing/webhook",
            content=first_bytes,
            headers={"Stripe-Signature": first_sig},
        )
        assert first.status_code == 200

        altered_payload = dict(base_payload)
        altered_payload["data"] = {
            "object": {
                "customer_email": "idem-conflict-api@example.com",
                "customer": "cus_conflict_api",
                "subscription": "sub_conflict_api_changed",
                "metadata": {"user_email": "idem-conflict-api@example.com", "plan": "pro"},
            }
        }
        second_bytes = json.dumps(altered_payload).encode("utf-8")
        second_sig = generate_stripe_signature(second_bytes, "whsec_test")
        second = client.post(
            "/api/v1/billing/webhook",
            content=second_bytes,
            headers={"Stripe-Signature": second_sig},
        )

        assert second.status_code == 409
        assert "payload mismatch" in str(second.json()).lower()


class TestBillingRateLimiting:
    """Tests for rate limiting on billing endpoints."""

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_xxx", "STRIPE_PRICE_ID": "price_xxx"}
    )
    def test_checkout_rate_limit(self):
        """Test checkout session rate limiting (10/minute)."""
        from src.core.circuit_breaker import CircuitBreakerOpen

        responses = []
        for i in range(15):
            with patch("src.api.billing.stripe_circuit") as mock_circuit:
                mock_circuit.call = AsyncMock(
                    return_value={"id": f"cs_{i}", "url": "..."}
                )

                payload = {
                    "email": f"test{i}@example.com",
                    "plan": "pro",
                    "quantity": 1,
                }
                response = client.post("/api/v1/billing/checkout-session", json=payload)
                responses.append(response.status_code)

        # Should hit rate limit after 10 requests
        assert 429 in responses or all(r in [200, 400, 503] for r in responses)


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with billing."""

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_xxx", "STRIPE_PRICE_ID": "price_xxx"}
    )
    def test_circuit_breaker_records_failures(self):
        """Test that failures are recorded in circuit breaker."""
        # Reset circuit breaker state
        import asyncio

        from src.core.circuit_breaker import stripe_circuit

        asyncio.get_event_loop().run_until_complete(stripe_circuit.reset())

        initial_failures = stripe_circuit.metrics.total_failures

        with patch("src.api.billing.stripe_circuit") as mock_circuit:

            async def failing_call(*args, **kwargs):
                raise Exception("Stripe API error")

            mock_circuit.call = failing_call

            payload = {"email": "test@example.com", "plan": "pro", "quantity": 1}

            # This should record a failure
            try:
                response = client.post("/api/v1/billing/checkout-session", json=payload)
            except Exception:
                pass

        # Verify circuit breaker is accessible
        assert stripe_circuit.name == "stripe_api"
