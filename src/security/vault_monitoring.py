"""
Vault monitoring and health checking.

This module provides health monitoring, metrics collection, and alerting
for Vault integration. It includes a background health check loop that
monitors Vault availability and token status.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import prometheus_client as prom
from prometheus_client import REGISTRY
from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 60:
        return "1-60"
    if value <= 300:
        return "61-300"
    if value <= 3600:
        return "301-3600"
    return "3600+"


def _get_or_create_metric(metric_class, name, description, **kwargs):
    """Get existing metric or create new one to avoid duplicate registration."""
    try:
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, "_name") and collector._name == name:
                return collector
        return metric_class(name, description, **kwargs)
    except (ValueError, KeyError):
        # Fallback: create with registry=None to avoid registration
        return metric_class(name, description, registry=None, **kwargs)

# Prometheus metrics - using helper to avoid duplicate registration
vault_token_expiry_seconds = _get_or_create_metric(
    prom.Gauge, "vault_token_expiry_seconds", "Seconds until Vault token expires"
)
vault_uptime_seconds = _get_or_create_metric(
    prom.Counter, "vault_uptime_seconds", "Total Vault connection uptime"
)
vault_health_check_failures = _get_or_create_metric(
    prom.Counter, "vault_health_check_failures_total", "Total health check failures"
)
vault_token_refresh_count = _get_or_create_metric(
    prom.Counter, "vault_token_refresh_count_total", "Total token refresh operations"
)
vault_degraded_mode = _get_or_create_metric(
    prom.Gauge, "vault_degraded_mode", "Vault client in degraded mode (1=yes, 0=no)"
)


class VaultHealthMonitor:
    """Monitor Vault health and availability.

    This monitor runs a background task that periodically checks Vault
    health status and updates metrics. It can trigger callbacks when
    health status changes.

    Example:
        >>> monitor = VaultHealthMonitor(vault_client, check_interval=60)
        >>> await monitor.start()
        >>> # ... run application ...
        >>> await monitor.stop()
    """

    def __init__(
        self,
        vault_client,
        check_interval: int = 60,
        on_health_change: Optional[Callable[[bool], None]] = None,
        on_token_expiry_warning: Optional[Callable[[], None]] = None,
        token_warning_threshold: int = 300,  # 5 minutes
    ):
        """Initialize health monitor.

        Args:
            vault_client: VaultClient instance to monitor
            check_interval: Seconds between health checks
            on_health_change: Callback when health status changes
            on_token_expiry_warning: Callback when token near expiry
            token_warning_threshold: Seconds before expiry to warn
        """
        self.vault_client = vault_client
        self.check_interval = check_interval
        self.on_health_change = on_health_change
        self.on_token_expiry_warning = on_token_expiry_warning
        self.token_warning_threshold = token_warning_threshold

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_health: Optional[bool] = None
        self._token_warning_sent = False
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"vault-health-monitor:{_safe_hash(id(vault_client))}",
            role="monitoring",
            capabilities=("security", "ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "vault_health_monitor_init",
                "goal": "Initialize Vault health monitoring safely",
                "signals": {
                    "vault_addr_hash": _safe_hash(
                        getattr(vault_client, "vault_addr", "")
                    ),
                    "check_interval_band": _safe_number_band(check_interval),
                    "token_warning_threshold_band": _safe_number_band(
                        token_warning_threshold
                    ),
                    "has_health_change_callback": on_health_change is not None,
                    "has_token_warning_callback": (
                        on_token_expiry_warning is not None
                    ),
                },
                "safety_boundary": (
                    "Keep raw Vault addresses, token expiry timestamps, callback "
                    "details, and exception text out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_vault_addr": True,
                    "redact_token_expiry_timestamp": True,
                    "redact_callback_details": True,
                    "redact_exception_text": True,
                    "preserve_health_decision": True,
                },
                "safety_boundary": "Use hashes, booleans, counts, and time bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def start(self) -> None:
        """Start health monitoring loop."""
        if self._running:
            self._record_thinking(
                "vault_health_monitor_start_skipped",
                "Skip duplicate Vault health monitor start safely",
                {"running": True},
            )
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        self._record_thinking(
            "vault_health_monitor_started",
            "Start Vault health monitor safely",
            {
                "running": self._running,
                "check_interval_band": _safe_number_band(self.check_interval),
            },
        )
        logger.info(
            "Vault health monitor started (check every %ds)", self.check_interval
        )

    async def stop(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            self._record_thinking(
                "vault_health_monitor_stop_skipped",
                "Skip Vault health monitor stop when already stopped",
                {"running": False},
            )
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Vault health monitor stopped")
        self._record_thinking(
            "vault_health_monitor_stopped",
            "Stop Vault health monitor safely",
            {"running": self._running, "task_present": self._task is not None},
        )

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                raise
            except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as e:
                self._record_thinking(
                    "vault_health_loop_failed",
                    "Record Vault health loop failure safely",
                    {"error_type": type(e).__name__},
                )
                logger.error("Health check loop error: %s", e)
                vault_health_check_failures.inc()
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self) -> None:
        """Perform single health check and update metrics."""
        try:
            # Check Vault health
            is_healthy = await self.vault_client.health_check()

            # Update uptime counter if healthy
            if is_healthy:
                vault_uptime_seconds.inc(self.check_interval)
                vault_degraded_mode.set(0)
            else:
                vault_degraded_mode.set(1)
            self._record_thinking(
                "vault_health_checked",
                "Perform Vault health check safely",
                {
                    "is_healthy": is_healthy,
                    "previous_health": self._last_health,
                    "health_changed": (
                        self._last_health is not None
                        and is_healthy != self._last_health
                    ),
                    "check_interval_band": _safe_number_band(self.check_interval),
                },
            )

            # Trigger callback on health change
            if self._last_health is not None and is_healthy != self._last_health:
                if self.on_health_change:
                    try:
                        self.on_health_change(is_healthy)
                    except (ValueError, TypeError, RuntimeError) as e:
                        self._record_thinking(
                            "vault_health_callback_failed",
                            "Record Vault health callback failure safely",
                            {"error_type": type(e).__name__},
                        )
                        logger.error("Health change callback error: %s", e)

                if is_healthy:
                    logger.info("Vault health restored")
                else:
                    logger.error("Vault health check failed - entering degraded mode")

            self._last_health = is_healthy

            # Check token expiry
            await self._check_token_expiry()

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as e:
            self._record_thinking(
                "vault_health_check_failed",
                "Record Vault health check failure safely",
                {"error_type": type(e).__name__},
            )
            logger.error("Health check failed: %s", e)
            vault_health_check_failures.inc()
            vault_degraded_mode.set(1)

    async def _check_token_expiry(self) -> None:
        """Check token expiry and update metrics."""
        if not self.vault_client.token_expiry:
            self._record_thinking(
                "vault_token_expiry_checked",
                "Check missing Vault token expiry safely",
                {"token_expiry_present": False},
            )
            return

        now = datetime.now()
        expiry = self.vault_client.token_expiry

        if expiry > now:
            seconds_left = (expiry - now).total_seconds()
            vault_token_expiry_seconds.set(max(0, seconds_left))
            self._record_thinking(
                "vault_token_expiry_checked",
                "Check Vault token expiry safely",
                {
                    "token_expiry_present": True,
                    "expired": False,
                    "seconds_left_band": _safe_number_band(seconds_left),
                    "warning_threshold_band": _safe_number_band(
                        self.token_warning_threshold
                    ),
                    "warning_sent": self._token_warning_sent,
                },
            )

            # Warn if token expiring soon
            if seconds_left < self.token_warning_threshold:
                if not self._token_warning_sent:
                    logger.warning("Vault token expires in %.0f seconds", seconds_left)
                    if self.on_token_expiry_warning:
                        try:
                            self.on_token_expiry_warning()
                        except (ValueError, TypeError, RuntimeError) as e:
                            self._record_thinking(
                                "vault_token_warning_callback_failed",
                                "Record Vault token warning callback failure safely",
                                {"error_type": type(e).__name__},
                            )
                            logger.error("Token expiry callback error: %s", e)
                    self._token_warning_sent = True
            else:
                self._token_warning_sent = False
        else:
            vault_token_expiry_seconds.set(0)
            if not self._token_warning_sent:
                logger.error("Vault token has expired!")
                self._token_warning_sent = True
            self._record_thinking(
                "vault_token_expiry_checked",
                "Report expired Vault token safely",
                {
                    "token_expiry_present": True,
                    "expired": True,
                    "warning_sent": self._token_warning_sent,
                },
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status.

        Returns:
            Dictionary with monitoring status
        """
        status = {
            "running": self._running,
            "last_health": self._last_health,
            "check_interval": self.check_interval,
            "token_warning_sent": self._token_warning_sent,
        }
        self._record_thinking(
            "vault_health_status_reported",
            "Report Vault health monitor status safely",
            {
                "running": self._running,
                "last_health": self._last_health,
                "check_interval_band": _safe_number_band(self.check_interval),
                "token_warning_sent": self._token_warning_sent,
            },
        )
        return status


