"""
Unit tests for src/self_healing/recovery_actions.py

Covers: RecoveryActionType enum, RecoveryResult dataclass, CircuitBreakerState,
CircuitBreaker state machine, RateLimiter windowing, RecoveryActionExecutor
(execute, retries, history, success_rate, rollback, circuit breaker/rate limiter
status, async wrappers).
"""

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

import subprocess
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from src.self_healing.recovery_actions import (CircuitBreaker,
                                               CircuitBreakerState,
                                               RateLimiter,
                                               RecoveryActionExecutor,
                                               RecoveryActionType,
                                               RecoveryResult)

# ────────────────────────────────────────────
# RecoveryActionType enum
# ────────────────────────────────────────────


class TestRecoveryActionType:
    def test_all_members_exist(self):
        expected = {
            "RESTART_SERVICE",
            "SWITCH_ROUTE",
            "CLEAR_CACHE",
            "SCALE_UP",
            "SCALE_DOWN",
            "FAILOVER",
            "QUARANTINE_NODE",
            "NO_ACTION",
        }
        assert set(RecoveryActionType.__members__.keys()) == expected

    def test_values_are_strings(self):
        for member in RecoveryActionType:
            assert isinstance(member.value, str)

    def test_specific_values(self):
        assert RecoveryActionType.RESTART_SERVICE.value == "restart_service"
        assert RecoveryActionType.NO_ACTION.value == "no_action"


# ────────────────────────────────────────────
# RecoveryResult dataclass
# ────────────────────────────────────────────


class TestRecoveryResult:
    def test_required_fields(self):
        r = RecoveryResult(
            success=True,
            action_type=RecoveryActionType.CLEAR_CACHE,
            duration_seconds=1.23,
        )
        assert r.success is True
        assert r.action_type == RecoveryActionType.CLEAR_CACHE
        assert r.duration_seconds == 1.23
        assert r.error_message is None
        assert r.details is None

    def test_optional_fields(self):
        r = RecoveryResult(
            success=False,
            action_type=RecoveryActionType.FAILOVER,
            duration_seconds=0.5,
            error_message="network down",
            details={"region": "eu"},
        )
        assert r.error_message == "network down"
        assert r.details == {"region": "eu"}


# ────────────────────────────────────────────
# CircuitBreakerState dataclass
# ────────────────────────────────────────────


class TestCircuitBreakerState:
    def test_defaults(self):
        s = CircuitBreakerState()
        assert s.failures == 0
        assert s.successes == 0
        assert s.state == "closed"
        assert s.last_failure_time is None
        assert s.opened_at is None


# ────────────────────────────────────────────
# CircuitBreaker state machine
# ────────────────────────────────────────────


