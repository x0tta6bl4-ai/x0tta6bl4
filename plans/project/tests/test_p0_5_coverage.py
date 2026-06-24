"""
Extended test coverage for P0#5 - reaching 75% coverage target

Tests for core components:
- Settings module
- Status collector
- mTLS middleware
- API endpoints
- Database layer
"""

import pytest
from fastapi.testclient import TestClient
from src.core.app import app
from src.core.settings import settings
from src.core.status_collector import StatusData, SystemMetricsCollector, MeshNetworkMetrics
from src.database import SessionLocal
import os


class TestSettingsModule:
    """Comprehensive tests for settings configuration"""
    
    def test_settings_load_from_environment(self):
        """Test settings load from environment"""
        assert settings is not None
        assert hasattr(settings, "database_url")
        assert hasattr(settings, "environment")
    
    def test_settings_default_values(self):
        """Test default settings values"""
        assert settings.api_port == 8000
        assert settings.api_host == "0.0.0.0"
        assert settings.log_level == "INFO"
    
    def test_settings_development_mode(self):
        """Test development mode detection"""
        assert settings.is_development() or settings.is_production()
    
    def test_settings_has_database_url(self):
        """Test that database URL is configured"""
        assert settings.database_url is not None
        assert len(settings.database_url) > 0


class TestAPIEndpoints:
    """Comprehensive tests for API endpoints"""
    
    def test_health_endpoint_200(self):
        """Test health endpoint returns 200"""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_endpoint_response_format(self):
        """Test health endpoint response format"""
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert data["status"] == "ok"
        assert data["version"] == "3.1.0"
    
    def test_root_endpoint_documentation(self):
        """Test root endpoint has documentation links"""
        client = TestClient(app)
        response = client.get("/")
        data = response.json()
        
        assert "docs" in data
        assert "name" in data
        assert data["name"] == "x0tta6bl4"
    
    def test_status_endpoint_has_all_required_fields(self):
        """Test status endpoint completeness"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        required_fields = ["status", "version", "timestamp", "uptime_seconds", "system", "mesh", "loop", "health"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_status_system_cpu_metrics(self):
        """Test status endpoint CPU metrics"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        cpu = data["system"]["cpu"]
        assert "percent" in cpu
        assert "cores" in cpu
        assert 0 <= cpu["percent"] <= 100
        assert cpu["cores"] > 0
    
    def test_status_system_memory_metrics(self):
        """Test status endpoint memory metrics"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        mem = data["system"]["memory"]
        assert "total_mb" in mem
        assert "used_mb" in mem
        assert "percent" in mem
        assert mem["total_mb"] > 0
        assert 0 <= mem["percent"] <= 100
    
    def test_status_system_disk_metrics(self):
        """Test status endpoint disk metrics"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        disk = data["system"]["disk"]
        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "percent" in disk
        assert disk["total_gb"] > 0
    
    def test_status_network_metrics(self):
        """Test status endpoint network metrics"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        net = data["system"]["network"]
        assert "bytes_sent" in net
        assert "bytes_recv" in net
        assert "packet_loss_percent" in net
    
    def test_status_mesh_metrics(self):
        """Test status endpoint mesh metrics"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        mesh = data["mesh"]
        assert "total_peers" in mesh
        assert "connected_peers" in mesh
        assert isinstance(mesh["total_peers"], int)
    
    def test_status_loop_state(self):
        """Test status endpoint MAPE-K loop state"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        loop = data["loop"]
        assert "running" in loop
        assert "iterations" in loop
        assert isinstance(loop["running"], bool)
    
    def test_status_health_checks(self):
        """Test status endpoint health component checks"""
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        
        health = data["health"]
        checks = ["cpu_ok", "memory_ok", "disk_ok", "network_ok", "mesh_connected"]
        for check in checks:
            assert check in health
            assert isinstance(health[check], bool)


class TestStatusCollectorComprehensive:
    """Comprehensive tests for status collector"""
    
    def test_status_data_initialization(self):
        """Test StatusData initialization"""
        status_data = StatusData()
        
        assert hasattr(status_data, "system_metrics")
        assert hasattr(status_data, "mesh_metrics")
        assert hasattr(status_data, "loop_state")
    
    def test_system_metrics_collector_all_metrics(self):
        """Test all system metrics are collected"""
        collector = SystemMetricsCollector()
        
        assert collector.get_cpu_metrics() is not None
        assert collector.get_memory_metrics() is not None
        assert collector.get_disk_metrics() is not None
        assert collector.get_network_metrics() is not None
    
    def test_mesh_network_metrics_initialization(self):
        """Test mesh network metrics"""
        mesh = MeshNetworkMetrics()
        
        assert mesh.peer_count >= 0
        assert mesh.connected_peers >= 0
        assert mesh.bandwidth_limit_mbps >= 0
    
    def test_status_health_determination_healthy(self):
        """Test status health determination for healthy system"""
        status = StatusData()
        status_data = status.get_status()
        
        # Should return one of the valid statuses
        assert status_data["status"] in ["healthy", "warning", "critical"]
    
    def test_status_uptime_tracking(self):
        """Test status uptime tracking"""
        status = StatusData()
        status_data = status.get_status()
        
        assert status_data["uptime_seconds"] >= 0


class TestDatabaseLayer:
    """Basic tests for database layer"""
    
    def test_database_url_configured(self):
        """Test that database URL is configured"""
        assert settings.database_url is not None
        assert len(settings.database_url) > 0
    
    def test_database_session_local_available(self):
        """Test that SessionLocal is available"""
        assert SessionLocal is not None


class TestSecurityHeaders:
    """Tests for security headers"""
    
    def test_csp_header_present(self):
        """Test Content-Security-Policy header"""
        client = TestClient(app)
        response = client.get("/")
        
        assert "Content-Security-Policy" in response.headers
    
    def test_x_content_type_options_header(self):
        """Test X-Content-Type-Options header"""
        client = TestClient(app)
        response = client.get("/")
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    
    def test_x_frame_options_header(self):
        """Test X-Frame-Options header"""
        client = TestClient(app)
        response = client.get("/")
        
        assert "X-Frame-Options" in response.headers
    
    def test_hsts_header_present(self):
        """Test HSTS header"""
        client = TestClient(app)
        response = client.get("/")
        
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
    
    def test_all_endpoints_have_security_headers(self):
        """Test that all endpoints have security headers"""
        client = TestClient(app)
        
        endpoints = ["/", "/health", "/status"]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert "Strict-Transport-Security" in response.headers


class TestErrorHandling:
    """Tests for error handling"""
    
    def test_404_not_found(self):
        """Test 404 response for unknown endpoint"""
        client = TestClient(app)
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test 405 for wrong HTTP method"""
        client = TestClient(app)
        response = client.post("/health")
        
        assert response.status_code == 405


class TestEnvironmentVariables:
    """Tests for environment variable handling"""
    
    def test_mtls_disabled_by_default(self):
        """Test that mTLS is disabled by default"""
        # Check if MTLS_ENABLED is false by default
        mtls_enabled = os.getenv("MTLS_ENABLED", "false").lower() == "true"
        assert mtls_enabled is False
    
    def test_settings_from_environment(self):
        """Test settings are loaded from environment"""
        assert settings is not None
        assert settings.environment in ["development", "testing", "production"]
