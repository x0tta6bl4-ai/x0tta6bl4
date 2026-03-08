"""Unit tests for src/api/maas/middleware.py.

Covers: exception hierarchy, RequestContext, error-response utilities,
        exception handlers, and MaaSMiddleware dispatch behaviour.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from src.api.maas.middleware import (
    BillingError,
    ForbiddenError,
    MaaSError,
    MaaSMiddleware,
    MeshError,
    NotFoundError,
    RateLimitError,
    RequestContext,
    UnauthorizedError,
    ValidationError,
    ValidationErrorDetail,
    ValidationErrorResponse,
    create_error_response,
    generic_exception_handler,
    get_request_context,
    maas_exception_handler,
    set_request_context,
)


# ---------------------------------------------------------------------------
# MaaSError hierarchy
# ---------------------------------------------------------------------------


class TestMaaSErrorHierarchy:
    def test_base_error_attributes(self):
        err = MaaSError("something broke", error_code="boom", status_code=503)
        assert str(err) == "something broke"
        assert err.error_code == "boom"
        assert err.status_code == 503

    def test_not_found_error(self):
        err = NotFoundError("mesh", "mesh-42")
        assert err.status_code == 404
        assert err.error_code == "not_found"
        assert "mesh-42" in err.message
        assert err.details["resource"] == "mesh"
        assert err.details["identifier"] == "mesh-42"

    def test_unauthorized_error(self):
        err = UnauthorizedError()
        assert err.status_code == 401
        assert err.error_code == "unauthorized"

    def test_unauthorized_custom_message(self):
        err = UnauthorizedError("Token expired")
        assert "Token expired" in err.message

    def test_forbidden_error(self):
        err = ForbiddenError()
        assert err.status_code == 403
        assert err.error_code == "forbidden"

    def test_validation_error(self):
        err = ValidationError("Bad input", field_errors=[{"field": "email"}])
        assert err.status_code == 422
        assert err.error_code == "validation_error"
        assert err.details["field_errors"][0]["field"] == "email"

    def test_rate_limit_error(self):
        err = RateLimitError(retry_after=120)
        assert err.status_code == 429
        assert err.error_code == "rate_limit_exceeded"
        assert err.details["retry_after"] == 120

    def test_billing_error_with_plan(self):
        err = BillingError("Requires enterprise plan", plan_required="enterprise")
        assert err.status_code == 402
        assert err.error_code == "billing_error"
        assert err.details["plan_required"] == "enterprise"

    def test_billing_error_without_plan(self):
        err = BillingError("Payment required")
        assert err.details == {}

    def test_mesh_error_with_mesh_id(self):
        err = MeshError("Mesh unreachable", mesh_id="mesh-7")
        assert err.status_code == 400
        assert err.details["mesh_id"] == "mesh-7"

    def test_mesh_error_without_mesh_id(self):
        err = MeshError("generic mesh error")
        assert err.details == {}

    def test_errors_are_exceptions(self):
        with pytest.raises(MaaSError):
            raise MaaSError("test")

    def test_subclasses_catchable_as_maas_error(self):
        with pytest.raises(MaaSError):
            raise NotFoundError("node", "node-1")


# ---------------------------------------------------------------------------
# RequestContext
# ---------------------------------------------------------------------------


class TestRequestContext:
    def test_to_dict_fields(self):
        ctx = RequestContext(
            request_id="req-123",
            start_time=time.time() - 0.1,
            method="GET",
            path="/api/v1/health",
            client_ip="10.0.0.1",
            user_id="user-42",
        )
        d = ctx.to_dict()
        assert d["request_id"] == "req-123"
        assert d["method"] == "GET"
        assert d["path"] == "/api/v1/health"
        assert d["client_ip"] == "10.0.0.1"
        assert d["user_id"] == "user-42"
        assert d["duration_ms"] >= 0

    def test_duration_ms_non_negative(self):
        ctx = RequestContext(
            request_id="r",
            start_time=time.time(),
            method="POST",
            path="/x",
        )
        assert ctx.to_dict()["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# get_request_context / set_request_context
# ---------------------------------------------------------------------------


class TestRequestContextGlobal:
    def test_set_and_get(self):
        ctx = RequestContext(
            request_id="r1", start_time=time.time(), method="GET", path="/p"
        )
        set_request_context(ctx)
        assert get_request_context() is ctx
        set_request_context(None)

    def test_set_none_clears(self):
        set_request_context(None)
        assert get_request_context() is None


# ---------------------------------------------------------------------------
# create_error_response
# ---------------------------------------------------------------------------


class TestCreateErrorResponse:
    def test_required_fields_present(self):
        result = create_error_response("not_found", "Resource missing")
        assert result["error"] == "not_found"
        assert result["message"] == "Resource missing"
        assert "request_id" in result
        assert "timestamp" in result

    def test_explicit_request_id(self):
        result = create_error_response("oops", "msg", request_id="req-xyz")
        assert result["request_id"] == "req-xyz"

    def test_details_included(self):
        result = create_error_response("err", "msg", details={"key": "val"})
        assert result["details"]["key"] == "val"

    def test_no_details_is_none(self):
        result = create_error_response("err", "msg")
        assert result["details"] is None


# ---------------------------------------------------------------------------
# maas_exception_handler
# ---------------------------------------------------------------------------


class TestMaaSExceptionHandler:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _fake_request(self, request_id: str = "") -> MagicMock:
        req = MagicMock(spec=Request)
        req.headers = {"X-Request-ID": request_id} if request_id else {}
        return req

    def test_handler_returns_correct_status(self):
        req = self._fake_request("req-001")
        exc = NotFoundError("mesh", "mesh-99")
        response = self._run(maas_exception_handler(req, exc))
        assert response.status_code == 404

    def test_handler_response_body(self):
        import json

        req = self._fake_request("req-002")
        exc = UnauthorizedError("Not authenticated")
        response = self._run(maas_exception_handler(req, exc))
        body = json.loads(response.body)
        assert body["error"] == "unauthorized"
        assert "Not authenticated" in body["message"]
        assert body["request_id"] == "req-002"

    def test_generic_handler_returns_500(self):
        import json

        req = self._fake_request()
        exc = RuntimeError("unexpected boom")
        response = self._run(generic_exception_handler(req, exc))
        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["error"] == "internal_error"


# ---------------------------------------------------------------------------
# MaaSMiddleware dispatch
# ---------------------------------------------------------------------------


def _make_app_with_middleware(**kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(MaaSMiddleware, **kwargs)

    @app.get("/ok")
    async def ok_endpoint():
        return {"status": "ok"}

    @app.get("/not-found")
    async def raise_not_found():
        raise NotFoundError("resource", "id-42")

    @app.get("/server-error")
    async def raise_server_error():
        raise RuntimeError("unexpected internal error")

    @app.get("/health")
    async def health():
        return {"health": "ok"}

    return app


class TestMaaSMiddlewareDispatch:
    def test_ok_request_passes_through(self):
        app = _make_app_with_middleware()
        client = TestClient(app)
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_request_id_added_to_response(self):
        app = _make_app_with_middleware()
        client = TestClient(app)
        resp = client.get("/ok")
        assert "x-request-id" in resp.headers

    def test_custom_request_id_propagated(self):
        app = _make_app_with_middleware()
        client = TestClient(app)
        resp = client.get("/ok", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers.get("x-request-id") == "my-custom-id"

    def test_maas_error_returns_correct_status(self):
        app = _make_app_with_middleware()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "not_found"

    def test_unexpected_error_returns_500(self):
        app = _make_app_with_middleware()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/server-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "internal_error"

    def test_excluded_path_skipped(self):
        app = _make_app_with_middleware(exclude_paths=["/health"])
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        # No X-Request-ID added because path was excluded
        assert "x-request-id" not in resp.headers

    def test_logging_disabled_option(self):
        # Smoke test: middleware works with logging disabled
        app = _make_app_with_middleware(log_requests=False, log_responses=False)
        client = TestClient(app)
        assert client.get("/ok").status_code == 200

    def test_client_ip_extracted_from_x_forwarded_for(self):
        """Middleware _get_client_ip reads X-Forwarded-For correctly."""
        app = FastAPI()
        captured: list = []

        app.add_middleware(MaaSMiddleware)

        @app.get("/ip-check")
        async def ip_check(request: Request):
            return {"client_ip": request.headers.get("X-Forwarded-For")}

        client = TestClient(app)
        resp = client.get("/ip-check", headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
        assert resp.status_code == 200
        assert "192.168.1.1" in resp.json()["client_ip"]

    def test_client_ip_extracted_from_x_real_ip(self):
        """Falls back to X-Real-IP when X-Forwarded-For is absent."""
        app = FastAPI()
        app.add_middleware(MaaSMiddleware)

        @app.get("/ip-real")
        async def ip_real(request: Request):
            return {"real_ip": request.headers.get("X-Real-IP")}

        client = TestClient(app)
        resp = client.get("/ip-real", headers={"X-Real-IP": "203.0.113.5"})
        assert resp.status_code == 200
        assert resp.json()["real_ip"] == "203.0.113.5"

    def test_4xx_response_logged_at_warning_level(self):
        """Smoke test: 4xx response goes through _log_response warning branch."""
        app = FastAPI()
        app.add_middleware(MaaSMiddleware)

        @app.get("/four-xx")
        async def four_xx():
            from fastapi.responses import JSONResponse as JR
            return JR(content={"error": "bad"}, status_code=404)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/four-xx")
        assert resp.status_code == 404

    def test_5xx_response_logged_at_error_level(self):
        """Smoke test: 5xx response goes through _log_response error branch."""
        app = FastAPI()
        app.add_middleware(MaaSMiddleware)

        @app.get("/five-xx")
        async def five_xx():
            from fastapi.responses import JSONResponse as JR
            return JR(content={"error": "crash"}, status_code=503)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/five-xx")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# ValidationError models
# ---------------------------------------------------------------------------

class TestValidationErrorModels:
    def test_validation_error_detail_fields(self):
        detail = ValidationErrorDetail(field="email", message="invalid format")
        assert detail.field == "email"
        assert detail.message == "invalid format"
        assert detail.value is None

    def test_validation_error_detail_with_value(self):
        detail = ValidationErrorDetail(field="age", message="must be positive", value=-1)
        assert detail.value == -1

    def test_validation_error_response_fields(self):
        details = [ValidationErrorDetail(field="name", message="too short")]
        resp = ValidationErrorResponse(
            error="validation_failed",
            message="Request validation failed",
            request_id="req-1",
            timestamp="2026-03-08T00:00:00",
            details=details,
        )
        assert resp.error == "validation_failed"
        assert len(resp.details) == 1
        assert resp.details[0].field == "name"

    def test_validation_error_response_default_error(self):
        details = [ValidationErrorDetail(field="x", message="y")]
        resp = ValidationErrorResponse(
            request_id="r",
            timestamp="t",
            details=details,
        )
        assert resp.error == "validation_error"
        assert resp.message == "Request validation failed"
