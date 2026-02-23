"""Unit tests for src.llm.rate_limiter."""

from __future__ import annotations

import time

import pytest

from src.llm.rate_limiter import (
    MultiProviderRateLimiter,
    RateLimitConfig,
    RateLimiter,
    RateLimitStrategy,
)


def test_token_bucket_acquire_and_nonblocking_limit():
    cfg = RateLimitConfig(
        requests_per_minute=1,
        tokens_per_minute=10,
        burst_size=1,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
    )
    limiter = RateLimiter(cfg)

    assert limiter.acquire(tokens=1, blocking=False) is True
    assert limiter.acquire(tokens=1, blocking=False) is False

    stats = limiter.get_stats()
    assert stats["total_requests"] == 1
    assert stats["total_limited"] >= 1


def test_sliding_window_limit_blocks_second_request():
    cfg = RateLimitConfig(
        requests_per_minute=1,
        tokens_per_minute=10,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
    )
    limiter = RateLimiter(cfg)

    assert limiter.acquire(tokens=1, blocking=False) is True
    assert limiter.acquire(tokens=1, blocking=False) is False


def test_get_wait_time_and_backoff_reset():
    cfg = RateLimitConfig(
        requests_per_minute=60,
        tokens_per_minute=60,
        burst_size=1,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
    )
    limiter = RateLimiter(cfg)
    limiter._state.available_requests = 0
    limiter._state.available_tokens = 0.0

    wait = limiter.get_wait_time(tokens=10)
    assert wait > 0.0

    limiter._state.current_backoff = 5.0
    limiter.reset_backoff()
    assert limiter.get_stats()["current_backoff"] == 0.0


def test_reset_restores_initial_capacity():
    cfg = RateLimitConfig(requests_per_minute=120, tokens_per_minute=240, burst_size=3)
    limiter = RateLimiter(cfg)
    limiter.acquire(tokens=10, blocking=False)
    limiter.reset()
    stats = limiter.get_stats()
    assert stats["available_requests"] == 3
    assert stats["available_tokens"] == 240.0


def test_multiprovider_register_acquire_wait_and_stats():
    m = MultiProviderRateLimiter()
    cfg = RateLimitConfig(requests_per_minute=1, tokens_per_minute=10, burst_size=1)
    m.register("ollama", cfg)

    assert m.acquire("ollama", tokens=1, blocking=False) is True
    assert m.acquire("ollama", tokens=1, blocking=False) is False

    # Unknown provider: no limiter configured, so allowed with zero wait.
    assert m.acquire("unknown", tokens=1, blocking=False) is True
    assert m.get_wait_time("unknown", tokens=1) == 0.0

    stats = m.get_all_stats()
    assert "ollama" in stats
    assert stats["ollama"]["total_requests"] == 1


def test_acquire_rejects_non_positive_tokens():
    limiter = RateLimiter(RateLimitConfig())
    with pytest.raises(ValueError, match="tokens must be > 0"):
        limiter.acquire(tokens=0, blocking=False)
    with pytest.raises(ValueError, match="tokens must be > 0"):
        limiter.acquire(tokens=-1, blocking=False)


def test_get_wait_time_handles_zero_token_refill_rate():
    cfg = RateLimitConfig(
        requests_per_minute=60,
        tokens_per_minute=0,
        burst_size=1,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
    )
    limiter = RateLimiter(cfg)
    limiter._state.available_requests = 0
    limiter._state.available_tokens = 0.0

    wait = limiter.get_wait_time(tokens=1)
    assert wait == float("inf")
