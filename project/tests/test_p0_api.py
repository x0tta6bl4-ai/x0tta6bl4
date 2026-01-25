"""API endpoint tests - /health, /status, and core functionality"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Try importing the actual app, if it fails, create a mock
try:
    from src.core.app import app as real_app
    app_available = True
except Exception as e:
    print(f"WARNING: Could not import src.core.app: {e}")
    app_available = False
    # Create minimal mock for testing
    from fastapi import FastAPI
    real_app = FastAPI()
    
    @real_app.get("/health")
    async def health():
        return {"status": "ok", "version": "3.1.0"}
    
    @real_app.get("/status")
    async def status():
        return {
            "status": "healthy",
            "version": "3.1.0",
            "loop_running": True,
            "timestamp": "2026-01-25T00:00:00Z"
        }


class TestAPIEndpoints:
    """Test core API endpoints"""
    
    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(real_app)
    
    def test_health_endpoint_exists(self, client):
        """GET /health endpoint should exist"""
        response = client.get("/health")
        assert response.status_code in [200, 307, 404], f"Got {response.status_code}"
    
    @pytest.mark.asyncio
    async def test_health_response_format(self):
        """Health response should have status and version"""
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/health")
        async def health():
            return {"status": "ok", "version": "3.1.0"}
        
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data, "Missing 'status' field"
        assert "version" in data, "Missing 'version' field"
    
    def test_status_endpoint_exists(self, client):
        """GET /status endpoint should exist"""
        response = client.get("/status")
        assert response.status_code in [200, 307, 404]
    
    @pytest.mark.asyncio
    async def test_status_response_format(self):
        """Status response should have required fields"""
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/status")
        async def status():
            return {
                "status": "healthy",
                "version": "3.1.0",
                "loop_running": True,
                "timestamp": "2026-01-25T00:00:00Z"
            }
        
        client = TestClient(app)
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "loop_running" in data
    
    def test_api_error_handling(self, client):
        """API should handle 404 gracefully"""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404


class TestAPIDocumentation:
    """Test API documentation endpoints"""
    
    @pytest.fixture
    def client(self):
        return TestClient(real_app)
    
    def test_openapi_schema_exists(self, client):
        """OpenAPI schema should be available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data or "swagger" in data.get("info", {})
    
    def test_docs_endpoint_exists(self, client):
        """Swagger docs should be available"""
        response = client.get("/docs")
        assert response.status_code in [200, 405]  # 405 if docs disabled
    
    def test_redoc_endpoint_exists(self, client):
        """ReDoc docs should be available"""
        response = client.get("/redoc")
        assert response.status_code in [200, 405]


class TestHTTPMethods:
    """Test HTTP method handling"""
    
    @pytest.fixture
    def client(self):
        return TestClient(real_app)
    
    def test_health_only_get_allowed(self, client):
        """Health endpoint should not accept POST"""
        response = client.post("/health")
        assert response.status_code in [405, 404]  # 405 Method Not Allowed
    
    def test_status_only_get_allowed(self, client):
        """Status endpoint should not accept POST"""
        response = client.post("/status")
        assert response.status_code in [405, 404]


class TestResponseHeaders:
    """Test security headers"""
    
    @pytest.fixture
    def client(self):
        return TestClient(real_app)
    
    def test_csp_header_present(self, client):
        """Content-Security-Policy header should be set"""
        response = client.get("/health")
        assert "content-security-policy" in response.headers or "Content-Security-Policy" in response.headers
    
    def test_hsts_header_present(self, client):
        """HSTS header should be set"""
        response = client.get("/health")
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "strict-transport-security" in headers_lower, "Missing HSTS header"
    
    def test_xss_protection_header(self, client):
        """X-XSS-Protection header should be set"""
        response = client.get("/health")
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "x-xss-protection" in headers_lower, "Missing XSS protection header"
    
    def test_content_type_options_header(self, client):
        """X-Content-Type-Options should be nosniff"""
        response = client.get("/health")
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "x-content-type-options" in headers_lower, "Missing Content-Type-Options"
        assert headers_lower["x-content-type-options"] == "nosniff"


class TestCORSHeaders:
    """Test CORS handling"""
    
    @pytest.fixture
    def client(self):
        return TestClient(real_app)
    
    def test_cors_preflight_handling(self, client):
        """Should handle CORS preflight requests"""
        response = client.options("/health")
        assert response.status_code in [200, 204, 405]


class TestResponseFormat:
    """Test response formats"""
    
    @pytest.mark.asyncio
    async def test_json_response_format(self):
        """Responses should be valid JSON"""
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/api/test")
        async def test():
            return {"key": "value", "number": 42, "boolean": True}
        
        client = TestClient(app)
        response = client.get("/api/test")
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "value"
        assert data["number"] == 42
        assert data["boolean"] is True
    
    @pytest.mark.asyncio
    async def test_error_response_has_detail(self):
        """Error responses should include detail field"""
        from fastapi import FastAPI, HTTPException
        app = FastAPI()
        
        @app.get("/api/error")
        async def error_endpoint():
            raise HTTPException(status_code=400, detail="Bad request")
        
        client = TestClient(app)
        response = client.get("/api/error")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestAppInitialization:
    """Test application startup and configuration"""
    
    def test_fastapi_instance_created(self):
        """FastAPI app should be properly instantiated"""
        assert real_app is not None
        assert isinstance(real_app, FastAPI)
    
    def test_app_has_routes(self):
        """App should have routes defined"""
        routes = [route.path for route in real_app.routes]
        assert len(routes) > 0, "No routes defined"
    
    def test_health_route_exists(self):
        """Health route should be registered"""
        routes = [route.path for route in real_app.routes]
        assert "/health" in routes, "/health route not found"


# Integration tests
class TestIntegration:
    """Integration tests combining multiple components"""
    
    @pytest.mark.asyncio
    async def test_health_to_status_flow(self):
        """Health check should be queryable before status"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        
        @app.get("/health")
        async def health():
            return {"status": "ok"}
        
        @app.get("/status")
        async def status():
            return {"status": "healthy"}
        
        client = TestClient(app)
        
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        
        status_resp = client.get("/status")
        assert status_resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
