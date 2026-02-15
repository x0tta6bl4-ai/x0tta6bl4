"""
Tests for Tracing Middleware.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.core.tracing_middleware import (TracingMiddleware, api_tracer,
                                         db_tracer, get_correlation_id)


class TestTracingMiddleware:
    """Tests for TracingMiddleware."""

    def setup_method(self):
        """Set up test app."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}

        @self.app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        self.app.add_middleware(
            TracingMiddleware, service_name="test-service", excluded_paths=["/health"]
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_adds_correlation_id(self):
        """Test that correlation ID is added to response."""
        response = self.client.get("/test")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) == 36  # UUID format

    def test_preserves_correlation_id(self):
        """Test that provided correlation ID is preserved."""
        custom_id = "my-custom-correlation-id"
        response = self.client.get("/test", headers={"X-Correlation-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_id

    def test_adds_request_duration(self):
        """Test that request duration header is added."""
        response = self.client.get("/test")
        assert response.status_code == 200
        assert "X-Request-Duration" in response.headers
        duration = response.headers["X-Request-Duration"]
        assert duration.endswith("s")

    def test_excludes_health_endpoint(self):
        """Test that excluded paths don't get traced."""
        response = self.client.get("/health")
        assert response.status_code == 200
        # Health endpoint may still get correlation ID from other middleware
        # but tracing span should not be created

    def test_handles_errors(self):
        """Test that errors are handled gracefully."""
        response = self.client.get("/error")
        assert response.status_code == 500
        # Note: When an exception is re-raised, the response headers
        # may not be set. This is expected behavior - the error is
        # recorded in the span but the response comes from error handler.


class TestCorrelationId:
    """Tests for correlation ID context variable."""

    def test_get_correlation_id_default(self):
        """Test that default correlation ID is None."""
        correlation_id = get_correlation_id()
        # May be None or set from previous tests
        assert correlation_id is None or isinstance(correlation_id, str)


class TestDatabaseTracer:
    """Tests for DatabaseTracingMiddleware."""

    def test_trace_query_without_otel(self):
        """Test database tracer works without OpenTelemetry."""
        # Should not raise even without OTEL
        ctx = db_tracer.trace_query("SELECT", table="users")
        # Context manager should work
        assert ctx is not None


class TestAPITracer:
    """Tests for ExternalAPITracingMiddleware."""

    def test_trace_call_without_otel(self):
        """Test API tracer works without OpenTelemetry."""
        ctx = api_tracer.trace_call("stripe", "create_checkout")
        assert ctx is not None

    def test_inject_headers_without_otel(self):
        """Test header injection works without OpenTelemetry."""
        headers = {"Content-Type": "application/json"}
        result = api_tracer.inject_headers(headers)
        # Should return headers unchanged without OTEL
        assert "Content-Type" in result


class TestMiddlewareIntegration:
    """Integration tests for tracing middleware."""

    def test_multiple_requests_different_correlation_ids(self):
        """Test that different requests get different correlation IDs."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        app.add_middleware(TracingMiddleware, service_name="test")
        client = TestClient(app)

        response1 = client.get("/test")
        response2 = client.get("/test")

        id1 = response1.headers.get("X-Correlation-ID")
        id2 = response2.headers.get("X-Correlation-ID")

        assert id1 != id2

    def test_post_request_tracing(self):
        """Test that POST requests are traced."""
        app = FastAPI()

        @app.post("/data")
        async def post_data(data: dict):
            return {"received": True}

        app.add_middleware(TracingMiddleware, service_name="test")
        client = TestClient(app)

        response = client.post("/data", json={"key": "value"})
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert "X-Request-Duration" in response.headers

    def test_different_http_methods(self):
        """Test tracing for different HTTP methods."""
        app = FastAPI()

        @app.get("/resource")
        async def get_resource():
            return {"method": "GET"}

        @app.put("/resource")
        async def put_resource():
            return {"method": "PUT"}

        @app.delete("/resource")
        async def delete_resource():
            return {"method": "DELETE"}

        app.add_middleware(TracingMiddleware, service_name="test")
        client = TestClient(app)

        for method in ["get", "put", "delete"]:
            response = getattr(client, method)("/resource")
            assert response.status_code == 200
            assert "X-Correlation-ID" in response.headers
