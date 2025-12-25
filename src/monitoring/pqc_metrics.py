"""
PQC Handshake Metrics and SLI/SLO
"""
import logging
import time
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# SLI/SLO Metrics
pqc_handshake_success_total = Counter(
    'pqc_handshake_success_total',
    'Total successful PQC handshakes'
)

pqc_handshake_failure_total = Counter(
    'pqc_handshake_failure_total',
    'Total failed PQC handshakes',
    ['reason']  # 'timeout', 'invalid_key', 'liboqs_error', 'fallback', etc.
)

pqc_handshake_latency_seconds = Histogram(
    'pqc_handshake_latency_seconds',
    'PQC handshake latency (p95 target: <0.1s)',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

pqc_fallback_enabled = Gauge(
    'pqc_fallback_enabled',
    'PQC fallback enabled (1=yes, 0=no)'
)

key_rotation_success_total = Counter(
    'pqc_key_rotation_success_total',
    'Total successful PQC key rotations'
)

key_rotation_failure_total = Counter(
    'pqc_key_rotation_failure_total',
    'Total failed PQC key rotations',
    ['reason']
)

# SLO Targets
PQC_HANDSHAKE_SUCCESS_RATE_SLO = 0.99  # 99% success rate
PQC_HANDSHAKE_P95_LATENCY_SLO = 0.1   # 100ms p95 latency
PQC_FALLBACK_RATE_SLO = 0.0            # 0% fallback (zero tolerance)

# Fallback state
_fallback_start_time: Optional[float] = None
_fallback_reason: Optional[str] = None
FALLBACK_TTL = 3600  # 1 hour max fallback


def record_handshake_success(latency: float):
    """Record successful PQC handshake."""
    pqc_handshake_success_total.inc()
    pqc_handshake_latency_seconds.observe(latency)
    
    # Check SLO violation
    if latency > PQC_HANDSHAKE_P95_LATENCY_SLO:
        logger.warning(
            f"⚠️ PQC handshake latency SLO violation: {latency:.3f}s > {PQC_HANDSHAKE_P95_LATENCY_SLO}s"
        )


def record_handshake_failure(reason: str):
    """Record failed PQC handshake."""
    pqc_handshake_failure_total.labels(reason=reason).inc()
    
    # Alert on any failure (zero tolerance)
    logger.error(f"🔴 PQC handshake failure: {reason}")
    # TODO: Integrate with alerting system
    # send_alert("PQC_HANDSHAKE_FAILURE", reason=reason)


def enable_fallback(reason: str):
    """Enable fallback mode with alerting."""
    global _fallback_start_time, _fallback_reason
    
    _fallback_start_time = time.time()
    _fallback_reason = reason
    
    pqc_fallback_enabled.set(1)
    
    logger.critical(
        f"🔴 PQC FALLBACK ENABLED: {reason}. "
        f"System running in INSECURE mode! "
        f"TTL: {FALLBACK_TTL}s"
    )
    
    # TODO: Integrate with alerting system
    # send_alert("PQC_FALLBACK_ENABLED", reason=reason)


def disable_fallback():
    """Disable fallback mode."""
    global _fallback_start_time, _fallback_reason
    
    _fallback_start_time = None
    _fallback_reason = None
    pqc_fallback_enabled.set(0)
    
    logger.info("✅ PQC fallback disabled - normal operation restored")


def check_fallback_ttl() -> bool:
    """Check if fallback TTL expired."""
    global _fallback_start_time
    
    if _fallback_start_time is None:
        return False
    
    elapsed = time.time() - _fallback_start_time
    
    if elapsed > FALLBACK_TTL:
        logger.critical(
            f"🔴 PQC FALLBACK TTL EXPIRED ({elapsed:.0f}s > {FALLBACK_TTL}s). "
            f"Shutting down for security!"
        )
        # In production, this should trigger graceful shutdown
        # raise SystemExit("PQC fallback TTL expired")
        return True
    
    return False


def is_fallback_enabled() -> bool:
    """Check if fallback is currently enabled."""
    return _fallback_start_time is not None


def record_key_rotation_success():
    """Record successful key rotation."""
    key_rotation_success_total.inc()


def record_key_rotation_failure(reason: str):
    """Record failed key rotation."""
    key_rotation_failure_total.labels(reason=reason).inc()
    logger.error(f"🔴 PQC key rotation failure: {reason}")

