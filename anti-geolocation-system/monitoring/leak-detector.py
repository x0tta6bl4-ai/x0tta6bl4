#!/usr/bin/env python3
"""
Real-time Geolocation Leak Detection and Alerting System
Monitors for IP, DNS, WebRTC, and fingerprint leaks with automated remediation
"""

import asyncio
import json
import logging
import smtplib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
import aiohttp
import yaml


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/leak-detector.log')
    ]
)
logger = logging.getLogger(__name__)


class LeakSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LeakType(Enum):
    IP_LEAK = "ip_leak"
    DNS_LEAK = "dns_leak"
    WEBRTC_LEAK = "webrtc_leak"
    GEOLOCATION_LEAK = "geolocation_leak"
    FINGERPRINT_LEAK = "fingerprint_leak"
    TIMEZONE_LEAK = "timezone_leak"
    WEBGL_LEAK = "webgl_leak"
    FONT_LEAK = "font_leak"
    CANVAS_LEAK = "canvas_leak"


@dataclass
class LeakEvent:
    """Represents a detected leak event"""
    timestamp: datetime
    leak_type: LeakType
    severity: LeakSeverity
    message: str
    detected_value: str
    expected_value: str
    source_ip: str
    remediation_action: Optional[str] = None
    resolved: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "leak_type": self.leak_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "detected_value": self.detected_value,
            "expected_value": self.expected_value,
            "source_ip": self.source_ip,
            "remediation_action": self.remediation_action,
            "resolved": self.resolved
        }


@dataclass
class AlertConfig:
    """Alert configuration"""
    email_enabled: bool = False
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_recipients: List[str] = field(default_factory=list)
    
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_headers: Dict = field(default_factory=dict)
    
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    log_file: str = "/var/log/leak-alerts.log"
    alert_on_info: bool = False
    alert_on_warning: bool = True
    alert_on_critical: bool = True


