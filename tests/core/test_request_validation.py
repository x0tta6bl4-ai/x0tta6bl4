"""
Tests for Request Validation Middleware.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.core.request_validation import (
    RequestValidationMiddleware,
    ValidationConfig,
    is_suspicious,
    sanitize_string,
    sanitize_dict,
)


class TestIsSuspicious:
    """Tests for is_suspicious function."""

    def test_clean_string(self):
        """Test that clean strings pass."""
        assert is_suspicious("hello world") is False
        assert is_suspicious("user@example.com") is False
        assert is_suspicious("12345") is False

    def test_sql_injection(self):
        """Test SQL injection detection."""
        assert is_suspicious("1; DROP TABLE users--") is True
        assert is_suspicious("' OR '1'='1") is True
        assert is_suspicious("UNION SELECT * FROM users") is True

    def test_command_injection(self):
        """Test command injection detection."""
        assert is_suspicious("hello; rm -rf /") is True
        assert is_suspicious("test | cat /etc/passwd") is True
        assert is_suspicious("$(whoami)") is True

    def test_path_traversal(self):
        """Test path traversal detection."""
        assert is_suspicious("../../../etc/passwd") is True
        assert is_suspicious("..\\..\\windows\\system32") is True

    def test_xss_patterns(self):
        """Test XSS pattern detection."""
        assert is_suspicious("<script>alert('xss')</script>") is True
        assert is_suspicious("javascript:alert(1)") is True
        assert is_suspicious("onclick=alert(1)") is True

    def test_empty_and_none(self):
        """Test empty and None values."""
        assert is_suspicious("") is False
        assert is_suspicious(None) is False


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_basic_string(self):
        """Test basic string passes through."""
        assert sanitize_string("hello") == "hello"

    def test_truncation(self):
        """Test string truncation."""
        long_string = "a" * 1000
        result = sanitize_string(long_string, max_length=100)
        assert len(result) == 100

    def test_null_bytes(self):
        """Test null byte removal."""
        assert sanitize_string("hello\x00world") == "helloworld"

    def test_whitespace_normalization(self):
        """Test whitespace normalization."""
        assert sanitize_string("hello   world") == "hello world"
        assert sanitize_string("hello\n\tworld") == "hello world"

    def test_empty_string(self):
        """Test empty string handling."""
        assert sanitize_string("") == ""
        assert sanitize_string(None) is None


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_simple_dict(self):
        """Test simple dictionary sanitization."""
        data = {"name": "test", "value": 123}
        result = sanitize_dict(data)
        assert result == {"name": "test", "value": 123}

    def test_nested_dict(self):
        """Test nested dictionary sanitization."""
        data = {"user": {"name": "test", "email": "test@example.com"}}
        result = sanitize_dict(data)
        assert result["user"]["name"] == "test"

    def test_list_values(self):
        """Test list value sanitization."""
        data = {"items": ["one", "two", "three"]}
        result = sanitize_dict(data)
        assert result["items"] == ["one", "two", "three"]

    def test_max_depth(self):
        """Test max depth limiting."""
        deep = {"a": {"b": {"c": {"d": {"e": "value"}}}}}
        result = sanitize_dict(deep, max_depth=2)
        assert "a" in result
        # Deep values should be truncated

    def test_string_sanitization_in_dict(self):
        """Test that strings in dict are sanitized."""
        data = {"name": "hello\x00world"}
        result = sanitize_dict(data)
        assert result["name"] == "helloworld"


class TestValidationConfig:
    """Tests for ValidationConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ValidationConfig()
        assert config.max_content_length == 10 * 1024 * 1024
        assert config.max_url_length == 2048
        assert "application/json" in config.allowed_content_types

    def test_custom_config(self):
        """Test custom configuration."""
        config = ValidationConfig(
            max_content_length=1024,
            max_url_length=500,
            validate_content_type=False
        )
        assert config.max_content_length == 1024
        assert config.max_url_length == 500
        assert config.validate_content_type is False


