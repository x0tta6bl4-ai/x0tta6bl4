"""Gateway security header regression tests for src/core/app.py."""

import os

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("MAAS_LIGHT_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("TESTING", "true")

try:
    from src.core.app import app
except ImportError as exc:
    pytest.skip(f"app.py not importable: {exc}", allow_module_level=True)


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as tc:
        yield tc


def _assert_security_headers(headers: httpx.Headers) -> None:
    assert headers.get("Content-Security-Policy") == (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self';"
    )
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert (
        headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains; preload"
    )
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
    assert headers.get("Server") == "x0tta6bl4-gateway"


@pytest.mark.asyncio
async def test_security_headers_present_on_success_response(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    _assert_security_headers(resp.headers)


@pytest.mark.asyncio
async def test_security_headers_present_on_error_response(client):
    resp = await client.get("/api/v1/non-existent")
    assert resp.status_code == 404
    _assert_security_headers(resp.headers)


@pytest.mark.asyncio
async def test_metrics_endpoint_keeps_gateway_security_headers(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    _assert_security_headers(resp.headers)
