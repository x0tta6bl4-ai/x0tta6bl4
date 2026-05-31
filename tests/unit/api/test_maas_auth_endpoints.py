"""
Unit tests for src/api/maas_auth.py — Auth endpoints including
/register, /login, /me, and the /set-admin privilege escalation guard.
"""
import asyncio
import uuid
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.app import app
import src.api.maas_auth as maas_auth_mod
from src.database import Base, get_db, User
from src.services.maas_auth_service import find_user_by_api_key

_TEST_DB_PATH = f"./test_auth_ep_{uuid.uuid4().hex}.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if original is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


def _force_maas_auth_dependencies_ready(monkeypatch):
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_user_model_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_session_model_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_service_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_api_key_manager_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_rbac_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_token_helpers_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_audit_log_available", lambda: True)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_oidc_enabled", lambda: False)
    monkeypatch.setattr(maas_auth_mod, "_maas_auth_oidc_redirect_available", lambda: True)
    monkeypatch.setattr(
        maas_auth_mod, "_maas_auth_bootstrap_token_configured", lambda: False
    )


@pytest.fixture(scope="module")
def normal_user(client):
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    return {"email": email, "api_key": api_key, "headers": {"X-API-Key": api_key}}


@pytest.fixture(scope="module")
def admin_user(client):
    email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    # Promote to admin directly in DB
    db = TestingSessionLocal()
    user = find_user_by_api_key(db, api_key)
    user.role = "admin"
    db.commit()
    db.close()
    return {"email": email, "api_key": api_key, "headers": {"X-API-Key": api_key}}


@pytest.fixture(scope="module")
def target_user(client):
    """A user to be promoted in set-admin tests."""
    email = f"target-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    return {"email": email, "api_key": api_key}


class TestMaaSAuthReadiness:
    def test_router_has_readiness_route(self):
        route_paths = [r.path for r in maas_auth_mod.router.routes]
        assert "/api/v1/maas/auth/readiness" in route_paths

    def test_ready_when_local_dependencies_are_available(self, monkeypatch):
        _force_maas_auth_dependencies_ready(monkeypatch)
        db = MagicMock(spec=["query", "add", "commit", "refresh"])

        payload = maas_auth_mod._maas_auth_readiness_status(db)

        assert payload["status"] == "ready"
        assert payload["maas_auth_runtime_ready"] is True
        assert payload["auth_db_ready"] is True
        assert payload["user_model_ready"] is True
        assert payload["session_model_ready"] is True
        assert payload["auth_service_ready"] is True
        assert payload["api_key_manager_ready"] is True
        assert payload["rbac_ready"] is True
        assert payload["token_helpers_ready"] is True
        assert payload["audit_log_ready"] is True
        assert payload["oidc_enabled"] is False
        assert payload["oidc_redirect_ready"] is True
        assert payload["bootstrap_token_configured"] is False
        assert payload["cross_plane_claim_gate"]["allowed"] is False
        assert "production_readiness" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
        assert payload["degraded_dependencies"] == []

    def test_degraded_when_dependencies_are_missing(self, monkeypatch):
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_user_model_available", lambda: False)
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_session_model_available", lambda: False)
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_service_available", lambda: False)
        monkeypatch.setattr(
            maas_auth_mod, "_maas_auth_api_key_manager_available", lambda: False
        )
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_rbac_available", lambda: False)
        monkeypatch.setattr(
            maas_auth_mod, "_maas_auth_token_helpers_available", lambda: False
        )
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_audit_log_available", lambda: False)
        monkeypatch.setattr(maas_auth_mod, "_maas_auth_oidc_enabled", lambda: True)
        monkeypatch.setattr(
            maas_auth_mod, "_maas_auth_oidc_redirect_available", lambda: False
        )
        monkeypatch.setattr(
            maas_auth_mod, "_maas_auth_bootstrap_token_configured", lambda: False
        )

        payload = maas_auth_mod._maas_auth_readiness_status(SimpleNamespace())

        assert payload["status"] == "degraded"
        assert payload["maas_auth_runtime_ready"] is False
        assert payload["degraded_dependencies"] == [
            "database",
            "user_model",
            "session_model",
            "auth_service",
            "api_key_manager",
            "rbac",
            "token_helpers",
            "audit_log",
            "oidc_redirect",
        ]
        assert "BOOTSTRAP_TOKEN is intentionally optional" in (
            payload["backing_state"]["bootstrap_token"]
        )
        assert "does not create a user" in payload["claim_boundary"]

    def test_endpoint_marks_degraded_dependencies(self, monkeypatch):
        _force_maas_auth_dependencies_ready(monkeypatch)
        request = SimpleNamespace(state=SimpleNamespace())

        payload = asyncio.run(
            maas_auth_mod.maas_auth_readiness(request, db=SimpleNamespace())
        )

        assert payload["status"] == "degraded"
        assert request.state.degraded_dependencies == {"database"}


