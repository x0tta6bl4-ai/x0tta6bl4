import asyncio
import os
import time
from types import SimpleNamespace

import pytest
from aiohttp import web

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from libx0t.network.proxy_auth_middleware import (Permission, ProxyAuthMiddleware,
                                               RequestSigner, Role,
                                               JWTAuthManager, APIKeyStore,
                                               RateLimiter)
import libx0t.network.proxy_auth_middleware as mod


class _FakeRequest(dict):
    def __init__(self, path="/private", remote="127.0.0.1", headers=None):
        super().__init__()
        self.path = path
        self.remote = remote
        self.headers = headers or {}


class _PassRateLimiter:
    async def acquire(self, _client_id):
        return True

    def get_remaining(self, _client_id):
        return 7


class _BlockRateLimiter:
    async def acquire(self, _client_id):
        return False

    def get_remaining(self, _client_id):
        return 0


class _APIKeyStore:
    def __init__(self, identity=None):
        self._identity = identity

    def validate(self, _api_key):
        return self._identity


class _JWTManager:
    def __init__(self, identity=None):
        self._identity = identity

    def validate_token(self, _token):
        return self._identity


async def _ok_handler(_request):
    return web.json_response({"ok": True})


def test_client_identity_permission_helpers():
    identity = mod.ClientIdentity(
        client_id="c1",
        role=Role.OPERATOR,
        permissions=Role.OPERATOR.value,
    )
    assert identity.has_permission(Permission.PROXY_READ) is True
    assert identity.can_access_proxy() is True
    assert identity.can_modify_proxy() is True


def test_jwt_manager_requires_secret_in_production(monkeypatch):
    monkeypatch.delenv("PROXY_JWT_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="PROXY_JWT_SECRET must be set"):
        JWTAuthManager()


def test_jwt_manager_without_secret_non_prod_disabled(monkeypatch, caplog):
    monkeypatch.delenv("PROXY_JWT_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    with caplog.at_level("WARNING"):
        manager = JWTAuthManager()
    assert manager.validate_token("anything") is None
    assert "JWT auth disabled" in caplog.text


def test_jwt_create_and_validate_roundtrip():
    manager = JWTAuthManager(secret="test-secret", expiry_hours=1)
    token = manager.create_token("client-1", Role.OPERATOR, {"tenant": "acme"})
    identity = manager.validate_token(token)
    assert identity is not None
    assert identity.client_id == "client-1"
    assert Permission.PROXY_WRITE in identity.permissions


def test_api_key_store_loads_named_role_from_env(monkeypatch):
    monkeypatch.setenv("PROXY_API_KEY_CI", "secret-key:operator")
    store = APIKeyStore()
    identity = store.validate("secret-key")
    assert identity is not None
    assert identity.role == Role.OPERATOR
    assert identity.api_key_id == "CI"


def test_api_key_store_unknown_role_falls_back_to_viewer(monkeypatch, caplog):
    monkeypatch.setenv("PROXY_API_KEY_BAD", "bad-key:not-a-role")
    with caplog.at_level("WARNING"):
        store = APIKeyStore()
    identity = store.validate("bad-key")
    assert identity is not None
    assert identity.role == Role.VIEWER
    assert "falling back to VIEWER" in caplog.text


def test_api_key_store_validate_missing_key_returns_none():
    store = APIKeyStore()
    assert store.validate("does-not-exist") is None


def test_api_key_store_rotate_key_replaces_old_entry(monkeypatch):
    monkeypatch.setenv("PROXY_API_KEY_ROT", "old-secret:viewer")
    store = APIKeyStore()
    assert store.validate("old-secret") is not None
    new_key = store.rotate_key("ROT")
    assert new_key.startswith("pk_")
    assert store.validate("old-secret") is None
    new_identity = store.validate(new_key)
    assert new_identity is not None
    assert new_identity.role == Role.OPERATOR


def test_jwt_create_token_without_secret_raises(monkeypatch):
    monkeypatch.delenv("PROXY_JWT_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    manager = JWTAuthManager(secret="")
    with pytest.raises(ValueError, match="JWT secret not configured"):
        manager.create_token("c1", Role.VIEWER)


def test_jwt_validate_expired_and_invalid_paths(monkeypatch, caplog):
    manager = JWTAuthManager(secret="s")
    monkeypatch.setattr(mod.jwt, "decode", lambda *a, **k: (_ for _ in ()).throw(mod.jwt.ExpiredSignatureError("expired")))
    with caplog.at_level("WARNING"):
        assert manager.validate_token("token") is None
    assert "JWT token expired" in caplog.text

    monkeypatch.setattr(mod.jwt, "decode", lambda *a, **k: (_ for _ in ()).throw(mod.jwt.InvalidTokenError("bad")))
    with caplog.at_level("WARNING"):
        assert manager.validate_token("token") is None
    assert "Invalid JWT token" in caplog.text


@pytest.mark.asyncio
async def test_rate_limiter_burst_and_reset():
    limiter = RateLimiter(requests_per_minute=60, burst_size=2)
    assert limiter.get_remaining("missing-client") == 0
    assert await limiter.acquire("c1") is True
    assert await limiter.acquire("c1") is True
    assert limiter.get_remaining("c1") < 0.1
    assert await limiter.acquire("c1") is False
    limiter.reset("c1")
    assert await limiter.acquire("c1") is True


@pytest.mark.asyncio
async def test_authenticate_public_path_bypasses_auth_and_rate_limit():
    class _NeverUsedRateLimiter:
        async def acquire(self, _client_id):  # pragma: no cover - should not be called
            raise AssertionError("rate limiter should not be called for public paths")

        def get_remaining(self, _client_id):  # pragma: no cover
            return 0

    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_NeverUsedRateLimiter(),
        require_auth=True,
    )
    request = _FakeRequest(path="/health")
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 200


@pytest.mark.asyncio
async def test_authenticate_rate_limited_returns_429():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_BlockRateLimiter(),
        require_auth=True,
    )
    request = _FakeRequest(path="/private")
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 429
    assert "Rate limit exceeded" in response.text


@pytest.mark.asyncio
async def test_authenticate_requires_auth_when_missing_identity():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(identity=None),
        jwt_manager=_JWTManager(identity=None),
        rate_limiter=_PassRateLimiter(),
        require_auth=True,
    )
    request = _FakeRequest(path="/private")
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 401
    assert "Authentication required" in response.text


