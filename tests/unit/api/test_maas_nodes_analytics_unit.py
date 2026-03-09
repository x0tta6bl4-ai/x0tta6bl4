"""Unit tests for analytics/telemetry helpers in src/api/maas_nodes.py."""

from __future__ import annotations

import sys
import importlib
from typing import Any, Dict, Optional
from unittest import mock

import pytest

# Pre-import so patch.dict teardown does not evict these modules
import src.core.rbac  # noqa: F401


# ---------------------------------------------------------------------------
# Module load — stub heavy dependencies
# ---------------------------------------------------------------------------

def _load_nodes_module():
    stubs = {
        "src.database": mock.MagicMock(),
        "src.api.maas_auth": mock.MagicMock(),
        "src.api.maas_telemetry": mock.MagicMock(),
        "src.mesh.network_manager": mock.MagicMock(),
        "src.monitoring.maas_metrics": mock.MagicMock(),
        "src.utils.audit": mock.MagicMock(),
    }
    key = "src.api.maas_nodes"
    if key in sys.modules:
        del sys.modules[key]
    with mock.patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    return mod


_mod = _load_nodes_module()
_build_analytics_telemetry_payload = _mod._build_analytics_telemetry_payload
_export_analytics_telemetry = _mod._export_analytics_telemetry
_read_external_telemetry = _mod._read_external_telemetry
_read_external_telemetry_history = _mod._read_external_telemetry_history
HeartbeatRequest = _mod.HeartbeatRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(**kwargs) -> HeartbeatRequest:
    """Build a HeartbeatRequest with sensible defaults."""
    defaults: Dict[str, Any] = {"status": "healthy"}
    defaults.update(kwargs)
    return HeartbeatRequest(**defaults)


# ---------------------------------------------------------------------------
# _build_analytics_telemetry_payload
# ---------------------------------------------------------------------------


