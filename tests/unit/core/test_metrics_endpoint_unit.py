"""Unit tests for /metrics endpoint in src/core/app.py."""

import os
import re
import hashlib

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


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_text(client):
    resp = await client.get("/metrics")

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "text/plain" in content_type
    assert "version=0.0.4" in content_type

    body = resp.text.strip()
    assert body
    assert "# HELP" in body or "# TYPE" in body


@pytest.mark.asyncio
async def test_metrics_endpoint_includes_health_request_series(client):
    # Generate one normal request that must be observed by MetricsMiddleware.
    health_resp = await client.get("/health")
    assert health_resp.status_code == 200

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200

    body = metrics_resp.text
    assert "x0tta6bl4_requests_total" in body

    pattern = (
        r'x0tta6bl4_requests_total\{'
        r'(?=[^}]*method="GET")'
        r'(?=[^}]*endpoint="/health")'
        r'(?=[^}]*status="200")'
        r'(?=[^}]*api_key="anonymous")'
        r'[^}]*\}\s+[0-9.]+'
    )
    assert re.search(pattern, body), "Missing /health request time-series in metrics"


@pytest.mark.asyncio
async def test_metrics_endpoint_redacts_raw_api_key_from_labels(client):
    raw_key = "very-secret-client-key-123"
    expected_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]

    health_resp = await client.get("/health", headers={"X-API-Key": raw_key})
    assert health_resp.status_code == 200

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.text

    assert raw_key not in body
    assert f'api_key="api_key_{expected_hash}"' in body
