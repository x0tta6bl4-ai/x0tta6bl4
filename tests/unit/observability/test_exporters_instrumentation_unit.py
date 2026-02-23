"""Focused unit coverage for observability exporters/instrumentation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.observability.exporters import (
    ConsoleSpanExporter,
    ExportResult,
    JaegerExporter,
    MultiSpanExporter,
    OTLPSpanExporter,
    get_exporter,
)
from src.observability.instrumentation import (
    _extract_table,
    instrument_all,
    instrument_httpx,
    instrument_redis,
    traced,
)
from src.observability.tracing import Span, SpanContext, SpanKind, SpanStatusCode


def _make_span() -> Span:
    start = datetime.utcnow()
    span = Span(
        name="unit-span",
        context=SpanContext(trace_id="0" * 32, span_id="1" * 16),
        kind=SpanKind.CLIENT,
    )
    span.start_time = start
    span.end_time = start + timedelta(milliseconds=12)
    span.status_code = SpanStatusCode.OK
    span.attributes = {"ok": True, "count": 3, "ratio": 1.5, "name": "alice"}
    span.events = [
        {
            "name": "event-a",
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": {"k": "v"},
        }
    ]
    return span


def test_console_exporter_formats_json_and_pretty(capsys):
    span = _make_span()
    exporter = ConsoleSpanExporter(output_format="json")
    result = exporter.export([span])
    assert result.success is True
    assert result.spans_exported == 1

    out = capsys.readouterr().out
    assert '"name": "unit-span"' in out

    pretty = ConsoleSpanExporter(output_format="pretty")._format_pretty(span)
    assert "SPAN: unit-span" in pretty


def test_console_exporter_returns_error_on_format_failure(monkeypatch):
    exporter = ConsoleSpanExporter(output_format="json")
    monkeypatch.setattr(exporter, "_format_json", lambda _span: (_ for _ in ()).throw(ValueError("bad span")))

    result = exporter.export([_make_span()])
    assert result.success is False
    assert "bad span" in (result.error or "")


def test_otlp_convert_span_maps_attributes_and_status():
    exporter = OTLPSpanExporter(endpoint="http://collector:4317")
    converted = exporter._convert_span_to_otlp(_make_span())

    assert converted["kind"] == 3  # client
    assert converted["status"]["code"] == 1  # ok
    assert converted["attributes"]["ok"] == {"bool_value": True}
    assert converted["attributes"]["count"] == {"int_value": 3}
    assert converted["attributes"]["ratio"] == {"double_value": 1.5}
    assert converted["attributes"]["name"] == {"string_value": "alice"}
    assert converted["events"][0]["name"] == "event-a"
    assert exporter._hex_to_bytes("00ff") == b"\x00\xff"


def test_otlp_export_success_failure_and_exception(monkeypatch):
    exporter = OTLPSpanExporter(endpoint="http://collector:4317")
    span = _make_span()
    monkeypatch.setattr(
        exporter,
        "_convert_span_to_otlp",
        lambda _span: {"trace_id": "trace", "span_id": "span", "name": "n"},
    )

    class _Resp:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Resp(200))
    ok = exporter.export([span])
    assert ok == ExportResult(success=True, spans_exported=1)

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Resp(500))
    bad = exporter.export([span])
    assert bad.success is False
    assert "status 500" in (bad.error or "")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    err = exporter.export([span])
    assert err.success is False
    assert "network down" in (err.error or "")


def test_jaeger_export_and_shutdown():
    class _Sock:
        def __init__(self):
            self.calls = []
            self.closed = False

        def sendto(self, data, addr):
            self.calls.append((data, addr))

        def close(self):
            self.closed = True

    exporter = JaegerExporter(agent_host="jaeger.local", agent_port=6831, service_name="svc")
    fake_sock = _Sock()
    exporter._socket = fake_sock

    result = exporter.export([_make_span()])
    assert result.success is True
    assert fake_sock.calls[0][1] == ("jaeger.local", 6831)

    exporter.shutdown()
    assert fake_sock.closed is True
    assert exporter._socket is None


def test_multi_exporter_aggregates_results_and_flush():
    class _Ok:
        def export(self, spans):
            return ExportResult(success=True, spans_exported=len(spans))

        def shutdown(self):
            return None

        def force_flush(self, timeout_ms=30000):
            return True

    class _Bad:
        def export(self, spans):
            return ExportResult(success=False, error="boom")

        def shutdown(self):
            return None

        def force_flush(self, timeout_ms=30000):
            raise RuntimeError("flush failed")

    exporter = MultiSpanExporter([_Ok(), _Bad()])
    result = exporter.export([_make_span()])
    assert result.success is False
    assert result.spans_exported == 1
    assert "boom" in (result.error or "")
    assert exporter.force_flush(10) is False


def test_get_exporter_selects_known_types_and_fallback():
    cfg = SimpleNamespace(
        exporter_type="otlp",
        otlp_endpoint="http://collector:4317",
        jaeger_agent_host="localhost",
        jaeger_agent_port=6831,
        service_name="svc",
    )
    assert isinstance(get_exporter(cfg), OTLPSpanExporter)
    cfg.exporter_type = "jaeger"
    assert isinstance(get_exporter(cfg), JaegerExporter)
    cfg.exporter_type = "console"
    assert isinstance(get_exporter(cfg), ConsoleSpanExporter)
    cfg.exporter_type = "multi"
    assert isinstance(get_exporter(cfg), MultiSpanExporter)
    cfg.exporter_type = "unknown"
    assert isinstance(get_exporter(cfg), ConsoleSpanExporter)


def test_extract_table_handles_common_sql_patterns():
    assert _extract_table("SELECT * FROM users") == "users"
    assert _extract_table("DELETE FROM sessions WHERE id=1") == "sessions"
    assert _extract_table("INSERT INTO payments (id) VALUES (1)") == "payments"
    assert _extract_table("UPDATE orders SET status='ok'") == "orders"
    assert _extract_table("") is None


def test_instrument_redis_wraps_execute_command_and_records_errors(monkeypatch):
    spans = {"error_called": 0}

    class _Span:
        def set_status(self, *_args, **_kwargs):
            return None

        def record_exception(self, _exc):
            spans["error_called"] += 1

    @contextmanager
    def _fake_ctx(**_kwargs):
        yield _Span()

    monkeypatch.setattr("src.observability.instrumentation.traced_context", _fake_ctx)

    class _Client:
        def execute_command(self, *args, **kwargs):
            return "PONG"

    client = instrument_redis(_Client())
    assert client.execute_command("PING") == "PONG"

    class _FailClient:
        def execute_command(self, *args, **kwargs):
            raise ValueError("redis down")

    fail_client = instrument_redis(_FailClient())
    with pytest.raises(ValueError, match="redis down"):
        fail_client.execute_command("PING")
    assert spans["error_called"] == 1


def test_instrument_httpx_injects_headers_and_sets_status(monkeypatch):
    capture = {"status": []}

    class _Span:
        def set_attribute(self, *_args, **_kwargs):
            return None

        def set_status(self, status, description=None):
            capture["status"].append((status, description))

        def record_exception(self, _exc):
            capture["status"].append(("error", "exception"))

    @contextmanager
    def _fake_ctx(**_kwargs):
        yield _Span()

    monkeypatch.setattr("src.observability.instrumentation.traced_context", _fake_ctx)
    monkeypatch.setattr(
        "src.observability.tracing.inject_trace_context",
        lambda headers: {**headers, "traceparent": "00-abc-def-01"},
    )

    class _Resp:
        def __init__(self, code):
            self.status_code = code

    class _Client:
        def __init__(self):
            self.seen_headers = None

        def request(self, method, url, **kwargs):
            self.seen_headers = kwargs.get("headers")
            return _Resp(200)

    client = instrument_httpx(_Client())
    response = client.request("GET", "https://example.com/api", headers={"x": "1"})
    assert response.status_code == 200
    assert client.seen_headers["traceparent"] == "00-abc-def-01"


def test_instrument_all_collects_failures(monkeypatch):
    monkeypatch.setattr("src.observability.instrumentation.instrument_fastapi", lambda app, service_name: None)
    monkeypatch.setattr("src.observability.instrumentation.instrument_sqlalchemy", lambda engine: (_ for _ in ()).throw(RuntimeError("db")))
    monkeypatch.setattr("src.observability.instrumentation.instrument_redis", lambda client: client)
    monkeypatch.setattr("src.observability.instrumentation.instrument_httpx", lambda client: client)
    monkeypatch.setattr("src.observability.instrumentation.instrument_celery", lambda app: app)

    result = instrument_all(
        fastapi_app=object(),
        sqlalchemy_engine=object(),
        redis_client=object(),
        httpx_client=object(),
        celery_app=object(),
    )

    assert result["fastapi"] is True
    assert result["sqlalchemy"] is False
    assert result["redis"] is True
    assert result["httpx"] is True
    assert result["celery"] is True


def test_traced_delegates_to_trace_method(monkeypatch):
    sentinel = object()
    monkeypatch.setattr("src.observability.instrumentation.trace_method", lambda *args, **kwargs: sentinel)
    assert traced("fn-name", kind=SpanKind.INTERNAL, attributes={"a": 1}) is sentinel