class VaultMetricsReporter:
    """Report Vault metrics for monitoring systems.

    This class provides methods to export Vault metrics in various
    formats for integration with monitoring systems like Prometheus,
    Grafana, or custom dashboards.
    """

    def __init__(self, vault_client):
        """Initialize metrics reporter.

        Args:
            vault_client: VaultClient instance
        """
        self.vault_client = vault_client

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus exposition format.

        Returns:
            Prometheus-formatted metrics string
        """
        return prom.generate_latest(prom.REGISTRY).decode("utf-8")

    async def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary.

        Returns:
            Dictionary with health information
        """
        summary = {
            "vault_addr": self.vault_client.vault_addr,
            "authenticated": self.vault_client.authenticated,
            "is_healthy": self.vault_client.is_healthy,
            "is_degraded": self.vault_client.is_degraded,
            "cache_stats": self.vault_client.get_cache_stats(),
        }

        if self.vault_client.token_expiry:
            seconds_left = (
                self.vault_client.token_expiry - datetime.now()
            ).total_seconds()
            summary["token_expires_in_seconds"] = max(0, seconds_left)

        return summary

    async def check_readiness(self) -> bool:
        """Check if Vault client is ready to serve requests.

        Returns:
            True if ready, False otherwise
        """
        if not self.vault_client.authenticated:
            return False

        if self.vault_client.is_degraded:
            return False

        # Check token not expired
        if self.vault_client.token_expiry:
            if datetime.now() >= self.vault_client.token_expiry:
                return False

        return True

    async def check_liveness(self) -> bool:
        """Check if Vault client is alive.

        This is a lightweight check that doesn't require API calls.

        Returns:
            True if alive, False otherwise
        """
        return self.vault_client.client is not None