class TestBuildAnalyticsTelemetryPayload:
    TS = "2026-03-09T00:00:00Z"

    def test_base_fields_always_present(self):
        req = _req()
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["mesh_id"] == "m1"
        assert result["node_id"] == "n1"
        assert result["status"] == "healthy"
        assert result["timestamp"] == self.TS
        assert result["last_seen"] == self.TS

    def test_latency_from_req_field(self):
        req = _req(latency_ms=12.5)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["latency_ms"] == pytest.approx(12.5)

    def test_latency_from_custom_metrics_when_req_none(self):
        req = _req(custom_metrics={"latency_ms": 7.0})
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["latency_ms"] == pytest.approx(7.0)

    def test_req_latency_takes_priority_over_custom_metrics(self):
        req = _req(latency_ms=5.0, custom_metrics={"latency_ms": 99.0})
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["latency_ms"] == pytest.approx(5.0)

    def test_negative_latency_excluded(self):
        req = _req(latency_ms=-1.0)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert "latency_ms" not in result

    def test_zero_latency_included(self):
        req = _req(latency_ms=0.0)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["latency_ms"] == pytest.approx(0.0)

    def test_traffic_from_req_field(self):
        req = _req(traffic_mbps=100.5)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["traffic_mbps"] == pytest.approx(100.5)

    def test_traffic_from_custom_metrics_when_req_none(self):
        req = _req(custom_metrics={"traffic_mbps": 50.0})
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["traffic_mbps"] == pytest.approx(50.0)

    def test_negative_traffic_excluded(self):
        req = _req(traffic_mbps=-10.0)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert "traffic_mbps" not in result

    def test_no_latency_or_traffic_when_none(self):
        req = _req()
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert "latency_ms" not in result
        assert "traffic_mbps" not in result

    def test_cpu_and_mem_passed_through(self):
        req = _req(cpu_percent=42.0, mem_percent=78.5)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["cpu_percent"] == pytest.approx(42.0)
        assert result["mem_percent"] == pytest.approx(78.5)

    def test_active_connections_passed_through(self):
        req = _req(active_connections=17)
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["active_connections"] == 17

    def test_custom_metrics_embedded_in_result(self):
        req = _req(custom_metrics={"foo": "bar", "baz": 42})
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["custom_metrics"]["foo"] == "bar"
        assert result["custom_metrics"]["baz"] == 42

    def test_none_custom_metrics_stored_as_empty_dict(self):
        req = _req()
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["custom_metrics"] == {}

    def test_degraded_status(self):
        req = _req(status="degraded")
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["status"] == "degraded"

    def test_unhealthy_status(self):
        req = _req(status="unhealthy")
        result = _build_analytics_telemetry_payload("m1", "n1", req, self.TS)
        assert result["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# _export_analytics_telemetry
# ---------------------------------------------------------------------------


class TestExportAnalyticsTelemetry:
    def test_returns_false_when_set_external_none(self):
        with mock.patch.object(_mod, "_set_external_telemetry", None):
            assert _export_analytics_telemetry("n1", {"k": "v"}) is False

    def test_returns_true_on_success(self):
        mock_setter = mock.MagicMock()
        with mock.patch.object(_mod, "_set_external_telemetry", mock_setter):
            result = _export_analytics_telemetry("n1", {"k": "v"})
        assert result is True
        mock_setter.assert_called_once_with("n1", {"k": "v"})

    def test_returns_false_on_exception(self):
        mock_setter = mock.MagicMock(side_effect=RuntimeError("boom"))
        with mock.patch.object(_mod, "_set_external_telemetry", mock_setter):
            result = _export_analytics_telemetry("n1", {})
        assert result is False


# ---------------------------------------------------------------------------
# _read_external_telemetry
# ---------------------------------------------------------------------------


class TestReadExternalTelemetry:
    def test_returns_empty_dict_when_getter_none(self):
        with mock.patch.object(_mod, "_get_external_telemetry", None):
            assert _read_external_telemetry("n1") == {}

    def test_returns_normalised_dict_on_success(self):
        mock_getter = mock.MagicMock(return_value={"latency": 5.0, "status": " UP "})
        with mock.patch.object(_mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("n1")
        assert result["latency_ms"] == pytest.approx(5.0)
        assert result["status"] == "up"

    def test_returns_empty_dict_when_getter_returns_non_dict(self):
        mock_getter = mock.MagicMock(return_value=[1, 2, 3])
        with mock.patch.object(_mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("n1")
        assert result == {}

    def test_returns_empty_dict_when_getter_raises(self):
        mock_getter = mock.MagicMock(side_effect=Exception("redis down"))
        with mock.patch.object(_mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("n1")
        assert result == {}

    def test_returns_empty_dict_when_getter_returns_none(self):
        mock_getter = mock.MagicMock(return_value=None)
        with mock.patch.object(_mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("n1")
        assert result == {}


# ---------------------------------------------------------------------------
# _read_external_telemetry_history
# ---------------------------------------------------------------------------


class TestReadExternalTelemetryHistory:
    def test_returns_empty_list_when_getter_none(self):
        with mock.patch.object(_mod, "_get_external_telemetry_history", None):
            assert _read_external_telemetry_history("n1", 10) == []

    def test_returns_normalised_list_on_success(self):
        raw = [{"latency": 3.0}, {"status": " ACTIVE "}]
        mock_getter = mock.MagicMock(return_value=raw)
        with mock.patch.object(_mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("n1", 5)
        assert result[0]["latency_ms"] == pytest.approx(3.0)
        assert result[1]["status"] == "active"

    def test_non_dict_items_filtered_out(self):
        raw = [{"latency": 1.0}, "bad", None, {"latency": 2.0}]
        mock_getter = mock.MagicMock(return_value=raw)
        with mock.patch.object(_mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("n1", 10)
        assert len(result) == 2

    def test_returns_empty_list_when_getter_raises(self):
        mock_getter = mock.MagicMock(side_effect=Exception("timeout"))
        with mock.patch.object(_mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("n1", 5)
        assert result == []

    def test_returns_empty_list_when_getter_returns_non_list(self):
        mock_getter = mock.MagicMock(return_value={"bad": "response"})
        with mock.patch.object(_mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("n1", 5)
        assert result == []

    def test_limit_passed_to_getter(self):
        mock_getter = mock.MagicMock(return_value=[])
        with mock.patch.object(_mod, "_get_external_telemetry_history", mock_getter):
            _read_external_telemetry_history("n1", 42)
        mock_getter.assert_called_once_with("n1", limit=42)
