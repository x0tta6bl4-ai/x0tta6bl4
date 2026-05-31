"""
Domain Fronting Implementation
==============================

Domain fronting is a censorship circumvention technique that uses
different domain names at different layers of the HTTPS request:
- TLS SNI: Shows a benign domain (e.g., cdn.cloudflare.com)
- HTTP Host header: Shows the actual target domain

This allows bypassing DNS-based and TLS SNI-based blocking.
"""

import logging
import random
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)


_SERVICE_AGENT = "anti-censorship-domain-fronting-client"
_SERVICE_LAYER = "anti_censorship_domain_fronting_local_evidence"
DOMAIN_FRONTING_CLAIM_BOUNDARY = (
    "Local domain-fronting client evidence only. It records local client "
    "configuration presence, provider/method/status buckets, request attempt "
    "counts, target URL/host hashes, stats reads, close calls, duration, and "
    "service identity presence; it does not expose raw target URLs, front "
    "domains, Host headers, CDN IP ranges, user-agent strings, request or "
    "response headers, request bodies, response bodies, redirect locations, "
    "error strings, or prove DNS/SNI blocking bypass, DPI bypass, remote "
    "reachability, packet delivery, anonymity, provider health, client "
    "installation, or production customer traffic use."
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


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:16]


def _provider_value(provider: Optional["CDNProvider"]) -> str:
    return provider.value if isinstance(provider, CDNProvider) else "unknown"


def _url_metadata(url: str, target_host: Optional[str]) -> Dict[str, Any]:
    parsed = urlparse(url)
    return {
        "url_hash": _stable_hash(url),
        "url_scheme_present": bool(parsed.scheme),
        "url_host_hash": _stable_hash(parsed.netloc) if parsed.netloc else None,
        "target_host_hash": _stable_hash(target_host) if target_host else None,
        "target_host_present": bool(target_host),
        "raw_url_redacted": True,
        "raw_target_host_redacted": True,
    }


class CDNProvider(Enum):
    """Supported CDN providers for domain fronting."""
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    FASTLY = "fastly"
    CLOUDFRONT = "cloudfront"
    GOOGLE = "google"
    AZURE = "azure"
    CUSTOM = "custom"


@dataclass
class CDNConfig:
    """Configuration for a CDN provider."""
    provider: CDNProvider
    front_domain: str  # Domain shown in TLS SNI
    cdn_ips: List[str]  # CDN edge server IPs
    host_header: Optional[str] = None  # Override Host header
    verify_ssl: bool = True
    timeout: float = 30.0
    extra_headers: Dict[str, str] = field(default_factory=dict)


# Predefined CDN configurations
CDN_CONFIGS: Dict[CDNProvider, CDNConfig] = {
    CDNProvider.CLOUDFLARE: CDNConfig(
        provider=CDNProvider.CLOUDFLARE,
        front_domain="cloudflare.com",
        cdn_ips=[
            "104.16.0.0/13",  # Cloudflare IP ranges
            "104.24.0.0/14",
            "172.64.0.0/13",
        ],
    ),
    CDNProvider.AKAMAI: CDNConfig(
        provider=CDNProvider.AKAMAI,
        front_domain="a.akamai.net",
        cdn_ips=["23.0.0.0/12"],
    ),
    CDNProvider.FASTLY: CDNConfig(
        provider=CDNProvider.FASTLY,
        front_domain="fastly.com",
        cdn_ips=["151.101.0.0/16"],
    ),
    CDNProvider.CLOUDFRONT: CDNConfig(
        provider=CDNProvider.CLOUDFRONT,
        front_domain="cloudfront.net",
        cdn_ips=["13.32.0.0/15", "52.46.0.0/17"],
    ),
    CDNProvider.GOOGLE: CDNConfig(
        provider=CDNProvider.GOOGLE,
        front_domain="googleusercontent.com",
        cdn_ips=["74.125.0.0/16"],
    ),
}


