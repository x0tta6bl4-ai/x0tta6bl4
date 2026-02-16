from datetime import datetime

import pytest

from src.monitoring.advanced_sla_metrics import (AdvancedSLAManager,
                                                 CustomMetricsRegistry,
                                                 MetricType,
                                                 SLAComplianceMonitor,
                                                 SLAStatus,
                                                 get_advanced_sla_manager)


class TestCustomMetricsRegistry:
    def test_register_metric(self):
        registry = CustomMetricsRegistry()
        metric = registry.register_metric("api_latency", MetricType.HISTOGRAM, "ms")
        assert metric.name == "api_latency"
        assert metric.metric_type == MetricType.HISTOGRAM

    def test_record_value(self):
        registry = CustomMetricsRegistry()
        registry.register_metric("api_latency", MetricType.HISTOGRAM, "ms")

        result = registry.record_value("api_latency", 100.5)
        assert result is True

    def test_record_unregistered_metric(self):
        registry = CustomMetricsRegistry()
        result = registry.record_value("unknown_metric", 100.5)
        assert result is False

    def test_get_metric_stats(self):
        registry = CustomMetricsRegistry()
        registry.register_metric("latency", MetricType.HISTOGRAM, "ms")

        for i in range(100):
            registry.record_value("latency", 100.0 + i)

        stats = registry.get_metric_stats("latency", window_seconds=300)
        assert "min" in stats
        assert "max" in stats
        assert "mean" in stats
        assert stats["count"] == 100


class TestSLAComplianceMonitor:
    def test_define_sla(self):
        registry = CustomMetricsRegistry()
        registry.register_metric("latency", MetricType.HISTOGRAM, "ms")
        monitor = SLAComplianceMonitor(registry)

        sla = monitor.define_sla("api_sla", "latency", 200.0, "<=")
        assert sla.name == "api_sla"
        assert sla.threshold_value == 200.0

    def test_check_compliance(self):
        registry = CustomMetricsRegistry()
        registry.register_metric("latency", MetricType.HISTOGRAM, "ms")
        monitor = SLAComplianceMonitor(registry)

        monitor.define_sla("api_sla", "latency", 200.0, "<=")

        for i in range(50):
            registry.record_value("latency", 100.0)

        point = monitor.check_compliance("api_sla")
        assert point is not None
        assert point.is_compliant is True

    def test_evaluate_threshold_operators(self):
        registry = CustomMetricsRegistry()
        monitor = SLAComplianceMonitor(registry)

        assert monitor._evaluate_threshold(100, 100, ">=") is True
        assert monitor._evaluate_threshold(100, 100, "<=") is True
        assert monitor._evaluate_threshold(100, 100, "==") is True
        assert monitor._evaluate_threshold(100, 101, ">") is False
        assert monitor._evaluate_threshold(100, 99, "<") is False

    def test_get_sla_compliance_report(self):
        registry = CustomMetricsRegistry()
        registry.register_metric("latency", MetricType.HISTOGRAM, "ms")
        monitor = SLAComplianceMonitor(registry)

        monitor.define_sla("api_sla", "latency", 200.0, "<=")

        for i in range(100):
            registry.record_value("latency", 100.0)
            point = monitor.check_compliance("api_sla")

        report = monitor.get_sla_compliance_report("api_sla", hours=1)
        assert "compliance_percentage" in report
        assert report["compliance_percentage"] >= 99.0


class TestAdvancedSLAManager:
    def test_register_metric(self):
        manager = AdvancedSLAManager()
        metric = manager.register_metric("response_time", MetricType.HISTOGRAM, "ms")
        assert metric.name == "response_time"

    def test_record_metric(self):
        manager = AdvancedSLAManager()
        manager.register_metric("response_time", MetricType.HISTOGRAM, "ms")

        result = manager.record_metric("response_time", 150.0)
        assert result is True

    def test_define_sla(self):
        manager = AdvancedSLAManager()
        manager.register_metric("response_time", MetricType.HISTOGRAM, "ms")

        sla = manager.define_sla("api_p95", "response_time", 200.0, "<=")
        assert sla.name == "api_p95"

    def test_check_all_slas(self):
        manager = AdvancedSLAManager()
        manager.register_metric("latency", MetricType.HISTOGRAM, "ms")
        manager.define_sla("sla1", "latency", 200.0, "<=")

        for i in range(100):
            manager.record_metric("latency", 100.0)

        results = manager.check_all_slas()
        assert "sla1" in results
        assert results["sla1"]["compliant"] is True

    def test_get_overall_compliance(self):
        manager = AdvancedSLAManager()
        manager.register_metric("latency", MetricType.HISTOGRAM, "ms")
        manager.define_sla("api_sla", "latency", 200.0, "<=")

        for i in range(100):
            manager.record_metric("latency", 100.0)
            manager.check_all_slas()

        overall = manager.get_overall_compliance()
        assert "overall_compliance_percentage" in overall
        assert "status" in overall


class TestSingleton:
    def test_get_singleton(self):
        manager1 = get_advanced_sla_manager()
        manager2 = get_advanced_sla_manager()
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
