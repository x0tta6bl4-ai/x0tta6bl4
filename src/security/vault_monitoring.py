"""
Vault monitoring and health checking.

This module provides health monitoring, metrics collection, and alerting
for Vault integration. It includes a background health check loop that
monitors Vault availability and token status.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
import prometheus_client as prom
from prometheus_client import REGISTRY

logger = logging.getLogger(__name__)


def _get_or_create_metric(metric_class, name, description, **kwargs):
    """Get existing metric or create new one to avoid duplicate registration."""
    try:
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, '_name') and collector._name == name:
                return collector
        return metric_class(name, description, **kwargs)
    except Exception:
        return metric_class(name, description, registry=None, **kwargs)


# Prometheus metrics - using helper to avoid duplicate registration
vault_token_expiry_seconds = _get_or_create_metric(
    prom.Gauge,
    'vault_token_expiry_seconds',
    'Seconds until Vault token expires'
)
vault_uptime_seconds = _get_or_create_metric(
    prom.Counter,
    'vault_uptime_seconds',
    'Total Vault connection uptime'
)
vault_health_check_failures = _get_or_create_metric(
    prom.Counter,
    'vault_health_check_failures_total',
    'Total health check failures'
)
vault_token_refresh_count = _get_or_create_metric(
    prom.Counter,
    'vault_token_refresh_count_total',
    'Total token refresh operations'
)
vault_degraded_mode = _get_or_create_metric(
    prom.Gauge,
    'vault_degraded_mode',
    'Vault client in degraded mode (1=yes, 0=no)'
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
    
    async def start(self) -> None:
        """Start health monitoring loop."""
        if self._running:
            logger.warning("Health monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info(
            "Vault health monitor started (check every %ds)",
            self.check_interval
        )
    
    async def stop(self) -> None:
        """Stop health monitoring."""
        if not self._running:
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
    
    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
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
            
            # Trigger callback on health change
            if self._last_health is not None and is_healthy != self._last_health:
                if self.on_health_change:
                    try:
                        self.on_health_change(is_healthy)
                    except Exception as e:
                        logger.error("Health change callback error: %s", e)
                
                if is_healthy:
                    logger.info("Vault health restored")
                else:
                    logger.error("Vault health check failed - entering degraded mode")
            
            self._last_health = is_healthy
            
            # Check token expiry
            await self._check_token_expiry()
            
        except Exception as e:
            logger.error("Health check failed: %s", e)
            vault_health_check_failures.inc()
            vault_degraded_mode.set(1)
    
    async def _check_token_expiry(self) -> None:
        """Check token expiry and update metrics."""
        if not self.vault_client.token_expiry:
            return
        
        now = datetime.now()
        expiry = self.vault_client.token_expiry
        
        if expiry > now:
            seconds_left = (expiry - now).total_seconds()
            vault_token_expiry_seconds.set(max(0, seconds_left))
            
            # Warn if token expiring soon
            if seconds_left < self.token_warning_threshold:
                if not self._token_warning_sent:
                    logger.warning(
                        "Vault token expires in %.0f seconds",
                        seconds_left
                    )
                    if self.on_token_expiry_warning:
                        try:
                            self.on_token_expiry_warning()
                        except Exception as e:
                            logger.error("Token expiry callback error: %s", e)
                    self._token_warning_sent = True
            else:
                self._token_warning_sent = False
        else:
            vault_token_expiry_seconds.set(0)
            if not self._token_warning_sent:
                logger.error("Vault token has expired!")
                self._token_warning_sent = True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status.
        
        Returns:
            Dictionary with monitoring status
        """
        return {
            'running': self._running,
            'last_health': self._last_health,
            'check_interval': self.check_interval,
            'token_warning_sent': self._token_warning_sent,
        }


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
        return prom.generate_latest(prom.REGISTRY).decode('utf-8')
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary.
        
        Returns:
            Dictionary with health information
        """
        summary = {
            'vault_addr': self.vault_client.vault_addr,
            'authenticated': self.vault_client.authenticated,
            'is_healthy': self.vault_client.is_healthy,
            'is_degraded': self.vault_client.is_degraded,
            'cache_stats': self.vault_client.get_cache_stats(),
        }
        
        if self.vault_client.token_expiry:
            seconds_left = (
                self.vault_client.token_expiry - datetime.now()
            ).total_seconds()
            summary['token_expires_in_seconds'] = max(0, seconds_left)
        
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