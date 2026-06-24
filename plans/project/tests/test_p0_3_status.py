"""
Tests for P0#3 - /status endpoint with real system metrics
"""

import pytest
from fastapi.testclient import TestClient
from src.core.app import app
from src.core.status_collector import get_current_status, SystemMetricsCollector, MeshNetworkMetrics


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


class TestStatusEndpoint:
    """Tests for /status endpoint with real metrics"""
    
    def test_status_endpoint_returns_200(self, client):
        """Test that /status returns 200 OK"""
        response = client.get("/status")
        assert response.status_code == 200
    
    def test_status_has_required_fields(self, client):
        """Test that /status has all required fields"""
        response = client.get("/status")
        data = response.json()
        
        # Required top-level fields
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "system" in data
        assert "mesh" in data
        assert "loop" in data
        assert "health" in data
    
    def test_status_health_values(self, client):
        """Test that status is one of valid values"""
        response = client.get("/status")
        data = response.json()
        
        assert data["status"] in ["healthy", "warning", "critical"]
        assert data["version"] == "3.1.0"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0
    
    def test_status_system_metrics(self, client):
        """Test that system metrics are present and valid"""
        response = client.get("/status")
        data = response.json()
        system = data["system"]
        
        # CPU metrics
        assert "cpu" in system
        assert "percent" in system["cpu"]
        assert "cores" in system["cpu"]
        assert "per_cpu" in system["cpu"]
        assert 0 <= system["cpu"]["percent"] <= 100
        assert system["cpu"]["cores"] > 0
        
        # Memory metrics
        assert "memory" in system
        assert "total_mb" in system["memory"]
        assert "used_mb" in system["memory"]
        assert "available_mb" in system["memory"]
        assert "percent" in system["memory"]
        assert system["memory"]["total_mb"] > 0
        assert 0 <= system["memory"]["percent"] <= 100
        
        # Disk metrics
        assert "disk" in system
        assert "total_gb" in system["disk"]
        assert "used_gb" in system["disk"]
        assert "free_gb" in system["disk"]
        assert "percent" in system["disk"]
        assert system["disk"]["total_gb"] > 0
        assert 0 <= system["disk"]["percent"] <= 100
        
        # Network metrics
        assert "network" in system
        assert "bytes_sent" in system["network"]
        assert "bytes_recv" in system["network"]
        assert "packets_in_per_sec" in system["network"]
        assert "packets_out_per_sec" in system["network"]
        assert "packet_loss_percent" in system["network"]
    
    def test_status_mesh_metrics(self, client):
        """Test that mesh network metrics are present"""
        response = client.get("/status")
        data = response.json()
        mesh = data["mesh"]
        
        assert "total_peers" in mesh
        assert "connected_peers" in mesh
        assert "bandwidth_limit_mbps" in mesh
        assert isinstance(mesh["total_peers"], int)
        assert isinstance(mesh["connected_peers"], int)
    
    def test_status_loop_state(self, client):
        """Test that MAPE-K loop state is present"""
        response = client.get("/status")
        data = response.json()
        loop = data["loop"]
        
        assert "running" in loop
        assert "current_phase" in loop
        assert "iterations" in loop
        assert "last_cycle_time_ms" in loop
        assert isinstance(loop["running"], bool)
        assert isinstance(loop["iterations"], int)
    
    def test_status_health_checks(self, client):
        """Test that health component checks are present"""
        response = client.get("/status")
        data = response.json()
        health = data["health"]
        
        assert "cpu_ok" in health
        assert "memory_ok" in health
        assert "disk_ok" in health
        assert "network_ok" in health
        assert "mesh_connected" in health
        
        # All should be boolean
        assert isinstance(health["cpu_ok"], bool)
        assert isinstance(health["memory_ok"], bool)
        assert isinstance(health["disk_ok"], bool)
        assert isinstance(health["network_ok"], bool)
        assert isinstance(health["mesh_connected"], bool)
    
    def test_status_timestamp_is_iso_format(self, client):
        """Test that timestamp is valid ISO format"""
        response = client.get("/status")
        data = response.json()
        
        # Should be parseable as datetime
        from datetime import datetime
        timestamp = data["timestamp"]
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            pytest.fail(f"Timestamp {timestamp} is not ISO format")


class TestStatusCollector:
    """Tests for SystemMetricsCollector and StatusData"""
    
    def test_system_metrics_collector_cpu(self):
        """Test CPU metrics collection"""
        collector = SystemMetricsCollector()
        cpu = collector.get_cpu_metrics()
        
        assert "percent" in cpu
        assert "cores" in cpu
        assert "per_cpu" in cpu
        assert 0 <= cpu["percent"] <= 100
        assert cpu["cores"] > 0
    
    def test_system_metrics_collector_memory(self):
        """Test memory metrics collection"""
        collector = SystemMetricsCollector()
        mem = collector.get_memory_metrics()
        
        assert "total_mb" in mem
        assert "used_mb" in mem
        assert "available_mb" in mem
        assert "percent" in mem
        assert mem["total_mb"] > 0
        assert 0 <= mem["percent"] <= 100
    
    def test_system_metrics_collector_disk(self):
        """Test disk metrics collection"""
        collector = SystemMetricsCollector()
        disk = collector.get_disk_metrics()
        
        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "percent" in disk
        assert disk["total_gb"] > 0
    
    def test_system_metrics_collector_network(self):
        """Test network metrics collection"""
        collector = SystemMetricsCollector()
        net = collector.get_network_metrics()
        
        assert "bytes_sent" in net
        assert "bytes_recv" in net
        assert "packets_in_per_sec" in net
        assert "packets_out_per_sec" in net
        assert "packet_loss_percent" in net
    
    def test_mesh_network_metrics(self):
        """Test mesh network metrics"""
        mesh = MeshNetworkMetrics()
        mesh.update_from_batman_adv()
        
        metrics = mesh.get_metrics()
        assert "total_peers" in metrics
        assert "connected_peers" in metrics
        assert "bandwidth_limit_mbps" in metrics
        assert isinstance(metrics["total_peers"], int)
    
    def test_get_current_status(self):
        """Test getting current status"""
        status = get_current_status()
        
        assert "status" in status
        assert "version" in status
        assert "system" in status
        assert status["version"] == "3.1.0"
        assert status["status"] in ["healthy", "warning", "critical"]
