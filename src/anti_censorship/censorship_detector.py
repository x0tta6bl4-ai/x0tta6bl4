"""
Censorship Detection Module
===========================

Detects various types of internet censorship and network interference:
- DNS manipulation
- TCP/IP blocking
- TLS interception
- Deep Packet Inspection
- Throttling
"""

import asyncio
import logging
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import dns.resolver

logger = logging.getLogger(__name__)


class BlockingType(Enum):
    """Types of censorship/blocking detected."""
    NONE = "none"
    DNS_MANIPULATION = "dns_manipulation"
    TCP_RESET = "tcp_reset"
    TCP_TIMEOUT = "tcp_timeout"
    TLS_INTERCEPTION = "tls_interception"
    DPI_BLOCKING = "dpi_blocking"
    THROTTLING = "throttling"
    HTTP_BLOCKING = "http_blocking"
    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    """Result of a censorship detection test."""
    blocking_type: BlockingType
    is_blocked: bool
    confidence: float  # 0.0 to 1.0
    target: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "blocking_type": self.blocking_type.value,
            "is_blocked": self.is_blocked,
            "confidence": self.confidence,
            "target": self.target,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class ProbeConfig:
    """Configuration for censorship probes."""
    timeout: float = 10.0
    dns_timeout: float = 5.0
    tcp_timeout: float = 10.0
    tls_timeout: float = 10.0
    http_timeout: float = 15.0
    retries: int = 3
    expected_dns_results: Dict[str, List[str]] = field(default_factory=dict)
    control_servers: List[str] = field(default_factory=lambda: [
        "8.8.8.8",  # Google DNS
        "1.1.1.1",  # Cloudflare DNS
    ])


