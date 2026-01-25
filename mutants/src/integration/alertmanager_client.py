"""
AlertManager Integration Client
Real-time alert stream subscription

Module: src/integration/alertmanager_client.py
Purpose: Subscribe to AlertManager alerts for reactive MAPE-K triggering
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass

try:
    import aiohttp
    import websockets
except ImportError:
    aiohttp = None
    websockets = None

logger = logging.getLogger(__name__)


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
    
    def __init__(self, alertmanager_url: str = "http://localhost:9093",
                 webhook_port: int = 5000,
                 webhook_path: str = "/webhooks/alerts"):
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
    
    async def start_webhook_server(self):
        """Start webhook server to receive alerts"""
        try:
            import aiohttp.web
        except ImportError:
            logger.warning("aiohttp.web not available, cannot start webhook server")
            return
        
        async def alert_handler(request):
            """Handle incoming alerts"""
            try:
                data = await request.json()
                logger.info(f"📨 Received {len(data.get('alerts', []))} alerts")
                
                # Parse alerts
                alerts = self._parse_alerts(data.get('alerts', []))
                
                # Trigger callbacks
                for callback in self.alert_callbacks:
                    try:
                        await callback(alerts)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
                
                return aiohttp.web.json_response({"status": "ok"})
            
            except Exception as e:
                logger.error(f"Error handling alert: {e}")
                return aiohttp.web.json_response(
                    {"error": str(e)}, 
                    status=400
                )
        
        app = aiohttp.web.Application()
        app.router.add_post(self.webhook_path, alert_handler)
        
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, '0.0.0.0', self.webhook_port)
        await site.start()
        
        self.server = runner
        self.is_listening = True
        
        logger.info(f"✅ Alert webhook server listening on port {self.webhook_port}")
    
    async def stop_webhook_server(self):
        """Stop webhook server"""
        if self.server:
            await self.server.cleanup()
            self.is_listening = False
            logger.info("⏹️ Alert webhook server stopped")
    
    def subscribe(self, callback: Callable):
        """Subscribe to alerts
        
        Args:
            callback: Async function to call on alerts
        """
        self.alert_callbacks.append(callback)
        logger.info(f"📬 Subscribed to alerts (total: {len(self.alert_callbacks)})")
    
    def _parse_alerts(self, raw_alerts: List[Dict]) -> List[Alert]:
        """Parse raw AlertManager alerts"""
        alerts = []
        
        for raw in raw_alerts:
            try:
                labels = raw.get('labels', {})
                severity = labels.get('severity', 'info').lower()
                
                alert = Alert(
                    label=labels.get('alertname', 'unknown'),
                    value=float(labels.get('value', 0)),
                    severity=AlertSeverity(severity) 
                        if severity in [s.value for s in AlertSeverity]
                        else AlertSeverity.INFO,
                    timestamp=datetime.fromisoformat(
                        raw.get('startsAt', datetime.now().isoformat())
                    ),
                    source=labels.get('instance', 'unknown'),
                    description=raw.get('annotations', {}).get('description', '')
                )
                alerts.append(alert)
                
            except Exception as e:
                logger.error(f"Error parsing alert: {e}")
        
        return alerts


class MockAlertManagerClient:
    """Mock AlertManager Client (Development/Testing)"""
    
    def __init__(self, alertmanager_url: str = "http://localhost:9093",
                 webhook_port: int = 5000,
                 webhook_path: str = "/webhooks/alerts"):
        """Initialize mock client"""
        self.alertmanager_url = alertmanager_url
        self.webhook_port = webhook_port
        self.webhook_path = webhook_path
        self.alert_callbacks: List[Callable] = []
        self.is_listening = False
        self.alert_queue: asyncio.Queue = asyncio.Queue()
    
    async def start_webhook_server(self):
        """Simulate webhook server"""
        self.is_listening = True
        logger.info(f"[MOCK] 🎯 Alert webhook server listening on port {self.webhook_port}")
        
        # Start background task to simulate alerts
        asyncio.create_task(self._simulate_alerts())
    
    async def stop_webhook_server(self):
        """Stop webhook server"""
        self.is_listening = False
        logger.info("[MOCK] ⏹️ Alert webhook server stopped")
    
    def subscribe(self, callback: Callable):
        """Subscribe to alerts"""
        self.alert_callbacks.append(callback)
        logger.info(f"[MOCK] 📬 Subscribed to alerts (total: {len(self.alert_callbacks)})")
    
    async def inject_alert(self, alert: Alert):
        """Manually inject an alert (for testing)"""
        for callback in self.alert_callbacks:
            try:
                await callback([alert])
            except Exception as e:
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
                        description="Validation latency exceeds threshold"
                    )
                    
                    for callback in self.alert_callbacks:
                        try:
                            await callback([alert])
                        except Exception as e:
                            logger.error(f"Error in alert callback: {e}")
            
            except Exception as e:
                logger.error(f"Error in alert simulation: {e}")


class AlertMessageRouter:
    """Route alerts to MAPE-K components"""
    
    def __init__(self):
        """Initialize router"""
        self.handlers: Dict[str, Callable] = {}
        self.unmatched_handler: Optional[Callable] = None
    
    def register_handler(self, alert_pattern: str, handler: Callable):
        """Register handler for alert pattern
        
        Args:
            alert_pattern: Pattern to match (e.g., "validation_latency")
            handler: Async function to handle matching alerts
        """
        self.handlers[alert_pattern] = handler
        logger.info(f"Registered handler for pattern: {alert_pattern}")
    
    def register_default_handler(self, handler: Callable):
        """Register handler for unmatched alerts"""
        self.unmatched_handler = handler
    
    async def route_alerts(self, alerts: List[Alert]):
        """Route alerts to appropriate handlers"""
        for alert in alerts:
            matched = False
            
            # Try pattern matching
            for pattern, handler in self.handlers.items():
                if pattern.lower() in alert.label.lower():
                    logger.info(f"Routing alert {alert.label} to {pattern} handler")
                    try:
                        await handler(alert)
                        matched = True
                        break
                    except Exception as e:
                        logger.error(f"Error in handler: {e}")
            
            # Default handler for unmatched
            if not matched and self.unmatched_handler:
                logger.info(f"Routing unmatched alert {alert.label} to default handler")
                try:
                    await self.unmatched_handler(alert)
                except Exception as e:
                    logger.error(f"Error in default handler: {e}")


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
        description="Validation latency exceeds threshold"
    )
    
    await client.inject_alert(test_alert)
    
    # Let it process
    await asyncio.sleep(1)
    
    await client.stop_webhook_server()
    
    print("\n✅ AlertManager client test complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
