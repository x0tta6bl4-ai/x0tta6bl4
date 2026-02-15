"""
Comprehensive unit tests for src/network/ebpf/metrics_exporter.py
"""

import json
import signal
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch, call

import pytest

from src.network.ebpf.metrics_exporter import (
    MetricValidationStatus,
    MetricValidationResult,
    ErrorCount,
    MetricSanitizer,
    EBPFMetricsError,
    MapReadError,
    BpftoolError,
    PrometheusExportError,
    MetricRegistrationError,
    ParseError,
    TimeoutError,
    RetryConfig,
    with_retry,
    DegradationLevel,
    DegradationState,
    GracefulShutdown,
    StructuredLogger,
    PrometheusExporter,
    EBPFMetricsExporter,
)


# ==================== MetricValidationStatus Tests ====================


class TestMetricValidationStatus:
    def test_enum_values(self):
        assert MetricValidationStatus.VALID.value == "valid"
        assert MetricValidationStatus.INVALID.value == "invalid"
        assert MetricValidationStatus.OUT_OF_RANGE.value == "out_of_range"
        assert MetricValidationStatus.TYPE_MISMATCH.value == "type_mismatch"


# ==================== MetricValidationResult Tests ====================


class TestMetricValidationResult:
    def test_default_fields(self):
        r = MetricValidationResult(
            name="test", value=42, status=MetricValidationStatus.VALID
        )
        assert r.name == "test"
        assert r.value == 42
        assert r.status == MetricValidationStatus.VALID
        assert r.message is None
        assert r.expected_type is None
        assert r.range_min is None
        assert r.range_max is None

    def test_all_fields(self):
        r = MetricValidationResult(
            name="m",
            value="bad",
            status=MetricValidationStatus.TYPE_MISMATCH,
            message="wrong type",
            expected_type=int,
            range_min=0,
            range_max=100,
        )
        assert r.message == "wrong type"
        assert r.expected_type is int
        assert r.range_min == 0
        assert r.range_max == 100


# ==================== ErrorCount Tests ====================


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

    def test_custom_values(self):
        ec = ErrorCount(total=5, map_read=2, export=3)
        assert ec.total == 5
        assert ec.map_read == 2
        assert ec.export == 3


# ==================== MetricSanitizer Tests ====================


class TestMetricSanitizer:
    def setup_method(self):
        self.sanitizer = MetricSanitizer()

    def test_validate_exact_match_valid(self):
        result = self.sanitizer.validate("packet_counters", 100)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_exact_match_out_of_range_negative(self):
        result = self.sanitizer.validate("packet_counters", -1)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_exact_match_out_of_range_too_large(self):
        result = self.sanitizer.validate("packet_counters", 10**13)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_type_mismatch(self):
        result = self.sanitizer.validate("packet_counters", "not_a_number")
        assert result.status == MetricValidationStatus.TYPE_MISMATCH
        assert "Expected type" in result.message

    def test_validate_pattern_match_packet(self):
        result = self.sanitizer.validate("my_packet_metric", 500)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_counter(self):
        result = self.sanitizer.validate("some_counter", 10)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_latency(self):
        result = self.sanitizer.validate("request_latency", 50.5)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_ms(self):
        result = self.sanitizer.validate("response_ms", 100)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_bytes(self):
        result = self.sanitizer.validate("total_bytes", 1024)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_transfer(self):
        result = self.sanitizer.validate("data_transfer", 2048)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_interface(self):
        result = self.sanitizer.validate("interface_eth0", 5)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_pattern_match_count(self):
        result = self.sanitizer.validate("error_count", 3)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_no_rules_match(self):
        """Metrics with no matching rule use default (int, float) type check."""
        result = self.sanitizer.validate("unknown_metric", 42)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_no_rules_match_type_mismatch(self):
        result = self.sanitizer.validate("unknown_metric", "string_val")
        assert result.status == MetricValidationStatus.TYPE_MISMATCH

    def test_validate_latency_out_of_range(self):
        result = self.sanitizer.validate("latency_ms", 70000)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_interface_count_out_of_range(self):
        result = self.sanitizer.validate("interface_count", 200)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_sanitize_all_valid(self):
        metrics = {"packet_counters": 10, "latency_ms": 5.0}
        valid, results = self.sanitizer.sanitize(metrics)
        assert len(valid) == 2
        assert all(r.status == MetricValidationStatus.VALID for r in results)

    def test_sanitize_mixed(self):
        metrics = {"packet_counters": 10, "latency_ms": "bad"}
        valid, results = self.sanitizer.sanitize(metrics)
        assert "packet_counters" in valid
        assert "latency_ms" not in valid
        assert len(results) == 2

    def test_sanitize_empty(self):
        valid, results = self.sanitizer.sanitize({})
        assert valid == {}
        assert results == []

    def test_custom_validation_rules(self):
        custom_rules = {"cpu_temp": {"min": 0, "max": 100, "type": (int, float)}}
        s = MetricSanitizer(validation_rules=custom_rules)
        assert s.validate("cpu_temp", 50).status == MetricValidationStatus.VALID
        assert s.validate("cpu_temp", 200).status == MetricValidationStatus.OUT_OF_RANGE

    def test_validate_boundary_values(self):
        # Exactly at min
        result = self.sanitizer.validate("packet_counters", 0)
        assert result.status == MetricValidationStatus.VALID
        # Exactly at max
        result = self.sanitizer.validate("packet_counters", 10**12)
        assert result.status == MetricValidationStatus.VALID

    def test_validate_float_for_latency(self):
        result = self.sanitizer.validate("latency_ms", 0.001)
        assert result.status == MetricValidationStatus.VALID


