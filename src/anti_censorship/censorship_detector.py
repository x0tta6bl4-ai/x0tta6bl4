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

import logging
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import dns.resolver

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)


_SERVICE_AGENT = "anti-censorship-censorship-detector"
_SERVICE_LAYER = "anti_censorship_censorship_detector_local_evidence"
CENSORSHIP_DETECTOR_CLAIM_BOUNDARY = (
    "Local censorship-detector probe evidence only. It records local probe "
    "operation, result buckets, duration, target hashes, detail-key shapes, "
    "probe configuration buckets, and service identity presence; it does not "
    "expose raw domains, URLs, IP addresses, headers, certificate subjects, "
    "probe payloads, control resolvers, error strings, or prove real-world "
    "censorship, DPI bypass, remote reachability, packet delivery, anonymity, "
    "provider health, client installation, or production customer traffic use."
)


def _count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value == 1:
        return "single"
    if value <= 3:
        return "few"
    if value <= 10:
        return "small"
    if value <= 50:
        return "medium"
    return "large"


def _latency_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "zero"
    if value <= 10:
        return "tiny"
    if value <= 100:
        return "small"
    if value <= 1000:
        return "medium"
    if value <= 10000:
        return "large"
    return "very_large"


def _confidence_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "zero"
    if value < 0.25:
        return "low"
    if value < 0.75:
        return "medium"
    return "high"


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:16]