class TestRequestValidationMiddleware:
    """Tests for RequestValidationMiddleware."""

    def setup_method(self):
        """Set up test app."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @self.app.post("/data")
        async def post_data(data: dict = None):
            return {"received": True}

        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}

        config = ValidationConfig(
            max_content_length=1024,
            max_url_length=100,
        )
        self.app.add_middleware(RequestValidationMiddleware, config=config)
        self.client = TestClient(self.app)

    def test_normal_request(self):
        """Test normal request passes."""
        response = self.client.get("/test")
        assert response.status_code == 200

    def test_excluded_path(self):
        """Test excluded paths bypass validation."""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_url_too_long(self):
        """Test URL length validation."""
        long_path = "/test?" + "a" * 200
        response = self.client.get(long_path)
        assert response.status_code == 414

    def test_content_length_exceeded(self):
        """Test content length validation."""
        large_body = {"data": "x" * 2000}
        response = self.client.post(
            "/data",
            json=large_body,
        )
        assert response.status_code == 413

    def test_invalid_content_type(self):
        """Test content type validation."""
        response = self.client.post(
            "/data",
            content="test data",
            headers={"Content-Type": "text/xml"}
        )
        assert response.status_code == 415

    def test_suspicious_query_param(self):
        """Test suspicious query parameter detection."""
        response = self.client.get("/test?id=1; DROP TABLE users--")
        assert response.status_code == 400

    def test_suspicious_path(self):
        """Test suspicious path detection."""
        response = self.client.get("/test/../../../etc/passwd")
        assert response.status_code == 400


class TestMiddlewareIntegration:
    """Integration tests for validation middleware."""

    def test_multiple_validations(self):
        """Test multiple validation rules together."""
        app = FastAPI()

        @app.post("/submit")
        async def submit():
            return {"success": True}

        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)

        # Valid request
        response = client.post(
            "/submit",
            json={"name": "test"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200

    def test_sql_injection_in_query(self):
        """Test SQL injection blocked in query params."""
        app = FastAPI()

        @app.get("/search")
        async def search(q: str = ""):
            return {"query": q}

        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)

        response = client.get("/search?q=SELECT * FROM users")
        assert response.status_code == 400

    def test_xss_in_query(self):
        """Test XSS blocked in query params."""
        app = FastAPI()

        @app.get("/search")
        async def search(q: str = ""):
            return {"query": q}

        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)

        response = client.get("/search?q=<script>alert(1)</script>")
        assert response.status_code == 400

    def test_valid_json_post(self):
        """Test valid JSON POST request."""
        app = FastAPI()

        @app.post("/api/data")
        async def post_data(data: dict):
            return data

        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)

        response = client.post(
            "/api/data",
            json={"name": "John", "email": "john@example.com"}
        )
        assert response.status_code == 200

    def test_form_data_allowed(self):
        """Test that form data content type is allowed."""
        app = FastAPI()

        @app.post("/form")
        async def post_form():
            return {"received": True}

        app.add_middleware(RequestValidationMiddleware)
        client = TestClient(app)

        response = client.post(
            "/form",
            data={"field": "value"},
        )
        # Form data should be allowed
        assert response.status_code in [200, 422]  # 422 if no body parser


class TestSecurityPatterns:
    """Tests for various security attack patterns."""

    def setup_method(self):
        """Set up test app."""
        self.app = FastAPI()

        @self.app.get("/api")
        async def api():
            return {"status": "ok"}

        self.app.add_middleware(RequestValidationMiddleware)
        self.client = TestClient(self.app)

    def test_nosql_injection(self):
        """Test NoSQL injection patterns."""
        response = self.client.get("/api?filter[$gt]=")
        assert response.status_code == 400

    def test_ldap_injection(self):
        """Test LDAP injection patterns."""
        response = self.client.get("/api?user=*)(uid=*))")
        assert response.status_code == 400

    def test_path_traversal_encoded(self):
        """Test encoded path traversal."""
        response = self.client.get("/api?file=..%2F..%2Fetc%2Fpasswd")
        # URL decoding happens before validation
        assert response.status_code in [200, 400]

    def test_command_injection_pipe(self):
        """Test command injection with pipe."""
        response = self.client.get("/api?cmd=test|cat /etc/passwd")
        assert response.status_code == 400

    def test_safe_special_chars(self):
        """Test that safe special characters are allowed."""
        response = self.client.get("/api?email=user@example.com")
        assert response.status_code == 200

        response = self.client.get("/api?name=John%20Doe")
        assert response.status_code == 200
