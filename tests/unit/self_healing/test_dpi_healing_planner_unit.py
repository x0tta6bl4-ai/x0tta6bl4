"""Unit tests for the Phase 1 DPI healing planner sketch."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from src.coordination.events import EventBus, EventType

planner_mod = pytest.importorskip("src.self_healing.dpi_healing_planner")

Decision = planner_mod.Decision
DpiHealingPlanner = planner_mod.DpiHealingPlanner
TestProfileSwitchBackend = planner_mod.TestProfileSwitchBackend
confidence_gate = planner_mod.confidence_gate
next_transport = planner_mod.next_transport


class _RecordingExecutor:
    """Duck-typed stand-in for MAPEKExecutor that drives a test backend."""

    def __init__(self, backend: TestProfileSwitchBackend) -> None:
        self.backend = backend
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        context = context or {}
        self.calls.append((action, context))
        return self.backend.switch_protocol(
            context["protocol"], context["mimic"], profile=context.get("profile")
        )


def _planner(bus: EventBus, **kw) -> tuple[DpiHealingPlanner, _RecordingExecutor]:
    backend = TestProfileSwitchBackend(test_profile="ghost-test-canary", dry_run=True)
    executor = _RecordingExecutor(backend)
    planner = DpiHealingPlanner(bus, executor, test_profile="ghost-test-canary", **kw)
    return planner, executor


# --- gate + ladder pure logic -------------------------------------------------


def test_confidence_gate_bands():
    assert confidence_gate(0.4) is Decision.OBSERVE
    assert confidence_gate(0.6) is Decision.DAO_VOTE
    assert confidence_gate(0.85) is Decision.DAO_VOTE
    assert confidence_gate(0.95) is Decision.AUTO_EXECUTE


def test_transport_ladder_progression():
    assert next_transport("reality") == ("xhttp", "http")
    assert next_transport("xhttp") == ("cf-tunnel", "https")
    assert next_transport("cf-tunnel") is None
    assert next_transport("unknown") == ("reality", "tls")


# --- planner decisions --------------------------------------------------------


def test_low_confidence_is_observe_only(tmp_path):
    bus = EventBus(str(tmp_path))
    planner, executor = _planner(bus)
    result = planner.on_dpi_block(
        _event(bus, confidence=0.4, current_transport="reality")
    )
    assert result.decision is Decision.OBSERVE
    assert result.executed is False
    assert executor.calls == []


def test_high_confidence_auto_executes_on_test_profile(tmp_path):
    bus = EventBus(str(tmp_path))
    planner, executor = _planner(bus)
    result = planner.on_dpi_block(
        _event(bus, confidence=0.95, current_transport="reality")
    )
    assert result.decision is Decision.AUTO_EXECUTE
    assert result.target_transport == "xhttp"
    assert result.executed is True
    assert result.dry_run is True
    assert executor.calls[0][1]["profile"] == "ghost-test-canary"


def test_mid_confidence_holds_for_dao_when_no_gate(tmp_path):
    bus = EventBus(str(tmp_path))
    planner, executor = _planner(bus)
    result = planner.on_dpi_block(
        _event(bus, confidence=0.7, current_transport="reality")
    )
    assert result.decision is Decision.DAO_VOTE
    assert result.executed is False  # no DAO gate wired -> held pending
    assert executor.calls == []


def test_mid_confidence_executes_when_dao_approves(tmp_path):
    bus = EventBus(str(tmp_path))

    class _ApprovingDao:
        def request_vote(self, proposal):
            return True

    backend = TestProfileSwitchBackend(test_profile="ghost-test-canary", dry_run=True)
    executor = _RecordingExecutor(backend)
    planner = DpiHealingPlanner(
        bus, executor, test_profile="ghost-test-canary", dao_gate=_ApprovingDao()
    )
    result = planner.on_dpi_block(
        _event(bus, confidence=0.7, current_transport="reality")
    )
    assert result.decision is Decision.DAO_VOTE
    assert result.executed is True


def test_backend_refuses_non_test_profile():
    backend = TestProfileSwitchBackend(test_profile="ghost-test-canary", dry_run=True)
    with pytest.raises(PermissionError):
        backend.switch_protocol("xhttp", "http", profile="prod-nl-live")


def test_subscribe_reacts_to_published_event(tmp_path):
    bus = EventBus(str(tmp_path))
    planner, executor = _planner(bus)
    planner.subscribe()
    bus.publish(
        EventType.DPI_BLOCK_DETECTED,
        "tspu-detector",
        {"confidence": 0.95, "current_transport": "reality"},
    )
    # The sync subscriber ran the planner, which drove the executor.
    assert executor.calls
    assert executor.calls[0][1]["protocol"] == "xhttp"


def _event(bus: EventBus, *, confidence: float, current_transport: str):
    return planner_mod.Event(
        event_type=EventType.DPI_BLOCK_DETECTED,
        source_agent="tspu-detector",
        data={"confidence": confidence, "current_transport": current_transport},
    )
