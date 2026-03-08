"""Unit tests for src/api/maas/endpoints/auth.py security behavior."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.maas.endpoints import auth as auth_module
from src.api.maas.auth import UserContext, get_current_user, set_auth_service, AuthService


def _build_client(user: UserContext | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/maas")
    if user:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _reset_auth_state() -> None:
    auth_module._user_store.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    # Reset the global auth service so sessions/keys don't leak between tests.
    set_auth_service(AuthService())


def _make_user(user_id: str = "u-1", plan: str = "pro") -> UserContext:
    return UserContext(user_id=user_id, plan=plan)


def test_login_rejects_wrong_password_for_existing_user():
    _reset_auth_state()
    client = _build_client()  # no user override — uses real auth

    email = "secure-auth@example.com"
    register_response = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": email,
            "password": "CorrectPassword123!",
        },
    )
    assert register_response.status_code == 201, register_response.text

    wrong_login_response = client.post(
        "/api/v1/maas/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!",
        },
    )
    assert wrong_login_response.status_code == 401
    assert wrong_login_response.json()["detail"] == "Invalid credentials"


def test_register_stores_password_hash_not_plaintext():
    _reset_auth_state()
    client = _build_client()

    raw_password = "PlaintextShouldNeverBeStored123!"
    response = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": "hash-storage@example.com",
            "password": raw_password,
        },
    )
    assert response.status_code == 201, response.text

    user_id = response.json()["user_id"]
    stored_user = auth_module._user_store[user_id]
    password_hash = stored_user.get("password_hash", "")

    assert password_hash
    assert password_hash != raw_password
    assert password_hash.startswith("pbkdf2_sha256$")


def test_register_rejects_case_insensitive_duplicate_email():
    _reset_auth_state()
    client = _build_client()

    first = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": "User@Example.Com",
            "password": "StrongPassword123!",
        },
    )
    assert first.status_code == 201, first.text

    duplicate = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": "user@example.com",
            "password": "AnotherStrongPassword123!",
        },
    )
    assert duplicate.status_code == 409


def test_login_matches_email_case_insensitively():
    _reset_auth_state()
    client = _build_client()

    register = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": "CaseInsensitive@Test.com",
            "password": "StrongPassword123!",
        },
    )
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/maas/auth/login",
        json={
            "email": "caseinsensitive@test.COM",
            "password": "StrongPassword123!",
        },
    )
    assert login.status_code == 200, login.text
    assert "session_token" in login.json()


def test_login_rate_limits_repeated_failures(monkeypatch):
    _reset_auth_state()
    client = _build_client()
    monkeypatch.setattr(auth_module, "_LOGIN_MAX_ATTEMPTS", 2)

    first = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    second = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    throttled = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert throttled.status_code == 429
    assert throttled.headers.get("Retry-After")


def test_successful_login_clears_failed_attempt_counter(monkeypatch):
    _reset_auth_state()
    client = _build_client()
    monkeypatch.setattr(auth_module, "_LOGIN_MAX_ATTEMPTS", 2)

    register = client.post(
        "/api/v1/maas/auth/register",
        json={"email": "clear-counter@example.com", "password": "CorrectPassword123!"},
    )
    assert register.status_code == 201, register.text

    fail_one = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "clear-counter@example.com", "password": "WrongPassword123!"},
    )
    success = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "clear-counter@example.com", "password": "CorrectPassword123!"},
    )
    fail_two = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "clear-counter@example.com", "password": "WrongPassword123!"},
    )
    fail_three = client.post(
        "/api/v1/maas/auth/login",
        json={"email": "clear-counter@example.com", "password": "WrongPassword123!"},
    )

    assert fail_one.status_code == 401
    assert success.status_code == 200
    assert fail_two.status_code == 401
    # Must still allow one more failed attempt after successful login reset.
    assert fail_three.status_code == 401


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def test_hash_password_produces_pbkdf2_format():
    h = auth_module._hash_password("my-password")
    parts = h.split("$")
    assert parts[0] == "pbkdf2_sha256"
    assert int(parts[1]) > 0
    assert len(parts[3]) == 64  # hex SHA-256 digest


def test_verify_password_roundtrip():
    pw = "correcthorsebatterystaple"
    h = auth_module._hash_password(pw)
    assert auth_module._verify_password(pw, h) is True
    assert auth_module._verify_password("wrongpassword", h) is False


def test_verify_password_returns_false_for_malformed_hash():
    assert auth_module._verify_password("any", "not-a-real-hash") is False
    assert auth_module._verify_password("any", "") is False


def test_normalize_email_strips_and_lowercases():
    assert auth_module._normalize_email("  User@EXAMPLE.com  ") == "user@example.com"


# ---------------------------------------------------------------------------
# GET /me — user profile
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_returns_profile_for_authenticated_user(self):
        _reset_auth_state()
        user = _make_user("u-prof", "pro")
        # Pre-populate user store so endpoint can find email
        auth_module._user_store["u-prof"] = {
            "email": "prof@test.com",
            "name": "Prof User",
            "plan": "pro",
        }
        client = _build_client(user)

        resp = client.get("/api/v1/maas/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "u-prof"
        assert data["email"] == "prof@test.com"
        assert data["plan"] == "pro"

    def test_returns_unknown_email_when_user_not_in_store(self):
        _reset_auth_state()
        user = _make_user("u-ghost", "starter")
        client = _build_client(user)

        resp = client.get("/api/v1/maas/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "unknown"

    def test_requires_auth(self):
        _reset_auth_state()
        # No dependency override — unauthenticated request
        client = _build_client()
        resp = client.get("/api/v1/maas/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api-key — key rotation
# ---------------------------------------------------------------------------

class TestRotateApiKey:
    def test_rotation_returns_new_key(self):
        _reset_auth_state()
        user = _make_user("u-rotate", "pro")
        auth = AuthService()
        set_auth_service(auth)
        old_key = auth.generate_api_key("u-rotate", "pro")
        user.api_key = old_key

        client = _build_client(user)
        resp = client.post("/api/v1/maas/auth/api-key", json={"revoke_old": True})
        assert resp.status_code == 200
        new_key = resp.json()["api_key"]
        assert new_key
        assert new_key != old_key
        # Old key was revoked
        assert old_key not in auth._api_keys

    def test_rotation_without_revoke_keeps_old_key(self):
        _reset_auth_state()
        user = _make_user("u-norevoke", "pro")
        auth = AuthService()
        set_auth_service(auth)
        old_key = auth.generate_api_key("u-norevoke", "pro")
        user.api_key = old_key

        client = _build_client(user)
        resp = client.post("/api/v1/maas/auth/api-key", json={"revoke_old": False})
        assert resp.status_code == 200
        # Old key is still in auth service
        assert old_key in auth._api_keys

    def test_rotation_requires_auth(self):
        _reset_auth_state()
        client = _build_client()
        resp = client.post("/api/v1/maas/auth/api-key", json={"revoke_old": True})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_ends_session(self):
        _reset_auth_state()
        auth = AuthService()
        set_auth_service(auth)
        token = auth.create_session("u-logout")
        user = UserContext(user_id="u-logout", plan="pro", session_token=token)
        client = _build_client(user)

        resp = client.post("/api/v1/maas/auth/logout")
        assert resp.status_code == 200
        assert "Logged out" in resp.json()["message"]
        # Session should be invalidated
        assert auth.validate_session(token) is None

    def test_logout_without_session_token_still_succeeds(self):
        _reset_auth_state()
        user = _make_user("u-nosession", "pro")
        user.session_token = None
        client = _build_client(user)
        resp = client.post("/api/v1/maas/auth/logout")
        assert resp.status_code == 200

    def test_logout_requires_auth(self):
        _reset_auth_state()
        client = _build_client()
        resp = client.post("/api/v1/maas/auth/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /account
# ---------------------------------------------------------------------------

class TestDeleteAccount:
    def test_delete_account_success(self):
        _reset_auth_state()
        user = _make_user("u-delete", "pro")
        auth_module._user_store["u-delete"] = {"email": "del@test.com", "plan": "pro"}
        client = _build_client(user)

        resp = client.delete("/api/v1/maas/auth/account", params={"confirm": "true"})
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    def test_delete_requires_confirmation_false_returns_400(self):
        _reset_auth_state()
        user = _make_user("u-noconf", "pro")
        client = _build_client(user)

        resp = client.delete("/api/v1/maas/auth/account", params={"confirm": "false"})
        assert resp.status_code == 400

    def test_delete_account_requires_auth(self):
        _reset_auth_state()
        client = _build_client()
        resp = client.delete("/api/v1/maas/auth/account", params={"confirm": "true"})
        assert resp.status_code == 401

    def test_delete_account_removes_user_from_store(self):
        _reset_auth_state()
        user = _make_user("u-vanish", "pro")
        auth_module._user_store["u-vanish"] = {"email": "vanish@test.com", "plan": "pro"}
        client = _build_client(user)

        client.delete("/api/v1/maas/auth/account", params={"confirm": "true"})

        assert "u-vanish" not in auth_module._user_store
