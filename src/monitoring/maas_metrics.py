"""
MaaS / VPN Business Metrics — x0tta6bl4

Prometheus metrics for MaaS and VPN critical business paths.
These correspond 1:1 with alert rules in docs/monitoring/prometheus_alerts.yaml.

Import pattern (lazy, no hard dep on prometheus_client at module load):
    from src.monitoring.maas_metrics import maas_metrics
    maas_metrics.escrow_failures.inc()
    maas_metrics.heartbeat_received.inc()
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conditional Prometheus import — graceful no-op when not installed
# ---------------------------------------------------------------------------

_prom_available = False
_registry = None

try:
    import prometheus_client
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram

    _prom_available = True
    # Use default REGISTRY so metrics are visible via /metrics
    _registry = REGISTRY
except ImportError:
    logger.debug("prometheus_client not available — MaaS metrics disabled")


def _make_counter(name: str, doc: str, labels: list[str] | None = None):
    if not _prom_available:
        return _NoOpMetric()
    try:
        return Counter(name, doc, labels or [])
    except ValueError:
        # Already registered (e.g. module reloaded in tests)
        return _get_existing(name) or _NoOpMetric()


def _make_gauge(name: str, doc: str, labels: list[str] | None = None):
    if not _prom_available:
        return _NoOpMetric()
    try:
        return Gauge(name, doc, labels or [])
    except ValueError:
        return _get_existing(name) or _NoOpMetric()


def _make_histogram(
    name: str, doc: str, labels: list[str] | None = None, buckets=None
):
    if not _prom_available:
        return _NoOpMetric()
    kw = {}
    if buckets:
        kw["buckets"] = buckets
    try:
        return Histogram(name, doc, labels or [], **kw)
    except ValueError:
        return _get_existing(name) or _NoOpMetric()


def _get_existing(name: str):
    """Retrieve already-registered collector by metric name."""
    try:
        for coll in REGISTRY._names_to_collectors.values():
            if getattr(coll, "_name", None) == name:
                return coll
    except Exception:
        pass
    return None


class _NoOpMetric:
    """Silent no-op when Prometheus is unavailable."""

    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def set(self, value):
        pass

    def observe(self, value):
        pass

    def labels(self, **kwargs):
        return self

    def time(self):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield

        return _ctx()


# ---------------------------------------------------------------------------
# MaaS Metrics
# ---------------------------------------------------------------------------


class MaaSMetrics:
    """
    Central registry for MaaS / VPN business metrics.

    All counters/gauges here are referenced in:
      docs/monitoring/prometheus_alerts.yaml

    Naming convention: maas_<component>_<what>_<unit>
    """

    def __init__(self):
        # ------------------------------------------------------------------
        # Escrow / Marketplace
        # ------------------------------------------------------------------
        self.escrow_failures = _make_counter(
            "maas_escrow_failures_total",
            "MaaS escrow auto-release or refund failures",
            ["reason"],
        )
        self.escrow_operations = _make_counter(
            "maas_escrow_operations_total",
            "MaaS escrow operations",
            ["operation", "status"],  # rent/release/refund, success/failure
        )
        self.marketplace_listings_active = _make_gauge(
            "maas_marketplace_listings_active",
            "Number of currently active marketplace listings",
        )
        self.marketplace_rent_duration_seconds = _make_histogram(
            "maas_marketplace_rent_duration_seconds",
            "Duration of marketplace node rentals in seconds",
            buckets=[60, 300, 900, 3600, 86400],
        )

        # ------------------------------------------------------------------
        # Telemetry / Heartbeat
        # ------------------------------------------------------------------
        self.heartbeat_received = _make_counter(
            "maas_heartbeat_received_total",
            "MaaS node heartbeat events received",
            ["node_id"],
        )
        self.heartbeat_latency_seconds = _make_histogram(
            "maas_heartbeat_latency_seconds",
            "Time between expected and actual heartbeat",
            buckets=[1, 5, 10, 30, 60, 120, 300],
        )
        self.nodes_active = _make_gauge(
            "maas_nodes_active",
            "Number of active MaaS nodes",
            ["region", "plan"],
        )
        self.nodes_offline = _make_gauge(
            "maas_nodes_offline",
            "Number of MaaS nodes that missed heartbeat threshold",
        )

        # ------------------------------------------------------------------
        # Billing
        # ------------------------------------------------------------------
        self.billing_errors = _make_counter(
            "maas_billing_errors_total",
            "MaaS billing pipeline errors",
            ["error_type"],  # stripe_timeout, invoice_failed, webhook_error
        )
        self.billing_operations = _make_counter(
            "maas_billing_operations_total",
            "MaaS billing operations",
            ["operation", "status"],  # checkout/webhook/invoice, success/failure
        )
        self.billing_amount_cents = _make_counter(
            "maas_billing_amount_cents_total",
            "Total billing amount processed in cents",
            ["currency"],
        )

        # ------------------------------------------------------------------
        # Governance / DAO
        # ------------------------------------------------------------------
        self.governance_quorum_failures = _make_counter(
            "maas_governance_quorum_failures_total",
            "DAO governance quorum check failures",
            ["proposal_id"],
        )
        self.governance_proposals = _make_counter(
            "maas_governance_proposals_total",
            "DAO governance proposals",
            ["status"],  # created/executed/failed/cancelled
        )

        # ------------------------------------------------------------------
        # Rate Limiting
        # ------------------------------------------------------------------
        self.rate_limit_rejected = _make_counter(
            "maas_rate_limit_rejected_total",
            "Requests rejected by rate limiter",
            ["endpoint"],
        )
        self.rate_limit_blocked_ips = _make_gauge(
            "maas_rate_limit_blocked_ips",
            "Number of currently blocked IPs",
        )

        # ------------------------------------------------------------------
        # VPN
        # ------------------------------------------------------------------
        self.vpn_configs_created = _make_counter(
            "maas_vpn_configs_created_total",
            "VPN configurations created",
            ["protocol"],
        )
        self.vpn_connections_active = _make_gauge(
            "maas_vpn_connections_active",
            "Active VPN connections",
        )
        self.vpn_errors = _make_counter(
            "maas_vpn_errors_total",
            "VPN operation errors",
            ["error_type"],
        )

        # ------------------------------------------------------------------
        # PQC / Security
        # ------------------------------------------------------------------
        self.pqc_handshake_failures = _make_counter(
            "pqc_handshake_failures_total",
            "PQC/mTLS handshake failures",
            ["reason"],  # cert_expired, algo_mismatch, verification_failed
        )
        self.pqc_handshakes_total = _make_counter(
            "pqc_handshakes_total",
            "PQC handshake attempts",
            ["result"],  # success/failure
        )

        # ------------------------------------------------------------------
        # MAPE-K Integration (referenced from maas_billing.py)
        # ------------------------------------------------------------------
        self.mapek_events_emitted = _make_counter(
            "maas_mapek_events_emitted_total",
            "MAPE-K events emitted from MaaS billing",
            ["event_type"],
        )


# Global singleton — import this
maas_metrics = MaaSMetrics()


def record_escrow_failure(reason: str = "unknown") -> None:
    """Convenience: record an escrow failure with reason label."""
    maas_metrics.escrow_failures.labels(reason=reason).inc()


def record_billing_error(error_type: str = "unknown") -> None:
    """Convenience: record a billing error."""
    maas_metrics.billing_errors.labels(error_type=error_type).inc()


def record_heartbeat(node_id: str = "unknown") -> None:
    """Convenience: record a heartbeat received event."""
    # Avoid high cardinality — truncate to first 16 chars
    safe_id = str(node_id)[:16]
    maas_metrics.heartbeat_received.labels(node_id=safe_id).inc()


def record_rate_limit_rejection(endpoint: str = "unknown") -> None:
    """Convenience: record rate limit rejection."""
    maas_metrics.rate_limit_rejected.labels(endpoint=endpoint).inc()


__all__ = [
    "MaaSMetrics",
    "maas_metrics",
    "record_escrow_failure",
    "record_billing_error",
    "record_heartbeat",
    "record_rate_limit_rejection",
]
