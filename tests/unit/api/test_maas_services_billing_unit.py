import asyncio
import hashlib
import hmac
import time

from src.api.maas.services import AuthService, BillingService


def _signature(secret: str, payload: bytes, timestamp: str | None = None, with_prefix: bool = True) -> str:
    message = payload if timestamp is None else f"{timestamp}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}" if with_prefix else digest


def test_verify_webhook_signature_with_timestamp():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    timestamp = str(int(time.time()))
    signature = _signature(secret, payload, timestamp=timestamp, with_prefix=True)
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature, timestamp=timestamp) is True


def test_verify_webhook_signature_accepts_unprefixed_digest():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    signature = _signature(secret, payload, with_prefix=False)
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature) is True


def test_verify_webhook_signature_rejects_timestamp_outside_skew():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    timestamp = str(int(time.time()) + 1200)
    signature = _signature(secret, payload, timestamp=timestamp, with_prefix=True)
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature, timestamp=timestamp) is False


def test_verify_webhook_signature_provider_header_uses_embedded_timestamp():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    timestamp = str(int(time.time()))
    digest = _signature(secret, payload, timestamp=timestamp, with_prefix=False)
    signature = f"t={timestamp},v1=deadbeef,v1={digest}"
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature) is True


def test_verify_webhook_signature_provider_header_rejects_when_no_v1_matches():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    timestamp = str(int(time.time()))
    signature = f"t={timestamp},v1=deadbeef,v1=badbad"
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature) is False


def test_verify_webhook_signature_provider_header_rejects_invalid_timestamp():
    secret = "test-webhook-secret"
    payload = b'{"type":"invoice.paid","data":{"customer_id":"cus_1"}}'
    digest = _signature(secret, payload, with_prefix=False)
    signature = f"t=not-a-number,v1={digest}"
    billing = BillingService(webhook_secret=secret)

    assert billing.verify_webhook_signature(payload, signature) is False


def test_process_webhook_handles_invoice_paid():
    billing = BillingService(webhook_secret="test")

    result = asyncio.run(
        billing.process_webhook(
            event_type="invoice.paid",
            event_data={"customer_id": "cus_123", "amount": 42},
            event_id="evt_1",
        )
    )

    assert result["status"] == "processed"
    assert result["action"] == "subscription_extended"
    assert result["customer_id"] == "cus_123"


def test_process_webhook_normalizes_legacy_subscription_event_name():
    billing = BillingService(webhook_secret="test")

    result = asyncio.run(
        billing.process_webhook(
            event_type="subscription.updated",
            event_data={"customer_id": "cus_123", "plan": "pro"},
            event_id="evt_2",
        )
    )

    assert result["status"] == "processed"
    assert result["action"] == "plan_updated"
    assert result["customer_id"] == "cus_123"
    assert result["new_plan"] == "pro"


def test_process_webhook_idempotency_returns_cached_result():
    billing = BillingService(webhook_secret="test")
    first = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_first", "attempt": 1},
            event_id="evt_same",
        )
    )
    second = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_second", "attempt": 999},
            event_id="evt_same",
        )
    )

    assert first == second
    assert second["customer_id"] == "cus_first"
    assert second["attempt"] == 1


def test_process_webhook_idempotency_metadata_flag():
    billing = BillingService(webhook_secret="test")
    first = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_meta", "attempt": 1},
            event_id="evt_meta",
            include_idempotency_metadata=True,
        )
    )
    second = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_other", "attempt": 9},
            event_id="evt_meta",
            include_idempotency_metadata=True,
        )
    )

    assert first["_idempotent"] is False
    assert second["_idempotent"] is True
    assert second["customer_id"] == "cus_meta"
    assert second["attempt"] == 1


def test_process_webhook_unknown_event_is_ignored():
    billing = BillingService(webhook_secret="test")

    result = asyncio.run(
        billing.process_webhook(
            event_type="totally.unknown.event",
            event_data={},
            event_id="evt_unknown",
        )
    )

    assert result["status"] == "ignored"
    assert result["reason"] == "unknown_event_type"


