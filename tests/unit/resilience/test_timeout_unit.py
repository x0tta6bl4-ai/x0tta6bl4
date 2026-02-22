"""Unit tests for src.resilience.timeout."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.resilience.timeout import (
    CascadeTimeout,
    TimeoutConfig,
    TimeoutContext,
    TimeoutError,
    TimeoutPattern,
)


def test_calculate_timeout_with_cascade_depth():
    pattern = TimeoutPattern(TimeoutConfig(cascade_timeout_multiplier=0.5))
    pattern._set_cascade_depth(0)
    assert pattern._calculate_timeout(10.0) == 10.0

    pattern._set_cascade_depth(1)
    assert pattern._calculate_timeout(10.0) == 5.0

    pattern._set_cascade_depth(4)
    assert pattern._calculate_timeout(0.1) == 1.0  # minimum clamp


def test_calculate_timeout_raises_on_max_depth():
    pattern = TimeoutPattern(TimeoutConfig(max_cascade_depth=2))
    pattern._set_cascade_depth(2)
    with pytest.raises(CascadeTimeout):
        pattern._calculate_timeout(5.0)


def test_execute_success_and_stats():
    pattern = TimeoutPattern(TimeoutConfig(default_timeout=1.0))
    result = pattern.execute(lambda x: x + 1, operation="add", timeout=0.5, x=2)
    assert result == 3

    stats = pattern.get_stats()["add"]
    assert stats["total_calls"] == 1
    assert stats["timeouts"] == 0
    assert stats["timeout_rate"] == 0.0


def test_execute_timeout_without_fallback_raises():
    pattern = TimeoutPattern(TimeoutConfig(default_timeout=0.01))
    pattern._calculate_timeout = lambda _base: 0.01

    def _slow():
        time.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError):
        pattern.execute(_slow, operation="slow-op", timeout=0.01)

    stats = pattern.get_stats()["slow-op"]
    assert stats["timeouts"] == 1


def test_execute_timeout_with_fallback_returns_value():
    cfg = TimeoutConfig(
        default_timeout=0.01,
        fallback_on_timeout=True,
        fallback_value="fallback",
    )
    pattern = TimeoutPattern(cfg)
    pattern._calculate_timeout = lambda _base: 0.01

    def _slow():
        time.sleep(0.05)
        return "late"

    assert pattern.execute(_slow, operation="slow-op", timeout=0.01) == "fallback"


@pytest.mark.asyncio
async def test_execute_async_timeout_and_fallback():
    cfg = TimeoutConfig(
        default_timeout=0.01,
        fallback_on_timeout=True,
        fallback_value={"status": "fallback"},
    )
    pattern = TimeoutPattern(cfg)
    pattern._calculate_timeout = lambda _base: 0.01

    async def _slow():
        await asyncio.sleep(0.05)
        return {"status": "late"}

    result = await pattern.execute_async(_slow, operation="async-op", timeout=0.01)
    assert result == {"status": "fallback"}


def test_timeout_context_tracks_remaining_and_callback():
    called = {"count": 0}
    ctx = TimeoutContext(timeout=0.01, on_timeout=lambda: called.__setitem__("count", called["count"] + 1))

    with ctx:
        time.sleep(0.02)

    assert ctx.elapsed > 0.0
    assert ctx.is_expired is True
    assert called["count"] == 1
