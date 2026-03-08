"""Unit tests for pure helper functions in src/api/maas_marketplace.py."""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch
import importlib
import sys

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Module loader — stubs all heavy dependencies
# ---------------------------------------------------------------------------

def _load_marketplace():
    stubs = {
        "src.database": MagicMock(),
        "src.api.maas_auth": MagicMock(),
        "src.core.reliability_policy": MagicMock(),
        "src.api.maas_telemetry": MagicMock(),
        "src.dao.token_bridge": MagicMock(),
        "src.dao.token": MagicMock(),
        "src.utils.audit": MagicMock(),
        "src.resilience.advanced_patterns": MagicMock(),
        "src.monitoring.maas_metrics": MagicMock(),
    }
    # reputation_system.get_proxy_trust returns None by default
    stubs["src.api.maas_telemetry"].reputation_system = MagicMock()
    stubs["src.api.maas_telemetry"].reputation_system.get_proxy_trust.return_value = None
    stubs["src.resilience.advanced_patterns"].get_resilient_executor.return_value = MagicMock()

    key = "src.api.maas_marketplace"
    if key in sys.modules:
        del sys.modules[key]
    with patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    return mod


_mod = _load_marketplace()

_env_flag = _mod._env_flag
_normalize_identity = _mod._normalize_identity
_ids_equal = _mod._ids_equal
_idempotency_compose_key = _mod._idempotency_compose_key
_normalize_idempotency_key = _mod._normalize_idempotency_key
_idempotency_get = _mod._idempotency_get
_idempotency_set = _mod._idempotency_set
_db_session_available = _mod._db_session_available
_is_dependency_placeholder = _mod._is_dependency_placeholder
_to_cents = _mod._to_cents
_to_dollars = _mod._to_dollars
_row_to_listing = _mod._row_to_listing


# ===========================================================================
# _env_flag
# ===========================================================================