def test_process_webhook_idempotency_cache_expires():
    billing = BillingService(webhook_secret="test")
    first = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_first", "attempt": 1},
            event_id="evt_expire",
        )
    )
    assert first["customer_id"] == "cus_first"

    # Force immediate expiration to ensure stale cached values are not reused.
    billing._idempotency_ttl_seconds = 0
    second = asyncio.run(
        billing.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_second", "attempt": 2},
            event_id="evt_expire",
        )
    )

    assert second["customer_id"] == "cus_second"
    assert second["attempt"] == 2


def test_process_webhook_idempotency_cache_evicts_oldest_entry():
    billing = BillingService(webhook_secret="test")
    billing._idempotency_max_entries = 2

    asyncio.run(
        billing.process_webhook(
            event_type="invoice.paid",
            event_data={"customer_id": "cus_a", "amount": 1},
            event_id="evt_a",
        )
    )
    asyncio.run(
        billing.process_webhook(
            event_type="invoice.paid",
            event_data={"customer_id": "cus_b", "amount": 2},
            event_id="evt_b",
        )
    )
    asyncio.run(
        billing.process_webhook(
            event_type="invoice.paid",
            event_data={"customer_id": "cus_c", "amount": 3},
            event_id="evt_c",
        )
    )

    assert list(billing._idempotency_cache.keys()) == ["evt_b", "evt_c"]


class _SharedStateFake:
    def __init__(self):
        self._store = {}

    def get_json(self, key):
        value = self._store.get(key)
        return dict(value) if isinstance(value, dict) else None

    def set_json(self, key, value, ttl_seconds=None):
        self._store[key] = dict(value)
        return True

    def delete(self, key):
        return self._store.pop(key, None) is not None


def test_process_webhook_idempotency_is_shared_across_instances():
    shared = _SharedStateFake()
    billing_a = BillingService(webhook_secret="test", shared_state=shared)
    billing_b = BillingService(webhook_secret="test", shared_state=shared)

    first = asyncio.run(
        billing_a.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_a", "attempt": 1},
            event_id="evt_shared",
        )
    )
    second = asyncio.run(
        billing_b.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_b", "attempt": 999},
            event_id="evt_shared",
        )
    )

    assert first == second
    assert second["customer_id"] == "cus_a"
    assert second["attempt"] == 1


def test_process_webhook_idempotency_metadata_is_shared_across_instances():
    shared = _SharedStateFake()
    billing_a = BillingService(webhook_secret="test", shared_state=shared)
    billing_b = BillingService(webhook_secret="test", shared_state=shared)

    first = asyncio.run(
        billing_a.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_a", "attempt": 1},
            event_id="evt_shared_meta",
            include_idempotency_metadata=True,
        )
    )
    second = asyncio.run(
        billing_b.process_webhook(
            event_type="invoice.payment_failed",
            event_data={"customer_id": "cus_b", "attempt": 999},
            event_id="evt_shared_meta",
            include_idempotency_metadata=True,
        )
    )

    assert first["_idempotent"] is False
    assert second["_idempotent"] is True
    assert second["customer_id"] == "cus_a"
    assert second["attempt"] == 1


def test_auth_service_shared_api_keys_work_across_instances():
    shared = _SharedStateFake()
    auth_a = AuthService(api_key_secret="test", shared_state=shared)
    auth_b = AuthService(api_key_secret="test", shared_state=shared)

    api_key = auth_a.generate_api_key(user_id="u1", plan="pro")
    validated = auth_b.validate_api_key(api_key)

    assert validated is not None
    assert validated["user_id"] == "u1"
    assert validated["plan"] == "pro"
    assert validated["request_count"] == 1


def test_auth_service_shared_sessions_work_across_instances():
    shared = _SharedStateFake()
    auth_a = AuthService(api_key_secret="test", shared_state=shared)
    auth_b = AuthService(api_key_secret="test", shared_state=shared)

    token = auth_a.create_session(user_id="u1", ttl_hours=1)
    assert auth_b.validate_session(token) is not None
    assert auth_b.end_session(token) is True
    assert auth_a.validate_session(token) is None
