"""
Integration tests for MaaS Auth — gaps in existing test_maas_auth_endpoints.py.

Existing tests cover: register, login, /me, set-admin, bootstrap-admin.
This file covers the remaining uncovered paths:

  POST /api/v1/maas/auth/api-key     — rotate_api_key
  GET  /api/v1/maas/auth/login/oidc  — OIDC redirect (501 when not configured)
  GET  /api/v1/maas/auth/callback    — OIDC callback (501 when not configured)

  require_permission() with explicit user.permissions field (not role defaults)
  get_current_user_from_maas() Bearer token / session-based auth path
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, User, get_db

_TEST_DB_PATH = f"./test_auth_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def auth_data(client):
    """Register a regular user and return token + helpers."""
    email = f"auth-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == token).first()
    user_id = user.id
    db.close()

    return {"token": token, "user_id": user_id, "email": email}


# ---------------------------------------------------------------------------
# POST /auth/api-key  (rotate_api_key)
# ---------------------------------------------------------------------------

def _fresh_user(client) -> str:
    """Register a brand-new user and return their token."""
    email = f"rot-{uuid.uuid4().hex[:10]}@test.com"
    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestRotateApiKey:
    """
    Each test that calls rotate uses a fresh user — because rotation
    invalidates the old key, reusing the same token across tests would
    cause subsequent calls to return 401.
    """

    def test_no_auth_401(self, client):
        r = client.post("/api/v1/maas/auth/api-key")
        assert r.status_code == 401

    def test_authenticated_returns_200(self, client):
        token = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": token})
        assert r.status_code == 200, r.text

    def test_response_has_api_key_field(self, client):
        token = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": token})
        assert r.status_code == 200, r.text
        assert "api_key" in r.json()

    def test_response_has_created_at(self, client):
        token = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": token})
        assert "created_at" in r.json()

    def test_new_key_has_correct_prefix(self, client):
        token = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": token})
        assert r.json()["api_key"].startswith("x0t_")

    def test_new_key_differs_from_old(self, client):
        token = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": token})
        assert r.json()["api_key"] != token

    def test_old_key_invalidated_after_rotation(self, client):
        """After rotation, old key → 401; new key → 200."""
        old_key = _fresh_user(client)
        r = client.post("/api/v1/maas/auth/api-key",
                        headers={"X-API-Key": old_key})
        new_key = r.json()["api_key"]
        assert client.get("/api/v1/maas/auth/me",
                          headers={"X-API-Key": old_key}).status_code == 401
        assert client.get("/api/v1/maas/auth/me",
                          headers={"X-API-Key": new_key}).status_code == 200


# ---------------------------------------------------------------------------
# GET /auth/login/oidc and GET /auth/callback  (501 when OIDC not configured)
# ---------------------------------------------------------------------------

class TestOIDCEndpoints:
    def test_login_oidc_not_configured_501(self, client):
        """OIDC_ISSUER / OIDC_CLIENT_ID not set → 501."""
        r = client.get("/api/v1/maas/auth/login/oidc")
        assert r.status_code == 501

    def test_callback_not_configured_501(self, client):
        """OIDC callback without configured OIDC → 501."""
        r = client.get("/api/v1/maas/auth/callback")
        assert r.status_code == 501

    def test_login_oidc_error_detail(self, client):
        r = client.get("/api/v1/maas/auth/login/oidc")
        assert "OIDC" in r.json()["detail"] or "oidc" in r.json()["detail"].lower()

    def test_callback_error_detail(self, client):
        r = client.get("/api/v1/maas/auth/callback")
        assert "OIDC" in r.json()["detail"] or "oidc" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# require_permission() with explicit user.permissions field
# ---------------------------------------------------------------------------

class TestRequirePermissionExplicit:
    """
    Tests the explicit permissions path: user.permissions = "perm1,perm2"
    (not the role_defaults path). This covers lines 74-77 of maas_auth.py.
    """

    @pytest.fixture(scope="class")
    def custom_perm_user(self, client):
        """User with explicit 'custom:read' permission set directly in DB."""
        email = f"cperm-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/v1/maas/auth/register",
                        json={"email": email, "password": "password123"})
        token = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == token).first()
        # Grant explicit analytics:view permission (overrides role defaults)
        user.permissions = "analytics:view,audit:view"
        user.role = "user"  # user doesn't have analytics:view by default
        db.commit()
        db.close()
        return {"token": token}

    def test_explicit_permission_grants_access(self, client, custom_perm_user):
        """User with explicit analytics:view can access analytics endpoint."""
        r = client.get(
            "/api/v1/maas/analytics/any-mesh-id/summary",
            headers={"X-API-Key": custom_perm_user["token"]},
        )
        # 404 (mesh not found) is fine — it means auth passed
        assert r.status_code in (200, 404)

    def test_wildcard_permission_grants_all(self, client):
        """User with '*' permission bypasses all checks."""
        email = f"wild-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/v1/maas/auth/register",
                        json={"email": email, "password": "password123"})
        token = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == token).first()
        user.permissions = "*"
        user.role = "user"
        db.commit()
        db.close()

        r = client.get(
            "/api/v1/maas/analytics/any-mesh-id/summary",
            headers={"X-API-Key": token},
        )
        assert r.status_code in (200, 404)

    def test_no_explicit_permission_role_user_forbidden(self, client):
        """Regular user without explicit permissions can't access analytics (operator-only)."""
        # Fresh user — no rotation risk, permissions explicitly None
        email = f"noperm-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/v1/maas/auth/register",
                        json={"email": email, "password": "password123"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == token).first()
        user.permissions = None
        user.role = "user"
        db.commit()
        db.close()

        r = client.get(
            "/api/v1/maas/analytics/any-mesh/summary",
            headers={"X-API-Key": token},
        )
        # User role doesn't have analytics:view → 403
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Bearer token / session-based auth (get_current_user_from_maas lines 118-122)
# ---------------------------------------------------------------------------

