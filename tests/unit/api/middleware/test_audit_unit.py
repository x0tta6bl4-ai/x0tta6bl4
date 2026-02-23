"""Unit tests for src/api/middleware/audit.py."""

from types import SimpleNamespace
from typing import Any, Dict, Optional

from fastapi import FastAPI, Response
from starlette.requests import Request

from src.api.middleware import audit as mod
from src.api.middleware.audit import AuditMiddleware
from src.database import Session as UserSession
from src.database import User


def _make_request(
    app: FastAPI,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
) -> Request:
    raw_headers = []
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))

    scope: Dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
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


class _DummyQuery:
    def __init__(self, first_result: object):
        self._first_result = first_result
        self.filter_calls = 0
        self.first_calls = 0

    def filter(self, *_args, **_kwargs):
        self.filter_calls += 1
        return self

    def first(self):
        self.first_calls += 1
        return self._first_result


class _DummyDB:
    def __init__(self, user_result: object = None, session_result: object = None):
        self.user_query = _DummyQuery(user_result)
        self.session_query = _DummyQuery(session_result)
        self.added = []
        self.commits = 0
        self.closed = False

    def query(self, model):
        if model is User:
            return self.user_query
        if model is UserSession:
            return self.session_query
        raise AssertionError(f"Unexpected model in query(): {model}")

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_log_audit_caches_api_key_identity():
    app = FastAPI()
    middleware = AuditMiddleware(app=app)
    db = _DummyDB(user_result=SimpleNamespace(id="user-1"))
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(app, "/api/v1/maas/dashboard/summary", {"X-API-Key": "key-1"})
    response = Response(status_code=200)

    middleware._log_audit(request, response, payload=None)
    middleware._log_audit(request, response, payload=None)

    assert db.user_query.first_calls == 1
    assert db.session_query.first_calls == 0
    assert db.commits == 2
    assert len(db.added) == 2
    assert db.added[0].user_id == "user-1"
    assert db.added[1].user_id == "user-1"


def test_log_audit_caches_bearer_session_identity():
    app = FastAPI()
    middleware = AuditMiddleware(app=app)
    db = _DummyDB(
        user_result=None,
        session_result=SimpleNamespace(user_id="session-user-1"),
    )
    app.dependency_overrides[mod.get_db] = lambda: db
    request = _make_request(
        app,
        "/api/v1/maas/analytics/mesh-1/summary",
        {"Authorization": "Bearer session-token-1"},
    )
    response = Response(status_code=200)

    middleware._log_audit(request, response, payload=None)
    middleware._log_audit(request, response, payload=None)

    assert db.user_query.first_calls == 0
    assert db.session_query.first_calls == 1
    assert db.commits == 2
    assert len(db.added) == 2
    assert db.added[0].user_id == "session-user-1"
    assert db.added[1].user_id == "session-user-1"
