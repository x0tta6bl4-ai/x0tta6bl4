#!/usr/bin/env python3
"""
PQC-MAPE-K Integration for x0tta6bl4
Integrates PQC Verification Daemon with MAPE-K self-healing loop.

This module:
1. Connects PQC verification daemon to MAPE-K Monitor phase
2. Reports PQC anomalies (verification failures, unknown keys)
3. Exports Prometheus metrics for PQC operations
4. Enables adaptive threshold management via DAO governance
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available - metrics disabled")


class PQCAnomalyType(Enum):
    """Types of PQC anomalies"""

    VERIFICATION_FAILED = "verification_failed"
    UNKNOWN_PUBKEY = "unknown_pubkey"
    SESSION_EXPIRED = "session_expired"
    HIGH_FAILURE_RATE = "high_failure_rate"
    REPLAY_ATTACK = "replay_attack"


@dataclass
class PQCAnomaly:
    """PQC security anomaly event"""

    anomaly_type: PQCAnomalyType
    session_id: str
    pubkey_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    severity: str = "medium"
    details: Dict = field(default_factory=dict)


class PQCPrometheusMetrics:
    """Prometheus metrics for PQC verification"""

    def __init__(self, namespace: str = "x0tta6bl4_pqc"):
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus metrics disabled")
            self._enabled = False
            return

        self._enabled = True
        self._namespace = namespace

        # Counters
        self.verifications_total = Counter(
            f"{namespace}_verifications_total",
            "Total PQC signature verifications",
            ["result"],  # success, failed
        )

        self.anomalies_total = Counter(
            f"{namespace}_anomalies_total",
            "Total PQC anomalies detected",
            ["type"],  # verification_failed, unknown_pubkey, etc.
        )

        self.events_received = Counter(
            f"{namespace}_events_received_total",
            "Total verification events received from eBPF",
        )

        # Gauges
        self.active_sessions = Gauge(
            f"{namespace}_active_sessions", "Number of active verified PQC sessions"
        )

        self.registered_pubkeys = Gauge(
            f"{namespace}_registered_pubkeys",
            "Number of registered ML-DSA-65 public keys",
        )

        self.verification_rate = Gauge(
            f"{namespace}_verification_rate", "Current verification success rate (0-1)"
        )

        self.failure_rate = Gauge(
            f"{namespace}_failure_rate", "Current verification failure rate (0-1)"
        )

        # Histogram for verification latency
        self.verification_latency = Histogram(
            f"{namespace}_verification_latency_seconds",
            "ML-DSA-65 verification latency",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
        )

        logger.info(f"PQC Prometheus metrics initialized (namespace: {namespace})")

    def record_verification(self, success: bool, latency_seconds: float = 0):
        """Record a verification attempt"""
        if not self._enabled:
            return

        result = "success" if success else "failed"
        self.verifications_total.labels(result=result).inc()

        if latency_seconds > 0:
            self.verification_latency.observe(latency_seconds)

    def record_anomaly(self, anomaly_type: PQCAnomalyType):
        """Record a detected anomaly"""
        if not self._enabled:
            return

        self.anomalies_total.labels(type=anomaly_type.value).inc()

    def record_event_received(self):
        """Record an event received from eBPF"""
        if not self._enabled:
            return

        self.events_received.inc()

    def update_session_count(self, count: int):
        """Update active session count"""
        if not self._enabled:
            return

        self.active_sessions.set(count)

    def update_pubkey_count(self, count: int):
        """Update registered public key count"""
        if not self._enabled:
            return

        self.registered_pubkeys.set(count)

    def update_rates(self, success_rate: float, failure_rate: float):
        """Update verification rates"""
        if not self._enabled:
            return

        self.verification_rate.set(success_rate)
        self.failure_rate.set(failure_rate)


class PQCMAPEKIntegration:
    """
    Integrates PQC Verification Daemon with MAPE-K self-healing loop.

    Responsibilities:
    - Monitor: Collect PQC verification metrics
    - Analyze: Detect anomalies and security threats
    - Plan: Generate remediation actions
    - Execute: Trigger key rotation, session invalidation
    - Knowledge: Learn from past incidents
    """

    # Default thresholds (can be overridden by DAO governance)
    DEFAULT_THRESHOLDS = {
        "max_failure_rate": 0.1,  # 10% failure rate triggers alert
        "max_unknown_pubkey_rate": 0.05,  # 5% unknown pubkey rate
        "min_verification_rate": 0.9,  # 90% success required
        "anomaly_window_seconds": 60,  # Rolling window for rate calculation
        "consecutive_failures_alert": 5,  # Alert after N consecutive failures
    }

    def __init__(
        self,
        pqc_daemon=None,
        metrics: Optional[PQCPrometheusMetrics] = None,
        thresholds: Optional[Dict] = None,
        enable_metrics: bool = True,
    ):
        """
        Initialize PQC-MAPE-K integration.

        Args:
            pqc_daemon: PQCVerificationDaemon instance
            metrics: PQCPrometheusMetrics instance (None to create default or disable)
            thresholds: Custom thresholds (overrides defaults)
            enable_metrics: If False and metrics is None, use disabled metrics
        """
        self.daemon = pqc_daemon
        if metrics is not None:
            self.metrics = metrics
        elif enable_metrics:
            self.metrics = PQCPrometheusMetrics()
        else:
            # Create disabled metrics object
            self.metrics = PQCPrometheusMetrics.__new__(PQCPrometheusMetrics)
            self.metrics._enabled = False
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}

        # Anomaly tracking
        self.anomaly_history: List[PQCAnomaly] = []
        self.consecutive_failures = 0
        self.last_anomaly_check = time.time()

        # Callbacks for MAPE-K phases
        self._mapek_alert_callback: Optional[Callable] = None
        self._mapek_action_callback: Optional[Callable] = None

        # Statistics window
        self._recent_verifications: List[tuple] = []  # (timestamp, success)

        logger.info("PQC-MAPE-K integration initialized")

    def set_mapek_alert_callback(self, callback: Callable[[PQCAnomaly], None]):
        """Set callback for MAPE-K Analyzer alerts"""
        self._mapek_alert_callback = callback

    def set_mapek_action_callback(self, callback: Callable[[str, Dict], None]):
        """Set callback for MAPE-K Execute actions"""
        self._mapek_action_callback = callback

    def handle_daemon_anomaly(self, event_type: str, data: Dict):
        """
        Handle anomaly from PQC verification daemon.
        This is the callback passed to PQCVerificationDaemon.

        Args:
            event_type: Type of anomaly (unknown_pubkey, verification_failed)
            data: Anomaly details
        """
        logger.debug(f"Received daemon anomaly: {event_type}")

        # Map to PQCAnomalyType
        anomaly_type_map = {
            "unknown_pubkey": PQCAnomalyType.UNKNOWN_PUBKEY,
            "verification_failed": PQCAnomalyType.VERIFICATION_FAILED,
        }

        anomaly_type = anomaly_type_map.get(
            event_type, PQCAnomalyType.VERIFICATION_FAILED
        )

        # Create anomaly record
        anomaly = PQCAnomaly(
            anomaly_type=anomaly_type,
            session_id=data.get("session_id", "unknown"),
            pubkey_id=data.get("pubkey_id"),
            severity="medium" if event_type == "unknown_pubkey" else "high",
            details=data,
        )

        self._process_anomaly(anomaly)

    def _process_anomaly(self, anomaly: PQCAnomaly):
        """Process and potentially escalate an anomaly"""
        # Record in history
        self.anomaly_history.append(anomaly)

        # Trim history to last hour
        cutoff = time.time() - 3600
        self.anomaly_history = [a for a in self.anomaly_history if a.timestamp > cutoff]

        # Update metrics
        self.metrics.record_anomaly(anomaly.anomaly_type)

        # Track consecutive failures
        if anomaly.anomaly_type == PQCAnomalyType.VERIFICATION_FAILED:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        # Check for escalation
        should_escalate = self._should_escalate(anomaly)

        if should_escalate:
            self._escalate_to_mapek(anomaly)

    def _should_escalate(self, anomaly: PQCAnomaly) -> bool:
        """Determine if anomaly should be escalated to MAPE-K"""
        # Always escalate high severity
        if anomaly.severity == "high":
            return True

        # Check consecutive failures
        if self.consecutive_failures >= self.thresholds["consecutive_failures_alert"]:
            return True

        # Check rate-based thresholds
        window_seconds = self.thresholds["anomaly_window_seconds"]
        cutoff = time.time() - window_seconds
        recent_anomalies = [a for a in self.anomaly_history if a.timestamp > cutoff]

        # Count by type
        type_counts = {}
        for a in recent_anomalies:
            type_counts[a.anomaly_type] = type_counts.get(a.anomaly_type, 0) + 1

        # Check thresholds
        total_recent = len(self._recent_verifications)
        if total_recent > 0:
            failure_count = type_counts.get(PQCAnomalyType.VERIFICATION_FAILED, 0)
            unknown_count = type_counts.get(PQCAnomalyType.UNKNOWN_PUBKEY, 0)

            if failure_count / total_recent > self.thresholds["max_failure_rate"]:
                return True

            if (
                unknown_count / total_recent
                > self.thresholds["max_unknown_pubkey_rate"]
            ):
                return True

        return False

    def _escalate_to_mapek(self, anomaly: PQCAnomaly):
        """Escalate anomaly to MAPE-K Analyzer"""
        logger.warning(
            f"🚨 PQC Anomaly escalated: {anomaly.anomaly_type.value} "
            f"(session: {anomaly.session_id[:8]}..., severity: {anomaly.severity})"
        )

        if self._mapek_alert_callback:
            self._mapek_alert_callback(anomaly)

        # Suggest remediation actions
        actions = self._suggest_remediation(anomaly)

        for action in actions:
            logger.info(f"Suggested action: {action['type']} - {action['description']}")

            if self._mapek_action_callback:
                self._mapek_action_callback(action["type"], action)

    def _suggest_remediation(self, anomaly: PQCAnomaly) -> List[Dict]:
        """Suggest remediation actions for anomaly"""
        actions = []

        if anomaly.anomaly_type == PQCAnomalyType.VERIFICATION_FAILED:
            actions.append(
                {
                    "type": "invalidate_session",
                    "session_id": anomaly.session_id,
                    "description": "Invalidate potentially compromised session",
                    "priority": "high",
                }
            )

            if self.consecutive_failures >= 3:
                actions.append(
                    {
                        "type": "rotate_keys",
                        "description": "Rotate ML-DSA-65 keypair due to repeated failures",
                        "priority": "medium",
                    }
                )

        elif anomaly.anomaly_type == PQCAnomalyType.UNKNOWN_PUBKEY:
            actions.append(
                {
                    "type": "request_key_registration",
                    "pubkey_id": anomaly.pubkey_id,
                    "description": "Request peer to register public key",
                    "priority": "medium",
                }
            )

        elif anomaly.anomaly_type == PQCAnomalyType.REPLAY_ATTACK:
            actions.append(
                {
                    "type": "block_session",
                    "session_id": anomaly.session_id,
                    "description": "Block session due to replay attack detection",
                    "priority": "critical",
                }
            )
            actions.append(
                {
                    "type": "alert_security",
                    "description": "Alert security team about potential attack",
                    "priority": "critical",
                }
            )

        return actions

    def record_verification(self, success: bool, latency_seconds: float = 0):
        """Record a verification attempt for rate tracking"""
        now = time.time()
        self._recent_verifications.append((now, success))

        # Trim to window
        cutoff = now - self.thresholds["anomaly_window_seconds"]
        self._recent_verifications = [
            (t, s) for t, s in self._recent_verifications if t > cutoff
        ]

        # Reset consecutive failures on success
        if success:
            self.consecutive_failures = 0

        # Update metrics
        self.metrics.record_verification(success, latency_seconds)

        # Update rates
        self._update_rates()

    def _update_rates(self):
        """Update verification rate metrics"""
        if not self._recent_verifications:
            return

        total = len(self._recent_verifications)
        successes = sum(1 for _, s in self._recent_verifications if s)

        success_rate = successes / total
        failure_rate = 1 - success_rate

        self.metrics.update_rates(success_rate, failure_rate)

        # Check for low verification rate
        if success_rate < self.thresholds["min_verification_rate"]:
            anomaly = PQCAnomaly(
                anomaly_type=PQCAnomalyType.HIGH_FAILURE_RATE,
                session_id="aggregate",
                severity="high",
                details={
                    "success_rate": success_rate,
                    "threshold": self.thresholds["min_verification_rate"],
                    "sample_size": total,
                },
            )
            self._process_anomaly(anomaly)

    def get_metrics_for_mapek(self) -> Dict:
        """
        Get PQC metrics for MAPE-K Monitor phase.

        Returns:
            Dict of metrics compatible with MAPE-K
        """
        if not self.daemon:
            return {}

        daemon_stats = self.daemon.get_stats()

        # Calculate rates
        total = daemon_stats.get("events_received", 0)
        success = daemon_stats.get("verifications_success", 0)
        failed = daemon_stats.get("verifications_failed", 0)

        success_rate = success / total if total > 0 else 1.0
        failure_rate = failed / total if total > 0 else 0.0

        return {
            "pqc_events_received": total,
            "pqc_verifications_success": success,
            "pqc_verifications_failed": failed,
            "pqc_unknown_pubkey": daemon_stats.get("unknown_pubkey", 0),
            "pqc_active_sessions": daemon_stats.get("active_sessions", 0),
            "pqc_registered_pubkeys": daemon_stats.get("registered_pubkeys", 0),
            "pqc_success_rate": success_rate,
            "pqc_failure_rate": failure_rate,
            "pqc_consecutive_failures": self.consecutive_failures,
            "pqc_anomalies_last_hour": len(self.anomaly_history),
        }

    def sync_daemon_metrics(self):
        """Sync metrics from daemon to Prometheus"""
        if not self.daemon:
            return

        stats = self.daemon.get_stats()

        self.metrics.update_session_count(stats.get("active_sessions", 0))
        self.metrics.update_pubkey_count(stats.get("registered_pubkeys", 0))

    def update_thresholds_from_dao(self, dao_thresholds: Dict):
        """
        Update thresholds from DAO governance decision.

        Args:
            dao_thresholds: New thresholds approved by DAO
        """
        for key, value in dao_thresholds.items():
            if key in self.thresholds:
                old_value = self.thresholds[key]
                self.thresholds[key] = value
                logger.info(f"DAO updated threshold: {key} = {old_value} → {value}")


def create_integrated_pqc_system(
    interface: str = "eth0", enable_prometheus: bool = True
) -> Dict:
    """
    Factory function to create fully integrated PQC verification system.

    Args:
        interface: Network interface for eBPF
        enable_prometheus: Enable Prometheus metrics

    Returns:
        Dict with daemon, integration, and metrics objects
    """
    from .pqc_verification_daemon import (MockPQCVerificationDaemon,
                                          PQCVerificationDaemon)

    # Create metrics
    metrics = PQCPrometheusMetrics() if enable_prometheus else None

    # Create daemon (mock mode if BCC not available)
    try:
        from .pqc_xdp_loader import PQCXDPLoader

        loader = PQCXDPLoader(interface=interface)
        daemon = PQCVerificationDaemon(bpf=loader.bpf)
        logger.info("Created real PQC verification daemon")
    except Exception as e:
        logger.warning(f"BCC/XDP not available ({e}), using mock daemon")
        daemon = MockPQCVerificationDaemon()

    # Create integration
    integration = PQCMAPEKIntegration(
        pqc_daemon=daemon, metrics=metrics, enable_metrics=enable_prometheus
    )

    # Wire up anomaly callback
    daemon.anomaly_callback = integration.handle_daemon_anomaly

    return {
        "daemon": daemon,
        "integration": integration,
        "metrics": metrics,
    }


def start_pqc_monitoring_thread(
    integration: PQCMAPEKIntegration,
    interval: float = 5.0,
    stop_event=None,
):
    """
    Start background thread for PQC monitoring.

    Args:
        integration: PQCMAPEKIntegration instance
        interval: Metrics sync interval in seconds
    """

    def monitoring_loop():
        while stop_event is None or not stop_event.is_set():
            try:
                integration.sync_daemon_metrics()
                metrics = integration.get_metrics_for_mapek()
                logger.debug(f"PQC metrics: {metrics}")
            except Exception as e:
                logger.error(f"PQC monitoring error: {e}")

            time.sleep(interval)

    thread = threading.Thread(target=monitoring_loop, daemon=True, name="pqc-monitor")
    thread.start()

    logger.info(f"PQC monitoring thread started (interval: {interval}s)")
    return thread


if __name__ == "__main__":
    # Demo integration
    import argparse

    parser = argparse.ArgumentParser(description="PQC-MAPE-K Integration Demo")
    parser.add_argument("--interface", "-i", default="eth0", help="Network interface")

    args = parser.parse_args()

    # Create integrated system
    system = create_integrated_pqc_system(
        interface=args.interface, enable_prometheus=True
    )

    daemon = system["daemon"]
    integration = system["integration"]

    # Start monitoring
    start_pqc_monitoring_thread(integration)

    # Start daemon
    daemon.start()
