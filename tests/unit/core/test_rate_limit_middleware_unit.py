import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""Unit tests for src/core/rate_limit_middleware.py"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rate_limit_middleware import (InMemoryRateLimiter,
                                            RateLimitConfig,
                                            RateLimitMiddleware, TokenBucket,
                                            default_config)

# ============================================================================
# RateLimitConfig tests
# ============================================================================


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self):
        config = RateLimitConfig()
        assert config.requests_per_second == 100
        assert config.requests_per_minute == 1000
        assert config.burst_size == 50
        assert config.block_duration == 60

    def test_custom_values(self):
        config = RateLimitConfig(
            requests_per_second=10,
            requests_per_minute=200,
            burst_size=5,
            block_duration=120,
        )
        assert config.requests_per_second == 10
        assert config.requests_per_minute == 200
        assert config.burst_size == 5
        assert config.block_duration == 120

    def test_default_config_module_level(self):
        """Module-level default_config should have expected values."""
        assert default_config.requests_per_second == 100
        assert default_config.burst_size == 50
        assert default_config.block_duration == 60


# ============================================================================
# TokenBucket tests
# ============================================================================


class TestTokenBucket:
    """Tests for TokenBucket async rate limiter."""

    @pytest.mark.asyncio
    async def test_initial_capacity(self):
        bucket = TokenBucket(rate=10.0, capacity=5)
        assert bucket.rate == 10.0
        assert bucket.capacity == 5
        assert bucket.tokens == 5

    @pytest.mark.asyncio
    async def test_consume_single_token(self):
        bucket = TokenBucket(rate=10.0, capacity=5)
        result = await bucket.consume(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_consume_all_tokens(self):
        bucket = TokenBucket(rate=10.0, capacity=3)
        # Consume all 3 tokens one at a time
        assert await bucket.consume(1) is True
        assert await bucket.consume(1) is True
        assert await bucket.consume(1) is True

    @pytest.mark.asyncio
    async def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(rate=10.0, capacity=3)
        # Consume all tokens
        await bucket.consume(3)
        # Next consume should fail (no time for refill within same instant)
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = bucket.last_update  # no time elapsed
            result = await bucket.consume(1)
            assert result is False

    @pytest.mark.asyncio
    async def test_consume_multiple_tokens_at_once(self):
        bucket = TokenBucket(rate=10.0, capacity=5)
        result = await bucket.consume(5)
        assert result is True

    @pytest.mark.asyncio
    async def test_consume_too_many_tokens_at_once(self):
        bucket = TokenBucket(rate=10.0, capacity=5)
        result = await bucket.consume(6)
        assert result is False

    @pytest.mark.asyncio
    async def test_token_refill_over_time(self):
        """Tokens refill based on elapsed time and rate."""
        base_time = 1000.0
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            bucket = TokenBucket(rate=10.0, capacity=5)

            # Consume all tokens
            mock_time.time.return_value = base_time
            result = await bucket.consume(5)
            assert result is True

            # No time passes: should fail
            mock_time.time.return_value = base_time
            result = await bucket.consume(1)
            assert result is False

            # 0.5 seconds pass: rate=10 => 5 tokens refilled
            mock_time.time.return_value = base_time + 0.5
            result = await bucket.consume(5)
            assert result is True

    @pytest.mark.asyncio
    async def test_tokens_capped_at_capacity(self):
        """Tokens should not exceed capacity even after long time."""
        base_time = 1000.0
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            bucket = TokenBucket(rate=100.0, capacity=5)

            # Consume 1 token
            await bucket.consume(1)

            # Wait a very long time (100s * 100 rate = 10000 potential tokens)
            mock_time.time.return_value = base_time + 100.0
            result = await bucket.consume(5)
            assert result is True

            # But not 6 (capacity is 5)
            mock_time.time.return_value = base_time + 200.0
            result = await bucket.consume(6)
            assert result is False

    @pytest.mark.asyncio
    async def test_available_tokens_property(self):
        base_time = 1000.0
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            bucket = TokenBucket(rate=10.0, capacity=5)
            assert bucket.available_tokens == 5.0

    @pytest.mark.asyncio
    async def test_available_tokens_after_consume(self):
        base_time = 1000.0
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            bucket = TokenBucket(rate=10.0, capacity=5)

            await bucket.consume(3)

            # available_tokens reads time.time() directly (no lock)
            mock_time.time.return_value = base_time
            # After consuming 3, last_update was set to base_time, tokens=2
            # available_tokens = min(5, 2 + 0 * 10) = 2
            assert bucket.available_tokens == pytest.approx(2.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_available_tokens_with_elapsed_time(self):
        base_time = 1000.0
        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            bucket = TokenBucket(rate=10.0, capacity=5)

            await bucket.consume(5)

            # 0.3 seconds later: 3 tokens refilled
            mock_time.time.return_value = base_time + 0.3
            assert bucket.available_tokens == pytest.approx(3.0, abs=0.1)


# ============================================================================
# InMemoryRateLimiter tests
# ============================================================================


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    @pytest.mark.asyncio
    async def test_is_allowed_new_ip(self):
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        limiter = InMemoryRateLimiter(config)
        allowed, retry_after = await limiter.is_allowed("1.2.3.4")
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_is_allowed_creates_bucket(self):
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        limiter = InMemoryRateLimiter(config)
        await limiter.is_allowed("1.2.3.4")
        assert "1.2.3.4" in limiter._buckets

    @pytest.mark.asyncio
    async def test_is_allowed_blocks_after_burst_exceeded(self):
        """After burst tokens are exhausted, IP gets blocked."""
        base_time = 1000.0
        config = RateLimitConfig(
            requests_per_second=10, burst_size=2, block_duration=30
        )
        limiter = InMemoryRateLimiter(config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time

            # First two requests consume the 2-token burst
            allowed1, _ = await limiter.is_allowed("1.2.3.4")
            assert allowed1 is True
            allowed2, _ = await limiter.is_allowed("1.2.3.4")
            assert allowed2 is True

            # Third request: no tokens left, should block
            allowed3, retry_after = await limiter.is_allowed("1.2.3.4")
            assert allowed3 is False
            assert retry_after == 30

    @pytest.mark.asyncio
    async def test_blocked_ip_returns_retry_after(self):
        base_time = 1000.0
        config = RateLimitConfig(
            requests_per_second=10, burst_size=1, block_duration=60
        )
        limiter = InMemoryRateLimiter(config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time

            # Consume the single token
            await limiter.is_allowed("5.5.5.5")
            # Trigger block
            await limiter.is_allowed("5.5.5.5")

            # 10 seconds later, still blocked
            mock_time.time.return_value = base_time + 10
            allowed, retry_after = await limiter.is_allowed("5.5.5.5")
            assert allowed is False
            assert retry_after == 50  # 60 - 10

    @pytest.mark.asyncio
    async def test_blocked_ip_unblocked_after_duration(self):
        base_time = 1000.0
        config = RateLimitConfig(
            requests_per_second=10, burst_size=1, block_duration=30
        )
        limiter = InMemoryRateLimiter(config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time

            # Trigger block
            await limiter.is_allowed("9.9.9.9")
            await limiter.is_allowed("9.9.9.9")

            # Block expires after 30s
            mock_time.time.return_value = base_time + 31
            allowed, retry_after = await limiter.is_allowed("9.9.9.9")
            assert allowed is True
            assert retry_after is None

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        config = RateLimitConfig(requests_per_second=10, burst_size=2)
        limiter = InMemoryRateLimiter(config)

        allowed_a, _ = await limiter.is_allowed("1.1.1.1")
        allowed_b, _ = await limiter.is_allowed("2.2.2.2")
        assert allowed_a is True
        assert allowed_b is True

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        config = RateLimitConfig(
            requests_per_second=50, burst_size=10, block_duration=45
        )
        limiter = InMemoryRateLimiter(config)
        stats = limiter.get_stats()
        assert stats["active_buckets"] == 0
        assert stats["blocked_ips"] == 0
        assert stats["config"]["requests_per_second"] == 50
        assert stats["config"]["burst_size"] == 10
        assert stats["config"]["block_duration"] == 45

    @pytest.mark.asyncio
    async def test_get_stats_with_activity(self):
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        limiter = InMemoryRateLimiter(config)
        await limiter.is_allowed("1.1.1.1")
        await limiter.is_allowed("2.2.2.2")
        stats = limiter.get_stats()
        assert stats["active_buckets"] == 2
        assert stats["blocked_ips"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_blocks(self):
        base_time = 1000.0
        config = RateLimitConfig(
            requests_per_second=10, burst_size=1, block_duration=30
        )
        limiter = InMemoryRateLimiter(config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time

            # Trigger block
            await limiter.is_allowed("7.7.7.7")
            await limiter.is_allowed("7.7.7.7")
            assert len(limiter._blocked) == 1

            # Cleanup after block expires
            mock_time.time.return_value = base_time + 31
            await limiter._cleanup()
            assert len(limiter._blocked) == 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_inactive_buckets(self):
        base_time = 1000.0
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        limiter = InMemoryRateLimiter(config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time
            await limiter.is_allowed("3.3.3.3")
            assert len(limiter._buckets) == 1

            # 5+ minutes of inactivity
            mock_time.time.return_value = base_time + 301
            await limiter._cleanup()
            assert len(limiter._buckets) == 0

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self):
        config = RateLimitConfig()
        limiter = InMemoryRateLimiter(config)
        assert limiter._cleanup_task is None

        await limiter.start()
        assert limiter._cleanup_task is not None
        assert not limiter._cleanup_task.done()

        await limiter.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanup_task(self):
        config = RateLimitConfig()
        limiter = InMemoryRateLimiter(config)
        await limiter.start()
        task = limiter._cleanup_task
        await limiter.stop()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Stopping without starting should be safe (no-op)."""
        config = RateLimitConfig()
        limiter = InMemoryRateLimiter(config)
        await limiter.stop()  # should not raise


# ============================================================================
# RateLimitMiddleware tests
# ============================================================================


def _make_request(path="/api/test", client_ip="10.0.0.1", headers=None):
    """Helper to create a mock Request object."""
    request = MagicMock(spec=["url", "headers", "client"])
    request.url = MagicMock()
    request.url.path = path
    request.headers = headers or {}
    request.client = MagicMock()
    request.client.host = client_ip
    return request


class TestGetClientIp:
    """Tests for _get_client_ip IP extraction."""

    def _make_middleware(self):
        app = MagicMock()
        return RateLimitMiddleware(app)

    def test_ip_from_x_forwarded_for(self):
        mw = self._make_middleware()
        request = _make_request(headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18"})
        assert mw._get_client_ip(request) == "203.0.113.50"

    def test_ip_from_x_forwarded_for_single(self):
        mw = self._make_middleware()
        request = _make_request(headers={"X-Forwarded-For": "1.2.3.4"})
        assert mw._get_client_ip(request) == "1.2.3.4"

    def test_ip_from_x_real_ip(self):
        mw = self._make_middleware()
        request = _make_request(headers={"X-Real-IP": "192.168.1.100"})
        assert mw._get_client_ip(request) == "192.168.1.100"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        mw = self._make_middleware()
        request = _make_request(
            headers={"X-Forwarded-For": "5.5.5.5", "X-Real-IP": "6.6.6.6"}
        )
        assert mw._get_client_ip(request) == "5.5.5.5"

    def test_ip_from_client_host(self):
        mw = self._make_middleware()
        request = _make_request(client_ip="192.168.0.1", headers={})
        assert mw._get_client_ip(request) == "192.168.0.1"

    def test_ip_fallback_unknown_when_no_client(self):
        mw = self._make_middleware()
        request = _make_request(headers={})
        request.client = None
        assert mw._get_client_ip(request) == "unknown"

    def test_ip_strips_whitespace_from_x_forwarded_for(self):
        mw = self._make_middleware()
        request = _make_request(headers={"X-Forwarded-For": "  8.8.8.8 , 9.9.9.9"})
        assert mw._get_client_ip(request) == "8.8.8.8"


class TestRateLimitMiddlewareDispatch:
    """Tests for middleware dispatch method."""

    @pytest.mark.asyncio
    async def test_excluded_path_health(self):
        """Requests to /health bypass rate limiting."""
        app = MagicMock()
        mw = RateLimitMiddleware(app, excluded_paths=["/health", "/metrics"])
        request = _make_request(path="/health")

        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        response = await mw.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert response is expected_response

    @pytest.mark.asyncio
    async def test_excluded_path_metrics(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, excluded_paths=["/health", "/metrics"])
        request = _make_request(path="/metrics")

        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        response = await mw.dispatch(request, call_next)
        assert response is expected_response

    @pytest.mark.asyncio
    async def test_excluded_path_prefix_match(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, excluded_paths=["/health"])
        request = _make_request(path="/health/live")

        call_next = AsyncMock(return_value=MagicMock())
        response = await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_allowed_request_returns_response_with_headers(self):
        app = MagicMock()
        config = RateLimitConfig(requests_per_second=100, burst_size=50)
        mw = RateLimitMiddleware(app, config=config)

        request = _make_request(path="/api/data", client_ip="10.0.0.1")
        inner_response = MagicMock()
        inner_response.headers = {}
        call_next = AsyncMock(return_value=inner_response)

        response = await mw.dispatch(request, call_next)
        assert response is inner_response
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in response.headers

    @pytest.mark.asyncio
    async def test_blocked_request_returns_429(self):
        """When rate limit exceeded, returns 429 with Retry-After."""
        app = MagicMock()
        base_time = 1000.0
        config = RateLimitConfig(
            requests_per_second=10, burst_size=1, block_duration=60
        )
        mw = RateLimitMiddleware(app, config=config)

        with patch("src.core.rate_limit_middleware.time") as mock_time:
            mock_time.time.return_value = base_time

            call_next = AsyncMock(return_value=MagicMock())

            # First request: allowed (consumes the 1 burst token)
            request1 = _make_request(path="/api/data", client_ip="10.0.0.1")
            inner_resp = MagicMock()
            inner_resp.headers = {}
            call_next.return_value = inner_resp
            resp1 = await mw.dispatch(request1, call_next)
            assert resp1 is inner_resp

            # Second request: blocked
            request2 = _make_request(path="/api/data", client_ip="10.0.0.1")
            resp2 = await mw.dispatch(request2, call_next)
            assert resp2.status_code == 429
            assert resp2.headers["Retry-After"] == "60"

    @pytest.mark.asyncio
    async def test_starts_limiter_on_first_request(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app)
        assert mw._started is False

        request = _make_request(path="/api/test")
        inner_response = MagicMock()
        inner_response.headers = {}
        call_next = AsyncMock(return_value=inner_response)

        await mw.dispatch(request, call_next)
        assert mw._started is True

        # Cleanup
        await mw.limiter.stop()

    @pytest.mark.asyncio
    async def test_does_not_restart_limiter(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app)
        request = _make_request(path="/api/test")
        inner_response = MagicMock()
        inner_response.headers = {}
        call_next = AsyncMock(return_value=inner_response)

        await mw.dispatch(request, call_next)

        with patch.object(mw.limiter, "start", new_callable=AsyncMock) as mock_start:
            await mw.dispatch(request, call_next)
            mock_start.assert_not_awaited()

        await mw.limiter.stop()

    @pytest.mark.asyncio
    async def test_custom_excluded_paths(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, excluded_paths=["/status", "/ping"])
        request = _make_request(path="/status")
        call_next = AsyncMock(return_value=MagicMock())

        await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()

    def test_default_excluded_paths(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app)
        assert mw.excluded_paths == ["/health", "/metrics"]


class TestRateLimitMiddlewareEnvOverrides:
    """Tests for environment variable configuration overrides."""

    def test_env_override_rps(self):
        app = MagicMock()
        with patch.dict(os.environ, {"RATE_LIMIT_RPS": "42"}):
            mw = RateLimitMiddleware(app)
            assert mw.config.requests_per_second == 42

    def test_env_override_burst(self):
        app = MagicMock()
        with patch.dict(os.environ, {"RATE_LIMIT_BURST": "25"}):
            mw = RateLimitMiddleware(app)
            assert mw.config.burst_size == 25

    def test_env_override_both(self):
        app = MagicMock()
        with patch.dict(
            os.environ, {"RATE_LIMIT_RPS": "200", "RATE_LIMIT_BURST": "100"}
        ):
            mw = RateLimitMiddleware(app)
            assert mw.config.requests_per_second == 200
            assert mw.config.burst_size == 100

    def test_no_env_override_uses_defaults(self):
        app = MagicMock()
        with patch.dict(os.environ, {}, clear=False):
            # Remove keys if present
            os.environ.pop("RATE_LIMIT_RPS", None)
            os.environ.pop("RATE_LIMIT_BURST", None)
            mw = RateLimitMiddleware(app)
            assert mw.config.requests_per_second == 100
            assert mw.config.burst_size == 50

    def test_no_env_override_with_custom_config(self):
        app = MagicMock()
        config = RateLimitConfig(requests_per_second=5, burst_size=3)
        os.environ.pop("RATE_LIMIT_RPS", None)
        os.environ.pop("RATE_LIMIT_BURST", None)
        mw = RateLimitMiddleware(app, config=config)
        assert mw.config.requests_per_second == 5
        assert mw.config.burst_size == 3
