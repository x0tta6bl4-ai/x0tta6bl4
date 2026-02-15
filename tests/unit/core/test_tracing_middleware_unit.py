"""Unit tests for tracing middleware."""

from types import SimpleNamespace

import pytest
from starlette.responses import Response

import src.core.tracing_middleware as tracing_middleware
from src.core.tracing_middleware import TracingMiddleware, get_correlation_id


def test_get_correlation_id_defaults_none():
    value = get_correlation_id()
    assert value is None or isinstance(value, str)


@pytest.mark.asyncio
async def test_tracing_middleware_adds_headers():
    monkeypatch = pytest.MonkeyPatch()
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
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_tracing_middleware_preserves_incoming_correlation_id():
    monkeypatch = pytest.MonkeyPatch()
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
    monkeypatch.undo()
