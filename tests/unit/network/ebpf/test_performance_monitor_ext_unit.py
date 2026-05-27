"""Extended unit tests for eBPF Performance Monitor."""
import os
from unittest.mock import patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.performance_monitor import (
    AlertSeverity,
    EBPFMetricSnapshot,
    EBPFSystemMetricSource,
    EBPFPerformanceMonitor,
    MetricType,
    AlertRule,
    PerformanceMetric,
    PerformanceThreshold,
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
        assert isinstance(m.metric_source, EBPFSystemMetricSource)

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


class TestEBPFSystemMetricSource:
    def test_reads_proc_net_dev_packet_totals(self, tmp_path):
        proc_net_dev = tmp_path / "dev"
        proc_net_dev.write_text(
            "\n".join(
                [
                    "Inter-|   Receive                                                |  Transmit",
                    " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed",
                    "  eth0: 100 7 0 0 0 0 0 0 200 11 0 0 0 0 0 0",
                    "  wlan0: 300 13 0 0 0 0 0 0 400 17 0 0 0 0 0 0",
                ]
            ),
            encoding="utf-8",
        )
        source = EBPFSystemMetricSource(
            proc_net_dev=proc_net_dev,
            bpffs_root=tmp_path / "missing-bpffs",
        )

        snapshot = source.snapshot()
        assert snapshot.packets_processed == 48
        assert snapshot.latency_microseconds == 0.0
        assert snapshot.cpu_usage_percent == 0.0
        assert snapshot.memory_usage_bytes == 0.0

    def test_reads_bpffs_file_sizes(self, tmp_path):
        bpffs = tmp_path / "bpffs"
        nested = bpffs / "maps"
        nested.mkdir(parents=True)
        (bpffs / "program").write_bytes(b"abcd")
        (nested / "map").write_bytes(b"123456")
        source = EBPFSystemMetricSource(
            proc_net_dev=tmp_path / "missing-dev",
            bpffs_root=bpffs,
        )

        assert source.snapshot().memory_usage_bytes == 10.0


class TestEBPFMetricSnapshot:
    def test_from_mapping_clamps_negative_values(self):
        snapshot = EBPFMetricSnapshot.from_mapping(
            {
                "packets_processed": -1,
                "latency_microseconds": -2.5,
                "cpu_usage_percent": -3.0,
                "memory_usage_bytes": -4.0,
            }
        )

        assert snapshot == EBPFMetricSnapshot()


class TestMetricSourceIntegration:
    def test_current_metric_values_use_injected_source(self):
        class Source:
            def snapshot(self):
                return {
                    "packets_processed": 123,
                    "latency_microseconds": 45.5,
                    "cpu_usage_percent": 6.5,
                    "memory_usage_bytes": 789.0,
                }

        monitor = EBPFPerformanceMonitor(metric_source=Source())

        assert monitor._get_current_metric_value("ebpf_packets_processed_total") == 123
        assert (
            monitor._get_current_metric_value(
                "ebpf_processing_latency_microseconds"
            )
            == 45.5
        )
        assert monitor._get_current_metric_value("ebpf_cpu_usage_percent") == 6.5
        assert monitor._get_current_metric_value("ebpf_memory_usage_bytes") == 789.0


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
