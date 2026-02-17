"""
Prometheus Exporter for eBPF Telemetry.

Export metrics to Prometheus format.
"""
import logging
from typing import Any, Dict, Optional

from .models import TelemetryConfig, MetricDefinition, MetricType
from .security import SecurityManager

logger = logging.getLogger(__name__)

# Try to import prometheus_client
PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
    logger.info("Prometheus client available")
except ImportError:
    logger.warning("Prometheus client not available - metrics export limited")


class PrometheusExporter:
    """
    Export metrics to Prometheus format.

    Features:
    - Automatic metric type detection
    - Label support
    - Histogram buckets
    - HTTP endpoint
    """

    def __init__(self, config: TelemetryConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.metrics: Dict[str, Any] = {}
        self.metric_definitions: Dict[str, MetricDefinition] = {}
        self.registry = CollectorRegistry() if PROMETHEUS_AVAILABLE else None
        self.server_started = False

        if PROMETHEUS_AVAILABLE:
            logger.info("PrometheusExporter initialized")
        else:
            logger.warning("Prometheus client not available")

    def start_server(self):
        """Start Prometheus HTTP server."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Cannot start Prometheus server - client not available")
            return

        if self.server_started:
            logger.warning("Prometheus server already started")
            return

        try:
            start_http_server(
                port=self.config.prometheus_port,
                addr=self.config.prometheus_host,
                registry=self.registry,
            )
            self.server_started = True
            logger.info(
                f"Prometheus server started on "
                f"{self.config.prometheus_host}:{self.config.prometheus_port}"
            )
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")

    def register_metric(self, definition: MetricDefinition):
        """
        Register a metric definition.

        Args:
            definition: MetricDefinition object
        """
        if not PROMETHEUS_AVAILABLE:
            return

        # Validate metric name
        is_valid, error = self.security.validate_metric_name(definition.name)
        if not is_valid:
            logger.error(f"Invalid metric name {definition.name}: {error}")
            return

        self.metric_definitions[definition.name] = definition

        try:
            if definition.type == MetricType.COUNTER:
                metric = Counter(
                    definition.name,
                    definition.description or definition.help_text,
                    definition.labels,
                    registry=self.registry,
                )
            elif definition.type == MetricType.GAUGE:
                metric = Gauge(
                    definition.name,
                    definition.description or definition.help_text,
                    definition.labels,
                    registry=self.registry,
                )
            elif definition.type == MetricType.HISTOGRAM:
                metric = Histogram(
                    definition.name,
                    definition.description or definition.help_text,
                    definition.labels,
                    registry=self.registry,
                )
            elif definition.type == MetricType.SUMMARY:
                metric = Summary(
                    definition.name,
                    definition.description or definition.help_text,
                    definition.labels,
                    registry=self.registry,
                )
            else:
                logger.error(f"Unknown metric type: {definition.type}")
                return

            self.metrics[definition.name] = metric
            logger.debug(f"Registered metric: {definition.name}")

        except Exception as e:
            logger.error(f"Failed to register metric {definition.name}: {e}")

    def set_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return

        # Validate value
        is_valid, error = self.security.validate_metric_value(value)
        if not is_valid:
            logger.warning(f"Invalid value for metric {name}: {error}")
            return

        try:
            metric = self.metrics[name]

            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)

        except Exception as e:
            logger.error(f"Failed to set metric {name}: {e}")

    def increment_metric(
        self,
        name: str,
        amount: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Increment counter metric.

        Args:
            name: Metric name
            amount: Amount to increment
            labels: Optional labels
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return

        try:
            metric = self.metrics[name]

            if labels:
                metric.labels(**labels).inc(amount)
            else:
                metric.inc(amount)

        except Exception as e:
            logger.error(f"Failed to increment metric {name}: {e}")

    def export_metrics(self, metrics_data: Dict[str, Any]):
        """
        Export multiple metrics.

        Args:
            metrics_data: Dictionary of metric_name -> value
        """
        for name, value in metrics_data.items():
            # Auto-register if not exists
            if name not in self.metrics:
                metric_type = MetricType.GAUGE
                if "total" in name or "count" in name:
                    metric_type = MetricType.COUNTER

                definition = MetricDefinition(
                    name=name,
                    type=metric_type,
                    description=f"Auto-registered metric: {name}",
                )
                self.register_metric(definition)

            # Set value
            self.set_metric(name, float(value))

    def get_metrics_text(self) -> str:
        """
        Get metrics in Prometheus text format.

        Returns:
            Metrics as text
        """
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available\n"

        try:
            return generate_latest(self.registry).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return "# Error generating metrics\n"
