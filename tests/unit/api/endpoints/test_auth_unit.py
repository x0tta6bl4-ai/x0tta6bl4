"""Unit tests for src/api/maas/endpoints/auth.py security behavior."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.maas.endpoints import auth as auth_module
from src.api.maas.auth import UserContext, get_current_user, set_auth_service, AuthService
from src.coordination.events import EventBus, EventType
from src.database import Base, get_db


def _build_client(
    user: UserContext | None = None,
    event_bus: EventBus | None = None,
) -> TestClient:
    app = FastAPI()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    if event_bus is not None:
        @app.middleware("http")
        async def _inject_event_bus(request, call_next):
            request.state.event_bus = event_bus
            return await call_next(request)

    app.include_router(auth_module.router, prefix="/api/v1/maas/auth")
    app.dependency_overrides[get_db] = override_get_db
    if user:
        async def _override_get_current_user():
            return user
        app.dependency_overrides[get_current_user] = _override_get_current_user
    return TestClient(app)


def _reset_auth_state() -> None:
    auth_module._user_store.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    # Reset the global auth service so sessions/keys don't leak between tests.
    set_auth_service(AuthService())


def _make_user(user_id: str = "u-1", plan: str = "pro") -> UserContext:
    return UserContext(user_id=user_id, plan=plan)


def _auth_payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(source_agent=source_agent, limit=20)
    ]


def test_modular_auth_register_and_login_publish_redacted_evidence(tmp_path):
    _reset_auth_state()
    bus = EventBus(project_root=str(tmp_path))
    client = _build_client(event_bus=bus)

    email = "Modular-Auth-Secret@example.test"
    password = "PrivatePassword123!"
    name = "Private Auth Name"
    register_response = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    login_response = client.post(
        "/api/v1/maas/auth/login",
        json={"email": email.lower(), "password": password},
    )

    assert register_response.status_code == 200, register_response.text
    assert login_response.status_code == 200, login_response.text

    register_payload = _auth_payloads(bus, "maas-modular-auth-register")[-1]
    login_payload = _auth_payloads(bus, "maas-modular-auth-login")[-1]

    assert register_payload["operation"] == "modular_auth_register"
    assert register_payload["service_name"] == "maas-modular-auth-register"
    assert register_payload["layer"] == "api_modular_auth_registration_intent"
    assert register_payload["status"] == "success"
    assert register_payload["http_status_code"] == 200
    assert register_payload["request_summary"]["email_hash"] == (
        auth_module._redacted_sha256_prefix(email.lower())
    )
    assert register_payload["request_summary"]["password_present"] is True
    assert register_payload["request_summary"]["name_present"] is True
    assert register_payload["credential_evidence"]["api_key_issued"] is True
    assert register_payload["auth_store_evidence"]["committed"] is True

    assert login_payload["operation"] == "modular_auth_login"
    assert login_payload["service_name"] == "maas-modular-auth-login"
    assert login_payload["layer"] == "api_modular_auth_login_intent"
    assert login_payload["status"] == "success"
    assert login_payload["credential_evidence"]["session_token_issued"] is True
    assert login_payload["raw_credentials_redacted"] is True

    serialized = json.dumps([register_payload, login_payload], sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    response_values = [
        register_response.json()["user_id"],
        register_response.json()["api_key"],
        login_response.json()["session_token"],
    ]
    for raw_value in [email, email.lower(), password, name, *response_values]:
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_modular_auth_control_and_read_routes_publish_redacted_evidence(tmp_path):
    _reset_auth_state()
    bus = EventBus(project_root=str(tmp_path))
    auth = AuthService()
    set_auth_service(auth)
    user = _make_user("modular-auth-user-secret", "pro")
    old_key = auth.generate_api_key(user.user_id, user.plan)
    session_token = auth.create_session(user.user_id)
    user.api_key = old_key
    user.session_token = session_token
    auth_module._user_store[user.user_id] = {
        "email": "profile-secret@example.test",
        "name": "Private Profile Name",
        "plan": "pro",
    }
    client = _build_client(user=user, event_bus=bus)

    profile_response = client.get("/api/v1/maas/auth/me")
    rotate_response = client.post(
        "/api/v1/maas/auth/api-key",
        json={"revoke_old": True},
    )
    logout_response = client.post("/api/v1/maas/auth/logout")
    blocked_delete_response = client.delete(
        "/api/v1/maas/auth/account",
        params={"confirm": "false"},
    )
    delete_response = client.delete(
        "/api/v1/maas/auth/account",
        params={"confirm": "true"},
    )

    assert profile_response.status_code == 200
    assert rotate_response.status_code == 200, rotate_response.text
    assert logout_response.status_code == 200
    assert blocked_delete_response.status_code == 400
    assert delete_response.status_code == 200

    profile_payload = _auth_payloads(bus, "maas-modular-auth-profile-read")[-1]
    rotate_payload = _auth_payloads(
        bus,
        "maas-modular-auth-api-key-rotation",
    )[-1]
    logout_payload = _auth_payloads(bus, "maas-modular-auth-session-control")[-1]
    account_payloads = _auth_payloads(bus, "maas-modular-auth-account-delete")

    assert profile_payload["observed_state"] is True
    assert profile_payload["auth_store_evidence"]["action"] == "read_user_profile"
    assert rotate_payload["credential_evidence"]["api_key_issued"] is True
    assert rotate_payload["credential_evidence"]["api_key_revoked"] is True
    assert logout_payload["credential_evidence"]["session_ended"] is True
    assert account_payloads[0]["stage"] == "account_delete_blocked"
    assert account_payloads[0]["reason"] == "confirmation_required"
    assert account_payloads[-1]["stage"] == "account_deleted"
    assert account_payloads[-1]["claim_boundary"] == (
        auth_module._MODULAR_AUTH_CLAIM_BOUNDARY
    )

    all_payloads = [
        profile_payload,
        rotate_payload,
        logout_payload,
        *account_payloads,
    ]
    serialized = json.dumps(all_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user.user_id,
        old_key,
        rotate_response.json()["api_key"],
        session_token,
        "profile-secret@example.test",
        "Private Profile Name",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


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
    assert register_response.status_code == 200, register_response.text

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
    assert response.status_code == 200, response.text

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
    assert first.status_code == 200, first.text

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
    assert register.status_code == 200, register.text

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
    assert register.status_code == 200, register.text

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
        assert auth._api_key_hash(old_key) not in auth._api_keys

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
        assert old_key not in auth._api_keys
        assert auth._api_key_hash(old_key) in auth._api_keys

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
