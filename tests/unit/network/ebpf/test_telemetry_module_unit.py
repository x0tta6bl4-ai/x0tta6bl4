"""
Comprehensive unit tests for src/network/ebpf/telemetry_module.py

Tests cover:
- Data structures (MetricType, MapType, EventSeverity, TelemetryConfig, etc.)
- SecurityManager (validation, sanitization, path traversal prevention)
- MapReader (BCC, bpftool, caching, parallel reads)
- PerfBufferReader (event handling, stats, start/stop)
- PrometheusExporter (metric registration, setting, incrementing, export)
- EBPFTelemetryCollector (program registration, collection, lifecycle)
- Convenience functions (create_collector, quick_start)
"""

import json
import os
import struct
import threading
import time
from collections import deque
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.telemetry_module import (CollectionStats,
                                               EBPFTelemetryCollector,
                                               EventSeverity, MapMetadata,
                                               MapReader, MapType,
                                               MetricDefinition, MetricType,
                                               PerfBufferReader,
                                               PrometheusExporter,
                                               SecurityManager,
                                               TelemetryConfig, TelemetryEvent,
                                               create_collector, quick_start)

# ============================================================================
# Data Structures
# ============================================================================


class TestMetricType:
    def test_values(self):
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"


class TestMapType:
    def test_values(self):
        assert MapType.HASH.value == "hash"
        assert MapType.ARRAY.value == "array"
        assert MapType.PERCPU_ARRAY.value == "percpu_array"
        assert MapType.RINGBUF.value == "ringbuf"
        assert MapType.PERF_EVENT_ARRAY.value == "perf_event_array"
        assert MapType.LRU_HASH.value == "lru_hash"


class TestEventSeverity:
    def test_values(self):
        assert EventSeverity.INFO.value == 1
        assert EventSeverity.LOW.value == 2
        assert EventSeverity.MEDIUM.value == 3
        assert EventSeverity.HIGH.value == 4
        assert EventSeverity.CRITICAL.value == 5

    def test_ordering(self):
        assert EventSeverity.INFO.value < EventSeverity.CRITICAL.value


class TestTelemetryConfig:
    def test_defaults(self):
        cfg = TelemetryConfig()
        assert cfg.collection_interval == 1.0
        assert cfg.batch_size == 100
        assert cfg.max_queue_size == 10000
        assert cfg.max_workers == 4
        assert cfg.read_timeout == 5.0
        assert cfg.poll_timeout == 100
        assert cfg.prometheus_port == 9090
        assert cfg.prometheus_host == "0.0.0.0"
        assert cfg.enable_validation is True
        assert cfg.enable_sanitization is True
        assert cfg.max_metric_value == 1e15
        assert cfg.sanitize_paths is True
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 0.5
        assert cfg.enable_fallback is True
        assert cfg.log_level == "INFO"
        assert cfg.log_events is False

    def test_custom_values(self):
        cfg = TelemetryConfig(
            collection_interval=5.0,
            prometheus_port=9999,
            max_metric_value=100.0,
        )
        assert cfg.collection_interval == 5.0
        assert cfg.prometheus_port == 9999
        assert cfg.max_metric_value == 100.0


class TestMetricDefinition:
    def test_defaults(self):
        md = MetricDefinition(name="test", type=MetricType.COUNTER, description="d")
        assert md.name == "test"
        assert md.type == MetricType.COUNTER
        assert md.labels == []
        assert md.help_text == ""

    def test_with_labels(self):
        md = MetricDefinition(
            name="m", type=MetricType.GAUGE, description="d", labels=["a", "b"]
        )
        assert md.labels == ["a", "b"]


class TestMapMetadata:
    def test_defaults(self):
        mm = MapMetadata(
            name="m", map_type=MapType.HASH, key_size=4, value_size=8, max_entries=1024
        )
        assert mm.program_name == ""
        assert mm.description == ""


class TestTelemetryEvent:
    def test_defaults(self):
        evt = TelemetryEvent(event_type="test", timestamp_ns=1000, cpu_id=0)
        assert evt.pid == 0
        assert evt.data == {}
        assert evt.severity == EventSeverity.INFO


class TestCollectionStats:
    def test_defaults(self):
        stats = CollectionStats()
        assert stats.total_collections == 0
        assert stats.successful_collections == 0
        assert stats.failed_collections == 0
        assert stats.total_metrics_collected == 0
        assert stats.total_events_processed == 0
        assert stats.last_collection_time == 0.0
        assert stats.average_collection_time == 0.0
        assert isinstance(stats.collection_times, deque)
        assert stats.collection_times.maxlen == 100


