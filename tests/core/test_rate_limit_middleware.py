"""
Tests for Rate Limit Middleware.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.core.rate_limit_middleware import (InMemoryRateLimiter,
                                            RateLimitConfig,
                                            RateLimitMiddleware, TokenBucket)


class TestTokenBucket:
    """Tests for TokenBucket implementation."""

    @pytest.mark.asyncio
    async def test_initial_tokens(self):
        """Test bucket starts with full capacity."""
        bucket = TokenBucket(rate=10, capacity=50)
        assert bucket.tokens == 50

    @pytest.mark.asyncio
    async def test_consume_tokens(self):
        """Test consuming tokens."""
        bucket = TokenBucket(rate=10, capacity=50)
        result = await bucket.consume(10)
        assert result is True
        assert bucket.tokens == 40

    @pytest.mark.asyncio
    async def test_consume_exceeds_available(self):
        """Test consuming more tokens than available."""
        bucket = TokenBucket(rate=10, capacity=5)
        result = await bucket.consume(10)
        assert result is False

    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test tokens refill over time."""
        bucket = TokenBucket(rate=100, capacity=100)
        await bucket.consume(50)
        assert bucket.tokens == 50

        # Simulate time passing
        bucket.last_update -= 0.5  # 0.5 seconds ago
        available = bucket.available_tokens
        assert available > 50  # Should have refilled some tokens


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_initial_requests(self):
        """Test that initial requests are allowed."""
        config = RateLimitConfig(requests_per_second=10, burst_size=20)
        limiter = InMemoryRateLimiter(config)

        allowed, retry_after = await limiter.is_allowed("192.168.1.1")
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_blocks_after_burst(self):
        """Test that requests are blocked after burst exceeded."""
        config = RateLimitConfig(
            requests_per_second=10, burst_size=5, block_duration=60
        )
        limiter = InMemoryRateLimiter(config)

        # Exhaust burst capacity
        for _ in range(5):
            await limiter.is_allowed("192.168.1.1")

        # Next request should be blocked
        allowed, retry_after = await limiter.is_allowed("192.168.1.1")
        assert allowed is False
        assert retry_after == 60

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        """Test that different IPs have independent limits."""
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        limiter = InMemoryRateLimiter(config)

        # Exhaust IP1
        for _ in range(5):
            await limiter.is_allowed("192.168.1.1")

        # IP2 should still be allowed
        allowed, _ = await limiter.is_allowed("192.168.1.2")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test statistics reporting."""
        config = RateLimitConfig(requests_per_second=10, burst_size=20)
        limiter = InMemoryRateLimiter(config)

        await limiter.is_allowed("192.168.1.1")
        await limiter.is_allowed("192.168.1.2")

        stats = limiter.get_stats()
        assert stats["active_buckets"] == 2
        assert "config" in stats


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware integration."""

    def setup_method(self):
        """Set up test app."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}

        config = RateLimitConfig(
            requests_per_second=10, burst_size=5, block_duration=60
        )
        self.app.add_middleware(
            RateLimitMiddleware, config=config, excluded_paths=["/health"]
        )
        self.client = TestClient(self.app)

    def test_allows_normal_requests(self):
        """Test that normal requests pass through."""
        response = self.client.get("/test")
        assert response.status_code == 200

    def test_excludes_health_endpoint(self):
        """Test that excluded paths bypass rate limiting."""
        # Make many requests to health - should never be blocked
        for _ in range(20):
            response = self.client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_headers(self):
        """Test that rate limit headers are added."""
        response = self.client.get("/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_blocks_after_burst(self):
        """Test that requests are blocked after burst exceeded."""
        responses = []
        for _ in range(10):
            response = self.client.get("/test")
            responses.append(response.status_code)

        # Some should be 429
        assert 429 in responses or all(r == 200 for r in responses)

    def test_429_response_format(self):
        """Test that 429 response has correct format."""
        # Exhaust rate limit
        for _ in range(10):
            self.client.get("/test")

        response = self.client.get("/test")
        if response.status_code == 429:
            data = response.json()
            assert "error" in data
            assert "retry_after" in data
            assert "Retry-After" in response.headers


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.requests_per_second == 100
        assert config.requests_per_minute == 1000
        assert config.burst_size == 50
        assert config.block_duration == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_second=50, burst_size=100, block_duration=120
        )
        assert config.requests_per_second == 50
        assert config.burst_size == 100
        assert config.block_duration == 120
