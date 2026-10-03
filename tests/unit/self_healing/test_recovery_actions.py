"""Public recovery wrappers must propagate actual backend outcomes."""

from unittest.mock import Mock

import pytest

from src.self_healing.recovery import RecoveryActionExecutor, RecoveryResult


@pytest.fixture
def executor(monkeypatch):
    for name in ("systemctl", "docker", "kubectl"):
        monkeypatch.setattr(RecoveryActionExecutor, f"_probe_{name}", staticmethod(lambda: False))
    monkeypatch.setattr(RecoveryActionExecutor, "_probe_routing", staticmethod(lambda: None))
    return RecoveryActionExecutor(node_id="test-node", event_bus=Mock(), retry_delay=0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,args,kind",
    [
        ("restart_service", ("svc", "lab"), "restart_service"),
        ("switch_route", ("old", "new"), "switch_route"),
        ("clear_cache", ("svc", "all"), "clear_cache"),
        ("scale_up", ("worker", 5, "lab"), "scale_up"),
        ("scale_down", ("worker", 1, "lab"), "scale_down"),
        ("failover", ("svc", "eu", "us"), "failover"),
        ("quarantine_node", ("node",), "quarantine_node"),
        ("execute_action", ("restart_service",), "restart_service"),
    ],
)
@pytest.mark.parametrize("success", [False, True])
async def test_wrapper_propagates_backend_outcome(
    executor, monkeypatch, method, args, kind, success
):
    handler = Mock(return_value=RecoveryResult(success, kind))
    monkeypatch.setattr(executor, "_execute_action_internal", handler)
    assert await getattr(executor, method)(*args) is success
    assert handler.call_args.args[0] == kind
    assert executor.last_result.success is success
    assert len(executor.action_history) == 1


@pytest.mark.asyncio
async def test_unknown_action(executor):
    assert await executor.execute_action("Unknown action") is False
