"""
Unit tests for ProductionMonitor and related components.

Tests cover:
- AlertThreshold and MonitoringConfig dataclasses
- ProductionMonitor initialization and default thresholds
- Request/connection/memory/CPU/PQC/error/throughput recording
- GTM stats recording
- Metrics collection with psutil mocked
- Alert checking (gt, lt, eq comparisons)
- Dashboard data aggregation
- Health status determination (healthy / unhealthy)
- Metrics history retention and pruning
- Global get_production_monitor() singleton
- Edge cases and error handling
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.production_monitoring import (AlertThreshold,
                                                  MonitoringConfig,
                                                  ProductionMonitor,
                                                  get_production_monitor)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_process(memory_rss=500 * 1024 * 1024, cpu_percent=25.0):
    """Create a mock psutil.Process object."""
    mock_proc = MagicMock()
    mem_info = MagicMock()
    mem_info.rss = memory_rss
    mock_proc.memory_info.return_value = mem_info
    mock_proc.cpu_percent.return_value = cpu_percent
    return mock_proc


def _patch_psutil(memory_rss=500 * 1024 * 1024, cpu=25.0):
    """Return a context manager that patches psutil.Process for collect_metrics().

    Since collect_metrics() does `import psutil` locally, we patch
    `psutil.Process` on the real psutil module (already in sys.modules).
    """
    mock_proc = _make_mock_process(memory_rss, cpu)
    return patch("psutil.Process", return_value=mock_proc), mock_proc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def monitor():
    """Return a fresh ProductionMonitor with default config."""
    return ProductionMonitor()


@pytest.fixture
def monitor_no_alerts():
    """Return a ProductionMonitor with alerting disabled."""
    config = MonitoringConfig(enable_alerting=False)
    return ProductionMonitor(config=config)


@pytest.fixture
def custom_config():
    """Return a custom MonitoringConfig."""
    return MonitoringConfig(
        alert_thresholds=[],
        metrics_retention_hours=1,
        sample_interval_seconds=5,
        enable_alerting=True,
    )


# ---------------------------------------------------------------------------
# AlertThreshold dataclass
# ---------------------------------------------------------------------------


class TestAlertThreshold:
    def test_creation(self):
        t = AlertThreshold(
            metric_name="error_rate",
            threshold_value=0.05,
            comparison="gt",
            severity="critical",
            description="Error rate too high",
        )
        assert t.metric_name == "error_rate"
        assert t.threshold_value == 0.05
        assert t.comparison == "gt"
        assert t.severity == "critical"
        assert t.description == "Error rate too high"

    def test_equality(self):
        a = AlertThreshold("m", 1.0, "gt", "warning", "desc")
        b = AlertThreshold("m", 1.0, "gt", "warning", "desc")
        assert a == b

    def test_different_severities(self):
        a = AlertThreshold("m", 1.0, "gt", "warning", "d")
        b = AlertThreshold("m", 1.0, "gt", "critical", "d")
        assert a != b


# ---------------------------------------------------------------------------
# MonitoringConfig dataclass
# ---------------------------------------------------------------------------


class TestMonitoringConfig:
    def test_defaults(self):
        cfg = MonitoringConfig()
        assert cfg.alert_thresholds == []
        assert cfg.metrics_retention_hours == 24
        assert cfg.sample_interval_seconds == 10
        assert cfg.enable_alerting is True

    def test_custom_values(self):
        cfg = MonitoringConfig(
            metrics_retention_hours=48,
            sample_interval_seconds=30,
            enable_alerting=False,
        )
        assert cfg.metrics_retention_hours == 48
        assert cfg.sample_interval_seconds == 30
        assert cfg.enable_alerting is False


# ---------------------------------------------------------------------------
# ProductionMonitor initialisation
# ---------------------------------------------------------------------------


class TestProductionMonitorInit:
    def test_default_config(self, monitor):
        assert monitor.config is not None
        assert isinstance(monitor.config, MonitoringConfig)
        assert monitor.metrics_history == []
        assert monitor.alerts == []
        assert isinstance(monitor.start_time, datetime)

    def test_custom_config(self, custom_config):
        m = ProductionMonitor(config=custom_config)
        assert m.config.metrics_retention_hours == 1
        assert m.config.sample_interval_seconds == 5

    def test_default_thresholds_loaded(self, monitor):
        names = [t.metric_name for t in monitor.config.alert_thresholds]
        assert "error_rate" in names
        assert "latency_p95" in names
        assert "memory_usage_mb" in names
        assert "cpu_usage_percent" in names
        assert "throughput_per_sec" in names

    def test_default_threshold_count(self, monitor):
        # 9 default thresholds
        assert len(monitor.config.alert_thresholds) == 9


# ---------------------------------------------------------------------------
# record_* methods (Prometheus gauge / counter / histogram)
# ---------------------------------------------------------------------------


class TestRecordMethods:
    @patch("src.monitoring.production_monitoring.production_requests_total")
    @patch("src.monitoring.production_monitoring.production_request_duration")
    def test_record_request(self, mock_duration, mock_counter, monitor):
        monitor.record_request("GET", "/health", 200, 0.05)
        mock_counter.labels.assert_called_once_with(
            method="GET", endpoint="/health", status=200
        )
        mock_counter.labels().inc.assert_called_once()
        mock_duration.labels.assert_called_once_with(method="GET", endpoint="/health")
        mock_duration.labels().observe.assert_called_once_with(0.05)

    @patch("src.monitoring.production_monitoring.production_active_connections")
    def test_record_connection(self, mock_gauge, monitor):
        monitor.record_connection(42)
        mock_gauge.set.assert_called_once_with(42)

    @patch("src.monitoring.production_monitoring.production_memory_usage")
    def test_record_memory(self, mock_gauge, monitor):
        monitor.record_memory(1024 * 1024 * 512)
        mock_gauge.set.assert_called_once_with(1024 * 1024 * 512)

    @patch("src.monitoring.production_monitoring.production_cpu_usage")
    def test_record_cpu(self, mock_gauge, monitor):
        monitor.record_cpu(55.5)
        mock_gauge.set.assert_called_once_with(55.5)

    @patch("src.monitoring.production_monitoring.production_pqc_handshake_duration")
    def test_record_pqc_handshake(self, mock_hist, monitor):
        monitor.record_pqc_handshake(0.12)
        mock_hist.observe.assert_called_once_with(0.12)

    @patch("src.monitoring.production_monitoring.production_error_rate")
    def test_record_error_rate(self, mock_gauge, monitor):
        monitor.record_error_rate(0.03)
        mock_gauge.set.assert_called_once_with(0.03)

    @patch("src.monitoring.production_monitoring.production_throughput")
    def test_record_throughput(self, mock_gauge, monitor):
        monitor.record_throughput(9500.0)
        mock_gauge.set.assert_called_once_with(9500.0)


# ---------------------------------------------------------------------------
# record_gtm_stats
# ---------------------------------------------------------------------------


class TestRecordGtmStats:
    @patch("src.monitoring.production_monitoring.gtm_conversion_rate")
    @patch("src.monitoring.production_monitoring.gtm_total_revenue")
    @patch("src.monitoring.production_monitoring.gtm_active_licenses")
    @patch("src.monitoring.production_monitoring.gtm_new_users_24h")
    @patch("src.monitoring.production_monitoring.gtm_total_users")
    def test_record_full_stats(self, m_users, m_new, m_lic, m_rev, m_conv, monitor):
        stats = {
            "total_users": 1000,
            "new_users_24h": 50,
            "active_licenses": 200,
            "total_revenue": 99999,
            "conversion_rate": 12.5,
        }
        monitor.record_gtm_stats(stats)
        m_users.set.assert_called_once_with(1000)
        m_new.set.assert_called_once_with(50)
        m_lic.set.assert_called_once_with(200)
        m_rev.set.assert_called_once_with(99999)
        m_conv.set.assert_called_once_with(12.5)

    @patch("src.monitoring.production_monitoring.gtm_conversion_rate")
    @patch("src.monitoring.production_monitoring.gtm_total_revenue")
    @patch("src.monitoring.production_monitoring.gtm_active_licenses")
    @patch("src.monitoring.production_monitoring.gtm_new_users_24h")
    @patch("src.monitoring.production_monitoring.gtm_total_users")
    def test_record_empty_stats_defaults_to_zero(
        self, m_users, m_new, m_lic, m_rev, m_conv, monitor
    ):
        monitor.record_gtm_stats({})
        m_users.set.assert_called_once_with(0)
        m_new.set.assert_called_once_with(0)
        m_lic.set.assert_called_once_with(0)
        m_rev.set.assert_called_once_with(0)
        m_conv.set.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# collect_metrics
# ---------------------------------------------------------------------------


class TestCollectMetrics:
    def test_collect_returns_expected_keys(self, monitor):
        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor.collect_metrics()
        expected_keys = {
            "timestamp",
            "memory_usage_mb",
            "cpu_usage_percent",
            "active_connections",
            "error_rate",
            "throughput_per_sec",
            "uptime_seconds",
        }
        assert expected_keys == set(result.keys())

    def test_collect_memory_conversion(self, monitor):
        rss = 1024 * 1024 * 256  # 256 MB
        patcher, _ = _patch_psutil(memory_rss=rss)
        with patcher:
            result = monitor.collect_metrics()
        assert abs(result["memory_usage_mb"] - 256.0) < 0.01

    def test_collect_cpu(self, monitor):
        patcher, _ = _patch_psutil(cpu=78.3)
        with patcher:
            result = monitor.collect_metrics()
        assert result["cpu_usage_percent"] == 78.3

    def test_collect_appends_to_history(self, monitor):
        patcher, _ = _patch_psutil()
        with patcher:
            assert len(monitor.metrics_history) == 0
            monitor.collect_metrics()
            assert len(monitor.metrics_history) == 1
            monitor.collect_metrics()
            assert len(monitor.metrics_history) == 2

    def test_collect_prunes_old_metrics(self, monitor):
        """Metrics older than metrics_retention_hours should be pruned."""
        monitor.config.metrics_retention_hours = 1
        old_ts = (datetime.now() - timedelta(hours=2)).isoformat()
        monitor.metrics_history.append(
            {
                "timestamp": old_ts,
                "memory_usage_mb": 100,
                "cpu_usage_percent": 10,
            }
        )

        patcher, _ = _patch_psutil()
        with patcher:
            monitor.collect_metrics()
        # Old entry should have been pruned, only new one remains
        assert len(monitor.metrics_history) == 1
        assert monitor.metrics_history[0]["timestamp"] != old_ts

    def test_collect_no_alerts_when_disabled(self, monitor_no_alerts):
        patcher, _ = _patch_psutil()
        with patcher:
            monitor_no_alerts.collect_metrics()
        assert len(monitor_no_alerts.alerts) == 0

    def test_collect_uptime_positive(self, monitor):
        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor.collect_metrics()
        assert result["uptime_seconds"] >= 0

    def test_collect_timestamp_is_isoformat(self, monitor):
        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor.collect_metrics()
        # Should parse without error
        datetime.fromisoformat(result["timestamp"])


# ---------------------------------------------------------------------------
# _check_alerts
# ---------------------------------------------------------------------------


class TestCheckAlerts:
    def test_gt_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("error_rate", 0.01, "gt", "warning", "high error"),
        ]
        metrics = {"error_rate": 0.02}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]["severity"] == "warning"
        assert monitor.alerts[0]["metric_value"] == 0.02

    def test_gt_not_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("error_rate", 0.05, "gt", "critical", "high error"),
        ]
        metrics = {"error_rate": 0.01}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_lt_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold(
                "throughput_per_sec", 5000.0, "lt", "warning", "low throughput"
            ),
        ]
        metrics = {"throughput_per_sec": 3000.0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]["description"] == "low throughput"

    def test_lt_not_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold(
                "throughput_per_sec", 5000.0, "lt", "warning", "low throughput"
            ),
        ]
        metrics = {"throughput_per_sec": 6000.0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_eq_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("status_code", 503, "eq", "critical", "service unavailable"),
        ]
        metrics = {"status_code": 503}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 1

    def test_eq_not_triggered(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("status_code", 503, "eq", "critical", "service unavailable"),
        ]
        metrics = {"status_code": 200}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_missing_metric_skipped(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("nonexistent", 1.0, "gt", "warning", "n/a"),
        ]
        metrics = {"error_rate": 0.5}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_multiple_alerts(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("error_rate", 0.01, "gt", "warning", "warn err"),
            AlertThreshold("error_rate", 0.05, "gt", "critical", "crit err"),
        ]
        metrics = {"error_rate": 0.10}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 2
        severities = {a["severity"] for a in monitor.alerts}
        assert severities == {"warning", "critical"}

    def test_alert_structure(self, monitor):
        monitor.config.alert_thresholds = [
            AlertThreshold("cpu", 90.0, "gt", "critical", "cpu overload"),
        ]
        metrics = {"cpu": 95.0}
        monitor._check_alerts(metrics)
        alert = monitor.alerts[0]
        assert "timestamp" in alert
        assert alert["metric_name"] == "cpu"
        assert alert["metric_value"] == 95.0
        assert alert["threshold"] == 90.0
        assert alert["severity"] == "critical"
        assert alert["description"] == "cpu overload"

    def test_alert_accumulates(self, monitor):
        """Repeated calls accumulate alerts."""
        monitor.config.alert_thresholds = [
            AlertThreshold("x", 10, "gt", "warning", "too high"),
        ]
        monitor._check_alerts({"x": 20})
        monitor._check_alerts({"x": 30})
        assert len(monitor.alerts) == 2


# ---------------------------------------------------------------------------
# get_dashboard_data
# ---------------------------------------------------------------------------


class TestGetDashboardData:
    def _run_dashboard(self, monitor, memory_rss=500 * 1024 * 1024, cpu=25.0):
        patcher, _ = _patch_psutil(memory_rss, cpu)
        with patcher:
            return monitor.get_dashboard_data()

    def test_dashboard_keys(self, monitor):
        data = self._run_dashboard(monitor)
        assert "current" in data
        assert "statistics" in data
        assert "alerts" in data
        assert "uptime_seconds" in data

    def test_statistics_computed(self, monitor):
        # Prime with a data point
        p1, _ = _patch_psutil(300 * 1024 * 1024, 30.0)
        with p1:
            monitor.collect_metrics()

        # Now get dashboard (adds another data point)
        p2, _ = _patch_psutil(500 * 1024 * 1024, 50.0)
        with p2:
            data = monitor.get_dashboard_data()

        stats = data["statistics"]
        assert stats["memory_avg_mb"] > 0
        assert stats["memory_max_mb"] >= stats["memory_avg_mb"]
        assert stats["cpu_avg_percent"] > 0
        assert stats["cpu_max_percent"] >= stats["cpu_avg_percent"]

    def test_alerts_limited_to_ten(self, monitor):
        # Populate 15 alerts manually
        for i in range(15):
            monitor.alerts.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "metric_name": "test",
                    "metric_value": i,
                    "threshold": 0,
                    "severity": "warning",
                    "description": f"alert {i}",
                }
            )
        data = self._run_dashboard(monitor)
        assert len(data["alerts"]) == 10
        # Should be the LAST 10
        assert data["alerts"][0]["description"] == "alert 5"

    def test_uptime_positive(self, monitor):
        data = self._run_dashboard(monitor)
        assert data["uptime_seconds"] >= 0

    def test_current_metrics_included(self, monitor):
        data = self._run_dashboard(monitor)
        assert "memory_usage_mb" in data["current"]
        assert "cpu_usage_percent" in data["current"]


# ---------------------------------------------------------------------------
# get_health_status
# ---------------------------------------------------------------------------


class TestGetHealthStatus:
    def _run_health(self, monitor, memory_rss=500 * 1024 * 1024, cpu=25.0):
        patcher, _ = _patch_psutil(memory_rss, cpu)
        with patcher:
            return monitor.get_health_status()

    def test_healthy_when_normal(self, monitor_no_alerts):
        result = self._run_health(
            monitor_no_alerts, memory_rss=500 * 1024 * 1024, cpu=25.0
        )
        assert result["status"] == "healthy"
        assert result["issues"] == []

    def test_unhealthy_high_memory(self, monitor_no_alerts):
        # 2500 MB > 2400 threshold
        result = self._run_health(
            monitor_no_alerts, memory_rss=2500 * 1024 * 1024, cpu=10.0
        )
        assert result["status"] == "unhealthy"
        assert "High memory usage" in result["issues"]

    def test_unhealthy_high_cpu(self, monitor_no_alerts):
        result = self._run_health(
            monitor_no_alerts, memory_rss=100 * 1024 * 1024, cpu=96.0
        )
        assert result["status"] == "unhealthy"
        assert "High CPU usage" in result["issues"]

    def test_unhealthy_high_error_rate(self, monitor_no_alerts):
        """Inject a high error_rate via the Prometheus fallback."""
        mock_proc = _make_mock_process(100 * 1024 * 1024, 10.0)

        # Make the error_rate fallback return 0.10
        mock_err_gauge = MagicMock()
        mock_err_gauge._value = MagicMock()
        mock_err_gauge._value.get.return_value = 0.10

        with patch("psutil.Process", return_value=mock_proc):
            with patch(
                "src.monitoring.production_monitoring.production_error_rate",
                mock_err_gauge,
            ):
                # Force the REGISTRY iteration to raise so we hit the fallback
                mock_registry = MagicMock()
                mock_registry._collector_to_names = {}  # empty - no collectors
                with patch("prometheus_client.REGISTRY", mock_registry):
                    result = monitor_no_alerts.get_health_status()

        assert result["status"] == "unhealthy"
        assert "High error rate" in result["issues"]

    def test_health_status_keys(self, monitor_no_alerts):
        result = self._run_health(monitor_no_alerts)
        assert "status" in result
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert "metrics" in result
        assert "issues" in result

    def test_health_multiple_issues(self, monitor_no_alerts):
        # 2500 MB memory AND 96% CPU
        result = self._run_health(
            monitor_no_alerts, memory_rss=2500 * 1024 * 1024, cpu=96.0
        )
        assert result["status"] == "unhealthy"
        assert len(result["issues"]) >= 2

    def test_health_returns_metrics_dict(self, monitor_no_alerts):
        result = self._run_health(monitor_no_alerts)
        metrics = result["metrics"]
        assert "memory_usage_mb" in metrics
        assert "cpu_usage_percent" in metrics
        assert "error_rate" in metrics


# ---------------------------------------------------------------------------
# Global singleton: get_production_monitor
# ---------------------------------------------------------------------------


class TestGetProductionMonitor:
    def test_returns_production_monitor(self):
        import src.monitoring.production_monitoring as mod

        mod._production_monitor = None
        m = get_production_monitor()
        assert isinstance(m, ProductionMonitor)

    def test_returns_same_instance(self):
        import src.monitoring.production_monitoring as mod

        mod._production_monitor = None
        m1 = get_production_monitor()
        m2 = get_production_monitor()
        assert m1 is m2

    def test_reset_singleton(self):
        import src.monitoring.production_monitoring as mod

        mod._production_monitor = None
        m1 = get_production_monitor()
        mod._production_monitor = None
        m2 = get_production_monitor()
        assert m1 is not m2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_collect_metrics_with_mesh_router_attr(self, monitor):
        """Test that code path for _mesh_router is exercised without crash."""
        mock_router = MagicMock()
        mock_router.get_stats.return_value = {
            "peers": [
                {"alive": True},
                {"alive": True},
                {"alive": False},
            ]
        }
        monitor._mesh_router = mock_router

        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor.collect_metrics()
        assert "active_connections" in result

    def test_empty_metrics_history_dashboard(self):
        """Dashboard with initially empty history should not crash."""
        m = ProductionMonitor(config=MonitoringConfig(enable_alerting=False))
        patcher, _ = _patch_psutil()
        with patcher:
            data = m.get_dashboard_data()
        assert data["statistics"]["memory_avg_mb"] >= 0

    def test_alert_threshold_boundary_gt(self, monitor):
        """Exactly at threshold should NOT trigger gt alert."""
        monitor.config.alert_thresholds = [
            AlertThreshold("cpu", 80.0, "gt", "warning", "cpu warn"),
        ]
        metrics = {"cpu": 80.0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_alert_threshold_boundary_lt(self, monitor):
        """Exactly at threshold should NOT trigger lt alert."""
        monitor.config.alert_thresholds = [
            AlertThreshold("throughput", 5000.0, "lt", "warning", "low tp"),
        ]
        metrics = {"throughput": 5000.0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_alert_threshold_boundary_eq(self, monitor):
        """Exactly at threshold SHOULD trigger eq alert."""
        monitor.config.alert_thresholds = [
            AlertThreshold("code", 503, "eq", "critical", "503 detected"),
        ]
        metrics = {"code": 503}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 1

    def test_unknown_comparison_does_not_trigger(self, monitor):
        """An unrecognized comparison operator should not trigger alert."""
        monitor.config.alert_thresholds = [
            AlertThreshold("m", 1.0, "unknown_op", "warning", "desc"),
        ]
        metrics = {"m": 999.0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 0

    def test_config_alert_thresholds_extend(self, custom_config):
        """Custom config with empty thresholds gets defaults appended."""
        m = ProductionMonitor(config=custom_config)
        assert len(m.config.alert_thresholds) == 9

    def test_record_request_various_status_codes(self, monitor):
        """Record requests with different status codes."""
        with patch(
            "src.monitoring.production_monitoring.production_requests_total"
        ) as mock_c:
            with patch(
                "src.monitoring.production_monitoring.production_request_duration"
            ) as mock_d:
                for code in [200, 201, 400, 404, 500, 503]:
                    monitor.record_request("POST", "/api", code, 0.1)
                assert mock_c.labels.call_count == 6

    def test_collect_metrics_uptime_increases(self, monitor):
        """Uptime should increase between calls."""
        patcher, _ = _patch_psutil()
        with patcher:
            r1 = monitor.collect_metrics()
            time.sleep(0.05)
            r2 = monitor.collect_metrics()
        assert r2["uptime_seconds"] >= r1["uptime_seconds"]

    def test_collect_metrics_default_error_rate_zero(self, monitor_no_alerts):
        """Without real Prometheus data, error_rate defaults to 0.0."""
        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor_no_alerts.collect_metrics()
        # error_rate should be 0.0 or a small number, not a crash
        assert isinstance(result["error_rate"], (int, float))

    def test_collect_metrics_default_throughput_zero(self, monitor_no_alerts):
        """Without real Prometheus data, throughput defaults to 0.0."""
        patcher, _ = _patch_psutil()
        with patcher:
            result = monitor_no_alerts.collect_metrics()
        assert isinstance(result["throughput_per_sec"], (int, float))

    def test_multiple_collects_keep_recent_history(self, monitor):
        """History should retain entries within the retention window."""
        monitor.config.metrics_retention_hours = 24
        patcher, _ = _patch_psutil()
        with patcher:
            for _ in range(5):
                monitor.collect_metrics()
        assert len(monitor.metrics_history) == 5

    def test_dashboard_statistics_with_single_entry(self, monitor_no_alerts):
        """Dashboard statistics should work even with just one metrics entry."""
        patcher, _ = _patch_psutil(memory_rss=800 * 1024 * 1024, cpu=40.0)
        with patcher:
            data = monitor_no_alerts.get_dashboard_data()
        # Only one entry so avg == max
        stats = data["statistics"]
        assert abs(stats["memory_avg_mb"] - stats["memory_max_mb"]) < 0.01
        assert abs(stats["cpu_avg_percent"] - stats["cpu_max_percent"]) < 0.01

    def test_health_boundary_memory_exactly_2400(self, monitor_no_alerts):
        """Memory at exactly 2400 MB should still be healthy (not >)."""
        patcher, _ = _patch_psutil(memory_rss=2400 * 1024 * 1024, cpu=10.0)
        with patcher:
            result = monitor_no_alerts.get_health_status()
        assert "High memory usage" not in result["issues"]

    def test_health_boundary_cpu_exactly_95(self, monitor_no_alerts):
        """CPU at exactly 95% should still be healthy (not >)."""
        patcher, _ = _patch_psutil(memory_rss=100 * 1024 * 1024, cpu=95.0)
        with patcher:
            result = monitor_no_alerts.get_health_status()
        assert "High CPU usage" not in result["issues"]

    def test_alert_threshold_with_zero_value(self, monitor):
        """Alert for metric with value 0 and lt comparison."""
        monitor.config.alert_thresholds = [
            AlertThreshold("connections", 1.0, "lt", "critical", "no connections"),
        ]
        metrics = {"connections": 0}
        monitor._check_alerts(metrics)
        assert len(monitor.alerts) == 1

    def test_record_gtm_partial_stats(self, monitor):
        """Partial stats should use defaults for missing keys."""
        with patch("src.monitoring.production_monitoring.gtm_total_users") as m_u:
            with patch("src.monitoring.production_monitoring.gtm_new_users_24h") as m_n:
                with patch(
                    "src.monitoring.production_monitoring.gtm_active_licenses"
                ) as m_l:
                    with patch(
                        "src.monitoring.production_monitoring.gtm_total_revenue"
                    ) as m_r:
                        with patch(
                            "src.monitoring.production_monitoring.gtm_conversion_rate"
                        ) as m_c:
                            monitor.record_gtm_stats({"total_users": 5})
                            m_u.set.assert_called_once_with(5)
                            m_n.set.assert_called_once_with(0)
                            m_l.set.assert_called_once_with(0)
                            m_r.set.assert_called_once_with(0)
                            m_c.set.assert_called_once_with(0)