class TestMe:
    def test_me_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/maas/auth/me")
        assert resp.status_code == 401

    def test_me_authenticated_returns_profile(self, client, normal_user):
        resp = client.get("/api/v1/maas/auth/me", headers=normal_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == normal_user["email"]
        assert "role" in data
        assert "plan" in data

    def test_me_shows_correct_role(self, client, admin_user):
        resp = client.get("/api/v1/maas/auth/me", headers=admin_user["headers"])
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


class TestSetAdmin:
    def test_set_admin_unauthenticated_returns_401(self, client, target_user):
        """Unauthenticated request to /set-admin must be rejected."""
        resp = client.post(f"/api/v1/maas/auth/set-admin/{target_user['email']}")
        assert resp.status_code == 401

    def test_set_admin_as_normal_user_returns_403(self, client, normal_user, target_user):
        """Non-admin user cannot promote others to admin."""
        resp = client.post(
            f"/api/v1/maas/auth/set-admin/{target_user['email']}",
            headers=normal_user["headers"],
        )
        assert resp.status_code == 403

    def test_set_admin_as_admin_succeeds(self, client, admin_user, target_user):
        """Admin user can promote another user to admin."""
        resp = client.post(
            f"/api/v1/maas/auth/set-admin/{target_user['email']}",
            headers=admin_user["headers"],
        )
        assert resp.status_code == 200
        assert "ADMIN" in resp.json()["message"].upper()

    def test_set_admin_nonexistent_user_returns_404(self, client, admin_user):
        """Promoting a non-existent email returns 404."""
        resp = client.post(
            "/api/v1/maas/auth/set-admin/nobody@nonexistent.invalid",
            headers=admin_user["headers"],
        )
        assert resp.status_code == 404

    def test_set_admin_verifies_role_in_db(self, client, admin_user, target_user):
        """After set-admin, the user's /me endpoint shows role=admin."""
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == target_user["email"]).first()
        target_role = user.role
        db.close()
        assert target_role == "admin"
        # Verify via /me
        resp = client.get(
            "/api/v1/maas/auth/me",
            headers={"X-API-Key": target_user["api_key"]},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


class TestRegisterLogin:
    def test_duplicate_email_returns_400(self, client, normal_user):
        resp = client.post(
            "/api/v1/maas/auth/register",
            json={"email": normal_user["email"], "password": "password123"},
        )
        assert resp.status_code == 400

    def test_short_password_returns_422(self, client):
        resp = client.post(
            "/api/v1/maas/auth/register",
            json={"email": f"short-{uuid.uuid4().hex[:6]}@test.com", "password": "abc"},
        )
        assert resp.status_code == 422

    def test_login_correct_credentials(self, client, normal_user):
        resp = client.post(
            "/api/v1/maas/auth/login",
            json={"email": normal_user["email"], "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password_returns_401(self, client, normal_user):
        resp = client.post(
            "/api/v1/maas/auth/login",
            json={"email": normal_user["email"], "password": "wrongpassword"},
        )
        assert resp.status_code == 401


class TestBootstrapAdmin:
    """Bootstrap endpoint — создаёт первого администратора при отсутствии BOOTSTRAP_TOKEN."""

    def test_bootstrap_without_token_env_returns_403(self, client):
        """Если BOOTSTRAP_TOKEN не задан в env — endpoint отключён."""
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BOOTSTRAP_TOKEN", None)
            resp = client.post(
                "/api/v1/maas/auth/bootstrap-admin",
                json={"email": f"boot-{uuid.uuid4().hex[:6]}@test.com",
                      "password": "bootstrap123"},
            )
        assert resp.status_code == 403

    def test_bootstrap_wrong_token_returns_403(self, client):
        """Неверный токен отклоняется."""
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"BOOTSTRAP_TOKEN": "correct-token"}):
            resp = client.post(
                "/api/v1/maas/auth/bootstrap-admin",
                json={"email": f"boot-{uuid.uuid4().hex[:6]}@test.com",
                      "password": "bootstrap123"},
                headers={"X-Bootstrap-Token": "wrong-token"},
            )
        assert resp.status_code == 403

    def test_bootstrap_creates_admin_when_no_admins(self, client):
        """Корректный токен создаёт admin-пользователя если их ещё нет."""
        import os
        from unittest.mock import patch
        email = f"first-admin-{uuid.uuid4().hex[:6]}@test.com"
        # Убираем всех admin из БД
        db = TestingSessionLocal()
        db.query(User).filter(User.role == "admin").update({"role": "user"})
        db.commit()
        db.close()

        with patch.dict(os.environ, {"BOOTSTRAP_TOKEN": "test-bootstrap-secret"}):
            resp = client.post(
                "/api/v1/maas/auth/bootstrap-admin",
                json={"email": email, "password": "strongpass123"},
                headers={"X-Bootstrap-Token": "test-bootstrap-secret"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data

        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.role == "admin"
        db.close()

    def test_bootstrap_disabled_when_admin_exists(self, client, admin_user):
        """Если admin уже есть — bootstrap возвращает 409."""
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"BOOTSTRAP_TOKEN": "test-bootstrap-secret"}):
            resp = client.post(
                "/api/v1/maas/auth/bootstrap-admin",
                json={"email": f"boot-{uuid.uuid4().hex[:6]}@test.com",
                      "password": "bootstrap123"},
                headers={"X-Bootstrap-Token": "test-bootstrap-secret"},
            )
        assert resp.status_code == 409