@pytest.mark.asyncio
async def test_authenticate_accepts_api_key_identity_and_sets_rate_header():
    identity = SimpleNamespace(
        client_id="apikey:ci",
        role=Role.OPERATOR,
        permissions=Role.OPERATOR.value,
        has_permission=lambda p: p in Role.OPERATOR.value,
    )
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(identity=identity),
        jwt_manager=_JWTManager(identity=None),
        rate_limiter=_PassRateLimiter(),
        require_auth=True,
    )
    request = _FakeRequest(path="/private", headers={"X-API-Key": "k"})
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 200
    assert request["identity"].client_id == "apikey:ci"
    assert response.headers["X-RateLimit-Remaining"] == "7"


@pytest.mark.asyncio
async def test_authenticate_accepts_bearer_jwt_identity():
    identity = SimpleNamespace(
        client_id="jwt:ci",
        role=Role.ADMIN,
        permissions=Role.ADMIN.value,
        has_permission=lambda p: p in Role.ADMIN.value,
    )
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(identity=None),
        jwt_manager=_JWTManager(identity=identity),
        rate_limiter=_PassRateLimiter(),
        require_auth=True,
    )
    request = _FakeRequest(path="/private", headers={"Authorization": "Bearer token"})
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 200
    assert request["identity"].client_id == "jwt:ci"


@pytest.mark.asyncio
async def test_authenticate_allows_anonymous_when_not_required():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(identity=None),
        jwt_manager=_JWTManager(identity=None),
        rate_limiter=_PassRateLimiter(),
        require_auth=False,
    )
    request = _FakeRequest(path="/private")
    response = await middleware.authenticate(request, _ok_handler)
    assert response.status == 200
    assert request["identity"].client_id == "anonymous"