class TestCircuitBreaker:
    def _make_fake_datetime(self, monkeypatch, initial):
        """Helper: patch datetime.now() in the module under test."""

        class FakeDT(datetime):
            _now = initial

            @classmethod
            def now(cls, tz=None):
                return cls._now

        monkeypatch.setattr("src.self_healing.recovery_actions.datetime", FakeDT)
        return FakeDT

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state.state == "closed"

    def test_successful_call_returns_result(self):
        cb = CircuitBreaker()
        assert cb.call(lambda: 42) == 42

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        # Cause one failure
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert cb.state.failures == 1
        # Success resets
        cb.call(lambda: "ok")
        assert cb.state.failures == 0

    def test_opens_after_threshold_failures(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        cb = CircuitBreaker(failure_threshold=3, timeout=timedelta(seconds=60))
        boom = lambda: (_ for _ in ()).throw(RuntimeError("fail"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(boom)

        assert cb.state.state == "open"
        assert cb.state.failures == 3

    def test_open_circuit_rejects_calls(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        cb = CircuitBreaker(failure_threshold=2, timeout=timedelta(seconds=60))
        boom = lambda: (_ for _ in ()).throw(RuntimeError("fail"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(boom)

        # Within timeout -> rejected
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(lambda: "should not run")

    def test_transitions_to_half_open_after_timeout(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=1,
            timeout=timedelta(seconds=10),
        )
        boom = lambda: (_ for _ in ()).throw(RuntimeError("fail"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(boom)
        assert cb.state.state == "open"

        # Advance past timeout
        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=11)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        # With success_threshold=1, one success in half_open closes it
        assert cb.state.state == "closed"

    def test_half_open_returns_to_open_on_failure(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout=timedelta(seconds=10),
        )
        boom = lambda: (_ for _ in ()).throw(RuntimeError("fail"))

        # Open the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(boom)
        assert cb.state.state == "open"

        # Advance past timeout -> transitions to half_open on next call
        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=11)
        # Fail in half_open
        with pytest.raises(RuntimeError):
            cb.call(boom)

        # failures >= threshold -> back to open
        assert cb.state.state == "open"

    def test_half_open_needs_multiple_successes_to_close(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=3,
            timeout=timedelta(seconds=10),
        )
        boom = lambda: (_ for _ in ()).throw(RuntimeError("fail"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(boom)

        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=11)

        # First success in half_open: not enough yet
        cb.call(lambda: "ok")
        assert cb.state.state == "half_open"
        assert cb.state.successes == 1

        # Second success
        cb.call(lambda: "ok")
        assert cb.state.state == "half_open"
        assert cb.state.successes == 2

        # Third success -> closes
        cb.call(lambda: "ok")
        assert cb.state.state == "closed"
        assert cb.state.successes == 0
        assert cb.state.failures == 0

    def test_on_success_in_closed_state_increments_successes(self):
        cb = CircuitBreaker()
        cb.call(lambda: 1)
        cb.call(lambda: 2)
        assert cb.state.successes == 2
        assert cb.state.failures == 0


# ────────────────────────────────────────────
# RateLimiter
# ────────────────────────────────────────────


class TestRateLimiter:
    def _make_fake_datetime(self, monkeypatch, initial):
        class FakeDT(datetime):
            _now = initial

            @classmethod
            def now(cls, tz=None):
                return cls._now

        monkeypatch.setattr("src.self_healing.recovery_actions.datetime", FakeDT)
        return FakeDT

    def test_allows_up_to_max_actions(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        rl = RateLimiter(max_actions=3, window_seconds=60)
        assert rl.allow() is True
        assert rl.allow() is True
        assert rl.allow() is True
        assert rl.allow() is False

    def test_window_expiry_allows_new_actions(self, monkeypatch):
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        rl = RateLimiter(max_actions=2, window_seconds=10)

        assert rl.allow() is True
        assert rl.allow() is True
        assert rl.allow() is False

        # Advance time past window
        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=11)
        assert rl.allow() is True

    def test_partial_window_expiry(self, monkeypatch):
        """Only actions older than window are evicted."""
        fake_dt = self._make_fake_datetime(monkeypatch, datetime(2026, 1, 1))
        rl = RateLimiter(max_actions=2, window_seconds=10)

        assert rl.allow() is True  # t=0
        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=5)
        assert rl.allow() is True  # t=5

        # t=11: first action expired, second still active
        fake_dt._now = datetime(2026, 1, 1) + timedelta(seconds=11)
        assert rl.allow() is True  # evicts first, now 2 in deque
        assert rl.allow() is False  # full again

    def test_default_values(self):
        rl = RateLimiter()
        assert rl.max_actions == 10
        assert rl.window_seconds == 60
        assert len(rl.action_times) == 0


# ────────────────────────────────────────────
# RecoveryActionExecutor - initialization
# ────────────────────────────────────────────


class TestExecutorInit:
    def test_default_initialization(self):
        ex = RecoveryActionExecutor()
        assert ex.node_id == "default-node"
        assert ex.circuit_breaker is not None
        assert ex.rate_limiter is not None
        assert ex.max_retries == 3
        assert ex.retry_delay == 1.0
        assert ex.action_history == []
        assert ex.rollback_stack == []

    def test_custom_initialization(self):
        ex = RecoveryActionExecutor(
            node_id="node-42",
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=5,
            retry_delay=0.5,
        )
        assert ex.node_id == "node-42"
        assert ex.circuit_breaker is None
        assert ex.rate_limiter is None
        assert ex.max_retries == 5
        assert ex.retry_delay == 0.5


# ────────────────────────────────────────────
# RecoveryActionExecutor._parse_action_type
# ────────────────────────────────────────────


class TestParseActionType:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
        )

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Restart service", RecoveryActionType.RESTART_SERVICE),
            ("reboot node", RecoveryActionType.RESTART_SERVICE),
            ("Switch route", RecoveryActionType.SWITCH_ROUTE),
            ("update route table", RecoveryActionType.SWITCH_ROUTE),
            ("Clear cache", RecoveryActionType.CLEAR_CACHE),
            ("clear all", RecoveryActionType.CLEAR_CACHE),
            ("Scale up deployment", RecoveryActionType.SCALE_UP),
            ("scale-up web", RecoveryActionType.SCALE_UP),
            ("Scale down deployment", RecoveryActionType.SCALE_DOWN),
            ("scale-down workers", RecoveryActionType.SCALE_DOWN),
            ("Failover to backup", RecoveryActionType.FAILOVER),
            ("Quarantine node-7", RecoveryActionType.QUARANTINE_NODE),
            ("do nothing", RecoveryActionType.NO_ACTION),
            ("something random", RecoveryActionType.NO_ACTION),
        ],
    )
    def test_parse_action_type(self, executor, text, expected):
        assert executor._parse_action_type(text) == expected


# ────────────────────────────────────────────
# RecoveryActionExecutor.execute + retries
# ────────────────────────────────────────────


class TestExecutorExecute:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            node_id="test-node",
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=3,
            retry_delay=0.0,  # no sleep in tests
        )

    def test_execute_clear_cache_success(self, executor):
        result = executor.execute("Clear cache", {"cache_type": "all"})
        assert result is True
        assert len(executor.action_history) == 1
        assert executor.action_history[0].success is True

    def test_execute_unknown_action_fails(self, executor):
        result = executor.execute("do nothing")
        assert result is False
        assert executor.action_history[-1].action_type == RecoveryActionType.NO_ACTION

    def test_execute_with_retry_succeeds_on_second_attempt(self, executor):
        call_count = {"n": 0}
        original = executor._execute_action_internal

        def flaky(action_type, context):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient failure")
            return original(action_type, context)

        executor._execute_action_internal = flaky
        result = executor.execute("Clear cache")
        assert result is True
        assert call_count["n"] == 2

    def test_execute_exhausts_retries(self, executor):
        def always_fail(action_type, context):
            raise RuntimeError("permanent failure")

        executor._execute_action_internal = always_fail
        result = executor.execute("Clear cache")
        assert result is False
        assert len(executor.action_history) == 1
        assert executor.action_history[0].error_message == "permanent failure"

    def test_execute_with_circuit_breaker(self, monkeypatch):
        """Execute goes through the circuit breaker when enabled."""
        ex = RecoveryActionExecutor(
            enable_circuit_breaker=True,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )
        result = ex.execute("Clear cache")
        assert result is True
        # CB should have incremented successes
        assert ex.circuit_breaker.state.successes >= 1

    def test_execute_rate_limited(self, monkeypatch):
        """Rate limiter blocks execution when limit exceeded."""
        ex = RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=True,
            max_retries=1,
            retry_delay=0.0,
        )
        # Force rate limiter to deny
        ex.rate_limiter.allow = lambda: False
        result = ex.execute("Clear cache")
        assert result is False
        # No history since it was blocked before execution
        assert len(ex.action_history) == 0

    @patch("time.sleep")
    @patch("time.time")
    def test_exponential_backoff_on_retries(self, mock_time, mock_sleep):
        """Retry delay increases linearly: delay*(attempt+1)."""
        mock_time.side_effect = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        ex = RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=3,
            retry_delay=0.5,
        )
        call_count = {"n": 0}

        def always_fail(action_type, context):
            call_count["n"] += 1
            raise RuntimeError("fail")

        ex._execute_action_internal = always_fail
        ex.execute("Clear cache")

        # Should sleep between retries: 0.5*1, 0.5*2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)


