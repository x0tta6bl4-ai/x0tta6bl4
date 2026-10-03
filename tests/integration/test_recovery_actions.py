"""Recovery integration with the real EventBus and mocked command boundary.

This verifies local orchestration, not live service recovery.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.coordination.events import EventBus, EventType
from src.self_healing.recovery import RecoveryActionExecutor


@pytest.fixture
def executor(monkeypatch, tmp_path):
    for name in ("systemctl", "docker", "kubectl"):
        monkeypatch.setattr(RecoveryActionExecutor, f"_probe_{name}", staticmethod(lambda: False))
    monkeypatch.setattr(RecoveryActionExecutor, "_probe_routing", staticmethod(lambda: None))
    return RecoveryActionExecutor(event_bus=EventBus(project_root=str(tmp_path)), retry_delay=0)


@pytest.mark.asyncio
async def test_successful_restart_records_command_and_event(executor, monkeypatch):
    executor._available_backends["systemctl"] = True
    run = Mock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", run)
    assert await executor.restart_service("test-service")
    assert run.call_args.args[0] == ["systemctl", "restart", "test-service"]
    events = executor.event_bus.get_event_history(event_type=EventType.PIPELINE_STAGE_END)
    assert len(events) == 1
    assert events[0].data["details"]["method"] == "systemd"
    assert events[0].data["success"] is True
    assert not executor.event_bus.get_event_history(event_type=EventType.HEALING_VERIFIED)


@pytest.mark.asyncio
async def test_scale_command_honors_namespace(executor, monkeypatch):
    executor._available_backends["kubectl"] = True
    run = Mock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", run)
    assert await executor.scale_up("worker", 3, namespace="lab")
    assert run.call_args.args[0] == [
        "kubectl",
        "scale",
        "deployment/worker",
        "--replicas=3",
        "--namespace",
        "lab",
        "--request-timeout=25s",
    ]
    assert executor.event_bus.get_event_history(event_type=EventType.PIPELINE_STAGE_END)


@pytest.mark.asyncio
async def test_unavailable_action_persists_failure(executor):
    assert not await executor.quarantine_node("node")
    events = executor.event_bus.get_event_history(event_type=EventType.TASK_FAILED)
    assert len(events) == 1
    assert events[0].data["success"] is False
    assert events[0].data["details"]["method"] == "unavailable"
    assert not executor.rollback_stack


@pytest.mark.asyncio
async def test_policy_denial_never_executes_command(executor, monkeypatch):
    executor.require_policy = True
    run = Mock()
    monkeypatch.setattr("src.self_healing.recovery.executor.safe_run", run)
    assert not await executor.restart_service("svc")
    run.assert_not_called()
    events = executor.event_bus.get_event_history(event_type=EventType.TASK_BLOCKED)
    assert len(events) == 1
    assert events[0].data["stage"] == "policy_denied"