# ==================== Exception Tests ====================


class TestExceptions:
    def test_ebpf_metrics_error_basic(self):
        e = EBPFMetricsError("test error")
        assert str(e) == "test error"
        assert e.context == {}
        assert isinstance(e.timestamp, float)

    def test_ebpf_metrics_error_with_context(self):
        ctx = {"key": "value"}
        e = EBPFMetricsError("test", context=ctx)
        assert e.context == ctx

    def test_ebpf_metrics_error_to_dict(self):
        e = EBPFMetricsError("msg", context={"a": 1})
        d = e.to_dict()
        assert d["error_type"] == "EBPFMetricsError"
        assert d["message"] == "msg"
        assert d["context"] == {"a": 1}
        assert "timestamp" in d

    def test_map_read_error(self):
        e = MapReadError("read failed")
        assert isinstance(e, EBPFMetricsError)
        assert str(e) == "read failed"

    def test_bpftool_error(self):
        e = BpftoolError("cmd failed", ["bpftool", "map"], "err output", 1)
        assert e.command == ["bpftool", "map"]
        assert e.stderr == "err output"
        assert e.returncode == 1
        assert "bpftool map" in e.context["command"]

    def test_prometheus_export_error(self):
        e = PrometheusExportError("export failed")
        assert isinstance(e, EBPFMetricsError)

    def test_metric_registration_error(self):
        e = MetricRegistrationError("reg failed")
        assert isinstance(e, EBPFMetricsError)

    def test_parse_error(self):
        e = ParseError("parse failed")
        assert isinstance(e, EBPFMetricsError)

    def test_timeout_error(self):
        e = TimeoutError("timed out")
        assert isinstance(e, EBPFMetricsError)


# ==================== RetryConfig Tests ====================


class TestRetryConfig:
    def test_defaults(self):
        rc = RetryConfig()
        assert rc.max_retries == 3
        assert rc.base_delay == 1.0
        assert rc.max_delay == 30.0
        assert rc.exponential_base == 2.0
        assert rc.jitter is True

    def test_custom(self):
        rc = RetryConfig(max_retries=5, base_delay=0.5, jitter=False)
        assert rc.max_retries == 5
        assert rc.base_delay == 0.5
        assert rc.jitter is False


# ==================== with_retry Tests ====================


class TestWithRetry:
    def test_success_on_first_try(self):
        config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)

        @with_retry(config=config, exceptions=(ValueError,))
        def good_func():
            return "ok"

        assert good_func() == "ok"

    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    def test_retry_then_succeed(self, mock_sleep):
        config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        call_count = 0

        @with_retry(config=config, exceptions=(ValueError,))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        assert flaky_func() == "ok"
        assert call_count == 3

    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)

        @with_retry(config=config, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            always_fail()

    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    def test_on_retry_callback(self, mock_sleep):
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)
        callback = MagicMock()
        call_count = 0

        @with_retry(config=config, exceptions=(ValueError,), on_retry=callback)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        flaky()
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == 0  # attempt number
        assert isinstance(args[1], ValueError)

    def test_default_config(self):
        """with_retry with no config uses defaults."""

        @with_retry(exceptions=(RuntimeError,))
        def func():
            return "ok"

        assert func() == "ok"

    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    def test_jitter_applied(self, mock_sleep):
        config = RetryConfig(max_retries=1, base_delay=1.0, jitter=True)
        call_count = 0

        @with_retry(config=config, exceptions=(ValueError,))
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        with patch("random.random", return_value=0.5):
            flaky()

    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    def test_max_delay_cap(self, mock_sleep):
        config = RetryConfig(
            max_retries=1, base_delay=100.0, max_delay=5.0, jitter=False
        )
        call_count = 0

        @with_retry(config=config, exceptions=(ValueError,))
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        flaky()
        # delay should be capped at max_delay (5.0)
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == 5.0

    def test_non_matching_exception_not_retried(self):
        config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)

        @with_retry(config=config, exceptions=(ValueError,))
        def raise_type_error():
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raise_type_error()


# ==================== DegradationLevel Tests ====================


class TestDegradationLevel:
    def test_enum_values(self):
        assert DegradationLevel.FULL.value == "full"
        assert DegradationLevel.DEGRADED.value == "degraded"
        assert DegradationLevel.MINIMAL.value == "minimal"
        assert DegradationLevel.OFFLINE.value == "offline"


# ==================== DegradationState Tests ====================


class TestDegradationState:
    def test_defaults(self):
        ds = DegradationState()
        assert ds.level == DegradationLevel.FULL
        assert ds.prometheus_available is True
        assert ds.bpftool_available is True
        assert ds.consecutive_failures == 0
        assert ds.error_count == 0

    def test_update_prometheus_status_available(self):
        ds = DegradationState()
        ds.prometheus_available = False
        ds.consecutive_failures = 3
        ds.update_prometheus_status(True)
        assert ds.consecutive_failures == 0
        assert ds.prometheus_available is True
        assert ds.level == DegradationLevel.FULL

    def test_update_prometheus_status_unavailable(self):
        ds = DegradationState()
        ds.update_prometheus_status(False)
        assert ds.consecutive_failures == 1
        assert ds.error_count == 1
        assert ds.prometheus_available is False

    def test_recalculate_level_full(self):
        ds = DegradationState()
        ds.prometheus_available = True
        ds.bpftool_available = True
        ds._recalculate_level()
        assert ds.level == DegradationLevel.FULL

    def test_recalculate_level_degraded(self):
        ds = DegradationState()
        ds.prometheus_available = False
        ds.bpftool_available = True
        ds._recalculate_level()
        assert ds.level == DegradationLevel.DEGRADED

    def test_recalculate_level_minimal(self):
        ds = DegradationState()
        ds.prometheus_available = True
        ds.bpftool_available = False
        ds._recalculate_level()
        assert ds.level == DegradationLevel.MINIMAL

    def test_recalculate_level_offline(self):
        ds = DegradationState()
        ds.prometheus_available = False
        ds.bpftool_available = False
        ds._recalculate_level()
        assert ds.level == DegradationLevel.OFFLINE

    def test_recovery_logs(self):
        """When prometheus recovers from unavailable, it logs recovery."""
        ds = DegradationState()
        ds.prometheus_available = False
        ds.update_prometheus_status(True)
        assert ds.prometheus_available is True


