"""
Metrics Collection System for Proxy Infrastructure.

Implements:
- Real-time metrics aggregation
- Time-series data storage
- Performance analytics
- Alerting on anomalies
"""

import asyncio
import hashlib
import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "proxy-metrics-collector"
_SERVICE_LAYER = "network_proxy_metrics_observed_state"
PROXY_METRICS_COLLECTOR_CLAIM_BOUNDARY = (
    "Local proxy metrics collector observed-state evidence only. It records "
    "redacted proxy request, health, domain-request, and alert aggregation "
    "metadata with proxy, domain, and error identifiers hashed. It does not "
    "copy proxy hosts, credentials, target domains, URLs, headers, request "
    "bodies, response payloads, or raw metric labels, and it does not prove "
    "provider reachability, customer traffic delivery, or end-to-end dataplane "
    "quality."
)


def _hash_value(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Single metric value with timestamp."""

    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metric values."""

    name: str
    metric_type: MetricType
    description: str
    values: List[MetricValue] = field(default_factory=list)
    retention_seconds: int = 86400  # 24 hours default

    def add(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a new value to the series."""
        # Clean old values
        cutoff = time.time() - self.retention_seconds
        self.values = [v for v in self.values if v.timestamp > cutoff]

        self.values.append(
            MetricValue(value=value, timestamp=time.time(), labels=labels or {})
        )

    def get_latest(self) -> Optional[float]:
        """Get the latest value."""
        if not self.values:
            return None
        return self.values[-1].value

    def get_average(self, window_seconds: int = 300) -> Optional[float]:
        """Get average over time window."""
        cutoff = time.time() - window_seconds
        recent = [v.value for v in self.values if v.timestamp > cutoff]
        if not recent:
            return None
        return statistics.mean(recent)

    def get_percentile(
        self, percentile: float, window_seconds: int = 300
    ) -> Optional[float]:
        """Get percentile over time window."""
        cutoff = time.time() - window_seconds
        recent = sorted([v.value for v in self.values if v.timestamp > cutoff])
        if not recent:
            return None

        index = int(len(recent) * percentile / 100)
        return recent[min(index, len(recent) - 1)]

    def get_rate(self, window_seconds: int = 60) -> float:
        """Get rate of change (for counters)."""
        cutoff = time.time() - window_seconds
        recent = [v for v in self.values if v.timestamp > cutoff]
        if len(recent) < 2:
            return 0.0

        values = [v.value for v in recent]
        return (values[-1] - values[0]) / window_seconds


@dataclass
class ProxyMetricsSnapshot:
    """Snapshot of proxy metrics at a point in time."""

    timestamp: float
    proxy_id: str

    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0

    # Latency metrics (ms)
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0

    # Error breakdown
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    # Health status
    health_status: str = "unknown"
    consecutive_failures: int = 0

    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "proxy_id": self.proxy_id,
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "blocked": self.blocked_requests,
                "success_rate": round(self.success_rate(), 4),
            },
            "latency_ms": {
                "avg": round(self.avg_latency, 2),
                "p50": round(self.p50_latency, 2),
                "p95": round(self.p95_latency, 2),
                "p99": round(self.p99_latency, 2),
            },
            "errors": self.errors_by_type,
            "health": {
                "status": self.health_status,
                "consecutive_failures": self.consecutive_failures,
            },
        }


class ProxyMetricsCollector:
    """
    Centralized metrics collector for proxy infrastructure.
    """

    def __init__(
        self,
        retention_hours: int = 24,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.retention_hours = retention_hours
        self.metrics: Dict[str, MetricSeries] = {}
        self.proxy_snapshots: Dict[str, List[ProxyMetricsSnapshot]] = defaultdict(list)
        self._alert_handlers: List[Callable] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._aggregation_task: Optional[asyncio.Task] = None
        self.event_bus = event_bus
        self.event_project_root = event_project_root

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize proxy-metrics EventBus: %s", exc)
            return None

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {field: bool(value) for field, value in identity.items()}

    def _configured_metrics(self, names: List[str]) -> Dict[str, bool]:
        return {name: name in self.metrics for name in names}

    def _publish_observed_state(
        self,
        *,
        operation: str,
        status: str,
        success: bool,
        duration_ms: float,
        payload: Dict[str, Any],
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None
        event_payload = {
            "component": "network.proxy_metrics_collector",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status,
            "success": bool(success),
            "duration_ms": round(float(duration_ms), 3),
            "service_identity_present": self._service_identity_presence(),
            "raw_identifiers_redacted": True,
            "claim_boundary": PROXY_METRICS_COLLECTOR_CLAIM_BOUNDARY,
            **payload,
        }
        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                _SERVICE_AGENT,
                event_payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish proxy metrics evidence: %s", exc)
            return None

    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        retention_seconds: Optional[int] = None,
    ):
        """Register a new metric series."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(
                name=name,
                metric_type=metric_type,
                description=description,
                retention_seconds=retention_seconds or (self.retention_hours * 3600),
            )

    async def record(
        self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None
    ):
        """Record a metric value."""
        async with self._lock:
            if metric_name not in self.metrics:
                logger.warning(f"Unknown metric: {metric_name}")
                return

            self.metrics[metric_name].add(value, labels)

    async def record_proxy_request(
        self,
        proxy_id: str,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None,
    ):
        """Record a proxy request result."""
        started = time.perf_counter()
        await self.record("proxy_requests_total", 1, {"proxy_id": proxy_id})

        metric_names = ["proxy_requests_total", "proxy_latency_ms"]
        if success:
            await self.record("proxy_requests_success", 1, {"proxy_id": proxy_id})
            metric_names.append("proxy_requests_success")
        else:
            await self.record(
                "proxy_requests_failed",
                1,
                {"proxy_id": proxy_id, "error_type": error_type or "unknown"},
            )
            metric_names.append("proxy_requests_failed")

        await self.record("proxy_latency_ms", latency_ms, {"proxy_id": proxy_id})
        self._publish_observed_state(
            operation="record_proxy_request",
            status="proxy_request_metric_recorded",
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "proxy_id_hash": _hash_value(proxy_id),
                "request_success": bool(success),
                "latency_ms": round(float(latency_ms), 3),
                "error_type_present": bool(error_type),
                "error_type_hash": _hash_value(error_type),
                "metrics_configured": self._configured_metrics(metric_names),
            },
        )

    async def record_proxy_health(
        self, proxy_id: str, is_healthy: bool, response_time_ms: float
    ):
        """Record proxy health check result."""
        started = time.perf_counter()
        await self.record(
            "proxy_health_check", 1 if is_healthy else 0, {"proxy_id": proxy_id}
        )
        await self.record(
            "proxy_health_response_time_ms", response_time_ms, {"proxy_id": proxy_id}
        )
        metric_names = ["proxy_health_check", "proxy_health_response_time_ms"]
        self._publish_observed_state(
            operation="record_proxy_health",
            status="proxy_health_metric_recorded",
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "proxy_id_hash": _hash_value(proxy_id),
                "is_healthy": bool(is_healthy),
                "response_time_ms": round(float(response_time_ms), 3),
                "health_value": 1 if is_healthy else 0,
                "metrics_configured": self._configured_metrics(metric_names),
            },
        )

    async def record_domain_request(
        self, domain: str, proxy_id: str, success: bool, latency_ms: float
    ):
        """Record a domain request."""
        started = time.perf_counter()
        await self.record(
            "domain_requests_total", 1, {"domain": domain, "proxy_id": proxy_id}
        )

        metric_names = ["domain_requests_total"]
        if success:
            await self.record(
                "domain_requests_success", 1, {"domain": domain, "proxy_id": proxy_id}
            )
            metric_names.append("domain_requests_success")
        else:
            await self.record(
                "domain_requests_failed", 1, {"domain": domain, "proxy_id": proxy_id}
            )
            metric_names.append("domain_requests_failed")
        self._publish_observed_state(
            operation="record_domain_request",
            status="domain_request_metric_recorded",
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "domain_hash": _hash_value(domain),
                "proxy_id_hash": _hash_value(proxy_id),
                "request_success": bool(success),
                "latency_ms": round(float(latency_ms), 3),
                "metrics_configured": self._configured_metrics(metric_names),
            },
        )

    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series."""
        return self.metrics.get(name)

    def get_proxy_metrics(
        self, proxy_id: str, window_seconds: int = 300
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a proxy."""
        result = {"proxy_id": proxy_id, "window_seconds": window_seconds, "metrics": {}}

        for name, series in self.metrics.items():
            # Filter by proxy_id label
            cutoff = time.time() - window_seconds
            values = [
                v.value
                for v in series.values
                if v.timestamp > cutoff and v.labels.get("proxy_id") == proxy_id
            ]

            if values:
                result["metrics"][name] = {
                    "count": len(values),
                    "latest": values[-1],
                    "avg": round(statistics.mean(values), 3),
                    "min": round(min(values), 3),
                    "max": round(max(values), 3),
                }

        return result

    def get_global_metrics(self, window_seconds: int = 300) -> Dict[str, Any]:
        """Get global aggregated metrics."""
        result = {
            "window_seconds": window_seconds,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {},
        }

        for name, series in self.metrics.items():
            cutoff = time.time() - window_seconds
            values = [v.value for v in series.values if v.timestamp > cutoff]

            if values:
                result["metrics"][name] = {
                    "count": len(values),
                    "rate_per_second": round(len(values) / window_seconds, 3),
                    "avg": round(statistics.mean(values), 3),
                    "p95": round(
                        sorted(values)[int(len(values) * 0.95)] if values else 0, 3
                    ),
                }

        return result

    def add_alert_handler(self, handler: Callable):
        """Add an alert handler callback."""
        self._alert_handlers.append(handler)

    async def _check_alerts(self):
        """Check for alert conditions."""
        started = time.perf_counter()
        alerts = []
        failure_rate = None
        p95_latency = None
        handler_errors = 0

        # Check for high failure rate
        failure_series = self.metrics.get("proxy_requests_failed")
        if failure_series:
            failure_rate = failure_series.get_rate(window_seconds=300)
            if failure_rate and failure_rate > 0.1:  # > 10% failure rate
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "high_failure_rate",
                        "message": f"High proxy failure rate: {failure_rate:.2%}",
                        "value": failure_rate,
                    }
                )

        # Check for high latency
        latency_series = self.metrics.get("proxy_latency_ms")
        if latency_series:
            p95_latency = latency_series.get_percentile(95, window_seconds=300)
            if p95_latency and p95_latency > 2000:  # > 2s p95 latency
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "high_latency",
                        "message": f"High P95 latency: {p95_latency:.0f}ms",
                        "value": p95_latency,
                    }
                )

        # Notify handlers
        for alert in alerts:
            for handler in self._alert_handlers:
                try:
                    await handler(alert)
                except Exception as e:
                    handler_errors += 1
                    logger.error(f"Alert handler error: {e}")

        self._publish_observed_state(
            operation="check_alerts",
            status="alerts_detected" if alerts else "no_alerts",
            success=handler_errors == 0,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "alerts_count": len(alerts),
                "alert_types": [alert["type"] for alert in alerts],
                "handler_count": len(self._alert_handlers),
                "handler_errors": handler_errors,
                "failure_rate_5m": (
                    round(float(failure_rate), 6)
                    if failure_rate is not None
                    else None
                ),
                "p95_latency_ms_5m": (
                    round(float(p95_latency), 3)
                    if p95_latency is not None
                    else None
                ),
                "metric_value_counts": {
                    "proxy_requests_failed": (
                        len(failure_series.values) if failure_series else 0
                    ),
                    "proxy_latency_ms": (
                        len(latency_series.values) if latency_series else 0
                    ),
                },
            },
        )

    async def _aggregation_loop(self):
        """Background loop for metric aggregation and alerting."""
        while self._running:
            try:
                await self._check_alerts()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation loop error: {e}")
                await asyncio.sleep(10)

    async def start(self):
        """Start the metrics collector."""
        self._running = True
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())
        logger.info("Metrics collector started")

    async def stop(self):
        """Stop the metrics collector."""
        self._running = False
        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics collector stopped")

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for name, series in self.metrics.items():
            lines.append(f"# HELP {name} {series.description}")
            lines.append(f"# TYPE {name} {series.metric_type.value}")

            # Get latest values with labels
            for value in series.values[-100:]:  # Last 100 values
                label_str = ",".join(f'{k}="{v}"' for k, v in value.labels.items())
                if label_str:
                    lines.append(f"{name}{{{label_str}}} {value.value}")
                else:
                    lines.append(f"{name} {value.value}")

        return "\n".join(lines)

    def export_json(self) -> Dict[str, Any]:
        """Export all metrics as JSON."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                name: {
                    "type": series.metric_type.value,
                    "description": series.description,
                    "latest": series.get_latest(),
                    "avg_5m": series.get_average(300),
                    "p95_5m": series.get_percentile(95, 300),
                }
                for name, series in self.metrics.items()
            },
        }


# Pre-configured metrics for proxy infrastructure
DEFAULT_METRICS = [
    ("proxy_requests_total", MetricType.COUNTER, "Total proxy requests"),
    ("proxy_requests_success", MetricType.COUNTER, "Successful proxy requests"),
    ("proxy_requests_failed", MetricType.COUNTER, "Failed proxy requests"),
    ("proxy_requests_blocked", MetricType.COUNTER, "Blocked proxy requests"),
    ("proxy_latency_ms", MetricType.HISTOGRAM, "Proxy request latency in ms"),
    ("proxy_health_check", MetricType.GAUGE, "Proxy health check status (1=healthy)"),
    (
        "proxy_health_response_time_ms",
        MetricType.HISTOGRAM,
        "Proxy health check response time",
    ),
    ("proxy_active_connections", MetricType.GAUGE, "Active proxy connections"),
    ("domain_requests_total", MetricType.COUNTER, "Total domain requests"),
    ("domain_requests_success", MetricType.COUNTER, "Successful domain requests"),
    ("domain_requests_failed", MetricType.COUNTER, "Failed domain requests"),
    (
        "selection_algorithm_calls",
        MetricType.COUNTER,
        "Proxy selection algorithm calls",
    ),
    (
        "selection_algorithm_latency_ms",
        MetricType.HISTOGRAM,
        "Selection algorithm latency",
    ),
]


def create_default_collector(
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
) -> ProxyMetricsCollector:
    """Create a collector with default metrics pre-registered."""
    collector = ProxyMetricsCollector(
        event_bus=event_bus,
        event_project_root=event_project_root,
    )

    for name, metric_type, description in DEFAULT_METRICS:
        collector.register_metric(name, metric_type, description)

    return collector
