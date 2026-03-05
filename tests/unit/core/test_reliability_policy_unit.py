"""Unit tests for src.core.reliability_policy."""

import asyncio
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from src.core.circuit_breaker import CircuitBreaker
from src.core.reliability_policy import (ReliabilityPolicy, RetryExhausted,
                                         call_with_reliability,
                                         get_degraded_dependencies,
                                         mark_degraded_dependency,
                                         policy_for_dependency,
                                         set_degraded_dependencies_header)


def test_mark_degraded_dependency_is_unique_and_sorted():
    request = SimpleNamespace(state=SimpleNamespace())
    mark_degraded_dependency(request, "redis")
    mark_degraded_dependency(request, "Stripe")
    mark_degraded_dependency(request, "redis")

    assert get_degraded_dependencies(request) == ["redis", "stripe"]


def test_set_degraded_dependencies_header_from_request_state():
    request = SimpleNamespace(state=SimpleNamespace())
    mark_degraded_dependency(request, "database")
    mark_degraded_dependency(request, "redis")
    response = Response(content="ok")

    set_degraded_dependencies_header(response, request)

    assert response.headers["X-Degraded-Dependencies"] == "database,redis"


def test_policy_for_dependency_reads_env(monkeypatch):
    monkeypatch.setenv("RELIABILITY_STRIPE_TIMEOUT_SECONDS", "4.5")
    monkeypatch.setenv("RELIABILITY_STRIPE_MAX_RETRIES", "5")
    monkeypatch.setenv("RELIABILITY_STRIPE_BASE_DELAY_SECONDS", "0.1")
    monkeypatch.setenv("RELIABILITY_STRIPE_MAX_DELAY_SECONDS", "0.7")
    monkeypatch.setenv("RELIABILITY_STRIPE_FAILURE_THRESHOLD", "4")
    monkeypatch.setenv("RELIABILITY_STRIPE_RECOVERY_TIMEOUT_SECONDS", "11")

    policy = policy_for_dependency("stripe")

    assert policy.timeout_seconds == 4.5
    assert policy.max_retries == 5
    assert policy.base_delay_seconds == 0.1
    assert policy.max_delay_seconds == 0.7
    assert policy.failure_threshold == 4
    assert policy.recovery_timeout_seconds == 11.0


def test_call_with_reliability_retries_then_succeeds():
    state = {"calls": 0}

    async def _operation():
        state["calls"] += 1
        if state["calls"] < 3:
            raise ConnectionError("transient")
        return "ok"

    policy = ReliabilityPolicy(
        timeout_seconds=1.0,
        max_retries=4,
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
    )

    result = asyncio.run(
        call_with_reliability(
            _operation,
            dependency="unit-test-retry",
            policy=policy,
            circuit_name="unit_test_retry_cb",
        )
    )

    assert result == "ok"
    assert state["calls"] == 3


def test_call_with_reliability_exhausts_retries():
    async def _operation():
        raise TimeoutError("always timeout")

    policy = ReliabilityPolicy(
        timeout_seconds=0.5,
        max_retries=1,
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
    )

    with pytest.raises(RetryExhausted):
        asyncio.run(
            call_with_reliability(
                _operation,
                dependency="unit-test-timeout",
                policy=policy,
                circuit_name="unit_test_timeout_cb",
            )
        )


def test_call_with_reliability_respects_open_circuit():
    cb = CircuitBreaker(
        name="unit_test_open_cb",
        failure_threshold=1,
        recovery_timeout=30.0,
    )

    async def _fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(cb.call(_fail))

    async def _operation():
        return "never"

    policy = ReliabilityPolicy(max_retries=0, base_delay_seconds=0.0, max_delay_seconds=0.0)

    from src.core.circuit_breaker import CircuitBreakerOpen

    with pytest.raises(CircuitBreakerOpen):
        asyncio.run(
            call_with_reliability(
                _operation,
                dependency="unit-test-open-circuit",
                policy=policy,
                circuit_breaker=cb,
            )
        )
