"""
Core Leak Detection Engine
Multi-vector detection for IP, DNS, WebRTC, and other geolocation leaks
"""
import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Callable, Any
from urllib.parse import urlparse

import aiohttp
import structlog

from config.settings import settings


logger = structlog.get_logger()


class LeakSeverity(Enum):
    """Leak severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LeakType(Enum):
    """Types of geolocation leaks"""
    IP_LEAK = "ip_leak"
    DNS_LEAK = "dns_leak"
    WEBRTC_LEAK = "webrtc_leak"
    GEOLOCATION_LEAK = "geolocation_leak"
    FINGERPRINT_LEAK = "fingerprint_leak"
    TIMEZONE_LEAK = "timezone_leak"
    WEBGL_LEAK = "webgl_leak"
    FONT_LEAK = "font_leak"
    CANVAS_LEAK = "canvas_leak"
    IPV6_LEAK = "ipv6_leak"


@dataclass
class LeakEvent:
    """Represents a detected leak event"""
    timestamp: datetime
    leak_type: LeakType
    severity: LeakSeverity
    message: str
    detected_value: str
    expected_value: Optional[str]
    source_ip: Optional[str]
    detected_country: Optional[str] = None
    detected_city: Optional[str] = None
    detected_isp: Optional[str] = None
    user_agent: Optional[str] = None
    remediation_action: Optional[str] = None
    resolved: bool = False
    check_source: Optional[str] = None
    raw_data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "leak_type": self.leak_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "detected_value": self.detected_value,
            "expected_value": self.expected_value,
            "source_ip": self.source_ip,
            "detected_country": self.detected_country,
            "detected_city": self.detected_city,
            "detected_isp": self.detected_isp,
            "user_agent": self.user_agent,
            "remediation_action": self.remediation_action,
            "resolved": self.resolved,
            "check_source": self.check_source,
            "raw_data": self.raw_data,
        }


@dataclass
class DetectionResult:
    """Result of a detection check"""
    check_type: str
    status: str  # "ok", "leak_detected", "error"
    response_time_ms: float
    leaks: List[LeakEvent] = field(default_factory=list)
    error_message: Optional[str] = None


class IPLeakDetector:
    """Detector for IP-based geolocation leaks"""
    
    LEAK_TEST_SERVERS = [
        ("https://ipleak.net/json/", "ipleak"),
        ("https://ipinfo.io/json", "ipinfo"),
        ("https://ifconfig.me/all.json", "ifconfig"),
        ("https://api.ipify.org?format=json", "ipify"),
        ("https://checkip.amazonaws.com/", "aws"),
    ]
    
    def __init__(self, expected_exit_ips: Set[str]):
        self.expected_exit_ips = expected_exit_ips
        self.logger = structlog.get_logger().bind(detector="ip_leak")
    
    async def check(self, session: aiohttp.ClientSession) -> DetectionResult:
        """Check for IP leaks across multiple servers"""
        start_time = asyncio.get_event_loop().time()
        leaks = []
        
        for url, source in self.LEAK_TEST_SERVERS:
            try:
                leak = await self._check_single_server(session, url, source)
                if leak:
                    leaks.append(leak)
            except Exception as e:
                self.logger.warning(f"IP check failed for {url}", error=str(e))
        
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return DetectionResult(
            check_type="ip_leak",
            status="leak_detected" if leaks else "ok",
            response_time_ms=response_time,
            leaks=leaks
        )
    
    async def _check_single_server(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        source: str
    ) -> Optional[LeakEvent]:
        """Check a single IP detection server"""
        try:
            async with session.get(
                url, 
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    data = json.loads(text) if text.strip() else {"ip": text.strip()}
                    
                    detected_ip = (
                        data.get("ip") or 
                        data.get("query") or 
                        data.get("ip_addr") or 
                        text.strip()
                    )
                    
                    if detected_ip and detected_ip not in self.expected_exit_ips:
                        return LeakEvent(
                            timestamp=datetime.utcnow(),
                            leak_type=LeakType.IP_LEAK,
                            severity=LeakSeverity.CRITICAL,
                            message=f"IP leak detected via {source}",
                            detected_value=detected_ip,
                            expected_value=str(self.expected_exit_ips),
                            source_ip=detected_ip,
                            detected_country=data.get("country"),
                            detected_city=data.get("city"),
                            detected_isp=data.get("isp") or data.get("org"),
                            check_source=source,
                            raw_data=data
                        )
                        
        except Exception as e:
            self.logger.warning(f"Failed to check {source}", error=str(e))
        
        return None


class DNSLeakDetector:
    """Detector for DNS-based geolocation leaks"""
    
    DNS_TEST_SERVERS = [
        ("https://dnsleaktest.com/api/servers", "dnsleaktest"),
        ("https://www.dnsleaktest.com/api/servers", "dnsleaktest2"),
    ]
    
    def __init__(self, expected_dns_servers: Set[str]):
        self.expected_dns_servers = expected_dns_servers
        self.logger = structlog.get_logger().bind(detector="dns_leak")
    
    async def check(self, session: aiohttp.ClientSession) -> DetectionResult:
        """Check for DNS leaks"""
        start_time = asyncio.get_event_loop().time()
        leaks = []
        
        for url, source in self.DNS_TEST_SERVERS:
            try:
                server_leaks = await self._check_single_server(session, url, source)
                leaks.extend(server_leaks)
            except Exception as e:
                self.logger.warning(f"DNS check failed for {url}", error=str(e))
        
        # Also check via DNS resolution test
        try:
            dns_resolution_leak = await self._check_dns_resolution()
            if dns_resolution_leak:
                leaks.append(dns_resolution_leak)
        except Exception as e:
            self.logger.warning("DNS resolution check failed", error=str(e))
        
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return DetectionResult(
            check_type="dns_leak",
            status="leak_detected" if leaks else "ok",
            response_time_ms=response_time,
            leaks=leaks
        )
    
    async def _check_single_server(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        source: str
    ) -> List[LeakEvent]:
        """Check a single DNS leak detection server"""
        leaks = []
        
        async with session.get(
            url, 
            timeout=aiohttp.ClientTimeout(total=10),
            ssl=False
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                
                if isinstance(data, list):
                    for server in data:
                        dns_ip = server.get("ip", "")
                        if dns_ip and dns_ip not in self.expected_dns_servers:
                            leaks.append(LeakEvent(
                                timestamp=datetime.utcnow(),
                                leak_type=LeakType.DNS_LEAK,
                                severity=LeakSeverity.WARNING,
                                message=f"DNS leak detected: {server.get('isp', 'Unknown ISP')}",
                                detected_value=dns_ip,
                                expected_value=str(self.expected_dns_servers),
                                source_ip=dns_ip,
                                detected_country=server.get("country"),
                                detected_city=server.get("city"),
                                check_source=source,
                                raw_data=server
                            ))
        
        return leaks
    
    async def _check_dns_resolution(self) -> Optional[LeakEvent]:
        """Check DNS resolution for leaks using system commands"""
        try:
            # Try to get current DNS servers
            result = subprocess.run(
                ["systemd-resolve", "--status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse DNS servers from output
            dns_servers = []
            for line in result.stdout.split('\n'):
                if 'DNS Servers:' in line or 'Current DNS Server:' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        if ip and ip not in self.expected_dns_servers:
                            dns_servers.append(ip)
            
            if dns_servers:
                return LeakEvent(
                    timestamp=datetime.utcnow(),
                    leak_type=LeakType.DNS_LEAK,
                    severity=LeakSeverity.WARNING,
                    message=f"System DNS leak detected: {', '.join(dns_servers)}",
                    detected_value=', '.join(dns_servers),
                    expected_value=str(self.expected_dns_servers),
                    check_source="system_dns"
                )
                
        except Exception as e:
            self.logger.debug("DNS resolution check skipped", error=str(e))
        
        return None


class WebRTCLeakDetector:
    """Detector for WebRTC-based IP leaks"""
    
    def __init__(self):
        self.logger = structlog.get_logger().bind(detector="webrtc_leak")
    
    async def check(self, session: aiohttp.ClientSession) -> DetectionResult:
        """Check for WebRTC leaks using browser automation"""
        start_time = asyncio.get_event_loop().time()
        leaks = []
        
        # Check if browsers are running with WebRTC enabled
        try:
            browser_leaks = await self._check_browser_webrtc()
            leaks.extend(browser_leaks)
        except Exception as e:
            self.logger.warning("Browser WebRTC check failed", error=str(e))
        
        # Check system WebRTC configuration
        try:
            system_leak = await self._check_system_webrtc()
            if system_leak:
                leaks.append(system_leak)
        except Exception as e:
            self.logger.debug("System WebRTC check skipped", error=str(e))
        
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return DetectionResult(
            check_type="webrtc_leak",
            status="leak_detected" if leaks else "ok",
            response_time_ms=response_time,
            leaks=leaks
        )
    
    async def _check_browser_webrtc(self) -> List[LeakEvent]:
        """Check browser WebRTC configuration"""
        leaks = []
        
        # Check Firefox configuration
        firefox_config_paths = [
            ".mozilla/firefox",
            ".var/app/org.mozilla.firefox/.mozilla/firefox"
        ]
        
        for config_path in firefox_config_paths:
            prefs_file = f"{config_path}/**/prefs.js"
            try:
                result = subprocess.run(
                    ["find", config_path, "-name", "prefs.js"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.stdout:
                    # Check if WebRTC is disabled
                    grep_result = subprocess.run(
                        ["grep", "media.peerconnection.enabled", result.stdout.strip().split('\n')[0]],
                        capture_output=True,
                        text=True
                    )
                    
                    if "false" not in grep_result.stdout:
                        leaks.append(LeakEvent(
                            timestamp=datetime.utcnow(),
                            leak_type=LeakType.WEBRTC_LEAK,
                            severity=LeakSeverity.CRITICAL,
                            message="Firefox WebRTC is enabled - potential IP leak risk",
                            detected_value="WebRTC enabled",
                            expected_value="WebRTC disabled",
                            check_source="firefox_config"
                        ))
                        
            except Exception as e:
                self.logger.debug(f"Firefox config check failed for {config_path}", error=str(e))
        
        return leaks
    
    async def _check_system_webrtc(self) -> Optional[LeakEvent]:
        """Check system-level WebRTC settings"""
        # Check for WebRTC processes
        try:
            result = subprocess.run(
                ["pgrep", "-f", "webrtc"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return LeakEvent(
                    timestamp=datetime.utcnow(),
                    leak_type=LeakType.WEBRTC_LEAK,
                    severity=LeakSeverity.WARNING,
                    message="WebRTC processes detected on system",
                    detected_value="WebRTC active",
                    expected_value="WebRTC disabled",
                    check_source="system_processes"
                )
                
        except Exception:
            pass
        
        return None


class IPv6LeakDetector:
    """Detector for IPv6 leaks"""
    
    def __init__(self):
        self.logger = structlog.get_logger().bind(detector="ipv6_leak")
    
    async def check(self, session: aiohttp.ClientSession) -> DetectionResult:
        """Check for IPv6 leaks"""
        start_time = asyncio.get_event_loop().time()
        leaks = []
        
        # Check if IPv6 is enabled
        try:
            with open('/proc/sys/net/ipv6/conf/all/disable_ipv6', 'r') as f:
                ipv6_disabled = f.read().strip() == '1'
            
            if not ipv6_disabled:
                leaks.append(LeakEvent(
                    timestamp=datetime.utcnow(),
                    leak_type=LeakType.IPV6_LEAK,
                    severity=LeakSeverity.WARNING,
                    message="IPv6 is enabled - potential dual-stack leak risk",
                    detected_value="IPv6 enabled",
                    expected_value="IPv6 disabled",
                    check_source="kernel_config"
                ))
        except Exception as e:
            self.logger.debug("IPv6 kernel check failed", error=str(e))
        
        # Check for IPv6 addresses on interfaces
        try:
            result = subprocess.run(
                ["ip", "-6", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Look for global IPv6 addresses (not link-local)
            for line in result.stdout.split('\n'):
                if 'inet6' in line and 'scope global' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ipv6_addr = parts[1].split('/')[0]
                        if not ipv6_addr.startswith('fe80'):  # Not link-local
                            leaks.append(LeakEvent(
                                timestamp=datetime.utcnow(),
                                leak_type=LeakType.IPV6_LEAK,
                                severity=LeakSeverity.CRITICAL,
                                message=f"Global IPv6 address detected: {ipv6_addr}",
                                detected_value=ipv6_addr,
                                expected_value="No global IPv6",
                                check_source="interface_config"
                            ))
                            
        except Exception as e:
            self.logger.debug("IPv6 interface check failed", error=str(e))
        
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return DetectionResult(
            check_type="ipv6_leak",
            status="leak_detected" if leaks else "ok",
            response_time_ms=response_time,
            leaks=leaks
        )


class LeakDetectionEngine:
    """Main leak detection engine coordinating all detectors"""
    
    def __init__(
        self,
        expected_exit_ips: Optional[Set[str]] = None,
        expected_dns_servers: Optional[Set[str]] = None,
        check_interval: int = 30
    ):
        self.expected_exit_ips = expected_exit_ips or settings.detection.expected_exit_ips
        self.expected_dns_servers = expected_dns_servers or settings.detection.expected_dns_servers
        self.check_interval = check_interval
        self.running = False
        
        # Initialize detectors
        self.ip_detector = IPLeakDetector(self.expected_exit_ips)
        self.dns_detector = DNSLeakDetector(self.expected_dns_servers)
        self.webrtc_detector = WebRTCLeakDetector()
        self.ipv6_detector = IPv6LeakDetector()
        
        # Event callbacks
        self.on_leak_detected: List[Callable[[LeakEvent], Any]] = []
        self.on_check_complete: List[Callable[[DetectionResult], Any]] = []
        
        self.logger = structlog.get_logger().bind(component="leak_detection_engine")
    
    async def run_full_check(self) -> List[DetectionResult]:
        """Run all leak detection checks"""
        results = []
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Run all checks concurrently
            tasks = [
                self.ip_detector.check(session),
                self.dns_detector.check(session),
                self.webrtc_detector.check(session),
                self.ipv6_detector.check(session),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            results = [
                r for r in results 
                if isinstance(r, DetectionResult)
            ]
            
            # Notify callbacks
            for result in results:
                for callback in self.on_check_complete:
                    try:
                        await callback(result) if asyncio.iscoroutinefunction(callback) else callback(result)
                    except Exception as e:
                        self.logger.error("Check complete callback failed", error=str(e))
                
                # Notify leak callbacks
                for leak in result.leaks:
                    for callback in self.on_leak_detected:
                        try:
                            await callback(leak) if asyncio.iscoroutinefunction(callback) else callback(leak)
                        except Exception as e:
                            self.logger.error("Leak detected callback failed", error=str(e))
        
        return results
    
    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.running = True
        self.logger.info("Starting leak detection monitoring")
        
        while self.running:
            try:
                results = await self.run_full_check()
                
                total_leaks = sum(len(r.leaks) for r in results)
                if total_leaks > 0:
                    self.logger.warning(
                        f"Detected {total_leaks} leaks in this cycle",
                        results=[{"type": r.check_type, "status": r.status} for r in results]
                    )
                else:
                    self.logger.debug("No leaks detected in this cycle")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error("Monitoring error", error=str(e))
                await asyncio.sleep(5)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        self.logger.info("Stopping leak detection monitoring")
    
    def get_status(self) -> Dict:
        """Get detector status"""
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "expected_exit_ips": list(self.expected_exit_ips),
            "expected_dns_servers": list(self.expected_dns_servers),
            "detectors": [
                "ip_leak",
                "dns_leak",
                "webrtc_leak",
                "ipv6_leak"
            ]
        }
