import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""Unit tests for src/core/request_validation.py"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import URL, Headers, QueryParams


# ---------------------------------------------------------------------------
# Helper to build a mock Starlette Request
# ---------------------------------------------------------------------------
def _make_request(
    method="GET",
    path="/api/test",
    headers=None,
    query_params=None,
    body=b"",
    url_str=None,
):
    """Create a mock starlette Request object."""
    request = MagicMock()
    request.method = method

    # Build URL
    if url_str is None:
        qs = ""
        if query_params:
            qs = "&".join(f"{k}={v}" for k, v in query_params.items())
            qs = "?" + qs
        url_str = f"http://localhost{path}{qs}"

    mock_url = MagicMock()
    mock_url.path = path
    mock_url.__str__ = lambda self: url_str
    mock_url.__len__ = lambda self: len(url_str)
    request.url = mock_url

    # Build headers
    raw_headers = headers or {}
    request.headers = Headers(raw_headers)

    # Build query params
    request.query_params = QueryParams(query_params or {})

    # Body as async
    async def _body():
        return body

    request.body = _body

    return request


# ---------------------------------------------------------------------------
# Tests for module-level functions
# ---------------------------------------------------------------------------


class TestIsSuspicious:
    """Tests for the is_suspicious() function."""

    def test_empty_string(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("") is False

    def test_none_value(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious(None) is False

    def test_clean_string(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("hello world") is False

    def test_sql_injection_union_select(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("1 UNION SELECT * FROM users") is True

    def test_sql_injection_comment_select(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("-- select name from users") is True

    def test_sql_injection_or_pattern(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("' or '1'='1") is True

    def test_nosql_injection_where(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("$where this.password") is True

    def test_nosql_injection_gt(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious('{"password": {"$gt": ""}}') is True

    def test_command_injection_semicolon(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("file; rm -rf /") is True

    def test_command_injection_pipe(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("data | cat /etc/passwd") is True

    def test_command_injection_backtick(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("`whoami`") is True

    def test_path_traversal(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("../../etc/passwd") is True

    def test_path_traversal_etc_shadow(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("/etc/shadow") is True

    def test_xss_script_tag(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("<script>alert('xss')</script>") is True

    def test_xss_javascript_proto(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("javascript:alert(1)") is True

    def test_xss_event_handler(self):
        from src.core.request_validation import is_suspicious

        assert is_suspicious("onerror = alert(1)") is True


class TestSanitizeString:
    """Tests for the sanitize_string() function."""

    def test_empty_string(self):
        from src.core.request_validation import sanitize_string

        assert sanitize_string("") == ""

    def test_none_value(self):
        from src.core.request_validation import sanitize_string

        assert sanitize_string(None) is None

    def test_truncation(self):
        from src.core.request_validation import sanitize_string

        result = sanitize_string("a" * 200, max_length=100)
        assert len(result) == 100

    def test_null_byte_removal(self):
        from src.core.request_validation import sanitize_string

        result = sanitize_string("hello\x00world")
        assert "\x00" not in result
        assert result == "hello world"

    def test_whitespace_normalization(self):
        from src.core.request_validation import sanitize_string

        result = sanitize_string("hello   \t  world")
        assert result == "hello world"

    def test_normal_string_unchanged(self):
        from src.core.request_validation import sanitize_string

        result = sanitize_string("normal text")
        assert result == "normal text"

    def test_default_max_length(self):
        from src.core.request_validation import sanitize_string

        long = "x" * 20000
        result = sanitize_string(long)
        assert len(result) == 10000


class TestSanitizeDict:
    """Tests for the sanitize_dict() function."""

    def test_empty_dict(self):
        from src.core.request_validation import sanitize_dict

        assert sanitize_dict({}) == {}

    def test_string_values_sanitized(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"key": "hello\x00world"})
        assert result["key"] == "hello world"

    def test_nested_dict(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"outer": {"inner": "text\x00here"}})
        assert result["outer"]["inner"] == "text here"

    def test_list_values_sanitized(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"items": ["hello\x00world", "clean"]})
        assert result["items"][0] == "hello world"
        assert result["items"][1] == "clean"

    def test_numeric_values_preserved(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"count": 42, "rate": 3.14})
        assert result["count"] == 42
        assert result["rate"] == 3.14

    def test_max_depth_returns_empty(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"key": "value"}, max_depth=10, current_depth=10)
        assert result == {}

    def test_key_sanitization(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"key\x00name": "value"})
        assert "key name" in result

    def test_list_size_limit(self):
        from src.core.request_validation import sanitize_dict

        big_list = list(range(2000))
        result = sanitize_dict({"items": big_list})
        assert len(result["items"]) == 1000

    def test_list_with_dict_items(self):
        from src.core.request_validation import sanitize_dict

        result = sanitize_dict({"items": [{"nested": "val\x00ue"}]})
        assert result["items"][0]["nested"] == "val ue"


class TestValidationConfig:
    """Tests for the ValidationConfig dataclass."""

    def test_defaults(self):
        from src.core.request_validation import ValidationConfig

        config = ValidationConfig()
        assert config.max_content_length == 10 * 1024 * 1024
        assert config.max_header_size == 8 * 1024
        assert config.max_url_length == 2048
        assert config.validate_content_type is True
        assert config.validate_content_length is True
        assert config.validate_headers is True
        assert config.sanitize_inputs is True
        assert config.block_suspicious_patterns is True

    def test_custom_values(self):
        from src.core.request_validation import ValidationConfig

        config = ValidationConfig(max_content_length=1024, max_url_length=512)
        assert config.max_content_length == 1024
        assert config.max_url_length == 512

    def test_allowed_content_types(self):
        from src.core.request_validation import ValidationConfig

        config = ValidationConfig()
        assert "application/json" in config.allowed_content_types
        assert "multipart/form-data" in config.allowed_content_types

    def test_body_methods(self):
        from src.core.request_validation import ValidationConfig

        config = ValidationConfig()
        assert "POST" in config.body_methods
        assert "PUT" in config.body_methods
        assert "PATCH" in config.body_methods
        assert "GET" not in config.body_methods

    def test_excluded_paths(self):
        from src.core.request_validation import ValidationConfig

        config = ValidationConfig()
        assert "/health" in config.excluded_paths
        assert "/metrics" in config.excluded_paths


class TestBlockedHeaders:
    """Tests for BLOCKED_HEADERS constant."""

    def test_blocked_headers_contains_expected(self):
        from src.core.request_validation import BLOCKED_HEADERS

        assert "x-forwarded-host" in BLOCKED_HEADERS
        assert "x-original-url" in BLOCKED_HEADERS
        assert "x-rewrite-url" in BLOCKED_HEADERS


# ---------------------------------------------------------------------------
# Tests for RequestValidationMiddleware
# ---------------------------------------------------------------------------


class TestRequestValidationMiddleware:
    """Tests for RequestValidationMiddleware async dispatch."""

    @pytest.mark.asyncio
    async def test_excluded_path_skips_validation(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        app = MagicMock()
        config = ValidationConfig()
        middleware = RequestValidationMiddleware(app, config=config)

        request = _make_request(path="/health")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_url_too_long_returns_414(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(max_url_length=50)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        long_path = "/api/" + "a" * 100
        request = _make_request(path=long_path, url_str="http://localhost" + long_path)
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 414
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_content_length_too_large_returns_413(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(max_content_length=100)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            method="POST",
            headers={"content-length": "999999"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 413
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_content_length_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig()
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(headers={"content-length": "not-a-number"})
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unsupported_content_type_returns_415(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig()
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            method="POST",
            headers={"content-type": "application/xml"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 415
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allowed_content_type_passes(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(
            validate_headers=False,
            block_suspicious_patterns=False,
        )
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_content_type_get_skips_validation(self):
        """GET requests should not be validated for content type."""
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(
            validate_headers=False,
            block_suspicious_patterns=False,
        )
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(method="GET")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blocked_header_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(block_suspicious_patterns=False)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            headers={"x-forwarded-host": "evil.com"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_headers_too_large_returns_431(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(max_header_size=10, block_suspicious_patterns=False)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            headers={"x-large-header": "x" * 100},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 431
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suspicious_path_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(validate_headers=False)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(path="/api/../../etc/passwd")
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suspicious_query_param_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(validate_headers=False)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            path="/api/search",
            query_params={"q": "<script>alert(1)</script>"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suspicious_header_value_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig()
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            headers={"x-custom": "<script>alert(1)</script>"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clean_request_passes(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(
            validate_headers=False,
            block_suspicious_patterns=False,
        )
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(path="/api/data")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_content_length_validation_disabled(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(
            validate_content_length=False,
            validate_content_type=False,
            validate_headers=False,
            block_suspicious_patterns=False,
        )
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            method="POST",
            headers={"content-length": "999999999"},
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_suspicious_query_key_returns_400(self):
        from src.core.request_validation import (RequestValidationMiddleware,
                                                 ValidationConfig)

        config = ValidationConfig(validate_headers=False)
        middleware = RequestValidationMiddleware(MagicMock(), config=config)

        request = _make_request(
            path="/api/search",
            query_params={"<script>": "value"},
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests for JSONSanitizationMiddleware
# ---------------------------------------------------------------------------


class TestJSONSanitizationMiddleware:
    """Tests for JSONSanitizationMiddleware async dispatch."""

    @pytest.mark.asyncio
    async def test_non_json_content_type_passes_through(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        request = _make_request(
            method="POST",
            headers={"content-type": "text/plain"},
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_method_passes_through(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        request = _make_request(
            method="GET",
            headers={"content-type": "application/json"},
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_body_too_large_returns_413(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock(), max_body_size=10)

        body = json.dumps({"data": "x" * 100}).encode()
        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=body,
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 413
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=b"{invalid json}}}",
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suspicious_json_value_returns_400(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        payload = {"username": "<script>alert('xss')</script>"}
        body = json.dumps(payload).encode()

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=body,
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clean_json_passes(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        payload = {"username": "gooduser", "email": "test@example.com"}
        body = json.dumps(payload).encode()

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=body,
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_body_passes(self):
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=b"",
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_dict_json_passes(self):
        """JSON arrays and primitives should pass through without sanitization."""
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        body = json.dumps([1, 2, 3]).encode()
        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
            body=body,
        )
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_body_read_exception_still_passes(self):
        """If reading body raises an exception, middleware should still pass."""
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        request = _make_request(
            method="POST",
            headers={"content-type": "application/json"},
        )

        # Override body to raise
        async def _raise_body():
            raise IOError("connection reset")

        request.body = _raise_body
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_put_method_validated(self):
        """PUT method should also be validated."""
        from src.core.request_validation import JSONSanitizationMiddleware

        middleware = JSONSanitizationMiddleware(MagicMock())

        payload = {"name": "<script>alert(1)</script>"}
        body = json.dumps(payload).encode()

        request = _make_request(
            method="PUT",
            headers={"content-type": "application/json"},
            body=body,
        )
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        call_next.assert_not_awaited()