class TestEnvFlag:
    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"])
    def test_truthy_values(self, value, monkeypatch):
        monkeypatch.setenv("TEST_FLAG", value)
        assert _env_flag("TEST_FLAG") is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "random"])
    def test_falsy_values(self, value, monkeypatch):
        monkeypatch.setenv("TEST_FLAG", value)
        assert _env_flag("TEST_FLAG") is False

    def test_missing_var_returns_default_false(self, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert _env_flag("TEST_FLAG") is False

    def test_missing_var_returns_custom_default(self, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert _env_flag("TEST_FLAG", default=True) is True

    def test_whitespace_trimmed(self, monkeypatch):
        monkeypatch.setenv("TEST_FLAG", "  true  ")
        assert _env_flag("TEST_FLAG") is True


# ===========================================================================
# _normalize_identity
# ===========================================================================


class TestNormalizeIdentity:
    def test_none_returns_empty_string(self):
        assert _normalize_identity(None) == ""

    def test_string_unchanged(self):
        assert _normalize_identity("user-123") == "user-123"

    def test_strips_whitespace(self):
        assert _normalize_identity("  abc  ") == "abc"

    def test_int_converted_to_string(self):
        assert _normalize_identity(42) == "42"

    def test_empty_string_returns_empty(self):
        assert _normalize_identity("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _normalize_identity("   ") == ""

    def test_uuid_string(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        assert _normalize_identity(uid) == uid


# ===========================================================================
# _ids_equal
# ===========================================================================


class TestIdsEqual:
    def test_equal_strings(self):
        assert _ids_equal("user-1", "user-1") is True

    def test_different_strings(self):
        assert _ids_equal("user-1", "user-2") is False

    def test_int_and_string_match(self):
        assert _ids_equal(42, "42") is True

    def test_int_and_string_no_match(self):
        assert _ids_equal(42, "43") is False

    def test_both_none_returns_false(self):
        assert _ids_equal(None, None) is False

    def test_left_none_returns_false(self):
        assert _ids_equal(None, "abc") is False

    def test_right_none_returns_false(self):
        assert _ids_equal("abc", None) is False

    def test_empty_left_returns_false(self):
        assert _ids_equal("", "abc") is False

    def test_empty_right_returns_false(self):
        assert _ids_equal("abc", "") is False

    def test_non_numeric_strings_compared_as_strings(self):
        # "abc" != "def"
        assert _ids_equal("abc", "def") is False

    def test_non_numeric_same_string(self):
        assert _ids_equal("abc", "abc") is True

    def test_mixed_int_string_non_numeric(self):
        # int + non-numeric string → int() fails → False
        assert _ids_equal(5, "xyz") is False


# ===========================================================================
# _idempotency_compose_key
# ===========================================================================


class TestIdempotencyComposeKey:
    def test_basic_composition(self):
        key = _idempotency_compose_key("rent", "listing-1", "user-99", "req-abc")
        assert key == "rent:listing-1:user-99:req-abc"

    def test_none_user_becomes_anonymous(self):
        key = _idempotency_compose_key("rent", "listing-1", None, "req-abc")
        assert "anonymous" in key

    def test_int_user_id_normalized(self):
        key = _idempotency_compose_key("release", "escrow-x", 7, "req-xyz")
        assert "7" in key

    def test_strips_idempotency_key_whitespace(self):
        key = _idempotency_compose_key("cancel", "scope", "u1", "  key-1  ")
        assert key.endswith(":key-1")


# ===========================================================================
# _normalize_idempotency_key
# ===========================================================================


class TestNormalizeIdempotencyKey:
    def test_valid_key_returned(self):
        assert _normalize_idempotency_key("valid-key-123") == "valid-key-123"

    def test_strips_whitespace(self):
        assert _normalize_idempotency_key("  my-key  ") == "my-key"

    def test_empty_string_returns_none(self):
        assert _normalize_idempotency_key("") is None

    def test_whitespace_only_returns_none(self):
        assert _normalize_idempotency_key("   ") is None

    def test_non_string_with_no_default_returns_none(self):
        assert _normalize_idempotency_key(12345) is None

    def test_object_with_default_string_attribute(self):
        obj = SimpleNamespace(default="valid-key")
        assert _normalize_idempotency_key(obj) == "valid-key"

    def test_object_with_empty_default_returns_none(self):
        obj = SimpleNamespace(default="  ")
        assert _normalize_idempotency_key(obj) is None

    def test_invalid_characters_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _normalize_idempotency_key("key with spaces")
        assert exc_info.value.status_code == 400

    def test_too_long_raises_400(self):
        max_len = _mod._IDEMPOTENCY_MAX_KEY_LEN
        long_key = "a" * (max_len + 1)
        with pytest.raises(HTTPException) as exc_info:
            _normalize_idempotency_key(long_key)
        assert exc_info.value.status_code == 400

    def test_exactly_max_len_is_accepted(self):
        max_len = _mod._IDEMPOTENCY_MAX_KEY_LEN
        key = "a" * max_len
        assert _normalize_idempotency_key(key) == key

    def test_dots_colons_allowed(self):
        assert _normalize_idempotency_key("key.name:scope") == "key.name:scope"


# ===========================================================================
# _idempotency_get / _idempotency_set
# ===========================================================================


class TestIdempotencyCache:
    def setup_method(self):
        # Clear the module-level idempotency cache before each test
        with _mod._idempotency_lock:
            _mod._idempotency_cache.clear()

    def test_set_then_get_returns_payload(self):
        _idempotency_set("k1", {"result": "ok"})
        result = _idempotency_get("k1")
        assert result == {"result": "ok"}

    def test_get_missing_key_returns_none(self):
        assert _idempotency_get("nonexistent") is None

    def test_payload_is_a_copy(self):
        payload = {"x": 1}
        _idempotency_set("k2", payload)
        retrieved = _idempotency_get("k2")
        retrieved["x"] = 999
        # Original should be unaffected
        assert _idempotency_get("k2")["x"] == 1

    def test_expired_entry_returns_none(self):
        orig_ttl = _mod._IDEMPOTENCY_TTL_SECONDS
        _mod._IDEMPOTENCY_TTL_SECONDS = 0  # expire immediately
        try:
            _idempotency_set("k3", {"v": 1})
            time.sleep(0.01)
            assert _idempotency_get("k3") is None
        finally:
            _mod._IDEMPOTENCY_TTL_SECONDS = orig_ttl

    def test_evicts_oldest_when_over_max_entries(self):
        orig_max = _mod._IDEMPOTENCY_MAX_ENTRIES
        _mod._IDEMPOTENCY_MAX_ENTRIES = 3
        try:
            for i in range(4):
                _idempotency_set(f"key-{i}", {"i": i})
            # key-0 should be evicted
            assert _idempotency_get("key-0") is None
            assert _idempotency_get("key-3") is not None
        finally:
            _mod._IDEMPOTENCY_MAX_ENTRIES = orig_max


# ===========================================================================
# _db_session_available
# ===========================================================================


class TestDbSessionAvailable:
    def test_real_sqlalchemy_session_like(self):
        db = MagicMock(spec=["query", "commit", "add", "flush"])
        assert _db_session_available(db) is True

    def test_missing_query_returns_false(self):
        db = SimpleNamespace(commit=lambda: None)
        assert _db_session_available(db) is False

    def test_missing_commit_returns_false(self):
        db = SimpleNamespace(query=lambda *a: None)
        assert _db_session_available(db) is False

    def test_none_returns_false(self):
        assert _db_session_available(None) is False

    def test_dict_returns_false(self):
        assert _db_session_available({}) is False


# ===========================================================================
# _to_cents / _to_dollars
# ===========================================================================


class TestPriceConversions:
    def test_to_cents_basic(self):
        assert _to_cents(1.0) == 100

    def test_to_cents_fractional(self):
        assert _to_cents(0.01) == 1

    def test_to_cents_rounding(self):
        # 1.005 * 100 = 100.5 → rounds to 101
        assert _to_cents(1.005) == 101

    def test_to_cents_zero(self):
        assert _to_cents(0.0) == 0

    def test_to_cents_large_value(self):
        assert _to_cents(999.99) == 99999

    def test_to_dollars_basic(self):
        assert _to_dollars(100) == pytest.approx(1.0)

    def test_to_dollars_small(self):
        assert _to_dollars(1) == pytest.approx(0.01)

    def test_to_dollars_zero(self):
        assert _to_dollars(0) == pytest.approx(0.0)

    def test_to_dollars_rounds_to_two_decimals(self):
        assert _to_dollars(150) == pytest.approx(1.50)

    def test_roundtrip_cents_dollars(self):
        original = 5.99
        assert _to_dollars(_to_cents(original)) == pytest.approx(original)


# ===========================================================================
# _row_to_listing
# ===========================================================================


class TestRowToListing:
    def _make_row(self, **kwargs):
        defaults = {
            "id": "lst-001",
            "owner_id": "u-abc",
            "node_id": "node-1",
            "region": "eu-central",
            "price_per_hour": 200,  # cents
            "price_token_per_hour": None,
            "currency": "USD",
            "bandwidth_mbps": 100,
            "status": "available",
            "renter_id": None,
            "mesh_id": "mesh-1",
            "created_at": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_basic_fields(self):
        row = self._make_row()
        result = _row_to_listing(row)
        assert result["listing_id"] == "lst-001"
        assert result["owner_id"] == "u-abc"
        assert result["node_id"] == "node-1"
        assert result["region"] == "eu-central"
        assert result["currency"] == "USD"
        assert result["bandwidth_mbps"] == 100
        assert result["status"] == "available"

    def test_price_converted_from_cents_to_dollars(self):
        row = self._make_row(price_per_hour=350)  # 350 cents = $3.50
        result = _row_to_listing(row)
        assert result["price_per_hour"] == pytest.approx(3.50)

    def test_price_per_hour_none_returns_zero(self):
        row = self._make_row(price_per_hour=None)
        result = _row_to_listing(row)
        assert result["price_per_hour"] == 0.0

    def test_renter_id_none_when_not_set(self):
        row = self._make_row(renter_id=None)
        result = _row_to_listing(row)
        assert result["renter_id"] is None

    def test_renter_id_normalized(self):
        row = self._make_row(renter_id="  u-999  ")
        result = _row_to_listing(row)
        assert result["renter_id"] == "u-999"

    def test_created_at_none_gives_fallback_isoformat(self):
        row = self._make_row(created_at=None)
        result = _row_to_listing(row)
        assert isinstance(result["created_at"], str)
        assert "T" in result["created_at"]

    def test_created_at_datetime_converted_to_isoformat(self):
        from datetime import datetime as dt
        ts = dt(2026, 3, 8, 12, 0, 0)
        row = self._make_row(created_at=ts)
        result = _row_to_listing(row)
        assert result["created_at"] == ts.isoformat()

    def test_owner_id_int_normalized_to_string(self):
        row = self._make_row(owner_id=42)
        result = _row_to_listing(row)
        assert result["owner_id"] == "42"

    def test_currency_defaults_to_usd(self):
        row = self._make_row(currency=None)
        result = _row_to_listing(row)
        assert result["currency"] == "USD"
