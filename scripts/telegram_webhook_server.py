#!/usr/bin/env python3
"""
Simple Telegram Webhook Server for Alertmanager
Receives alerts from Alertmanager and forwards them to Telegram
Дата: 2026-01-08
"""

import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    exit(1)


def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def format_alert(alert_data: dict) -> str:
    """Format alert data for Telegram message"""
    alerts = alert_data.get("alerts", [])
    if not alerts:
        return "Empty alert"
    
    alert = alerts[0]
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status = alert.get("status", "unknown")
    
    alertname = labels.get("alertname", "Unknown")
    severity = labels.get("severity", "unknown")
    summary = annotations.get("summary", "No summary")
    description = annotations.get("description", "No description")
    
    if status == "resolved":
        emoji = "✅"
        status_text = "RESOLVED"
    else:
        if severity == "critical":
            emoji = "🚨🚨🚨"
            status_text = "CRITICAL"
        elif severity == "warning":
            emoji = "⚠️"
            status_text = "WARNING"
        else:
            emoji = "ℹ️"
            status_text = "INFO"
    
    message = f"""{emoji} <b>{status_text} ALERT</b>

<b>Alert:</b> {alertname}
<b>Severity:</b> {severity}
<b>Status:</b> {status_text}

<b>Summary:</b>
{summary}

<b>Description:</b>
{description}"""
    
    return message


class AlertWebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for Alertmanager webhooks"""
    
    def do_POST(self):
        """Handle POST requests from Alertmanager"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            alert_data = json.loads(post_data.decode('utf-8'))
            logger.info(f"Received alert: {alert_data.get('alerts', [{}])[0].get('labels', {}).get('alertname', 'Unknown')}")
            
            message = format_alert(alert_data)
            success = send_telegram_message(message)
            
            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Failed to send Telegram message"}).encode())
                
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
    
    def do_GET(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    """Start webhook server"""
    port = int(os.getenv("WEBHOOK_PORT", "8080"))
    server = HTTPServer(('0.0.0.0', port), AlertWebhookHandler)
    logger.info(f"Telegram webhook server started on port {port}")
    logger.info(f"Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"Chat ID: {TELEGRAM_CHAT_ID}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.shutdown()


if __name__ == "__main__":
    main()

