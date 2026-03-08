"""Unit tests for degraded dependency header propagation in app middleware."""

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
os.environ.setdefault("MAAS_LIGHT_MODE", "true")

from src.core.app import app
from src.core.reliability_policy import mark_degraded_dependency


def _ensure_test_route() -> None:
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    if "/__test__/degraded-header" in route_paths:
        return

    @app.get("/__test__/degraded-header", include_in_schema=False)
    async def _degraded_header_probe(request: Request):
        mark_degraded_dependency(request, "redis")
        mark_degraded_dependency(request, "database")
        return JSONResponse({"ok": True})


def _client():
    _ensure_test_route()
    return TestClient(app)


def test_degraded_dependencies_header_is_propagated():
    with _client() as client:
        response = client.get("/__test__/degraded-header")

        assert response.status_code == 200
        assert response.headers["X-Degraded-Dependencies"] == "database,redis"
        assert response.headers["X-Request-ID"]
