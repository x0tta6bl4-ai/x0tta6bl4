"""Unit tests for src/api/middleware/metering.py."""

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI, Response
from starlette.requests import Request

from src.api.middleware import metering as mod
from src.api.middleware.metering import MeteringMiddleware


def _make_request(app: FastAPI, path: str, headers: Optional[Dict[str, str]] = None) -> Request:
    raw_headers = []
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))

    scope: Dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


class _DummyDB:
    def __init__(self, user: Optional[SimpleNamespace], commit_error: Optional[Exception] = None):
        self._user = user
        self._commit_error = commit_error
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.first_calls = 0
        self.update_calls = 0

    def query(self, _model):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        self.first_calls += 1
        return self._user

    def update(self, _values, synchronize_session=False):
        self.update_calls += 1
        if self._user is None:
            return 0
        self._user.requests_count = (self._user.requests_count or 0) + 1
        return 1

    def commit(self):
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_dispatch_sets_process_time_and_updates_usage(monkeypatch):
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "key-1"})
    seen = {}

    def _fake_update(req, api_key):
        seen["path"] = req.url.path
        seen["api_key"] = api_key

    monkeypatch.setattr(middleware, "_update_usage", _fake_update)

    async def call_next(_request: Request) -> Response:
        return Response(content="ok", media_type="text/plain")

    response = await middleware.dispatch(request, call_next)
    assert "X-Process-Time" in response.headers
    assert seen == {"path": "/api/v1/maas/meshes", "api_key": "key-1"}


@pytest.mark.asyncio
async def test_dispatch_skips_register_login_and_non_maas(monkeypatch):
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    called = {"count": 0}

    def _fake_update(_req, _api_key):
        called["count"] += 1

    monkeypatch.setattr(middleware, "_update_usage", _fake_update)

    async def call_next(_request: Request) -> Response:
        return Response(content="ok")

    await middleware.dispatch(
        _make_request(app, "/api/v1/maas/register", {"X-API-Key": "k"}),
        call_next,
    )
    await middleware.dispatch(
        _make_request(app, "/api/v1/maas/login", {"X-API-Key": "k"}),
        call_next,
    )
    await middleware.dispatch(
        _make_request(app, "/healthz", {"X-API-Key": "k"}),
        call_next,
    )
    await middleware.dispatch(
        _make_request(app, "/api/v1/maas/meshes"),
        call_next,
    )

    assert called["count"] == 0


@pytest.mark.asyncio
async def test_dispatch_swallows_update_exceptions(monkeypatch):
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    def _boom(_req, _api_key):
        raise RuntimeError("db is down")

    monkeypatch.setattr(middleware, "_update_usage", _boom)

    async def call_next(_request: Request) -> Response:
        return Response(content="ok")

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    assert "X-Process-Time" in response.headers


def test_update_usage_increments_and_commits_with_override_object_provider():
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    user = SimpleNamespace(requests_count=10)
    db = _DummyDB(user)
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    middleware._update_usage(request, "k")

    assert user.requests_count == 11
    assert db.update_calls == 1
    assert db.first_calls == 0
    assert db.committed is True
    assert db.closed is True


def test_update_usage_with_generator_provider_closes_generator():
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    user = SimpleNamespace(requests_count=1)
    db = _DummyDB(user)
    finalized = {"closed": False}

    def provider():
        try:
            yield db
        finally:
            finalized["closed"] = True

    app.dependency_overrides[mod.get_db] = provider
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    middleware._update_usage(request, "k")

    assert user.requests_count == 2
    assert db.update_calls == 1
    assert db.first_calls == 0
    assert db.committed is True
    assert finalized["closed"] is True


def test_update_usage_no_user_does_not_commit():
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    db = _DummyDB(None)
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    middleware._update_usage(request, "k")

    assert db.update_calls == 1
    assert db.first_calls == 0
    assert db.committed is False
    assert db.closed is True


def test_update_usage_handles_null_requests_count():
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    user = SimpleNamespace(requests_count=None)
    db = _DummyDB(user)
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    middleware._update_usage(request, "k")

    assert user.requests_count == 1
    assert db.update_calls == 1
    assert db.first_calls == 0
    assert db.committed is True
    assert db.rolled_back is False
    assert db.closed is True


def test_update_usage_rolls_back_and_reraises_on_commit_error():
    app = FastAPI()
    middleware = MeteringMiddleware(app=app)
    user = SimpleNamespace(requests_count=4)
    db = _DummyDB(user, commit_error=RuntimeError("commit failed"))
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(app, "/api/v1/maas/meshes", {"X-API-Key": "k"})

    with pytest.raises(RuntimeError, match="commit failed"):
        middleware._update_usage(request, "k")

    assert user.requests_count == 5
    assert db.update_calls == 1
    assert db.first_calls == 0
    assert db.committed is False
    assert db.rolled_back is True
    assert db.closed is True
