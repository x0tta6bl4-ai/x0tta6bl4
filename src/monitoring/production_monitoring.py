"""
Production Monitoring for x0tta6bl4

Provides comprehensive monitoring for production deployment:
- Real-time metrics collection
- Alert thresholds
- Dashboard data
- Performance tracking
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)

# Prometheus metrics
production_requests_total = Counter(
    "production_requests_total",
    "Total production requests",
    ["method", "endpoint", "status"],
)

production_request_duration = Histogram(
    "production_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)

production_active_connections = Gauge(
    "production_active_connections", "Active connections"
)

production_memory_usage = Gauge(
    "production_memory_usage_bytes", "Memory usage in bytes"
)

production_cpu_usage = Gauge("production_cpu_usage_percent", "CPU usage percentage")

production_pqc_handshake_duration = Histogram(
    "production_pqc_handshake_duration_seconds",
    "PQC handshake duration",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
)

production_error_rate = Gauge("production_error_rate", "Error rate (0-1)")

production_throughput = Gauge(
    "production_throughput_per_second", "Throughput in requests per second"
)

# GTM Metrics
gtm_total_users = Gauge("gtm_total_users", "Total registered users")
gtm_new_users_24h = Gauge("gtm_new_users_24h", "New registrations in last 24h")
gtm_active_licenses = Gauge("gtm_active_licenses", "Total active licenses")
gtm_total_revenue = Gauge("gtm_total_revenue_rub", "Total revenue in RUB")
gtm_conversion_rate = Gauge("gtm_conversion_rate_percent", "Conversion rate percentage")


@dataclass
class AlertThreshold:
    """Alert threshold configuration"""

    metric_name: str
    threshold_value: float
    comparison: str  # 'gt', 'lt', 'eq'
    severity: str  # 'warning', 'critical'
    description: str


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""

    alert_thresholds: List[AlertThreshold] = field(default_factory=list)
    metrics_retention_hours: int = 24
    sample_interval_seconds: int = 10
    enable_alerting: bool = True


class ProductionMonitor:
    """
    Production monitoring system for x0tta6bl4.

    Features:
    - Real-time metrics collection
    - Alert thresholds
    - Performance tracking
    - Resource monitoring
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self.metrics_history: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

        # Load default alert thresholds
        self._load_default_thresholds()

        logger.info("Production Monitor initialized")

    def _load_default_thresholds(self):
        """Load default alert thresholds."""
        default_thresholds = [
            AlertThreshold(
                metric_name="error_rate",
                threshold_value=0.01,  # 1%
                comparison="gt",
                severity="warning",
                description="Error rate above 1%",
            ),
            AlertThreshold(
                metric_name="error_rate",
                threshold_value=0.05,  # 5%
                comparison="gt",
                severity="critical",
                description="Error rate above 5%",
            ),
            AlertThreshold(
                metric_name="latency_p95",
                threshold_value=150.0,  # ms
                comparison="gt",
                severity="warning",
                description="P95 latency above 150ms",
            ),
            AlertThreshold(
                metric_name="latency_p95",
                threshold_value=200.0,  # ms
                comparison="gt",
                severity="critical",
                description="P95 latency above 200ms",
            ),
            AlertThreshold(
                metric_name="memory_usage_mb",
                threshold_value=2000.0,  # MB
                comparison="gt",
                severity="warning",
                description="Memory usage above 2GB",
            ),
            AlertThreshold(
                metric_name="memory_usage_mb",
                threshold_value=2400.0,  # MB
                comparison="gt",
                severity="critical",
                description="Memory usage above 2.4GB",
            ),
            AlertThreshold(
                metric_name="cpu_usage_percent",
                threshold_value=80.0,  # %
                comparison="gt",
                severity="warning",
                description="CPU usage above 80%",
            ),
            AlertThreshold(
                metric_name="cpu_usage_percent",
                threshold_value=95.0,  # %
                comparison="gt",
                severity="critical",
                description="CPU usage above 95%",
            ),
            AlertThreshold(
                metric_name="throughput_per_sec",
                threshold_value=5000.0,  # req/sec
                comparison="lt",
                severity="warning",
                description="Throughput below 5000 req/sec",
            ),
        ]

        self.config.alert_thresholds.extend(default_thresholds)

    def record_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ):
        """Record a request metric."""
        production_requests_total.labels(
            method=method, endpoint=endpoint, status=status_code
        ).inc()

        production_request_duration.labels(method=method, endpoint=endpoint).observe(
            duration_seconds
        )

    def record_connection(self, active_count: int):
        """Record active connections."""
        production_active_connections.set(active_count)

    def record_memory(self, memory_bytes: int):
        """Record memory usage."""
        production_memory_usage.set(memory_bytes)

    def record_cpu(self, cpu_percent: float):
        """Record CPU usage."""
        production_cpu_usage.set(cpu_percent)

    def record_pqc_handshake(self, duration_seconds: float):
        """Record PQC handshake duration."""
        production_pqc_handshake_duration.observe(duration_seconds)

    def record_error_rate(self, error_rate: float):
        """Record error rate."""
        production_error_rate.set(error_rate)

    def record_throughput(self, throughput: float):
        """Record throughput."""
        production_throughput.set(throughput)

    def record_gtm_stats(self, stats: Dict[str, Any]):
        """Record GTM/Sales metrics."""
        gtm_total_users.set(stats.get("total_users", 0))
        gtm_new_users_24h.set(stats.get("new_users_24h", 0))
        gtm_active_licenses.set(stats.get("active_licenses", 0))
        gtm_total_revenue.set(stats.get("total_revenue", 0))
        gtm_conversion_rate.set(stats.get("conversion_rate", 0))

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect current metrics snapshot.

        Returns:
            Dictionary with current metrics
        """
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Memory
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        # CPU
        cpu_percent = process.cpu_percent(interval=0.1)

        # Active connections - query from mesh network or Prometheus
        active_connections = 0
        try:
            # Try to get from Prometheus metrics if available
            from prometheus_client import REGISTRY

            for collector in REGISTRY._collector_to_names:
                if (
                    hasattr(collector, "_name")
                    and "connections" in collector._name.lower()
                ):
                    active_connections = int(
                        collector._value.get() if hasattr(collector, "_value") else 0
                    )
                    break
        except Exception:
            pass

        # If not available from Prometheus, try mesh router stats
        if active_connections == 0:
            try:
                from src.network.mesh_router import MeshRouter

                # Try to get router instance (if available in context)
                router = getattr(self, "_mesh_router", None)
                if router:
                    stats = router.get_stats()
                    peers = stats.get("peers", [])
                    active_connections = sum(1 for p in peers if p.get("alive", False))
            except Exception:
                pass

        # Error rate - calculate from Prometheus metrics
        error_rate = 0.0
        try:
            from prometheus_client import REGISTRY

            total_requests = 0
            error_requests = 0
            for collector in REGISTRY._collector_to_names:
                if hasattr(collector, "_name"):
                    name = collector._name
                    if "requests_total" in name:
                        # Get samples
                        samples = (
                            list(collector.collect()[0].samples)
                            if hasattr(collector, "collect")
                            else []
                        )
                        for sample in samples:
                            labels = sample.labels if hasattr(sample, "labels") else {}
                            total_requests += (
                                sample.value if hasattr(sample, "value") else 0
                            )
                            if labels.get("status", "").startswith("4") or labels.get(
                                "status", ""
                            ).startswith("5"):
                                error_requests += (
                                    sample.value if hasattr(sample, "value") else 0
                                )
            if total_requests > 0:
                error_rate = error_requests / total_requests
            else:
                # No request counters found; fall back to explicit gauge if available.
                try:
                    error_rate = (
                        production_error_rate._value.get()
                        if hasattr(production_error_rate, "_value")
                        else 0.0
                    )
                except Exception:
                    pass
        except Exception:
            # Fallback: use production_error_rate gauge if available
            try:
                error_rate = (
                    production_error_rate._value.get()
                    if hasattr(production_error_rate, "_value")
                    else 0.0
                )
            except Exception:
                pass

        # Throughput - calculate from Prometheus metrics or recent history
        throughput = 0.0
        throughput_unknown = False
        try:
            # Use production_throughput gauge if available
            throughput = (
                production_throughput._value.get()
                if hasattr(production_throughput, "_value")
                else 0.0
            )
            if throughput == 0.0 and not self.metrics_history:
                # Treat the default gauge value as unknown until we have observations.
                throughput_unknown = True
        except Exception:
            # Calculate from metrics history
            if len(self.metrics_history) >= 2:
                recent = self.metrics_history[-10:]  # Last 10 samples
                if len(recent) > 1:
                    time_diff = (
                        datetime.fromisoformat(recent[-1]["timestamp"])
                        - datetime.fromisoformat(recent[0]["timestamp"])
                    ).total_seconds()
                    if time_diff > 0:
                        # Estimate requests per second from history
                        throughput = len(recent) / time_diff

        metrics = {
            "timestamp": datetime.now().isoformat(),
            "memory_usage_mb": memory_mb,
            "cpu_usage_percent": cpu_percent,
            "active_connections": active_connections,
            "error_rate": error_rate,
            "throughput_per_sec": throughput,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }

        # Store in history
        self.metrics_history.append(metrics)

        # Clean old metrics
        cutoff_time = datetime.now() - timedelta(
            hours=self.config.metrics_retention_hours
        )
        self.metrics_history = [
            m
            for m in self.metrics_history
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]

        # Check alerts
        if self.config.enable_alerting:
            self._check_alerts(metrics, throughput_unknown=throughput_unknown)

        return metrics

    def _check_alerts(self, metrics: Dict[str, Any], throughput_unknown: bool = False):
        """Check if any metrics exceed alert thresholds."""
        for threshold in self.config.alert_thresholds:
            metric_value = metrics.get(threshold.metric_name)

            if threshold.metric_name == "throughput_per_sec" and throughput_unknown:
                continue

            if metric_value is None:
                continue

            triggered = False

            if (
                threshold.comparison == "gt"
                and metric_value > threshold.threshold_value
            ):
                triggered = True
            elif (
                threshold.comparison == "lt"
                and metric_value < threshold.threshold_value
            ):
                triggered = True
            elif (
                threshold.comparison == "eq"
                and metric_value == threshold.threshold_value
            ):
                triggered = True

            if triggered:
                alert = {
                    "timestamp": datetime.now().isoformat(),
                    "metric_name": threshold.metric_name,
                    "metric_value": metric_value,
                    "threshold": threshold.threshold_value,
                    "severity": threshold.severity,
                    "description": threshold.description,
                }

                self.alerts.append(alert)

                # Send alert (would integrate with alerting system)
                logger.warning(
                    f"🚨 ALERT [{threshold.severity.upper()}]: "
                    f"{threshold.description} "
                    f"(value: {metric_value}, threshold: {threshold.threshold_value})"
                )

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for monitoring dashboard.

        Returns:
            Dictionary with dashboard data
        """
        current_metrics = self.collect_metrics()

        # Calculate statistics from history
        if self.metrics_history:
            memory_values = [m["memory_usage_mb"] for m in self.metrics_history]
            cpu_values = [m["cpu_usage_percent"] for m in self.metrics_history]

            memory_avg = sum(memory_values) / len(memory_values)
            memory_max = max(memory_values)
            cpu_avg = sum(cpu_values) / len(cpu_values)
            cpu_max = max(cpu_values)
        else:
            memory_avg = memory_max = cpu_avg = cpu_max = 0

        return {
            "current": current_metrics,
            "statistics": {
                "memory_avg_mb": memory_avg,
                "memory_max_mb": memory_max,
                "cpu_avg_percent": cpu_avg,
                "cpu_max_percent": cpu_max,
            },
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status for /health endpoint.

        Returns:
            Dictionary with health status
        """
        metrics = self.collect_metrics()

        # Determine health
        is_healthy = True
        issues = []

        if metrics["error_rate"] > 0.05:
            is_healthy = False
            issues.append("High error rate")

        if metrics["memory_usage_mb"] > 2400:
            is_healthy = False
            issues.append("High memory usage")

        if metrics["cpu_usage_percent"] > 95:
            is_healthy = False
            issues.append("High CPU usage")

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": metrics["uptime_seconds"],
            "metrics": metrics,
            "issues": issues,
        }


# Global instance
_production_monitor: Optional[ProductionMonitor] = None


def get_production_monitor() -> ProductionMonitor:
    """Get global ProductionMonitor instance."""
    global _production_monitor
    if _production_monitor is None:
        _production_monitor = ProductionMonitor()
    return _production_monitor
