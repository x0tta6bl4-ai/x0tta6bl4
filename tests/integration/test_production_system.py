import pytest
from src.core.production_system import ProductionSystem, get_production_system


class TestProductionSystem:
    def test_system_initialization(self):
        system = ProductionSystem()
        assert system.request_count == 0
        assert system.error_count == 0
    
    def test_record_successful_request(self):
        system = ProductionSystem()
        system.record_request(
            "GET", "/api/users", 200, 45.5,
            {"client_ip": "192.168.1.1", "service": "api"}
        )
        assert system.request_count == 1
        assert system.error_count == 0
    
    def test_record_error_request(self):
        system = ProductionSystem()
        system.record_request(
            "POST", "/api/users", 500, 100.0,
            {"client_ip": "192.168.1.1"}
        )
        assert system.request_count == 1
        assert system.error_count == 1
    
    def test_get_system_health(self):
        system = ProductionSystem()
        for i in range(10):
            system.record_request(
                "GET", f"/endpoint{i}", 200, 50.0,
                {"client_ip": "192.168.1.1"}
            )
        
        health = system.get_system_health()
        assert health["requests"]["total"] == 10
        assert health["requests"]["error_rate"] == 0.0
        assert "health_score" in health
    
    def test_health_score_calculation(self):
        system = ProductionSystem()
        
        for _ in range(100):
            system.record_request("GET", "/api", 200, 50.0, {})
        
        health = system.get_system_health()
        score = health["health_score"]
        assert 0 <= score <= 100
        assert score > 80
    
    def test_cardinality_tracking(self):
        system = ProductionSystem()
        
        for i in range(50):
            system.record_request(
                "GET", "/api", 200, 30.0,
                {"client_ip": f"192.168.1.{i}", "method": "GET"}
            )
        
        health = system.get_system_health()
        assert health["cardinality"]["total_metrics"] > 0
    
    def test_production_readiness_report(self):
        system = ProductionSystem()
        
        for _ in range(50):
            system.record_request("GET", "/api", 200, 40.0, {})
        
        report = system.get_production_readiness_report()
        assert "overall_score" in report
        assert "components" in report
        assert "readiness_level" in report
        assert report["readiness_level"] in [
            "PRODUCTION_READY", "NEAR_PRODUCTION", "STAGING_READY", "DEVELOPMENT"
        ]
    
    def test_components_integrated(self):
        system = ProductionSystem()
        assert system.cardinality_optimizer is not None
        assert system.performance_tuner is not None
        assert system.hardening_manager is not None
        assert system.resilient_executor is not None
    
    def test_error_rate_impacts_health(self):
        system1 = ProductionSystem()
        system2 = ProductionSystem()
        
        for _ in range(100):
            system1.record_request("GET", "/api", 200, 50.0, {})
        
        for _ in range(100):
            system2.record_request("GET", "/api", 200, 50.0, {})
        
        for _ in range(50):
            system2.record_request("GET", "/api", 500, 50.0, {})
        
        health1 = system1.get_system_health()
        health2 = system2.get_system_health()
        
        assert health1["health_score"] > health2["health_score"]
    
    def test_singleton_pattern(self):
        sys1 = get_production_system()
        sys2 = get_production_system()
        assert sys1 is sys2


class TestProductionIntegration:
    def test_full_workflow(self):
        system = ProductionSystem()
        
        requests = [
            ("GET", "/users", 200, 45.0),
            ("POST", "/users", 201, 120.0),
            ("GET", "/users/1", 200, 35.0),
            ("PUT", "/users/1", 200, 80.0),
            ("DELETE", "/users/1", 204, 50.0),
        ]
        
        for method, path, status, latency in requests:
            system.record_request(
                method, path, status, latency,
                {"client_ip": "192.168.1.100", "user_id": "123"}
            )
        
        report = system.get_production_readiness_report()
        assert report["overall_score"] >= 70
        assert report["components"]["cardinality_management"] == "operational"
        assert report["components"]["resilience_patterns"] == "operational"
    
    def test_high_load_scenario(self):
        system = ProductionSystem()
        
        for i in range(1000):
            status = 200 if i % 20 != 0 else 500
            system.record_request(
                "GET", f"/api/{i % 10}", status, 30.0 + (i % 50),
                {"client_ip": f"192.168.1.{i % 256}", "request_id": str(i)}
            )
        
        health = system.get_system_health()
        assert health["requests"]["total"] == 1000
        assert 0 <= health["health_score"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
