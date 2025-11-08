"""Prometheus metrics exporter for x0tta6bl4 mesh.

Exports key metrics:
- mesh_peers_count: Number of connected mesh peers
- mesh_latency_seconds: Latency to mesh peers (histogram)
- mape_k_cycle_duration_seconds: MAPE-K self-healing loop duration
- http_requests_total: HTTP request counter
- http_request_duration_seconds: HTTP request duration histogram
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Optional

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

# Mesh metrics
mesh_peers_count = Gauge(
    "mesh_peers_count",
    "Number of connected mesh peers",
    ["node_id"],
)

mesh_latency_seconds = Histogram(
    "mesh_latency_seconds",
    "Latency to mesh peers in seconds",
    ["node_id", "peer_id"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Self-healing metrics
mape_k_cycle_duration_seconds = Histogram(
    "mape_k_cycle_duration_seconds",
    "Duration of MAPE-K self-healing cycle",
    ["phase"],  # monitor, analyze, plan, execute, knowledge
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

self_healing_events_total = Counter(
    "self_healing_events_total",
    "Total self-healing events triggered",
    ["event_type", "node_id"],  # node_failure, network_partition, high_latency, etc.
)

self_healing_mttr_seconds = Histogram(
    "self_healing_mttr_seconds",
    "Mean Time To Recovery (MTTR) in seconds",
    ["recovery_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

# Node health metrics
node_health_status = Gauge(
    "node_health_status",
    "Node health status (1=healthy, 0=unhealthy)",
    ["node_id"],
)

node_uptime_seconds = Gauge(
    "node_uptime_seconds",
    "Node uptime in seconds",
    ["node_id"],
)


class MetricsMiddleware:
    """FastAPI middleware for automatic HTTP metrics collection."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Skip metrics endpoint to avoid recursion
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        status_code = 500  # Default to 500 in case of unhandled exception

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            http_requests_total.labels(method=method, endpoint=path, status=status_code).inc()
            http_request_duration_seconds.labels(method=method, endpoint=path).observe(duration)


def get_metrics() -> Response:
    """FastAPI endpoint to expose Prometheus metrics.

    Returns:
        Response with Prometheus exposition format
    """
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


def update_mesh_peer_count(node_id: str, count: int):
    """Update mesh peer count metric."""
    mesh_peers_count.labels(node_id=node_id).set(count)


def record_mesh_latency(node_id: str, peer_id: str, latency: float):
    """Record mesh peer latency."""
    mesh_latency_seconds.labels(node_id=node_id, peer_id=peer_id).observe(latency)


def record_mape_k_cycle(phase: str, duration: float):
    """Record MAPE-K cycle duration."""
    mape_k_cycle_duration_seconds.labels(phase=phase).observe(duration)


def record_self_healing_event(event_type: str, node_id: str):
    """Increment self-healing event counter."""
    self_healing_events_total.labels(event_type=event_type, node_id=node_id).inc()


def record_mttr(recovery_type: str, mttr: float):
    """Record Mean Time To Recovery."""
    self_healing_mttr_seconds.labels(recovery_type=recovery_type).observe(mttr)


def set_node_health(node_id: str, is_healthy: bool):
    """Set node health status (1=healthy, 0=unhealthy)."""
    node_health_status.labels(node_id=node_id).set(1 if is_healthy else 0)


def set_node_uptime(node_id: str, uptime_seconds: float):
    """Set node uptime in seconds."""
    node_uptime_seconds.labels(node_id=node_id).set(uptime_seconds)
