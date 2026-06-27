"""Contract tests for unified API error response shape."""

from __future__ import annotations

from fastapi import HTTPException, Query
from fastapi.testclient import TestClient

from src.core.app import app


client = TestClient(app)


def _assert_error_contract(payload: dict) -> None:
    assert payload["status"] == "error"
    assert "detail" in payload
    assert isinstance(payload.get("code"), str)
    assert isinstance(payload.get("trace_id"), str)
    assert payload["trace_id"]


def test_success_response_generates_trace_header():
    response = client.get("/health")
    assert response.status_code == 200
    trace_id = response.headers.get("X-Trace-ID")
    assert isinstance(trace_id, str)
    assert trace_id


def test_success_response_preserves_trace_header():
    trace_id = "contract-trace-success"
    response = client.get("/health", headers={"X-Trace-ID": trace_id})
    assert response.status_code == 200
    assert response.headers.get("X-Trace-ID") == trace_id


def test_http_404_error_contract_with_trace_passthrough():
    trace_id = "contract-trace-404"
    response = client.get("/definitely-missing-contract-path", headers={"X-Trace-ID": trace_id})
    assert response.status_code == 404
    data = response.json()
    _assert_error_contract(data)
    assert data["code"] == "HTTP_404"
    assert data["trace_id"] == trace_id
    assert response.headers.get("X-Trace-ID") == trace_id


def test_http_403_error_contract_for_protected_agent_endpoint(monkeypatch):
    trace_id = "contract-trace-403"
    monkeypatch.setenv("MAAS_AGENT_BOT_TOKEN", "expected-token")

    # Override auth so the request reaches the 403 bot-token check (not 401).
    from src.api.maas_auth import get_current_user_from_maas
    app.dependency_overrides[get_current_user_from_maas] = lambda: {"id": "u1", "role": "user"}
    try:
        response = client.post(
            "/api/v1/maas/agents/health/run",
            headers={"X-Trace-ID": trace_id},
            json={"auto_heal": True, "dry_run": False},
        )
    finally:
        app.dependency_overrides.pop(get_current_user_from_maas, None)

    assert response.status_code == 403
    data = response.json()
    _assert_error_contract(data)
    assert data["code"] == "HTTP_403"
    assert data["trace_id"] == trace_id
    assert response.headers.get("X-Trace-ID") == trace_id


def test_http_error_contract_respects_explicit_detail_code():
    coded_path = "/__contract__/http-coded"
    if not any(getattr(route, "path", None) == coded_path for route in app.routes):

        async def _coded():
            raise HTTPException(
                status_code=409,
                detail={"code": "CONTRACT_CONFLICT", "detail": "conflict"},
            )

        app.add_api_route(coded_path, _coded, methods=["GET"], include_in_schema=False)

    response = client.get(coded_path)
    assert response.status_code == 409
    data = response.json()
    _assert_error_contract(data)
    assert data["code"] == "CONTRACT_CONFLICT"
    assert isinstance(data["detail"], dict)


def test_validation_error_contract_on_missing_required_query_param():
    validation_path = "/__contract__/validation"
    if not any(getattr(route, "path", None) == validation_path for route in app.routes):
        async def _validation_endpoint(required_value: int = Query(...)):
            return {"required_value": required_value}

        app.add_api_route(
            validation_path,
            _validation_endpoint,
            methods=["GET"],
            include_in_schema=False,
        )

    response = client.get(validation_path)
    assert response.status_code == 422
    data = response.json()
    _assert_error_contract(data)
    assert data["code"] == "VALIDATION_ERROR"
    assert isinstance(data["detail"], list)


def test_unhandled_error_contract_returns_500():
    # SandboxSafeTestClient (patched in tests/conftest.py) defaults to
    # raise_server_exceptions=True, which re-raises app exceptions in tests.
    # For contract validation we need the HTTP 500 response payload.
    local_client = TestClient(app, raise_server_exceptions=False)

    boom_path = "/__contract__/boom"
    if not any(getattr(route, "path", None) == boom_path for route in app.routes):
        async def _boom():
            raise RuntimeError("contract-boom")

        app.add_api_route(boom_path, _boom, methods=["GET"], include_in_schema=False)

    response = local_client.get(boom_path)
    assert response.status_code == 500
    data = response.json()
    _assert_error_contract(data)
    assert data["code"] == "INTERNAL_ERROR"
    assert data["detail"] == "Internal server error"