# ==================== GracefulShutdown Tests ====================


class TestGracefulShutdown:
    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_init_registers_signals(self, mock_signal):
        gs = GracefulShutdown()
        assert not gs.shutdown_requested
        # Should register SIGINT and SIGTERM handlers
        assert mock_signal.call_count == 2

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_signal_handler_sets_flag(self, mock_signal):
        gs = GracefulShutdown()
        gs._signal_handler(signal.SIGTERM, None)
        assert gs.shutdown_requested is True

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_signal_handler_calls_callbacks(self, mock_signal):
        gs = GracefulShutdown()
        callback = MagicMock()
        gs.register_callback(callback)
        gs._signal_handler(signal.SIGTERM, None)
        callback.assert_called_once()

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_signal_handler_callback_error(self, mock_signal):
        gs = GracefulShutdown()
        bad_callback = MagicMock(side_effect=RuntimeError("oops"))
        gs.register_callback(bad_callback)
        # Should not raise
        gs._signal_handler(signal.SIGTERM, None)
        assert gs.shutdown_requested is True

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_is_shutdown_requested(self, mock_signal):
        gs = GracefulShutdown()
        assert gs.is_shutdown_requested() is False
        gs.shutdown_requested = True
        assert gs.is_shutdown_requested() is True

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    def test_multiple_callbacks(self, mock_signal):
        gs = GracefulShutdown()
        cb1 = MagicMock()
        cb2 = MagicMock()
        gs.register_callback(cb1)
        gs.register_callback(cb2)
        gs._signal_handler(signal.SIGINT, None)
        cb1.assert_called_once()
        cb2.assert_called_once()


# ==================== StructuredLogger Tests ====================