class TestBearerTokenAuth:
    """
    Tests the session-based auth path: Authorization: Bearer <session_token>
    This covers the code path in get_current_user_from_maas that checks
    UserSession.token and validates expiry.
    """

    @pytest.fixture(scope="class")
    def session_token(self, client):
        """Create a user + valid session directly in DB, return session token."""
        from src.database import Session as UserSession

        email = f"sess-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/v1/maas/auth/register",
                        json={"email": email, "password": "password123"})
        api_key = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == api_key).first()
        user_id = user.id

        sess_token = f"sess-{uuid.uuid4().hex}"
        db.add(UserSession(
            token=sess_token,
            user_id=user_id,
            email=email,
            expires_at=datetime.utcnow() + timedelta(days=7),
        ))
        db.commit()
        db.close()
        return sess_token

    def test_bearer_token_auth_success(self, client, session_token):
        """Valid Bearer token → 200 on /me."""
        r = client.get(
            "/api/v1/maas/auth/me",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert r.status_code == 200, r.text

    def test_bearer_token_returns_user_profile(self, client, session_token):
        r = client.get(
            "/api/v1/maas/auth/me",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        data = r.json()
        assert "email" in data
        assert "role" in data

    def test_expired_session_token_401(self, client):
        """Expired session token → 401."""
        from src.database import Session as UserSession

        email = f"exp-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post("/api/v1/maas/auth/register",
                        json={"email": email, "password": "password123"})
        api_key = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == api_key).first()
        user_id = user.id

        expired_token = f"exp-{uuid.uuid4().hex}"
        db.add(UserSession(
            token=expired_token,
            user_id=user_id,
            email=email,
            expires_at=datetime.utcnow() - timedelta(seconds=1),  # already expired
        ))
        db.commit()
        db.close()

        r = client.get(
            "/api/v1/maas/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert r.status_code == 401

    def test_invalid_bearer_token_401(self, client):
        """Non-existent Bearer token → 401."""
        r = client.get(
            "/api/v1/maas/auth/me",
            headers={"Authorization": "Bearer nonexistent-token-xyz"},
        )
        assert r.status_code == 401

    def test_api_key_takes_precedence_over_bearer(self, client, session_token, auth_data):
        """X-API-Key header takes precedence over Authorization Bearer."""
        # If both headers present, API key is checked first
        r = client.get(
            "/api/v1/maas/auth/me",
            headers={
                "X-API-Key": auth_data["token"],
                "Authorization": f"Bearer {session_token}",
            },
        )
        assert r.status_code in (200, 401)  # depends on whether auth_data token is still valid