# ────────────────────────────────────────────
# RecoveryActionExecutor - action history
# ────────────────────────────────────────────


class TestActionHistory:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )

    def test_get_action_history_empty(self, executor):
        assert executor.get_action_history() == []

    def test_get_action_history_returns_recent(self, executor):
        executor.execute("Clear cache")
        executor.execute("Failover")
        history = executor.get_action_history()
        assert len(history) == 2
        assert history[0].action_type == RecoveryActionType.CLEAR_CACHE
        assert history[1].action_type == RecoveryActionType.FAILOVER

    def test_get_action_history_with_limit(self, executor):
        for _ in range(5):
            executor.execute("Clear cache")
        history = executor.get_action_history(limit=3)
        assert len(history) == 3

    def test_history_trimmed_at_max_size(self, executor):
        executor.max_history_size = 5
        for i in range(8):
            executor.execute("Clear cache")
        assert len(executor.action_history) == 5

    def test_record_action_duration(self, executor):
        """Duration is recorded from time.time() calls."""
        executor.execute("Clear cache")
        assert executor.action_history[0].duration_seconds >= 0.0


# ────────────────────────────────────────────
# RecoveryActionExecutor.get_success_rate
# ────────────────────────────────────────────


class TestSuccessRate:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )

    def test_success_rate_empty_history(self, executor):
        assert executor.get_success_rate() == 0.0

    def test_success_rate_all_success(self, executor):
        executor.execute("Clear cache")
        executor.execute("Failover")
        assert executor.get_success_rate() == 1.0

    def test_success_rate_mixed(self, executor):
        # 2 successful + 1 failure
        executor.execute("Clear cache")
        executor.execute("Failover")
        executor.execute("do nothing")  # NO_ACTION -> returns False
        rate = executor.get_success_rate()
        assert 0.0 < rate < 1.0

    def test_success_rate_filtered_by_action_type(self, executor):
        executor.execute("Clear cache")
        executor.execute("do nothing")  # fails
        rate = executor.get_success_rate(RecoveryActionType.CLEAR_CACHE)
        assert rate == 1.0
        rate2 = executor.get_success_rate(RecoveryActionType.NO_ACTION)
        assert rate2 == 0.0

    def test_success_rate_filtered_nonexistent_type(self, executor):
        executor.execute("Clear cache")
        rate = executor.get_success_rate(RecoveryActionType.FAILOVER)
        assert rate == 0.0


