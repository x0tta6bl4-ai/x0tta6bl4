"""Extended unit tests for eBPF Performance Monitor."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.performance_monitor import (
    AlertSeverity,
    MetricType,
    PerformanceMetric,
    AlertRule,
    PerformanceThreshold,
    EBPFPerformanceMonitor,
)


class TestAlertSeverityEnum:
    def test_values(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestMetricTypeEnum:
    def test_values(self):
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"


class TestPerformanceMetricDataclass:
    def test_defaults(self):
        m = PerformanceMetric(name="test", type=MetricType.COUNTER, description="desc")
        assert m.labels == []
        assert m.unit == ""

    def test_custom(self):
        m = PerformanceMetric(
            name="lat", type=MetricType.HISTOGRAM,
            description="lat", labels=["prog"], unit="us"
        )
        assert m.labels == ["prog"]
        assert m.unit == "us"


class TestAlertRuleDataclass:
    def test_defaults(self):
        r = AlertRule(name="test", condition="foo > 10")
        assert r.duration == "5m"
        assert r.severity == AlertSeverity.WARNING
        assert r.description == ""

    def test_custom(self):
        r = AlertRule(
            name="crit", condition="bar > 100",
            duration="1m", severity=AlertSeverity.CRITICAL,
        )
        assert r.severity == AlertSeverity.CRITICAL


class TestPerformanceThresholdDataclass:
    def test_fields(self):
        t = PerformanceThreshold(
            metric="cpu", warning_threshold=80.0,
            critical_threshold=95.0, description="CPU"
        )
        assert t.warning_threshold == 80.0
        assert t.critical_threshold == 95.0


class TestEBPFPerformanceMonitorInit:
    def test_default(self):
        m = EBPFPerformanceMonitor()
        assert m.prometheus_port == 9090
        assert m.monitoring_active is False
        assert isinstance(m.metrics, dict)

    def test_custom_port(self):
        m = EBPFPerformanceMonitor(prometheus_port=8080)
        assert m.prometheus_port == 8080

    def test_alert_rules_populated(self):
        m = EBPFPerformanceMonitor()
        assert len(m.alert_rules) > 0
        names = [r.name for r in m.alert_rules]
        assert "EBPFHighLatency" in names

    def test_thresholds_populated(self):
        m = EBPFPerformanceMonitor()
        assert len(m.thresholds) > 0

    def test_performance_history(self):
        m = EBPFPerformanceMonitor()
        assert m.performance_history == {}


class TestRegisterMetric:
    @patch("src.network.ebpf.performance_monitor.PROMETHEUS_AVAILABLE", False)
    def test_no_prometheus(self):
        m = EBPFPerformanceMonitor()
        pm = PerformanceMetric(name="x", type=MetricType.GAUGE, description="x")
        m._register_metric(pm)  # Should not crash

    @patch("src.network.ebpf.performance_monitor.PROMETHEUS_AVAILABLE", True)
    def test_register_counter(self):
        m = EBPFPerformanceMonitor()
        pm = PerformanceMetric(
            name="test_c2", type=MetricType.COUNTER, description="test"
        )
        m._register_metric(pm)
        assert "test_c2" in m.metrics

    @patch("src.network.ebpf.performance_monitor.PROMETHEUS_AVAILABLE", True)
    def test_register_gauge(self):
        m = EBPFPerformanceMonitor()
        pm = PerformanceMetric(
            name="test_g2", type=MetricType.GAUGE, description="test"
        )
        m._register_metric(pm)
        assert "test_g2" in m.metrics

    @patch("src.network.ebpf.performance_monitor.PROMETHEUS_AVAILABLE", True)
    def test_register_histogram(self):
        m = EBPFPerformanceMonitor()
        pm = PerformanceMetric(
            name="test_h2", type=MetricType.HISTOGRAM, description="test"
        )
        m._register_metric(pm)
        assert "test_h2" in m.metrics