class TestStructuredLogger:
    def test_set_context(self):
        sl = StructuredLogger("test")
        sl.set_context(component="test_comp", version="1.0")
        assert sl._context["component"] == "test_comp"
        assert sl._context["version"] == "1.0"

    def test_clear_context(self):
        sl = StructuredLogger("test")
        sl.set_context(key="val")
        sl.clear_context()
        assert sl._context == {}

    def test_format_extra_no_args(self):
        sl = StructuredLogger("test")
        sl.set_context(a=1)
        result = sl._format_extra()
        assert result == {"a": 1}

    def test_format_extra_with_extra(self):
        sl = StructuredLogger("test")
        sl.set_context(a=1)
        result = sl._format_extra({"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_format_extra_override(self):
        sl = StructuredLogger("test")
        sl.set_context(a=1)
        result = sl._format_extra({"a": 99})
        assert result == {"a": 99}

    @patch("logging.Logger.debug")
    def test_debug(self, mock_debug):
        sl = StructuredLogger("test")
        sl.debug("msg", key="val")
        mock_debug.assert_called_once()

    @patch("logging.Logger.info")
    def test_info(self, mock_info):
        sl = StructuredLogger("test")
        sl.info("msg")
        mock_info.assert_called_once()

    @patch("logging.Logger.warning")
    def test_warning(self, mock_warn):
        sl = StructuredLogger("test")
        sl.warning("msg")
        mock_warn.assert_called_once()

    @patch("logging.Logger.error")
    def test_error_without_exception(self, mock_err):
        sl = StructuredLogger("test")
        sl.error("msg")
        mock_err.assert_called_once()

    @patch("logging.Logger.error")
    def test_error_with_exception(self, mock_err):
        sl = StructuredLogger("test")
        e = ValueError("bad")
        sl.error("msg", error=e)
        mock_err.assert_called_once()
        extra = mock_err.call_args[1]["extra"]
        assert extra["error_type"] == "ValueError"
        assert extra["error_message"] == "bad"

    @patch("logging.Logger.error")
    def test_error_with_ebpf_error(self, mock_err):
        sl = StructuredLogger("test")
        e = EBPFMetricsError("fail", context={"detail": "info"})
        sl.error("msg", error=e)
        extra = mock_err.call_args[1]["extra"]
        assert extra["error_context"] == {"detail": "info"}

    @patch("logging.Logger.critical")
    def test_critical_without_error(self, mock_crit):
        sl = StructuredLogger("test")
        sl.critical("msg")
        mock_crit.assert_called_once()

    @patch("logging.Logger.critical")
    def test_critical_with_error(self, mock_crit):
        sl = StructuredLogger("test")
        e = RuntimeError("critical")
        sl.critical("msg", error=e)
        extra = mock_crit.call_args[1]["extra"]
        assert extra["error_type"] == "RuntimeError"


# ==================== PrometheusExporter Tests ====================


class TestPrometheusExporter:
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_init_with_prometheus(self):
        pe = PrometheusExporter(port=9999)
        assert pe.port == 9999
        assert pe.metrics == {}
        assert pe._server_started is False

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", False)
    def test_init_without_prometheus(self):
        pe = PrometheusExporter()
        assert pe.degradation.prometheus_available is False

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", False)
    def test_start_server_no_prometheus(self):
        pe = PrometheusExporter()
        result = pe.start_server()
        assert result is False

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_start_server_already_started(self):
        pe = PrometheusExporter()
        pe._server_started = True
        assert pe.start_server() is True

    @patch("src.network.ebpf.metrics_exporter.start_http_server")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_start_server_success(self, mock_start):
        pe = PrometheusExporter(port=9091)
        result = pe.start_server()
        assert result is True
        assert pe._server_started is True
        mock_start.assert_called_once_with(9091)

    @patch("src.network.ebpf.metrics_exporter.start_http_server", side_effect=OSError("bind"))
    @patch("src.network.ebpf.metrics_exporter.time.sleep")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_start_server_os_error(self, mock_sleep, mock_start):
        pe = PrometheusExporter(port=9091)
        with pytest.raises(PrometheusExportError):
            pe.start_server()

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", False)
    def test_create_gauge_no_prometheus(self):
        pe = PrometheusExporter()
        assert pe.create_gauge("test", "desc") is None

    @patch("src.network.ebpf.metrics_exporter.Gauge")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_gauge_new(self, mock_gauge_cls):
        mock_gauge = MagicMock()
        mock_gauge_cls.return_value = mock_gauge
        pe = PrometheusExporter()
        result = pe.create_gauge("test_gauge", "A test gauge", ["label1"])
        assert result == mock_gauge
        assert "test_gauge" in pe.metrics
        mock_gauge_cls.assert_called_once_with("test_gauge", "A test gauge", ["label1"])

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_gauge_existing(self):
        pe = PrometheusExporter()
        existing = MagicMock()
        pe.metrics["existing_gauge"] = existing
        result = pe.create_gauge("existing_gauge", "desc")
        assert result is existing

    @patch("src.network.ebpf.metrics_exporter.Gauge", side_effect=Exception("fail"))
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_gauge_error(self, mock_gauge_cls):
        pe = PrometheusExporter()
        with pytest.raises(MetricRegistrationError):
            pe.create_gauge("bad_gauge", "desc")

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", False)
    def test_create_counter_no_prometheus(self):
        pe = PrometheusExporter()
        assert pe.create_counter("test", "desc") is None

    @patch("src.network.ebpf.metrics_exporter.Counter")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_counter_new(self, mock_counter_cls):
        mock_counter = MagicMock()
        mock_counter_cls.return_value = mock_counter
        pe = PrometheusExporter()
        result = pe.create_counter("test_counter", "A counter", [])
        assert result == mock_counter
        assert "test_counter" in pe.metrics

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_counter_existing(self):
        pe = PrometheusExporter()
        existing = MagicMock()
        pe.metrics["c"] = existing
        assert pe.create_counter("c", "desc") is existing

    @patch("src.network.ebpf.metrics_exporter.Counter", side_effect=Exception("fail"))
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_counter_error(self, mock_counter_cls):
        pe = PrometheusExporter()
        with pytest.raises(MetricRegistrationError):
            pe.create_counter("bad", "desc")

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", False)
    def test_create_histogram_no_prometheus(self):
        pe = PrometheusExporter()
        assert pe.create_histogram("test", "desc") is None

    @patch("src.network.ebpf.metrics_exporter.Histogram")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_histogram_new(self, mock_hist_cls):
        mock_hist = MagicMock()
        mock_hist_cls.return_value = mock_hist
        pe = PrometheusExporter()
        result = pe.create_histogram("test_hist", "A histogram", ["op"])
        assert result == mock_hist
        assert "test_hist" in pe.metrics

    @patch("src.network.ebpf.metrics_exporter.Histogram")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_histogram_with_buckets(self, mock_hist_cls):
        mock_hist = MagicMock()
        mock_hist_cls.return_value = mock_hist
        pe = PrometheusExporter()
        buckets = (0.1, 0.5, 1.0)
        pe.create_histogram("h", "desc", buckets=buckets)
        mock_hist_cls.assert_called_once_with("h", "desc", labelnames=[], buckets=buckets)

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_histogram_existing(self):
        pe = PrometheusExporter()
        existing = MagicMock()
        pe.metrics["h"] = existing
        assert pe.create_histogram("h", "desc") is existing

    @patch("src.network.ebpf.metrics_exporter.Histogram", side_effect=Exception("fail"))
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_histogram_error(self, mock_hist_cls):
        pe = PrometheusExporter()
        with pytest.raises(MetricRegistrationError):
            pe.create_histogram("bad", "desc")

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_export_to_fallback_success(self, tmp_path=None):
        pe = PrometheusExporter()
        pe._fallback_file = Path("/tmp/test_fallback_metrics.json")
        pe.export_to_fallback({"metric1": 42})
        # Verify file was written
        assert pe._fallback_file.exists()
        data = json.loads(pe._fallback_file.read_text())
        assert data["metrics"]["metric1"] == 42
        assert "timestamp" in data
        pe._fallback_file.unlink(missing_ok=True)

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_export_to_fallback_error(self):
        pe = PrometheusExporter()
        pe._fallback_file = Path("/nonexistent/dir/file.json")
        # Should not raise, just log error
        pe.export_to_fallback({"m": 1})

    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def test_create_gauge_no_labels(self):
        with patch("src.network.ebpf.metrics_exporter.Gauge") as mock_gauge_cls:
            mock_gauge_cls.return_value = MagicMock()
            pe = PrometheusExporter()
            pe.create_gauge("g", "desc")
            mock_gauge_cls.assert_called_once_with("g", "desc", [])


# ==================== EBPFMetricsExporter Tests ====================


class TestEBPFMetricsExporter:
    """Tests for the main EBPFMetricsExporter class."""

    @patch("src.network.ebpf.metrics_exporter.signal.signal")
    @patch("src.network.ebpf.metrics_exporter.PROMETHEUS_AVAILABLE", True)
    def _make_exporter(self, mock_signal, port=9090):
        return EBPFMetricsExporter(prometheus_port=port)

    def test_init(self):
        exp = self._make_exporter()
        assert exp.registered_maps == {}
        assert isinstance(exp.prometheus, PrometheusExporter)
        assert isinstance(exp.sanitizer, MetricSanitizer)
        assert isinstance(exp.error_count, ErrorCount)
        assert "export_time" in exp.performance_stats

    def test_register_map_per_cpu_array(self):
        exp = self._make_exporter()
        with patch.object(exp.prometheus, "create_gauge") as mock_gauge:
            exp.register_map("pkt_counters", "xdp_counter", "per_cpu_array")
            assert "pkt_counters" in exp.registered_maps
            assert exp.registered_maps["pkt_counters"]["program"] == "xdp_counter"
            assert exp.registered_maps["pkt_counters"]["type"] == "per_cpu_array"
            # Should create 4 gauge metrics (tcp, udp, icmp, other)
            assert mock_gauge.call_count == 4

    def test_register_map_histogram(self):
        exp = self._make_exporter()
        with patch.object(exp.prometheus, "create_histogram") as mock_hist:
            exp.register_map("lat_map", "lat_prog", "histogram")
            assert "lat_map" in exp.registered_maps
            mock_hist.assert_called_once()

    def test_register_map_unknown_type(self):
        exp = self._make_exporter()
        # Should still register, just no prometheus metrics created
        exp.register_map("m", "p", "ringbuf")
        assert "m" in exp.registered_maps

    def test_register_map_error(self):
        exp = self._make_exporter()
        with patch.object(
            exp.prometheus, "create_gauge", side_effect=Exception("boom")
        ):
            with pytest.raises(MetricRegistrationError):
                exp.register_map("m", "p", "per_cpu_array")

    def test_parse_per_cpu_array_empty(self):
        exp = self._make_exporter()
        result = exp._parse_per_cpu_array("")
        assert result == [0, 0, 0, 0]

    def test_parse_per_cpu_array_valid_list(self):
        exp = self._make_exporter()
        data = json.dumps([
            {"key": 0, "value": [10, 20, 30]},
            {"key": 1, "value": [5, 15]},
            {"key": 2, "value": [100]},
            {"key": 3, "value": [7, 3]},
        ])
        result = exp._parse_per_cpu_array(data)
        assert result == [60, 20, 100, 10]

    def test_parse_per_cpu_array_single_dict(self):
        exp = self._make_exporter()
        data = json.dumps({"key": 0, "value": [5, 10]})
        result = exp._parse_per_cpu_array(data)
        assert result == [15, 0, 0, 0]

    def test_parse_per_cpu_array_scalar_values(self):
        exp = self._make_exporter()
        data = json.dumps([{"key": 0, "value": 42}])
        result = exp._parse_per_cpu_array(data)
        assert result == [42, 0, 0, 0]

    def test_parse_per_cpu_array_invalid_json(self):
        exp = self._make_exporter()
        with pytest.raises(ParseError):
            exp._parse_per_cpu_array("{invalid json")

    def test_parse_per_cpu_array_key_out_of_range(self):
        exp = self._make_exporter()
        data = json.dumps([{"key": 10, "value": [100]}])
        result = exp._parse_per_cpu_array(data)
        assert result == [0, 0, 0, 0]

    def test_parse_per_cpu_array_non_numeric_values(self):
        exp = self._make_exporter()
        data = json.dumps([{"key": 0, "value": ["not_num", 5]}])
        result = exp._parse_per_cpu_array(data)
        assert result == [5, 0, 0, 0]

    def test_parse_per_cpu_array_non_numeric_scalar(self):
        exp = self._make_exporter()
        data = json.dumps([{"key": 0, "value": "string_val"}])
        result = exp._parse_per_cpu_array(data)
        assert result == [0, 0, 0, 0]

    def test_parse_per_cpu_array_unexpected_error(self):
        """Unexpected error returns zeros."""
        exp = self._make_exporter()
        # A valid JSON but with something that triggers an unexpected error
        # e.g., value that isn't iterable and not a number
        data = json.dumps([{"key": 0, "value": None}])
        result = exp._parse_per_cpu_array(data)
        assert result == [0, 0, 0, 0]

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_success(self, mock_run):
        exp = self._make_exporter()
        # First call: map show
        show_result = MagicMock()
        show_result.returncode = 0
        show_result.stdout = json.dumps([{"id": 42, "name": "test_map"}])
        # Second call: map dump
        dump_result = MagicMock()
        dump_result.returncode = 0
        dump_result.stdout = json.dumps([{"key": 0, "value": [10]}])
        mock_run.side_effect = [show_result, dump_result]

        result = exp._read_map_via_bpftool("test_map")
        assert result is not None
        assert result["map_id"] == 42
        assert "raw_output" in result

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_map_not_found(self, mock_run):
        exp = self._make_exporter()
        result_mock = MagicMock()
        result_mock.returncode = 1
        result_mock.stderr = "not found"
        mock_run.return_value = result_mock

        result = exp._read_map_via_bpftool("nonexistent")
        assert result is None

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_empty_map_info(self, mock_run):
        exp = self._make_exporter()
        result_mock = MagicMock()
        result_mock.returncode = 0
        result_mock.stdout = "[]"
        mock_run.return_value = result_mock

        result = exp._read_map_via_bpftool("empty")
        assert result is None

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_no_id(self, mock_run):
        exp = self._make_exporter()
        result_mock = MagicMock()
        result_mock.returncode = 0
        result_mock.stdout = json.dumps([{"name": "test"}])
        mock_run.return_value = result_mock

        result = exp._read_map_via_bpftool("test")
        assert result is None

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_json_decode_error(self, mock_run):
        exp = self._make_exporter()
        result_mock = MagicMock()
        result_mock.returncode = 0
        result_mock.stdout = "not json"
        mock_run.return_value = result_mock

        with pytest.raises(ParseError):
            exp._read_map_via_bpftool("test")

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_dump_fails(self, mock_run):
        exp = self._make_exporter()
        show_result = MagicMock()
        show_result.returncode = 0
        show_result.stdout = json.dumps([{"id": 1}])
        dump_result = MagicMock()
        dump_result.returncode = 1
        dump_result.stderr = "dump error"
        mock_run.side_effect = [show_result, dump_result]

        with pytest.raises(BpftoolError):
            exp._read_map_via_bpftool("test")

    @patch("src.network.ebpf.metrics_exporter.subprocess.run", side_effect=FileNotFoundError)
    def test_read_map_via_bpftool_not_installed(self, mock_run):
        exp = self._make_exporter()
        result = exp._read_map_via_bpftool("test")
        assert result is None
        assert exp.prometheus.degradation.bpftool_available is False

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_timeout(self, mock_run):
        exp = self._make_exporter()
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bpftool", timeout=5)

        with pytest.raises(TimeoutError):
            exp._read_map_via_bpftool("test")

    def test_read_map_via_bpftool_shutdown_requested(self):
        exp = self._make_exporter()
        exp.shutdown.shutdown_requested = True
        result = exp._read_map_via_bpftool("test")
        assert result is None

    @patch("src.network.ebpf.metrics_exporter.subprocess.run")
    def test_read_map_via_bpftool_dict_format(self, mock_run):
        """Map info as dict instead of list."""
        exp = self._make_exporter()
        show_result = MagicMock()
        show_result.returncode = 0
        show_result.stdout = json.dumps({"id": 7, "name": "m"})
        dump_result = MagicMock()
        dump_result.returncode = 0
        dump_result.stdout = json.dumps([{"key": 0, "value": [1]}])
        mock_run.side_effect = [show_result, dump_result]

        result = exp._read_map_via_bpftool("m")
        assert result["map_id"] == 7

    def test_collect_all_metrics_empty(self):
        exp = self._make_exporter()
        metrics = exp._collect_all_metrics()
        assert metrics == {}

    def test_collect_all_metrics_with_maps(self):
        exp = self._make_exporter()
        exp.registered_maps["test_map"] = {"program": "prog", "type": "per_cpu_array"}
        with patch.object(
            exp, "_read_map_via_bpftool", return_value={"raw_output": "[]", "map_id": 1}
        ):
            with patch.object(exp, "_parse_per_cpu_array", return_value=[10, 20, 30, 40]):
                metrics = exp._collect_all_metrics()
                assert metrics["ebpf_prog_tcp_packets"] == 10
                assert metrics["ebpf_prog_udp_packets"] == 20
                assert metrics["ebpf_prog_icmp_packets"] == 30
                assert metrics["ebpf_prog_other_packets"] == 40

    def test_collect_all_metrics_read_returns_none(self):
        exp = self._make_exporter()
        exp.registered_maps["m"] = {"program": "p", "type": "per_cpu_array"}
        with patch.object(exp, "_read_map_via_bpftool", return_value=None):
            metrics = exp._collect_all_metrics()
            assert metrics == {}

    def test_collect_all_metrics_ebpf_error(self):
        exp = self._make_exporter()
        exp.registered_maps["m"] = {"program": "p", "type": "per_cpu_array"}
        with patch.object(
            exp, "_read_map_via_bpftool", side_effect=MapReadError("fail")
        ):
            metrics = exp._collect_all_metrics()
            assert metrics == {}

    def test_collect_all_metrics_unexpected_error(self):
        exp = self._make_exporter()
        exp.registered_maps["m"] = {"program": "p", "type": "per_cpu_array"}
        with patch.object(
            exp, "_read_map_via_bpftool", side_effect=RuntimeError("unexpected")
        ):
            metrics = exp._collect_all_metrics()
            assert metrics == {}

    def test_collect_all_metrics_with_validation(self):
        exp = self._make_exporter()
        with patch.object(exp, "_collect_all_metrics", return_value={"packet_counters": 10}):
            with patch.object(
                exp,
                "_validate_and_sanitize",
                return_value=(
                    {"packet_counters": 10},
                    [MetricValidationResult("packet_counters", 10, MetricValidationStatus.VALID)],
                ),
            ):
                valid, results = exp._collect_all_metrics_with_validation()
                assert "packet_counters" in valid
                assert len(results) == 1

    def test_collect_all_metrics_with_validation_error(self):
        exp = self._make_exporter()
        with patch.object(exp, "_collect_all_metrics", side_effect=RuntimeError("fail")):
            valid, results = exp._collect_all_metrics_with_validation()
            assert valid == {}
            assert results == []
            assert exp.error_count.map_read == 1
            assert exp.error_count.total == 1

    def test_validate_and_sanitize(self):
        exp = self._make_exporter()
        metrics = {"packet_counters": 10, "latency_ms": "bad"}
        valid, results = exp._validate_and_sanitize(metrics)
        assert "packet_counters" in valid
        assert "latency_ms" not in valid

    def test_validate_and_sanitize_increments_error_count(self):
        exp = self._make_exporter()
        metrics = {"latency_ms": "bad"}
        exp._validate_and_sanitize(metrics)
        assert exp.error_count.validation == 1
        assert exp.error_count.total == 1

    def test_validate_and_sanitize_no_errors(self):
        exp = self._make_exporter()
        metrics = {"packet_counters": 10}
        valid, results = exp._validate_and_sanitize(metrics)
        assert exp.error_count.validation == 0

    def test_track_performance(self):
        exp = self._make_exporter()
        exp._track_performance("export_time", 0.1)
        exp._track_performance("export_time", 0.2)
        assert len(exp.performance_stats["export_time"]) == 2

    def test_track_performance_new_metric(self):
        exp = self._make_exporter()
        exp._track_performance("new_metric", 0.5)
        assert "new_metric" in exp.performance_stats
        assert exp.performance_stats["new_metric"] == [0.5]

    def test_track_performance_max_samples(self):
        exp = self._make_exporter()
        for i in range(110):
            exp._track_performance("export_time", float(i))
        assert len(exp.performance_stats["export_time"]) == 100

    def test_update_error_count(self):
        exp = self._make_exporter()
        exp._update_error_count("map_read")
        assert exp.error_count.map_read == 1
        assert exp.error_count.total == 1

    def test_update_error_count_unknown_type(self):
        exp = self._make_exporter()
        exp._update_error_count("nonexistent_type")
        # total still incremented
        assert exp.error_count.total == 1

    def test_export_metrics_empty(self):
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            result = exp.export_metrics()
            assert result == {}

    def test_export_metrics_with_custom_metrics(self):
        exp = self._make_exporter()
        mock_metric = MagicMock()
        mock_metric.set = MagicMock()
        exp.prometheus.metrics["my_gauge"] = mock_metric

        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            result = exp.export_metrics(custom_metrics={"my_gauge": 42})
            assert result["my_gauge"] == 42
            mock_metric.set.assert_called_with(42)

    def test_export_metrics_creates_counter_for_total(self):
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            with patch.object(exp.prometheus, "create_counter") as mock_cc:
                mock_cc.return_value = MagicMock()
                exp.export_metrics(custom_metrics={"request_total": 100})
                mock_cc.assert_called()

    def test_export_metrics_creates_gauge_for_other(self):
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            with patch.object(exp.prometheus, "create_gauge") as mock_cg:
                mock_g = MagicMock()
                mock_cg.return_value = mock_g
                exp.export_metrics(custom_metrics={"temperature": 36.5})
                mock_cg.assert_called()

    def test_export_metrics_fallback_when_prometheus_unavailable(self):
        exp = self._make_exporter()
        exp.prometheus.degradation.prometheus_available = False
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            with patch.object(exp.prometheus, "export_to_fallback") as mock_fb:
                exp.export_metrics()
                mock_fb.assert_called_once()

    def test_export_metrics_error_handling(self):
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", side_effect=RuntimeError("boom")
        ):
            result = exp.export_metrics()
            assert result == {}
            assert exp.error_count.export == 1

    def test_export_metrics_individual_metric_error(self):
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            # create_gauge raises on the metric
            with patch.object(
                exp.prometheus, "create_gauge", side_effect=Exception("reg fail")
            ):
                result = exp.export_metrics(custom_metrics={"bad_metric": 1})
                # Should not crash, just skip the metric
                assert "bad_metric" not in result
                assert exp.error_count.export >= 1

    def test_export_metrics_logs_invalid_validations(self):
        exp = self._make_exporter()
        invalid_result = MetricValidationResult(
            "bad", "x", MetricValidationStatus.TYPE_MISMATCH, message="wrong"
        )
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [invalid_result])
        ):
            exp.export_metrics()

    def test_export_metrics_metric_without_set(self):
        """If metric has no set method, it's still exported."""
        exp = self._make_exporter()
        mock_metric = MagicMock(spec=[])  # no 'set' method
        exp.prometheus.metrics["no_set"] = mock_metric
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            result = exp.export_metrics(custom_metrics={"no_set": 5})
            assert result["no_set"] == 5

    def test_get_error_summary(self):
        exp = self._make_exporter()
        exp.error_count.total = 10
        exp.error_count.map_read = 3
        exp.error_count.export = 7
        summary = exp.get_error_summary()
        assert summary["total"] == 10
        assert summary["map_read"] == 3
        assert summary["export"] == 7
        assert summary["bpftool"] == 0

    def test_get_performance_stats_empty(self):
        exp = self._make_exporter()
        stats = exp.get_performance_stats()
        assert stats == {}

    def test_get_performance_stats_with_data(self):
        exp = self._make_exporter()
        exp.performance_stats["export_time"] = [0.01, 0.02, 0.03]
        stats = exp.get_performance_stats()
        assert "export_time" in stats
        assert stats["export_time"]["count"] == 3
        assert stats["export_time"]["min_ms"] == pytest.approx(10.0)
        assert stats["export_time"]["max_ms"] == pytest.approx(30.0)
        assert stats["export_time"]["latest_ms"] == pytest.approx(30.0)
        assert stats["export_time"]["average_ms"] == pytest.approx(20.0)

    def test_get_health_status_healthy(self):
        exp = self._make_exporter()
        status = exp.get_health_status()
        assert status["overall"] == "healthy"
        assert "degradation" in status
        assert "errors" in status
        assert "performance" in status

    def test_get_health_status_degraded(self):
        exp = self._make_exporter()
        exp.error_count.total = 51
        status = exp.get_health_status()
        assert status["overall"] == "degraded"

    def test_get_health_status_degraded_by_level(self):
        exp = self._make_exporter()
        exp.prometheus.degradation.prometheus_available = False
        exp.prometheus.degradation.bpftool_available = True
        exp.prometheus.degradation._recalculate_level()
        status = exp.get_health_status()
        assert status["overall"] == "degraded"

    def test_get_health_status_unhealthy_by_failures(self):
        exp = self._make_exporter()
        exp.prometheus.degradation.consecutive_failures = 6
        status = exp.get_health_status()
        assert status["overall"] == "unhealthy"

    def test_get_health_status_unhealthy_by_errors(self):
        exp = self._make_exporter()
        exp.error_count.total = 101
        status = exp.get_health_status()
        assert status["overall"] == "unhealthy"

    def test_reset_error_counts(self):
        exp = self._make_exporter()
        exp.error_count.total = 50
        exp.error_count.map_read = 10
        exp.reset_error_counts()
        assert exp.error_count.total == 0
        assert exp.error_count.map_read == 0

    def test_dump_diagnostics(self):
        exp = self._make_exporter()
        diag_file = "/tmp/test_ebpf_diagnostics.json"
        exp.dump_diagnostics(diag_file)
        with open(diag_file) as f:
            data = json.load(f)
        assert data["version"] == "2.0"
        assert "health" in data
        assert "registered_maps" in data
        Path(diag_file).unlink(missing_ok=True)

    def test_dump_diagnostics_error(self):
        exp = self._make_exporter()
        # Should not raise on write error
        exp.dump_diagnostics("/nonexistent/path/diag.json")

    def test_get_metrics_summary(self):
        exp = self._make_exporter()
        exp.registered_maps["m1"] = {"program": "p1", "type": "per_cpu_array"}
        summary = exp.get_metrics_summary()
        assert summary["registered_maps"] == 1
        assert "m1" in summary["maps"]
        assert "degradation_level" in summary
        assert "prometheus_available" in summary
        assert "bpftool_available" in summary

    def test_get_degradation_status(self):
        exp = self._make_exporter()
        status = exp.get_degradation_status()
        assert status["level"] == "full"
        assert status["prometheus_available"] is True
        assert status["bpftool_available"] is True
        assert status["consecutive_failures"] == 0
        assert status["total_errors"] == 0

    def test_get_degradation_status_string_level(self):
        """If level is already a string (edge case), it's returned as-is."""
        exp = self._make_exporter()
        exp.prometheus.degradation.level = "custom_string"
        status = exp.get_degradation_status()
        assert status["level"] == "custom_string"

    def test_on_shutdown(self):
        exp = self._make_exporter()
        with patch.object(exp, "_collect_all_metrics", return_value={"m": 1}):
            with patch.object(exp.prometheus, "export_to_fallback") as mock_fb:
                exp._on_shutdown()
                mock_fb.assert_called_once()

    def test_on_shutdown_error(self):
        exp = self._make_exporter()
        with patch.object(exp, "_collect_all_metrics", side_effect=RuntimeError("fail")):
            # Should not raise
            exp._on_shutdown()

    def test_export_metrics_with_map_metrics_and_custom(self):
        """Integration-style: both map and custom metrics exported."""
        exp = self._make_exporter()
        map_metrics = {"ebpf_prog_tcp_packets": 100}
        valid_result = MetricValidationResult(
            "ebpf_prog_tcp_packets", 100, MetricValidationStatus.VALID
        )
        with patch.object(
            exp,
            "_collect_all_metrics_with_validation",
            return_value=(map_metrics, [valid_result]),
        ):
            mock_metric = MagicMock()
            exp.prometheus.metrics["ebpf_prog_tcp_packets"] = mock_metric
            exp.prometheus.metrics["custom_val"] = MagicMock()

            result = exp.export_metrics(custom_metrics={"custom_val": 5})
            assert "ebpf_prog_tcp_packets" in result
            assert "custom_val" in result

    def test_export_metrics_custom_invalid_filtered(self):
        """Invalid custom metrics are filtered out by sanitizer."""
        exp = self._make_exporter()
        with patch.object(
            exp, "_collect_all_metrics_with_validation", return_value=({}, [])
        ):
            # "packet_counters" with string value -> type mismatch, filtered
            result = exp.export_metrics(custom_metrics={"packet_counters": "bad"})
            assert "packet_counters" not in result

    def test_collect_all_metrics_non_per_cpu_array(self):
        """Maps with non per_cpu_array type are not parsed as per_cpu_array."""
        exp = self._make_exporter()
        exp.registered_maps["m"] = {"program": "p", "type": "histogram"}
        with patch.object(
            exp,
            "_read_map_via_bpftool",
            return_value={"raw_output": "[]", "map_id": 1},
        ):
            metrics = exp._collect_all_metrics()
            # histogram type not handled in _collect_all_metrics
            assert metrics == {}
