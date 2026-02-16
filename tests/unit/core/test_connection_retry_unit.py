"""Unit tests for core connection retry utilities."""

from unittest.mock import AsyncMock

import pytest

from src.core.connection_retry import (ConnectionPool, RetryExhausted,
                                       RetryPolicy, with_retry)


def test_retry_policy_calculate_delay_without_jitter():
    policy = RetryPolicy(
        base_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False
    )
    assert policy.calculate_delay(0) == 1.0
    assert policy.calculate_delay(1) == 2.0
    assert policy.calculate_delay(4) == 10.0


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
