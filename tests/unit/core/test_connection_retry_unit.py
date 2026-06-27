"""Unit tests for core connection retry utilities."""

from unittest.mock import AsyncMock

import pytest

from src.core.connection_retry import (ConnectionPool, RetryExhausted,
                                       RetryPolicy, retry, with_retry)
from src.core.circuit_breaker import CircuitBreakerOpen


def test_retry_policy_calculate_delay_without_jitter():
    policy = RetryPolicy(
        base_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False
    )
    assert policy.calculate_delay(0) == 1.0
    assert policy.calculate_delay(1) == 2.0
    assert policy.calculate_delay(4) == 10.0


def test_retry_policy_calculate_delay_with_jitter(monkeypatch):
    policy = RetryPolicy(
        base_delay=1.0,
        exponential_base=2.0,
        max_delay=10.0,
        jitter=True,
        jitter_max=0.5,
    )
    monkeypatch.setattr("src.core.connection_retry.random.uniform", lambda _a, _b: 0.25)
    assert policy.calculate_delay(2) == 4.25


@pytest.mark.asyncio
async def test_with_retry_retries_then_succeeds():
    fn = AsyncMock(side_effect=[ConnectionError("tmp"), "ok"])
    policy = RetryPolicy(
        max_retries=2,
        base_delay=0.001,
        jitter=False,
        retryable_exceptions=(ConnectionError,),
    )

    result = await with_retry(fn, policy=policy)

    assert result == "ok"
    assert fn.call_count == 2


@pytest.mark.asyncio
async def test_with_retry_raises_retry_exhausted():
    fn = AsyncMock(side_effect=ConnectionError("boom"))
    policy = RetryPolicy(
        max_retries=1,
        base_delay=0.001,
        jitter=False,
        retryable_exceptions=(ConnectionError,),
    )

    with pytest.raises(RetryExhausted):
        await with_retry(fn, policy=policy)


@pytest.mark.asyncio
async def test_connection_pool_reuses_released_connection():
    factory = AsyncMock(return_value="conn-1")
    pool = ConnectionPool(
        factory, max_size=2, retry_policy=RetryPolicy(max_retries=0, jitter=False)
    )

    conn1 = await pool.acquire()
    await pool.release(conn1)
    factory.reset_mock()
    conn2 = await pool.acquire()

    assert conn2 == "conn-1"
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_connection_pool_close_all_closes_and_clears():
    factory = AsyncMock(return_value="unused")
    pool = ConnectionPool(factory, max_size=2, retry_policy=RetryPolicy(max_retries=0))

    class _ConnWithClose:
        def __init__(self):
            self.close = AsyncMock()

    conn_with_close = _ConnWithClose()
    conn_without_close = object()
    pool._pool = [conn_with_close, conn_without_close]

    await pool.close_all()

    conn_with_close.close.assert_awaited_once()
    assert pool._pool == []


@pytest.mark.asyncio
async def test_with_retry_uses_default_policy_when_not_provided():
    fn = AsyncMock(return_value="ok")

    result = await with_retry(fn)

    assert result == "ok"
    fn.assert_called_once_with()


@pytest.mark.asyncio
async def test_with_retry_uses_circuit_breaker_call_path():
    fn = AsyncMock(return_value="direct-value")
    calls = {"count": 0}

    class _CircuitBreaker:
        async def call(self, func, *args, **kwargs):
            calls["count"] += 1
            return await func(*args, **kwargs)

    result = await with_retry(fn, "arg", circuit_breaker=_CircuitBreaker())

    assert result == "direct-value"
    assert calls["count"] == 1
    fn.assert_called_once_with("arg")


@pytest.mark.asyncio
async def test_with_retry_reraises_circuit_breaker_open():
    fn = AsyncMock(return_value="never")

    class _OpenCircuitBreaker:
        async def call(self, func, *args, **kwargs):
            raise CircuitBreakerOpen("open")

    with pytest.raises(CircuitBreakerOpen):
        await with_retry(fn, circuit_breaker=_OpenCircuitBreaker())


@pytest.mark.asyncio
async def test_retry_decorator_uses_named_circuit_breaker(monkeypatch):
    import src.core.circuit_breaker as cb_module

    state = {"created": 0, "used": 0}

    class _FakeCB:
        async def call(self, func, *args, **kwargs):
            state["used"] += 1
            return await func(*args, **kwargs)

    def _get_cb(_name):
        return None

    def _create_cb(_name):
        state["created"] += 1
        return _FakeCB()

    monkeypatch.setattr(cb_module, "get_circuit_breaker", _get_cb)
    monkeypatch.setattr(cb_module, "create_circuit_breaker", _create_cb)

    @retry(circuit_breaker_name="api-cb", max_retries=0)
    async def _fn():
        return "ok"

    assert await _fn() == "ok"
    assert state["created"] == 1
    assert state["used"] == 1
