"""
Prometheus metrics for Anti-Delos Charter observability.

WEST-0105: Observability Layer for Charter enforcement.
Exports metrics for:
- Violation detection and severity tracking
- Forbidden metric detection attempts
- Validation latency and performance
- Data operations (revocation, audit)
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import logging

logger = logging.getLogger(__name__)

# Global registry for Charter metrics
_registry = None


def get_registry():
    """Get or create the global metrics registry."""
    global _registry
    if _registry is None:
        _registry = CollectorRegistry()
    return _registry


# ============================================================================
# Counter Metrics
# ============================================================================

violations_total = Counter(
    'westworld_charter_violations_total',
    'Total charter violations detected',
    labelnames=['severity', 'violation_type', 'node_or_service'],
    registry=get_registry()
)
"""
Track every violation by severity and type.
Labels:
  - severity: WARNING | SUSPENSION | BAN_1YEAR | PERMANENT_BAN | CRIMINAL_REFERRAL
  - violation_type: silent_collection | behavioral_prediction | data_extraction | ...
  - node_or_service: Name of violating node/service
"""

forbidden_metric_attempts_total = Counter(
    'westworld_charter_forbidden_metric_attempts_total',
    'Attempts to collect forbidden metrics',
    labelnames=['metric_name', 'node_or_service', 'status'],
    registry=get_registry()
)
"""
Track every attempt to collect a forbidden metric.
Labels:
  - metric_name: user_location | browsing_history | device_hardware_id | ...
  - node_or_service: Attempting node/service
  - status: blocked | reported | escalated
"""

data_revocation_events_total = Counter(
    'westworld_charter_data_revocation_events_total',
    'Data access revocation events',
    labelnames=['reason', 'node_or_service'],
    registry=get_registry()
)
"""
Track data revocation operations.
Labels:
  - reason: account_closure | policy_violation | security_incident | ...
  - node_or_service: Affected node/service
"""

audit_committee_notifications_total = Counter(
    'westworld_charter_audit_committee_notifications_total',
    'Notifications sent to audit committee',
    labelnames=['severity', 'recipient_count'],
    registry=get_registry()
)
"""
Track audit committee notifications.
Labels:
  - severity: Violation severity
  - recipient_count: Number of committee members notified
"""

investigation_initiated_total = Counter(
    'westworld_charter_investigation_initiated_total',
    'Investigation procedures initiated',
    labelnames=['violation_type', 'initiated_by'],
    registry=get_registry()
)
"""
Track investigation initiations.
Labels:
  - violation_type: Type of violation triggering investigation
  - initiated_by: system | committee | external
"""

emergency_override_total = Counter(
    'westworld_charter_emergency_override_total',
    'Emergency overrides executed',
    labelnames=['reason', 'who_triggered'],
    registry=get_registry()
)
"""
Track emergency override procedures.
Labels:
  - reason: Reason for override
  - who_triggered: Admin/role who triggered it
"""


# ============================================================================
# Histogram Metrics (Latency/Duration)
# ============================================================================

metric_validation_latency_ns = Histogram(
    'westworld_charter_metric_validation_latency_ns',
    'Latency of metric validation in nanoseconds',
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),  # 0.1µs to 10ms
    registry=get_registry()
)
"""
Measure validation latency.
Buckets: 100ns, 1µs, 10µs, 100µs, 1ms, 10ms
Used to detect SLA violations.
"""

policy_load_duration_ms = Histogram(
    'westworld_charter_policy_load_duration_ms',
    'Time to load charter policy in milliseconds',
    buckets=(10, 50, 100, 200, 500, 1000),  # 10ms to 1s
    registry=get_registry()
)
"""
Measure policy loading time.
Buckets: 10ms, 50ms, 100ms, 200ms, 500ms, 1s
Used to detect policy loading issues.
"""

violation_report_latency_ms = Histogram(
    'westworld_charter_violation_report_latency_ms',
    'Time to report and escalate a violation in milliseconds',
    buckets=(50, 100, 250, 500, 1000, 2000),  # 50ms to 2s
    registry=get_registry()
)
"""
Measure violation escalation latency.
Buckets: 50ms, 100ms, 250ms, 500ms, 1s, 2s
Includes: investigation trigger, committee notification, immediate action.
"""

committee_notification_latency_ms = Histogram(
    'westworld_charter_committee_notification_latency_ms',
    'Latency to notify audit committee in milliseconds',
    buckets=(10, 50, 100, 250, 500, 1000),  # 10ms to 1s
    registry=get_registry()
)
"""
Measure audit committee notification latency.
Buckets: 10ms, 50ms, 100ms, 250ms, 500ms, 1s
SLA: Should complete < 1s.
"""

data_revocation_latency_ms = Histogram(
    'westworld_charter_data_revocation_latency_ms',
    'Time to revoke data access in milliseconds',
    buckets=(50, 100, 250, 500, 1000, 5000),  # 50ms to 5s
    registry=get_registry()
)
"""
Measure data revocation procedure latency.
Buckets: 50ms, 100ms, 250ms, 500ms, 1s, 5s
Includes: audit log creation, event propagation.
"""


# ============================================================================
# Gauge Metrics (Current State)
# ============================================================================

violations_under_investigation = Gauge(
    'westworld_charter_violations_under_investigation',
    'Current number of violations being investigated',
    labelnames=['severity'],
    registry=get_registry()
)
"""
Current state of investigations.
Labels:
  - severity: Violation severity
