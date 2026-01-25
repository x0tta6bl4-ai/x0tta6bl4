"""
Tests for enhanced eBPF metrics exporter.

These tests cover:
- Metric validation and sanitization
- Enhanced error handling
- Performance tracking
- Health check integration
- Error reporting
"""

import pytest
import time
import json
import subprocess
from unittest.mock import MagicMock, patch
from src.network.ebpf.metrics_exporter_enhanced import (
    EBPFMetricsExporterEnhanced,
    MetricValidationStatus,
    MetricValidationResult
)


class TestEBPFMetricsExporterEnhanced:
    """Tests for EBPFMetricsExporterEnhanced class."""

    @pytest.fixture
    def metrics_exporter(self):
        """Create EBPFMetricsExporterEnhanced instance."""
        with patch('src.network.ebpf.metrics_exporter.PrometheusExporter') as mock_prometheus:
            mock_instance = MagicMock()
            mock_prometheus.return_value = mock_instance
            mock_instance.metrics = {}

            # Mock degradation status
            mock_instance.degradation = MagicMock()
            mock_instance.degradation.prometheus_available = True

            exporter = EBPFMetricsExporterEnhanced(prometheus_port=9090)

            # Replace PrometheusExporter instance
            exporter.prometheus = mock_instance
            return exporter

    def test_initialization(self, metrics_exporter):
        """Test initializing enhanced metrics exporter."""
        assert metrics_exporter is not None
        assert hasattr(metrics_exporter, 'sanitizer')
        assert hasattr(metrics_exporter, 'error_count')
        assert hasattr(metrics_exporter, 'performance_stats')

    def test_register_map_with_validation(self, metrics_exporter):
        """Test registering map with validation."""
        metrics_exporter._validate_map_metadata = MagicMock(return_value=True)
        with patch.object(metrics_exporter, '_validate_and_sanitize') as mock_validate:
            mock_validate.return_value = {}, []

            success = metrics_exporter.register_map("packet_counters", "xdp_counter", "per_cpu_array")
            assert success is True

    def test_register_map_invalid_metadata(self, metrics_exporter):
        """Test registering map with invalid metadata."""
        metrics_exporter._validate_map_metadata = MagicMock(return_value=False)
        with patch.object(metrics_exporter, '_validate_and_sanitize') as mock_validate:
            mock_validate.return_value = {}, []

            success = metrics_exporter.register_map("invalid map", "", "invalid_type")
            assert success is False

    @pytest.mark.parametrize("metric_name, value, expected_status", [
        ("packet_counters", 100, MetricValidationStatus.VALID),
        ("packet_counters", -10, MetricValidationStatus.OUT_OF_RANGE),
        ("latency_ms", 50.5, MetricValidationStatus.VALID),
        ("latency_ms", "invalid", MetricValidationStatus.TYPE_MISMATCH),
        ("interface_count", 10, MetricValidationStatus.VALID),
        ("interface_count", 1000, MetricValidationStatus.OUT_OF_RANGE)
    ])
    def test_metric_validation(self, metrics_exporter, metric_name, value, expected_status):
        """Test metric validation with various scenarios."""
        result = metrics_exporter.sanitizer.validate(metric_name, value)
        assert result.status == expected_status
        assert result.name == metric_name
        assert result.value == value

    @pytest.mark.parametrize("metric_name, value, expected_status", [
        ("packet_counters", 100, MetricValidationStatus.VALID),
        ("packet_counters", -10, MetricValidationStatus.OUT_OF_RANGE),
        ("latency_ms", 50.5, MetricValidationStatus.VALID),
        ("latency_ms", "invalid", MetricValidationStatus.TYPE_MISMATCH)
    ])
    def test_metric_sanitization(self, metrics_exporter, metric_name, value, expected_status):
        """Test metric sanitization and validation."""
        metrics = {metric_name: value}
        valid_metrics, results = metrics_exporter.sanitizer.sanitize(metrics)
        assert len(results) == 1
        assert results[0].status == expected_status
        if expected_status == MetricValidationStatus.VALID:
            assert metric_name in valid_metrics
            assert valid_metrics[metric_name] == value
        else:
            assert metric_name not in valid_metrics

    def test_error_counting(self, metrics_exporter):
        """Test that error counts are properly tracked."""
        initial_total = metrics_exporter.error_count.total

        # Trigger different types of errors
        metrics_exporter._update_error_count("map_read")
        metrics_exporter._update_error_count("bpftool")
        metrics_exporter._update_error_count("validation")
        metrics_exporter._update_error_count("export")

        assert metrics_exporter.error_count.total == initial_total + 4
        assert metrics_exporter.error_count.map_read == 1
        assert metrics_exporter.error_count.bpftool == 1
        assert metrics_exporter.error_count.validation == 1
        assert metrics_exporter.error_count.export == 1

    def test_performance_tracking(self, metrics_exporter):
        """Test performance tracking."""
        start_time = time.time()
        metrics_exporter._track_performance("read_time", 0.010)
        metrics_exporter._track_performance("read_time", 0.020)
        metrics_exporter._track_performance("read_time", 0.015)

        assert len(metrics_exporter.performance_stats["read_time"]) == 3
        assert all(0.010 <= t <= 0.020 for t in metrics_exporter.performance_stats["read_time"])

    def test_get_error_summary(self, metrics_exporter):
        """Test getting error count summary."""
        metrics_exporter.error_count.total = 10
        metrics_exporter.error_count.map_read = 3
        metrics_exporter.error_count.bpftool = 2
        metrics_exporter.error_count.validation = 4
        metrics_exporter.error_count.export = 1

        summary = metrics_exporter.get_error_summary()
        assert summary["total"] == 10
        assert summary["map_read"] == 3
        assert summary["bpftool"] == 2
        assert summary["validation"] == 4
        assert summary["export"] == 1

    def test_get_performance_stats(self, metrics_exporter):
        """Test getting performance statistics."""
        metrics_exporter.performance_stats["read_time"] = [0.010, 0.020, 0.015]
        metrics_exporter.performance_stats["parse_time"] = [0.005, 0.008, 0.006]

        stats = metrics_exporter.get_performance_stats()
        assert "read_time" in stats
        assert "parse_time" in stats

        assert stats["read_time"]["count"] == 3
        assert 15 == pytest.approx(stats["read_time"]["average_ms"])
        assert 10 == pytest.approx(stats["read_time"]["min_ms"])
        assert 20 == pytest.approx(stats["read_time"]["max_ms"])
        assert 15 == pytest.approx(stats["read_time"]["latest_ms"])

    def test_get_health_status_healthy(self, metrics_exporter):
        """Test getting health status when system is healthy."""
        metrics_exporter.error_count.total = 0
        metrics_exporter.prometheus.degradation.consecutive_failures = 0

        health = metrics_exporter.get_health_status()
        assert health["overall"] == "healthy"
        assert health["errors"]["total"] == 0
        assert health["degradation"]["consecutive_failures"] == 0

    def test_get_health_status_degraded(self, metrics_exporter):
        """Test getting health status when system is degraded."""
        metrics_exporter.error_count.total = 60
        metrics_exporter.prometheus.degradation.consecutive_failures = 4
        metrics_exporter.prometheus.degradation.level = "degraded"

        health = metrics_exporter.get_health_status()
        assert health["overall"] == "degraded"
        assert health["errors"]["total"] == 60

    def test_get_health_status_unhealthy(self, metrics_exporter):
        """Test getting health status when system is unhealthy."""
        metrics_exporter.error_count.total = 150
        metrics_exporter.prometheus.degradation.consecutive_failures = 6

        health = metrics_exporter.get_health_status()
        assert health["overall"] == "unhealthy"
        assert health["errors"]["total"] == 150

    def test_reset_error_counts(self, metrics_exporter):
        """Test resetting error counts."""
        metrics_exporter.error_count.total = 10
        metrics_exporter.error_count.map_read = 3

        metrics_exporter.reset_error_counts()
        assert metrics_exporter.error_count.total == 0
        assert metrics_exporter.error_count.map_read == 0

    @patch('builtins.open', new_callable=MagicMock)
    def test_dump_diagnostics(self, mock_open, metrics_exporter):
        """Test dumping diagnostics information."""
        metrics_exporter.get_health_status = MagicMock(return_value={
            "overall": "healthy",
            "errors": {"total": 0},
            "degradation": {"level": "full"}
        })
        metrics_exporter.performance_stats = {
            "read_time": [0.010, 0.020],
            "parse_time": [0.005, 0.008]
        }
        metrics_exporter.registered_maps = {"map1": {}}
        metrics_exporter.prometheus.metrics = {"metric1": {}}

        metrics_exporter.dump_diagnostics("/tmp/ebpf_diagnostics.json")

        assert mock_open.called
        mock_open.assert_called_once_with("/tmp/ebpf_diagnostics.json", "w")
        handle = mock_open.return_value.__enter__.return_value
        assert handle.write.called

    @pytest.mark.parametrize("custom_metrics, map_metrics, expected_count", [
        ({}, {}, 0),
        ({'test_metric': 100}, {}, 1),
        ({}, {'packet_counters': 200}, 1),
        ({'test_metric': 100, 'another': 'invalid'}, {'packet_counters': 200}, 2)
    ])
    def test_export_metrics_with_validation(self, metrics_exporter,
                                           custom_metrics, map_metrics, expected_count):
        """Test exporting metrics with validation."""
        metrics_exporter._collect_all_metrics_with_validation = MagicMock(return_value=(map_metrics, []))
        metrics_exporter.sanitizer.sanitize = MagicMock(side_effect=[
            ({k: v for k, v in custom_metrics.items() if k == 'test_metric'}, []),
            (map_metrics, [])
        ])

        with patch.object(metrics_exporter, 'prometheus') as mock_prometheus:
            mock_prometheus.metrics = {}
            mock_prometheus.create_counter = MagicMock()
            mock_prometheus.create_gauge = MagicMock()

            exported = metrics_exporter.export_metrics(custom_metrics)

            assert len(exported) == expected_count

    @pytest.mark.parametrize("read_result, expected_action", [
        ("valid data", 1),
        (subprocess.TimeoutExpired("bpftool", 5), 0),
        (Exception("Test error"), 0)
    ])
    def test_map_read_with_timeout(self, metrics_exporter, read_result, expected_action):
        """Test map reading with timeout and error handling."""
        with patch.object(metrics_exporter, '_read_map_via_bpftool',
                        return_value=read_result if not isinstance(read_result, Exception) else None,
                        side_effect=read_result if isinstance(read_result, Exception) else None) as mock_read:

            result = metrics_exporter._read_map_via_bpftool_with_timeout("test_map")

            if expected_action == 1:
                assert result == "valid data"
            else:
                assert result is None

    def test_track_performance_samples(self, metrics_exporter):
        """Test performance tracking with maximum samples."""
        max_samples = 100
        for i in range(max_samples + 10):
            metrics_exporter._track_performance("read_time", i * 0.001)

        assert len(metrics_exporter.performance_stats["read_time"]) == max_samples
        assert metrics_exporter.performance_stats["read_time"][0] == 0.010
        assert metrics_exporter.performance_stats["read_time"][-1] == 0.109

    def test_validate_and_sanitize_batch(self, metrics_exporter):
        """Test validating and sanitizing a batch of metrics."""
        metrics = {
            "packet_counters": 100,
            "latency_ms": 50.5,
            "interface_count": 5,
            "invalid_metric": "not_a_number"
        }

        valid_metrics, results = metrics_exporter.sanitizer.sanitize(metrics)

        assert len(valid_metrics) == 3
        assert "packet_counters" in valid_metrics
        assert "latency_ms" in valid_metrics
        assert "interface_count" in valid_metrics
        assert "invalid_metric" not in valid_metrics

        assert len(results) == 4
        valid_results = [r for r in results if r.status == MetricValidationStatus.VALID]
        invalid_results = [r for r in results if r.status != MetricValidationStatus.VALID]
        assert len(valid_results) == 3
        assert len(invalid_results) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])