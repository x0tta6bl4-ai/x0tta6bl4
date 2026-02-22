"""Unit tests for src.network.ebpf.metrics.logging_utils."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.network.ebpf.metrics.exceptions import EBPFMetricsError
from src.network.ebpf.metrics.logging_utils import StructuredLogger


def test_context_merge_and_clear():
    slog = StructuredLogger("test.logging")
    mock_logger = MagicMock()
    slog.logger = mock_logger

    slog.set_context(component="metrics", version="2.0")
    slog.info("start", metric_count=4)

    extra = mock_logger.info.call_args.kwargs["extra"]
    assert extra == {"component": "metrics", "version": "2.0", "metric_count": 4}

    context_copy = slog.get_context()
    context_copy["component"] = "changed"
    assert slog.get_context()["component"] == "metrics"

    slog.clear_context()
    assert slog.get_context() == {}


def test_error_with_ebpf_metrics_error_adds_error_context():
    slog = StructuredLogger("test.logging")
    mock_logger = MagicMock()
    slog.logger = mock_logger
    slog.set_context(component="reader")

    err = EBPFMetricsError("map read failed", context={"map": "packets_total"})
    slog.error("failed", error=err, operation="read_map")

    extra = mock_logger.error.call_args.kwargs["extra"]
    assert extra["component"] == "reader"
    assert extra["operation"] == "read_map"
    assert extra["error_type"] == "EBPFMetricsError"
    assert extra["error_message"] == "map read failed"
    assert extra["error_context"] == {"map": "packets_total"}


def test_critical_and_exception_with_generic_error():
    slog = StructuredLogger("test.logging")
    mock_logger = MagicMock()
    slog.logger = mock_logger

    err = RuntimeError("boom")
    slog.critical("critical failure", error=err, stage="export")
    critical_extra = mock_logger.critical.call_args.kwargs["extra"]
    assert critical_extra["stage"] == "export"
    assert critical_extra["error_type"] == "RuntimeError"
    assert critical_extra["error_message"] == "boom"

    slog.exception("exception path", error=err, stage="retry")
    exception_extra = mock_logger.exception.call_args.kwargs["extra"]
    assert exception_extra["stage"] == "retry"
    assert exception_extra["error_type"] == "RuntimeError"
    assert exception_extra["error_message"] == "boom"
