"""
Edge Computing and Event Sourcing Prometheus Metrics
=====================================================

Comprehensive metrics for Edge Computing and Event Sourcing modules.
Integrates with the existing metrics infrastructure.

Metrics Categories:
- Edge Node metrics (registration, status, resources)
- Task Distribution metrics (submission, completion, latency)
- Edge Cache metrics (hits, misses, evictions)
- Event Store metrics (append, read, streams)
- Command Bus metrics (execution, latency)
- Query Bus metrics (execution, cache)
- Projection metrics (processing, lag)
"""

import logging
import time
from typing import Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry

logger = logging.getLogger(__name__)

# Use the existing metrics registry
try:
    from src.monitoring.metrics import _metrics_registry as registry
except ImportError:
    registry = CollectorRegistry()


# =============================================================================
# Edge Computing Metrics
# =============================================================================

# Edge Node Metrics
edge_nodes_total = Gauge(
    "x0tta6bl4_edge_nodes_total",
    "Total number of registered edge nodes",
    ["status"],  # active, inactive, draining
    registry=registry,
)

edge_node_registration_total = Counter(
    "x0tta6bl4_edge_node_registration_total",
    "Total edge node registrations",
    ["status"],  # success, failed
    registry=registry,
)

edge_node_registration_duration = Histogram(
    "x0tta6bl4_edge_node_registration_duration_seconds",
    "Duration of edge node registration",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry,
)

edge_node_heartbeat_total = Counter(
    "x0tta6bl4_edge_node_heartbeat_total",
    "Total heartbeats received from edge nodes",
    ["node_id"],
    registry=registry,
)

edge_node_resource_cpu = Gauge(
    "x0tta6bl4_edge_node_resource_cpu_percent",
    "CPU usage percent on edge node",
    ["node_id"],
    registry=registry,
)

edge_node_resource_memory = Gauge(
    "x0tta6bl4_edge_node_resource_memory_percent",
    "Memory usage percent on edge node",
    ["node_id"],
    registry=registry,
)

edge_node_resource_gpu = Gauge(
    "x0tta6bl4_edge_node_resource_gpu_percent",
    "GPU usage percent on edge node",
    ["node_id"],
    registry=registry,
)

edge_node_drain_total = Counter(
    "x0tta6bl4_edge_node_drain_total",
    "Total edge node drain operations",
    ["status"],  # success, failed
    registry=registry,
)

# Task Distribution Metrics
edge_tasks_submitted_total = Counter(
    "x0tta6bl4_edge_tasks_submitted_total",
    "Total tasks submitted to edge nodes",
    ["task_type", "priority"],
    registry=registry,
)

edge_tasks_completed_total = Counter(
    "x0tta6bl4_edge_tasks_completed_total",
    "Total tasks completed by edge nodes",
    ["task_type", "status"],  # status: success, failed, cancelled
    registry=registry,
)

edge_tasks_active = Gauge(
    "x0tta6bl4_edge_tasks_active",
    "Number of currently active tasks",
    ["node_id"],
    registry=registry,
)

edge_tasks_queued = Gauge(
    "x0tta6bl4_edge_tasks_queued",
    "Number of queued tasks waiting for assignment",
    registry=registry,
)

edge_task_submission_duration = Histogram(
    "x0tta6bl4_edge_task_submission_duration_seconds",
    "Duration of task submission",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
    registry=registry,
)

