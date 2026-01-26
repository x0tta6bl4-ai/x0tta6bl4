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
    """Record successful PQC handshake with SLO monitoring."""
    pqc_handshake_success_total.inc()
    pqc_handshake_latency_seconds.observe(latency)
    
    # Check SLO violation and alert
    if latency > PQC_HANDSHAKE_P95_LATENCY_SLO:
        logger.warning(
            f"⚠️ PQC handshake latency SLO violation: {latency:.3f}s > {PQC_HANDSHAKE_P95_LATENCY_SLO}s"
        )
        
        # Send alert for SLO violation
        try:
            import asyncio
            from src.monitoring.alerting import send_alert_sync, AlertSeverity
            
            # Use simplified sync function
            send_alert_sync(
                "PQC_HANDSHAKE_SLO_VIOLATION",
                AlertSeverity.WARNING,
                f"PQC handshake latency SLO violation: {latency:.3f}s > {PQC_HANDSHAKE_P95_LATENCY_SLO}s",
                labels={"component": "pqc_security", "latency": f"{latency:.3f}"},
                annotations={
                    "impact": "Handshake latency exceeds SLO target",
                    "action": "Investigate network conditions or PQC performance",
                    "slo_target": f"{PQC_HANDSHAKE_P95_LATENCY_SLO}s"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send SLO violation alert: {e}")


def record_handshake_failure(reason: str):
    """Record failed PQC handshake."""
    pqc_handshake_failure_total.labels(reason=reason).inc()
    
    # Alert on any failure (zero tolerance)
    logger.error(f"🔴 PQC handshake failure: {reason}")
    # Send alert (async, fire and forget) - Improved integration
    try:
        from src.monitoring.alerting import send_alert_sync, AlertSeverity
        
        # Use simplified sync function
        send_alert_sync(
            "PQC_HANDSHAKE_FAILURE",
            AlertSeverity.CRITICAL,
            f"PQC handshake failed: {reason}",
            labels={"reason": reason, "component": "pqc_security"},
            annotations={"impact": "Security compromised", "action": "Review PQC configuration"},
            skip_rate_limit=True  # Critical alert, skip rate limit
        )
    except Exception as e:
        logger.warning(f"Failed to send alert: {e}")


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
    
    # Send alert (async, fire and forget) - Improved integration
    try:
        import asyncio
        from src.monitoring.alerting import AlertManager, AlertSeverity
        
        # Get or create AlertManager instance
        alert_manager = getattr(enable_fallback, '_alert_manager', None)
        if alert_manager is None:
            alert_manager = AlertManager()
            enable_fallback._alert_manager = alert_manager
        
        # Create task if event loop is running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(alert_manager.send_alert(
                    "PQC_FALLBACK_ENABLED",
                    AlertSeverity.CRITICAL,
                    f"PQC fallback enabled: {reason}. System running in INSECURE mode!",
                    labels={"reason": reason, "component": "pqc_security", "ttl_seconds": str(FALLBACK_TTL)},
                    annotations={
                        "impact": "System running in INSECURE mode without post-quantum protection",
                        "action": "Immediately investigate and restore PQC functionality",
                        "ttl": f"{FALLBACK_TTL}s"
                    }
                ))
            else:
                loop.run_until_complete(alert_manager.send_alert(
                    "PQC_FALLBACK_ENABLED",
                    AlertSeverity.CRITICAL,
                    f"PQC fallback enabled: {reason}. System running in INSECURE mode!",
                    labels={"reason": reason, "component": "pqc_security", "ttl_seconds": str(FALLBACK_TTL)},
                    annotations={
                        "impact": "System running in INSECURE mode without post-quantum protection",
                        "action": "Immediately investigate and restore PQC functionality",
                        "ttl": f"{FALLBACK_TTL}s"
                    }
                ))
        except RuntimeError:
            # No event loop, create new one
            asyncio.run(alert_manager.send_alert(
                "PQC_FALLBACK_ENABLED",
                AlertSeverity.CRITICAL,
                f"PQC fallback enabled: {reason}. System running in INSECURE mode!",
                labels={"reason": reason, "component": "pqc_security", "ttl_seconds": str(FALLBACK_TTL)},
                annotations={
                    "impact": "System running in INSECURE mode without post-quantum protection",
                    "action": "Immediately investigate and restore PQC functionality",
                    "ttl": f"{FALLBACK_TTL}s"
                }
            ))
    except Exception as e:
        logger.warning(f"Failed to send fallback alert: {e}")


def disable_fallback():
    """Disable fallback mode."""
    global _fallback_start_time, _fallback_reason
    
    _fallback_start_time = None
    _fallback_reason = None
    pqc_fallback_enabled.set(0)
    
    logger.info("✅ PQC fallback disabled - normal operation restored")


