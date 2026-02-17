"""Unit tests for tracing middleware."""

import builtins
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.responses import Response

import src.core.tracing_middleware as tracing_middleware
from src.core.tracing_middleware import (DatabaseTracingMiddleware,
                                         ExternalAPITracingMiddleware,
                                         TracingMiddleware,
                                         correlation_id_var,
                                         get_correlation_id)


class _FakeStatusCode:
    OK = "ok"
    ERROR = "error"


class _FakeStatus:
    def __init__(self, code, description=None):
        self.code = code
        self.description = description


class _FakeSpan:
    def __init__(self, name="", kind=None, context=None):
        self.name = name
        self.kind = kind
        self.context = context
        self.attributes = {}
        self.status = None
        self.recorded_exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.recorded_exception = exc


class _FakeTracer:
    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name, context=None, kind=None):
        span = _FakeSpan(name=name, kind=kind, context=context)
        self.spans.append(span)
        return span

    def start_span(self, name, kind=None):
        span = _FakeSpan(name=name, kind=kind, context=None)
        self.spans.append(span)
        return span


class _FakePropagator:
    def __init__(self):
        self.extracted = None
        self.injected = []

    def extract(self, carrier):
        self.extracted = carrier
        return {"trace": "ctx"}

    def inject(self, carrier):
        carrier["traceparent"] = "00-abc-xyz-01"
        self.injected.append(dict(carrier))


def _install_fake_otel(monkeypatch):
    tracer = _FakeTracer()
    propagator = _FakePropagator()
    fake_trace = SimpleNamespace(
        get_tracer=lambda _name: tracer,
        SpanKind=SimpleNamespace(SERVER="server", CLIENT="client"),
    )
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", True)
    monkeypatch.setattr(tracing_middleware, "trace", fake_trace)
    monkeypatch.setattr(tracing_middleware, "Status", _FakeStatus)
    monkeypatch.setattr(tracing_middleware, "StatusCode", _FakeStatusCode)
    monkeypatch.setattr(
        tracing_middleware, "TraceContextTextMapPropagator", lambda: propagator
    )
    return tracer, propagator


class _ReqURL:
    def __init__(self, path="/api/test"):
        self.path = path
        self.hostname = "example.local"
        self.scheme = "https"

    def __str__(self):
        return f"https://example.local{self.path}"


def test_get_correlation_id_defaults_none():
    value = get_correlation_id()
    assert value is None or isinstance(value, str)


@pytest.mark.asyncio
async def test_tracing_middleware_adds_headers(monkeypatch):
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", False)
    middleware = TracingMiddleware(app=SimpleNamespace(), service_name="unit-test")
    request = SimpleNamespace(
        url=SimpleNamespace(path="/ping"),
        headers={},
        method="GET",
    )

    async def call_next(_):
        return Response(content="ok", status_code=200)

    res = await middleware.dispatch(request, call_next)
    assert res.status_code == 200
    assert "X-Correlation-ID" in res.headers
    assert "X-Request-Duration" in res.headers


@pytest.mark.asyncio
async def test_tracing_middleware_preserves_incoming_correlation_id(monkeypatch):
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", False)
    middleware = TracingMiddleware(app=SimpleNamespace(), service_name="unit-test")
    request = SimpleNamespace(
        url=SimpleNamespace(path="/ping"),
        headers={"X-Correlation-ID": "corr-123"},
        method="GET",
    )

    async def call_next(_):
        return Response(content="ok", status_code=200)

    res = await middleware.dispatch(request, call_next)
    assert res.status_code == 200
    assert res.headers["X-Correlation-ID"] == "corr-123"


@pytest.mark.asyncio
async def test_tracing_middleware_skips_excluded_paths(monkeypatch):
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", False)
    middleware = TracingMiddleware(
        app=SimpleNamespace(), service_name="unit-test", excluded_paths=["/health"]
    )
    request = SimpleNamespace(
        url=SimpleNamespace(path="/health/live"),
        headers={},
        method="GET",
    )
    call_next = AsyncMock(return_value=Response(status_code=200))

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_tracing_middleware_otel_success_sets_span_and_headers(monkeypatch):
    tracer, propagator = _install_fake_otel(monkeypatch)
    middleware = TracingMiddleware(app=SimpleNamespace(), service_name="unit-test")
    request = SimpleNamespace(
        url=_ReqURL("/orders"),
        headers={"User-Agent": "pytest-agent"},
        method="GET",
        client=SimpleNamespace(host="10.0.0.9"),
        query_params={"limit": "10"},
    )

    async def call_next(_request):
        response = Response(status_code=200)
        response.headers["content-type"] = "application/json"
        return response

    response = await middleware.dispatch(request, call_next)
    span = tracer.spans[-1]

    assert span.name == "GET /orders"
    assert span.attributes["http.method"] == "GET"
    assert span.attributes["http.path"] == "/orders"
    assert span.attributes["http.client_ip"] == "10.0.0.9"
    assert span.attributes["http.query_params_count"] == 1
    assert span.status.code == _FakeStatusCode.OK
    assert response.headers["X-Correlation-ID"]
    assert response.headers["X-Request-Duration"].endswith("s")
    assert response.headers["X-Trace-ID"] == "00-abc-xyz-01"
    assert propagator.extracted == {"User-Agent": "pytest-agent"}


