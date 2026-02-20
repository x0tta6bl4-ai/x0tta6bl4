"""Unit tests for eBPF Enhanced Metrics Exporter."""
import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.metrics_exporter_enhanced import (
    MetricValidationStatus,
    MetricValidationResult,
    ErrorCount,
    MetricSanitizer,
    EBPFMetricsExporterEnhanced,
)


class TestMetricValidationStatus:
    def test_values(self):
        assert MetricValidationStatus.VALID.value == "valid"
        assert MetricValidationStatus.INVALID.value == "invalid"
        assert MetricValidationStatus.OUT_OF_RANGE.value == "out_of_range"
        assert MetricValidationStatus.TYPE_MISMATCH.value == "type_mismatch"


class TestMetricValidationResult:
    def test_basic(self):
        r = MetricValidationResult(name="test", value=42, status=MetricValidationStatus.VALID)
        assert r.name == "test"
        assert r.value == 42
        assert r.status == MetricValidationStatus.VALID
        assert r.message is None

    def test_with_message(self):
        r = MetricValidationResult(
            name="x", value="bad", status=MetricValidationStatus.TYPE_MISMATCH,
            message="wrong type", expected_type=int,
        )
        assert r.message == "wrong type"
        assert r.expected_type is int

    def test_with_range(self):
        r = MetricValidationResult(
            name="y", value=-1, status=MetricValidationStatus.OUT_OF_RANGE,
            range_min=0, range_max=100,
        )
        assert r.range_min == 0
        assert r.range_max == 100


class TestErrorCount:
    def test_defaults(self):
        ec = ErrorCount()
        assert ec.total == 0
        assert ec.map_read == 0
        assert ec.bpftool == 0
        assert ec.parsing == 0
        assert ec.validation == 0
        assert ec.export == 0
        assert ec.timeout == 0

    def test_custom(self):
        ec = ErrorCount(total=5, map_read=2)
        assert ec.total == 5
        assert ec.map_read == 2


class TestMetricSanitizer:
    def test_default_rules(self):
        s = MetricSanitizer()
        assert "packet_counters" in s.validation_rules
        assert "latency_ms" in s.validation_rules

    def test_custom_rules(self):
        rules = {"custom": {"min": 0, "max": 10, "type": int}}
        s = MetricSanitizer(validation_rules=rules)
        assert "custom" in s.validation_rules

    def test_validate_exact_match(self):
        s = MetricSanitizer()
        r = s.validate("packet_counters", 100)
        assert r.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_packet(self):
        s = MetricSanitizer()
        r = s.validate("rx_packet_total", 500)
        assert r.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_latency(self):
        s = MetricSanitizer()
        r = s.validate("rtt_latency", 10.5)
        assert r.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_bytes(self):
        s = MetricSanitizer()
        r = s.validate("bytes_transferred_total", 1024)
        assert r.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_interface(self):
        s = MetricSanitizer()
        r = s.validate("interface_count", 5)
        assert r.status == MetricValidationStatus.VALID

    def test_validate_type_mismatch(self):
        s = MetricSanitizer()
        r = s.validate("packet_counters", "not_a_number")
        assert r.status == MetricValidationStatus.TYPE_MISMATCH

    def test_validate_out_of_range(self):
        s = MetricSanitizer()
        r = s.validate("packet_counters", -1)
        assert r.status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_out_of_range_high(self):
        s = MetricSanitizer()
        r = s.validate("interface_count", 999)
        assert r.status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_no_rules(self):
        s = MetricSanitizer()
        r = s.validate("unknown_metric", 42)
        assert r.status == MetricValidationStatus.VALID

    def test_sanitize_all_valid(self):
        s = MetricSanitizer()
        valid, results = s.sanitize({"packet_counters": 100, "latency_ms": 5.0})
        assert len(valid) == 2
        assert all(r.status == MetricValidationStatus.VALID for r in results)

    def test_sanitize_mixed(self):
        s = MetricSanitizer()
        valid, results = s.sanitize({
            "packet_counters": 100,
            "latency_ms": "bad",
        })
        assert len(valid) == 1
        assert "packet_counters" in valid

    def test_sanitize_empty(self):
        s = MetricSanitizer()
        valid, results = s.sanitize({})
        assert valid == {}
        assert results == []