def check_fallback_ttl() -> bool:
    """Check if fallback TTL expired with alerting."""
    global _fallback_start_time, _fallback_reason
    
    if _fallback_start_time is None:
        return False
    
    elapsed = time.time() - _fallback_start_time
    
    if elapsed > FALLBACK_TTL:
        logger.critical(
            f"🔴 PQC FALLBACK TTL EXPIRED ({elapsed:.0f}s > {FALLBACK_TTL}s). "
            f"Shutting down for security!"
        )
        
        # Send critical alert for TTL expiration
        try:
            import asyncio
            from src.monitoring.alerting import AlertManager, AlertSeverity
            
            # Get or create AlertManager instance
            alert_manager = getattr(check_fallback_ttl, '_alert_manager', None)
            if alert_manager is None:
                alert_manager = AlertManager()
                check_fallback_ttl._alert_manager = alert_manager
            
            # Create task if event loop is running
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(alert_manager.send_alert(
                        "PQC_FALLBACK_TTL_EXPIRED",
                        AlertSeverity.CRITICAL,
                        f"PQC fallback TTL expired ({elapsed:.0f}s > {FALLBACK_TTL}s). System will shutdown!",
                        labels={
                            "component": "pqc_security",
                            "elapsed_seconds": f"{elapsed:.0f}",
                            "ttl_seconds": str(FALLBACK_TTL),
                            "reason": _fallback_reason or "unknown"
                        },
                        annotations={
                            "impact": "CRITICAL: System running in INSECURE mode beyond TTL",
                            "action": "IMMEDIATE: Restore PQC functionality or shutdown system",
                            "ttl_expired": "true"
                        }
                    ))
                else:
                    loop.run_until_complete(alert_manager.send_alert(
                        "PQC_FALLBACK_TTL_EXPIRED",
                        AlertSeverity.CRITICAL,
                        f"PQC fallback TTL expired ({elapsed:.0f}s > {FALLBACK_TTL}s). System will shutdown!",
                        labels={
                            "component": "pqc_security",
                            "elapsed_seconds": f"{elapsed:.0f}",
                            "ttl_seconds": str(FALLBACK_TTL),
                            "reason": _fallback_reason or "unknown"
                        },
                        annotations={
                            "impact": "CRITICAL: System running in INSECURE mode beyond TTL",
                            "action": "IMMEDIATE: Restore PQC functionality or shutdown system",
                            "ttl_expired": "true"
                        }
                    ))
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(alert_manager.send_alert(
                    "PQC_FALLBACK_TTL_EXPIRED",
                    AlertSeverity.CRITICAL,
                    f"PQC fallback TTL expired ({elapsed:.0f}s > {FALLBACK_TTL}s). System will shutdown!",
                    labels={
                        "component": "pqc_security",
                        "elapsed_seconds": f"{elapsed:.0f}",
                        "ttl_seconds": str(FALLBACK_TTL),
                        "reason": _fallback_reason or "unknown"
                    },
                    annotations={
                        "impact": "CRITICAL: System running in INSECURE mode beyond TTL",
                        "action": "IMMEDIATE: Restore PQC functionality or shutdown system",
                        "ttl_expired": "true"
                    }
                ))
        except Exception as e:
            logger.warning(f"Failed to send TTL expiration alert: {e}")
        
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
    """Record failed key rotation with alerting."""
    key_rotation_failure_total.labels(reason=reason).inc()
    logger.error(f"🔴 PQC key rotation failure: {reason}")
    
    # Send alert for key rotation failure
    try:
        import asyncio
        from src.monitoring.alerting import AlertManager, AlertSeverity
        
        # Get or create AlertManager instance
        alert_manager = getattr(record_key_rotation_failure, '_alert_manager', None)
        if alert_manager is None:
            alert_manager = AlertManager()
            record_key_rotation_failure._alert_manager = alert_manager
        
        # Create task if event loop is running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(alert_manager.send_alert(
                    "PQC_KEY_ROTATION_FAILURE",
                    AlertSeverity.ERROR,
                    f"PQC key rotation failed: {reason}",
                    labels={"reason": reason, "component": "pqc_security"},
                    annotations={
                        "impact": "Key rotation failed, keys may need manual rotation",
                        "action": "Review key rotation configuration and retry"
                    }
                ))
            else:
                loop.run_until_complete(alert_manager.send_alert(
                    "PQC_KEY_ROTATION_FAILURE",
                    AlertSeverity.ERROR,
                    f"PQC key rotation failed: {reason}",
                    labels={"reason": reason, "component": "pqc_security"},
                    annotations={
                        "impact": "Key rotation failed, keys may need manual rotation",
                        "action": "Review key rotation configuration and retry"
                    }
                ))
        except RuntimeError:
            # No event loop, create new one
            asyncio.run(alert_manager.send_alert(
                "PQC_KEY_ROTATION_FAILURE",
                AlertSeverity.ERROR,
                f"PQC key rotation failed: {reason}",
                labels={"reason": reason, "component": "pqc_security"},
                annotations={
                    "impact": "Key rotation failed, keys may need manual rotation",
                    "action": "Review key rotation configuration and retry"
                }
            ))
    except Exception as e:
        logger.warning(f"Failed to send key rotation alert: {e}")

