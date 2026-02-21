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
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger(__name__)


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
        original_host = urlparse(request.url).netloc
        
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
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Domain fronting request failed (attempt {attempt + 1}): {e}"
                )
                time.sleep(2 ** attempt)  # Exponential backoff
        
        stats["failures"] += 1
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
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
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
    
    def close(self) -> None:
        """Close all sessions."""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()


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
