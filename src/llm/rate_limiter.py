"""
Rate Limiter for LLM API Calls
==============================

Token bucket and sliding window rate limiting for LLM providers.
Prevents API rate limit errors and manages costs.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategy."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    requests_per_day: Optional[int] = None
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    backoff_factor: float = 2.0
    max_backoff_seconds: float = 60.0
    retry_after_header: bool = True


@dataclass
class RateLimitState:
    """Current state of rate limiter."""
    available_tokens: float = 0.0
    available_requests: int = 0
    last_refill: float = 0.0
    request_timestamps: deque = field(default_factory=deque)
    token_timestamps: deque = field(default_factory=deque)
    current_backoff: float = 0.0
    last_limited: Optional[float] = None
    total_limited: int = 0
    total_requests: int = 0
    total_tokens: int = 0


class RateLimiter:
    """
    Rate limiter for LLM API calls.
    
    Features:
    - Token bucket algorithm
    - Sliding window rate limiting
    - Request and token limits
    - Automatic backoff
    - Thread-safe operations
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._state = RateLimitState(
            available_tokens=float(self.config.tokens_per_minute),
            available_requests=self.config.burst_size,
            last_refill=time.time(),
        )
        self._lock = threading.RLock()
        
    def _refill_token_bucket(self) -> None:
        """Refill tokens based on elapsed time (token bucket algorithm)."""
        now = time.time()
        elapsed = now - self._state.last_refill
        
        # Refill requests
        requests_per_second = self.config.requests_per_minute / 60.0
        new_requests = int(elapsed * requests_per_second)
        self._state.available_requests = min(
            self.config.burst_size,
            self._state.available_requests + new_requests,
        )
        
        # Refill tokens
        tokens_per_second = self.config.tokens_per_minute / 60.0
        new_tokens = elapsed * tokens_per_second
        self._state.available_tokens = min(
            float(self.config.tokens_per_minute),
            self._state.available_tokens + new_tokens,
        )
        
        self._state.last_refill = now
    
    def _check_sliding_window(self, window_seconds: float = 60.0) -> int:
        """Count requests in sliding window."""
        now = time.time()
        cutoff = now - window_seconds
        
        # Remove old timestamps
        while (
            self._state.request_timestamps and 
            self._state.request_timestamps[0] < cutoff
        ):
            self._state.request_timestamps.popleft()
        
        return len(self._state.request_timestamps)
    
    def _check_token_window(self, window_seconds: float = 60.0) -> int:
        """Count tokens in sliding window."""
        now = time.time()
        cutoff = now - window_seconds
        
        # Remove old entries and count tokens
        total_tokens = 0
        valid_entries = deque()
        
        for timestamp, tokens in self._state.token_timestamps:
            if timestamp >= cutoff:
                valid_entries.append((timestamp, tokens))
                total_tokens += tokens
        
        self._state.token_timestamps = valid_entries
        return total_tokens
    
    def acquire(
        self,
        tokens: int = 1,
        blocking: bool = True,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire permission to make a request.
        
        Args:
            tokens: Number of tokens needed
            blocking: Whether to block until available
            timeout: Maximum time to wait (seconds)
            
        Returns:
            True if permission granted, False otherwise
        """
        if tokens <= 0:
            raise ValueError("tokens must be > 0")

        start_time = time.time()
        
        while True:
            with self._lock:
                if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                    self._refill_token_bucket()
                    
                    if (
                        self._state.available_requests > 0 and
                        self._state.available_tokens >= tokens
                    ):
                        self._state.available_requests -= 1
                        self._state.available_tokens -= tokens
                        self._state.total_requests += 1
                        self._state.total_tokens += tokens
                        return True
                        
                elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                    request_count = self._check_sliding_window()
                    token_count = self._check_token_window()
                    
                    if (
                        request_count < self.config.requests_per_minute and
                        token_count + tokens <= self.config.tokens_per_minute
                    ):
                        now = time.time()
                        self._state.request_timestamps.append(now)
                        self._state.token_timestamps.append((now, tokens))
                        self._state.total_requests += 1
                        self._state.total_tokens += tokens
                        return True
                        
                else:  # FIXED_WINDOW
                    # Simple minute-based window
                    current_minute = int(time.time() / 60)
                    if not hasattr(self, "_current_window"):
                        self._current_window = current_minute
                        self._window_requests = 0
                        self._window_tokens = 0
                    
                    if current_minute != self._current_window:
                        self._current_window = current_minute
                        self._window_requests = 0
                        self._window_tokens = 0
                    
                    if (
                        self._window_requests < self.config.requests_per_minute and
                        self._window_tokens + tokens <= self.config.tokens_per_minute
                    ):
                        self._window_requests += 1
                        self._window_tokens += tokens
                        self._state.total_requests += 1
                        self._state.total_tokens += tokens
                        return True
                
                # Rate limited
                self._state.total_limited += 1
                self._state.last_limited = time.time()
                
                # Calculate backoff
                if self._state.current_backoff == 0:
                    self._state.current_backoff = 1.0
                else:
                    self._state.current_backoff = min(
                        self._state.current_backoff * self.config.backoff_factor,
                        self.config.max_backoff_seconds,
                    )
            
            if not blocking:
                return False
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                wait_time = min(
                    self._state.current_backoff,
                    timeout - elapsed,
                )
            else:
                wait_time = self._state.current_backoff
            
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            time.sleep(wait_time)
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get estimated wait time before request can be made.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Estimated wait time in seconds (0 if no wait needed)
        """
        if tokens <= 0:
            raise ValueError("tokens must be > 0")

        with self._lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                self._refill_token_bucket()
                
                if (
                    self._state.available_requests > 0 and
                    self._state.available_tokens >= tokens
                ):
                    return 0.0
                
                # Calculate time to refill enough tokens
                tokens_needed = tokens - self._state.available_tokens
                tokens_per_second = self.config.tokens_per_minute / 60.0
                if tokens_per_second <= 0:
                    return float("inf") if tokens_needed > 0 else 0.0
                return max(0, tokens_needed / tokens_per_second)
                
            else:  # SLIDING_WINDOW or FIXED_WINDOW
                request_count = self._check_sliding_window()
                
                if request_count < self.config.requests_per_minute:
                    return 0.0
                
                # Time until oldest request exits window
                if self._state.request_timestamps:
                    oldest = self._state.request_timestamps[0]
                    return max(0, 60.0 - (time.time() - oldest))
                
                return 0.0
    
    def reset_backoff(self) -> None:
        """Reset backoff after successful request."""
        with self._lock:
            self._state.current_backoff = 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                "strategy": self.config.strategy.value,
                "requests_per_minute": self.config.requests_per_minute,
                "tokens_per_minute": self.config.tokens_per_minute,
                "total_requests": self._state.total_requests,
                "total_tokens": self._state.total_tokens,
                "total_limited": self._state.total_limited,
                "current_backoff": self._state.current_backoff,
                "available_requests": self._state.available_requests,
                "available_tokens": self._state.available_tokens,
                "last_limited": (
                    datetime.fromtimestamp(
                        self._state.last_limited, tz=timezone.utc
                    ).isoformat()
                    if self._state.last_limited else None
                ),
            }
    
    def reset(self) -> None:
        """Reset rate limiter state."""
        with self._lock:
            self._state = RateLimitState(
                available_tokens=float(self.config.tokens_per_minute),
                available_requests=self.config.burst_size,
                last_refill=time.time(),
            )