# ============================================================================
# SecurityManager
# ============================================================================


class TestSecurityManager:
    @pytest.fixture
    def sec(self):
        return SecurityManager(TelemetryConfig())

    # -- validate_metric_name --

    def test_validate_metric_name_valid(self, sec):
        ok, err = sec.validate_metric_name("my_metric_1")
        assert ok is True
        assert err is None

    def test_validate_metric_name_empty(self, sec):
        ok, err = sec.validate_metric_name("")
        assert ok is False
        assert "empty" in err.lower()

    def test_validate_metric_name_too_long(self, sec):
        ok, err = sec.validate_metric_name("a" * 201)
        assert ok is False
        assert "too long" in err.lower()

    def test_validate_metric_name_invalid_char(self, sec):
        ok, err = sec.validate_metric_name("my-metric")
        assert ok is False
        assert "Invalid character" in err

    def test_validate_metric_name_reserved_prefix(self, sec):
        ok, err = sec.validate_metric_name("__reserved")
        assert ok is False
        assert "__" in err

    def test_validate_metric_name_with_colon(self, sec):
        ok, err = sec.validate_metric_name("namespace:metric")
        assert ok is True

    # -- validate_metric_value --

    def test_validate_metric_value_int(self, sec):
        ok, err = sec.validate_metric_value(42)
        assert ok is True

    def test_validate_metric_value_float(self, sec):
        ok, err = sec.validate_metric_value(3.14)
        assert ok is True

    def test_validate_metric_value_none(self, sec):
        ok, err = sec.validate_metric_value(None)
        assert ok is False
        assert "None" in err

    def test_validate_metric_value_string(self, sec):
        ok, err = sec.validate_metric_value("bad")
        assert ok is False
        assert "Invalid metric type" in err

    def test_validate_metric_value_nan(self, sec):
        ok, err = sec.validate_metric_value(float("nan"))
        assert ok is False
        assert "NaN" in err

    def test_validate_metric_value_inf(self, sec):
        ok, err = sec.validate_metric_value(float("inf"))
        assert ok is False
        assert "infinite" in err

    def test_validate_metric_value_neg_inf(self, sec):
        ok, err = sec.validate_metric_value(float("-inf"))
        assert ok is False
        assert "infinite" in err

    def test_validate_metric_value_exceeds_max(self, sec):
        ok, err = sec.validate_metric_value(1e16)
        assert ok is False
        assert "exceeds" in err.lower()

    def test_validate_metric_value_negative_in_range(self, sec):
        ok, err = sec.validate_metric_value(-100)
        assert ok is True

    # -- sanitize_string --

    def test_sanitize_string_normal(self, sec):
        assert sec.sanitize_string("hello") == "hello"
        assert sec.sanitized_count == 1

    def test_sanitize_string_null_byte(self, sec):
        result = sec.sanitize_string("hel\x00lo")
        assert "\x00" not in result

    def test_sanitize_string_too_long(self, sec):
        result = sec.sanitize_string("x" * 2000)
        assert len(result) <= 1000

    def test_sanitize_string_blocked_patterns(self, sec):
        result = sec.sanitize_string("../etc/passwd")
        assert "../" not in result

    def test_sanitize_string_non_string(self, sec):
        assert sec.sanitize_string(123) == ""

    def test_sanitize_string_proc_path(self, sec):
        result = sec.sanitize_string("/proc/self/maps")
        assert "/proc/" not in result

    # -- sanitize_path --

    def test_sanitize_path_traversal(self, sec):
        result = sec.sanitize_path("../../etc/passwd")
        assert ".." not in result
        # basename only
        assert result == "passwd"

    def test_sanitize_path_leading_slash(self, sec):
        result = sec.sanitize_path("/absolute/path/file.txt")
        assert result == "file.txt"

    def test_sanitize_path_disabled(self):
        cfg = TelemetryConfig(sanitize_paths=False)
        sec = SecurityManager(cfg)
        result = sec.sanitize_path("../../etc/passwd")
        assert result == "../../etc/passwd"

    # -- validate_event --

    def test_validate_event_valid(self, sec):
        evt = TelemetryEvent(event_type="test", timestamp_ns=1000, cpu_id=0, pid=100)
        ok, err = sec.validate_event(evt)
        assert ok is True

    def test_validate_event_empty_type(self, sec):
        evt = TelemetryEvent(event_type="", timestamp_ns=1000, cpu_id=0)
        ok, err = sec.validate_event(evt)
        assert ok is False
        assert "event type" in err.lower()

    def test_validate_event_zero_timestamp(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=0, cpu_id=0)
        ok, err = sec.validate_event(evt)
        assert ok is False
        assert "timestamp" in err.lower()

    def test_validate_event_negative_timestamp(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=-1, cpu_id=0)
        ok, err = sec.validate_event(evt)
        assert ok is False

    def test_validate_event_bad_cpu_id(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=256)
        ok, err = sec.validate_event(evt)
        assert ok is False
        assert "CPU ID" in err

    def test_validate_event_negative_cpu_id(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=-1)
        ok, err = sec.validate_event(evt)
        assert ok is False

    def test_validate_event_bad_pid(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=0, pid=5000000)
        ok, err = sec.validate_event(evt)
        assert ok is False
        assert "PID" in err

    def test_validate_event_negative_pid(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=0, pid=-1)
        ok, err = sec.validate_event(evt)
        assert ok is False

    def test_validate_event_max_valid_cpu(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=255)
        ok, _ = sec.validate_event(evt)
        assert ok is True

    def test_validate_event_max_valid_pid(self, sec):
        evt = TelemetryEvent(event_type="t", timestamp_ns=1, cpu_id=0, pid=4194304)
        ok, _ = sec.validate_event(evt)
        assert ok is True

    # -- get_stats --

    def test_get_stats(self, sec):
        stats = sec.get_stats()
        assert "validation_errors" in stats
        assert "sanitized_count" in stats
        assert "config" in stats
        assert stats["config"]["enable_validation"] is True


