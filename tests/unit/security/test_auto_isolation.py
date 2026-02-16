import time

import pytest

from src.security.auto_isolation import (AutoIsolationManager, CircuitBreaker,
                                         IsolationLevel, IsolationPolicy,
                                         IsolationReason, IsolationRecord)


def test_isolation_record_expired_and_to_dict(monkeypatch):
    now = 1234.0
    monkeypatch.setattr(time, "time", lambda: now)

    rec = IsolationRecord(
        node_id="n1",
        level=IsolationLevel.RESTRICTED,
        reason=IsolationReason.THREAT_DETECTED,
        started_at=now - 10,
        expires_at=now - 1,
        details="x",
        auto_recover=True,
    )

    assert rec.is_expired() is True
    d = rec.to_dict()
    assert d["node_id"] == "n1"
    assert d["level"] == "RESTRICTED"
    assert d["reason"] == IsolationReason.THREAT_DETECTED.value


def test_isolation_policy_duration_and_level_caps():
    policy = IsolationPolicy(
        name="p",
        trigger_reason=IsolationReason.THREAT_DETECTED,
        initial_level=IsolationLevel.RESTRICTED,
        escalation_levels=[IsolationLevel.RESTRICTED, IsolationLevel.QUARANTINE],
        escalation_threshold=2,
        initial_duration=10,
        escalation_multiplier=3.0,
        max_duration=50,
        auto_recover=True,
    )

    assert policy.get_duration(0) == 10
    assert policy.get_duration(1) == 30
    assert policy.get_duration(2) == 50

    assert policy.get_level(0) == IsolationLevel.RESTRICTED
    assert policy.get_level(1) == IsolationLevel.QUARANTINE
    assert policy.get_level(2) == IsolationLevel.QUARANTINE


def test_circuit_breaker_transitions(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(time, "time", lambda: now)

    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10, half_open_requests=2)

    assert cb.allow_request() is True

    cb.record_failure()
    assert cb.state == CircuitBreaker.State.CLOSED

    cb.record_failure()
    assert cb.state == CircuitBreaker.State.OPEN

    assert cb.allow_request() is False

    now += 11
    assert cb.allow_request() is True
    assert cb.state == CircuitBreaker.State.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitBreaker.State.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitBreaker.State.CLOSED


def test_auto_isolation_manager_isolate_escalate_release(monkeypatch):
    now = 2000.0
    monkeypatch.setattr(time, "time", lambda: now)

    mgr = AutoIsolationManager(node_id="self")

    events = []

    def cb(node_id: str, level: IsolationLevel):
        events.append((node_id, level))

    mgr.register_callback(cb)

    r1 = mgr.isolate("nodeA", IsolationReason.THREAT_DETECTED)
    assert r1.node_id == "nodeA"
    assert mgr.get_isolation_level("nodeA") != IsolationLevel.NONE
    assert events[-1] == ("nodeA", r1.level)

    r2 = mgr.isolate("nodeA", IsolationReason.THREAT_DETECTED)
    assert r2.escalation_count == 1
    assert r2.level.value >= r1.level.value

    assert mgr.release("nodeA") is True
    assert mgr.get_isolation_level("nodeA") == IsolationLevel.NONE
    assert events[-1] == ("nodeA", IsolationLevel.NONE)


@pytest.mark.parametrize(
    "level,operation,allowed",
    [
        (IsolationLevel.NONE, "anything", True),
        (IsolationLevel.MONITOR, "anything", True),
        (IsolationLevel.RATE_LIMIT, "anything", True),
        (IsolationLevel.RESTRICTED, "health", True),
        (IsolationLevel.RESTRICTED, "write", False),
        (IsolationLevel.QUARANTINE, "health", True),
        (IsolationLevel.QUARANTINE, "auth", False),
        (IsolationLevel.BLOCKED, "health", False),
    ],
)
def test_auto_isolation_manager_is_allowed_by_level(
    monkeypatch, level, operation, allowed
):
    now = 3000.0
    monkeypatch.setattr(time, "time", lambda: now)

    mgr = AutoIsolationManager(node_id="self")

    if level != IsolationLevel.NONE:
        mgr.isolate(
            "nodeB",
            IsolationReason.ADMIN_ACTION,
            level_override=level,
            duration_override=60,
        )

    ok, _ = mgr.is_allowed("nodeB", operation=operation)
    assert ok is allowed


def test_cleanup_expired_auto_recover(monkeypatch):
    now = 4000.0
    monkeypatch.setattr(time, "time", lambda: now)

    mgr = AutoIsolationManager(node_id="self")

    mgr.isolate(
        "nodeC",
        IsolationReason.ADMIN_ACTION,
        level_override=IsolationLevel.RESTRICTED,
        duration_override=1,
    )

    now += 2
    assert mgr.cleanup_expired() == 1
    assert mgr.get_isolation_level("nodeC") == IsolationLevel.NONE
