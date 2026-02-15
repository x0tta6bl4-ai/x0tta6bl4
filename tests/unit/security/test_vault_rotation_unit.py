"""Unit tests for src.security.vault_rotation module.

Covers:
- CircuitBreaker: states, transitions, call() protection, async context manager
- CircuitBreakerOpenError
- RotationValidator: register, validate pass/fail/exception/unknown
- EnhancedDatabaseCredentialRotator: helper methods, rotate() happy path,
  rotate() with circuit-breaker open, rotate() failure & rollback, close()
- RotationScheduler: schedule_database_rotation, schedule_api_key_rotation,
  start/stop, _execute_rotation, get_schedules, get_metrics
- RotationResult / dataclass defaults
- RotationStrategy / RotationStatus enums
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.security.vault_rotation import (CircuitBreaker, CircuitBreakerConfig,
                                         CircuitBreakerOpenError,
                                         CircuitBreakerState,
                                         EnhancedDatabaseCredentialRotator,
                                         RotationResult, RotationScheduler,
                                         RotationStatus, RotationStrategy,
                                         RotationValidator)
from src.security.vault_secrets import DatabaseCredentials

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cb_config():
    return CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=10,
        half_open_max_calls=2,
        success_threshold=2,
    )


@pytest.fixture
def circuit_breaker(cb_config):
    return CircuitBreaker(cb_config, name="test-cb")


@pytest.fixture
def mock_vault_client():
    client = MagicMock()
    client.get_secret = AsyncMock(
        return_value={
            "username": "old_user",
            "password": "old_pass",
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "connection_string": "postgresql://old_user:old_pass@localhost:5432/testdb",
        }
    )
    client.put_secret = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Enum / Dataclass Tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rotation_strategy_values(self):
        assert RotationStrategy.IMMEDIATE is not None
        assert RotationStrategy.GRACEFUL is not None
        assert RotationStrategy.BLUE_GREEN is not None
        assert RotationStrategy.CANARY is not None
        assert RotationStrategy.SHADOW is not None

    def test_rotation_status_values(self):
        assert RotationStatus.PENDING.value == "pending"
        assert RotationStatus.COMPLETED.value == "completed"
        assert RotationStatus.FAILED.value == "failed"
        assert RotationStatus.ROLLING_BACK.value == "rolling_back"
        assert RotationStatus.ROLLED_BACK.value == "rolled_back"
        assert RotationStatus.CIRCUIT_OPEN.value == "circuit_open"

    def test_circuit_breaker_state_values(self):
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestRotationResult:
    def test_defaults(self):
        result = RotationResult(
            secret_path="p",
            status=RotationStatus.PENDING,
            strategy=RotationStrategy.GRACEFUL,
            started_at=datetime.now(),
        )
        assert result.completed_at is None
        assert result.old_version is None
        assert result.new_version is None
        assert result.old_creds_hash is None
        assert result.new_creds_hash is None
        assert result.error is None
        assert result.metadata == {}
        assert result.rollback_reason is None
        assert result.validation_results == {}


class TestCircuitBreakerConfig:
    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 60
        assert cfg.half_open_max_calls == 3
        assert cfg.success_threshold == 2


# ---------------------------------------------------------------------------
# CircuitBreaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_initial_state_is_closed(self, circuit_breaker):
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call_stays_closed(self, circuit_breaker):
        async def ok():
            return 42

        result = await circuit_breaker.call(ok)
        assert result == 42
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_below_threshold_stay_closed(self, circuit_breaker):
        async def fail():
            raise RuntimeError("boom")

        for _ in range(circuit_breaker.config.failure_threshold - 1):
            with pytest.raises(RuntimeError):
                await circuit_breaker.call(fail)
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_at_threshold_open_circuit(self, circuit_breaker):
        async def fail():
            raise RuntimeError("boom")

        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(RuntimeError):
                await circuit_breaker.call(fail)
        assert circuit_breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, circuit_breaker):
        async def fail():
            raise RuntimeError("boom")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(RuntimeError):
                await circuit_breaker.call(fail)

        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(fail)

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self, cb_config):
        cb_config.recovery_timeout = 0  # immediate recovery for test
        cb = CircuitBreaker(cb_config, name="fast-recover")

        async def fail():
            raise RuntimeError("boom")

        for _ in range(cb_config.failure_threshold):
            with pytest.raises(RuntimeError):
                await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

        # With recovery_timeout=0, next call should transition to HALF_OPEN
        async def ok():
            return "recovered"

        result = await cb.call(ok)
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self, cb_config):
        cb_config.recovery_timeout = 0
        cb = CircuitBreaker(cb_config, name="ho-close")

        async def fail():
            raise RuntimeError("boom")

        # Open the circuit
        for _ in range(cb_config.failure_threshold):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        async def ok():
            return True

        # Need success_threshold successes to close
        for _ in range(cb_config.success_threshold):
            await cb.call(ok)

        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, cb_config):
        cb_config.recovery_timeout = 0
        cb = CircuitBreaker(cb_config, name="ho-reopen")

        async def fail():
            raise RuntimeError("boom")

        # Open the circuit
        for _ in range(cb_config.failure_threshold):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        # Enter half-open, then fail again
        with pytest.raises(RuntimeError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limit(self, cb_config):
        cb_config.recovery_timeout = 0
        cb_config.half_open_max_calls = 1
        cb = CircuitBreaker(cb_config, name="ho-limit")

        async def fail():
            raise RuntimeError("boom")

        async def ok():
            return True

        # Open circuit
        for _ in range(cb_config.failure_threshold):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        # First half-open call OK
        await cb.call(ok)

        # Second call should be rejected (half_open_max_calls=1, but we only
        # need success_threshold=2 so circuit is still half-open)
        # Actually the call already succeeded once; depends on success_threshold.
        # With success_threshold=2 and half_open_max_calls=1, the second call
        # will hit the limit.
        with pytest.raises(CircuitBreakerOpenError, match="half-open limit"):
            await cb.call(ok)

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, circuit_breaker):
        async def fail():
            raise RuntimeError("boom")

        async def ok():
            return True

        # Accumulate some failures (below threshold)
        for _ in range(circuit_breaker.config.failure_threshold - 1):
            with pytest.raises(RuntimeError):
                await circuit_breaker.call(fail)

        # A success should reset the failure count
        await circuit_breaker.call(ok)
        assert circuit_breaker._failure_count == 0

    def test_should_attempt_reset_no_failure(self, circuit_breaker):
        assert circuit_breaker._should_attempt_reset() is True

    def test_should_attempt_reset_recent_failure(self, circuit_breaker):
        circuit_breaker._last_failure_time = time.time()
        assert circuit_breaker._should_attempt_reset() is False

    def test_should_attempt_reset_old_failure(self, circuit_breaker):
        circuit_breaker._last_failure_time = time.time() - 1000
        assert circuit_breaker._should_attempt_reset() is True


# ---------------------------------------------------------------------------
# CircuitBreaker async context manager tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerContextManager:
    @pytest.mark.asyncio
    async def test_aenter_closed(self, circuit_breaker):
        async with circuit_breaker as cb:
            assert cb is circuit_breaker

    @pytest.mark.asyncio
    async def test_aexit_success_records_success(self, circuit_breaker):
        async with circuit_breaker:
            pass
        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_aexit_failure_records_failure(self, circuit_breaker):
        with pytest.raises(ValueError):
            async with circuit_breaker:
                raise ValueError("fail")
        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_aenter_open_no_recovery(self, circuit_breaker):
        circuit_breaker._state = CircuitBreakerState.OPEN
        circuit_breaker._last_failure_time = time.time()
        with pytest.raises(CircuitBreakerOpenError):
            async with circuit_breaker:
                pass

    @pytest.mark.asyncio
    async def test_aenter_open_with_recovery(self, circuit_breaker):
        circuit_breaker._state = CircuitBreakerState.OPEN
        circuit_breaker._last_failure_time = time.time() - 1000
        async with circuit_breaker:
            assert circuit_breaker._state == CircuitBreakerState.HALF_OPEN


# ---------------------------------------------------------------------------
# RotationValidator Tests
# ---------------------------------------------------------------------------


class TestRotationValidator:
    @pytest.mark.asyncio
    async def test_validate_all_pass(self):
        v = RotationValidator()
        v.register_validator("a", AsyncMock(return_value=True))
        v.register_validator("b", AsyncMock(return_value=True))
        results = await v.validate({"user": "x"})
        assert results == {"a": True, "b": True}

    @pytest.mark.asyncio
    async def test_validate_one_fails(self):
        v = RotationValidator()
        v.register_validator("ok", AsyncMock(return_value=True))
        v.register_validator("bad", AsyncMock(return_value=False))
        results = await v.validate({"user": "x"})
        assert results["ok"] is True
        assert results["bad"] is False

    @pytest.mark.asyncio
    async def test_validate_exception_becomes_false(self):
        v = RotationValidator()
        v.register_validator("err", AsyncMock(side_effect=RuntimeError("oops")))
        results = await v.validate({"user": "x"})
        assert results["err"] is False

    @pytest.mark.asyncio
    async def test_validate_unknown_validator_skipped(self):
        v = RotationValidator()
        results = await v.validate({"user": "x"}, validators=["nonexistent"])
        assert results == {}

    @pytest.mark.asyncio
    async def test_validate_specific_subset(self):
        v = RotationValidator()
        v.register_validator("a", AsyncMock(return_value=True))
        v.register_validator("b", AsyncMock(return_value=True))
        results = await v.validate({"user": "x"}, validators=["a"])
        assert "a" in results
        assert "b" not in results

    @pytest.mark.asyncio
    async def test_validate_empty_validators(self):
        v = RotationValidator()
        results = await v.validate({"user": "x"})
        assert results == {}


# ---------------------------------------------------------------------------
# EnhancedDatabaseCredentialRotator Tests
# ---------------------------------------------------------------------------


class TestEnhancedDatabaseCredentialRotator:
    def _make_rotator(self, vault_client, strategy=RotationStrategy.IMMEDIATE):
        return EnhancedDatabaseCredentialRotator(
            vault_client=vault_client,
            db_host="localhost",
            db_port=5432,
            admin_username="postgres",
            admin_password="admin_pass",
            strategy=strategy,
            grace_period=0,
        )

    # --- Helper methods ---

    def test_generate_password_length(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        pw = rotator._generate_password(48)
        assert len(pw) == 48

    def test_generate_password_default_length(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        pw = rotator._generate_password()
        assert len(pw) == 32

    def test_generate_username_prefix(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        name = rotator._generate_username("myprefix")
        assert name.startswith("myprefix_")

    def test_generate_username_default_prefix(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        name = rotator._generate_username()
        assert name.startswith("vault_")

    def test_hash_creds_deterministic(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        creds = {"username": "u", "password": "p"}
        h1 = rotator._hash_creds(creds)
        h2 = rotator._hash_creds(creds)
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_creds_different_for_different_input(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        h1 = rotator._hash_creds({"a": "1"})
        h2 = rotator._hash_creds({"a": "2"})
        assert h1 != h2

    # --- rotate() happy path (IMMEDIATE strategy) ---

    @pytest.mark.asyncio
    async def test_rotate_immediate_success(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client, RotationStrategy.IMMEDIATE)

        # Mock pg pool and connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock()

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock()

        # Make acquire() an async context manager returning mock_conn
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_pool.close = AsyncMock()

        # Patch _get_pg_connection and validator
        rotator._pg_pool = mock_pool
        rotator._get_pg_connection = AsyncMock(return_value=mock_pool)
        rotator._validator = RotationValidator()
        rotator._validator.register_validator(
            "connectivity", AsyncMock(return_value=True)
        )
        rotator._validator.register_validator(
            "permissions", AsyncMock(return_value=True)
        )

        result = await rotator.rotate("testdb")

        assert result.status == RotationStatus.COMPLETED
        assert result.secret_path == "proxy/database/testdb"
        assert result.old_creds_hash is not None
        assert result.new_creds_hash is not None
        assert result.completed_at is not None
        assert result.error is None

    # --- rotate() with circuit breaker OPEN ---

    @pytest.mark.asyncio
    async def test_rotate_circuit_breaker_open(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        rotator._circuit_breaker._state = CircuitBreakerState.OPEN
        rotator._circuit_breaker._last_failure_time = time.time()

        result = await rotator.rotate("testdb")
        assert result.status == RotationStatus.CIRCUIT_OPEN
        assert result.error == "Circuit breaker is open"

    # --- rotate() failure triggers rollback ---

    @pytest.mark.asyncio
    async def test_rotate_failure_triggers_rollback(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client, RotationStrategy.IMMEDIATE)

        # Make vault get_database_credentials raise an error
        mock_vault_client.get_secret = AsyncMock(
            side_effect=Exception("vault unavailable")
        )

        result = await rotator.rotate("testdb")
        assert result.status in (RotationStatus.FAILED, RotationStatus.ROLLED_BACK)
        assert result.error is not None

    # --- rotate() with custom secret path ---

    @pytest.mark.asyncio
    async def test_rotate_custom_secret_path(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        rotator._circuit_breaker._state = CircuitBreakerState.OPEN
        rotator._circuit_breaker._last_failure_time = time.time()

        result = await rotator.rotate("testdb", secret_path="custom/path")
        assert result.secret_path == "custom/path"

    # --- rotate() default secret_path ---

    @pytest.mark.asyncio
    async def test_rotate_default_secret_path(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        rotator._circuit_breaker._state = CircuitBreakerState.OPEN
        rotator._circuit_breaker._last_failure_time = time.time()

        result = await rotator.rotate("mydb")
        assert result.secret_path == "proxy/database/mydb"

    # --- rotate() validation failure triggers rollback ---

    @pytest.mark.asyncio
    async def test_rotate_validation_failure_rollback(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client, RotationStrategy.IMMEDIATE)

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock()

        mock_pool = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_pool.close = AsyncMock()

        rotator._pg_pool = mock_pool
        rotator._get_pg_connection = AsyncMock(return_value=mock_pool)

        # One validator fails
        rotator._validator = RotationValidator()
        rotator._validator.register_validator(
            "connectivity", AsyncMock(return_value=False)
        )

        result = await rotator.rotate("testdb")
        assert result.status in (RotationStatus.FAILED, RotationStatus.ROLLED_BACK)

    # --- close() ---

    @pytest.mark.asyncio
    async def test_close_with_pool(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        rotator._pg_pool = mock_pool

        await rotator.close()
        mock_pool.close.assert_awaited_once()
        assert rotator._pg_pool is None

    @pytest.mark.asyncio
    async def test_close_no_pool(self, mock_vault_client):
        rotator = self._make_rotator(mock_vault_client)
        await rotator.close()  # should not raise
        assert rotator._pg_pool is None


# ---------------------------------------------------------------------------
# Rollback Tests
# ---------------------------------------------------------------------------


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_drops_new_user_and_restores_old_creds(self):
        vault_client = MagicMock()
        vault_client.put_secret = AsyncMock()

        rotator = EnhancedDatabaseCredentialRotator(
            vault_client=vault_client,
            db_host="localhost",
            strategy=RotationStrategy.IMMEDIATE,
        )

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=cm)
        mock_pool.close = AsyncMock()

        rotator._pg_pool = mock_pool
        rotator._get_pg_connection = AsyncMock(return_value=mock_pool)

        result = RotationResult(
            secret_path="p",
            status=RotationStatus.FAILED,
            strategy=RotationStrategy.IMMEDIATE,
            started_at=datetime.now(),
            error="test failure",
        )
        old_creds = {
            "username": "old_user",
            "password": "old_pass",
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "connection_string": None,
        }

        await rotator._rollback("testdb", "new_user_xyz", old_creds, result)

        assert result.status == RotationStatus.ROLLED_BACK
        assert result.rollback_reason == "test failure"
        # Verify DROP USER was called
        mock_conn.execute.assert_awaited()
        # Verify old creds were stored back in vault
        vault_client.put_secret.assert_awaited()

    @pytest.mark.asyncio
    async def test_rollback_no_new_user(self):
        vault_client = MagicMock()
        vault_client.put_secret = AsyncMock()

        rotator = EnhancedDatabaseCredentialRotator(
            vault_client=vault_client,
            db_host="localhost",
            strategy=RotationStrategy.IMMEDIATE,
        )

        result = RotationResult(
            secret_path="p",
            status=RotationStatus.FAILED,
            strategy=RotationStrategy.IMMEDIATE,
            started_at=datetime.now(),
            error="e",
        )
        old_creds = {
            "username": "old",
            "password": "pass",
            "host": "localhost",
            "port": 5432,
            "database": "db",
            "connection_string": None,
        }

        await rotator._rollback("testdb", None, old_creds, result)
        assert result.status == RotationStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_no_old_creds(self):
        vault_client = MagicMock()
        rotator = EnhancedDatabaseCredentialRotator(
            vault_client=vault_client,
            db_host="localhost",
            strategy=RotationStrategy.IMMEDIATE,
        )

        mock_conn = AsyncMock()
        mock_pool = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        rotator._pg_pool = mock_pool
        rotator._get_pg_connection = AsyncMock(return_value=mock_pool)

        result = RotationResult(
            secret_path="p",
            status=RotationStatus.FAILED,
            strategy=RotationStrategy.IMMEDIATE,
            started_at=datetime.now(),
            error="e",
        )

        await rotator._rollback("testdb", "new_user", None, result)
        assert result.status == RotationStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_pg_drop_fails_gracefully(self):
        vault_client = MagicMock()
        vault_client.put_secret = AsyncMock()

        rotator = EnhancedDatabaseCredentialRotator(
            vault_client=vault_client,
            db_host="localhost",
            strategy=RotationStrategy.IMMEDIATE,
        )

        # Make pg connection raise
        rotator._get_pg_connection = AsyncMock(side_effect=Exception("pg down"))

        result = RotationResult(
            secret_path="p",
            status=RotationStatus.FAILED,
            strategy=RotationStrategy.IMMEDIATE,
            started_at=datetime.now(),
            error="e",
        )
        old_creds = {
            "username": "old",
            "password": "pass",
            "host": "localhost",
            "port": 5432,
            "database": "db",
            "connection_string": None,
        }

        # Should not raise, failure is caught internally
        await rotator._rollback("testdb", "new_user", old_creds, result)
        assert result.status == RotationStatus.ROLLED_BACK


# ---------------------------------------------------------------------------
# RotationScheduler Tests
# ---------------------------------------------------------------------------


class TestRotationScheduler:
    def test_schedule_database_rotation(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        scheduler.schedule_database_rotation(
            "main-db", days=14, strategy=RotationStrategy.BLUE_GREEN
        )
        schedules = scheduler.get_schedules()
        assert "db:main-db" in schedules
        entry = schedules["db:main-db"]
        assert entry["type"] == "database"
        assert entry["db_name"] == "main-db"
        assert entry["interval"] == timedelta(days=14)
        assert entry["strategy"] == RotationStrategy.BLUE_GREEN
        assert entry["last_rotation"] is None
        assert entry["failure_count"] == 0

    def test_schedule_api_key_rotation(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        scheduler.schedule_api_key_rotation("stripe", days=30)
        schedules = scheduler.get_schedules()
        assert "api:stripe" in schedules
        entry = schedules["api:stripe"]
        assert entry["type"] == "api_key"
        assert entry["api_name"] == "stripe"
        assert entry["secret_path"] == "proxy/api-keys/stripe"
        assert entry["interval"] == timedelta(days=30)

    def test_schedule_api_key_rotation_custom_path(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        scheduler.schedule_api_key_rotation(
            "custom-api", days=7, secret_path="custom/api/path"
        )
        schedules = scheduler.get_schedules()
        assert schedules["api:custom-api"]["secret_path"] == "custom/api/path"

    def test_get_metrics_initial(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        metrics = scheduler.get_metrics()
        assert metrics["rotations_total"] == 0
        assert metrics["rotations_failed"] == 0
        assert metrics["rotations_successful"] == 0

    def test_get_schedules_returns_copy(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        scheduler.schedule_database_rotation("db1")
        s = scheduler.get_schedules()
        s["injected"] = "bad"
        assert "injected" not in scheduler.get_schedules()

    def test_get_metrics_returns_copy(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        m = scheduler.get_metrics()
        m["rotations_total"] = 9999
        assert scheduler.get_metrics()["rotations_total"] == 0

    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        await scheduler.start()
        task1 = scheduler._task
        await scheduler.start()  # should be no-op
        assert scheduler._task is task1
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        await scheduler.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_execute_rotation_database_success(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)

        schedule = {
            "type": "database",
            "db_name": "testdb",
            "db_config": {"host": "localhost", "port": 5432},
            "strategy": RotationStrategy.IMMEDIATE,
        }

        # Patch the rotator that gets created inside _execute_rotation
        with patch(
            "src.security.vault_rotation.EnhancedDatabaseCredentialRotator"
        ) as MockRotator:
            mock_rotator_instance = AsyncMock()
            mock_rotator_instance.rotate = AsyncMock(
                return_value=RotationResult(
                    secret_path="p",
                    status=RotationStatus.COMPLETED,
                    strategy=RotationStrategy.IMMEDIATE,
                    started_at=datetime.now(),
                )
            )
            mock_rotator_instance.close = AsyncMock()
            MockRotator.return_value = mock_rotator_instance

            success = await scheduler._execute_rotation("db:testdb", schedule)
            assert success is True
            mock_rotator_instance.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_rotation_database_failure(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)

        schedule = {
            "type": "database",
            "db_name": "testdb",
            "db_config": {},
            "strategy": RotationStrategy.IMMEDIATE,
        }

        with patch(
            "src.security.vault_rotation.EnhancedDatabaseCredentialRotator"
        ) as MockRotator:
            mock_rotator_instance = AsyncMock()
            mock_rotator_instance.rotate = AsyncMock(
                return_value=RotationResult(
                    secret_path="p",
                    status=RotationStatus.FAILED,
                    strategy=RotationStrategy.IMMEDIATE,
                    started_at=datetime.now(),
                    error="boom",
                )
            )
            mock_rotator_instance.close = AsyncMock()
            MockRotator.return_value = mock_rotator_instance

            success = await scheduler._execute_rotation("db:testdb", schedule)
            assert success is False

    @pytest.mark.asyncio
    async def test_execute_rotation_api_key_returns_false(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        schedule = {
            "type": "api_key",
            "api_name": "stripe",
            "secret_path": "proxy/api-keys/stripe",
        }
        success = await scheduler._execute_rotation("api:stripe", schedule)
        assert success is False

    @pytest.mark.asyncio
    async def test_execute_rotation_exception_returns_false(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        schedule = {
            "type": "database",
            "db_name": "testdb",
            "db_config": {},
            "strategy": RotationStrategy.IMMEDIATE,
        }

        with patch(
            "src.security.vault_rotation.EnhancedDatabaseCredentialRotator"
        ) as MockRotator:
            MockRotator.side_effect = Exception("constructor boom")
            success = await scheduler._execute_rotation("db:testdb", schedule)
            assert success is False

    @pytest.mark.asyncio
    async def test_execute_rotation_circuit_breaker_open(self, mock_vault_client):
        scheduler = RotationScheduler(mock_vault_client)
        scheduler._circuit_breaker._state = CircuitBreakerState.OPEN
        scheduler._circuit_breaker._last_failure_time = time.time()

        schedule = {
            "type": "database",
            "db_name": "testdb",
            "db_config": {},
            "strategy": RotationStrategy.IMMEDIATE,
        }
        success = await scheduler._execute_rotation("db:testdb", schedule)
        assert success is False


# ---------------------------------------------------------------------------
# CircuitBreakerOpenError
# ---------------------------------------------------------------------------


class TestCircuitBreakerOpenError:
    def test_is_exception(self):
        err = CircuitBreakerOpenError("open!")
        assert isinstance(err, Exception)
        assert str(err) == "open!"