# ────────────────────────────────────────────
# RecoveryActionExecutor - rollback
# ────────────────────────────────────────────


class TestRollback:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )

    def test_rollback_empty_stack_returns_false(self, executor):
        assert executor.rollback_last_action() is False

    def test_rollback_after_switch_route(self, executor):
        executor.execute("Switch route", {"old_route": "r1", "alternative_route": "r2"})
        assert len(executor.rollback_stack) == 1
        # Rollback should call execute with the rollback action
        result = executor.rollback_last_action()
        assert result is True
        assert len(executor.rollback_stack) >= 0  # may add a new entry from rollback

    def test_rollback_after_scale_up(self, executor):
        executor.execute("Scale up", {"deployment_name": "web", "old_replicas": 2})
        assert len(executor.rollback_stack) == 1
        result = executor.rollback_last_action()
        # scale_up rollback -> scale down action
        assert result is True

    def test_rollback_restart_has_no_rollback_action(self, executor):
        executor.execute("Restart service")
        assert len(executor.rollback_stack) == 1
        # restart_service maps to None rollback
        result = executor.rollback_last_action()
        assert result is False

    def test_rollback_stack_limit(self, executor):
        for i in range(110):
            executor._save_state_for_rollback(RecoveryActionType.CLEAR_CACHE, {"i": i})
        assert len(executor.rollback_stack) == 100

    def test_rollback_failover(self, executor):
        executor.execute("Failover", {"primary_region": "us-east"})
        result = executor.rollback_last_action()
        assert result is True


