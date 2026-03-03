"""Unit tests for src/api/maas/endpoints/auth.py security behavior."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.maas.endpoints import auth as auth_module


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/maas")
    return TestClient(app)


def test_login_rejects_wrong_password_for_existing_user():
    auth_module._user_store.clear()
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
    auth_module._user_store.clear()
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
