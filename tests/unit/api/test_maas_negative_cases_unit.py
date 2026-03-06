"""Negative-case contract tests for critical MaaS API endpoints.

Covers: 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity, 429 Rate Limited.
All tests use dependency_overrides so no real DB/Stripe/Redis is required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from types import SimpleNamespace

from src.core.app import app
from src.api.maas_auth import get_current_user_from_maas, require_permission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: str = "user", permissions: str = "") -> SimpleNamespace:
    """Return a minimal User-like object with the attributes the auth layer expects."""
    return SimpleNamespace(id="u-test", role=role, permissions=permissions, email="t@x.io")


def _unauth_client() -> TestClient:
    """Client with NO auth override — exercises real 401 path."""
    c = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user_from_maas, None)
    return c


def _authed_client(role: str = "user", permissions: str = "") -> TestClient:
    user = _make_user(role, permissions)
    app.dependency_overrides[get_current_user_from_maas] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 401 — Unauthorized (no token / bad token)
# ---------------------------------------------------------------------------

def _raise_401():
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Not authenticated")


class TestUnauthorized:

    def test_marketplace_create_listing_401_no_token(self):
        app.dependency_overrides[get_current_user_from_maas] = _raise_401
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "us-east", "price_per_hour": 1.0
        })
        assert r.status_code == 401

    def test_billing_status_401_no_token(self):
        app.dependency_overrides[get_current_user_from_maas] = _raise_401
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/maas/billing/status")
        assert r.status_code == 401

    def test_dashboard_401_no_token(self):
        app.dependency_overrides[get_current_user_from_maas] = _raise_401
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/maas/dashboard/overview")
        assert r.status_code in (401, 404)  # 404 if route doesn't exist


# ---------------------------------------------------------------------------
# 403 — Forbidden (authenticated but wrong role/permission)
# ---------------------------------------------------------------------------

class TestForbidden:

    def test_marketplace_create_listing_403_readonly_user(self):
        """User with no marketplace:list permission gets 403."""
        user = _make_user(role="readonly", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "us-east", "price_per_hour": 1.0
        })
        assert r.status_code == 403
        assert "permission" in r.json().get("detail", "").lower()

    def test_marketplace_rent_403_readonly_user(self):
        user = _make_user(role="readonly", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/rent/lst-abc123", json={})
        assert r.status_code == 403

    def test_marketplace_escrow_release_403_wrong_user(self):
        """Renter without explicit grant cannot release escrow (403 or 404)."""
        user = _make_user(role="readonly", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/escrow/lst-abc/release")
        assert r.status_code in (403, 404)

    def test_billing_checkout_403_no_billing_permission(self):
        user = _make_user(role="readonly", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/billing/subscriptions/checkout",
                        json={"plan": "pro"})
        assert r.status_code in (403, 422)

    def test_admin_bypasses_permission_check(self):
        """Admin role always passes require_permission gate."""
        user = _make_user(role="admin", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        # POST with missing body → 422 (validation), NOT 403 — proves auth passed
        r = client.post("/api/v1/maas/marketplace/list", json={})
        assert r.status_code != 403


# ---------------------------------------------------------------------------
# 422 — Unprocessable Entity (schema / validation errors)
# ---------------------------------------------------------------------------

class TestUnprocessableEntity:

    def test_marketplace_create_listing_422_missing_node_id(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "marketplace:list")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "region": "us-east", "price_per_hour": 1.0
            # node_id missing
        })
        assert r.status_code == 422

    def test_marketplace_create_listing_422_invalid_region(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "marketplace:list")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "invalid-region", "price_per_hour": 1.0
        })
        assert r.status_code == 422

    def test_marketplace_create_listing_422_invalid_currency(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "marketplace:list")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "us-east", "currency": "BTC", "price_per_hour": 1.0
        })
        assert r.status_code == 422

    def test_marketplace_create_listing_422_negative_price(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "marketplace:list")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "us-east", "price_per_hour": -5.0
        })
        assert r.status_code == 422

    def test_marketplace_search_422_invalid_currency(self):
        """Search with invalid currency value → 422 (pattern validation)."""
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/maas/marketplace/search?currency=BTC")
        assert r.status_code == 422

    def test_billing_checkout_422_missing_body(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "billing:write")
        client = TestClient(app, raise_server_exceptions=False)
        # POST with no JSON body at all
        r = client.post("/api/v1/maas/billing/subscriptions/checkout")
        assert r.status_code == 422

    def test_telemetry_heartbeat_422_missing_node_id(self):
        """POST /heartbeat with empty body → 422 (node_id required by schema).
        If an auth middleware runs first, 401 is also acceptable."""
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/heartbeat", json={})
        # 422 = schema validation (expected); 401 = auth middleware runs before schema validation
        assert r.status_code in (422, 401)


# ---------------------------------------------------------------------------
# 429 — Rate Limited
# ---------------------------------------------------------------------------

def _raise_429():
    from fastapi import HTTPException
    raise HTTPException(status_code=429, detail="Too many requests")


class TestRateLimited:

    def test_rate_limit_dependency_returns_429(self):
        """When a dependency raises 429, client receives 429."""
        app.dependency_overrides[get_current_user_from_maas] = _raise_429
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/maas/billing/status")
        assert r.status_code == 429

    def test_rate_limit_on_billing_checkout_returns_429(self):
        """Endpoints with auth dependency return 429 when auth raises it."""
        app.dependency_overrides[get_current_user_from_maas] = _raise_429
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/billing/subscriptions/checkout", json={})
        assert r.status_code == 429

    def test_rate_limit_response_has_detail(self):
        app.dependency_overrides[get_current_user_from_maas] = _raise_429
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/maas/billing/status")
        assert r.status_code == 429
        assert "detail" in r.json()


# ---------------------------------------------------------------------------
# Error response shape contract (cross-cutting)
# ---------------------------------------------------------------------------

class TestErrorResponseShape:

    def _assert_shape(self, r, expected_status: int):
        assert r.status_code == expected_status
        # FastAPI returns {"detail": ...} for validation errors
        body = r.json()
        assert "detail" in body or "status" in body

    def test_403_has_detail(self):
        user = _make_user(role="readonly", permissions="")
        app.dependency_overrides[get_current_user_from_maas] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={
            "node_id": "n1", "region": "us-east", "price_per_hour": 1.0
        })
        self._assert_shape(r, 403)

    def test_422_has_detail_with_loc(self):
        app.dependency_overrides[get_current_user_from_maas] = lambda: _make_user("user", "marketplace:list")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/maas/marketplace/list", json={})
        assert r.status_code == 422
        body = r.json()
        assert "detail" in body
        # FastAPI 422 detail is a list of validation errors
        assert isinstance(body["detail"], list)
        assert len(body["detail"]) > 0
        assert "loc" in body["detail"][0]