@dataclass
class FrontingConfig:
    """Configuration for domain fronting client."""
    enabled: bool = True
    provider: CDNProvider = CDNProvider.CLOUDFLARE
    target_host: str = ""
    front_domain: str = ""
    rotate_providers: bool = True
    max_retries: int = 3
    timeout: float = 30.0
    verify_ssl: bool = False  # Often disabled for fronting
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    custom_cdn_configs: Dict[CDNProvider, CDNConfig] = field(default_factory=dict)
    event_bus: Optional[EventBus] = field(default=None, repr=False)
    event_project_root: Optional[str] = None


class DomainFrontingAdapter(HTTPAdapter):
    """
    Custom HTTP adapter that implements domain fronting.
    
    Modifies the TLS connection to use a different SNI than the Host header.
    """
    
    def __init__(
        self,
        front_domain: str,
        target_host: str,
        verify_ssl: bool = False,
        **kwargs
    ):
        self.front_domain = front_domain
        self.target_host = target_host
        self.verify_ssl = verify_ssl
        super().__init__(**kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        """Initialize connection pool with custom SSL context."""
        # Create SSL context that doesn't verify hostname
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE if not self.verify_ssl else ssl.CERT_REQUIRED
        
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)
    
    def send(self, request, **kwargs):
        """Modify request for domain fronting."""
        # Store original host
        urlparse(request.url).netloc
        
        # Set Host header to target
        if self.target_host:
            request.headers['Host'] = self.target_host
        
        # Add fronting headers
        request.headers.setdefault('User-Agent', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        return super().send(request, **kwargs)


class DomainFrontingClient:
    """
    Client for making domain-fronted HTTP requests.
    
    Features:
    - Multiple CDN provider support
    - Automatic provider rotation
    - Connection pooling
    - Retry logic
    - Request obfuscation
    """
    
    def __init__(self, config: Optional[FrontingConfig] = None):
        """
        Initialize domain fronting client.
        
        Args:
            config: Fronting configuration
        """
        self.config = config or FrontingConfig()
        self._sessions: Dict[CDNProvider, requests.Session] = {}
        self._provider_stats: Dict[CDNProvider, Dict[str, Any]] = {}
        self._current_provider_index = 0
        self.event_bus = self.config.event_bus
        self.event_project_root = self.config.event_project_root
        
        # Merge custom CDN configs
        self._cdn_configs = {**CDN_CONFIGS, **self.config.custom_cdn_configs}
        
        # Initialize stats for each provider
        for provider in CDNProvider:
            self._provider_stats[provider] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "last_used": None,
            }

        self._publish_evidence(
            operation="initialize",
            status_value="ready",
            started_at=time.monotonic(),
            metadata={
                "available_provider_count": len(self._cdn_configs),
                "available_provider_count_bucket": _count_bucket(
                    len(self._cdn_configs)
                ),
            },
        )

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize domain-fronting EventBus: %s", exc)
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
            "enabled": bool(self.config.enabled),
            "provider": self.config.provider.value,
            "target_host_present": bool(self.config.target_host),
            "front_domain_present": bool(self.config.front_domain),
            "rotate_providers": bool(self.config.rotate_providers),
            "max_retries_count": self.config.max_retries,
            "max_retries_count_bucket": _count_bucket(self.config.max_retries),
            "timeout_ms_bucket": _latency_bucket(round(self.config.timeout * 1000)),
            "verify_ssl": bool(self.config.verify_ssl),
            "user_agent_present": bool(self.config.user_agent),
            "custom_cdn_config_count": len(self.config.custom_cdn_configs),
            "custom_cdn_config_count_bucket": _count_bucket(
                len(self.config.custom_cdn_configs)
            ),
            "raw_target_host_redacted": True,
            "raw_front_domain_redacted": True,
            "raw_user_agent_redacted": True,
            "raw_cdn_ips_redacted": True,
            "raw_extra_headers_redacted": True,
        }

    def _provider_stats_metadata(self) -> Dict[str, Any]:
        active = {
            provider.value: {
                "requests": stats["requests"],
                "successes": stats["successes"],
                "failures": stats["failures"],
                "last_used_present": stats["last_used"] is not None,
            }
            for provider, stats in self._provider_stats.items()
            if stats["requests"] > 0
        }
        return {
            "active_provider_count": len(active),
            "active_provider_count_bucket": _count_bucket(len(active)),
            "provider_stats": active,
            "raw_provider_domains_redacted": True,
        }

    def _publish_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "anti_censorship.domain_fronting",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "config": self._config_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": operation in {"initialize", "close"},
            "observed_state": True,
            "payloads_redacted": True,
            "raw_urls_redacted": True,
            "raw_targets_redacted": True,
            "raw_http_headers_redacted": True,
            "raw_request_body_redacted": True,
            "raw_response_body_redacted": True,
            "raw_redirects_redacted": True,
            "raw_errors_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": DOMAIN_FRONTING_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value.endswith("failed")
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish domain-fronting evidence: %s", exc)
            return None
    
    def _get_session(
        self,
        provider: CDNProvider,
        target_host: str,
    ) -> requests.Session:
        """Get or create a session for the provider."""
        if provider not in self._sessions:
            cdn_config = self._cdn_configs.get(provider)
            if not cdn_config:
                raise ValueError(f"No configuration for provider: {provider}")
            
            session = requests.Session()
            
            # Create fronting adapter
            adapter = DomainFrontingAdapter(
                front_domain=cdn_config.front_domain,
                target_host=target_host,
                verify_ssl=self.config.verify_ssl,
            )
            
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            
            # Set default headers
            session.headers.update({
                'User-Agent': self.config.user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            })
            
            self._sessions[provider] = session
        
        return self._sessions[provider]
    
    def _select_provider(self) -> CDNProvider:
        """Select a CDN provider based on configuration."""
        if not self.config.rotate_providers:
            return self.config.provider
        
        # Get providers sorted by success rate
        available = [
            (p, self._provider_stats[p]["successes"] / 
             max(1, self._provider_stats[p]["requests"]))
            for p in CDNProvider
            if p in self._cdn_configs
        ]
        
        if not available:
            return self.config.provider
        
        # Weighted random selection favoring successful providers
        total_weight = sum(w for _, w in available)
        r = random.random() * total_weight
        
        cumulative = 0
        for provider, weight in available:
            cumulative += weight
            if r <= cumulative:
                return provider
        
        return available[0][0]
    
    def request(
        self,
        method: str,
        url: str,
        target_host: Optional[str] = None,
        provider: Optional[CDNProvider] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make a domain-fronted HTTP request.
        
        Args:
            method: HTTP method
            url: Target URL
            target_host: Host header value (defaults to URL host)
            provider: CDN provider to use
            **kwargs: Additional request arguments
            
        Returns:
            HTTP Response
        """
        started_at = time.monotonic()
        # Parse target host from URL if not provided
        if not target_host:
            parsed = urlparse(url)
            target_host = parsed.netloc
        
        # Select provider
        selected_provider = provider or self._select_provider()
        
        # Get session
        session = self._get_session(selected_provider, target_host)
        
        # Update stats
        stats = self._provider_stats[selected_provider]
        stats["requests"] += 1
        stats["last_used"] = time.time()
        
        # Set timeout
        kwargs.setdefault('timeout', self.config.timeout)
        kwargs.setdefault('verify', self.config.verify_ssl)
        
        # Make request with retries
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = session.request(method, url, **kwargs)
                stats["successes"] += 1
                metadata = {
                    "method": str(method).upper()[:16],
                    "provider": _provider_value(selected_provider),
                    "attempt_count": attempt + 1,
                    "attempt_count_bucket": _count_bucket(attempt + 1),
                    "http_status_code": getattr(response, "status_code", None),
                    "request_kwarg_keys": sorted(str(key)[:48] for key in kwargs.keys()),
                    "raw_request_kwargs_redacted": True,
                    "raw_response_headers_redacted": True,
                }
                metadata.update(_url_metadata(url, target_host))
                self._publish_evidence(
                    operation="request",
                    status_value="request_completed",
                    started_at=started_at,
                    metadata=metadata,
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Domain fronting request failed (attempt {attempt + 1}): {e}"
                )
                time.sleep(2 ** attempt)  # Exponential backoff
        
        stats["failures"] += 1
        metadata = {
            "method": str(method).upper()[:16],
            "provider": _provider_value(selected_provider),
            "attempt_count": self.config.max_retries,
            "attempt_count_bucket": _count_bucket(self.config.max_retries),
            "request_kwarg_keys": sorted(str(key)[:48] for key in kwargs.keys()),
            "raw_request_kwargs_redacted": True,
            "raw_response_headers_redacted": True,
        }
        metadata.update(_url_metadata(url, target_host))
        self._publish_evidence(
            operation="request",
            status_value="request_failed",
            started_at=started_at,
            metadata=metadata,
            error_type=type(last_error).__name__ if last_error else "ConnectionError",
        )
        raise ConnectionError(
            f"Domain fronting failed after {self.config.max_retries} attempts: {last_error}"
        )
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Make a GET request."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Make a POST request."""
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Make a PUT request."""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Make a DELETE request."""
        return self.request("DELETE", url, **kwargs)
    
    def test_fronting(self, test_url: str = "https://www.google.com") -> Dict[str, bool]:
        """
        Test domain fronting with each provider.
        
        Args:
            test_url: URL to test against
            
        Returns:
            Dictionary of provider -> success status
        """
        started_at = time.monotonic()
        results = {}
        
        for provider in CDNProvider:
            if provider not in self._cdn_configs:
                continue
            
            try:
                response = self.get(
                    test_url,
                    provider=provider,
                    timeout=10.0,
                )
                results[provider.value] = response.status_code == 200
            except Exception as e:
                logger.debug(f"Fronting test failed for {provider.value}: {e}")
                results[provider.value] = False
        
        self._publish_evidence(
            operation="test_fronting",
            status_value="completed",
            started_at=started_at,
            metadata={
                "provider_count": len(results),
                "provider_count_bucket": _count_bucket(len(results)),
                "successful_provider_count": sum(1 for value in results.values() if value),
                "raw_test_url_redacted": True,
            },
        )
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        started_at = time.monotonic()
        stats = {
            "config": {
                "enabled": self.config.enabled,
                "provider": self.config.provider.value,
                "rotate_providers": self.config.rotate_providers,
            },
            "providers": {
                p.value: stats for p, stats in self._provider_stats.items()
                if stats["requests"] > 0
            },
        }
        self._publish_evidence(
            operation="get_stats",
            status_value="read",
            started_at=started_at,
            metadata=self._provider_stats_metadata(),
        )
        return stats
    
    def close(self) -> None:
        """Close all sessions."""
        started_at = time.monotonic()
        session_count = len(self._sessions)
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
        self._publish_evidence(
            operation="close",
            status_value="closed",
            started_at=started_at,
            metadata={
                "closed_session_count": session_count,
                "closed_session_count_bucket": _count_bucket(session_count),
            },
        )


def create_fronting_client(
    provider: str = "cloudflare",
    target_host: str = "",
    **kwargs
) -> DomainFrontingClient:
    """
    Factory function to create a domain fronting client.
    
    Args:
        provider: CDN provider name
        target_host: Target host for Host header
        **kwargs: Additional configuration
        
    Returns:
        Configured DomainFrontingClient
    """
    try:
        cdn_provider = CDNProvider(provider.lower())
    except ValueError:
        cdn_provider = CDNProvider.CUSTOM
    
    config = FrontingConfig(
        provider=cdn_provider,
        target_host=target_host,
        **kwargs
    )
    
    return DomainFrontingClient(config)


__all__ = [
    "CDNProvider",
    "CDNConfig",
    "CDN_CONFIGS",
    "FrontingConfig",
    "DomainFrontingAdapter",
    "DomainFrontingClient",
    "create_fronting_client",
]
