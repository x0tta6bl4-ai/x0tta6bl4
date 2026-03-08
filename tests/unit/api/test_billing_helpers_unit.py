"""
Unit tests for billing helper functions in src/api/maas/billing_helpers.py:
- IdempotencyRecord / IdempotencyStore
- calculate_node_cost / calculate_mesh_cost / estimate_monthly_cost
- format_currency
All tests are pure computation — no I/O, no network, no DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.api.maas.billing_helpers import (
    IdempotencyRecord,
    IdempotencyStore,
    calculate_mesh_cost,
    calculate_node_cost,
    estimate_monthly_cost,
    format_currency,
)


# ---------------------------------------------------------------------------
# IdempotencyRecord
# ---------------------------------------------------------------------------

class TestIdempotencyRecord:
    def test_new_record_not_expired(self):
        rec = IdempotencyRecord(key="k1", status="pending")
        assert rec.is_expired() is False

    def test_expired_record(self):
        old_time = datetime.utcnow() - timedelta(seconds=86401)
        rec = IdempotencyRecord(key="k2", status="pending", ttl_seconds=86400)
        rec.created_at = old_time
        assert rec.is_expired() is True

    def test_to_dict_contains_key_and_status(self):
        rec = IdempotencyRecord(key="k3", status="completed", result={"ok": True})
        d = rec.to_dict()
        assert d["key"] == "k3"
        assert d["status"] == "completed"
        assert d["result"] == {"ok": True}

    def test_to_dict_completed_at_none_when_not_set(self):
        rec = IdempotencyRecord(key="k4", status="pending")
        assert rec.to_dict()["completed_at"] is None

    def test_to_dict_completed_at_isoformat_when_set(self):
        rec = IdempotencyRecord(key="k5", status="completed")
        rec.completed_at = datetime(2026, 3, 8, 12, 0, 0)
        d = rec.to_dict()
        assert d["completed_at"] == "2026-03-08T12:00:00"

    def test_short_ttl_record_expires_quickly(self):
        rec = IdempotencyRecord(key="k6", status="pending", ttl_seconds=1)
        rec.created_at = datetime.utcnow() - timedelta(seconds=2)
        assert rec.is_expired() is True


# ---------------------------------------------------------------------------
# IdempotencyStore
# ---------------------------------------------------------------------------

class TestIdempotencyStore:
    def test_get_returns_none_for_unknown_key(self):
        store = IdempotencyStore()
        assert store.get("nonexistent") is None

    def test_set_pending_stores_record(self):
        store = IdempotencyStore()
        rec = store.set_pending("op-1")
        assert rec.status == "pending"
        assert rec.key == "op-1"
        assert store.get("op-1") is rec

    def test_set_completed_updates_existing_record(self):
        store = IdempotencyStore()
        store.set_pending("op-2")
        completed = store.set_completed("op-2", {"charge_id": "ch_abc"})
        assert completed.status == "completed"
        assert completed.result == {"charge_id": "ch_abc"}
        assert completed.completed_at is not None

    def test_set_completed_creates_record_if_missing(self):
        store = IdempotencyStore()
        rec = store.set_completed("op-3", {"result": "ok"})
        assert rec.status == "completed"
        assert rec.result == {"result": "ok"}

    def test_set_failed_updates_existing_record(self):
        store = IdempotencyStore()
        store.set_pending("op-4")
        failed = store.set_failed("op-4", "payment_declined")
        assert failed.status == "failed"
        assert failed.result == {"error": "payment_declined"}

    def test_set_failed_on_nonexistent_returns_none(self):
        store = IdempotencyStore()
        result = store.set_failed("ghost", "error")
        assert result is None

    def test_get_returns_none_for_expired_record(self):
        store = IdempotencyStore(default_ttl=1)
        store.set_pending("op-exp")
        # Manually expire the record
        store._records["op-exp"].created_at = datetime.utcnow() - timedelta(seconds=10)
        assert store.get("op-exp") is None
        # Record should also be removed from _records
        assert "op-exp" not in store._records

    def test_cleanup_expired_removes_old_records(self):
        store = IdempotencyStore(default_ttl=1)
        store.set_pending("old-1")
        store.set_pending("old-2")
        store.set_pending("fresh")

        # Expire the first two
        for key in ("old-1", "old-2"):
            store._records[key].created_at = datetime.utcnow() - timedelta(seconds=10)

        removed = store.cleanup_expired()
        assert removed == 2
        assert store.get("fresh") is not None
        assert "old-1" not in store._records
        assert "old-2" not in store._records

    def test_cleanup_with_no_expired_returns_zero(self):
        store = IdempotencyStore()
        store.set_pending("active-1")
        assert store.cleanup_expired() == 0

    def test_idempotency_lifecycle_pending_to_completed(self):
        store = IdempotencyStore()
        store.set_pending("lifecycle")
        rec = store.get("lifecycle")
        assert rec.status == "pending"
        store.set_completed("lifecycle", {"invoice_id": "inv_123"})
        rec = store.get("lifecycle")
        assert rec.status == "completed"
        assert rec.result["invoice_id"] == "inv_123"


# ---------------------------------------------------------------------------
# calculate_node_cost
# ---------------------------------------------------------------------------

class TestCalculateNodeCost:
    def test_standard_node_1_hour(self):
        cost = calculate_node_cost("standard", "starter", "global", 1.0)
        assert isinstance(cost, Decimal)
        assert cost > Decimal("0")

    def test_unknown_node_type_falls_back_to_standard(self):
        cost_unknown = calculate_node_cost("alien_type", "starter", "global", 1.0)
        cost_standard = calculate_node_cost("standard", "starter", "global", 1.0)
        assert cost_unknown == cost_standard

    def test_enterprise_plan_has_volume_discount_vs_pro(self):
        # Enterprise (0.6x) is cheaper per-node than pro (0.8x) — volume discount
        pro = calculate_node_cost("standard", "pro", "global", 1.0)
        enterprise = calculate_node_cost("standard", "enterprise", "global", 1.0)
        assert enterprise < pro

    def test_cost_scales_linearly_with_hours(self):
        one_hour = calculate_node_cost("standard", "starter", "global", 1.0)
        two_hours = calculate_node_cost("standard", "starter", "global", 2.0)
        assert two_hours == (one_hour * 2).quantize(Decimal("0.01"))

    def test_result_rounded_to_two_decimal_places(self):
        cost = calculate_node_cost("standard", "starter", "global", 3.0)
        # Decimal quantization: value should have at most 2 decimal places
        assert cost == cost.quantize(Decimal("0.01"))

    def test_zero_hours_returns_zero(self):
        cost = calculate_node_cost("standard", "starter", "global", 0.0)
        assert cost == Decimal("0.00")

    def test_regional_surcharge_increases_cost(self):
        global_cost = calculate_node_cost("standard", "starter", "global", 1.0)
        eu_cost = calculate_node_cost("standard", "starter", "eu-west", 1.0)
        # eu-west should have surcharge >= 1.0 (could be same or higher)
        assert eu_cost >= global_cost


# ---------------------------------------------------------------------------
# calculate_mesh_cost
# ---------------------------------------------------------------------------

class TestCalculateMeshCost:
    def test_mesh_cost_equals_node_count_times_node_cost(self):
        per_node = calculate_node_cost("standard", "pro", "global", 5.0)
        mesh_cost = calculate_mesh_cost(3, "standard", "pro", "global", 5.0)
        assert mesh_cost == per_node * 3

    def test_single_node_mesh_equals_node_cost(self):
        node_cost = calculate_node_cost("standard", "starter", "global", 1.0)
        mesh_cost = calculate_mesh_cost(1, "standard", "starter", "global", 1.0)
        assert mesh_cost == node_cost

    def test_zero_nodes_returns_zero(self):
        cost = calculate_mesh_cost(0, "standard", "starter", "global", 10.0)
        assert cost == Decimal("0.00")


# ---------------------------------------------------------------------------
# estimate_monthly_cost
# ---------------------------------------------------------------------------

class TestEstimateMonthlyCost:
    def test_uses_730_hours(self):
        monthly = estimate_monthly_cost(1, "standard", "starter", "global")
        direct = calculate_mesh_cost(1, "standard", "starter", "global", 730)
        assert monthly == direct

    def test_10_nodes_ten_times_1_node(self):
        one_node = estimate_monthly_cost(1, "standard", "starter", "global")
        ten_nodes = estimate_monthly_cost(10, "standard", "starter", "global")
        assert ten_nodes == one_node * 10


# ---------------------------------------------------------------------------
# format_currency
# ---------------------------------------------------------------------------

class TestFormatCurrency:
    def test_basic_format(self):
        assert format_currency(Decimal("12.50")) == "$12.50 USD"

    def test_custom_currency(self):
        assert format_currency(Decimal("99.99"), "EUR") == "$99.99 EUR"

    def test_zero_amount(self):
        assert format_currency(Decimal("0.00")) == "$0.00 USD"

    def test_large_amount(self):
        result = format_currency(Decimal("10000.00"))
        assert "10000.00" in result
