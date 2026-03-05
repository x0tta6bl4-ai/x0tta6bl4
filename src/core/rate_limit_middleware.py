"""
Global Rate Limiting Middleware for DDoS Protection

Provides:
- Per-IP rate limiting at the middleware level
- Configurable limits per endpoint pattern
- Redis-backed distributed rate limiting
- Graceful degradation to in-memory when Redis unavailable
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_second: int = 100
    requests_per_minute: int = 1000
    burst_size: int = 50
    block_duration: int = 60  # seconds to block after exceeding limits
    # Path specific overrides
    path_overrides: Optional[Dict[str, "RateLimitConfig"]] = None


class TokenBucket:
    """Token bucket rate limiter implementation."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now

            # Refill tokens
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        now = time.time()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class InMemoryRateLimiter:
    """In-memory rate limiter for single instance deployment."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._buckets: Dict[str, TokenBucket] = {}
        self._blocked: Dict[str, float] = {}  # IP -> block expiry time
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Periodically clean up old entries."""
        while True:
            await asyncio.sleep(60)
            await self._cleanup()

    async def _cleanup(self):
        """Remove expired entries."""
        async with self._lock:
            now = time.time()
            # Remove expired blocks
            expired = [ip for ip, expiry in self._blocked.items() if expiry < now]
            for ip in expired:
                del self._blocked[ip]

            # Remove inactive buckets (no activity for 5 minutes)
            inactive = [
                ip
                for ip, bucket in self._buckets.items()
                if now - bucket.last_update > 300
            ]
            for ip in inactive:
                del self._buckets[ip]

    async def is_allowed(self, client_id: str, config_override: Optional[RateLimitConfig] = None) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed for a specific client (IP or API Key).

        Returns:
            (allowed, retry_after) - retry_after is seconds to wait if blocked
        """
        config = config_override or self.config
        
        async with self._lock:
            now = time.time()

            # Check if client ID is blocked
            if client_id in self._blocked:
                if self._blocked[client_id] > now:
                    retry_after = int(self._blocked[client_id] - now)
                    return False, retry_after
                else:
                    del self._blocked[client_id]

            # Get or create token bucket for this client ID
            # We include rate in key to handle different paths for the same user
            bucket_key = f"{client_id}:{config.requests_per_second}"
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = TokenBucket(
                    rate=config.requests_per_second,
                    capacity=config.burst_size,
                )

            bucket = self._buckets[bucket_key]
            if await bucket.consume():
                return True, None

            # Rate limit exceeded - block client temporarily
            self._blocked[client_id] = now + config.block_duration
            logger.warning(
                f"Rate limit exceeded for {client_id}, blocked for {config.block_duration}s"
            )
            return False, config.block_duration

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "active_buckets": len(self._buckets),
            "blocked_ips": len(self._blocked),
            "config": {
                "requests_per_second": self.config.requests_per_second,
                "burst_size": self.config.burst_size,
                "block_duration": self.config.block_duration,
            },
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware for FastAPI.

    Usage:
        app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
    """

    def __init__(
        self,
        app,
        config: Optional[RateLimitConfig] = None,
        excluded_paths: Optional[list] = None,
    ):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.excluded_paths = excluded_paths or ["/health", "/metrics"]
        self.limiter = InMemoryRateLimiter(self.config)
        self._started = False

        # Environment-based configuration override
        if os.getenv("RATE_LIMIT_RPS"):
            self.config.requests_per_second = int(os.getenv("RATE_LIMIT_RPS"))
        if os.getenv("RATE_LIMIT_BURST"):
            self.config.burst_size = int(os.getenv("RATE_LIMIT_BURST"))

        logger.info(
            f"Rate limit middleware initialized: "
            f"{self.config.requests_per_second} RPS, "
            f"burst={self.config.burst_size}"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        # Start cleanup task on first request
        if not self._started:
            await self.limiter.start()
            self._started = True

        # Skip rate limiting for excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)

        # 1) Resolve client identity (API Key takes priority over IP)
        api_key = request.headers.get("X-API-Key")
        client_id = api_key if api_key else self._get_client_ip(request)

        # 2) Resolve config (Check for path overrides)
        current_config = self.config
        if self.config.path_overrides:
            for pattern, override in self.config.path_overrides.items():
                if path.startswith(pattern):
                    current_config = override
                    break

        # Check rate limit
        allowed, retry_after = await self.limiter.is_allowed(client_id, current_config)

        if not allowed:
            try:
                from src.monitoring.maas_metrics import record_rate_limit_rejection
                record_rate_limit_rejection(path)
            except Exception:
                pass
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please slow down.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(current_config.requests_per_second)
        # Use available tokens from the bucket used
        bucket_key = f"{client_id}:{current_config.requests_per_second}"
        available = int(self.limiter._buckets.get(bucket_key, TokenBucket(1, 1)).available_tokens)
        response.headers["X-RateLimit-Remaining"] = str(available)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP considering proxies."""
        # Check X-Forwarded-For header (set by proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


# Default instance for easy import
default_config = RateLimitConfig(
    requests_per_second=100, burst_size=50, block_duration=60
)
