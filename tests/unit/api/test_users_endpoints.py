"""
Unit tests for src/api/users.py User Management API.

Tests user models, password hashing, API key generation, session tokens,
admin token verification, and router metadata.
All database interactions are mocked.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

try:
    from src.api.users import (SessionResponse, UserCreate, UserLogin,
                               UserResponse, generate_api_key,
                               generate_session_token, hash_password, router,
                               users_db, verify_admin_token)

    USERS_AVAILABLE = True
except ImportError as exc:
    USERS_AVAILABLE = False
    pytest.skip(f"users module not importable: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestUserModels:
    def test_user_create_valid(self):
        u = UserCreate(email="test@example.com", password="securepass123")
        assert u.email == "test@example.com"
        assert u.password == "securepass123"
        assert u.full_name is None
        assert u.company is None

    def test_user_create_with_optional_fields(self):
        u = UserCreate(
            email="dev@corp.io",
            password="password1234",
            full_name="Dev User",
            company="Corp Inc.",
        )
        assert u.full_name == "Dev User"
        assert u.company == "Corp Inc."

    def test_user_create_invalid_email_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="securepass123")

    def test_user_create_short_password_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(email="a@b.com", password="short")

    def test_user_login_model(self):
        login = UserLogin(email="a@b.com", password="mypassword")
        assert login.email == "a@b.com"

    def test_user_response_model(self):
        from datetime import datetime

        resp = UserResponse(
            id="uid1",
            email="a@b.com",
            full_name="Test",
            company=None,
            plan="free",
            created_at=datetime.utcnow(),
        )
        assert resp.plan == "free"
        assert resp.id == "uid1"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("testpass")
        assert hashed.startswith("$2")
        assert len(hashed) > 50

    def test_hash_password_different_results(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        # bcrypt uses random salt, so hashes differ
        assert h1 != h2

    def test_generate_api_key_format(self):
        key = generate_api_key()
        assert key.startswith("x0tta6bl4_")
        assert len(key) > 20

    def test_generate_api_key_unique(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2

    def test_generate_session_token_length(self):
        token = generate_session_token()
        assert len(token) > 40

    def test_generate_session_token_unique(self):
        t1 = generate_session_token()
        t2 = generate_session_token()
        assert t1 != t2


# ---------------------------------------------------------------------------
# Admin token verification
# ---------------------------------------------------------------------------


class TestAdminTokenVerification:
    @pytest.mark.asyncio
    async def test_admin_token_not_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ADMIN_TOKEN", None)
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token(None)
            assert exc_info.value.status_code == 500
            os.environ["ADMIN_TOKEN"] = "test-admin-token"

    @pytest.mark.asyncio
    async def test_admin_token_wrong(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "real-token"}, clear=False):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token("fake-token")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_token_correct(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "match-me"}, clear=False):
            result = await verify_admin_token("match-me")
            assert result is None  # no exception means success


# ---------------------------------------------------------------------------
# Router metadata
# ---------------------------------------------------------------------------


class TestUsersRouter:
    def test_router_prefix(self):
        assert router.prefix == "/api/v1/users"

    def test_router_tags(self):
        assert "users" in router.tags

    def test_router_has_register_route(self):
        route_paths = [r.path for r in router.routes]
        assert any("/register" in p for p in route_paths)

    def test_router_has_login_route(self):
        route_paths = [r.path for r in router.routes]
        assert any("/login" in p for p in route_paths)
