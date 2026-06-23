"""
Residential Proxy Manager for Google Cloud API access.

Provides:
- Rotating residential IP addresses
- Health monitoring of proxy endpoints
- Geographic IP rotation
- Automatic failover between proxy pools
- TLS fingerprint randomization
- Integration with Xray proxy infrastructure
"""

import asyncio
import hashlib
import logging
import random
import ssl
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.circuit_breaker import CircuitBreaker
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "residential-proxy-manager"
_SERVICE_LAYER = "network_residential_proxy_manager_observed_state"
RESIDENTIAL_PROXY_MANAGER_CLAIM_BOUNDARY = (
    "Local residential proxy manager observed-state evidence only. It records "
    "redacted health-check, selection, and request-attempt metadata with proxy "
    "and target identifiers hashed. It does not copy proxy hosts, credentials, "
    "target URLs, headers, request bodies, or response payloads, and it does not "
    "prove provider reputation, customer traffic delivery, or end-to-end "
    "dataplane quality."
)


def _hash_value(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class ProxyStatus(Enum):
    """Proxy endpoint status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    BANNED = "banned"


@dataclass
class ProxyEndpoint:
    """Residential proxy endpoint configuration."""

    id: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    region: str = "unknown"
    country_code: str = "US"
    city: Optional[str] = None
    isp: Optional[str] = None

    # Health tracking
    status: ProxyStatus = ProxyStatus.HEALTHY
    last_check: float = field(default_factory=time.time)
    response_time_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    ban_count: int = 0

    # Rate limiting
    max_requests_per_minute: int = 60
    request_times: deque = field(default_factory=lambda: deque(maxlen=100))

    def to_url(self) -> str:
        """Convert to proxy URL format."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    def record_request(self):
        """Record a request timestamp for rate limiting."""
        now = time.time()
        self.request_times.append(now)

    def get_requests_in_last_minute(self) -> int:
        """Count requests in the last minute."""
        now = time.time()
        cutoff = now - 60
        return sum(1 for t in self.request_times if t > cutoff)

    def is_rate_limited(self) -> bool:
        """Check if proxy is rate limited."""
        return self.get_requests_in_last_minute() >= self.max_requests_per_minute


@dataclass
class DomainReputation:
    """Domain reputation scoring for proxy selection."""

    domain: str
    score: float = 1.0  # 0.0 to 1.0
    last_access: float = field(default_factory=time.time)
    block_count: int = 0
    success_count: int = 0

    def update_score(self, success: bool):
        """Update reputation score based on access result."""
        if success:
            self.success_count += 1
            self.score = min(1.0, self.score + 0.1)
        else:
            self.block_count += 1
            self.score = max(0.0, self.score - 0.2)
        self.last_access = time.time()


class TLSFingerprintRandomizer:
    """Randomize TLS fingerprints to avoid detection."""

    BROWSER_PROFILES = [
        {
            "name": "chrome_120",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "tls_version": ssl.PROTOCOL_TLS_CLIENT,
            "ciphers": "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384",
        },
        {
            "name": "firefox_121",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "tls_version": ssl.PROTOCOL_TLS_CLIENT,
            "ciphers": "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384",
        },
        {
            "name": "safari_17",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "tls_version": ssl.PROTOCOL_TLS_CLIENT,
            "ciphers": "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256",
        },
    ]

    def __init__(self):
        self._current_profile: Optional[Dict[str, Any]] = None

    def get_random_profile(self) -> Dict[str, Any]:
        """Get a random browser profile."""
        self._current_profile = random.choice(self.BROWSER_PROFILES)
        return self._current_profile

    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with randomized fingerprint."""
        profile = self.get_random_profile()

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3

        # Set cipher suites based on profile
        if "ciphers" in profile:
            context.set_ciphers(profile["ciphers"])

        return context

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers matching the browser profile."""
        if not self._current_profile:
            self.get_random_profile()

        return {
            "User-Agent": self._current_profile["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }


class ResidentialProxyManager:
    """
    Manager for residential proxy pool with health monitoring and rotation.
    """

    def __init__(
        self,
        health_check_interval: int = 60,
        rotation_interval: int = 300,
        max_failures: int = 3,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.proxies: List[ProxyEndpoint] = []
        self.domain_reputations: Dict[str, DomainReputation] = {}
        self.tls_randomizer = TLSFingerprintRandomizer()

        self.health_check_interval = health_check_interval
        self.rotation_interval = rotation_interval
        self.max_failures = max_failures

        self._current_proxy_index = 0
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self.event_bus = event_bus
        self.event_project_root = event_project_root

        # Circuit breaker for proxy operations
        self._circuit_breaker = CircuitBreaker(
            name="proxy_manager", failure_threshold=5, recovery_timeout=60.0
        )
        self.thinking_coach = AgentThinkingCoach(
            agent_id=_SERVICE_AGENT,
            role="security",
            capabilities=("zero-trust", "ops", "network"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error(
                "Failed to initialize residential-proxy-manager EventBus: %s",
                exc,
            )
            return None

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {field: bool(value) for field, value in identity.items()}

    def _proxy_identity_metadata(
        self, proxy: Optional[ProxyEndpoint]
    ) -> Dict[str, Any]:
        if proxy is None:
            return {"present": False}
        return {
            "present": True,
            "proxy_id_hash": _hash_value(proxy.id),
            "status": proxy.status.value,
            "region": proxy.region,
            "country_code": proxy.country_code,
            "has_auth": bool(proxy.username or proxy.password),
        }

    def _prepare_proxy_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Prepare redacted thinking context for local proxy decisions."""
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "proxy_pool_total": len(self.proxies),
            "healthy_proxy_count": sum(
                1 for proxy in self.proxies if proxy.status == ProxyStatus.HEALTHY
            ),
            "degraded_proxy_count": sum(
                1 for proxy in self.proxies if proxy.status == ProxyStatus.DEGRADED
            ),
            "unhealthy_proxy_count": sum(
                1 for proxy in self.proxies if proxy.status == ProxyStatus.UNHEALTHY
            ),
            "banned_proxy_count": sum(
                1 for proxy in self.proxies if proxy.status == ProxyStatus.BANNED
            ),
            "domain_reputation_count": len(self.domain_reputations),
            "constraints": {
                "redact_proxy_credentials": True,
                "redact_proxy_hosts": True,
                "hash_target_domains": True,
                "do_not_copy_headers_or_body": True,
            },
            "safety_boundary": (
                "Do not claim provider reputation, customer traffic delivery, or "
                "end-to-end dataplane quality from local proxy-manager observations."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def _publish_observed_state(
        self,
        *,
        operation: str,
        status: str,
        success: bool,
        duration_ms: float,
        payload: Dict[str, Any],
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None
        event_payload = {
            "component": "network.residential_proxy_manager",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status,
            "success": bool(success),
            "duration_ms": round(float(duration_ms), 3),
            "service_identity_present": self._service_identity_presence(),
            "raw_identifiers_redacted": True,
            "claim_boundary": RESIDENTIAL_PROXY_MANAGER_CLAIM_BOUNDARY,
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            **payload,
        }
        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                _SERVICE_AGENT,
                event_payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish residential proxy evidence: %s", exc)
            return None

    def add_proxy(self, proxy: ProxyEndpoint):
        """Add a proxy endpoint to the pool."""
        self.proxies.append(proxy)
        logger.info(f"Added proxy {proxy.id} ({proxy.region})")

    def add_proxies_from_config(self, config: List[Dict[str, Any]]):
        """Add multiple proxies from configuration."""
        for proxy_config in config:
            proxy = ProxyEndpoint(**proxy_config)
            self.add_proxy(proxy)

    async def start(self):
        """Start the proxy manager and health monitoring."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Residential proxy manager started")

    async def stop(self):
        """Stop the proxy manager."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Residential proxy manager stopped")

    async def _health_check_loop(self):
        """Background task for health checking proxies."""
        while self._running:
            try:
                await self._check_all_proxies()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(10)

    async def _check_all_proxies(self):
        """Check health of all proxy endpoints."""
        tasks = [self._check_proxy_health(proxy) for proxy in self.proxies]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_proxy_health(self, proxy: ProxyEndpoint):
        """Check health of a single proxy."""
        started = time.perf_counter()
        previous_status = proxy.status
        status_code: Optional[int] = None
        error_type: Optional[str] = None
        success = False
        try:
            start_time = time.time()

            # Test proxy with a simple request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.google.com",
                    proxy=proxy.to_url(),
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False,
                ) as response:
                    elapsed_ms = (time.time() - start_time) * 1000
                    proxy.response_time_ms = elapsed_ms
                    status_code = int(response.status)

                    if response.status == 200:
                        success = True
                        proxy.success_count += 1
                        proxy.failure_count = 0

                        if proxy.status == ProxyStatus.UNHEALTHY:
                            proxy.status = ProxyStatus.HEALTHY
                            logger.info(f"Proxy {proxy.id} recovered")
                    else:
                        proxy.failure_count += 1
                        if proxy.failure_count >= self.max_failures:
                            proxy.status = ProxyStatus.UNHEALTHY
                            logger.warning(f"Proxy {proxy.id} marked unhealthy")
        except Exception as e:
            error_type = type(e).__name__
            proxy.failure_count += 1
            if proxy.failure_count >= self.max_failures:
                proxy.status = ProxyStatus.UNHEALTHY
            logger.debug(f"Proxy {proxy.id} health check failed: {e}")

        proxy.last_check = time.time()
        self._prepare_proxy_thinking_context(
            task_type="residential_proxy_health_check",
            goal="classify proxy health from a local probe without exposing proxy details",
            extra={
                "proxy": self._proxy_identity_metadata(proxy),
                "previous_status": previous_status.value,
                "new_status": proxy.status.value,
                "status_code": status_code,
                "error_type": error_type,
                "success": success,
            },
        )
        self._publish_observed_state(
            operation="health_check",
            status="health_check_ok" if success else "health_check_failed",
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "proxy": self._proxy_identity_metadata(proxy),
                "previous_status": previous_status.value,
                "new_status": proxy.status.value,
                "status_code": status_code,
                "error_type": error_type,
                "health_check": {
                    "target": "google_homepage_probe",
                    "max_failures": int(self.max_failures),
                    "success_count": int(proxy.success_count),
                    "failure_count": int(proxy.failure_count),
                    "ban_count": int(proxy.ban_count),
                    "response_time_ms": round(float(proxy.response_time_ms), 3),
                },
            },
        )

    def get_domain_reputation(self, domain: str) -> DomainReputation:
        """Get or create domain reputation."""
        if domain not in self.domain_reputations:
            self.domain_reputations[domain] = DomainReputation(domain=domain)
        return self.domain_reputations[domain]

    async def get_proxy(
        self,
        target_domain: Optional[str] = None,
        preferred_region: Optional[str] = None,
        require_healthy: bool = True,
    ) -> Optional[ProxyEndpoint]:
        """
        Get a proxy for the target domain with smart selection.

        Args:
            target_domain: Target domain for reputation-based selection
            preferred_region: Preferred geographic region
            require_healthy: Only return healthy proxies

        Returns:
            Selected proxy endpoint or None
        """
        async with self._lock:
            started = time.perf_counter()
            candidates = self.proxies
            candidate_counts: Dict[str, int] = {
                "pool_total": len(candidates),
                "after_health_filter": len(candidates),
                "after_region_filter": len(candidates),
                "rate_limited": 0,
                "after_rate_limit_filter": len(candidates),
            }

            # Filter by health status
            if require_healthy:
                candidates = [p for p in candidates if p.status == ProxyStatus.HEALTHY]
                candidate_counts["after_health_filter"] = len(candidates)

            if not candidates:
                logger.error("No healthy proxies available")
                candidate_counts["after_region_filter"] = len(candidates)
                candidate_counts["after_rate_limit_filter"] = len(candidates)
                self._prepare_proxy_thinking_context(
                    task_type="residential_proxy_selection",
                    goal="select an eligible proxy or explain why none is safe to use",
                    extra={
                        "status": "no_eligible_proxy_after_health_filter",
                        "target_domain_hash": _hash_value(target_domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "require_healthy": bool(require_healthy),
                        "candidate_counts": dict(candidate_counts),
                    },
                )
                self._publish_observed_state(
                    operation="select_proxy",
                    status="no_eligible_proxy_after_health_filter",
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "target_domain_hash": _hash_value(target_domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "require_healthy": bool(require_healthy),
                        "candidate_counts": candidate_counts,
                        "selected_proxy": self._proxy_identity_metadata(None),
                    },
                )
                return None

            # Filter by region if specified
            if preferred_region:
                region_candidates = [
                    p for p in candidates if p.region == preferred_region
                ]
                if region_candidates:
                    candidates = region_candidates
                candidate_counts["after_region_filter"] = len(candidates)

            # Filter by rate limit
            before_rate_limit = len(candidates)
            candidates = [p for p in candidates if not p.is_rate_limited()]
            candidate_counts["rate_limited"] = before_rate_limit - len(candidates)
            candidate_counts["after_rate_limit_filter"] = len(candidates)

            if not candidates:
                logger.warning("All proxies rate limited")
                self._prepare_proxy_thinking_context(
                    task_type="residential_proxy_selection",
                    goal="select an eligible proxy or explain why none is safe to use",
                    extra={
                        "status": "no_eligible_proxy_after_rate_limit_filter",
                        "target_domain_hash": _hash_value(target_domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "require_healthy": bool(require_healthy),
                        "candidate_counts": dict(candidate_counts),
                    },
                )
                self._publish_observed_state(
                    operation="select_proxy",
                    status="no_eligible_proxy_after_rate_limit_filter",
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "target_domain_hash": _hash_value(target_domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "require_healthy": bool(require_healthy),
                        "candidate_counts": candidate_counts,
                        "selected_proxy": self._proxy_identity_metadata(None),
                    },
                )
                return None

            reputation_bucket = "none"
            # Domain reputation-based selection
            if target_domain:
                reputation = self.get_domain_reputation(target_domain)
                reputation_bucket = "low" if reputation.score < 0.5 else "normal"

                # If domain has low reputation, prefer proxies with better history
                if reputation.score < 0.5:
                    # Sort by success count
                    candidates = sorted(
                        candidates, key=lambda p: p.success_count, reverse=True
                    )

            # Round-robin with randomization
            if len(candidates) > 1:
                self._current_proxy_index = (self._current_proxy_index + 1) % len(
                    candidates
                )
                # Add some randomization to avoid patterns
                if random.random() < 0.3:
                    self._current_proxy_index = random.randint(0, len(candidates) - 1)

                proxy = candidates[self._current_proxy_index]
            else:
                proxy = candidates[0]

            proxy.record_request()
            self._prepare_proxy_thinking_context(
                task_type="residential_proxy_selection",
                goal="select an eligible proxy using health, region, rate, and reputation signals",
                extra={
                    "status": "proxy_selected",
                    "target_domain_hash": _hash_value(target_domain),
                    "preferred_region_hash": _hash_value(preferred_region),
                    "require_healthy": bool(require_healthy),
                    "candidate_counts": dict(candidate_counts),
                    "reputation_bucket": reputation_bucket,
                    "selected_proxy": self._proxy_identity_metadata(proxy),
                },
            )
            self._publish_observed_state(
                operation="select_proxy",
                status="proxy_selected",
                success=True,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "target_domain_hash": _hash_value(target_domain),
                    "preferred_region_hash": _hash_value(preferred_region),
                    "require_healthy": bool(require_healthy),
                    "candidate_counts": candidate_counts,
                    "reputation_bucket": reputation_bucket,
                    "selected_proxy": self._proxy_identity_metadata(proxy),
                },
            )
            return proxy

    async def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        target_domain: Optional[str] = None,
        preferred_region: Optional[str] = None,
        max_retries: int = 3,
    ) -> aiohttp.ClientResponse:
        """
        Make an HTTP request through a residential proxy.

        Args:
            url: Target URL
            method: HTTP method
            headers: Additional headers
            data: Request body
            target_domain: Domain for reputation tracking
            preferred_region: Preferred proxy region
            max_retries: Maximum retry attempts

        Returns:
            HTTP response
        """
        domain = target_domain or url.split("/")[2]
        reputation = self.get_domain_reputation(domain)

        if max_retries <= 0:
            self._prepare_proxy_thinking_context(
                task_type="residential_proxy_request",
                goal="reject requests with invalid retry budget before proxy use",
                extra={
                    "status": "invalid_retry_budget",
                    "target_domain_hash": _hash_value(domain),
                    "preferred_region_hash": _hash_value(preferred_region),
                    "request": {
                        "method": method.upper(),
                        "attempt": 0,
                        "max_retries": int(max_retries),
                        "headers_present": bool(headers),
                        "body_present": data is not None,
                    },
                },
            )
            self._publish_observed_state(
                operation="request",
                status="invalid_retry_budget",
                success=False,
                duration_ms=0.0,
                payload={
                    "target_domain_hash": _hash_value(domain),
                    "preferred_region_hash": _hash_value(preferred_region),
                    "selected_proxy": self._proxy_identity_metadata(None),
                    "request": {
                        "method": method.upper(),
                        "attempt": 0,
                        "max_retries": int(max_retries),
                        "headers_present": bool(headers),
                        "body_present": data is not None,
                    },
                    "error_type": "InvalidRetryBudget",
                },
            )
            raise RuntimeError("Max retries exceeded")

        for attempt in range(max_retries):
            started = time.perf_counter()
            proxy = await self.get_proxy(
                target_domain=domain, preferred_region=preferred_region
            )

            if not proxy:
                self._prepare_proxy_thinking_context(
                    task_type="residential_proxy_request",
                    goal="stop request attempt when no eligible proxy is available",
                    extra={
                        "status": "no_proxy_available",
                        "target_domain_hash": _hash_value(domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "request": {
                            "method": method.upper(),
                            "attempt": attempt + 1,
                            "max_retries": int(max_retries),
                            "headers_present": bool(headers),
                            "body_present": data is not None,
                        },
                    },
                )
                self._publish_observed_state(
                    operation="request",
                    status="no_proxy_available",
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "target_domain_hash": _hash_value(domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "selected_proxy": self._proxy_identity_metadata(None),
                        "request": {
                            "method": method.upper(),
                            "attempt": attempt + 1,
                            "max_retries": int(max_retries),
                            "headers_present": bool(headers),
                            "body_present": data is not None,
                        },
                        "error_type": "NoProxyAvailable",
                    },
                )
                raise RuntimeError("No proxies available")

            try:
                # Randomize TLS fingerprint
                ssl_context = self.tls_randomizer.create_ssl_context()
                browser_headers = self.tls_randomizer.get_headers()

                # Merge headers
                request_headers = {**browser_headers}
                if headers:
                    request_headers.update(headers)

                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        headers=request_headers,
                        data=data,
                        proxy=proxy.to_url(),
                        ssl=ssl_context,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        # Update reputation
                        reputation.update_score(response.status < 400)

                        if response.status == 403:
                            # Possible block, mark proxy as degraded
                            proxy.ban_count += 1
                            if proxy.ban_count >= 3:
                                proxy.status = ProxyStatus.BANNED
                                logger.warning(f"Proxy {proxy.id} banned by {domain}")

                        self._prepare_proxy_thinking_context(
                            task_type="residential_proxy_request",
                            goal="observe proxied response while keeping target and payload redacted",
                            extra={
                                "status": "response_observed",
                                "target_domain_hash": _hash_value(domain),
                                "preferred_region_hash": _hash_value(preferred_region),
                                "selected_proxy": self._proxy_identity_metadata(proxy),
                                "request": {
                                    "method": method.upper(),
                                    "attempt": attempt + 1,
                                    "max_retries": int(max_retries),
                                    "headers_present": bool(headers),
                                    "body_present": data is not None,
                                },
                                "response": {
                                    "status_code": int(response.status),
                                    "blocked_status": response.status == 403,
                                },
                                "reputation": {
                                    "score_bucket": (
                                        "low" if reputation.score < 0.5 else "normal"
                                    ),
                                    "success_count": int(reputation.success_count),
                                    "block_count": int(reputation.block_count),
                                },
                            },
                        )
                        self._publish_observed_state(
                            operation="request",
                            status="response_observed",
                            success=response.status < 400,
                            duration_ms=(time.perf_counter() - started) * 1000,
                            payload={
                                "target_domain_hash": _hash_value(domain),
                                "preferred_region_hash": _hash_value(preferred_region),
                                "selected_proxy": self._proxy_identity_metadata(proxy),
                                "request": {
                                    "method": method.upper(),
                                    "attempt": attempt + 1,
                                    "max_retries": int(max_retries),
                                    "headers_present": bool(headers),
                                    "body_present": data is not None,
                                },
                                "response": {
                                    "status_code": int(response.status),
                                    "blocked_status": response.status == 403,
                                },
                                "reputation": {
                                    "score_bucket": (
                                        "low" if reputation.score < 0.5 else "normal"
                                    ),
                                    "success_count": int(reputation.success_count),
                                    "block_count": int(reputation.block_count),
                                },
                            },
                        )
                        return response

            except Exception as e:
                logger.warning(f"Request failed with proxy {proxy.id}: {e}")
                proxy.failure_count += 1
                reputation.update_score(False)
                self._prepare_proxy_thinking_context(
                    task_type="residential_proxy_request",
                    goal="record failed proxied request attempt without leaking request data",
                    extra={
                        "status": "request_exception",
                        "target_domain_hash": _hash_value(domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "selected_proxy": self._proxy_identity_metadata(proxy),
                        "request": {
                            "method": method.upper(),
                            "attempt": attempt + 1,
                            "max_retries": int(max_retries),
                            "headers_present": bool(headers),
                            "body_present": data is not None,
                        },
                        "error_type": type(e).__name__,
                    },
                )
                self._publish_observed_state(
                    operation="request",
                    status="request_exception",
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "target_domain_hash": _hash_value(domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "selected_proxy": self._proxy_identity_metadata(proxy),
                        "request": {
                            "method": method.upper(),
                            "attempt": attempt + 1,
                            "max_retries": int(max_retries),
                            "headers_present": bool(headers),
                            "body_present": data is not None,
                        },
                        "error_type": type(e).__name__,
                    },
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    raise

        raise RuntimeError("Max retries exceeded")

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose thinking profile and latest redacted proxy decision context."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }


class XrayResidentialIntegration:
    """
    Integration between Xray and residential proxy layer.
    """

    def __init__(
        self,
        proxy_manager: ResidentialProxyManager,
        xray_config_path: str = "/usr/local/etc/xray/config.json",
    ):
        self.proxy_manager = proxy_manager
        self.xray_config_path = xray_config_path

    def generate_xray_outbound(self, proxy: ProxyEndpoint) -> Dict[str, Any]:
        """Generate Xray outbound configuration for a proxy."""
        return {
            "protocol": "socks",
            "settings": {
                "servers": [
                    {
                        "address": proxy.host,
                        "port": proxy.port,
                        "users": (
                            [
                                {
                                    "user": proxy.username or "",
                                    "pass": proxy.password or "",
                                }
                            ]
                            if proxy.username
                            else []
                        ),
                    }
                ]
            },
            "tag": f"residential-{proxy.id}",
            "streamSettings": {"sockopt": {"tcpFastOpen": True, "tcpNoDelay": True}},
        }

    async def update_xray_config(self, target_domains: List[str]):
        """
        Update Xray configuration to route target domains through residential proxies.

        Args:
            target_domains: List of domains to route through residential proxies
        """
        import json

        # Load current config
        with open(self.xray_config_path, "r") as f:
            config = json.load(f)

        # Get healthy proxies
        healthy_proxies = [
            p for p in self.proxy_manager.proxies if p.status == ProxyStatus.HEALTHY
        ]

        if not healthy_proxies:
            logger.error("No healthy proxies for Xray integration")
            return

        # Generate outbounds for each proxy
        new_outbounds = []
        for proxy in healthy_proxies[:3]:  # Use top 3 proxies
            outbound = self.generate_xray_outbound(proxy)
            new_outbounds.append(outbound)

        # Add to config
        config["outbounds"] = [
            ob
            for ob in config.get("outbounds", [])
            if not ob.get("tag", "").startswith("residential-")
        ] + new_outbounds

        # Add routing rules for target domains
        routing_rules = config.get("routing", {}).get("rules", [])

        # Remove old residential rules
        routing_rules = [
            r
            for r in routing_rules
            if not r.get("outboundTag", "").startswith("residential-")
        ]

        # Add new rules
        for i, proxy in enumerate(healthy_proxies[:3]):
            rule = {
                "type": "field",
                "domain": target_domains,
                "outboundTag": f"residential-{proxy.id}",
            }
            routing_rules.insert(0, rule)  # High priority

        config["routing"]["rules"] = routing_rules

        # Save config
        with open(self.xray_config_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(
            f"Updated Xray config with {len(new_outbounds)} residential outbounds"
        )


# Pre-configured proxy pools for common providers
PROXY_POOL_CONFIGS = {
    "oxylabs": {
        "host_template": "pr.oxylabs.io",
        "port": 7777,
        "regions": ["us", "uk", "de", "fr", "jp"],
    },
    "brightdata": {
        "host_template": "brd.superproxy.io",
        "port": 22225,
        "regions": ["us", "eu", "asia"],
    },
    "smartproxy": {
        "host_template": "gate.smartproxy.com",
        "port": 7000,
        "regions": ["us", "gb", "de", "jp"],
    },
}


def create_proxy_pool_from_provider(
    provider: str, username: str, password: str, regions: Optional[List[str]] = None
) -> List[ProxyEndpoint]:
    """
    Create proxy pool from a residential proxy provider.

    Args:
        provider: Provider name (oxylabs, brightdata, smartproxy)
        username: API username
        password: API password
        regions: Specific regions to use

    Returns:
        List of proxy endpoints
    """
    if provider not in PROXY_POOL_CONFIGS:
        raise ValueError(f"Unknown provider: {provider}")

    config = PROXY_POOL_CONFIGS[provider]
    target_regions = regions or config["regions"]

    proxies = []
    for region in target_regions:
        proxy = ProxyEndpoint(
            id=f"{provider}-{region}",
            host=config["host_template"],
            port=config["port"],
            username=username,
            password=password,
            region=region,
            country_code=region.upper() if len(region) == 2 else "US",
        )
        proxies.append(proxy)

    return proxies
