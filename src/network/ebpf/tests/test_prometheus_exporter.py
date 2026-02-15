"""
Unit tests for PrometheusExporter component.

Tests cover:
- Initialization
- Metric registration
- Metric setting
- Counter operations
- Gauge operations
- Histogram operations
- Summary operations
- HTTP server
- Error handling
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from telemetry_module import (MetricDefinition, MetricType, PrometheusExporter,
                              TelemetryConfig)


class TestPrometheusExporterInitialization:
    """Test PrometheusExporter initialization."""

    def test_initialization_with_config(self, telemetry_config):
        """Test initialization with configuration."""
        security = MagicMock()
        exporter = PrometheusExporter(telemetry_config, security)

        assert exporter.config == telemetry_config
        assert exporter.security == security
        assert isinstance(exporter.metrics, dict)
        assert isinstance(exporter.metric_definitions, dict)

    def test_initialization_registry(self, telemetry_config):
        """Test that registry is created."""
        security = MagicMock()
        exporter = PrometheusExporter(telemetry_config, security)

        assert exporter.registry is not None

    def test_initialization_server_not_started(self, telemetry_config):
        """Test that server is not started on initialization."""
        security = MagicMock()
        exporter = PrometheusExporter(telemetry_config, security)

        assert exporter.server_started == False


class TestPrometheusExporterMetricRegistration:
    """Test metric registration."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_register_counter_metric(self, exporter):
        """Test registering a counter metric."""
        definition = MetricDefinition(
            name="test_counter",
            type=MetricType.COUNTER,
            description="Test counter metric",
        )

        exporter.register_metric(definition)

        assert "test_counter" in exporter.metric_definitions
        assert exporter.metric_definitions["test_counter"] == definition

    def test_register_gauge_metric(self, exporter):
        """Test registering a gauge metric."""
        definition = MetricDefinition(
            name="test_gauge", type=MetricType.GAUGE, description="Test gauge metric"
        )

        exporter.register_metric(definition)

        assert "test_gauge" in exporter.metric_definitions

    def test_register_histogram_metric(self, exporter):
        """Test registering a histogram metric."""
        definition = MetricDefinition(
            name="test_histogram",
            type=MetricType.HISTOGRAM,
            description="Test histogram metric",
        )

        exporter.register_metric(definition)

        assert "test_histogram" in exporter.metric_definitions

    def test_register_summary_metric(self, exporter):
        """Test registering a summary metric."""
        definition = MetricDefinition(
            name="test_summary",
            type=MetricType.SUMMARY,
            description="Test summary metric",
        )

        exporter.register_metric(definition)

        assert "test_summary" in exporter.metric_definitions

    def test_register_metric_with_labels(self, exporter):
        """Test registering metric with labels."""
        definition = MetricDefinition(
            name="test_metric_with_labels",
            type=MetricType.GAUGE,
            description="Test metric with labels",
            labels=["label1", "label2"],
        )

        exporter.register_metric(definition)

        assert "test_metric_with_labels" in exporter.metric_definitions
        assert exporter.metric_definitions["test_metric_with_labels"].labels == [
            "label1",
            "label2",
        ]

    def test_register_duplicate_metric(self, exporter):
        """Test registering duplicate metric."""
        definition = MetricDefinition(
            name="test_metric", type=MetricType.GAUGE, description="Test metric"
        )

        exporter.register_metric(definition)
        exporter.register_metric(definition)

        # Should still be registered (no error)
        assert "test_metric" in exporter.metric_definitions