edge_task_execution_duration = Histogram(
    "x0tta6bl4_edge_task_execution_duration_seconds",
    "Duration of task execution on edge node",
    ["task_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=registry,
)

edge_task_queue_time = Histogram(
    "x0tta6bl4_edge_task_queue_time_seconds",
    "Time tasks spend in queue before execution",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
    registry=registry,
)

edge_task_distribution_strategy = Gauge(
    "x0tta6bl4_edge_task_distribution_strategy",
    "Current task distribution strategy (0=round_robin, 1=least_loaded, 2=capability, 3=latency, 4=adaptive)",
    registry=registry,
)

edge_batch_tasks_total = Counter(
    "x0tta6bl4_edge_batch_tasks_total",
    "Total batch task submissions",
    ["status"],  # success, partial, failed
    registry=registry,
)

# Edge Cache Metrics
edge_cache_operations_total = Counter(
    "x0tta6bl4_edge_cache_operations_total",
    "Total edge cache operations",
    ["operation", "status"],  # operation: get, set, delete, invalidate; status: hit, miss, success, failed
    registry=registry,
)

edge_cache_size = Gauge(
    "x0tta6bl4_edge_cache_size_entries",
    "Number of entries in edge cache",
    registry=registry,
)

edge_cache_memory_bytes = Gauge(
    "x0tta6bl4_edge_cache_memory_bytes",
    "Memory usage of edge cache in bytes",
    registry=registry,
)

edge_cache_hit_ratio = Gauge(
    "x0tta6bl4_edge_cache_hit_ratio",
    "Cache hit ratio (0-1)",
    registry=registry,
)

edge_cache_evictions_total = Counter(
    "x0tta6bl4_edge_cache_evictions_total",
    "Total cache evictions",
    ["reason"],  # ttl_expired, lru, max_size
    registry=registry,
)

edge_cache_operation_duration = Histogram(
    "x0tta6bl4_edge_cache_operation_duration_seconds",
    "Duration of cache operations",
    ["operation"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05),
    registry=registry,
)

# Edge Health Metrics
edge_health_status = Gauge(
    "x0tta6bl4_edge_health_status",
    "Overall edge computing health status (1=healthy, 0=unhealthy)",
    registry=registry,
)

edge_health_check_duration = Histogram(
    "x0tta6bl4_edge_health_check_duration_seconds",
    "Duration of health check operations",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
    registry=registry,
)


# =============================================================================
# Event Sourcing Metrics
# =============================================================================

# Event Store Metrics
events_appended_total = Counter(
    "x0tta6bl4_events_appended_total",
    "Total events appended to event store",
    ["event_type"],
    registry=registry,
)

events_read_total = Counter(
    "x0tta6bl4_events_read_total",
    "Total events read from event store",
    ["stream_id"],
    registry=registry,
)

event_streams_total = Gauge(
    "x0tta6bl4_event_streams_total",
    "Total number of event streams",
    registry=registry,
)

event_stream_size = Gauge(
    "x0tta6bl4_event_stream_size_events",
    "Number of events in a stream",
    ["stream_id"],
    registry=registry,
)

event_stream_version = Gauge(
    "x0tta6bl4_event_stream_version",
    "Current version of event stream",
    ["stream_id"],
    registry=registry,
)

event_append_duration = Histogram(
    "x0tta6bl4_event_append_duration_seconds",
    "Duration of event append operation",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=registry,
)

event_read_duration = Histogram(
    "x0tta6bl4_event_read_duration_seconds",
    "Duration of event read operation",
    ["operation"],  # stream, all, range
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=registry,
)

event_version_conflicts_total = Counter(
    "x0tta6bl4_event_version_conflicts_total",
    "Total version conflict errors during append",
    registry=registry,
)

event_snapshot_creations_total = Counter(
    "x0tta6bl4_event_snapshot_creations_total",
    "Total snapshot creations",
    ["stream_id"],
    registry=registry,
)

event_snapshot_loads_total = Counter(
    "x0tta6bl4_event_snapshot_loads_total",
    "Total snapshot loads",
    ["stream_id"],
    registry=registry,
)

# WebSocket Subscription Metrics
event_subscriptions_active = Gauge(
    "x0tta6bl4_event_subscriptions_active",
    "Number of active WebSocket event subscriptions",
    registry=registry,
)

event_subscriptions_total = Counter(
    "x0tta6bl4_event_subscriptions_total",
    "Total WebSocket event subscriptions",
    ["event_type"],
    registry=registry,
)

events_broadcast_total = Counter(
    "x0tta6bl4_events_broadcast_total",
    "Total events broadcast to WebSocket subscribers",
    ["event_type"],
    registry=registry,
)

# Command Bus Metrics
commands_executed_total = Counter(
    "x0tta6bl4_commands_executed_total",
    "Total commands executed",
    ["command_type", "status"],  # status: success, failed
    registry=registry,
)

commands_active = Gauge(
    "x0tta6bl4_commands_active",
    "Number of currently executing commands",
    registry=registry,
)

command_execution_duration = Histogram(
    "x0tta6bl4_command_execution_duration_seconds",
    "Duration of command execution",
    ["command_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=registry,
)

command_events_produced = Histogram(
    "x0tta6bl4_command_events_produced",
    "Number of events produced by command execution",
    ["command_type"],
    buckets=(0, 1, 2, 3, 5, 10, 20, 50),
    registry=registry,
)

command_batch_total = Counter(
    "x0tta6bl4_command_batch_total",
    "Total batch command executions",
    ["status"],  # success, partial, failed
    registry=registry,
)

command_handlers_registered = Gauge(
    "x0tta6bl4_command_handlers_registered",
    "Number of registered command handlers",
    registry=registry,
)

# Query Bus Metrics
queries_executed_total = Counter(
    "x0tta6bl4_queries_executed_total",
    "Total queries executed",
    ["query_type", "cached"],  # cached: true, false
    registry=registry,
)

queries_active = Gauge(
    "x0tta6bl4_queries_active",
    "Number of currently executing queries",
    registry=registry,
)

query_execution_duration = Histogram(
    "x0tta6bl4_query_execution_duration_seconds",
    "Duration of query execution",
    ["query_type", "cached"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
    registry=registry,
)

query_cache_size = Gauge(
    "x0tta6bl4_query_cache_size_entries",
    "Number of entries in query cache",
    registry=registry,
)

query_cache_hit_ratio = Gauge(
    "x0tta6bl4_query_cache_hit_ratio",
    "Query cache hit ratio (0-1)",
    registry=registry,
)

query_cache_evictions_total = Counter(
    "x0tta6bl4_query_cache_evictions_total",
    "Total query cache evictions",
    registry=registry,
)

# Projection Metrics
projections_total = Gauge(
    "x0tta6bl4_projections_total",
    "Total number of projections",
    ["status"],  # running, paused, stopped, error
    registry=registry,
)

projection_events_processed = Counter(
    "x0tta6bl4_projection_events_processed_total",
    "Total events processed by projection",
    ["projection_name"],
    registry=registry,
)

projection_lag = Gauge(
    "x0tta6bl4_projection_lag_events",
    "Number of events behind for projection",
    ["projection_name"],
    registry=registry,
)

projection_position = Gauge(
    "x0tta6bl4_projection_position",
    "Current position of projection",
    ["projection_name"],
    registry=registry,
)

projection_processing_duration = Histogram(
    "x0tta6bl4_projection_processing_duration_seconds",
    "Duration of projection event processing",
    ["projection_name"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=registry,
)

projection_resets_total = Counter(
    "x0tta6bl4_projection_resets_total",
    "Total projection reset operations",
    ["projection_name"],
    registry=registry,
)

projection_errors_total = Counter(
    "x0tta6bl4_projection_errors_total",
    "Total projection errors",
    ["projection_name", "error_type"],
    registry=registry,
)

# Aggregate Metrics
aggregates_loaded_total = Counter(
    "x0tta6bl4_aggregates_loaded_total",
    "Total aggregates loaded from event store",
    ["aggregate_type"],
    registry=registry,
)

aggregate_rebuild_duration = Histogram(
    "x0tta6bl4_aggregate_rebuild_duration_seconds",
    "Duration of aggregate state rebuild from events",
    ["aggregate_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=registry,
)

aggregate_events_replayed = Histogram(
    "x0tta6bl4_aggregate_events_replayed",
    "Number of events replayed during aggregate rebuild",
    ["aggregate_type"],
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
    registry=registry,
)


# =============================================================================
# Resilience Pattern Metrics (for Edge & Event Sourcing)
# =============================================================================

resilience_rate_limit_total = Counter(
    "x0tta6bl4_resilience_rate_limit_total",
    "Total rate limit decisions",
    ["module", "result"],  # module: edge, events; result: allowed, rejected
    registry=registry,
)

resilience_bulkhead_total = Counter(
    "x0tta6bl4_resilience_bulkhead_total",
    "Total bulkhead decisions",
    ["module", "bulkhead", "result"],  # result: accepted, rejected
    registry=registry,
)

resilience_bulkhead_active = Gauge(
    "x0tta6bl4_resilience_bulkhead_active",
    "Active executions in bulkhead",
    ["module", "bulkhead"],
    registry=registry,
)

resilience_circuit_breaker_state = Gauge(
    "x0tta6bl4_resilience_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["module", "circuit"],
    registry=registry,
)

resilience_circuit_breaker_total = Counter(
    "x0tta6bl4_resilience_circuit_breaker_total",
    "Total circuit breaker decisions",
    ["module", "circuit", "result"],  # result: success, rejected, fallback
    registry=registry,
)

resilience_fallback_total = Counter(
    "x0tta6bl4_resilience_fallback_total",
    "Total fallback invocations",
    ["module", "fallback_type"],
    registry=registry,
)


# =============================================================================
# Metrics Collector Classes
# =============================================================================

class EdgeMetricsCollector:
    """Collector for Edge Computing metrics."""

    def __init__(self):
        self._start_times: Dict[str, float] = {}

    # Node Operations
    def record_node_registration(self, success: bool, duration: float):
        """Record node registration."""
        status = "success" if success else "failed"
        edge_node_registration_total.labels(status=status).inc()
        edge_node_registration_duration.observe(duration)

    def update_nodes_count(self, active: int, inactive: int, draining: int):
        """Update node counts by status."""
        edge_nodes_total.labels(status="active").set(active)
        edge_nodes_total.labels(status="inactive").set(inactive)
        edge_nodes_total.labels(status="draining").set(draining)

    def record_heartbeat(self, node_id: str):
        """Record heartbeat from node."""
        edge_node_heartbeat_total.labels(node_id=node_id).inc()

    def update_node_resources(
        self,
        node_id: str,
        cpu_percent: float,
        memory_percent: float,
        gpu_percent: Optional[float] = None
    ):
        """Update node resource metrics."""
        edge_node_resource_cpu.labels(node_id=node_id).set(cpu_percent)
        edge_node_resource_memory.labels(node_id=node_id).set(memory_percent)
        if gpu_percent is not None:
            edge_node_resource_gpu.labels(node_id=node_id).set(gpu_percent)

    def record_node_drain(self, success: bool):
        """Record node drain operation."""
        status = "success" if success else "failed"
        edge_node_drain_total.labels(status=status).inc()

    # Task Operations
    def record_task_submitted(self, task_type: str, priority: str, duration: float):
        """Record task submission."""
        edge_tasks_submitted_total.labels(task_type=task_type, priority=priority).inc()
        edge_task_submission_duration.observe(duration)

    def record_task_completed(self, task_type: str, success: bool, duration: float):
        """Record task completion."""
        status = "success" if success else "failed"
        edge_tasks_completed_total.labels(task_type=task_type, status=status).inc()
        edge_task_execution_duration.labels(task_type=task_type).observe(duration)

    def record_task_cancelled(self, task_type: str):
        """Record task cancellation."""
        edge_tasks_completed_total.labels(task_type=task_type, status="cancelled").inc()

    def update_active_tasks(self, node_id: str, count: int):
        """Update active task count for node."""
        edge_tasks_active.labels(node_id=node_id).set(count)

    def update_queued_tasks(self, count: int):
        """Update queued task count."""
        edge_tasks_queued.set(count)

    def record_task_queue_time(self, queue_time: float):
        """Record time task spent in queue."""
        edge_task_queue_time.observe(queue_time)

    def set_distribution_strategy(self, strategy: int):
        """Set current distribution strategy."""
        edge_task_distribution_strategy.set(strategy)

    def record_batch_submission(self, success: bool, partial: bool = False):
        """Record batch task submission."""
        if success and not partial:
            status = "success"
        elif partial:
            status = "partial"
        else:
            status = "failed"
        edge_batch_tasks_total.labels(status=status).inc()

    # Cache Operations
    def record_cache_get(self, hit: bool, duration: float):
        """Record cache get operation."""
        status = "hit" if hit else "miss"
        edge_cache_operations_total.labels(operation="get", status=status).inc()
        edge_cache_operation_duration.labels(operation="get").observe(duration)

    def record_cache_set(self, success: bool, duration: float):
        """Record cache set operation."""
        status = "success" if success else "failed"
        edge_cache_operations_total.labels(operation="set", status=status).inc()
        edge_cache_operation_duration.labels(operation="set").observe(duration)

    def record_cache_delete(self, success: bool):
        """Record cache delete operation."""
        status = "success" if success else "failed"
        edge_cache_operations_total.labels(operation="delete", status=status).inc()

    def record_cache_invalidation(self, count: int):
        """Record cache invalidation."""
        edge_cache_operations_total.labels(operation="invalidate", status="success").inc()
        edge_cache_evictions_total.labels(reason="invalidation").inc(count)

    def update_cache_stats(self, size: int, memory_bytes: int, hit_ratio: float):
        """Update cache statistics."""
        edge_cache_size.set(size)
        edge_cache_memory_bytes.set(memory_bytes)
        edge_cache_hit_ratio.set(hit_ratio)

    def record_cache_eviction(self, reason: str):
        """Record cache eviction."""
        edge_cache_evictions_total.labels(reason=reason).inc()

    # Health
    def set_health_status(self, healthy: bool):
        """Set overall health status."""
        edge_health_status.set(1 if healthy else 0)

    def record_health_check(self, duration: float):
        """Record health check duration."""
        edge_health_check_duration.observe(duration)


class EventSourcingMetricsCollector:
    """Collector for Event Sourcing metrics."""

    # Event Store Operations
    def record_events_appended(self, event_type: str, count: int, duration: float):
        """Record events appended."""
        events_appended_total.labels(event_type=event_type).inc(count)
        event_append_duration.observe(duration)

    def record_events_read(self, stream_id: str, count: int, duration: float, operation: str = "stream"):
        """Record events read."""
        events_read_total.labels(stream_id=stream_id).inc(count)
        event_read_duration.labels(operation=operation).observe(duration)

    def update_streams_count(self, count: int):
        """Update total streams count."""
        event_streams_total.set(count)

    def update_stream_stats(self, stream_id: str, size: int, version: int):
        """Update stream statistics."""
        event_stream_size.labels(stream_id=stream_id).set(size)
        event_stream_version.labels(stream_id=stream_id).set(version)

    def record_version_conflict(self):
        """Record version conflict error."""
        event_version_conflicts_total.inc()

    def record_snapshot_creation(self, stream_id: str):
        """Record snapshot creation."""
        event_snapshot_creations_total.labels(stream_id=stream_id).inc()

    def record_snapshot_load(self, stream_id: str):
        """Record snapshot load."""
        event_snapshot_loads_total.labels(stream_id=stream_id).inc()

    # WebSocket Subscriptions
    def update_active_subscriptions(self, count: int):
        """Update active WebSocket subscriptions."""
        event_subscriptions_active.set(count)

    def record_subscription(self, event_type: str):
        """Record new subscription."""
        event_subscriptions_total.labels(event_type=event_type).inc()

    def record_event_broadcast(self, event_type: str):
        """Record event broadcast to subscribers."""
        events_broadcast_total.labels(event_type=event_type).inc()

    # Command Bus Operations
    def record_command_executed(
        self,
        command_type: str,
        success: bool,
        duration: float,
        events_produced: int = 0
    ):
        """Record command execution."""
        status = "success" if success else "failed"
        commands_executed_total.labels(command_type=command_type, status=status).inc()
        command_execution_duration.labels(command_type=command_type).observe(duration)
        if events_produced > 0:
            command_events_produced.labels(command_type=command_type).observe(events_produced)

    def update_active_commands(self, count: int):
        """Update active command count."""
        commands_active.set(count)

    def record_batch_commands(self, success: bool, partial: bool = False):
        """Record batch command execution."""
        if success and not partial:
            status = "success"
        elif partial:
            status = "partial"
        else:
            status = "failed"
        command_batch_total.labels(status=status).inc()

    def update_command_handlers(self, count: int):
        """Update registered command handlers count."""
        command_handlers_registered.set(count)

    # Query Bus Operations
    def record_query_executed(self, query_type: str, cached: bool, duration: float):
        """Record query execution."""
        cached_str = "true" if cached else "false"
        queries_executed_total.labels(query_type=query_type, cached=cached_str).inc()
        query_execution_duration.labels(query_type=query_type, cached=cached_str).observe(duration)

    def update_active_queries(self, count: int):
        """Update active query count."""
        queries_active.set(count)

    def update_query_cache_stats(self, size: int, hit_ratio: float):
        """Update query cache statistics."""
        query_cache_size.set(size)
        query_cache_hit_ratio.set(hit_ratio)

    def record_query_cache_eviction(self):
        """Record query cache eviction."""
        query_cache_evictions_total.inc()

    # Projection Operations
    def update_projections_count(self, running: int, paused: int, stopped: int, error: int):
        """Update projection counts by status."""
        projections_total.labels(status="running").set(running)
        projections_total.labels(status="paused").set(paused)
        projections_total.labels(status="stopped").set(stopped)
        projections_total.labels(status="error").set(error)

    def record_projection_event(self, projection_name: str, duration: float):
        """Record projection event processing."""
        projection_events_processed.labels(projection_name=projection_name).inc()
        projection_processing_duration.labels(projection_name=projection_name).observe(duration)

    def update_projection_status(self, projection_name: str, position: int, lag: int):
        """Update projection status."""
        projection_position.labels(projection_name=projection_name).set(position)
        projection_lag.labels(projection_name=projection_name).set(lag)

    def record_projection_reset(self, projection_name: str):
        """Record projection reset."""
        projection_resets_total.labels(projection_name=projection_name).inc()

    def record_projection_error(self, projection_name: str, error_type: str):
        """Record projection error."""
        projection_errors_total.labels(projection_name=projection_name, error_type=error_type).inc()

    # Aggregate Operations
    def record_aggregate_loaded(self, aggregate_type: str, events_count: int, duration: float):
        """Record aggregate loaded from events."""
        aggregates_loaded_total.labels(aggregate_type=aggregate_type).inc()
        aggregate_rebuild_duration.labels(aggregate_type=aggregate_type).observe(duration)
        aggregate_events_replayed.labels(aggregate_type=aggregate_type).observe(events_count)


class ResilienceMetricsCollector:
    """Collector for resilience pattern metrics."""

    def record_rate_limit(self, module: str, allowed: bool):
        """Record rate limit decision."""
        result = "allowed" if allowed else "rejected"
        resilience_rate_limit_total.labels(module=module, result=result).inc()

    def record_bulkhead_accept(self, module: str, bulkhead: str):
        """Record bulkhead acceptance."""
        resilience_bulkhead_total.labels(module=module, bulkhead=bulkhead, result="accepted").inc()

    def record_bulkhead_reject(self, module: str, bulkhead: str):
        """Record bulkhead rejection."""
        resilience_bulkhead_total.labels(module=module, bulkhead=bulkhead, result="rejected").inc()

    def update_bulkhead_active(self, module: str, bulkhead: str, count: int):
        """Update active count in bulkhead."""
        resilience_bulkhead_active.labels(module=module, bulkhead=bulkhead).set(count)

    def set_circuit_breaker_state(self, module: str, circuit: str, state: int):
        """Set circuit breaker state (0=closed, 1=open, 2=half_open)."""
        resilience_circuit_breaker_state.labels(module=module, circuit=circuit).set(state)

    def record_circuit_breaker_result(self, module: str, circuit: str, result: str):
        """Record circuit breaker result."""
        resilience_circuit_breaker_total.labels(module=module, circuit=circuit, result=result).inc()

    def record_fallback(self, module: str, fallback_type: str):
        """Record fallback invocation."""
        resilience_fallback_total.labels(module=module, fallback_type=fallback_type).inc()


# =============================================================================
# Global Collector Instances
# =============================================================================

edge_metrics = EdgeMetricsCollector()
event_sourcing_metrics = EventSourcingMetricsCollector()
resilience_metrics = ResilienceMetricsCollector()


def get_edge_metrics() -> EdgeMetricsCollector:
    """Get Edge Computing metrics collector."""
    return edge_metrics


def get_event_sourcing_metrics() -> EventSourcingMetricsCollector:
    """Get Event Sourcing metrics collector."""
    return event_sourcing_metrics


def get_resilience_metrics() -> ResilienceMetricsCollector:
    """Get resilience metrics collector."""
    return resilience_metrics


__all__ = [
    # Edge Computing Metrics
    "edge_nodes_total",
    "edge_node_registration_total",
    "edge_node_registration_duration",
    "edge_node_heartbeat_total",
    "edge_node_resource_cpu",
    "edge_node_resource_memory",
    "edge_node_resource_gpu",
    "edge_node_drain_total",
    "edge_tasks_submitted_total",
    "edge_tasks_completed_total",
    "edge_tasks_active",
    "edge_tasks_queued",
    "edge_task_submission_duration",
    "edge_task_execution_duration",
    "edge_task_queue_time",
    "edge_task_distribution_strategy",
    "edge_batch_tasks_total",
    "edge_cache_operations_total",
    "edge_cache_size",
    "edge_cache_memory_bytes",
    "edge_cache_hit_ratio",
    "edge_cache_evictions_total",
    "edge_cache_operation_duration",
    "edge_health_status",
    "edge_health_check_duration",

    # Event Sourcing Metrics
    "events_appended_total",
    "events_read_total",
    "event_streams_total",
    "event_stream_size",
    "event_stream_version",
    "event_append_duration",
    "event_read_duration",
    "event_version_conflicts_total",
    "event_snapshot_creations_total",
    "event_snapshot_loads_total",
    "event_subscriptions_active",
    "event_subscriptions_total",
    "events_broadcast_total",
    "commands_executed_total",
    "commands_active",
    "command_execution_duration",
    "command_events_produced",
    "command_batch_total",
    "command_handlers_registered",
    "queries_executed_total",
    "queries_active",
    "query_execution_duration",
    "query_cache_size",
    "query_cache_hit_ratio",
    "query_cache_evictions_total",
    "projections_total",
    "projection_events_processed",
    "projection_lag",
    "projection_position",
    "projection_processing_duration",
    "projection_resets_total",
    "projection_errors_total",
    "aggregates_loaded_total",
    "aggregate_rebuild_duration",
    "aggregate_events_replayed",

    # Resilience Metrics
    "resilience_rate_limit_total",
    "resilience_bulkhead_total",
    "resilience_bulkhead_active",
    "resilience_circuit_breaker_state",
    "resilience_circuit_breaker_total",
    "resilience_fallback_total",

    # Collectors
    "EdgeMetricsCollector",
    "EventSourcingMetricsCollector",
    "ResilienceMetricsCollector",
    "edge_metrics",
    "event_sourcing_metrics",
    "resilience_metrics",
    "get_edge_metrics",
    "get_event_sourcing_metrics",
    "get_resilience_metrics",
]