"""

audit_committee_size = Gauge(
    'westworld_charter_audit_committee_size',
    'Number of members in audit committee',
    registry=get_registry()
)
"""
Current audit committee size.
Used to verify committee responsiveness.
"""

policy_last_load_timestamp = Gauge(
    'westworld_charter_policy_last_load_timestamp',
    'Timestamp of last policy load (seconds since epoch)',
    registry=get_registry()
)
"""
When was policy last loaded.
Used to detect stale policies.
"""

emergency_override_active_count = Gauge(
    'westworld_charter_emergency_override_active_count',
    'Number of active emergency overrides',
    registry=get_registry()
)
"""
How many emergency overrides are currently in effect.
Should normally be 0 or very low.
"""


# ============================================================================
# Convenience Recording Functions
# ============================================================================

def record_violation(severity: str, violation_type: str, node_or_service: str):
    """Record a violation event."""
    try:
        violations_total.labels(
            severity=severity,
            violation_type=violation_type,
            node_or_service=node_or_service
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record violation metric: {e}")


def record_forbidden_attempt(metric_name: str, node_or_service: str, status: str = "blocked"):
    """Record a forbidden metric collection attempt."""
    try:
        forbidden_metric_attempts_total.labels(
            metric_name=metric_name,
            node_or_service=node_or_service,
            status=status
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record forbidden attempt metric: {e}")


def record_data_revocation(reason: str, node_or_service: str):
    """Record a data revocation event."""
    try:
        data_revocation_events_total.labels(
            reason=reason,
            node_or_service=node_or_service
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record revocation metric: {e}")


def record_validation_latency_ns(latency_ns: float):
    """Record metric validation latency in nanoseconds."""
    try:
        metric_validation_latency_ns.observe(latency_ns)
    except Exception as e:
        logger.error(f"Failed to record validation latency: {e}")


def record_policy_load_duration_ms(duration_ms: float):
    """Record policy load duration in milliseconds."""
    try:
        policy_load_duration_ms.observe(duration_ms)
    except Exception as e:
        logger.error(f"Failed to record policy load duration: {e}")


def record_violation_report_latency_ms(latency_ms: float):
    """Record violation reporting latency in milliseconds."""
    try:
        violation_report_latency_ms.observe(latency_ms)
    except Exception as e:
        logger.error(f"Failed to record violation report latency: {e}")


def update_committee_size(size: int):
    """Update current audit committee size."""
    try:
        audit_committee_size.set(size)
    except Exception as e:
        logger.error(f"Failed to update committee size: {e}")


def update_violations_investigating(severity: str, count: int):
    """Update count of violations under investigation."""
    try:
        violations_under_investigation.labels(severity=severity).set(count)
    except Exception as e:
        logger.error(f"Failed to update violations investigating: {e}")


# ============================================================================
# Metric Export
# ============================================================================

def get_metrics_text():
    """Get all metrics as Prometheus text format."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(get_registry())


__all__ = [
    # Counters
    'violations_total',
    'forbidden_metric_attempts_total',
    'data_revocation_events_total',
    'audit_committee_notifications_total',
    'investigation_initiated_total',
    'emergency_override_total',
    # Histograms
    'metric_validation_latency_ns',
    'policy_load_duration_ms',
    'violation_report_latency_ms',
    'committee_notification_latency_ms',
    'data_revocation_latency_ms',
    # Gauges
    'violations_under_investigation',
    'audit_committee_size',
    'policy_last_load_timestamp',
    'emergency_override_active_count',
    # Functions
    'record_violation',
    'record_forbidden_attempt',
    'record_data_revocation',
    'record_validation_latency_ns',
    'record_policy_load_duration_ms',
    'record_violation_report_latency_ms',
    'update_committee_size',
    'update_violations_investigating',
    'get_metrics_text',
]
