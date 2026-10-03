from unittest.mock import MagicMock
from datetime import datetime, timedelta

import pytest

from src.self_healing.recovery_actions import (
    CircuitBreaker,
    RateLimiter,
    RecoveryActionExecutor,
    RecoveryActionType,
    RecoveryResult,
)


@pytest.fixture(autouse=True)
def isolated_backends(monkeypatch):
    for name in ("systemctl", "docker", "kubectl"):
        monkeypatch.setattr(RecoveryActionExecutor, f"_probe_{name}", staticmethod(lambda: False))
    monkeypatch.setattr(RecoveryActionExecutor, "_probe_routing", staticmethod(lambda: None))
    monkeypatch.setattr("src.self_healing.recovery.executor.get_event_bus", lambda: MagicMock())


def test_rate_limiter_blocks_when_exceeded(monkeypatch):
    rl = RateLimiter(max_actions=2, window_seconds=60)

    class _FakeDT(datetime):
        now_value = datetime(2026, 1, 1, 0, 0, 0)

        @classmethod
        def now(cls, tz=None):
            return cls.now_value

    monkeypatch.setattr("src.self_healing.recovery.rate_limiter.datetime", _FakeDT)

    assert rl.allow() is True
    assert rl.allow() is True
    assert rl.allow() is False


def test_circuit_breaker_opens_and_transitions_to_half_open(monkeypatch):
    cb = CircuitBreaker(failure_threshold=2, success_threshold=1, timeout=timedelta(seconds=10))

    class _FakeDT(datetime):
        now_value = datetime(2026, 1, 1, 0, 0, 0)

        @classmethod
        def now(cls, tz=None):
            return cls.now_value

    monkeypatch.setattr("src.self_healing.recovery.circuit_breaker.datetime", _FakeDT)

    def boom():
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        cb.call(boom)
    with pytest.raises(RuntimeError):
        cb.call(boom)

    assert cb.state.state == "open"

    with pytest.raises(Exception):
        cb.call(lambda: True)

    _FakeDT.now_value = _FakeDT.now_value + timedelta(seconds=11)
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state.state in ("half_open", "closed")


def test_parse_action_type_mapping():
    ex = RecoveryActionExecutor(enable_circuit_breaker=False, enable_rate_limiting=False)

    assert ex._parse_action_type("Restart service") == RecoveryActionType.RESTART_SERVICE
    assert ex._parse_action_type("Switch route") == RecoveryActionType.SWITCH_ROUTE
    assert ex._parse_action_type("Clear cache") == RecoveryActionType.CLEAR_CACHE
    assert ex._parse_action_type("Scale up") == RecoveryActionType.SCALE_UP
    assert ex._parse_action_type("Scale down") == RecoveryActionType.SCALE_DOWN
    assert ex._parse_action_type("Failover") == RecoveryActionType.FAILOVER
    assert ex._parse_action_type("Quarantine") == RecoveryActionType.QUARANTINE_NODE
    assert ex._parse_action_type("Unknown") == RecoveryActionType.NO_ACTION


def test_execute_retries_and_records_failure(monkeypatch):
    ex = RecoveryActionExecutor(
        enable_circuit_breaker=False,
        enable_rate_limiting=False,
        max_retries=2,
        retry_delay=0.0,
    )

    calls = {"n": 0}

    def _internal(action_type, context):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("fail")
        return RecoveryResult(True, RecoveryActionType.CLEAR_CACHE)

    monkeypatch.setattr(ex, "_execute_action_internal", _internal)

    ok = ex.execute("Clear cache", {"cache_type": "all"})
    assert ok is True
    assert calls["n"] == 2
    assert ex.action_history


def test_rollback_last_action_executes_rollback_action(monkeypatch):
    ex = RecoveryActionExecutor(enable_circuit_breaker=False, enable_rate_limiting=False)

    monkeypatch.setattr(
        ex, "_switch_route", lambda context: RecoveryResult(True, RecoveryActionType.SWITCH_ROUTE)
    )
    # Explicit test backend executes the forward action.
    ex.execute("Switch route", {"old_route": "r1", "alternative_route": "r2"})
    assert ex.rollback_stack

    called = {"action": None}

    def _execute(action, context=None, **kwargs):
        called["action"] = action
        return True

    monkeypatch.setattr(ex, "execute", _execute)

    assert ex.rollback_last_action() is True
    assert called["action"] == RecoveryActionType.SWITCH_ROUTE


def test_restart_service_tries_systemd_then_fallback(monkeypatch):
    ex = RecoveryActionExecutor(enable_circuit_breaker=False, enable_rate_limiting=False)

    def _run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", _run)

    res = ex._restart_service({"service_name": "svc"})
    assert res.success is False
    assert res.details and res.details.get("method") == "unavailable"
