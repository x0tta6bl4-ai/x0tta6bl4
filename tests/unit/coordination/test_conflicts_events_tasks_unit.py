"""Focused unit tests for coordination conflicts/events/tasks modules."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.coordination.conflicts import (
    Conflict,
    ConflictDetector,
    ConflictSeverity,
    ConflictType,
    ResolutionStrategy,
)
from src.coordination.events import (
    Event,
    EventBus,
    EventType,
    emit_conflict_detected,
    emit_pipeline_handoff,
    emit_task_created,
)
from src.coordination.state import AgentCoordinator, AgentRole, AgentStatus
from src.coordination.tasks import Task, TaskPriority, TaskQueue, TaskStatus, TaskType


def test_event_roundtrip_ack_and_full_ack():
    event = Event(
        event_type=EventType.TASK_CREATED,
        source_agent="agent-a",
        data={"task_id": "t1"},
        target_agents={"agent-b", "agent-c"},
        requires_ack=True,
    )
    as_dict = event.to_dict()
    loaded = Event.from_dict(as_dict)

    assert loaded.event_type == EventType.TASK_CREATED
    assert loaded.requires_ack is True
    assert loaded.is_fully_acked({"agent-b"}) is False
    loaded.ack("agent-b")
    loaded.ack("agent-c")
    assert loaded.is_fully_acked({"agent-b", "agent-c"}) is True


def test_event_bus_publish_pending_ack_and_replay(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    seen = []
    bus.subscribe(EventType.LOCK_ACQUIRED, lambda ev: seen.append(ev.event_id))

    event = bus.publish(
        EventType.LOCK_ACQUIRED,
        "agent-a",
        {"path": "src/a.py"},
        target_agents={"agent-b"},
        requires_ack=True,
    )

    assert event.event_id in seen
    assert bus.get_pending_acks("agent-b")[0].event_id == event.event_id
    assert bus.ack_event(event.event_id, "agent-b") is True
    assert bus.get_pending_acks("agent-b") == []

    history = bus.get_event_history(event_type=EventType.LOCK_ACQUIRED)
    assert len(history) == 1
    replay = bus.replay_events("agent-b")
    assert replay[0].event_id == event.event_id


def test_event_emit_helpers_wire_payloads(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    created = emit_task_created(bus, "agent-a", "t1", "code.implement", ["src/x.py"], assigned_to="agent-b")
    assert created.event_type == EventType.TASK_CREATED
    assert created.target_agents == {"agent-b"}

    handoff = emit_pipeline_handoff(bus, "agent-a", "agent-c", "review", ["a.diff"])
    assert handoff.event_type == EventType.PIPELINE_HANDOFF
    assert handoff.requires_ack is True

    conflict = emit_conflict_detected(bus, "agent-a", "lock", "src/y.py", ["agent-b"])
    assert conflict.event_type == EventType.CONFLICT_DETECTED
    assert conflict.priority == 10


def test_task_roundtrip_ready_overdue_and_duration():
    task = Task(
        task_type=TaskType.CODE_IMPLEMENT,
        title="Implement feature",
        depends_on={"dep1"},
        deadline=datetime.utcnow() - timedelta(seconds=1),
    )
    assert task.is_ready(set()) is False
    assert task.is_ready({"dep1"}) is True
    assert task.is_overdue() is True
    assert task.duration() is None

    payload = task.to_dict()
    rebuilt = Task.from_dict(payload)
    assert rebuilt.task_type == TaskType.CODE_IMPLEMENT
    assert rebuilt.depends_on == {"dep1"}


def test_task_queue_unblocks_blocked_dependents(tmp_path):
    queue = TaskQueue(project_root=str(tmp_path))

    dep = queue.add_task(TaskType.DESIGN_ARCHITECTURE, "Design")
    child = queue.add_task(
        TaskType.CODE_IMPLEMENT,
        "Implement",
        depends_on={dep.task_id},
    )

    queue.update_task_status(child.task_id, TaskStatus.BLOCKED)
    assert queue.get_task(child.task_id).status == TaskStatus.BLOCKED

    assert queue.complete_task(dep.task_id, result="done") is True
    assert queue.get_task(child.task_id).status == TaskStatus.PENDING

    stats = queue.get_stats()
    assert stats["total"] == 2
    assert stats["by_status"]["completed"] == 1


def test_task_queue_create_pipeline_builds_dependency_chain(tmp_path):
    queue = TaskQueue(project_root=str(tmp_path))
    tasks = queue.create_pipeline(
        title="Feature X",
        description="Desc",
        files={"src/x.py"},
        priority=TaskPriority.BACKGROUND,
    )

    assert len(tasks) == 5
    assert tasks[1].depends_on == {tasks[0].task_id}
    assert tasks[3].depends_on == {tasks[1].task_id, tasks[2].task_id}
    assert tasks[2].priority == TaskPriority.BACKGROUND


def test_conflict_model_strategy_selection_and_resolution(tmp_path):
    coordinator = AgentCoordinator(project_root=str(tmp_path))
    coordinator.register_agent("a", AgentRole.CODER)
    coordinator.register_agent("b", AgentRole.REVIEWER)
    coordinator.register_agent("c", AgentRole.ARCHITECT)

    coordinator.update_agent_status("a", AgentStatus.WORKING, "src/feature")
    coordinator.update_agent_status("c", AgentStatus.WORKING, "src/feature")

    detector = ConflictDetector(coordinator=coordinator, project_root=str(tmp_path))

    conflict = Conflict(
        conflict_id="c1",
        conflict_type=ConflictType.FILE_LOCK,
        severity=ConflictSeverity.MEDIUM,
        agents={"a", "b"},
        path="src/file.py",
        description="same file",
    )

    assert conflict.is_resolved() is False
    assert detector._select_strategy(conflict) == ResolutionStrategy.PRIORITY

    resolved = detector.resolve_conflict(conflict, strategy=ResolutionStrategy.PRIORITY)
    assert resolved.winner == "b"  # reviewer role has higher priority than coder
    assert conflict.is_resolved() is True

    coordinator.acquire_lock("a", "src/file.py")
    first_come_conflict = Conflict(
        conflict_id="c2",
        conflict_type=ConflictType.FILE_LOCK,
        severity=ConflictSeverity.MEDIUM,
        agents={"a", "c"},
        path="src/file.py",
        description="first come",
    )
    first_come = detector.resolve_conflict(first_come_conflict, strategy=ResolutionStrategy.FIRST_COME)
    assert first_come.winner == "a"


def test_conflict_detector_priority_conflict_detection(tmp_path):
    coordinator = AgentCoordinator(project_root=str(tmp_path))
    coordinator.register_agent("arch", AgentRole.ARCHITECT)
    coordinator.register_agent("res", AgentRole.RESEARCHER)
    coordinator.update_agent_status("arch", AgentStatus.WORKING, "src/shared")
    coordinator.update_agent_status("res", AgentStatus.WORKING, "src/shared")

    detector = ConflictDetector(coordinator=coordinator, project_root=str(tmp_path))
    conflicts = detector._detect_priority_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.PRIORITY
