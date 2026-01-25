import pytest
from src.monitoring.unified_metrics import (
    UnifiedMetricsCollector,
    HealthCheckAggregator,
    get_metrics_collector,
    get_health_aggregator,
)


class TestUnifiedMetricsCollector:
    def test_record_metric(self):
        collector = UnifiedMetricsCollector()
        collector.record_metric("requests", 100.0)
        
        metric = collector.get_metric("requests")
        assert metric["latest"] == 100.0
    
    def test_compute_statistics(self):
        collector = UnifiedMetricsCollector()
        for i in range(10):
            collector.record_metric("latency", float(i * 10))
        
        metric = collector.get_metric("latency")
        assert metric["min"] == 0.0
        assert metric["max"] == 90.0
        assert metric["count"] == 10
    
    def test_export_prometheus(self):
        collector = UnifiedMetricsCollector()
        collector.record_metric("test_metric", 42.0)
        
        prom_output = collector.export_prometheus_format()
        assert "test_metric" in prom_output
        assert "42.0" in prom_output


class TestHealthCheckAggregator:
    def test_register_check(self):
        agg = HealthCheckAggregator()
        agg.register_check("db", lambda: {"connected": True})
        
        health = agg.get_overall_health()
        assert health["healthy_components"] == 1
    
    def test_failing_check(self):
        agg = HealthCheckAggregator()
        agg.register_check("bad", lambda: 1/0)
        
        health = agg.get_overall_health()
        assert health["healthy_components"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