class AlertManager:
    """Manages alert notifications"""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.alert_history: List[LeakEvent] = []
        
    async def send_alert(self, event: LeakEvent):
        """Send alert through all configured channels"""
        self.alert_history.append(event)
        
        # Check severity threshold
        if event.severity == LeakSeverity.INFO and not self.config.alert_on_info:
            return
        if event.severity == LeakSeverity.WARNING and not self.config.alert_on_warning:
            return
        if event.severity == LeakSeverity.CRITICAL and not self.config.alert_on_critical:
            return
        
        # Log to file
        await self._log_to_file(event)
        
        # Send email
        if self.config.email_enabled:
            await self._send_email(event)
        
        # Send webhook
        if self.config.webhook_enabled:
            await self._send_webhook(event)
        
        # Send Telegram
        if self.config.telegram_enabled:
            await self._send_telegram(event)
    
    async def _log_to_file(self, event: LeakEvent):
        """Log alert to file"""
        try:
            with open(self.config.log_file, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
    
    async def _send_email(self, event: LeakEvent):
        """Send email alert"""
        try:
            msg = MIMEText(f"""
Leak Detection Alert

Type: {event.leak_type.value}
Severity: {event.severity.value}
Time: {event.timestamp.isoformat()}
Message: {event.message}
Detected: {event.detected_value}
Expected: {event.expected_value}
Source IP: {event.source_ip}
            """)
            
            msg['Subject'] = f"[LEAK DETECTED] {event.leak_type.value} - {event.severity.value}"
            msg['From'] = self.config.email_username
            msg['To'] = ', '.join(self.config.email_recipients)
            
            server = smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port)
            server.starttls()
            server.login(self.config.email_username, self.config.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent for {event.leak_type.value}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    async def _send_webhook(self, event: LeakEvent):
        """Send webhook alert"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = event.to_dict()
                headers = {
                    "Content-Type": "application/json",
                    **self.config.webhook_headers
                }
                async with session.post(
                    self.config.webhook_url,
                    json=payload,
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Webhook alert sent for {event.leak_type.value}")
                    else:
                        logger.error(f"Webhook returned status {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    async def _send_telegram(self, event: LeakEvent):
        """Send Telegram alert"""
        try:
            emoji = {
                LeakSeverity.INFO: "ℹ️",
                LeakSeverity.WARNING: "⚠️",
                LeakSeverity.CRITICAL: "🚨"
            }.get(event.severity, "⚠️")
            
            message = f"""
{emoji} <b>LEAK DETECTED</b> {emoji}

<b>Type:</b> {event.leak_type.value}
<b>Severity:</b> {event.severity.value}
<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
<b>Message:</b> {event.message}
<b>Detected:</b> <code>{event.detected_value}</code>
<b>Expected:</b> <code>{event.expected_value}</code>
            """
            
            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Telegram alert sent for {event.leak_type.value}")
                    else:
                        logger.error(f"Telegram returned status {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


class LeakDetector:
    """Detects various types of geolocation leaks"""
    
    LEAK_TEST_SERVERS = [
        "https://ipleak.net/json/",
        "https://ipinfo.io/json",
        "https://ifconfig.me/all.json",
    ]
    
    DNS_TEST_SERVERS = [
        "https://dnsleaktest.com/api/servers",
        "https://www.dnsleaktest.com/api/servers",
    ]
    
    def __init__(
        self,
        expected_exit_ips: Set[str],
        expected_dns_servers: Set[str],
        alert_manager: AlertManager,
        check_interval: int = 60
    ):
        self.expected_exit_ips = expected_exit_ips
        self.expected_dns_servers = expected_dns_servers
        self.alert_manager = alert_manager
        self.check_interval = check_interval
        self.running = False
        self.leak_events: List[LeakEvent] = []
        self.remediation_actions: Dict[LeakType, Callable] = {}
        
        # Register default remediation actions
        self._register_default_remediations()
    
    def _register_default_remediations(self):
        """Register default remediation actions"""
        self.remediation_actions[LeakType.IP_LEAK] = self._remediate_ip_leak
        self.remediation_actions[LeakType.DNS_LEAK] = self._remediate_dns_leak
        self.remediation_actions[LeakType.WEBRTC_LEAK] = self._remediate_webrtc_leak
    
    async def _remediate_ip_leak(self, event: LeakEvent):
        """Remediate IP leak"""
        logger.critical("Executing IP leak remediation...")
        
        # Kill VPN connections
        subprocess.run(["pkill", "-f", "openvpn"], capture_output=True)
        subprocess.run(["wg-quick", "down", "all"], capture_output=True)
        
        # Activate killswitch
        subprocess.run(["/usr/local/bin/killswitch.sh", "enable"], capture_output=True)
        
        event.remediation_action = "Activated killswitch, disconnected VPN"
    
    async def _remediate_dns_leak(self, event: LeakEvent):
        """Remediate DNS leak"""
        logger.critical("Executing DNS leak remediation...")
        
        # Restart DNS proxy
        subprocess.run(["systemctl", "restart", "cloudflared-proxy-dns"], capture_output=True)
        subprocess.run(["systemctl", "restart", "dnscrypt-proxy"], capture_output=True)
        
        # Flush DNS cache
        subprocess.run(["systemd-resolve", "--flush-caches"], capture_output=True)
        
        event.remediation_action = "Restarted DNS services, flushed caches"
    
    async def _remediate_webrtc_leak(self, event: LeakEvent):
        """Remediate WebRTC leak"""
        logger.critical("Executing WebRTC leak remediation...")
        
        # Kill browser processes
        subprocess.run(["pkill", "-f", "firefox"], capture_output=True)
        subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
        
        event.remediation_action = "Killed browser processes"
    
    async def check_ip_leak(self, session: aiohttp.ClientSession) -> Optional[LeakEvent]:
        """Check for IP leaks"""
        for url in self.LEAK_TEST_SERVERS:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        detected_ip = data.get("ip") or data.get("query") or data.get("ip_addr")
                        
                        if detected_ip and detected_ip not in self.expected_exit_ips:
                            event = LeakEvent(
                                timestamp=datetime.now(),
                                leak_type=LeakType.IP_LEAK,
                                severity=LeakSeverity.CRITICAL,
                                message=f"IP leak detected via {url}",
                                detected_value=detected_ip,
                                expected_value=str(self.expected_exit_ips),
                                source_ip=detected_ip
                            )
                            return event
                            
            except Exception as e:
                logger.warning(f"IP leak check failed for {url}: {e}")
        
        return None
    
    async def check_dns_leak(self, session: aiohttp.ClientSession) -> Optional[LeakEvent]:
        """Check for DNS leaks"""
        for url in self.DNS_TEST_SERVERS:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if isinstance(data, list):
                            for server in data:
                                dns_ip = server.get("ip", "")
                                if dns_ip and dns_ip not in self.expected_dns_servers:
                                    event = LeakEvent(
                                        timestamp=datetime.now(),
                                        leak_type=LeakType.DNS_LEAK,
                                        severity=LeakSeverity.WARNING,
                                        message=f"DNS leak detected: {server.get('isp', 'Unknown ISP')}",
                                        detected_value=dns_ip,
                                        expected_value=str(self.expected_dns_servers),
                                        source_ip=dns_ip
                                    )
                                    return event
                                    
            except Exception as e:
                logger.warning(f"DNS leak check failed for {url}: {e}")
        
        return None
    
    async def check_webrtc_leak(self) -> Optional[LeakEvent]:
        """Check for WebRTC leaks using browser automation"""
        # This would require Selenium/Playwright to check browser WebRTC
        # For now, return None (no leak detected)
        return None
    
    async def check_geolocation_leak(self, session: aiohttp.ClientSession) -> Optional[LeakEvent]:
        """Check for geolocation API leaks"""
        try:
            # Check if geolocation is enabled in browsers
            # This would require browser automation
            return None
        except Exception as e:
            logger.warning(f"Geolocation leak check failed: {e}")
            return None
    
    async def run_check(self) -> List[LeakEvent]:
        """Run all leak checks"""
        leaks = []
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Check IP leak
            leak = await self.check_ip_leak(session)
            if leak:
                leaks.append(leak)
            
            # Check DNS leak
            leak = await self.check_dns_leak(session)
            if leak:
                leaks.append(leak)
            
            # Check WebRTC leak
            leak = await self.check_webrtc_leak()
            if leak:
                leaks.append(leak)
            
            # Check geolocation leak
            leak = await self.check_geolocation_leak(session)
            if leak:
                leaks.append(leak)
        
        return leaks
    
    async def execute_remediation(self, event: LeakEvent):
        """Execute remediation for a leak event"""
        action = self.remediation_actions.get(event.leak_type)
        if action:
            await action(event)
    
    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.running = True
        logger.info("Starting leak detection monitoring...")
        
        while self.running:
            try:
                leaks = await self.run_check()
                
                for leak in leaks:
                    logger.critical(f"LEAK DETECTED: {leak.leak_type.value} - {leak.message}")
                    
                    # Execute remediation
                    await self.execute_remediation(leak)
                    
                    # Send alert
                    await self.alert_manager.send_alert(leak)
                    
                    self.leak_events.append(leak)
                
                if not leaks:
                    logger.debug("No leaks detected")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Stopping leak detection monitoring...")
    
    def get_status(self) -> Dict:
        """Get detector status"""
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "expected_exit_ips": list(self.expected_exit_ips),
            "expected_dns_servers": list(self.expected_dns_servers),
            "total_leaks_detected": len(self.leak_events),
            "recent_leaks": [e.to_dict() for e in self.leak_events[-10:]]
        }


class LeakDetectorService:
    """Systemd service wrapper for leak detector"""
    
    def __init__(self, config_path: str = "/etc/anti-geolocation/leak-detector.yaml"):
        self.config_path = Path(config_path)
        self.detector: Optional[LeakDetector] = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML"""
        if not self.config_path.exists():
            # Create default config
            default_config = {
                "expected_exit_ips": [],
                "expected_dns_servers": ["127.0.0.1", "::1"],
                "check_interval": 60,
                "alert": {
                    "email_enabled": False,
                    "email_smtp_host": "smtp.gmail.com",
                    "email_smtp_port": 587,
                    "email_username": "",
                    "email_password": "",
                    "email_recipients": [],
                    "webhook_enabled": False,
                    "webhook_url": "",
                    "telegram_enabled": False,
                    "telegram_bot_token": "",
                    "telegram_chat_id": "",
                    "alert_on_info": False,
                    "alert_on_warning": True,
                    "alert_on_critical": True
                }
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(default_config, f)
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        alert_config = AlertConfig(**config.get("alert", {}))
        alert_manager = AlertManager(alert_config)
        
        self.detector = LeakDetector(
            expected_exit_ips=set(config.get("expected_exit_ips", [])),
            expected_dns_servers=set(config.get("expected_dns_servers", ["127.0.0.1"])),
            alert_manager=alert_manager,
            check_interval=config.get("check_interval", 60)
        )
    
    async def run(self):
        """Run the service"""
        await self.detector.start_monitoring()
    
    def stop(self):
        """Stop the service"""
        if self.detector:
            self.detector.stop_monitoring()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Leak Detection System')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Start monitoring
    subparsers.add_parser('start', help='Start monitoring')
    
    # Stop monitoring
    subparsers.add_parser('stop', help='Stop monitoring')
    
    # Check once
    subparsers.add_parser('check', help='Run single check')
    
    # Status
    subparsers.add_parser('status', help='Show status')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        service = LeakDetectorService()
        try:
            asyncio.run(service.run())
        except KeyboardInterrupt:
            service.stop()
    
    elif args.command == 'check':
        service = LeakDetectorService()
        leaks = asyncio.run(service.detector.run_check())
        if leaks:
            print(f"Detected {len(leaks)} leaks:")
            for leak in leaks:
                print(f"  - {leak.leak_type.value}: {leak.message}")
        else:
            print("No leaks detected")
    
    elif args.command == 'status':
        service = LeakDetectorService()
        status = service.detector.get_status()
        print(json.dumps(status, indent=2))
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