class TestPrometheusExporterMetricSetting:
    """Test metric value setting."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_set_metric_value(self, exporter):
        """Test setting metric value."""
        # Register metric
        definition = MetricDefinition(
            name="test_gauge", type=MetricType.GAUGE, description="Test gauge"
        )
        exporter.register_metric(definition)

        # Set value
        exporter.set_metric("test_gauge", 42.0)

        # Should not raise exception
        assert True

    def test_set_metric_with_labels(self, exporter):
        """Test setting metric value with labels."""
        # Register metric with labels
        definition = MetricDefinition(
            name="test_metric_with_labels",
            type=MetricType.GAUGE,
            description="Test metric",
            labels=["label1", "label2"],
        )
        exporter.register_metric(definition)

        # Set value with labels
        exporter.set_metric(
            "test_metric_with_labels",
            42.0,
            labels={"label1": "value1", "label2": "value2"},
        )

        # Should not raise exception
        assert True

    def test_set_metric_not_registered(self, exporter):
        """Test setting value for unregistered metric."""
        # Should not raise exception (just log warning)
        exporter.set_metric("unregistered_metric", 42.0)

        assert True

    def test_set_metric_invalid_value(self, exporter):
        """Test setting invalid metric value."""
        # Register metric
        definition = MetricDefinition(
            name="test_gauge", type=MetricType.GAUGE, description="Test gauge"
        )
        exporter.register_metric(definition)

        # Set invalid value (NaN)
        import math

        exporter.set_metric("test_gauge", float("nan"))

        # Should handle gracefully
        assert True


class TestPrometheusExporterCounterOperations:
    """Test counter metric operations."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_increment_counter(self, exporter):
        """Test incrementing counter."""
        # Register counter
        definition = MetricDefinition(
            name="test_counter", type=MetricType.COUNTER, description="Test counter"
        )
        exporter.register_metric(definition)

        # Increment
        exporter.increment_metric("test_counter")

        # Should not raise exception
        assert True

    def test_increment_counter_with_amount(self, exporter):
        """Test incrementing counter with amount."""
        # Register counter
        definition = MetricDefinition(
            name="test_counter", type=MetricType.COUNTER, description="Test counter"
        )
        exporter.register_metric(definition)

        # Increment with amount
        exporter.increment_metric("test_counter", amount=5)

        # Should not raise exception
        assert True

    def test_increment_counter_with_labels(self, exporter):
        """Test incrementing counter with labels."""
        # Register counter with labels
        definition = MetricDefinition(
            name="test_counter_with_labels",
            type=MetricType.COUNTER,
            description="Test counter",
            labels=["method", "endpoint"],
        )
        exporter.register_metric(definition)

        # Increment with labels
        exporter.increment_metric(
            "test_counter_with_labels",
            amount=1,
            labels={"method": "GET", "endpoint": "/api/health"},
        )

        # Should not raise exception
        assert True


class TestPrometheusExporterBatchExport:
    """Test batch metric export."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_export_metrics_single(self, exporter):
        """Test exporting single metric."""
        metrics_data = {"test_metric": 42.0}

        result = exporter.export_metrics(metrics_data)

        assert isinstance(result, dict)
        assert "test_metric" in result

    def test_export_metrics_multiple(self, exporter):
        """Test exporting multiple metrics."""
        metrics_data = {"metric1": 42.0, "metric2": 100.5, "metric3": 200}

        result = exporter.export_metrics(metrics_data)

        assert isinstance(result, dict)
        assert len(result) == 3

    def test_export_metrics_auto_register(self, exporter):
        """Test auto-registration of metrics."""
        metrics_data = {"new_metric": 42.0}

        result = exporter.export_metrics(metrics_data)

        # Metric should be auto-registered
        assert "new_metric" in exporter.metric_definitions

    def test_export_metrics_with_validation(self, exporter):
        """Test export with metric validation."""
        # Mock security to reject some metrics
        exporter.security.validate_metric_value = Mock(
            side_effect=lambda v: (False, "Invalid") if v > 100 else (True, None)
        )

        metrics_data = {"valid_metric": 50.0, "invalid_metric": 150.0}

        result = exporter.export_metrics(metrics_data)

        # Only valid metric should be exported
        assert "valid_metric" in result
        assert "invalid_metric" not in result


class TestPrometheusExporterHTTPServer:
    """Test HTTP server."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_start_server(self, exporter):
        """Test starting HTTP server."""
        with patch("telemetry_module.PROMETHEUS_AVAILABLE", True):
            with patch("telemetry_module.start_http_server") as mock_start:
                exporter.start_server()

                mock_start.assert_called_once()
                assert exporter.server_started == True

    def test_start_server_already_started(self, exporter):
        """Test starting server when already started."""
        exporter.server_started = True

        with patch("telemetry_module.PROMETHEUS_AVAILABLE", True):
            with patch("telemetry_module.start_http_server") as mock_start:
                exporter.start_server()

                # Should not start again
                mock_start.assert_not_called()

    def test_start_server_prometheus_unavailable(self, exporter):
        """Test starting server when Prometheus client is unavailable."""
        with patch("telemetry_module.PROMETHEUS_AVAILABLE", False):
            exporter.start_server()

            # Should not start
            assert exporter.server_started == False

    def test_get_metrics_text(self, exporter):
        """Test getting metrics in text format."""
        with patch("telemetry_module.PROMETHEUS_AVAILABLE", True):
            with patch("telemetry_module.generate_latest") as mock_generate:
                mock_generate.return_value = b"# Test metrics\n"

                text = exporter.get_metrics_text()

                assert text == "# Test metrics\n"


