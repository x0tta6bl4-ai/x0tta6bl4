"""Unit tests for src/api/maas/billing_helpers.py and billing endpoint."""

import time
from decimal import Decimal

import pytest

from src.api.maas.billing_helpers import (
    IdempotencyStore,
    calculate_mesh_cost,
    calculate_node_cost,
    compute_hmac_signature,
    estimate_monthly_cost,
    format_currency,
    generate_invoice,
    verify_hmac_signature,
    verify_webhook_with_timestamp,
)


# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------


def test_compute_hmac_signature_returns_prefixed_hex():
    sig = compute_hmac_signature(b"payload", "secret")
    assert sig.startswith("sha256=")
    assert len(sig) == len("sha256=") + 64


def test_compute_hmac_signature_str_and_bytes_are_equal():
    assert compute_hmac_signature("hello", "s") == compute_hmac_signature(b"hello", "s")


def test_verify_hmac_signature_valid():
    sig = compute_hmac_signature(b"data", "mysecret")
    assert verify_hmac_signature(b"data", sig, "mysecret") is True


def test_verify_hmac_signature_wrong_payload():
    sig = compute_hmac_signature(b"data", "mysecret")
    assert verify_hmac_signature(b"other", sig, "mysecret") is False


def test_verify_hmac_signature_wrong_secret():
    sig = compute_hmac_signature(b"data", "secret1")
    assert verify_hmac_signature(b"data", sig, "secret2") is False


def test_verify_hmac_signature_without_prefix():
    # signature without "sha256=" prefix
    import hashlib
    import hmac as hmac_mod

    raw = hmac_mod.new(b"s", b"p", hashlib.sha256).hexdigest()
    assert verify_hmac_signature(b"p", raw, "s") is True


# ---------------------------------------------------------------------------
# Webhook timestamp verification
# ---------------------------------------------------------------------------


def test_verify_webhook_with_timestamp_valid():
    secret = "webhooksecret"
    ts = str(int(time.time()))
    payload = '{"type":"payment"}'
    signed = f"{ts}.{payload}"
    sig = compute_hmac_signature(signed, secret)
    assert verify_webhook_with_timestamp(payload.encode(), sig, ts, secret) is True


def test_verify_webhook_with_timestamp_expired():
    secret = "s"
    old_ts = str(int(time.time()) - 400)  # > 300s skew
    payload = b"body"
    signed = f"{old_ts}.body"
    sig = compute_hmac_signature(signed, secret)
    assert verify_webhook_with_timestamp(payload, sig, old_ts, secret) is False


def test_verify_webhook_with_timestamp_invalid_ts():
    assert verify_webhook_with_timestamp(b"x", "sig", "not-a-number", "s") is False


def test_verify_webhook_with_timestamp_wrong_sig():
    ts = str(int(time.time()))
    assert verify_webhook_with_timestamp(b"body", "sha256=bad", ts, "secret") is False


# ---------------------------------------------------------------------------
# Billing calculations
# ---------------------------------------------------------------------------


def test_calculate_node_cost_standard_free_us_east():
    # 0.05 * 1.0 * 1.0 * 10h = 0.50
    cost = calculate_node_cost("standard", "free", "us-east-1", 10)
    assert cost == Decimal("0.50")


def test_calculate_node_cost_enterprise_discount():
    # enterprise = 0.6 multiplier → 0.05 * 0.6 * 1.0 * 10 = 0.30
    cost = calculate_node_cost("standard", "enterprise", "us-east-1", 10)
    assert cost == Decimal("0.30")


def test_calculate_node_cost_eu_region_surcharge():
    # eu-central-1 surcharge = 1.1 → 0.05 * 1.0 * 1.1 * 10 = 0.55
    cost = calculate_node_cost("standard", "free", "eu-central-1", 10)
    assert cost == Decimal("0.55")


def test_calculate_node_cost_unknown_type_falls_back_to_standard():
    cost_std = calculate_node_cost("standard", "free", "us-east-1", 1)
    cost_unk = calculate_node_cost("nonexistent_type", "free", "us-east-1", 1)
    assert cost_std == cost_unk


def test_calculate_mesh_cost_multiplies_nodes():
    single = calculate_node_cost("standard", "pro", "us-east-1", 5)
    mesh = calculate_mesh_cost(3, "standard", "pro", "us-east-1", 5)
    assert mesh == single * 3


