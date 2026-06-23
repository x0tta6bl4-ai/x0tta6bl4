"""Prometheus exporter for eBPF metrics."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .utils import with_retry, RetryConfig

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """Handles Prometheus metric export with graceful degradation"""

    def __init__(self, port: int = 9090):
        self.port = port
        self.metrics: Dict[str, Any] = {}
        self._server_started = False
        self._fallback_file = Path("/tmp/ebpf_metrics_fallback.json")  # nosec B108
        self.degradation = DegradationState()
        self.slog = StructuredLogger(__name__)

        if not PROMETHEUS_AVAILABLE:
            self.slog.warning(
                "prometheus_client not available, using fallback mode",
                degradation_level=DegradationLevel.DEGRADED.value,
            )
            self.degradation.prometheus_available = False
            self.degradation._recalculate_level()

    @with_retry(
        config=RetryConfig(max_retries=3, base_delay=2.0),
        exceptions=(OSError, Exception),
    )
    def start_server(self) -> bool:
        """Start Prometheus HTTP server with retry logic"""
        if not PROMETHEUS_AVAILABLE:
            return False

        if self._server_started:
            return True

        try:
            start_http_server(self.port)
            self._server_started = True
            self.degradation.update_prometheus_status(True)
            self.slog.info("Prometheus metrics server started", port=self.port)
            return True
        except OSError as e:
            self.degradation.update_prometheus_status(False)
            self.slog.error(
                "Failed to start Prometheus server", error=e, port=self.port
            )
            raise PrometheusExportError(
                f"Failed to start Prometheus server on port {self.port}",
                {"port": self.port, "error": str(e)},
            )

    def create_gauge(
        self, name: str, description: str, labels: List[str] = None
    ) -> Optional[Any]:
        """Create a Prometheus Gauge metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            metric = Gauge(name, description, labels or [])
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error("Failed to create gauge metric", error=e, metric_name=name)
            raise MetricRegistrationError(
                f"Failed to create gauge '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def create_counter(
        self, name: str, description: str, labels: List[str] = None
    ) -> Optional[Any]:
        """Create a Prometheus Counter metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            metric = Counter(name, description, labels or [])
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error(
                "Failed to create counter metric", error=e, metric_name=name
            )
            raise MetricRegistrationError(
                f"Failed to create counter '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def create_histogram(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: tuple = None,
    ) -> Optional[Any]:
        """Create a Prometheus Histogram metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            kwargs = {"labelnames": labels or []}
            if buckets:
                kwargs["buckets"] = buckets

            metric = Histogram(name, description, **kwargs)
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error(
                "Failed to create histogram metric", error=e, metric_name=name
            )
            raise MetricRegistrationError(
                f"Failed to create histogram '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def export_to_fallback(self, metrics: Dict[str, Any]):
        """Export metrics to fallback file when Prometheus unavailable"""
        try:
            data = {
                "timestamp": time.time(),
                "metrics": metrics,
                "degradation_level": self.degradation.level.value,
            }

            with open(self._fallback_file, "w") as f:
                json.dump(data, f, indent=2)

            self.slog.debug(
                "Metrics exported to fallback file", file=str(self._fallback_file)
            )
        except Exception as e:
            self.slog.error(
                "Failed to export to fallback file",
                error=e,
                file=str(self._fallback_file),
            )


# ==================== Main Exporter Class ====================


