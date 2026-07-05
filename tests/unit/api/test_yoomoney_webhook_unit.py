"""Unit tests for YooMoney webhook endpoint."""

import hashlib
import hmac
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestYoomoneySignatureVerification:
    """Tests for YooMoney HMAC-SHA1 signature verification."""

    def test_valid_signature(self):
        from src.api.billing import _verify_yoomoney_signature

        secret = "test_secret_key"
        params = {
            "notification_type": "p2p-incoming",
            "operation_id": "12345678",
            "amount": "100.00",
            "label": "yoomoney_checkout:pay_001:premium",
            "datetime": "2026-07-05T10:00:00Z",
            "sender": "card*1234",
            "codepro": "false",
        }

        sorted_keys = sorted(k for k in params if k != "sha1_hash")
        data = "".join(params[k] for k in sorted_keys)
        expected_hash = hmac.new(
            secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha1
        ).hexdigest()
        params["sha1_hash"] = expected_hash

        assert _verify_yoomoney_signature(params, secret) is True

    def test_invalid_signature(self):
        from src.api.billing import _verify_yoomoney_signature

        params = {
            "notification_type": "p2p-incoming",
            "operation_id": "12345678",
            "amount": "100.00",
            "sha1_hash": "invalid_hash",
        }
        assert _verify_yoomoney_signature(params, "secret") is False

    def test_missing_signature(self):
        from src.api.billing import _verify_yoomoney_signature

        params = {
            "notification_type": "p2p-incoming",
            "operation_id": "12345678",
        }
        assert _verify_yoomoney_signature(params, "secret") is False


class TestYoomoneyNetToGross:
    """Tests for YooMoney net-to-gross conversion."""

    def test_net_to_gross_basic(self):
        from src.api.billing import _yoomoney_net_to_gross

        # 97.00 net → 100.00 gross (3% commission)
        assert _yoomoney_net_to_gross(Decimal("97.00")) == Decimal("100.00")

    def test_net_to_gross_small_amount(self):
        from src.api.billing import _yoomoney_net_to_gross

        # 29.10 net → 30.00 gross
        assert _yoomoney_net_to_gross(Decimal("29.10")) == Decimal("30.00")

    def test_net_to_gross_rounding(self):
        from src.api.billing import _yoomoney_net_to_gross

        # 48.50 net → 50.00 gross
        assert _yoomoney_net_to_gross(Decimal("48.50")) == Decimal("50.00")


class TestYoomoneyAmountMatching:
    """Tests for YooMoney amount matching logic."""

    def test_exact_match(self):
        from src.api.billing import _yoomoney_amount_matches

        assert _yoomoney_amount_matches(Decimal("100.00"), Decimal("100.00")) is True

    def test_net_matches_gross_after_fee(self):
        from src.api.billing import _yoomoney_amount_matches

        # 100.00 gross, 97.00 net (after 3% fee)
        assert _yoomoney_amount_matches(Decimal("100.00"), Decimal("97.00")) is True

    def test_small_rounding_difference(self):
        from src.api.billing import _yoomoney_amount_matches

        # 100.00 gross, 96.99 net (rounding)
        assert _yoomoney_amount_matches(Decimal("100.00"), Decimal("96.99")) is True

    def test_large_difference_fails(self):
        from src.api.billing import _yoomoney_amount_matches

        # 100.00 gross, 90.00 net (too large difference)
        assert _yoomoney_amount_matches(Decimal("100.00"), Decimal("90.00")) is False


class TestYoomoneyWebhookEndpoint:
    """Tests for the webhook endpoint itself."""

    def test_endpoint_exists(self):
        from src.api.billing import router

        routes = [r.path for r in router.routes]
        assert "/api/v1/billing/webhook/yoomoney" in routes

    def test_endpoint_method(self):
        from src.api.billing import router

        for route in router.routes:
            if route.path == "/api/v1/billing/webhook/yoomoney":
                assert "POST" in route.methods
                break