class TestEBPFMetricsExporterEnhanced:
    @patch("src.network.ebpf.metrics_exporter.EBPFMetricsExporter.__init__", return_value=None)
    def _make(self, mock_init):
        e = EBPFMetricsExporterEnhanced.__new__(EBPFMetricsExporterEnhanced)
        e.sanitizer = MetricSanitizer()
        e.error_count = ErrorCount()
        e.max_queue_size = 1000
        e.metric_queue = []
        e.performance_stats = {"export_time": [], "parse_time": [], "read_time": []}
        e.registered_maps = {}
        e.prometheus = MagicMock()
        e.prometheus.metrics = {}
        e.prometheus.degradation = MagicMock()
        e.prometheus.degradation.prometheus_available = True
        e.prometheus.port = 9090
        return e

    def test_track_performance(self):
        e = self._make()
        e._track_performance("export_time", 0.01)
        assert len(e.performance_stats["export_time"]) == 1

    def test_track_performance_cap_100(self):
        e = self._make()
        for i in range(105):
            e._track_performance("export_time", 0.01)
        assert len(e.performance_stats["export_time"]) == 100

    def test_track_performance_unknown_metric(self):
        e = self._make()
        e._track_performance("unknown", 0.01)  # Should not raise

    def test_update_error_count(self):
        e = self._make()
        e._update_error_count("map_read")
        assert e.error_count.map_read == 1
        assert e.error_count.total == 1

    def test_update_error_count_unknown(self):
        e = self._make()
        e._update_error_count("nonexistent_field")
        assert e.error_count.total == 1

    def test_validate_and_sanitize(self):
        e = self._make()
        valid, results = e._validate_and_sanitize({"packet_counters": 100})
        assert "packet_counters" in valid

    def test_validate_and_sanitize_invalid_increments_error(self):
        e = self._make()
        e._validate_and_sanitize({"packet_counters": "bad"})
        assert e.error_count.validation == 1

    def test_validate_map_metadata_valid(self):
        e = self._make()
        assert e._validate_map_metadata("map1", "prog1", "per_cpu_array") is True

    def test_validate_map_metadata_empty_name(self):
        e = self._make()
        assert e._validate_map_metadata("", "prog1", "per_cpu_array") is False

    def test_validate_map_metadata_invalid_type(self):
        e = self._make()
        assert e._validate_map_metadata("map1", "prog1", "invalid_type") is False

    def test_validate_map_metadata_long_name(self):
        e = self._make()
        assert e._validate_map_metadata("x" * 200, "prog1", "per_cpu_array") is True

    def test_get_error_summary(self):
        e = self._make()
        e._update_error_count("map_read")
        e._update_error_count("timeout")
        s = e.get_error_summary()
        assert s["total"] == 2
        assert s["map_read"] == 1
        assert s["timeout"] == 1

    def test_get_performance_stats_empty(self):
        e = self._make()
        stats = e.get_performance_stats()
        assert stats == {}

    def test_get_performance_stats_with_data(self):
        e = self._make()
        e._track_performance("export_time", 0.01)
        e._track_performance("export_time", 0.02)
        stats = e.get_performance_stats()
        assert "export_time" in stats
        assert stats["export_time"]["count"] == 2
        assert stats["export_time"]["min_ms"] == pytest.approx(10.0, abs=1)
        assert stats["export_time"]["max_ms"] == pytest.approx(20.0, abs=1)

    def test_get_health_status_healthy(self):
        e = self._make()
        e.get_degradation_status = MagicMock(return_value={"consecutive_failures": 0, "level": "normal"})
        health = e.get_health_status()
        assert health["overall"] == "healthy"

    def test_get_health_status_degraded(self):
        e = self._make()
        e.error_count.total = 60
        e.get_degradation_status = MagicMock(return_value={"consecutive_failures": 0, "level": "normal"})
        health = e.get_health_status()
        assert health["overall"] == "degraded"

    def test_get_health_status_unhealthy(self):
        e = self._make()
        e.error_count.total = 150
        e.get_degradation_status = MagicMock(return_value={"consecutive_failures": 10, "level": "critical"})
        health = e.get_health_status()
        assert health["overall"] == "unhealthy"

    def test_reset_error_counts(self):
        e = self._make()
        e._update_error_count("map_read")
        e.reset_error_counts()
        assert e.error_count.total == 0
        assert e.error_count.map_read == 0

    def test_dump_diagnostics(self, tmp_path):
        e = self._make()
        e.get_degradation_status = MagicMock(return_value={"consecutive_failures": 0})
        out = tmp_path / "diag.json"
        e.dump_diagnostics(str(out))
        assert out.exists()
        data = json.loads(out.read_text())
        assert "health" in data
        assert "version" in data

    def test_dump_diagnostics_bad_path(self):
        e = self._make()
        e.get_degradation_status = MagicMock(return_value={})
        e.dump_diagnostics("/nonexistent/path/diag.json")  # Should not raise

    def test_cleanup_stale_metrics(self):
        e = self._make()
        e._cleanup_stale_metrics()  # Should not raise

    def test_register_map_valid(self):
        e = self._make()
        with patch.object(type(e).__mro__[2], "register_map"):
            assert e.register_map("m1", "p1", "per_cpu_array") is True

    def test_register_map_invalid_metadata(self):
        e = self._make()
        assert e.register_map("", "p1", "per_cpu_array") is False

    def test_register_map_exception(self):
        e = self._make()
        with patch.object(type(e).__mro__[2], "register_map", side_effect=Exception("fail")):
            assert e.register_map("m1", "p1", "per_cpu_array") is False

    def test_read_map_via_bpftool_with_timeout_success(self):
        e = self._make()
        e._read_map_via_bpftool = MagicMock(return_value={"key": "val"})
        result = e._read_map_via_bpftool_with_timeout("test_map")
        assert result == {"key": "val"}

    def test_read_map_via_bpftool_with_timeout_timeout(self):
        import subprocess
        e = self._make()
        e._read_map_via_bpftool = MagicMock(
            side_effect=subprocess.TimeoutExpired(cmd="bpftool", timeout=5)
        )
        result = e._read_map_via_bpftool_with_timeout("test_map")
        assert result is None
        assert e.error_count.timeout == 1

    def test_read_map_via_bpftool_with_timeout_error(self):
        e = self._make()
        e._read_map_via_bpftool = MagicMock(side_effect=RuntimeError("fail"))
        result = e._read_map_via_bpftool_with_timeout("test_map")
        assert result is None
        assert e.error_count.map_read == 1
