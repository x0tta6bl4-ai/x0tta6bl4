"""
AlertManager Integration Client
Real-time alert stream subscription

Module: src/integration/alertmanager_client.py
Purpose: Subscribe to AlertManager alerts for reactive MAPE-K triggering
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

try:
    import aiohttp
    import websockets
except ImportError:
    aiohttp = None
    websockets = None

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
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


def _severity_counts(alerts: List["Alert"]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for alert in alerts:
        severity = str(alert.severity.value)
        counts[severity] = counts.get(severity, 0) + 1
    return counts


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Alert:
    """Parsed alert from AlertManager"""

    label: str
    value: float
    severity: AlertSeverity
    timestamp: datetime
    source: str
    description: str


class RealAlertManagerClient:
    """Real AlertManager Client (Production)

    Subscribes to AlertManager alert webhook stream.
    Requires AlertManager configured with webhook receiver.
    """

    def __init__(
        self,
        alertmanager_url: str = "http://localhost:9093",
        webhook_port: int = 5000,
        webhook_path: str = "/webhooks/alerts",
    ):
        """
        Initialize AlertManager client

        Args:
            alertmanager_url: AlertManager API URL
            webhook_port: Port for receiving webhooks
            webhook_path: Path for webhook endpoint
        """
        self.alertmanager_url = alertmanager_url
        self.webhook_port = webhook_port
        self.webhook_path = webhook_path
        self.alert_callbacks: List[Callable] = []
        self.is_listening = False
        self.server = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"real-alertmanager-client:{_safe_hash(alertmanager_url)}",
            role="monitoring",
            capabilities=("ops", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "real_alertmanager_client_init",
                "goal": "Initialize AlertManager webhook client safely",
                "signals": {
                    "alertmanager_url_hash": _safe_hash(alertmanager_url),
                    "webhook_port_band": _safe_number_band(webhook_port),
                    "webhook_path_hash": _safe_hash(webhook_path),
                    "callback_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep raw AlertManager URLs, webhook paths, alert labels, "
                    "sources, and descriptions out of thinking context."
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
                    "redact_alertmanager_url": True,
                    "redact_webhook_path": True,
                    "redact_alert_labels": True,
                    "redact_alert_sources": True,
                    "redact_alert_descriptions": True,
                    "preserve_alert_routing_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, severities, and value bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def start_webhook_server(self):
        """Start webhook server to receive alerts"""
        try:
            import aiohttp.web
        except ImportError:
            self._record_thinking(
                "alertmanager_webhook_start_failed",
                "Record missing aiohttp webhook dependency safely",
                {"error_type": "ImportError"},
            )
            logger.warning("aiohttp.web not available, cannot start webhook server")
            return

        async def alert_handler(request):
            """Handle incoming alerts"""
            try:
                data = await request.json()
                logger.info(f"📨 Received {len(data.get('alerts', []))} alerts")

                # Parse alerts
                alerts = self._parse_alerts(data.get("alerts", []))
                self._record_thinking(
                    "alertmanager_webhook_alerts_received",
                    "Receive AlertManager webhook alerts safely",
                    {
                        "raw_alert_count_bucket": _safe_count_bucket(
                            len(data.get("alerts", []))
                        ),
                        "parsed_alert_count_bucket": _safe_count_bucket(len(alerts)),
                        "severity_counts": _severity_counts(alerts),
                        "callback_count_bucket": _safe_count_bucket(
                            len(self.alert_callbacks)
                        ),
                    },
                )

                # Trigger callbacks
                for callback in self.alert_callbacks:
                    try:
                        await callback(alerts)
                    except Exception as e:
                        self._record_thinking(
                            "alertmanager_callback_failed",
                            "Record AlertManager callback failure safely",
                            {"error_type": type(e).__name__},
                        )
                        logger.error(f"Error in alert callback: {e}")

                return aiohttp.web.json_response({"status": "ok"})

            except Exception as e:
                self._record_thinking(
                    "alertmanager_webhook_request_failed",
                    "Record AlertManager webhook request failure safely",
                    {"error_type": type(e).__name__},
                )
                logger.error(f"Error handling alert: {e}")
                return aiohttp.web.json_response({"error": str(e)}, status=400)

        app = aiohttp.web.Application()
        app.router.add_post(self.webhook_path, alert_handler)

        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, "0.0.0.0", self.webhook_port)  # nosec B104
        await site.start()

        self.server = runner
        self.is_listening = True

        logger.info(f"✅ Alert webhook server listening on port {self.webhook_port}")
        self._record_thinking(
            "alertmanager_webhook_started",
            "Start AlertManager webhook server safely",
            {
                "webhook_port_band": _safe_number_band(self.webhook_port),
                "webhook_path_hash": _safe_hash(self.webhook_path),
                "is_listening": self.is_listening,
            },
        )

    async def stop_webhook_server(self):
        """Stop webhook server"""
        if self.server:
            await self.server.cleanup()
            self.is_listening = False
            logger.info("⏹️ Alert webhook server stopped")
        self._record_thinking(
            "alertmanager_webhook_stopped",
            "Stop AlertManager webhook server safely",
            {"is_listening": self.is_listening},
        )

    def subscribe(self, callback: Callable):
        """Subscribe to alerts

        Args:
            callback: Async function to call on alerts
        """
        self.alert_callbacks.append(callback)
        logger.info(f"📬 Subscribed to alerts (total: {len(self.alert_callbacks)})")
        self._record_thinking(
            "alertmanager_callback_subscribed",
            "Subscribe AlertManager callback safely",
            {"callback_count_bucket": _safe_count_bucket(len(self.alert_callbacks))},
        )

    def _parse_alerts(self, raw_alerts: List[Dict]) -> List[Alert]:
        """Parse raw AlertManager alerts"""
        alerts = []

        for raw in raw_alerts:
            try:
                labels = raw.get("labels", {})
                severity = labels.get("severity", "info").lower()

                alert = Alert(
                    label=labels.get("alertname", "unknown"),
                    value=float(labels.get("value", 0)),
                    severity=(
                        AlertSeverity(severity)
                        if severity in [s.value for s in AlertSeverity]
                        else AlertSeverity.INFO
                    ),
                    timestamp=datetime.fromisoformat(
                        raw.get("startsAt", datetime.now().isoformat())
                    ),
                    source=labels.get("instance", "unknown"),
                    description=raw.get("annotations", {}).get("description", ""),
                )
                alerts.append(alert)

            except Exception as e:
                self._record_thinking(
                    "alertmanager_alert_parse_failed",
                    "Record AlertManager alert parse failure safely",
                    {"error_type": type(e).__name__},
                )
                logger.error(f"Error parsing alert: {e}")

        self._record_thinking(
            "alertmanager_alerts_parsed",
            "Parse AlertManager alerts safely",
            {
                "raw_alert_count_bucket": _safe_count_bucket(len(raw_alerts)),
                "parsed_alert_count_bucket": _safe_count_bucket(len(alerts)),
                "severity_counts": _severity_counts(alerts),
            },
        )
        return alerts


class MockAlertManagerClient:
    """Mock AlertManager Client (Development/Testing)"""

    def __init__(
        self,
        alertmanager_url: str = "http://localhost:9093",
        webhook_port: int = 5000,
        webhook_path: str = "/webhooks/alerts",
    ):
        """Initialize mock client"""
        self.alertmanager_url = alertmanager_url
        self.webhook_port = webhook_port
        self.webhook_path = webhook_path
        self.alert_callbacks: List[Callable] = []
        self.is_listening = False
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"mock-alertmanager-client:{_safe_hash(alertmanager_url)}",
            role="monitoring",
            capabilities=("ops", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mock_alertmanager_client_init",
                "goal": "Initialize mock AlertManager client safely",
                "signals": {
                    "alertmanager_url_hash": _safe_hash(alertmanager_url),
                    "webhook_port_band": _safe_number_band(webhook_port),
                    "webhook_path_hash": _safe_hash(webhook_path),
                    "callback_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep raw alert labels, sources, descriptions, URLs, "
                    "and webhook paths out of thinking context."
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
                    "redact_alertmanager_url": True,
                    "redact_webhook_path": True,
                    "redact_alert_labels": True,
                    "redact_alert_sources": True,
                    "redact_alert_descriptions": True,
                    "preserve_alert_routing_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, severities, and value bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def start_webhook_server(self):
        """Simulate webhook server"""
        self.is_listening = True
        logger.info(
            f"[MOCK] 🎯 Alert webhook server listening on port {self.webhook_port}"
        )

        # Start background task to simulate alerts
        asyncio.create_task(self._simulate_alerts())
        self._record_thinking(
            "mock_alertmanager_webhook_started",
            "Start mock AlertManager alert loop safely",
            {
                "is_listening": self.is_listening,
                "callback_count_bucket": _safe_count_bucket(
                    len(self.alert_callbacks)
                ),
            },
        )

    async def stop_webhook_server(self):
        """Stop webhook server"""
        self.is_listening = False
        logger.info("[MOCK] ⏹️ Alert webhook server stopped")
        self._record_thinking(
            "mock_alertmanager_webhook_stopped",
            "Stop mock AlertManager alert loop safely",
            {"is_listening": self.is_listening},
        )

    def subscribe(self, callback: Callable):
        """Subscribe to alerts"""
        self.alert_callbacks.append(callback)
        logger.info(
            f"[MOCK] 📬 Subscribed to alerts (total: {len(self.alert_callbacks)})"
        )
        self._record_thinking(
            "mock_alertmanager_callback_subscribed",
            "Subscribe mock AlertManager callback safely",
            {"callback_count_bucket": _safe_count_bucket(len(self.alert_callbacks))},
        )

    async def inject_alert(self, alert: Alert):
        """Manually inject an alert (for testing)"""
        self._record_thinking(
            "mock_alertmanager_alert_injected",
            "Inject mock AlertManager alert safely",
            {
                "severity": alert.severity.value,
                "label_hash": _safe_hash(alert.label),
                "source_hash": _safe_hash(alert.source),
                "value_band": _safe_number_band(alert.value),
                "callback_count_bucket": _safe_count_bucket(
                    len(self.alert_callbacks)
                ),
            },
        )
        for callback in self.alert_callbacks:
            try:
                await callback([alert])
            except Exception as e:
                self._record_thinking(
                    "mock_alertmanager_callback_failed",
                    "Record mock AlertManager callback failure safely",
                    {"error_type": type(e).__name__},
                )
                logger.error(f"Error in alert callback: {e}")

    async def _simulate_alerts(self):
        """Simulate random alerts"""
        while self.is_listening:
            try:
                # Simulate occasional validation latency alert
                if asyncio.get_event_loop()._running:
                    await asyncio.sleep(60)  # Alert every minute

                    alert = Alert(
                        label="westworld_charter_validation_latency_high",
                        value=2.5,
                        severity=AlertSeverity.WARNING,
                        timestamp=datetime.now(),
                        source="prometheus",
                        description="Validation latency exceeds threshold",
                    )

                    for callback in self.alert_callbacks:
                        try:
                            await callback([alert])
                        except Exception as e:
                            self._record_thinking(
                                "mock_alertmanager_simulation_callback_failed",
                                "Record simulated alert callback failure safely",
                                {"error_type": type(e).__name__},
                            )
                            logger.error(f"Error in alert callback: {e}")

            except Exception as e:
                self._record_thinking(
                    "mock_alertmanager_simulation_failed",
                    "Record mock AlertManager simulation failure safely",
                    {"error_type": type(e).__name__},
                )
                logger.error(f"Error in alert simulation: {e}")


class AlertMessageRouter:
    """Route alerts to MAPE-K components"""

    def __init__(self):
        """Initialize router"""
        self.handlers: Dict[str, Callable] = {}
        self.unmatched_handler: Optional[Callable] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id="alert-message-router",
            role="coordinator",
            capabilities=("monitoring", "ops", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "alert_message_router_init",
                "goal": "Initialize alert routing safely",
                "signals": {
                    "handler_count_bucket": "0",
                    "has_default_handler": False,
                },
                "safety_boundary": (
                    "Keep raw alert labels, handler patterns, sources, and "
                    "descriptions out of thinking context."
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
                    "redact_alert_labels": True,
                    "redact_handler_patterns": True,
                    "redact_alert_sources": True,
                    "redact_alert_descriptions": True,
                    "preserve_routing_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, severities, and match status.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def register_handler(self, alert_pattern: str, handler: Callable):
        """Register handler for alert pattern

        Args:
            alert_pattern: Pattern to match (e.g., "validation_latency")
            handler: Async function to handle matching alerts
        """
        self.handlers[alert_pattern] = handler
        logger.info(f"Registered handler for pattern: {alert_pattern}")
        self._record_thinking(
            "alert_router_handler_registered",
            "Register alert route handler safely",
            {
                "pattern_hash": _safe_hash(alert_pattern),
                "handler_count_bucket": _safe_count_bucket(len(self.handlers)),
                "has_default_handler": self.unmatched_handler is not None,
            },
        )

    def register_default_handler(self, handler: Callable):
        """Register handler for unmatched alerts"""
        self.unmatched_handler = handler
        self._record_thinking(
            "alert_router_default_handler_registered",
            "Register default alert handler safely",
            {
                "handler_count_bucket": _safe_count_bucket(len(self.handlers)),
                "has_default_handler": True,
            },
        )

    async def route_alerts(self, alerts: List[Alert]):
        """Route alerts to appropriate handlers"""
        matched_count = 0
        unmatched_count = 0
        error_count = 0
        for alert in alerts:
            matched = False

            # Try pattern matching
            for pattern, handler in self.handlers.items():
                if pattern.lower() in alert.label.lower():
                    logger.info(f"Routing alert {alert.label} to {pattern} handler")
                    try:
                        await handler(alert)
                        matched = True
                        matched_count += 1
                        break
                    except Exception as e:
                        error_count += 1
                        self._record_thinking(
                            "alert_router_handler_failed",
                            "Record alert route handler failure safely",
                            {
                                "pattern_hash": _safe_hash(pattern),
                                "alert_label_hash": _safe_hash(alert.label),
                                "error_type": type(e).__name__,
                            },
                        )
                        logger.error(f"Error in handler: {e}")

            # Default handler for unmatched
            if not matched and self.unmatched_handler:
                logger.info(f"Routing unmatched alert {alert.label} to default handler")
                try:
                    await self.unmatched_handler(alert)
                    unmatched_count += 1
                except Exception as e:
                    error_count += 1
                    self._record_thinking(
                        "alert_router_default_handler_failed",
                        "Record default alert handler failure safely",
                        {
                            "alert_label_hash": _safe_hash(alert.label),
                            "error_type": type(e).__name__,
                        },
                    )
                    logger.error(f"Error in default handler: {e}")
            elif not matched:
                unmatched_count += 1
        self._record_thinking(
            "alert_router_alerts_routed",
            "Route AlertManager alerts safely",
            {
                "alert_count_bucket": _safe_count_bucket(len(alerts)),
                "matched_count_bucket": _safe_count_bucket(matched_count),
                "unmatched_count_bucket": _safe_count_bucket(unmatched_count),
                "error_count_bucket": _safe_count_bucket(error_count),
                "severity_counts": _severity_counts(alerts),
                "handler_count_bucket": _safe_count_bucket(len(self.handlers)),
                "has_default_handler": self.unmatched_handler is not None,
            },
        )


def get_alertmanager_client(use_mock: bool = True, **kwargs) -> any:
    """Factory function to get appropriate AlertManager client

    Args:
        use_mock: If True, return MockAlertManagerClient
        **kwargs: Arguments to pass to client constructor

    Returns:
        AlertManager client instance
    """
    if use_mock:
        logger.info("📝 Using MockAlertManagerClient (testing mode)")
        return MockAlertManagerClient(**kwargs)
    else:
        logger.info("🔌 Using RealAlertManagerClient (production mode)")
        return RealAlertManagerClient(**kwargs)


async def main():
    """Test AlertManager client"""

    print("\n🧪 MOCK ALERTMANAGER TEST")
    print("=" * 60)

    client = MockAlertManagerClient()
    router = AlertMessageRouter()

    # Register handlers
    async def handle_validation_latency(alert: Alert):
        print(f"🚨 Handling validation latency alert: {alert.value}s")

    async def handle_default(alert: Alert):
        print(f"📢 Default handler: {alert.label}")

    router.register_handler("validation_latency", handle_validation_latency)
    router.register_default_handler(handle_default)

    # Subscribe
    client.subscribe(router.route_alerts)

    # Start server
    await client.start_webhook_server()

    # Inject test alert
    test_alert = Alert(
        label="westworld_charter_validation_latency_high",
        value=2.5,
        severity=AlertSeverity.WARNING,
        timestamp=datetime.now(),
        source="prometheus",
        description="Validation latency exceeds threshold",
    )

    await client.inject_alert(test_alert)

    # Let it process
    await asyncio.sleep(1)

    await client.stop_webhook_server()

    print("\n✅ AlertManager client test complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
