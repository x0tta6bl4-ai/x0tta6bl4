"""
Alert Manager for Geo-Leak Detector
Handles Telegram, Redis pub/sub, and webhook alerts
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import aiohttp
from telegram import Bot
from telegram.constants import ParseMode
import aioredis

from config.settings import settings
from src.core.leak_detector import LeakEvent, LeakSeverity
from src.models.database import AlertLog, async_session_maker
import structlog


logger = structlog.get_logger()


@dataclass
class AlertChannel:
    """Alert channel configuration"""
    name: str
    enabled: bool
    severity_filter: List[LeakSeverity]


class RedisAlertPublisher:
    """Redis pub/sub for real-time alerts"""
    
    CHANNEL_LEAKS = "geo-leak-detector:leaks"
    CHANNEL_ALERTS = "geo-leak-detector:alerts"
    CHANNEL_STATUS = "geo-leak-detector:status"
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.logger = structlog.get_logger().bind(component="redis_alert_publisher")
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            self.logger.info("Disconnected from Redis")
    
    async def publish_leak(self, leak_event: LeakEvent):
        """Publish leak event to Redis"""
        if not self.redis:
            return
        
        message = {
            "type": "leak_detected",
            "timestamp": datetime.utcnow().isoformat(),
            "data": leak_event.to_dict()
        }
        
        try:
            await self.redis.publish(
                self.CHANNEL_LEAKS,
                json.dumps(message)
            )
            self.logger.debug("Published leak to Redis", leak_type=leak_event.leak_type.value)
        except Exception as e:
            self.logger.error("Failed to publish leak to Redis", error=str(e))
    
    async def publish_alert(self, alert_type: str, data: Dict[str, Any]):
        """Publish alert to Redis"""
        if not self.redis:
            return
        
        message = {
            "type": alert_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        try:
            await self.redis.publish(
                self.CHANNEL_ALERTS,
                json.dumps(message)
            )
        except Exception as e:
            self.logger.error("Failed to publish alert to Redis", error=str(e))
    
    async def publish_status(self, status: Dict[str, Any]):
        """Publish system status to Redis"""
        if not self.redis:
            return
        
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": status
        }
        
        try:
            await self.redis.setex(
                "geo-leak-detector:current_status",
                60,  # Expire after 60 seconds
                json.dumps(message)
            )
        except Exception as e:
            self.logger.error("Failed to publish status to Redis", error=str(e))
    
    async def get_recent_leaks(self, count: int = 100) -> List[Dict]:
        """Get recent leaks from Redis list"""
        if not self.redis:
            return []
        
        try:
            leaks = await self.redis.lrange(
                "geo-leak-detector:recent_leaks",
                0,
                count - 1
            )
            return [json.loads(leak) for leak in leaks]
        except Exception as e:
            self.logger.error("Failed to get recent leaks from Redis", error=str(e))
            return []
    
    async def add_to_recent_leaks(self, leak_event: LeakEvent):
        """Add leak to recent leaks list"""
        if not self.redis:
            return
        
        try:
            # Add to list
            await self.redis.lpush(
                "geo-leak-detector:recent_leaks",
                json.dumps(leak_event.to_dict())
            )
            # Trim to keep only last 1000
            await self.redis.ltrim("geo-leak-detector:recent_leaks", 0, 999)
        except Exception as e:
            self.logger.error("Failed to add to recent leaks", error=str(e))


class TelegramAlertManager:
    """Telegram Bot for critical alerts"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot: Optional[Bot] = None
        self.logger = structlog.get_logger().bind(component="telegram_alert")
    
    async def connect(self):
        """Initialize Telegram bot"""
        try:
            self.bot = Bot(token=self.bot_token)
            self.logger.info("Telegram bot initialized")
        except Exception as e:
            self.logger.error("Failed to initialize Telegram bot", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect Telegram bot"""
        if self.bot:
            await self.bot.session.close()
            self.logger.info("Telegram bot disconnected")
    
    def _format_leak_message(self, leak: LeakEvent) -> str:
        """Format leak event for Telegram message"""
        emoji_map = {
            LeakSeverity.INFO: "ℹ️",
            LeakSeverity.WARNING: "⚠️",
            LeakSeverity.CRITICAL: "🚨"
        }
        
        emoji = emoji_map.get(leak.severity, "⚠️")
        
        message = f"""
{emoji} <b>GEOCATION LEAK DETECTED</b> {emoji}

<b>Type:</b> <code>{leak.leak_type.value}</code>
<b>Severity:</b> <code>{leak.severity.value.upper()}</code>
<b>Time:</b> {leak.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

<b>Message:</b>
<pre>{leak.message}</pre>

<b>Detected Value:</b>
<code>{leak.detected_value}</code>

<b>Expected Value:</b>
<code>{leak.expected_value or 'N/A'}</code>
"""
        
        if leak.detected_country:
            message += f"\n<b>Country:</b> {leak.detected_country}"
        if leak.detected_city:
            message += f"\n<b>City:</b> {leak.detected_city}"
        if leak.detected_isp:
            message += f"\n<b>ISP:</b> {leak.detected_isp}"
        if leak.source_ip:
            message += f"\n<b>Source IP:</b> <code>{leak.source_ip}</code>"
        
        if leak.remediation_action:
            message += f"""

✅ <b>Remediation Action:</b>
<pre>{leak.remediation_action}</pre>
"""
        
        return message
    
    async def send_leak_alert(self, leak: LeakEvent) -> bool:
        """Send leak alert via Telegram"""
        if not self.bot:
            self.logger.warning("Telegram bot not initialized")
            return False
        
        # Check severity filter
        if leak.severity == LeakSeverity.INFO and not settings.telegram.alert_on_info:
            return False
        if leak.severity == LeakSeverity.WARNING and not settings.telegram.alert_on_warning:
            return False
        if leak.severity == LeakSeverity.CRITICAL and not settings.telegram.alert_on_critical:
            return False
        
        try:
            message = self._format_leak_message(leak)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            self.logger.info(
                "Telegram alert sent",
                leak_type=leak.leak_type.value,
                severity=leak.severity.value
            )
            
            # Log to database
            await self._log_alert(leak, "telegram", "sent", 200)
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to send Telegram alert", error=str(e))
            await self._log_alert(leak, "telegram", "failed", 0, str(e))
            return False
    
    async def send_status_update(self, status: Dict[str, Any]) -> bool:
        """Send status update via Telegram"""
        if not self.bot:
            return False
        
        try:
            message = f"""
📊 <b>Geo-Leak Detector Status</b>

<b>Status:</b> {'✅ Running' if status.get('running') else '❌ Stopped'}
<b>Check Interval:</b> {status.get('check_interval', 'N/A')}s
<b>Total Leaks Detected:</b> {status.get('total_leaks', 0)}
<b>Last Check:</b> {status.get('last_check', 'N/A')}
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to send status update", error=str(e))
            return False
    
    async def _log_alert(self, leak: LeakEvent, channel: str, status: str, response_code: int, message: str = ""):
        """Log alert to database"""
        try:
            async with async_session_maker() as session:
                alert_log = AlertLog(
                    leak_event_id=leak.raw_data.get("id") if leak.raw_data else None,
                    channel=channel,
                    status=status,
                    response_code=response_code,
                    response_message=message
                )
                session.add(alert_log)
                await session.commit()
        except Exception as e:
            self.logger.error("Failed to log alert", error=str(e))


class WebhookAlertManager:
    """Webhook alerts for external integrations"""
    
    def __init__(self, webhook_url: str, headers: Optional[Dict[str, str]] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.logger = structlog.get_logger().bind(component="webhook_alert")
    
    async def send_leak_alert(self, leak: LeakEvent) -> bool:
        """Send leak alert via webhook"""
        try:
            payload = {
                "type": "leak_detected",
                "timestamp": datetime.utcnow().isoformat(),
                "data": leak.to_dict()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        **self.headers
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        self.logger.info("Webhook alert sent", leak_type=leak.leak_type.value)
                        return True
                    else:
                        self.logger.error(
                            "Webhook returned error",
                            status=resp.status,
                            leak_type=leak.leak_type.value
                        )
                        return False
                        
        except Exception as e:
            self.logger.error("Failed to send webhook alert", error=str(e))
            return False


class AlertManager:
    """Main alert manager coordinating all alert channels"""
    
    def __init__(self):
        self.redis_publisher: Optional[RedisAlertPublisher] = None
        self.telegram_manager: Optional[TelegramAlertManager] = None
        self.webhook_manager: Optional[WebhookAlertManager] = None
        
        self.logger = structlog.get_logger().bind(component="alert_manager")
        
        self._init_channels()
    
    def _init_channels(self):
        """Initialize alert channels based on configuration"""
        # Redis
        if settings.redis.host:
            self.redis_publisher = RedisAlertPublisher(settings.redis.url)
        
        # Telegram
        if settings.telegram.enabled and settings.telegram.bot_token:
            self.telegram_manager = TelegramAlertManager(
                settings.telegram.bot_token,
                settings.telegram.chat_id
            )
        
        # Webhook (if configured)
        webhook_url = settings.detection.raw_data.get("webhook_url") if hasattr(settings.detection, 'raw_data') else None
        if webhook_url:
            self.webhook_manager = WebhookAlertManager(webhook_url)
    
    async def start(self):
        """Start alert manager and connect to channels"""
        self.logger.info("Starting alert manager")
        
        if self.redis_publisher:
            await self.redis_publisher.connect()
        
        if self.telegram_manager:
            await self.telegram_manager.connect()
    
    async def stop(self):
        """Stop alert manager and disconnect from channels"""
        self.logger.info("Stopping alert manager")
        
        if self.redis_publisher:
            await self.redis_publisher.disconnect()
        
        if self.telegram_manager:
            await self.telegram_manager.disconnect()
    
    async def send_alert(self, leak: LeakEvent):
        """Send alert through all configured channels"""
        self.logger.info(
            "Sending alert",
            leak_type=leak.leak_type.value,
            severity=leak.severity.value
        )
        
        # Redis pub/sub (real-time)
        if self.redis_publisher:
            await self.redis_publisher.publish_leak(leak)
            await self.redis_publisher.add_to_recent_leaks(leak)
        
        # Telegram (critical alerts)
        if self.telegram_manager:
            await self.telegram_manager.send_leak_alert(leak)
        
        # Webhook (external integrations)
        if self.webhook_manager:
            await self.webhook_manager.send_leak_alert(leak)
    
    async def publish_status(self, status: Dict[str, Any]):
        """Publish system status"""
        if self.redis_publisher:
            await self.redis_publisher.publish_status(status)
    
    async def get_recent_leaks(self, count: int = 100) -> List[Dict]:
        """Get recent leaks from Redis"""
        if self.redis_publisher:
            return await self.redis_publisher.get_recent_leaks(count)
        return []
