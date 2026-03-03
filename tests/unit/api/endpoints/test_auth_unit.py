"""Unit tests for src/api/maas/endpoints/auth.py security behavior."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.maas.endpoints import auth as auth_module


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/maas")
    return TestClient(app)


def _reset_auth_state() -> None:
    auth_module._user_store.clear()
    auth_module._LOGIN_ATTEMPTS.clear()


def test_login_rejects_wrong_password_for_existing_user():
    _reset_auth_state()
    client = _build_client()

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