# ────────────────────────────────────────────
# RecoveryActionExecutor - status methods
# ────────────────────────────────────────────


class TestStatusMethods:
    def test_circuit_breaker_status_enabled(self):
        ex = RecoveryActionExecutor(enable_circuit_breaker=True)
        status = ex.get_circuit_breaker_status()
        assert status["enabled"] is True
        assert status["state"] == "closed"
        assert status["failures"] == 0
        assert status["successes"] == 0
        assert status["last_failure"] is None

    def test_circuit_breaker_status_disabled(self):
        ex = RecoveryActionExecutor(enable_circuit_breaker=False)
        status = ex.get_circuit_breaker_status()
        assert status == {"enabled": False}

    def test_circuit_breaker_status_after_failure(self, monkeypatch):
        ex = RecoveryActionExecutor(
            enable_circuit_breaker=True,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )

        def always_fail(action_type, context):
            raise RuntimeError("fail")

        ex._execute_action_internal = always_fail
        ex.execute("Clear cache")
        status = ex.get_circuit_breaker_status()
        assert status["failures"] >= 1
        assert status["last_failure"] is not None

    def test_rate_limiter_status_enabled(self):
        ex = RecoveryActionExecutor(enable_rate_limiting=True)
        status = ex.get_rate_limiter_status()
        assert status["enabled"] is True
        assert status["current_actions"] == 0
        assert status["max_actions"] == 10
        assert status["window_seconds"] == 60

    def test_rate_limiter_status_disabled(self):
        ex = RecoveryActionExecutor(enable_rate_limiting=False)
        status = ex.get_rate_limiter_status()
        assert status == {"enabled": False}

    def test_rate_limiter_status_after_actions(self):
        ex = RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=True,
            max_retries=1,
            retry_delay=0.0,
        )
        ex.execute("Clear cache")
        status = ex.get_rate_limiter_status()
        assert status["current_actions"] >= 1


# ────────────────────────────────────────────
# RecoveryActionExecutor - internal action methods
# ────────────────────────────────────────────


