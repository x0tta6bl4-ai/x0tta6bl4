"""Unit tests for pure helpers in src/api/maas_dashboard.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# Load module with DB / auth stubs so no side-effects at import time
# ---------------------------------------------------------------------------

def _load_dashboard():
    stubs = {
        "redis": MagicMock(),
        "src.database": MagicMock(),
        "src.api.maas_auth": MagicMock(),
        "src.resilience.advanced_patterns": MagicMock(),
        "src.core.cache": MagicMock(),
    }
    # Avoid re-use of cached module across other test sessions
    key = "src.api.maas_dashboard"
    if key in sys.modules:
        del sys.modules[key]
    with patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    return mod


_mod = _load_dashboard()

_node_attestation_type = _mod._node_attestation_type
_node_health = _mod._node_health
STALE_THRESHOLD = _mod._STALE_THRESHOLD_MINUTES


def _node(
    hardware_id=None,
    enclave_enabled=False,
    last_seen=None,
):
    """Build a minimal mock MeshNode."""
    n = SimpleNamespace(
        id="node-test-001",
        hardware_id=hardware_id,
        enclave_enabled=enclave_enabled,
        last_seen=last_seen,
    )
    return n


# ===========================================================================
# _node_attestation_type
# ===========================================================================


class TestNodeAttestationType:
    def _mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        return db

    def test_hardware_rooted_when_both_set(self):
        node = _node(hardware_id="tpm-abc", enclave_enabled=True)
        result = _node_attestation_type(node, self._mock_db())
        assert result["hardware"] == "HARDWARE_ROOTED"

    def test_software_only_when_no_hardware_id(self):
        node = _node(hardware_id=None, enclave_enabled=True)
        result = _node_attestation_type(node, self._mock_db())
        assert result["hardware"] == "SOFTWARE_ONLY"

    def test_software_only_when_enclave_disabled(self):
        node = _node(hardware_id="tpm-abc", enclave_enabled=False)
        result = _node_attestation_type(node, self._mock_db())
        assert result["hardware"] == "SOFTWARE_ONLY"

    def test_software_only_when_both_absent(self):
        node = _node(hardware_id=None, enclave_enabled=False)
        result = _node_attestation_type(node, self._mock_db())
        assert result["hardware"] == "SOFTWARE_ONLY"

    def test_empty_string_hardware_id_is_software_only(self):
        # Empty string is falsy
        node = _node(hardware_id="", enclave_enabled=True)
        result = _node_attestation_type(node, self._mock_db())
        assert result["hardware"] == "SOFTWARE_ONLY"

    def test_hardware_rooted_with_various_id_formats(self):
        for hw_id in ("tpm-001", "hsm-xyz", "123456"):
            node = _node(hardware_id=hw_id, enclave_enabled=True)
            result = _node_attestation_type(node, self._mock_db())
            assert result["hardware"] == "HARDWARE_ROOTED"


# ===========================================================================
# _node_health
# ===========================================================================


class TestNodeHealth:
    def _utcnow(self):
        return datetime.utcnow()

    def test_healthy_when_last_seen_within_threshold(self):
        # Just seen 1 minute ago — well within 5-minute threshold
        node = _node(last_seen=self._utcnow() - timedelta(minutes=1))
        assert _node_health(node) == "healthy"

    def test_healthy_at_near_threshold(self):
        # Just under threshold (1 second margin for clock drift)
        node = _node(last_seen=self._utcnow() - timedelta(minutes=STALE_THRESHOLD - 1))
        assert _node_health(node) == "healthy"

    def test_stale_past_threshold(self):
        # Well past threshold → stale
        node = _node(last_seen=self._utcnow() - timedelta(minutes=STALE_THRESHOLD + 1))
        assert _node_health(node) == "stale"

    def test_stale_at_twenty_minutes(self):
        node = _node(last_seen=self._utcnow() - timedelta(minutes=20))
        assert _node_health(node) == "stale"

    def test_stale_at_twenty_nine_minutes(self):
        # Well within stale range
        node = _node(last_seen=self._utcnow() - timedelta(minutes=29))
        assert _node_health(node) == "stale"

    def test_offline_past_thirty_minutes(self):
        node = _node(last_seen=self._utcnow() - timedelta(minutes=31))
        assert _node_health(node) == "offline"

    def test_offline_at_one_hour(self):
        node = _node(last_seen=self._utcnow() - timedelta(hours=1))
        assert _node_health(node) == "offline"

    def test_offline_at_one_day(self):
        node = _node(last_seen=self._utcnow() - timedelta(days=1))
        assert _node_health(node) == "offline"

    def test_unknown_when_last_seen_is_none(self):
        node = _node(last_seen=None)
        assert _node_health(node) == "unknown"

    def test_healthy_just_seen(self):
        node = _node(last_seen=self._utcnow() - timedelta(seconds=5))
        assert _node_health(node) == "healthy"

    def test_return_values_are_strings(self):
        for minutes, expected in [
            (1, "healthy"),
            (10, "stale"),
            (60, "offline"),
        ]:
            node = _node(last_seen=self._utcnow() - timedelta(minutes=minutes))
            result = _node_health(node)
            assert isinstance(result, str)
            assert result == expected