class TestPrometheusExporterErrorHandling:
    """Test error handling."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_handle_metric_not_found(self, exporter):
        """Test handling of metric not found."""
        # Should not raise exception
        exporter.set_metric("nonexistent_metric", 42.0)

        assert True

    def test_handle_set_exception(self, exporter):
        """Test handling of exception when setting metric."""
        # Register metric
        definition = MetricDefinition(
            name="test_metric", type=MetricType.GAUGE, description="Test metric"
        )
        exporter.register_metric(definition)

        # Mock metric to raise exception
        exporter.metrics["test_metric"] = Mock(side_effect=Exception("Set error"))

        # Should handle gracefully
        exporter.set_metric("test_metric", 42.0)

        assert True

    def test_handle_increment_exception(self, exporter):
        """Test handling of exception when incrementing metric."""
        # Register counter
        definition = MetricDefinition(
            name="test_counter", type=MetricType.COUNTER, description="Test counter"
        )
        exporter.register_metric(definition)

        # Mock metric to raise exception
        exporter.metrics["test_counter"] = Mock(
            side_effect=Exception("Increment error")
        )

        # Should handle gracefully
        exporter.increment_metric("test_counter")

        assert True


class TestPrometheusExporterEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def exporter(self, telemetry_config):
        security = MagicMock()
        return PrometheusExporter(telemetry_config, security)

    def test_export_empty_metrics(self, exporter):
        """Test exporting empty metrics."""
        result = exporter.export_metrics({})

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_export_metrics_with_none_value(self, exporter):
        """Test exporting metrics with None value."""
        metrics_data = {"metric1": 42.0, "metric2": None}

        result = exporter.export_metrics(metrics_data)

        # Should handle None gracefully
        assert isinstance(result, dict)

    def test_set_metric_zero_value(self, exporter):
        """Test setting metric to zero."""
        # Register metric
        definition = MetricDefinition(
            name="test_metric", type=MetricType.GAUGE, description="Test metric"
        )
        exporter.register_metric(definition)

        # Set to zero
        exporter.set_metric("test_metric", 0.0)

        # Should not raise exception
        assert True

    def test_set_metric_negative_value(self, exporter):
        """Test setting metric to negative value."""
        # Register metric
        definition = MetricDefinition(
            name="test_metric", type=MetricType.GAUGE, description="Test metric"
        )
        exporter.register_metric(definition)

        # Set to negative
        exporter.set_metric("test_metric", -42.0)

        # Should not raise exception (gauges can be negative)
        assert True

    def test_increment_counter_zero_amount(self, exporter):
        """Test incrementing counter by zero."""
        # Register counter
        definition = MetricDefinition(
            name="test_counter", type=MetricType.COUNTER, description="Test counter"
        )
        exporter.register_metric(definition)

        # Increment by zero
        exporter.increment_metric("test_counter", amount=0)

        # Should not raise exception
        assert True

    def test_increment_counter_negative_amount(self, exporter):
        """Test incrementing counter by negative amount."""
        # Register counter
        definition = MetricDefinition(
            name="test_counter", type=MetricType.COUNTER, description="Test counter"
        )
        exporter.register_metric(definition)

        # Increment by negative (should be allowed)
        exporter.increment_metric("test_counter", amount=-5)

        # Should not raise exception
        assert True
