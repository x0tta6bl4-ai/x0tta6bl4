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

node_spiffe_attested = Gauge(
    "node_spiffe_attested",
    "Node SPIFFE attestation status (1=attested, 0=unattested)",
    ["node_id", "spiffe_id"],
)

# Obfuscation metrics
heartbeat_obfuscated_total = Counter(
    "heartbeat_obfuscated_total",
    "Total obfuscated heartbeats sent"
)

# Traffic shaping metrics
traffic_shaped_packets_total = Counter(
    "traffic_shaped_packets_total",
    "Total packets shaped by traffic shaper",
    ["node_id", "profile"],
)

traffic_shaping_bytes_total = Counter(
    "traffic_shaping_bytes_total",
    "Total bytes of shaped traffic",
    ["node_id", "profile"],
)

traffic_shaping_padding_bytes_total = Counter(
    "traffic_shaping_padding_bytes_total",
    "Total padding bytes added by traffic shaper",
    ["node_id", "profile"],
)

traffic_shaping_delay_seconds = Histogram(
    "traffic_shaping_delay_seconds",
    "Delay added by traffic shaper in seconds",
    ["node_id", "profile"],
    buckets=(0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5),
)

traffic_profile_active = Gauge(
    "traffic_profile_active",
    "Currently active traffic profile (1=active)",
    ["node_id", "profile"],
)

# eBPF telemetry metrics
ebpf_cpu_overhead_percent = Gauge(
    "ebpf_cpu_overhead_percent",
    "eBPF telemetry CPU overhead percentage",
    ["node_id", "program_type"],
)

ebpf_memory_bytes = Gauge(
    "ebpf_memory_bytes",
    "eBPF program memory usage in bytes",
    ["node_id", "program_id"],
)

ebpf_packets_processed_total = Counter(
    "ebpf_packets_processed_total",
    "Total packets processed by eBPF programs",
    ["node_id", "program_id", "direction"],
)

ebpf_packet_drops_total = Counter(
    "ebpf_packet_drops_total",
    "Total packets dropped by eBPF programs",
    ["node_id", "program_id", "reason"],
)

ebpf_program_load_time_seconds = Histogram(
    "ebpf_program_load_time_seconds",
    "Time to load eBPF program",
    ["node_id", "program_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
)

# Slot-based synchronization metrics
slot_sync_beacon_collisions_total = Counter(
    "slot_sync_beacon_collisions_total",
    "Total beacon collisions in slot-based synchronization",
    ["node_id"],
)

slot_sync_resync_time_seconds = Histogram(
    "slot_sync_resync_time_seconds",
    "Time to resynchronize slot after collision",
    ["node_id"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

slot_sync_success_rate = Gauge(
    "slot_sync_success_rate",
    "Slot synchronization success rate (0-1)",
    ["node_id"],
)

mesh_topology_changes_total = Counter(
    "mesh_topology_changes_total",
    "Total mesh topology changes",
    ["node_id", "change_type"],  # node_added, node_removed, link_added, link_removed
)

k_disjoint_paths_count = Gauge(
    "k_disjoint_paths_count",
    "Number of k-disjoint paths available",
    ["node_id", "destination"],
)

k_disjoint_path_cache_hits_total = Counter(
    "k_disjoint_path_cache_hits_total",
    "Total k-disjoint path cache hits",
    ["node_id"],
)

k_disjoint_path_cache_misses_total = Counter(
    "k_disjoint_path_cache_misses_total",
    "Total k-disjoint path cache misses",
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


def set_node_spiffe_attested(node_id: str, spiffe_id: str, is_attested: bool):
    """Set node SPIFFE attestation status."""
    node_spiffe_attested.labels(node_id=node_id, spiffe_id=spiffe_id).set(1 if is_attested else 0)


# eBPF telemetry metric helpers
def record_ebpf_cpu_overhead(node_id: str, program_type: str, overhead_percent: float):
    """Record eBPF CPU overhead."""
    ebpf_cpu_overhead_percent.labels(node_id=node_id, program_type=program_type).set(overhead_percent)


def record_ebpf_memory(node_id: str, program_id: str, memory_bytes: int):
    """Record eBPF program memory usage."""
    ebpf_memory_bytes.labels(node_id=node_id, program_id=program_id).set(memory_bytes)


def record_ebpf_packets(node_id: str, program_id: str, direction: str, count: int = 1):
    """Record eBPF packets processed."""
    ebpf_packets_processed_total.labels(node_id=node_id, program_id=program_id, direction=direction).inc(count)


def record_ebpf_drops(node_id: str, program_id: str, reason: str, count: int = 1):
    """Record eBPF packet drops."""
    ebpf_packet_drops_total.labels(node_id=node_id, program_id=program_id, reason=reason).inc(count)


def record_ebpf_load_time(node_id: str, program_type: str, load_time: float):
    """Record eBPF program load time."""
    ebpf_program_load_time_seconds.labels(node_id=node_id, program_type=program_type).observe(load_time)


# Slot-based synchronization metric helpers
def record_slot_sync_collision(node_id: str):
    """Record slot synchronization beacon collision."""
    slot_sync_beacon_collisions_total.labels(node_id=node_id).inc()


def record_slot_sync_resync_time(node_id: str, resync_time: float):
    """Record slot resynchronization time."""
    slot_sync_resync_time_seconds.labels(node_id=node_id).observe(resync_time)


def set_slot_sync_success_rate(node_id: str, success_rate: float):
    """Set slot synchronization success rate (0-1)."""
    slot_sync_success_rate.labels(node_id=node_id).set(success_rate)


# Mesh topology metric helpers
def record_topology_change(node_id: str, change_type: str):
    """Record mesh topology change."""
    mesh_topology_changes_total.labels(node_id=node_id, change_type=change_type).inc()


# k-disjoint paths metric helpers
def set_k_disjoint_paths_count(node_id: str, destination: str, count: int):
    """Set number of k-disjoint paths available."""
    k_disjoint_paths_count.labels(node_id=node_id, destination=destination).set(count)


def record_k_disjoint_cache_hit(node_id: str):
    """Record k-disjoint path cache hit."""
    k_disjoint_path_cache_hits_total.labels(node_id=node_id).inc()


def record_k_disjoint_cache_miss(node_id: str):
    """Record k-disjoint path cache miss."""
    k_disjoint_path_cache_misses_total.labels(node_id=node_id).inc()
