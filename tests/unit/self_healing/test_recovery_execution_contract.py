"""Recovery contract regressions; all operating-system actions are mocked.

Run without the unrelated global dependency mocks:
python -m pytest --confcutdir=tests/unit/self_healing \
    tests/unit/self_healing/test_recovery_execution_contract.py
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.coordination.events import EventType
from src.self_healing.recovery import (
    CircuitBreaker,
    RecoveryActionExecutor,
    RecoveryActionType,
    RecoveryResult,
)


@pytest.fixture
def executor(monkeypatch):
    for name in ("systemctl", "docker", "kubectl"):
        monkeypatch.setattr(RecoveryActionExecutor, f"_probe_{name}", staticmethod(lambda: False))
    monkeypatch.setattr(RecoveryActionExecutor, "_probe_routing", staticmethod(lambda: None))

    # Unexpected command execution must fail the test.
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected operating-system command")

    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", unexpected)
    return RecoveryActionExecutor(event_bus=Mock(), retry_delay=0, enable_rate_limiting=False)


@pytest.mark.parametrize("action_type", list(RecoveryActionType))
def test_canonical_action_round_trip(executor, action_type):
    assert isinstance(action_type, str)
    assert executor._parse_action_type(action_type.value) is action_type


@pytest.mark.parametrize(
    "action",
    [
        "restart_service",
        "clear_cache",
        "scale_up",
        "scale_down",
        "failover",
        "quarantine_node",
        "switch_protocol",
    ],
)
def test_missing_executor_is_not_success(executor, action):
    assert executor.execute(action) is False
    assert executor.last_result.success is False
    assert executor.last_result.details["method"] == "unavailable"
    assert not executor.rollback_stack
    assert executor.get_success_rate() == 0
    assert executor.event_bus.publish.call_args.args[0] == EventType.TASK_FAILED


def test_missing_route_is_not_success(executor, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "src.network.routing.mesh_router", None)
    assert not executor.execute("switch_route")
    assert executor.last_result.details["method"] == "unavailable"


def test_rejected_route_is_not_success(executor):
    executor._routing_backend = SimpleNamespace(switch_route=Mock(return_value=False))
    assert not executor.execute("switch_route", {"target_node": "n", "alternative_route": "r"})
    assert not executor.rollback_stack


def test_backend_failure_opens_breaker(executor, monkeypatch):
    handler = Mock(return_value=RecoveryResult(False, "restart_service"))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    executor.circuit_breaker.failure_threshold = 2
    assert not executor.execute("restart_service")
    assert not executor.execute("restart_service")
    assert executor.circuit_breaker.state.state == "open"
    assert not executor.execute("restart_service")
    assert handler.call_count == 2


def test_generic_breaker_preserves_falsy_result():
    cb = CircuitBreaker()
    assert cb.call(lambda: False) is False
    assert cb.state.failures == 0


def test_half_open_requires_new_successes():
    cb = CircuitBreaker(
        failure_threshold=1,
        success_threshold=2,
        timeout=timedelta(0),
        is_failure=lambda result: result is False,
    )
    for _ in range(4):
        cb.call(lambda: True)
    cb.call(lambda: False)
    assert cb.state.state == "open"
    cb.call(lambda: True)
    assert cb.state.state == "half_open"
    assert cb.state.successes == 1
    cb.call(lambda: False)
    assert cb.state.state == "open"
    cb.call(lambda: True)
    cb.call(lambda: True)
    assert cb.state.state == "closed"


@pytest.mark.parametrize(
    "method,args",
    [
        ("restart_service", ("svc",)),
        ("switch_route", ("old", "new")),
        ("clear_cache", ("svc", "redis")),
        ("scale_up", ("svc", 3)),
        ("scale_down", ("svc", 1)),
        ("failover", ("svc", "eu", "us")),
        ("quarantine_node", ("node",)),
        ("execute_action", ("restart_service",)),
    ],
)
def test_public_wrappers_enforce_policy(executor, monkeypatch, method, args):
    handler = Mock()
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    executor.require_policy = True
    assert asyncio.run(getattr(executor, method)(*args)) is False
    handler.assert_not_called()
    assert "required" in executor.last_result.error_message
    assert executor.event_bus.publish.call_args.args[0] == EventType.TASK_BLOCKED


@pytest.mark.parametrize("action", ["scale_up", "scale_down"])
def test_scaling_uses_requested_deployment_and_namespace(executor, monkeypatch, action):
    run = Mock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", run)
    executor._available_backends["kubectl"] = True
    assert executor.execute(
        action, {"deployment_name": "worker", "namespace": "lab", "replicas": 2}
    )
    command = run.call_args.args[0]
    assert "deployment/worker" in command
    assert command[command.index("--namespace") + 1] == "lab"
    assert "--replicas=2" in command
    assert len(executor.rollback_stack) == 1


@pytest.mark.parametrize("replicas", [-1, True, "3", 1.5])
def test_invalid_replica_count_never_reaches_backend(executor, replicas):
    executor._available_backends["kubectl"] = True
    assert not executor.execute("scale_up", {"replicas": replicas})
    assert "non-negative integer" in executor.last_result.error_message


def test_nonzero_exit_is_not_simulated_success(executor, monkeypatch):
    monkeypatch.setattr(
        "src.self_healing.recovery.executor.safe_run",
        Mock(return_value=SimpleNamespace(returncode=1, stderr="denied")),
    )
    executor._available_backends["kubectl"] = True
    assert not executor.execute("scale_down")
    assert executor.last_result.error_message == "denied"


def test_event_failure_does_not_repeat_side_effect(executor, monkeypatch):
    handler = Mock(return_value=RecoveryResult(True, "restart_service"))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    executor.event_bus.publish.side_effect = OSError("disk full")
    assert executor.execute("restart_service")
    assert handler.call_count == 1
    assert len(executor.action_history) == 1


def test_rate_limit_replaces_stale_success(executor, monkeypatch):
    monkeypatch.setattr(
        executor,
        "_execute_action_internal",
        Mock(return_value=RecoveryResult(True, "restart_service")),
    )
    assert executor.execute("restart_service")
    executor.rate_limiter = SimpleNamespace(allow=lambda: False)
    assert not executor.execute("restart_service")
    assert not executor.last_result.success
    assert executor.event_bus.publish.call_args.args[0] == EventType.TASK_BLOCKED


def test_async_call_does_not_mutate_context(executor):
    context = {"cache_type": "redis"}
    asyncio.run(executor.execute_action("clear_cache", context, service_name="svc"))
    assert context == {"cache_type": "redis"}


def test_duration_uses_monotonic_clock(executor, monkeypatch):
    clock = iter([100.0, 100.25])
    monkeypatch.setattr("src.self_healing.recovery.executor.time.monotonic", lambda: next(clock))
    monkeypatch.setattr(
        executor,
        "_execute_action_internal",
        Mock(return_value=RecoveryResult(True, "restart_service")),
    )
    assert executor.execute("restart_service")
    assert executor.last_result.duration_seconds == 0.25


@pytest.mark.parametrize(
    "kind,context,expected_key,expected_value",
    [
        (
            "scale_up",
            {"deployment_name": "worker", "namespace": "lab", "replicas": 9, "old_replicas": 2},
            "replicas",
            2,
        ),
        (
            "scale_down",
            {"deployment_name": "worker", "replicas": 0, "old_replicas": 4},
            "replicas",
            4,
        ),
        (
            "switch_route",
            {"target_node": "n", "alternative_route": "new", "old_route": "old"},
            "alternative_route",
            "old",
        ),
    ],
)
def test_rollback_restores_previous_target(
    executor, monkeypatch, kind, context, expected_key, expected_value
):
    handler = Mock(side_effect=lambda action, ctx: RecoveryResult(True, action))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    assert executor.execute(kind, context)
    assert executor.rollback_last_action()
    inverse_context = handler.call_args.args[1]
    assert inverse_context[expected_key] == expected_value
    assert executor.rollback_stack == []
    assert len(executor.action_history) == 2
    assert context[expected_key] != expected_value  # input was not mutated


@pytest.mark.parametrize("denied", [False, True])
def test_failed_or_denied_rollback_keeps_entry(executor, monkeypatch, denied):
    handler = Mock(return_value=RecoveryResult(True, "scale_up"))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    assert executor.execute("scale_up", {"replicas": 8, "old_replicas": 3})
    entry = executor.rollback_stack[-1]
    if denied:
        executor.require_policy = True
    else:
        handler.return_value = RecoveryResult(False, "scale_down")
    assert not executor.rollback_last_action()
    assert executor.rollback_stack == [entry]
    assert not executor.last_result.success


@pytest.mark.parametrize(
    "kind,context",
    [
        ("scale_up", {"replicas": 9}),
        ("scale_down", {"old_replicas": -1}),
        ("scale_up", {"old_replicas": True}),
        ("switch_route", {}),
        ("failover", {"primary_region": "eu"}),
        ("quarantine_node", {"node_id": "n"}),
    ],
)
def test_rollback_requires_real_inverse(executor, monkeypatch, kind, context):
    executor._save_state_for_rollback(kind, context)
    handler = Mock()
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    assert not executor.rollback_last_action()
    handler.assert_not_called()
    assert len(executor.rollback_stack) == 1


@pytest.mark.parametrize("method", ["scale_up", "scale_down"])
def test_wrapper_does_not_invent_previous_replicas(executor, monkeypatch, method):
    handler = Mock(return_value=RecoveryResult(True, method))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    assert asyncio.run(getattr(executor, method)("worker", 20))
    assert "old_replicas" not in handler.call_args.args[1]
    assert not executor.rollback_last_action()


def test_zero_history_limit_returns_no_records(executor):
    executor._record_action(RecoveryResult(True, "restart_service"))
    assert executor.get_action_history(0) == []
    assert executor.get_action_history(-1) == []