@pytest.mark.asyncio
async def test_tracing_middleware_otel_sets_error_status_for_4xx_and_5xx(monkeypatch):
    tracer, _ = _install_fake_otel(monkeypatch)
    middleware = TracingMiddleware(app=SimpleNamespace(), service_name="unit-test")
    request = SimpleNamespace(
        url=_ReqURL("/errors"),
        headers={},
        method="POST",
        client=None,
        query_params={},
    )

    async def call_next_404(_request):
        return Response(status_code=404)

    async def call_next_500(_request):
        return Response(status_code=503)

    await middleware.dispatch(request, call_next_404)
    span_404 = tracer.spans[-1]
    assert span_404.status.code == _FakeStatusCode.ERROR
    assert "Client error 404" in span_404.status.description

    await middleware.dispatch(request, call_next_500)
    span_500 = tracer.spans[-1]
    assert span_500.status.code == _FakeStatusCode.ERROR
    assert "HTTP 503" in span_500.status.description


@pytest.mark.asyncio
async def test_tracing_middleware_otel_records_exception(monkeypatch):
    tracer, _ = _install_fake_otel(monkeypatch)
    middleware = TracingMiddleware(app=SimpleNamespace(), service_name="unit-test")
    request = SimpleNamespace(
        url=_ReqURL("/boom"),
        headers={},
        method="GET",
        client=None,
        query_params={},
    )

    async def call_next(_request):
        raise RuntimeError("handler exploded")

    with pytest.raises(RuntimeError, match="handler exploded"):
        await middleware.dispatch(request, call_next)

    span = tracer.spans[-1]
    assert isinstance(span.recorded_exception, RuntimeError)
    assert span.attributes["error.type"] == "RuntimeError"
    assert span.attributes["error.message"] == "handler exploded"
    assert span.status.code == _FakeStatusCode.ERROR


def test_database_tracing_middleware_noop_when_otel_disabled(monkeypatch):
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", False)
    middleware = DatabaseTracingMiddleware()
    cm = middleware.trace_query("select", "users")
    with cm as token:
        assert token is None


def test_database_tracing_middleware_creates_span_when_otel_enabled(monkeypatch):
    tracer, _ = _install_fake_otel(monkeypatch)
    correlation_id_var.set("corr-db")
    middleware = DatabaseTracingMiddleware()

    span = middleware.trace_query("select", "users")

    assert span.name == "db.select"
    assert span.attributes["db.system"] == "postgresql"
    assert span.attributes["db.operation"] == "select"
    assert span.attributes["db.table"] == "users"
    assert span.attributes["correlation_id"] == "corr-db"
    assert tracer.spans[-1] is span


def test_external_api_tracing_noop_and_inject_headers(monkeypatch):
    monkeypatch.setattr(tracing_middleware, "OTEL_AVAILABLE", False)
    middleware = ExternalAPITracingMiddleware()
    cm = middleware.trace_call("stripe", "charge")
    with cm as token:
        assert token is None

    headers = {"Authorization": "Bearer x"}
    assert middleware.inject_headers(headers) is headers


def test_external_api_tracing_creates_span_and_injects_headers(monkeypatch):
    tracer, propagator = _install_fake_otel(monkeypatch)
    correlation_id_var.set("corr-api")
    middleware = ExternalAPITracingMiddleware()

    span = middleware.trace_call(
        service="stripe", operation="create_checkout", url="https://stripe.test"
    )
    assert span.name == "external.stripe.create_checkout"
    assert span.attributes["external.service"] == "stripe"
    assert span.attributes["external.operation"] == "create_checkout"
    assert span.attributes["external.url"] == "https://stripe.test"
    assert span.attributes["correlation_id"] == "corr-api"
    assert tracer.spans[-1] is span

    headers = {}
    result = middleware.inject_headers(headers)
    assert result is headers
    assert result["traceparent"] == "00-abc-xyz-01"
    assert propagator.injected


def test_import_fallback_when_opentelemetry_missing(monkeypatch):
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("otel missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    reloaded = importlib.reload(tracing_middleware)
    assert reloaded.OTEL_AVAILABLE is False

    monkeypatch.setattr(builtins, "__import__", original_import)
    importlib.reload(tracing_middleware)