def _target_metadata(target: str) -> Dict[str, Any]:
    if "://" in target:
        kind = "url"
    elif ":" in target:
        kind = "host_port"
    else:
        kind = "domain_or_host"
    return {
        "target_kind": kind,
        "target_hash": _stable_hash(target),
        "target_redacted": True,
    }


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
    
    def __init__(
        self,
        config: Optional[ProbeConfig] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        """
        Initialize censorship detector.
        
        Args:
            config: Probe configuration
        """
        self.config = config or ProbeConfig()
        self._results: List[DetectionResult] = []
        self._baseline: Dict[str, Any] = {}
        self.event_bus = event_bus
        self.event_project_root = event_project_root

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize censorship-detector EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _config_metadata(self) -> Dict[str, Any]:
        return {
            "timeout_ms_bucket": _latency_bucket(round(self.config.timeout * 1000)),
            "dns_timeout_ms_bucket": _latency_bucket(
                round(self.config.dns_timeout * 1000)
            ),
            "tcp_timeout_ms_bucket": _latency_bucket(
                round(self.config.tcp_timeout * 1000)
            ),
            "tls_timeout_ms_bucket": _latency_bucket(
                round(self.config.tls_timeout * 1000)
            ),
            "http_timeout_ms_bucket": _latency_bucket(
                round(self.config.http_timeout * 1000)
            ),
            "retries_count": self.config.retries,
            "retries_count_bucket": _count_bucket(self.config.retries),
            "control_server_count": len(self.config.control_servers),
            "control_server_count_bucket": _count_bucket(
                len(self.config.control_servers)
            ),
            "expected_dns_result_count": len(self.config.expected_dns_results),
            "raw_control_servers_redacted": True,
            "raw_expected_dns_results_redacted": True,
        }

    def _result_metadata(self, result: DetectionResult) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "blocking_type": result.blocking_type.value,
            "local_probe_blocked": bool(result.is_blocked),
            "confidence_bucket": _confidence_bucket(result.confidence),
            "latency_ms_bucket": _latency_bucket(result.latency_ms),
            "detail_keys": sorted(str(key)[:48] for key in result.details.keys()),
            "detail_count_bucket": _count_bucket(len(result.details)),
            "error_present": bool(result.error),
            "raw_details_redacted": True,
            "raw_error_redacted": True,
        }
        metadata.update(_target_metadata(result.target))
        return metadata

    def _publish_evidence(
        self,
        *,
        operation: str,
        result: Optional[DetectionResult] = None,
        started_at: Optional[float] = None,
        status_value: str = "observed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        duration_ms = 0.0
        if result is not None:
            duration_ms = round(result.latency_ms, 3)
        elif started_at is not None:
            duration_ms = round((time.monotonic() - started_at) * 1000.0, 3)

        payload: Dict[str, Any] = {
            "component": "anti_censorship.censorship_detector",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": duration_ms,
            "config": self._config_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_targets_redacted": True,
            "raw_dns_records_redacted": True,
            "raw_http_headers_redacted": True,
            "raw_certificates_redacted": True,
            "raw_errors_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": CENSORSHIP_DETECTOR_CLAIM_BOUNDARY,
        }
        if result is not None:
            payload.update(self._result_metadata(result))
        if metadata:
            payload.update(metadata)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                _SERVICE_AGENT,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish censorship-detector evidence: %s", exc)
            return None

    def _record_and_return(
        self,
        operation: str,
        result: DetectionResult,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DetectionResult:
        self._publish_evidence(
            operation=operation,
            result=result,
            metadata=metadata,
        )
        return result
    
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
            
            return self._record_and_return(
                "detect_dns_manipulation",
                DetectionResult(
                    blocking_type=(
                        BlockingType.DNS_MANIPULATION
                        if is_manipulated
                        else BlockingType.NONE
                    ),
                    is_blocked=is_manipulated,
                    confidence=confidence,
                    target=domain,
                    details={
                        "local_ips": local_ips,
                        "control_ips": list(control_ips),
                        "expected_ips": expected_ips,
                    },
                    latency_ms=latency_ms,
                ),
                metadata={
                    "local_ip_count": len(local_ips),
                    "local_ip_count_bucket": _count_bucket(len(local_ips)),
                    "control_ip_count": len(control_ips),
                    "control_ip_count_bucket": _count_bucket(len(control_ips)),
                    "expected_ip_count": len(expected_ips or []),
                    "expected_ip_count_bucket": _count_bucket(len(expected_ips or [])),
                },
            )
            
        except Exception as e:
            return self._record_and_return(
                "detect_dns_manipulation",
                DetectionResult(
                    blocking_type=BlockingType.UNKNOWN,
                    is_blocked=False,
                    confidence=0.0,
                    target=domain,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                ),
                metadata={
                    "local_ip_count_bucket": "zero",
                    "control_ip_count_bucket": "zero",
                    "expected_ip_count": len(expected_ips or []),
                    "expected_ip_count_bucket": _count_bucket(len(expected_ips or [])),
                },
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
        
        return self._record_and_return(
            "detect_tcp_blocking",
            DetectionResult(
                blocking_type=blocking_type,
                is_blocked=is_blocked,
                confidence=confidence,
                target=f"{host}:{port}",
                details={
                    "attempts": results,
                    "success_rate": successes / self.config.retries,
                },
                latency_ms=latency_ms,
            ),
            metadata={
                "attempt_count": len(results),
                "attempt_count_bucket": _count_bucket(len(results)),
                "success_count": successes,
                "reset_count": resets,
                "timeout_count": timeouts,
                "refused_count": sum(
                    1 for result in results if result.get("error") == "refused"
                ),
                "raw_attempts_redacted": True,
            },
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
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            with socket.create_connection((host, port), timeout=self.config.tls_timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.getpeercert(binary_form=True)
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
                    
                    return self._record_and_return(
                        "detect_tls_interception",
                        DetectionResult(
                            blocking_type=(
                                BlockingType.TLS_INTERCEPTION
                                if is_intercepted
                                else BlockingType.NONE
                            ),
                            is_blocked=is_intercepted,
                            confidence=confidence,
                            target=f"{host}:{port}",
                            details={
                                "issuer": issuer,
                                "subject": subject,
                                "common_name": common_name,
                            },
                            latency_ms=latency_ms,
                        ),
                        metadata={
                            "issuer_present": bool(issuer),
                            "subject_present": bool(subject),
                            "common_name_present": bool(common_name),
                            "raw_certificate_values_redacted": True,
                        },
                    )
                    
        except ssl.SSLCertVerificationError as e:
            return self._record_and_return(
                "detect_tls_interception",
                DetectionResult(
                    blocking_type=BlockingType.TLS_INTERCEPTION,
                    is_blocked=True,
                    confidence=0.9,
                    target=f"{host}:{port}",
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                ),
                metadata={
                    "issuer_present": False,
                    "subject_present": False,
                    "raw_certificate_values_redacted": True,
                },
            )
        except Exception as e:
            return self._record_and_return(
                "detect_tls_interception",
                DetectionResult(
                    blocking_type=BlockingType.UNKNOWN,
                    is_blocked=False,
                    confidence=0.0,
                    target=f"{host}:{port}",
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                ),
                metadata={
                    "issuer_present": False,
                    "subject_present": False,
                    "raw_certificate_values_redacted": True,
                },
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
            
            return self._record_and_return(
                "detect_http_blocking",
                DetectionResult(
                    blocking_type=(
                        BlockingType.HTTP_BLOCKING
                        if is_blocked
                        else BlockingType.NONE
                    ),
                    is_blocked=is_blocked,
                    confidence=confidence,
                    target=url,
                    details=details,
                    latency_ms=latency_ms,
                ),
                metadata={
                    "http_status_code": response.status_code,
                    "redirect_location_present": "redirect_location" in details,
                    "expected_content_present": expected_content is not None,
                    "raw_response_headers_redacted": True,
                    "raw_redirect_location_redacted": True,
                },
            )
            
        except Exception as e:
            return self._record_and_return(
                "detect_http_blocking",
                DetectionResult(
                    blocking_type=BlockingType.UNKNOWN,
                    is_blocked=False,
                    confidence=0.0,
                    target=url,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                ),
                metadata={
                    "redirect_location_present": False,
                    "expected_content_present": expected_content is not None,
                    "raw_response_headers_redacted": True,
                    "raw_redirect_location_redacted": True,
                },
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
                return self._record_and_return(
                    "detect_throttling",
                    DetectionResult(
                        blocking_type=BlockingType.UNKNOWN,
                        is_blocked=False,
                        confidence=0.0,
                        target=f"{host}:{port}",
                        error="Insufficient data",
                        latency_ms=(time.time() - start_time) * 1000,
                    ),
                    metadata={
                        "speed_sample_count": len(speeds),
                        "speed_sample_count_bucket": _count_bucket(len(speeds)),
                        "total_bytes_bucket": _count_bucket(total_bytes),
                        "raw_speed_samples_redacted": True,
                    },
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
            
            return self._record_and_return(
                "detect_throttling",
                DetectionResult(
                    blocking_type=(
                        BlockingType.THROTTLING
                        if is_throttled
                        else BlockingType.NONE
                    ),
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
                ),
                metadata={
                    "speed_sample_count": len(speeds),
                    "speed_sample_count_bucket": _count_bucket(len(speeds)),
                    "total_bytes_bucket": _count_bucket(total_bytes),
                    "raw_speed_samples_redacted": True,
                },
            )
            
        except Exception as e:
            return self._record_and_return(
                "detect_throttling",
                DetectionResult(
                    blocking_type=BlockingType.UNKNOWN,
                    is_blocked=False,
                    confidence=0.0,
                    target=f"{host}:{port}",
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                ),
                metadata={
                    "speed_sample_count_bucket": "zero",
                    "total_bytes_bucket": "zero",
                    "raw_speed_samples_redacted": True,
                },
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
        started_at = time.monotonic()
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
        self._publish_evidence(
            operation="run_full_scan",
            started_at=started_at,
            status_value="completed",
            metadata={
                "target_count": len(targets),
                "target_count_bucket": _count_bucket(len(targets)),
                "result_count": len(results),
                "result_count_bucket": _count_bucket(len(results)),
                "blocked_count": sum(1 for result in results if result.is_blocked),
                "include_throttling": include_throttling,
                "raw_targets_redacted": True,
            },
        )
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all detection results."""
        started_at = time.monotonic()
        if not self._results:
            self._publish_evidence(
                operation="get_summary",
                started_at=started_at,
                status_value="empty",
                metadata={
                    "total_tests": 0,
                    "blocked_count": 0,
                    "result_type_counts": {},
                    "raw_targets_redacted": True,
                },
            )
            return {"total_tests": 0}
        
        blocked = [r for r in self._results if r.is_blocked]
        
        by_type: Dict[str, int] = {}
        for result in self._results:
            t = result.blocking_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        summary = {
            "total_tests": len(self._results),
            "blocked_count": len(blocked),
            "block_rate": len(blocked) / len(self._results),
            "by_type": by_type,
            "last_scan": max(r.timestamp for r in self._results).isoformat(),
        }
        self._publish_evidence(
            operation="get_summary",
            started_at=started_at,
            status_value="read",
            metadata={
                "total_tests": summary["total_tests"],
                "total_tests_bucket": _count_bucket(summary["total_tests"]),
                "blocked_count": summary["blocked_count"],
                "blocked_count_bucket": _count_bucket(summary["blocked_count"]),
                "result_type_counts": dict(by_type),
                "raw_targets_redacted": True,
            },
        )
        return summary
    
    def clear_results(self) -> None:
        """Clear all stored results."""
        started_at = time.monotonic()
        cleared_count = len(self._results)
        self._results.clear()
        self._publish_evidence(
            operation="clear_results",
            started_at=started_at,
            status_value="cleared",
            metadata={
                "cleared_count": cleared_count,
                "cleared_count_bucket": _count_bucket(cleared_count),
                "raw_targets_redacted": True,
            },
        )


__all__ = [
    "BlockingType",
    "DetectionResult",
    "ProbeConfig",
    "CensorshipDetector",
]
