"""Unit tests for API error handlers middleware context behavior."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.core.api_error_handlers import register_api_error_handlers
from src.core.logging_config import RequestIdContextVar


def _build_app() -> FastAPI:
    app = FastAPI()
    register_api_error_handlers(app)

    @app.get("/echo-trace")
    async def echo_trace(request: Request):
        return {
            "request_id_ctx": RequestIdContextVar.get(),
            "state_trace_id": getattr(request.state, "trace_id", None),
        }

    return app


def test_trace_context_uses_incoming_header_value():
    client = TestClient(_build_app())

    response = client.get("/echo-trace", headers={"X-Trace-ID": "trace-123"})
    payload = response.json()

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "trace-123"
    assert payload["request_id_ctx"] == "trace-123"
    assert payload["state_trace_id"] == "trace-123"


def test_trace_context_generates_value_when_header_missing():
    client = TestClient(_build_app())

    response = client.get("/echo-trace")
    payload = response.json()
    trace_id = response.headers.get("X-Trace-ID")

    assert response.status_code == 200
    assert trace_id
    assert payload["request_id_ctx"] == trace_id
    assert payload["state_trace_id"] == trace_id