@pytest.mark.asyncio
async def test_require_permission_decorator_denies_without_permission():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_PassRateLimiter(),
    )

    @middleware.require_permission(Permission.PROXY_ADMIN)
    async def _handler(_request):
        return web.json_response({"ok": True})

    request = _FakeRequest()
    request["identity"] = SimpleNamespace(
        permissions=Role.VIEWER.value,
        has_permission=lambda p: p in Role.VIEWER.value,
    )
    response = await _handler(request)
    assert response.status == 403
    assert "Permission denied" in response.text


@pytest.mark.asyncio
async def test_require_permission_decorator_requires_identity_and_allows_valid():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_PassRateLimiter(),
    )

    @middleware.require_permission(Permission.PROXY_READ)
    async def _handler(_request):
        return web.json_response({"ok": True})

    request_no_identity = _FakeRequest()
    denied = await _handler(request_no_identity)
    assert denied.status == 401

    request_with_identity = _FakeRequest()
    request_with_identity["identity"] = SimpleNamespace(
        permissions=Role.OPERATOR.value,
        has_permission=lambda p: p in Role.OPERATOR.value,
    )
    ok = await _handler(request_with_identity)
    assert ok.status == 200


@pytest.mark.asyncio
async def test_require_any_permission_decorator_allows_when_any_matches():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_PassRateLimiter(),
    )

    @middleware.require_any_permission(
        [Permission.PROXY_ADMIN, Permission.PROXY_WRITE]
    )
    async def _handler(_request):
        return web.json_response({"ok": True})

    request = _FakeRequest()
    request["identity"] = SimpleNamespace(
        permissions=Role.OPERATOR.value,
        has_permission=lambda p: p in Role.OPERATOR.value,
    )
    response = await _handler(request)
    assert response.status == 200


@pytest.mark.asyncio
async def test_require_any_permission_decorator_missing_identity_and_denied():
    middleware = ProxyAuthMiddleware(
        api_key_store=_APIKeyStore(),
        jwt_manager=_JWTManager(),
        rate_limiter=_PassRateLimiter(),
    )

    @middleware.require_any_permission(
        [Permission.PROXY_ADMIN, Permission.CONFIG_WRITE]
    )
    async def _handler(_request):
        return web.json_response({"ok": True})

    request_no_identity = _FakeRequest()
    missing = await _handler(request_no_identity)
    assert missing.status == 401

    request_denied = _FakeRequest()
    request_denied["identity"] = SimpleNamespace(
        permissions=Role.VIEWER.value,
        has_permission=lambda p: p in Role.VIEWER.value,
    )
    denied = await _handler(request_denied)
    assert denied.status == 403
    assert "required_any" in denied.text


def test_request_signer_sign_and_verify_roundtrip():
    signer = RequestSigner(secret_key="k")
    ts = str(int(time.time()))
    headers = {"X-Request-Timestamp": ts, "X-Client": "test"}
    signature = signer.sign_request("POST", "/request", headers, '{"a":1}', ts)
    assert signer.verify_signature(
        signature, "POST", "/request", headers, '{"a":1}', ts, max_age_seconds=30
    )


def test_request_signer_rejects_old_or_invalid_timestamp():
    signer = RequestSigner(secret_key="k")
    old_ts = str(int(time.time()) - 3600)
    headers = {"X-Request-Timestamp": old_ts}
    signature = signer.sign_request("GET", "/x", headers, None, old_ts)
    assert not signer.verify_signature(
        signature, "GET", "/x", headers, None, old_ts, max_age_seconds=30
    )
    bad_headers = {"X-Request-Timestamp": "not-a-number"}
    assert not signer.verify_signature("deadbeef", "GET", "/x", bad_headers)


def test_request_signer_rejects_when_timestamp_missing():
    signer = RequestSigner(secret_key="k")
    assert not signer.verify_signature("deadbeef", "GET", "/x", headers={})


def test_create_auth_middleware_factory():
    middleware = mod.create_auth_middleware(
        require_auth=False, requests_per_minute=77, jwt_secret="x"
    )
    assert isinstance(middleware, mod.ProxyAuthMiddleware)
    assert middleware.require_auth is False
    assert middleware.rate_limiter.requests_per_minute == 77
