from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.core.consciousness import ConsciousnessMetrics, ConsciousnessState
from src.core.mape_k_loop import MAPEKLoop


def _metrics(state: ConsciousnessState = ConsciousnessState.HARMONIC) -> ConsciousnessMetrics:
    return ConsciousnessMetrics(
        phi_ratio=1.0,
        state=state,
        frequency_alignment=1.0,
        entropy=0.0,
        harmony_index=1.0,
        mesh_health=1.0,
        timestamp=0.0,
    )


def _loop(tmp_path):
    consciousness = MagicMock()
    mesh = MagicMock()
    prometheus = MagicMock()
    zero_trust = MagicMock()
    dao_logger = AsyncMock()
    event_bus = EventBus(str(tmp_path))

    mesh.set_route_preference = AsyncMock(return_value=True)

    return MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        dao_logger=dao_logger,
        event_bus=event_bus,
        event_project_root=str(tmp_path),
    )


@pytest.mark.asyncio
async def test_planning_error_enters_safe_mode_without_control_action(tmp_path):
    loop = _loop(tmp_path)
    metric_snapshot = _metrics()
    loop._monitor = AsyncMock(return_value={"cpu_percent": 10.0})
    loop._analyze = AsyncMock(return_value=metric_snapshot)
    loop.consciousness.get_operational_directive.side_effect = RuntimeError(
        "planner unavailable"
    )

    await loop._execute_cycle()

    assert loop.safe_mode_active is True
    assert loop.safe_mode_reason_id == "planning_failed"
    loop.mesh.set_route_preference.assert_not_called()

    events = loop.event_bus.get_event_history(
        EventType.TASK_BLOCKED,
        source_agent="core-mapek-loop",
    )
    payload = events[-1].data
    assert payload["stage"] == "safe_mode_entered"
    assert payload["operation"] == "enter_safe_mode"
    assert payload["directives"]["safe_mode"] is True
    assert payload["directives"]["safe_mode_final_state"] == "control_actions_blocked"
    assert payload["result"]["keys"] == [
        "control_actions_blocked",
        "production_readiness_claim_allowed",
        "safe_mode_active",
        "success",
    ]


@pytest.mark.asyncio
async def test_cid_log_failure_enters_safe_mode(tmp_path):
    loop = _loop(tmp_path)
    loop.dao_logger.log_consciousness_event.side_effect = RuntimeError("cid down")
    metric_snapshot = _metrics(ConsciousnessState.MYSTICAL)
    setattr(metric_snapshot, "raw_metrics", {"cpu_percent": 99.0})

    await loop._knowledge(metric_snapshot, {"monitoring_interval_sec": 60}, [])

    assert loop.safe_mode_active is True
    assert loop.safe_mode_reason_id == "cid_log_failed"

    events = loop.event_bus.get_event_history(
        EventType.TASK_BLOCKED,
        source_agent="core-mapek-loop",
    )
    payload = events[-1].data
    assert payload["stage"] == "safe_mode_entered"
    assert payload["context"]["dependency"] == "cid_audit_log"
    assert payload["directives"]["safe_mode_reason_id"] == "cid_log_failed"
