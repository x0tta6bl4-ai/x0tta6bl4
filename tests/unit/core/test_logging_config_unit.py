"""Unit tests for core logging configuration helpers."""

import json
import logging

from src.core.tracing_middleware import correlation_id_var
from src.core.logging_config import (RequestIdContextVar, SensitiveDataFilter,
                                     StructuredJsonFormatter,
                                     mask_sensitive_data, setup_logging)


def test_mask_sensitive_data_masks_credentials_and_ip():
    text = "password=secret token=abc 10.1.2.3"
    masked = mask_sensitive_data(text)
    assert "password=***" in masked
    assert "token=***" in masked
    assert "10.1.2.***" in masked
    assert "secret" not in masked


def test_sensitive_data_filter_masks_message_and_args():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="auth %s",
        args=("token=abc",),
        exc_info=None,
    )

    assert SensitiveDataFilter().filter(record) is True
    assert "token=***" in record.args[0]


def test_structured_json_formatter_outputs_json_with_extra_fields():
    record = logging.LogRecord(
        name="api",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="request ok",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.duration_ms = 12.3
    out = StructuredJsonFormatter().format(record)
    payload = json.loads(out)

    assert payload["logger"] == "api"
    assert payload["message"] == "request ok"
    assert payload["request_id"] == "req-1"
    assert payload["duration_ms"] == 12.3


def test_structured_json_formatter_uses_context_request_id_when_extra_absent():
    RequestIdContextVar.clear()
    RequestIdContextVar.set("ctx-req-77")
    record = logging.LogRecord(
        name="api.ctx",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="context req id",
        args=(),
        exc_info=None,
    )
    out = StructuredJsonFormatter().format(record)
    payload = json.loads(out)

    assert payload["request_id"] == "ctx-req-77"
    assert payload["trace_id"] == "ctx-req-77"
    RequestIdContextVar.clear()


def test_structured_json_formatter_falls_back_to_correlation_id_context():
    RequestIdContextVar.clear()
    token = correlation_id_var.set("corr-abc-42")
    try:
        record = logging.LogRecord(
            name="api.corr",
            level=logging.INFO,
            pathname=__file__,
            lineno=11,
            msg="correlation id",
            args=(),
            exc_info=None,
        )
        out = StructuredJsonFormatter().format(record)
        payload = json.loads(out)

        assert payload["request_id"] == "corr-abc-42"
        assert payload["trace_id"] == "corr-abc-42"
    finally:
        correlation_id_var.reset(token)
        RequestIdContextVar.clear()


def test_request_id_context_var_set_get_clear():
    RequestIdContextVar.clear()
    assert RequestIdContextVar.get() is None
    RequestIdContextVar.set("rid-123")
    assert RequestIdContextVar.get() == "rid-123"
    RequestIdContextVar.clear()
    assert RequestIdContextVar.get() is None


def test_setup_logging_respects_named_logger_without_reconfiguring_root():
    root_logger = logging.getLogger()
    root_handlers = list(root_logger.handlers)
    root_filters = list(root_logger.filters)
    root_level = root_logger.level
    logger_name = "x0tta6bl4.test.named_logger_contract"

    try:
        logger = setup_logging(name=logger_name, log_level="WARNING")

        assert logger is logging.getLogger(logger_name)
        assert logger is not root_logger
        assert logger.name == logger_name
        assert logger.level == logging.WARNING
        assert tuple(root_logger.handlers) == tuple(root_handlers)
        assert tuple(root_logger.filters) == tuple(root_filters)
        assert root_logger.level == root_level
    finally:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        logger.filters.clear()
        root_logger.handlers = root_handlers
        root_logger.filters = root_filters
        root_logger.setLevel(root_level)
