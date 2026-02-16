"""
Tests for connection retry logic.

Covers:
- Retry policy calculations
- Exponential backoff with jitter
- Circuit breaker integration
- Retry decorator functionality
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.connection_retry import (IDEMPOTENT_RETRY_POLICY,
                                       NETWORK_RETRY_POLICY, ConnectionPool,
                                       RetryExhausted, RetryPolicy, retry,
                                       with_retry)


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_default_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter is True

    def test_calculate_delay_no_jitter(self):
        """Test delay calculation without jitter."""
        policy = RetryPolicy(jitter=False, base_delay=1.0, exponential_base=2.0)

        assert policy.calculate_delay(0) == 1.0
        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 4.0
        assert policy.calculate_delay(3) == 8.0

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter adds randomness."""
        policy = RetryPolicy(jitter=True, base_delay=1.0, jitter_max=0.5)

        delay = policy.calculate_delay(0)
        assert 1.0 <= delay <= 1.5

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        policy = RetryPolicy(
            base_delay=1.0, exponential_base=10.0, max_delay=50.0, jitter=False
        )

        # 10^3 = 1000, but should be capped at 50
        delay = policy.calculate_delay(3)
        assert delay == 50.0


class TestWithRetry:
    """Tests for with_retry function."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful execution without retries."""
        mock_func = AsyncMock(return_value="success")
        policy = RetryPolicy(max_retries=3)

        result = await with_retry(mock_func, policy=policy)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Test retry on failure followed by success."""
        mock_func = AsyncMock(side_effect=[Exception("error"), "success"])
        policy = RetryPolicy(max_retries=3, base_delay=0.01, jitter=False)

        result = await with_retry(mock_func, policy=policy)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test that RetryExhausted is raised after all retries fail."""
        mock_func = AsyncMock(side_effect=Exception("persistent error"))
        policy = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)

        with pytest.raises(RetryExhausted) as exc_info:
            await with_retry(mock_func, policy=policy)

        assert "failed after 3 attempts" in str(exc_info.value)
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_args_and_kwargs(self):
        """Test retry passes args and kwargs correctly."""
        mock_func = AsyncMock(return_value="success")
        policy = RetryPolicy(max_retries=1, base_delay=0.01, jitter=False)

        result = await with_retry(
            mock_func, "arg1", "arg2", key1="value1", key2="value2", policy=policy
        )

        assert result == "success"
        mock_func.assert_called_once_with("arg1", "arg2", key1="value1", key2="value2")


class TestRetryDecorator:
    """Tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful function."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        async def my_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_function()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_retry_then_success(self):
        """Test decorator retries then succeeds."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        async def my_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary error")
            return "success"

        result = await my_function()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_exhausted(self):
        """Test decorator raises RetryExhausted."""

        @retry(max_retries=2, base_delay=0.01)
        async def my_function():
            raise ConnectionError("persistent error")

        with pytest.raises(RetryExhausted):
            await my_function()


class TestConnectionPool:
    """Tests for ConnectionPool."""

    @pytest.mark.asyncio
    async def test_pool_acquire_new_connection(self):
        """Test acquiring a new connection when pool is empty."""
        factory = AsyncMock(return_value="connection1")
        pool = ConnectionPool(factory, max_size=2)

        conn = await pool.acquire()

        assert conn == "connection1"
        factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_pool_acquire_reuse_connection(self):
        """Test reusing a connection from the pool."""
        factory = AsyncMock(return_value="connection1")
        pool = ConnectionPool(factory, max_size=2)

        # Acquire and release
        conn1 = await pool.acquire()
        await pool.release(conn1)

        # Acquire again (should reuse)
        factory.reset_mock()
        conn2 = await pool.acquire()

        assert conn2 == "connection1"
        factory.assert_not_called()  # Factory not called for reuse

    @pytest.mark.asyncio
    async def test_pool_max_size(self):
        """Test pool respects max size."""
        factory = AsyncMock(side_effect=["conn1", "conn2", "conn3"])
        pool = ConnectionPool(factory, max_size=2)

        # Acquire and release 3 connections
        conn1 = await pool.acquire()
        conn2 = await pool.acquire()
        conn3 = await pool.acquire()

        await pool.release(conn1)
        await pool.release(conn2)
        await pool.release(conn3)  # Should not be added (pool full)

        # Pool should only have 2 connections
        assert len(pool._pool) == 2

    @pytest.mark.asyncio
    async def test_pool_close_all(self):
        """Test closing all connections."""
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()

        factory = AsyncMock(return_value=mock_conn)
        pool = ConnectionPool(factory, max_size=2)

        conn = await pool.acquire()
        await pool.release(conn)

        await pool.close_all()

        assert len(pool._pool) == 0
        mock_conn.close.assert_called_once()


class TestPredefinedPolicies:
    """Tests for predefined retry policies."""

    def test_idempotent_policy(self):
        """Test IDEMPOTENT_RETRY_POLICY settings."""
        policy = IDEMPOTENT_RETRY_POLICY

        assert policy.max_retries == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 30.0

    def test_network_policy(self):
        """Test NETWORK_RETRY_POLICY settings."""
        policy = NETWORK_RETRY_POLICY

        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
