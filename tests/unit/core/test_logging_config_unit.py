"""Unit tests for core logging configuration helpers."""

import json
import logging

from src.core.tracing_middleware import correlation_id_var
from src.core.logging_config import (RequestIdContextVar, SensitiveDataFilter,
                                     StructuredJsonFormatter,
                                     mask_sensitive_data)


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
