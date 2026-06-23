import asyncio
import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Notifier:
    """Simple notification service (Slack/Telegram/Discord webhook)."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("WEBHOOK_URL")

    def send(self, title: str, message: str, color: str = "#36a64f"):
        """Send notification."""
        if not self.webhook_url:
            logger.warning("No webhook URL configured, skipping notification")
            return

        try:
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": title,
                        "text": message,
                        "footer": "x0tta6bl4 Mesh",
                    }
                ]
            }

            # Support for Discord slack-compatible webhooks
            if "discord" in self.webhook_url:
                payload["username"] = "X0T Bot"

            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def send_async(self, title: str, message: str, color: str = "#36a64f"):
        """Send notification without blocking the event loop."""
        await asyncio.to_thread(self.send, title, message, color)


# Global instance
notifier = Notifier()
