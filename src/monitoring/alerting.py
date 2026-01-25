"""
Alerting System for x0tta6bl4.

Integrates with:
- Prometheus Alertmanager
- Telegram notifications
- PagerDuty (optional)

Features:
- Singleton pattern for centralized management
- Retry logic with exponential backoff
- Rate limiting to prevent alert storms
- Health checks for alerting channels
- Async and sync support
"""

import logging
import os
import asyncio
import time
from typing import Dict, Optional, List, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("⚠️ httpx not available. Alerting will be limited.")


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert structure"""
    name: str
    severity: AlertSeverity
    message: str
    labels: Dict[str, str]
    annotations: Optional[Dict[str, str]] = None


class AlertManager:
    """
    Centralized alerting manager.
    
    Supports:
    - Prometheus Alertmanager
    - Telegram notifications
    - PagerDuty (optional)
    
    Features:
    - Retry logic with exponential backoff
    - Rate limiting to prevent alert storms
    - Health checks for channels
    - Singleton pattern support
    """
    
    # Class-level singleton
    _instance: Optional['AlertManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        alertmanager_url: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        pagerduty_integration_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        rate_limit_per_minute: int = 60
    ):
        """
        Initialize AlertManager.
        
        Args:
            alertmanager_url: Prometheus Alertmanager URL (e.g., http://alertmanager:9093)
            telegram_bot_token: Telegram bot token for notifications
            telegram_chat_id: Telegram chat ID for notifications
            pagerduty_integration_key: PagerDuty integration key (optional)
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay for retries (seconds)
            rate_limit_per_minute: Maximum alerts per minute per alert name
        """
        self.alertmanager_url = alertmanager_url or os.getenv("ALERTMANAGER_URL")
        self.telegram_bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_ALERT_CHAT_ID")
        self.pagerduty_integration_key = pagerduty_integration_key or os.getenv("PAGERDUTY_INTEGRATION_KEY")
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_per_minute = rate_limit_per_minute
        
        # Rate limiting: track alerts per minute per alert name
        self._rate_limit_tracker: Dict[str, List[float]] = defaultdict(list)
        
        # Health status for each channel
        self._channel_health: Dict[str, bool] = {
            "alertmanager": True,
            "telegram": True,
            "pagerduty": True
        }
        
        self._http_client = None
        if HTTPX_AVAILABLE:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        
        logger.info("AlertManager initialized")
    
    def _check_rate_limit(self, alert_name: str) -> bool:
        """
        Check if alert is within rate limit.
        
        Args:
            alert_name: Name of the alert
            
        Returns:
            True if within rate limit, False otherwise
        """
        now = time.time()
        minute_ago = now - 60.0
        
        # Clean old entries
        self._rate_limit_tracker[alert_name] = [
            timestamp for timestamp in self._rate_limit_tracker[alert_name]
            if timestamp > minute_ago
        ]
        
        # Check limit
        if len(self._rate_limit_tracker[alert_name]) >= self.rate_limit_per_minute:
            return False
        
        # Record this alert
        self._rate_limit_tracker[alert_name].append(now)
        return True
    
    async def send_alert(
        self,
        alert_name: str,
        severity: AlertSeverity,
        message: str,
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
        skip_rate_limit: bool = False
    ):
        """
        Send alert to all configured channels.
        
        Args:
            alert_name: Name of the alert
            severity: Alert severity
            message: Alert message
            labels: Additional labels for Prometheus
            annotations: Additional annotations for Prometheus
            skip_rate_limit: Skip rate limiting (for critical alerts)
        """
        # Rate limiting (skip for critical alerts)
        if not skip_rate_limit and severity != AlertSeverity.CRITICAL:
            if not self._check_rate_limit(alert_name):
                logger.debug(f"⚠️ Alert {alert_name} rate limited")
                return
        
        alert = Alert(
            name=alert_name,
            severity=severity,
            message=message,
            labels=labels or {},
            annotations=annotations or {}
        )
        
        # Send to all channels
        tasks = []
        
        if self.alertmanager_url and self._channel_health.get("alertmanager", True):
            tasks.append(self._send_to_alertmanager_with_retry(alert))
        
        if self.telegram_bot_token and self.telegram_chat_id and self._channel_health.get("telegram", True):
            tasks.append(self._send_to_telegram_with_retry(alert))
        
        if self.pagerduty_integration_key and severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] and self._channel_health.get("pagerduty", True):
            tasks.append(self._send_to_pagerduty_with_retry(alert))
        
        # Execute all tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Alert sending failed: {result}")
    
    async def _send_to_alertmanager_with_retry(self, alert: Alert):
        """Send alert to Alertmanager with retry logic."""
        for attempt in range(self.max_retries):
            try:
                await self._send_to_alertmanager(alert)
                self._channel_health["alertmanager"] = True
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️ Alertmanager send failed (attempt {attempt + 1}/{self.max_retries}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Alertmanager send failed after {self.max_retries} attempts: {e}")
                    self._channel_health["alertmanager"] = False
                    raise
    
    async def _send_to_telegram_with_retry(self, alert: Alert):
        """Send alert to Telegram with retry logic."""
        for attempt in range(self.max_retries):
            try:
                await self._send_to_telegram(alert)
                self._channel_health["telegram"] = True
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️ Telegram send failed (attempt {attempt + 1}/{self.max_retries}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Telegram send failed after {self.max_retries} attempts: {e}")
                    self._channel_health["telegram"] = False
                    raise
    
    async def _send_to_pagerduty_with_retry(self, alert: Alert):
        """Send alert to PagerDuty with retry logic."""
        for attempt in range(self.max_retries):
            try:
                await self._send_to_pagerduty(alert)
                self._channel_health["pagerduty"] = True
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️ PagerDuty send failed (attempt {attempt + 1}/{self.max_retries}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ PagerDuty send failed after {self.max_retries} attempts: {e}")
                    self._channel_health["pagerduty"] = False
                    raise
    
    async def _send_to_alertmanager(self, alert: Alert):
        """Send alert to Prometheus Alertmanager."""
        if not self.alertmanager_url or not HTTPX_AVAILABLE:
            return
        
        try:
            annotations = {
                "summary": alert.message,
                "description": f"x0tta6bl4 alert: {alert.message}",
                **(alert.annotations or {})
            }
            if "runbook_url" in alert.annotations:
                annotations["runbook_url"] = alert.annotations["runbook_url"]

            alert_data = {
                "labels": {
                    "alertname": alert.name,
                    "severity": alert.severity.value,
                    "service": "x0tta6bl4",
                    **alert.labels
                },
                "annotations": annotations
            }
            
            response = await self._http_client.post(
                f"{self.alertmanager_url}/api/v1/alerts",
                json=[alert_data],
                timeout=5.0
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Alert sent to Alertmanager: {alert.name}")
            else:
                logger.warning(f"⚠️ Alertmanager returned {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send alert to Alertmanager: {e}")
    
    async def _send_to_telegram(self, alert: Alert):
        """Send alert to Telegram."""
        if not self.telegram_bot_token or not self.telegram_chat_id or not HTTPX_AVAILABLE:
            return
        
        try:
            # Format message
            severity_emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "❌",
                AlertSeverity.CRITICAL: "🚨"
            }
            
            emoji = severity_emoji.get(alert.severity, "📢")
            message_text = f"{emoji} *[{alert.severity.value.upper()}] {alert.name}*\n\n{alert.message}"
            
            if alert.labels:
                labels_text = "\n".join([f"• {k}: {v}" for k, v in alert.labels.items()])
                message_text += f"\n\n*Labels:*\n{labels_text}"
            
            if alert.annotations and alert.annotations.get("runbook_url"):
                message_text += f"\n\n📖 [Runbook]({alert.annotations['runbook_url']})"

            response = await self._http_client.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message_text,
                    "parse_mode": "Markdown"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Alert sent to Telegram: {alert.name}")
            else:
                logger.warning(f"⚠️ Telegram API returned {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send alert to Telegram: {e}")
    
    async def _send_to_pagerduty(self, alert: Alert):
        """Send alert to PagerDuty."""
        if not self.pagerduty_integration_key or not HTTPX_AVAILABLE:
            return
        
        try:
            event = {
                "routing_key": self.pagerduty_integration_key,
                "event_action": "trigger",
                "payload": {
                    "summary": f"{alert.name}: {alert.message}",
                    "severity": alert.severity.value,
                    "source": "x0tta6bl4",
                    "custom_details": {
                        "labels": alert.labels,
                        "annotations": alert.annotations or {}
                    }
                }
            }
            if alert.annotations and alert.annotations.get("runbook_url"):
                event["links"] = [{"href": alert.annotations["runbook_url"], "text": "Runbook"}]

            response = await self._http_client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=event,
                timeout=5.0
            )
            
            if response.status_code in [200, 202]:
                logger.debug(f"✅ Alert sent to PagerDuty: {alert.name}")
            else:
                logger.warning(f"⚠️ PagerDuty returned {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send alert to PagerDuty: {e}")
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()


    def get_health_status(self) -> Dict[str, bool]:
        """Get health status of all alerting channels."""
        return self._channel_health.copy()
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Perform health check on all configured channels.
        
        Returns:
            Dict with health status for each channel
        """
        health = {}
        
        # Check Alertmanager
        if self.alertmanager_url:
            try:
                if HTTPX_AVAILABLE and self._http_client:
                    response = await self._http_client.get(
                        f"{self.alertmanager_url}/-/healthy",
                        timeout=5.0
                    )
                    health["alertmanager"] = response.status_code == 200
                else:
                    health["alertmanager"] = False
            except Exception:
                health["alertmanager"] = False
        else:
            health["alertmanager"] = None  # Not configured
        
        # Check Telegram (simple ping)
        if self.telegram_bot_token and self.telegram_chat_id:
            health["telegram"] = True  # Assume healthy if configured
        else:
            health["telegram"] = None  # Not configured
        
        # Check PagerDuty (assume healthy if configured)
        if self.pagerduty_integration_key:
            health["pagerduty"] = True
        else:
            health["pagerduty"] = None  # Not configured
        
        # Update internal health status
        for channel, status in health.items():
            if status is not None:
                self._channel_health[channel] = status
        
        return health

    # --- Predefined Alerting Rules for Mesh Network ---
    async def send_spiffe_renewal_failure_alert(
        self,
        error_message: str,
        spiffe_id: str,
        runbook_url: Optional[str] = None
    ):
        """Send critical alert for SPIFFE SVID renewal failure."""
        labels = {"component": "spiffe-auto-renew", "spiffe_id": spiffe_id}
        annotations = {"runbook_url": runbook_url} if runbook_url else None
        await self.send_alert(
            alert_name="SPIFFE_SVID_RenewalFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"Failed to renew SPIFFE SVID for {spiffe_id}: {error_message}",
            labels=labels,
            annotations=annotations,
            skip_rate_limit=True
        )

    async def send_spiffe_expiring_soon_alert(
        self,
        spiffe_id: str,
        time_until_expiry_seconds: int,
        runbook_url: Optional[str] = None
    ):
        """Send warning alert for SPIFFE SVID expiring soon."""
        labels = {"component": "spiffe-auto-renew", "spiffe_id": spiffe_id}
        annotations = {"runbook_url": runbook_url} if runbook_url else None
        await self.send_alert(
            alert_name="SPIFFE_SVID_ExpiringSoon",
            severity=AlertSeverity.WARNING,
            message=f"SPIFFE SVID for {spiffe_id} expires in {time_until_expiry_seconds} seconds.",
            labels=labels,
            annotations=annotations
        )

    async def send_pqc_fallback_alert(
        self,
        reason: str,
        node_id: str,
        runbook_url: Optional[str] = None
    ):
        """Send critical alert when PQC falls back to insecure stub."""
        labels = {"component": "pqc-security", "node_id": node_id}
        annotations = {"runbook_url": runbook_url} if runbook_url else None
        await self.send_alert(
            alert_name="PQC_Backend_Fallback_Activated",
            severity=AlertSeverity.CRITICAL,
            message=f"PQC backend fell back to insecure stub on node {node_id}: {reason}",
            labels=labels,
            annotations=annotations,
            skip_rate_limit=True
        )

    async def send_ebpf_load_failure_alert(
        self,
        program_name: str,
        interface: str,
        error_message: str,
        node_id: str,
        runbook_url: Optional[str] = None
    ):
        """Send error alert for eBPF program load or attach failure."""
        labels = {"component": "ebpf-loader", "program": program_name, "interface": interface, "node_id": node_id}
        annotations = {"runbook_url": runbook_url} if runbook_url else None
        await self.send_alert(
            alert_name="EBPF_Program_LoadFailure",
            severity=AlertSeverity.ERROR,
            message=f"Failed to load or attach eBPF program {program_name} on {interface} (node {node_id}): {error_message}",
            labels=labels,
            annotations=annotations,
            skip_rate_limit=True
        )

    async def send_mesh_node_offline_alert(
        self,
        node_id: str,
        last_seen_seconds_ago: int,
        runbook_url: Optional[str] = None
    ):
        """Send critical alert when a mesh node goes offline."""
        labels = {"component": "mesh-status", "node_id": node_id}
        annotations = {"runbook_url": runbook_url} if runbook_url else None
        await self.send_alert(
            alert_name="Mesh_Node_Offline",
            severity=AlertSeverity.CRITICAL,
            message=f"Mesh node {node_id} is offline. Last seen {last_seen_seconds_ago} seconds ago.",
            labels=labels,
            annotations=annotations,
            skip_rate_limit=True
        )

# Global alert manager instance (singleton)
_alert_manager: Optional[AlertManager] = None
_alert_manager_lock = asyncio.Lock()


async def get_alert_manager() -> AlertManager:
    """Get or create global AlertManager instance (thread-safe)."""
    global _alert_manager
    if _alert_manager is None:
        async with _alert_manager_lock:
            if _alert_manager is None:
                _alert_manager = AlertManager()
    return _alert_manager


def get_alert_manager_sync() -> AlertManager:
    """Get or create global AlertManager instance (sync version)."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


async def send_alert(
    alert_name: str,
    severity: AlertSeverity,
    message: str,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
    skip_rate_limit: bool = False
):
    """
    Convenience function to send alert.
    
    Args:
        alert_name: Name of the alert
        severity: Alert severity
        message: Alert message
        labels: Additional labels for Prometheus
        annotations: Additional annotations for Prometheus
        skip_rate_limit: Skip rate limiting (for critical alerts)
    """
    manager = await get_alert_manager()
    await manager.send_alert(alert_name, severity, message, labels, annotations, skip_rate_limit)


def send_alert_sync(
    alert_name: str,
    severity: AlertSeverity,
    message: str,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
    skip_rate_limit: bool = False
):
    """
    Convenience function to send alert (sync version).
    
    Args:
        alert_name: Name of the alert
        severity: Alert severity
        message: Alert message
        labels: Additional labels for Prometheus
        annotations: Additional annotations for Prometheus
        skip_rate_limit: Skip rate limiting (for critical alerts)
    """
    manager = get_alert_manager_sync()
    # Run async function in new event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create task
            asyncio.create_task(manager.send_alert(alert_name, severity, message, labels, annotations, skip_rate_limit))
        else:
            loop.run_until_complete(manager.send_alert(alert_name, severity, message, labels, annotations, skip_rate_limit))
    except RuntimeError:
        # No event loop, create new one
        asyncio.run(manager.send_alert(alert_name, severity, message, labels, annotations, skip_rate_limit))

