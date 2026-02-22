"""Unit tests for src/core/resilience_patterns.py."""

import asyncio
import time

import pytest

from src.core.resilience_patterns import (
    Bulkhead,
    CircuitBreaker,
    CircuitState,
    retry_with_jitter,
)


@pytest.mark.asyncio
async def test_circuit_breaker_returns_result_when_closed():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

    async def ok(value):
        return value

    result = await cb.call(ok, 42)
    assert result == 42
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

    async def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    with pytest.raises(RuntimeError):
        await cb.call(fail)

    assert cb.state == CircuitState.OPEN
    with pytest.raises(Exception, match="OPEN"):
        await cb.call(fail)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_then_closed_on_success():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    cb.state = CircuitState.OPEN
    cb.failure_count = 1
    cb.last_failure_time = time.time() - 5

    async def ok():
        return "ok"

    result = await cb.call(ok)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_bulkhead_limits_concurrency_to_one():
    bulkhead = Bulkhead(max_concurrent_calls=1)
    active = 0
    max_seen = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal active, max_seen
        async with lock:
            active += 1
            max_seen = max(max_seen, active)
        await asyncio.sleep(0.01)
        async with lock:
            active -= 1
        return "done"

    results = await asyncio.gather(
        bulkhead.call(worker),
        bulkhead.call(worker),
    )
    assert results == ["done", "done"]
    assert max_seen == 1


@pytest.mark.asyncio
async def test_retry_with_jitter_retries_and_then_succeeds(monkeypatch):
    attempts = {"count": 0}
    sleeps = []

    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("temporary")
        return "ok"

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("src.core.resilience_patterns.random.random", lambda: 0.0)
    monkeypatch.setattr("src.core.resilience_patterns.asyncio.sleep", fake_sleep)

    result = await retry_with_jitter(flaky, max_retries=4, initial_delay=1.0, max_delay=10.0)
    assert result == "ok"
    assert attempts["count"] == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_with_jitter_raises_after_max_retries(monkeypatch):
    attempts = {"count": 0}

    async def always_fail():
        attempts["count"] += 1
        raise RuntimeError("nope")

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("src.core.resilience_patterns.random.random", lambda: 0.0)
    monkeypatch.setattr("src.core.resilience_patterns.asyncio.sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="nope"):
        await retry_with_jitter(always_fail, max_retries=3, initial_delay=1.0, max_delay=10.0)
    assert attempts["count"] == 3