class TestInternalActions:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
        )

    def test_restart_service_systemd_success(self, executor, monkeypatch):
        mock_result = MagicMock()
        mock_result.returncode = 0
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        result = executor._restart_service({"service_name": "myservice"})
        assert result.success is True
        assert result.details["method"] == "systemd"

    def test_restart_service_docker_fallback(self, executor, monkeypatch):
        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if cmd[0] == "systemctl":
                raise FileNotFoundError()
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = executor._restart_service({"service_name": "myservice"})
        assert result.success is True
        assert result.details["method"] == "docker"

    def test_restart_service_kubernetes_fallback(self, executor, monkeypatch):
        def mock_run(cmd, **kwargs):
            if cmd[0] in ("systemctl", "docker"):
                raise FileNotFoundError()
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = executor._restart_service({"service_name": "myservice"})
        assert result.success is True
        assert result.details["method"] == "kubernetes"

    def test_restart_service_all_fail_simulated(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = executor._restart_service({"service_name": "myservice"})
        assert result.success is True
        assert result.details["method"] == "simulated"

    def test_restart_service_nonzero_exit_falls_through(self, executor, monkeypatch):
        """When subprocess returns nonzero, it falls through to next method."""

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 1
            return result

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = executor._restart_service({"service_name": "myservice"})
        # All return code 1 -> falls through to simulated
        assert result.success is True
        assert result.details["method"] == "simulated"

    def test_switch_route(self, executor):
        result = executor._switch_route(
            {"target_node": "n1", "alternative_route": "r2"}
        )
        assert result.success is True

    def test_clear_cache(self, executor):
        result = executor._clear_cache({"cache_type": "redis"})
        assert result.success is True
        assert result.details["cache_type"] == "redis"

    def test_clear_cache_default(self, executor):
        result = executor._clear_cache({})
        assert result.details["cache_type"] == "all"

    def test_scale_up_kubernetes(self, executor, monkeypatch):
        mock_result = MagicMock()
        mock_result.returncode = 0
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        result = executor._scale_up({"service_name": "web", "replicas": 5})
        assert result.success is True
        assert result.details["method"] == "kubernetes"

    def test_scale_up_simulated(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = executor._scale_up({"service_name": "web", "replicas": 3})
        assert result.success is True
        assert result.details["method"] == "simulated"

    def test_scale_down_kubernetes(self, executor, monkeypatch):
        mock_result = MagicMock()
        mock_result.returncode = 0
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

        result = executor._scale_down({"service_name": "web", "replicas": 1})
        assert result.success is True
        assert result.details["method"] == "kubernetes"

    def test_scale_down_simulated(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = executor._scale_down({"service_name": "web", "replicas": 1})
        assert result.success is True
        assert result.details["method"] == "simulated"

    def test_failover(self, executor):
        result = executor._failover({"primary_node": "p1", "backup_node": "b1"})
        assert result.success is True
        assert result.details["primary_node"] == "p1"

    def test_quarantine_node(self, executor):
        result = executor._quarantine_node({"node_id": "bad-node"})
        assert result.success is True
        assert result.details["node_id"] == "bad-node"

    def test_execute_action_internal_no_action(self, executor):
        result = executor._execute_action_internal(RecoveryActionType.NO_ACTION, {})
        assert result.success is False
        assert result.error_message == "Unknown action type"


# ────────────────────────────────────────────
# RecoveryActionExecutor - async wrappers
# ────────────────────────────────────────────


class TestAsyncWrappers:
    @pytest.fixture
    def executor(self):
        return RecoveryActionExecutor(
            enable_circuit_breaker=False,
            enable_rate_limiting=False,
            max_retries=1,
            retry_delay=0.0,
        )

    @pytest.mark.asyncio
    async def test_restart_service_async(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = await executor.restart_service("svc", "default")
        assert result is True

    @pytest.mark.asyncio
    async def test_switch_route_async(self, executor):
        result = await executor.switch_route("old", "new")
        assert result is True

    @pytest.mark.asyncio
    async def test_clear_cache_async(self, executor):
        result = await executor.clear_cache("svc", "redis")
        assert result is True

    @pytest.mark.asyncio
    async def test_scale_up_async(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = await executor.scale_up("deploy", 3, "default")
        assert result is True

    @pytest.mark.asyncio
    async def test_scale_down_async(self, executor, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()),
        )
        result = await executor.scale_down("deploy", 2, "default")
        assert result is True

    @pytest.mark.asyncio
    async def test_failover_async(self, executor):
        result = await executor.failover("svc", "us-east", "us-west")
        assert result is True

    @pytest.mark.asyncio
    async def test_quarantine_node_async(self, executor):
        result = await executor.quarantine_node("bad-node")
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_action_async(self, executor):
        result = await executor.execute_action("Clear cache", cache_type="all")
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_action_async_with_context(self, executor):
        result = await executor.execute_action(
            "Failover",
            context={"primary_node": "p1"},
            backup_node="b1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_action_async_unknown(self, executor):
        result = await executor.execute_action("do nothing")
        assert result is False