class MultiProviderRateLimiter:
    """
    Rate limiter that manages multiple providers.
    
    Each provider can have its own rate limits.
    """
    
    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.RLock()
    
    def register(
        self,
        provider: str,
        config: Optional[RateLimitConfig] = None,
    ) -> None:
        """Register a provider with rate limit config."""
        with self._lock:
            self._limiters[provider] = RateLimiter(config)
    
    def acquire(
        self,
        provider: str,
        tokens: int = 1,
        blocking: bool = True,
        timeout: Optional[float] = None,
    ) -> bool:
        """Acquire permission for a provider."""
        with self._lock:
            limiter = self._limiters.get(provider)
            if not limiter:
                return True  # No limit configured
            return limiter.acquire(tokens, blocking, timeout)
    
    def get_wait_time(self, provider: str, tokens: int = 1) -> float:
        """Get wait time for a provider."""
        with self._lock:
            limiter = self._limiters.get(provider)
            if not limiter:
                return 0.0
            return limiter.get_wait_time(tokens)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers."""
        with self._lock:
            return {
                provider: limiter.get_stats()
                for provider, limiter in self._limiters.items()
            }


__all__ = [
    "RateLimitStrategy",
    "RateLimitConfig",
    "RateLimiter",
    "MultiProviderRateLimiter",
]