class CensorshipDetector:
    """
    Comprehensive censorship detection system.
    
    Performs multiple tests to detect various censorship techniques:
    - DNS tampering detection
    - TCP/IP blocking detection
    - TLS interception detection
    - DPI detection
    - Throttling detection
    """
    
    # Known blocked IP ranges (for comparison)
    KNOWN_BLOCKED_IPS = set()
    
    # Expected responses for control requests
    CONTROL_RESPONSES = {
        "http://www.google.com": "<!doctype html>",
        "http://www.cloudflare.com": "cloudflare",
    }
    
    def __init__(self, config: Optional[ProbeConfig] = None):
        """
        Initialize censorship detector.
        
        Args:
            config: Probe configuration
        """
        self.config = config or ProbeConfig()
        self._results: List[DetectionResult] = []
        self._baseline: Dict[str, Any] = {}
    
    def detect_dns_manipulation(
        self,
        domain: str,
        expected_ips: Optional[List[str]] = None,
    ) -> DetectionResult:
        """
        Detect DNS manipulation for a domain.
        
        Compares DNS responses from multiple resolvers.
        
        Args:
            domain: Domain to test
            expected_ips: Expected IP addresses
            
        Returns:
            DetectionResult
        """
        start_time = time.time()
        
        try:
            # Query local DNS
            local_resolver = dns.resolver.get_default_resolver()
            local_answer = local_resolver.resolve(domain, 'A')
            local_ips = [str(rdata) for rdata in local_answer]
            
            # Query control DNS servers
            control_ips = set()
            for server in self.config.control_servers:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = [server]
                    resolver.timeout = self.config.dns_timeout
                    
                    answer = resolver.resolve(domain, 'A')
                    for rdata in answer:
                        control_ips.add(str(rdata))
                except Exception as e:
                    logger.debug(f"Control DNS query failed for {server}: {e}")
            
            # Compare results
            local_set = set(local_ips)
            control_set = control_ips
            
            # Check for manipulation
            is_manipulated = False
            confidence = 0.0
            
            if expected_ips:
                expected_set = set(expected_ips)
                if local_set != expected_set and local_set != control_set:
                    is_manipulated = True
                    confidence = 0.9
            elif control_set and local_set != control_set:
                is_manipulated = True
                confidence = 0.7
            
            latency_ms = (time.time() - start_time) * 1000
            
            return DetectionResult(
                blocking_type=BlockingType.DNS_MANIPULATION if is_manipulated else BlockingType.NONE,
                is_blocked=is_manipulated,
                confidence=confidence,
                target=domain,
                details={
                    "local_ips": local_ips,
                    "control_ips": list(control_ips),
                    "expected_ips": expected_ips,
                },
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            return DetectionResult(
                blocking_type=BlockingType.UNKNOWN,
                is_blocked=False,
                confidence=0.0,
                target=domain,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def detect_tcp_blocking(
        self,
        host: str,
        port: int,
    ) -> DetectionResult:
        """
        Detect TCP-level blocking.
        
        Tests for connection resets, timeouts, and filtering.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            DetectionResult
        """
        start_time = time.time()
        
        results = []
        for attempt in range(self.config.retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config.tcp_timeout)
                
                start_connect = time.time()
                sock.connect((host, port))
                connect_time = time.time() - start_connect
                
                sock.close()
                
                results.append({
                    "success": True,
                    "connect_time": connect_time,
                })
                
            except socket.timeout:
                results.append({
                    "success": False,
                    "error": "timeout",
                })
            except ConnectionResetError:
                results.append({
                    "success": False,
                    "error": "reset",
                })
            except ConnectionRefusedError:
                results.append({
                    "success": False,
                    "error": "refused",
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                })
            
            if attempt < self.config.retries - 1:
                time.sleep(1)
        
        # Analyze results
        successes = sum(1 for r in results if r.get("success"))
        resets = sum(1 for r in results if r.get("error") == "reset")
        timeouts = sum(1 for r in results if r.get("error") == "timeout")
        
        blocking_type = BlockingType.NONE
        is_blocked = False
        confidence = 0.0
        
        if resets >= self.config.retries // 2 + 1:
            blocking_type = BlockingType.TCP_RESET
            is_blocked = True
            confidence = 0.9
        elif timeouts >= self.config.retries:
            blocking_type = BlockingType.TCP_TIMEOUT
            is_blocked = True
            confidence = 0.7
        
        latency_ms = (time.time() - start_time) * 1000
        
        return DetectionResult(
            blocking_type=blocking_type,
            is_blocked=is_blocked,
            confidence=confidence,
            target=f"{host}:{port}",
            details={
                "attempts": results,
                "success_rate": successes / self.config.retries,
            },
            latency_ms=latency_ms,
        )
    
    def detect_tls_interception(
        self,
        host: str,
        port: int = 443,
    ) -> DetectionResult:
        """
        Detect TLS/SSL interception (MITM).
        
        Verifies certificate chain and compares with known certificates.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            DetectionResult
        """
        start_time = time.time()
        
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=self.config.tls_timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert(binary_form=True)
                    cert_dict = ssock.getpeercert()
                    
                    # Check certificate issuer
                    issuer = dict(x[0] for x in cert_dict.get('issuer', []))
                    subject = dict(x[0] for x in cert_dict.get('subject', []))
                    
                    # Check for suspicious issuers
                    common_issuers = [
                        "Let's Encrypt", "DigiCert", "GlobalSign",
                        "Cloudflare", "Amazon", "Google",
                    ]
                    
                    is_intercepted = False
                    confidence = 0.0
                    
                    issuer_org = issuer.get('organizationName', '')
                    
                    if issuer_org and not any(
                        ci.lower() in issuer_org.lower() for ci in common_issuers
                    ):
                        # Unknown issuer - potential interception
                        is_intercepted = True
                        confidence = 0.6
                    
                    # Check if subject matches host
                    common_name = subject.get('commonName', '')
                    if common_name and host not in common_name and not common_name.endswith('*'):
                        is_intercepted = True
                        confidence = max(confidence, 0.8)
                    
                    latency_ms = (time.time() - start_time) * 1000
                    
                    return DetectionResult(
                        blocking_type=BlockingType.TLS_INTERCEPTION if is_intercepted else BlockingType.NONE,
                        is_blocked=is_intercepted,
                        confidence=confidence,
                        target=f"{host}:{port}",
                        details={
                            "issuer": issuer,
                            "subject": subject,
                            "common_name": common_name,
                        },
                        latency_ms=latency_ms,
                    )
                    
        except ssl.SSLCertVerificationError as e:
            return DetectionResult(
                blocking_type=BlockingType.TLS_INTERCEPTION,
                is_blocked=True,
                confidence=0.9,
                target=f"{host}:{port}",
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return DetectionResult(
                blocking_type=BlockingType.UNKNOWN,
                is_blocked=False,
                confidence=0.0,
                target=f"{host}:{port}",
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def detect_http_blocking(
        self,
        url: str,
        expected_content: Optional[str] = None,
    ) -> DetectionResult:
        """
        Detect HTTP-level blocking.
        
        Checks for HTTP status codes, redirects, and content manipulation.
        
        Args:
            url: Target URL
            expected_content: Expected content substring
            
        Returns:
            DetectionResult
        """
        import requests
        
        start_time = time.time()
        
        try:
            response = requests.get(
                url,
                timeout=self.config.http_timeout,
                allow_redirects=False,
            )
            
            is_blocked = False
            confidence = 0.0
            details = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
            }
            
            # Check for blocking indicators
            if response.status_code in [403, 451]:
                is_blocked = True
                confidence = 0.9
            elif response.status_code >= 400:
                is_blocked = True
                confidence = 0.5
            
            # Check for redirect to block page
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                if any(block_word in location.lower() for block_word in 
                       ['block', 'deny', 'forbidden', 'restricted']):
                    is_blocked = True
                    confidence = 0.8
                details['redirect_location'] = location
            
            # Check content
            if expected_content and expected_content not in response.text:
                is_blocked = True
                confidence = max(confidence, 0.6)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return DetectionResult(
                blocking_type=BlockingType.HTTP_BLOCKING if is_blocked else BlockingType.NONE,
                is_blocked=is_blocked,
                confidence=confidence,
                target=url,
                details=details,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            return DetectionResult(
                blocking_type=BlockingType.UNKNOWN,
                is_blocked=False,
                confidence=0.0,
                target=url,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def detect_throttling(
        self,
        host: str,
        port: int = 443,
        duration: float = 5.0,
    ) -> DetectionResult:
        """
        Detect bandwidth throttling.
        
        Measures transfer speeds over time to detect throttling.
        
        Args:
            host: Target host
            port: Target port
            duration: Test duration in seconds
            
        Returns:
            DetectionResult
        """
        start_time = time.time()
        
        try:
            # Measure multiple transfers
            speeds = []
            chunk_size = 65536
            total_bytes = 0
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.tcp_timeout)
            sock.connect((host, port))
            
            test_start = time.time()
            
            while time.time() - test_start < duration:
                chunk_start = time.time()
                
                try:
                    # Send data and measure speed
                    data = b'\x00' * chunk_size
                    sock.sendall(data)
                    total_bytes += chunk_size
                    
                    chunk_time = time.time() - chunk_start
                    speed = chunk_size / chunk_time if chunk_time > 0 else 0
                    speeds.append(speed)
                    
                except Exception:
                    break
            
            sock.close()
            
            # Analyze speed pattern
            if len(speeds) < 3:
                return DetectionResult(
                    blocking_type=BlockingType.UNKNOWN,
                    is_blocked=False,
                    confidence=0.0,
                    target=f"{host}:{port}",
                    error="Insufficient data",
                    latency_ms=(time.time() - start_time) * 1000,
                )
            
            # Check for speed degradation
            first_half = speeds[:len(speeds)//2]
            second_half = speeds[len(speeds)//2:]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            is_throttled = False
            confidence = 0.0
            
            if avg_second < avg_first * 0.5:  # 50% speed drop
                is_throttled = True
                confidence = 0.8
            
            latency_ms = (time.time() - start_time) * 1000
            
            return DetectionResult(
                blocking_type=BlockingType.THROTTLING if is_throttled else BlockingType.NONE,
                is_blocked=is_throttled,
                confidence=confidence,
                target=f"{host}:{port}",
                details={
                    "avg_speed_first_half": avg_first,
                    "avg_speed_second_half": avg_second,
                    "speed_ratio": avg_second / avg_first if avg_first > 0 else 0,
                    "total_bytes": total_bytes,
                },
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            return DetectionResult(
                blocking_type=BlockingType.UNKNOWN,
                is_blocked=False,
                confidence=0.0,
                target=f"{host}:{port}",
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def run_full_scan(
        self,
        targets: List[str],
        include_throttling: bool = False,
    ) -> List[DetectionResult]:
        """
        Run comprehensive censorship detection scan.
        
        Args:
            targets: List of targets to test
            include_throttling: Whether to include throttling tests
            
        Returns:
            List of DetectionResult for all tests
        """
        results = []
        
        for target in targets:
            # DNS test
            results.append(self.detect_dns_manipulation(target))
            
            # TCP test
            results.append(self.detect_tcp_blocking(target, 443))
            
            # TLS test
            results.append(self.detect_tls_interception(target))
            
            # HTTP test
            results.append(self.detect_http_blocking(f"https://{target}"))
            
            # Throttling test (optional)
            if include_throttling:
                results.append(self.detect_throttling(target))
        
        self._results.extend(results)
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all detection results."""
        if not self._results:
            return {"total_tests": 0}
        
        blocked = [r for r in self._results if r.is_blocked]
        
        by_type: Dict[str, int] = {}
        for result in self._results:
            t = result.blocking_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        return {
            "total_tests": len(self._results),
            "blocked_count": len(blocked),
            "block_rate": len(blocked) / len(self._results),
            "by_type": by_type,
            "last_scan": max(r.timestamp for r in self._results).isoformat(),
        }
    
    def clear_results(self) -> None:
        """Clear all stored results."""
        self._results.clear()


__all__ = [
    "BlockingType",
    "DetectionResult",
    "ProbeConfig",
    "CensorshipDetector",
]