# ============================================================================
# MapReader
# ============================================================================


class TestMapReader:
    @pytest.fixture
    def reader(self):
        cfg = TelemetryConfig()
        sec = SecurityManager(cfg)
        with patch(
            "src.network.ebpf.telemetry_module.MapReader._check_bpftool",
            return_value=False,
        ):
            return MapReader(cfg, sec)

    def test_init(self, reader):
        assert reader.bpftool_available is False
        assert reader.cache == {}
        assert reader.cache_ttl == 0.5

    @patch("subprocess.run")
    def test_check_bpftool_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cfg = TelemetryConfig()
        sec = SecurityManager(cfg)
        r = MapReader(cfg, sec)
        assert r.bpftool_available is True

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_check_bpftool_not_found(self, mock_run):
        cfg = TelemetryConfig()
        sec = SecurityManager(cfg)
        r = MapReader(cfg, sec)
        assert r.bpftool_available is False

    # -- read_map_via_bcc --

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", False)
    def test_read_map_via_bcc_no_bcc(self, reader):
        with pytest.raises(RuntimeError, match="BCC not available"):
            reader.read_map_via_bcc(MagicMock(), "test_map")

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_read_map_via_bcc_bytes_key(self, reader):
        mock_bpf = MagicMock()
        table = MagicMock()
        table.items.return_value = [(b"key1\x00", 42)]
        mock_bpf.__getitem__ = MagicMock(return_value=table)

        result = reader.read_map_via_bcc(mock_bpf, "test_map")
        assert result == {"key1": 42}

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_read_map_via_bcc_struct_value(self, reader):
        mock_bpf = MagicMock()
        table = MagicMock()
        val = MagicMock()
        val.__dict__ = {"count": 10, "data": b"hello\x00"}
        table.items.return_value = [("k", val)]
        mock_bpf.__getitem__ = MagicMock(return_value=table)

        result = reader.read_map_via_bcc(mock_bpf, "m")
        assert result["k"]["count"] == 10
        assert result["k"]["data"] == "hello"

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_read_map_via_bcc_exception(self, reader):
        mock_bpf = MagicMock()
        mock_bpf.__getitem__ = MagicMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            reader.read_map_via_bcc(mock_bpf, "m")

    # -- read_map_via_bpftool --

    @patch("subprocess.run")
    def test_read_map_via_bpftool_success(self, mock_run, reader):
        data = {"data": [{"key": "k1", "value": 100}]}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data), stderr=""
        )
        result = reader.read_map_via_bpftool("m")
        assert result == {"k1": 100}

    @patch("subprocess.run")
    def test_read_map_via_bpftool_list_key(self, mock_run, reader):
        data = {"data": [{"key": [1, 2, 3], "value": 99}]}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data), stderr=""
        )
        result = reader.read_map_via_bpftool("m")
        assert result["1_2_3"] == 99

    @patch("subprocess.run")
    def test_read_map_via_bpftool_failure(self, mock_run, reader):
        mock_run.return_value = MagicMock(returncode=1, stderr="err", stdout="")
        with pytest.raises(RuntimeError, match="bpftool failed"):
            reader.read_map_via_bpftool("m")

    @patch("subprocess.run")
    def test_read_map_via_bpftool_timeout(self, mock_run, reader):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bpftool", timeout=5)
        with pytest.raises(RuntimeError, match="timeout"):
            reader.read_map_via_bpftool("m")

    @patch("subprocess.run")
    def test_read_map_via_bpftool_no_data_key(self, mock_run, reader):
        """When JSON does not contain a 'data' key, return empty dict."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps({"other": 1}), stderr=""
        )
        result = reader.read_map_via_bpftool("m")
        assert result == {}

    # -- read_map (with caching / fallback) --

    def test_read_map_cache_hit(self, reader):
        reader.cache["m"] = (time.time(), {"cached": True})
        result = reader.read_map(None, "m", use_cache=True)
        assert result == {"cached": True}

    def test_read_map_cache_expired(self, reader):
        reader.cache["m"] = (time.time() - 10, {"old": True})
        # No BCC, no bpftool -> empty dict
        result = reader.read_map(None, "m", use_cache=True)
        assert result == {}

    def test_read_map_no_cache(self, reader):
        reader.cache["m"] = (time.time(), {"cached": True})
        result = reader.read_map(None, "m", use_cache=False)
        assert result == {}  # No backend available

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_read_map_bcc_success_updates_cache(self, reader):
        mock_bpf = MagicMock()
        table = MagicMock()
        table.items.return_value = [("k", 1)]
        mock_bpf.__getitem__ = MagicMock(return_value=table)

        result = reader.read_map(mock_bpf, "m", use_cache=False)
        assert result == {"k": 1}
        assert "m" in reader.cache

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_read_map_bcc_fails_falls_to_bpftool(self, reader):
        mock_bpf = MagicMock()
        mock_bpf.__getitem__ = MagicMock(side_effect=RuntimeError("bcc error"))
        reader.bpftool_available = True

        with patch.object(
            reader, "read_map_via_bpftool", return_value={"bpftool": True}
        ) as mock_bt:
            result = reader.read_map(mock_bpf, "m", use_cache=False)
            assert result == {"bpftool": True}
            mock_bt.assert_called_once_with("m")

    def test_read_map_all_fail(self, reader):
        result = reader.read_map(None, "m", use_cache=False)
        assert result == {}

    # -- read_multiple_maps --

    def test_read_multiple_maps(self, reader):
        reader.cache["m1"] = (time.time(), {"a": 1})
        reader.cache["m2"] = (time.time(), {"b": 2})
        result = reader.read_multiple_maps(None, ["m1", "m2"])
        assert result["m1"] == {"a": 1}
        assert result["m2"] == {"b": 2}

    def test_read_multiple_maps_one_fails(self, reader):
        reader.cache["m1"] = (time.time(), {"a": 1})
        # m2 not in cache, no backend -> empty
        result = reader.read_multiple_maps(None, ["m1", "m2"])
        assert result["m1"] == {"a": 1}
        assert result["m2"] == {}

    # -- clear_cache --

    def test_clear_cache(self, reader):
        reader.cache["x"] = (time.time(), {})
        reader.clear_cache()
        assert reader.cache == {}


# ============================================================================
# PerfBufferReader
# ============================================================================


class TestPerfBufferReader:
    @pytest.fixture
    def pbr(self):
        cfg = TelemetryConfig()
        sec = SecurityManager(cfg)
        return PerfBufferReader(cfg, sec)

    def test_init(self, pbr):
        assert pbr.running is False
        assert pbr.stats["events_received"] == 0
        assert pbr.stats["events_processed"] == 0
        assert pbr.stats["events_dropped"] == 0
        assert pbr.stats["parse_errors"] == 0

    def test_register_handler(self, pbr):
        handler = MagicMock()
        pbr.register_handler("evt_type", handler)
        assert handler in pbr.event_handlers["evt_type"]

    def test_register_multiple_handlers(self, pbr):
        h1 = MagicMock()
        h2 = MagicMock()
        pbr.register_handler("t", h1)
        pbr.register_handler("t", h2)
        assert len(pbr.event_handlers["t"]) == 2

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", False)
    def test_start_reading_no_bcc(self, pbr):
        pbr.start_reading(MagicMock(), "events")
        assert pbr.running is False

    def test_stop_reading(self, pbr):
        pbr.running = True
        pbr.stop_reading()
        assert pbr.running is False

    def test_get_stats(self, pbr):
        stats = pbr.get_stats()
        assert isinstance(stats, dict)
        assert "events_received" in stats
        # Returns a copy
        stats["events_received"] = 999
        assert pbr.stats["events_received"] == 0

    def test_process_events(self, pbr):
        handler = MagicMock()
        pbr.register_handler("event_1", handler)
        evt = TelemetryEvent(event_type="event_1", timestamp_ns=100, cpu_id=0)
        pbr.event_queue.append(evt)
        pbr._process_events()
        handler.assert_called_once_with(evt)
        assert pbr.stats["events_processed"] == 1

    def test_process_events_handler_exception(self, pbr):
        handler = MagicMock(side_effect=RuntimeError("boom"))
        pbr.register_handler("event_1", handler)
        evt = TelemetryEvent(event_type="event_1", timestamp_ns=100, cpu_id=0)
        pbr.event_queue.append(evt)
        pbr._process_events()
        # Should not raise, just log
        assert pbr.stats["events_processed"] == 0

    def test_process_events_no_handlers(self, pbr):
        evt = TelemetryEvent(event_type="unknown", timestamp_ns=100, cpu_id=0)
        pbr.event_queue.append(evt)
        pbr._process_events()
        assert len(pbr.event_queue) == 0

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_start_reading_runs_poll_loop(self, pbr):
        """Verify start_reading opens perf buffer and polls until stopped."""
        mock_bpf = MagicMock()
        mock_map = MagicMock()
        mock_bpf.__getitem__ = MagicMock(return_value=mock_map)

        call_count = 0

        def fake_poll(timeout=100):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                pbr.running = False

        mock_bpf.perf_buffer_poll = fake_poll

        pbr.start_reading(mock_bpf, "events")
        mock_map.open_perf_buffer.assert_called_once()
        assert call_count >= 2
        assert pbr.running is False

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_start_reading_exception(self, pbr):
        mock_bpf = MagicMock()
        mock_map = MagicMock()
        mock_map.open_perf_buffer.side_effect = RuntimeError("fail")
        mock_bpf.__getitem__ = MagicMock(return_value=mock_map)

        pbr.start_reading(mock_bpf, "events")
        assert pbr.running is False


# ============================================================================
# PrometheusExporter
# ============================================================================


class TestPrometheusExporter:
    @pytest.fixture
    def exporter(self):
        cfg = TelemetryConfig()
        sec = SecurityManager(cfg)
        return PrometheusExporter(cfg, sec)

    def test_init(self, exporter):
        assert exporter.metrics == {}
        assert exporter.server_started is False

    # -- start_server --

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", False)
    def test_start_server_no_prometheus(self, exporter):
        exporter.start_server()
        assert exporter.server_started is False

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.start_http_server")
    def test_start_server_success(self, mock_start, exporter):
        exporter.start_server()
        assert exporter.server_started is True
        mock_start.assert_called_once()

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.start_http_server")
    def test_start_server_already_started(self, mock_start, exporter):
        exporter.server_started = True
        exporter.start_server()
        mock_start.assert_not_called()

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch(
        "src.network.ebpf.telemetry_module.start_http_server",
        side_effect=OSError("port in use"),
    )
    def test_start_server_exception(self, mock_start, exporter):
        exporter.start_server()
        assert exporter.server_started is False

    # -- register_metric --

    def test_register_metric_invalid_name(self, exporter):
        defn = MetricDefinition(name="__bad", type=MetricType.COUNTER, description="d")
        exporter.register_metric(defn)
        assert "__bad" not in exporter.metrics

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.Counter")
    def test_register_counter(self, mock_counter_cls, exporter):
        mock_counter_cls.return_value = MagicMock()
        defn = MetricDefinition(
            name="req_total", type=MetricType.COUNTER, description="d"
        )
        exporter.register_metric(defn)
        assert "req_total" in exporter.metrics
        assert "req_total" in exporter.metric_definitions

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.Gauge")
    def test_register_gauge(self, mock_gauge_cls, exporter):
        mock_gauge_cls.return_value = MagicMock()
        defn = MetricDefinition(name="temp", type=MetricType.GAUGE, description="d")
        exporter.register_metric(defn)
        assert "temp" in exporter.metrics

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.Histogram")
    def test_register_histogram(self, mock_hist_cls, exporter):
        mock_hist_cls.return_value = MagicMock()
        defn = MetricDefinition(
            name="latency", type=MetricType.HISTOGRAM, description="d"
        )
        exporter.register_metric(defn)
        assert "latency" in exporter.metrics

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.telemetry_module.Summary")
    def test_register_summary(self, mock_sum_cls, exporter):
        mock_sum_cls.return_value = MagicMock()
        defn = MetricDefinition(
            name="duration", type=MetricType.SUMMARY, description="d"
        )
        exporter.register_metric(defn)
        assert "duration" in exporter.metrics

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch(
        "src.network.ebpf.telemetry_module.Counter", side_effect=RuntimeError("fail")
    )
    def test_register_metric_exception(self, mock_cls, exporter):
        defn = MetricDefinition(name="broken", type=MetricType.COUNTER, description="d")
        exporter.register_metric(defn)
        assert "broken" not in exporter.metrics

    # -- set_metric --

    def test_set_metric_not_registered(self, exporter):
        # Should not raise
        exporter.set_metric("missing", 1.0)

    def test_set_metric_invalid_value(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["m"] = mock_m
        exporter.set_metric("m", float("nan"))
        mock_m.set.assert_not_called()

    def test_set_metric_success(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["m"] = mock_m
        exporter.set_metric("m", 42.0)
        mock_m.set.assert_called_once_with(42.0)

    def test_set_metric_with_labels(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["m"] = mock_m
        exporter.set_metric("m", 5.0, labels={"host": "a"})
        mock_m.labels.assert_called_once_with(host="a")
        mock_m.labels.return_value.set.assert_called_once_with(5.0)

    def test_set_metric_exception(self, exporter):
        mock_m = MagicMock()
        mock_m.set.side_effect = RuntimeError("fail")
        exporter.metrics["m"] = mock_m
        # Should not raise
        exporter.set_metric("m", 1.0)

    # -- increment_metric --

    def test_increment_metric_not_registered(self, exporter):
        exporter.increment_metric("missing")

    def test_increment_metric_success(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["c"] = mock_m
        exporter.increment_metric("c", 5.0)
        mock_m.inc.assert_called_once_with(5.0)

    def test_increment_metric_with_labels(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["c"] = mock_m
        exporter.increment_metric("c", 1.0, labels={"path": "/api"})
        mock_m.labels.assert_called_once_with(path="/api")
        mock_m.labels.return_value.inc.assert_called_once_with(1.0)

    def test_increment_metric_exception(self, exporter):
        mock_m = MagicMock()
        mock_m.inc.side_effect = RuntimeError("fail")
        exporter.metrics["c"] = mock_m
        exporter.increment_metric("c")

    # -- export_metrics --

    def test_export_metrics_auto_register_gauge(self, exporter):
        with patch.object(exporter, "register_metric") as mock_reg:
            with patch.object(exporter, "set_metric") as mock_set:
                exporter.export_metrics({"my_metric": 10})
                mock_reg.assert_called_once()
                defn = mock_reg.call_args[0][0]
                assert defn.type == MetricType.GAUGE

    def test_export_metrics_auto_register_counter(self, exporter):
        with patch.object(exporter, "register_metric") as mock_reg:
            with patch.object(exporter, "set_metric") as mock_set:
                exporter.export_metrics({"request_total": 10})
                defn = mock_reg.call_args[0][0]
                assert defn.type == MetricType.COUNTER

    def test_export_metrics_count_suffix(self, exporter):
        with patch.object(exporter, "register_metric") as mock_reg:
            with patch.object(exporter, "set_metric"):
                exporter.export_metrics({"error_count": 5})
                defn = mock_reg.call_args[0][0]
                assert defn.type == MetricType.COUNTER

    def test_export_metrics_already_registered(self, exporter):
        mock_m = MagicMock()
        exporter.metrics["m"] = mock_m
        with patch.object(exporter, "register_metric") as mock_reg:
            exporter.export_metrics({"m": 1})
            mock_reg.assert_not_called()
        mock_m.set.assert_called_once_with(1.0)

    # -- get_metrics_text --

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", False)
    def test_get_metrics_text_no_prometheus(self, exporter):
        text = exporter.get_metrics_text()
        assert "not available" in text

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch(
        "src.network.ebpf.telemetry_module.generate_latest", return_value=b"# HELP m\n"
    )
    def test_get_metrics_text_success(self, mock_gen, exporter):
        text = exporter.get_metrics_text()
        assert "HELP" in text

    @patch("src.network.ebpf.telemetry_module.PROMETHEUS_AVAILABLE", True)
    @patch(
        "src.network.ebpf.telemetry_module.generate_latest",
        side_effect=RuntimeError("err"),
    )
    def test_get_metrics_text_exception(self, mock_gen, exporter):
        text = exporter.get_metrics_text()
        assert "Error" in text


# ============================================================================
# EBPFTelemetryCollector
# ============================================================================


class TestEBPFTelemetryCollector:
    @pytest.fixture
    def collector(self):
        with patch(
            "src.network.ebpf.telemetry_module.MapReader._check_bpftool",
            return_value=False,
        ):
            with patch("src.network.ebpf.telemetry_module.CollectorRegistry"):
                return EBPFTelemetryCollector()

    def test_init_default_config(self, collector):
        assert isinstance(collector.config, TelemetryConfig)
        assert isinstance(collector.security, SecurityManager)
        assert isinstance(collector.map_reader, MapReader)
        assert isinstance(collector.perf_reader, PerfBufferReader)
        assert isinstance(collector.prometheus, PrometheusExporter)
        assert collector.programs == {}
        assert collector.program_maps == {}

    def test_init_custom_config(self):
        cfg = TelemetryConfig(collection_interval=10.0)
        with patch(
            "src.network.ebpf.telemetry_module.MapReader._check_bpftool",
            return_value=False,
        ):
            with patch("src.network.ebpf.telemetry_module.CollectorRegistry"):
                c = EBPFTelemetryCollector(cfg)
        assert c.config.collection_interval == 10.0

    # -- register_program --

    def test_register_program(self, collector):
        mock_bpf = MagicMock()
        collector.register_program(mock_bpf, "prog1", ["map_a", "map_b"])
        assert "prog1" in collector.programs
        assert collector.programs["prog1"] is mock_bpf
        assert collector.program_maps["prog1"] == ["map_a", "map_b"]

    def test_register_program_no_maps(self, collector):
        collector.register_program(MagicMock(), "prog1")
        assert collector.program_maps["prog1"] == []

    # -- register_map --

    def test_register_map(self, collector):
        collector.register_map("prog1", "new_map")
        assert "new_map" in collector.program_maps["prog1"]

    def test_register_map_no_duplicate(self, collector):
        collector.register_map("prog1", "m")
        collector.register_map("prog1", "m")
        assert collector.program_maps["prog1"].count("m") == 1

    def test_register_map_existing_program(self, collector):
        collector.program_maps["prog1"] = ["existing"]
        collector.register_map("prog1", "new")
        assert "existing" in collector.program_maps["prog1"]
        assert "new" in collector.program_maps["prog1"]

    # -- collect_from_map --

    def test_collect_from_map_no_program(self, collector):
        result = collector.collect_from_map("nonexistent", "m")
        assert result == {}

    def test_collect_from_map_success(self, collector):
        mock_bpf = MagicMock()
        collector.programs["prog1"] = mock_bpf
        collector.map_reader.cache["m"] = (time.time(), {"k": 1})
        result = collector.collect_from_map("prog1", "m")
        assert result == {"k": 1}
        assert collector.stats.total_metrics_collected == 1

    def test_collect_from_map_exception(self, collector):
        mock_bpf = MagicMock()
        collector.programs["prog1"] = mock_bpf
        with patch.object(
            collector.map_reader, "read_map", side_effect=RuntimeError("err")
        ):
            result = collector.collect_from_map("prog1", "m")
        assert result == {}

    # -- collect_all_metrics --

    def test_collect_all_metrics_empty(self, collector):
        result = collector.collect_all_metrics()
        assert result == {}
        assert collector.stats.total_collections == 1
        assert collector.stats.successful_collections == 1

    def test_collect_all_metrics_with_maps(self, collector):
        mock_bpf = MagicMock()
        collector.programs["p1"] = mock_bpf
        collector.program_maps["p1"] = ["m1"]

        with patch.object(
            collector.map_reader,
            "read_multiple_maps",
            return_value={"m1": {"key1": 10}},
        ):
            result = collector.collect_all_metrics()

        assert "p1" in result
        assert "p1_m1_key1" in result["p1"]
        assert result["p1"]["p1_m1_key1"] == 10
        assert collector.stats.successful_collections == 1
        assert len(collector.stats.collection_times) == 1

    def test_collect_all_metrics_exception(self, collector):
        collector.programs["p1"] = MagicMock()
        collector.program_maps["p1"] = ["m1"]
        with patch.object(
            collector.map_reader,
            "read_multiple_maps",
            side_effect=RuntimeError("err"),
        ):
            result = collector.collect_all_metrics()
        assert collector.stats.failed_collections == 1

    @patch("src.network.ebpf.telemetry_module.BCC_AVAILABLE", True)
    def test_collect_all_metrics_auto_discover(self, collector):
        """When map_names is empty and BCC is available, try auto-discover."""
        mock_bpf = MagicMock()
        mock_bpf.__dir__ = MagicMock(return_value=["normal", "[[map1]]"])
        collector.programs["p1"] = mock_bpf
        collector.program_maps["p1"] = []

        with patch.object(
            collector.map_reader,
            "read_multiple_maps",
            return_value={},
        ) as mock_read:
            collector.collect_all_metrics()

    # -- export_to_prometheus --

    def test_export_to_prometheus(self, collector):
        metrics = {"p1": {"metric_a": 10, "metric_b": 20}}
        with patch.object(collector.prometheus, "export_metrics") as mock_export:
            collector.export_to_prometheus(metrics)
            mock_export.assert_called_once()
            args = mock_export.call_args[0][0]
            assert "p1_metric_a" in args
            assert "p1_metric_b" in args

    # -- start_perf_reading --

    def test_start_perf_reading_no_programs(self, collector):
        collector.start_perf_reading()
        assert collector.perf_thread is None

    def test_start_perf_reading_with_program(self, collector):
        collector.programs["p1"] = MagicMock()
        with patch.object(collector.perf_reader, "start_reading"):
            collector.start_perf_reading("events")
            assert collector.perf_thread is not None
            assert collector.perf_thread.daemon is True
            collector.perf_thread.join(timeout=1)

    # -- start_collection_loop --

    def test_start_collection_loop(self, collector):
        collector.programs["p1"] = MagicMock()
        collector.program_maps["p1"] = []

        collector.start_collection_loop(interval=0.01)
        assert collector.collection_thread is not None
        assert collector.collection_thread.daemon is True

        # Let it run a couple of cycles
        time.sleep(0.05)
        collector.stop_event.set()
        collector.collection_thread.join(timeout=2)
        assert collector.stats.total_collections >= 1

    # -- start / stop --

    def test_start(self, collector):
        with patch.object(collector.prometheus, "start_server") as mock_srv:
            with patch.object(collector, "start_collection_loop") as mock_loop:
                collector.start()
                mock_srv.assert_called_once()
                mock_loop.assert_called_once()

    def test_stop(self, collector):
        collector.collection_thread = MagicMock()
        collector.perf_thread = MagicMock()
        with patch.object(collector.perf_reader, "stop_reading") as mock_stop:
            collector.stop()
            mock_stop.assert_called_once()
            collector.collection_thread.join.assert_called_once_with(timeout=5)
            collector.perf_thread.join.assert_called_once_with(timeout=5)
        assert collector.stop_event.is_set()

    def test_stop_no_threads(self, collector):
        collector.stop()
        assert collector.stop_event.is_set()

    # -- get_stats --

    def test_get_stats(self, collector):
        collector.programs["p1"] = MagicMock()
        collector.program_maps["p1"] = ["m1"]
        stats = collector.get_stats()
        assert "collection" in stats
        assert "security" in stats
        assert "perf_reader" in stats
        assert "programs" in stats
        assert "maps" in stats
        assert "p1" in stats["programs"]

    # -- context manager --

    def test_context_manager(self, collector):
        with patch.object(collector, "start") as mock_start:
            with patch.object(collector, "stop") as mock_stop:
                with collector as c:
                    assert c is collector
                    mock_start.assert_called_once()
                mock_stop.assert_called_once()


# ============================================================================
# Convenience Functions
# ============================================================================


class TestConvenienceFunctions:
    @patch(
        "src.network.ebpf.telemetry_module.MapReader._check_bpftool", return_value=False
    )
    @patch("src.network.ebpf.telemetry_module.CollectorRegistry")
    def test_create_collector(self, mock_registry, mock_bpftool):
        c = create_collector(prometheus_port=8888, collection_interval=2.0)
        assert isinstance(c, EBPFTelemetryCollector)
        assert c.config.prometheus_port == 8888
        assert c.config.collection_interval == 2.0

    @patch(
        "src.network.ebpf.telemetry_module.MapReader._check_bpftool", return_value=False
    )
    @patch("src.network.ebpf.telemetry_module.CollectorRegistry")
    @patch("src.network.ebpf.telemetry_module.EBPFTelemetryCollector.start")
    def test_quick_start(self, mock_start, mock_registry, mock_bpftool):
        mock_bpf = MagicMock()
        c = quick_start(mock_bpf, "test_prog", prometheus_port=7777)
        assert isinstance(c, EBPFTelemetryCollector)
        assert "test_prog" in c.programs
        mock_start.assert_called_once()