def test_estimate_monthly_cost_uses_730_hours():
    monthly = estimate_monthly_cost(1, "standard", "free", "us-east-1")
    expected = calculate_mesh_cost(1, "standard", "free", "us-east-1", 730)
    assert monthly == expected


def test_format_currency_formats_correctly():
    assert format_currency(Decimal("12.50")) == "$12.50 USD"
    assert format_currency(Decimal("0.00")) == "$0.00 USD"


# ---------------------------------------------------------------------------
# Invoice generation
# ---------------------------------------------------------------------------


def test_generate_invoice_structure():
    invoice = generate_invoice(
        customer_id="cust-1",
        mesh_usage=[
            {
                "mesh_id": "mesh-abc",
                "node_count": 2,
                "node_type": "standard",
                "plan": "pro",
                "region": "us-east-1",
                "hours": 10,
            }
        ],
    )
    d = invoice.to_dict()
    assert d["customer_id"] == "cust-1"
    assert d["invoice_id"].startswith("inv-")
    assert len(d["line_items"]) == 1
    assert Decimal(d["subtotal"]) > 0
    assert Decimal(d["tax"]) == Decimal("0")
    assert Decimal(d["total"]) == Decimal(d["subtotal"])


def test_generate_invoice_with_tax():
    invoice = generate_invoice(
        customer_id="cust-2",
        mesh_usage=[
            {
                "mesh_id": "m1",
                "node_count": 1,
                "node_type": "standard",
                "plan": "free",
                "region": "us-east-1",
                "hours": 100,
            }
        ],
        tax_rate=Decimal("0.10"),
    )
    d = invoice.to_dict()
    subtotal = Decimal(d["subtotal"])
    tax = Decimal(d["tax"])
    total = Decimal(d["total"])
    assert tax == (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    assert total == subtotal + tax


def test_generate_invoice_multiple_meshes():
    invoice = generate_invoice(
        customer_id="cust-3",
        mesh_usage=[
            {"mesh_id": "m1", "node_count": 1, "node_type": "standard",
             "plan": "free", "region": "us-east-1", "hours": 1},
            {"mesh_id": "m2", "node_count": 1, "node_type": "gpu",
             "plan": "free", "region": "us-east-1", "hours": 1},
        ],
    )
    d = invoice.to_dict()
    assert len(d["line_items"]) == 2
    assert Decimal(d["subtotal"]) > 0


def test_generate_invoice_ids_are_unique():
    i1 = generate_invoice("c", [{"mesh_id": "m", "node_count": 1,
                                  "node_type": "standard", "plan": "free",
                                  "region": "us-east-1", "hours": 1}])
    i2 = generate_invoice("c", [{"mesh_id": "m", "node_count": 1,
                                  "node_type": "standard", "plan": "free",
                                  "region": "us-east-1", "hours": 1}])
    assert i1.invoice_id != i2.invoice_id


# ---------------------------------------------------------------------------
# IdempotencyStore
# ---------------------------------------------------------------------------


def test_idempotency_store_pending_then_completed():
    store = IdempotencyStore()
    key = "op-123"

    store.set_pending(key)
    rec = store.get(key)
    assert rec is not None
    assert rec.status == "pending"

    store.set_completed(key, {"result": "ok"})
    rec = store.get(key)
    assert rec.status == "completed"
    assert rec.result == {"result": "ok"}


def test_idempotency_store_missing_key_returns_none():
    store = IdempotencyStore()
    assert store.get("nonexistent") is None


def test_idempotency_store_set_failed():
    store = IdempotencyStore()
    store.set_pending("k")
    store.set_failed("k", "boom")
    rec = store.get("k")
    assert rec.status == "failed"
    assert rec.result["error"] == "boom"


def test_idempotency_store_cleanup_expired():
    from datetime import timedelta

    store = IdempotencyStore(default_ttl=0)
    store.set_pending("old")
    # Force expiry by backdating created_at
    store._records["old"].created_at -= timedelta(seconds=1)
    removed = store.cleanup_expired()
    assert removed == 1
    assert store.get("old") is None


def test_idempotency_record_to_dict_shape():
    store = IdempotencyStore()
    store.set_pending("x")
    store.set_completed("x", {"v": 1})
    d = store.get("x").to_dict()
    assert "key" in d
    assert "status" in d
    assert "result" in d
    assert d["status"] == "completed"
