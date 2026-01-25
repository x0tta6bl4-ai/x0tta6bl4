"""
Unit tests for Node Manager Service.

Tests node management, health checks, and service lifecycle.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List

try:
    from src.services.node_manager_service import (
        NodeManagerService,
        NodeStatus,
        ServiceConfig
    )
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False
    NodeManagerService = None
    NodeStatus = None
    ServiceConfig = None


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Node Manager Service not available")
class TestNodeManagerService:
    """Tests for Node Manager Service"""
    
    def test_service_initialization(self):
        """Test service initialization"""
        config = ServiceConfig(
            node_id="test-node",
            port=8080,
            health_check_interval=5.0
        )
        
        service = NodeManagerService(config)
        
        assert service.node_id == "test-node"
        assert service.port == 8080
        assert service.status == NodeStatus.STOPPED
    
    def test_service_start(self):
        """Test service start"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        with patch.object(service, '_start_server', return_value=None):
            service.start()
            assert service.status == NodeStatus.RUNNING
    
    def test_service_stop(self):
        """Test service stop"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        service.status = NodeStatus.RUNNING
        
        with patch.object(service, '_stop_server', return_value=None):
            service.stop()
            assert service.status == NodeStatus.STOPPED
    
    def test_health_check(self):
        """Test health check"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        service.status = NodeStatus.RUNNING
        
        health = service.check_health()
        
        assert health is not None
        assert "status" in health
        assert health["status"] == "healthy" or health["status"] == "unhealthy"
    
    def test_node_registration(self):
        """Test node registration"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        peer_node = {
            "node_id": "peer-1",
            "address": "192.168.1.2",
            "port": 8081
        }
        
        service.register_node(peer_node["node_id"], peer_node["address"], peer_node["port"])
        
        assert peer_node["node_id"] in service.registered_nodes
    
    def test_node_unregistration(self):
        """Test node unregistration"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        # Register node
        service.register_node("peer-1", "192.168.1.2", 8081)
        assert "peer-1" in service.registered_nodes
        
        # Unregister
        service.unregister_node("peer-1")
        assert "peer-1" not in service.registered_nodes
    
    def test_get_registered_nodes(self):
        """Test getting registered nodes"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        # Register multiple nodes
        service.register_node("peer-1", "192.168.1.2", 8081)
        service.register_node("peer-2", "192.168.1.3", 8082)
        
        nodes = service.get_registered_nodes()
        
        assert len(nodes) == 2
        assert "peer-1" in nodes
        assert "peer-2" in nodes
    
    def test_service_config_validation(self):
        """Test service config validation"""
        # Valid config
        config = ServiceConfig(node_id="test-node", port=8080)
        assert config.node_id == "test-node"
        assert config.port == 8080
        
        # Invalid port (should be handled)
        with pytest.raises((ValueError, TypeError)) or pytest.raises(Exception):
            invalid_config = ServiceConfig(node_id="test-node", port=-1)


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="Node Manager Service not available")
class TestNodeManagerServiceEdgeCases:
    """Edge case tests for Node Manager Service"""
    
    def test_duplicate_node_registration(self):
        """Test handling of duplicate node registration"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        # Register same node twice
        service.register_node("peer-1", "192.168.1.2", 8081)
        service.register_node("peer-1", "192.168.1.3", 8082)  # Different address
        
        # Should update or handle gracefully
        nodes = service.get_registered_nodes()
        assert "peer-1" in nodes
    
    def test_unregister_nonexistent_node(self):
        """Test unregistering nonexistent node"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        # Should handle gracefully
        service.unregister_node("nonexistent-node")
        # Should not raise error
    
    def test_health_check_when_stopped(self):
        """Test health check when service is stopped"""
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        service.status = NodeStatus.STOPPED
        
        health = service.check_health()
        
        assert health is not None
        assert health["status"] == "unhealthy" or health["status"] == "stopped"
    
    def test_concurrent_node_registration(self):
        """Test concurrent node registration"""
        import threading
        
        config = ServiceConfig(node_id="test-node", port=8080)
        service = NodeManagerService(config)
        
        results = []
        errors = []
        
        def register_worker(node_id: str, address: str, port: int):
            try:
                service.register_node(node_id, address, port)
                results.append(node_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=register_worker,
                args=(f"peer-{i}", f"192.168.1.{i+1}", 8080 + i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

