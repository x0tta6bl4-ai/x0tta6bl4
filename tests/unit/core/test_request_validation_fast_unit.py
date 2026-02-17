"""Fast, branch-focused unit tests for request validation middleware."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import Headers, QueryParams
from starlette.responses import Response

from src.core import request_validation as mod


class _URL:
    def __init__(self, path: str, raw_url: str | None = None):
        self.path = path
        self._raw_url = raw_url or f"http://localhost{path}"

    def __str__(self):
        return self._raw_url


def _make_request(
    *,
    method: str = "GET",
    path: str = "/api/test",
    headers: dict | None = None,
    query_params: dict | None = None,
    body: bytes = b"",
    raw_url: str | None = None,
):
    request = MagicMock()
    request.method = method
    request.url = _URL(path=path, raw_url=raw_url)
    request.headers = Headers(headers or {})
    request.query_params = QueryParams(query_params or {})

    async def _body():
        return body

    request.body = _body
    return request


def test_module_level_helpers_and_defaults():
    assert mod.is_suspicious("hello") is False
    assert mod.is_suspicious("") is False
    assert mod.is_suspicious("UNION SELECT * FROM users") is True

    assert mod.sanitize_string("a\x00b   c") == "a b c"
    assert mod.sanitize_string("x" * 20, max_length=5) == "xxxxx"
    assert mod.sanitize_string("") == ""

    nested = {"a\x00": {"b": ["x\x00", {"c": " y  z "}, 7]}}
    cleaned = mod.sanitize_dict(nested, max_depth=5)
    assert "a" in cleaned
    assert cleaned["a"]["b"][0] == "x"
    assert cleaned["a"]["b"][1]["c"] == "y z"
    assert cleaned["a"]["b"][2] == 7

    too_deep = mod.sanitize_dict({"k": "v"}, max_depth=1, current_depth=1)
    assert too_deep == {}
    assert mod.sanitize_dict({"count": 3})["count"] == 3

    # Ensure module default config is initialized.
    assert mod.default_config.max_content_length > 0


@pytest.mark.asyncio
async def test_request_validation_dispatch_covers_major_branches():
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace())

    async def _ok(_request):
        return Response(status_code=200)

    # Excluded path
    response = await middleware.dispatch(_make_request(path="/health"), _ok)
    assert response.status_code == 200

    # URL too long
    short_cfg = mod.ValidationConfig(max_url_length=15)
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace(), config=short_cfg)
    response = await middleware.dispatch(
        _make_request(path="/api/a", raw_url="http://localhost/" + ("x" * 100)),
        _ok,
    )
    assert response.status_code == 414

    # Invalid content-length
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace())
    response = await middleware.dispatch(
        _make_request(method="POST", headers={"content-length": "bad"}),
        _ok,
    )
    assert response.status_code == 400

    # Too large payload
    cfg = mod.ValidationConfig(max_content_length=10)
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace(), config=cfg)
    response = await middleware.dispatch(
        _make_request(method="POST", headers={"content-length": "100"}),
        _ok,
    )
    assert response.status_code == 413

    # Unsupported media type
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace())
    response = await middleware.dispatch(
        _make_request(method="POST", headers={"content-type": "application/xml"}),
        _ok,
    )
    assert response.status_code == 415

    # Blocked header
    response = await middleware.dispatch(
        _make_request(headers={"x-forwarded-host": "evil.local"}),
        _ok,
    )
    assert response.status_code == 400

    # Suspicious header value
    response = await middleware.dispatch(
        _make_request(headers={"x-user": "<script>alert(1)</script>"}),
        _ok,
    )
    assert response.status_code == 400

    # Oversized headers
    cfg = mod.ValidationConfig(max_header_size=10, block_suspicious_patterns=False)
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace(), config=cfg)
    response = await middleware.dispatch(
        _make_request(headers={"x-large": "x" * 64}),
        _ok,
    )
    assert response.status_code == 431

    # Suspicious path/query
    cfg = mod.ValidationConfig(validate_headers=False)
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace(), config=cfg)
    response = await middleware.dispatch(
        _make_request(path="/api/../../etc/passwd"),
        _ok,
    )
    assert response.status_code == 400

    response = await middleware.dispatch(
        _make_request(path="/api/search", query_params={"q": "1; DROP TABLE users"}),
        _ok,
    )
    assert response.status_code == 400

    # Explicit header validation happy-path (returns None)
    validation_result = middleware._validate_headers(
        _make_request(headers={"x-good": "value"})
    )
    assert validation_result is None

    # Clean request reaches next handler
    cfg = mod.ValidationConfig(
        validate_headers=False,
        block_suspicious_patterns=False,
    )
    middleware = mod.RequestValidationMiddleware(app=SimpleNamespace(), config=cfg)
    call_next = AsyncMock(return_value=Response(status_code=204))
    response = await middleware.dispatch(
        _make_request(method="POST", headers={"content-type": "application/json"}),
        call_next,
    )
    assert response.status_code == 204
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_json_sanitization_dispatch_covers_branches():
    async def _ok(_request):
        return Response(status_code=200)

    middleware = mod.JSONSanitizationMiddleware(
        app=SimpleNamespace(), max_body_size=2048
    )

    # Non-JSON and non-body methods pass through.
    response = await middleware.dispatch(
        _make_request(method="POST", headers={"content-type": "text/plain"}),
        _ok,
    )
    assert response.status_code == 200

    response = await middleware.dispatch(
        _make_request(method="GET", headers={"content-type": "application/json"}),
        _ok,
    )
    assert response.status_code == 200

    # Body too large.
    middleware = mod.JSONSanitizationMiddleware(app=SimpleNamespace(), max_body_size=16)
    response = await middleware.dispatch(
        _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=json.dumps({"x": "y" * 200}).encode(),
        ),
        _ok,
    )
    assert response.status_code == 413

    middleware = mod.JSONSanitizationMiddleware(
        app=SimpleNamespace(), max_body_size=2048
    )

    # Invalid JSON.
    response = await middleware.dispatch(
        _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=b"{invalid",
        ),
        _ok,
    )
    assert response.status_code == 400

    # Suspicious sanitized JSON content.
    response = await middleware.dispatch(
        _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=json.dumps({"name": "<script>alert(1)</script>"}).encode(),
        ),
        _ok,
    )
    assert response.status_code == 400

    # Non-dict JSON should pass.
    response = await middleware.dispatch(
        _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=json.dumps([1, 2, 3]).encode(),
        ),
        _ok,
    )
    assert response.status_code == 200

    # Empty body should pass.
    response = await middleware.dispatch(
        _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=b"",
        ),
        _ok,
    )
    assert response.status_code == 200

    # Body-read error should be swallowed and request continues.
    request = _make_request(
        method="POST",
        headers={"content-type": "application/json"},
    )

    async def _raise_body():
        raise IOError("stream broken")

    request.body = _raise_body
    response = await middleware.dispatch(request, _ok)
    assert response.status_code == 200
