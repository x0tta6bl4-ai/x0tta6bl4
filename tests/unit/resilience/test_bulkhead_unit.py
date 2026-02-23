"""Focused unit tests for src.resilience.bulkhead."""

from __future__ import annotations

import pytest

from src.resilience.bulkhead import (
    AdaptiveBulkhead,
    BulkheadFullException,
    BulkheadRegistry,
    BulkheadStats,
    BulkheadType,
    PartitionedBulkhead,
    QueueBulkhead,
    SemaphoreBulkhead,
    bulkhead,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    registry = BulkheadRegistry()
    snapshot = dict(registry._bulkheads)
    registry._bulkheads.clear()
    try:
        yield
    finally:
        registry._bulkheads.clear()
        registry._bulkheads.update(snapshot)


def test_bulkhead_stats_to_dict_calculates_rates():
    stats = BulkheadStats(
        name="x",
        max_concurrent=4,
        current_count=2,
        queue_size=0,
        total_calls=10,
        accepted_calls=8,
        rejected_calls=1,
        timeout_calls=1,
        avg_wait_time_ms=1.2,
        avg_execution_time_ms=2.3,
    )

    as_dict = stats.to_dict()
    assert as_dict["utilization"] == 0.5
    assert as_dict["accept_rate"] == 0.8


def test_semaphore_bulkhead_try_enter_and_execute_over_capacity():
    bh = SemaphoreBulkhead(max_concurrent=1, name="sem")
    assert bh.try_enter() is True
    assert bh.try_enter() is False

    with pytest.raises(BulkheadFullException) as exc:
        bh.execute(lambda: "never")

    assert exc.value.max_concurrent == 1
    assert exc.value.current_count == 1
    bh.exit()

    stats = bh.get_stats()
    assert stats.total_calls == 3
    assert stats.accepted_calls == 1
    assert stats.rejected_calls == 1
    assert stats.timeout_calls == 1


def test_semaphore_bulkhead_execute_releases_on_exception():
    bh = SemaphoreBulkhead(max_concurrent=1, name="sem-err")

    with pytest.raises(RuntimeError):
        bh.execute(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    stats = bh.get_stats()
    assert stats.current_count == 0
    assert stats.accepted_calls == 1
    assert stats.total_calls == 1


class _AlwaysFalseSemaphore:
    def acquire(self, **_kwargs):
        return False

    def release(self):
        return None


class _RaisingSemaphore:
    def acquire(self, **_kwargs):
        raise RuntimeError("acquire failed")

    def release(self):
        return None


def test_queue_bulkhead_enter_timeout_increments_metric():
    bh = QueueBulkhead(max_concurrent=1, queue_size=2, name="queue", max_wait_ms=1)
    bh._semaphore = _AlwaysFalseSemaphore()

    assert bh.enter(timeout_ms=1) is False
    stats = bh.get_stats()
    assert stats.timeout_calls == 1
    assert stats.queue_size == 0


def test_queue_bulkhead_enter_exception_cleans_queue():
    bh = QueueBulkhead(max_concurrent=1, queue_size=2, name="queue-err", max_wait_ms=1)
    bh._semaphore = _RaisingSemaphore()

    with pytest.raises(RuntimeError, match="acquire failed"):
        bh.enter(timeout_ms=1)

    stats = bh.get_stats()
    assert stats.queue_size == 0


def test_queue_bulkhead_rejects_when_queue_is_full():
    bh = QueueBulkhead(max_concurrent=1, queue_size=1, name="queue-full")
    bh._current_queue_size = 1

    assert bh.enter(timeout_ms=1) is False
    stats = bh.get_stats()
    assert stats.rejected_calls == 1


def test_partitioned_bulkhead_partition_selection_and_aggregate_stats():
    bh = PartitionedBulkhead(partitions={"critical": 1, "default": 2}, name="part")
    assert bh.execute(lambda x: x + 1, "critical", 3) == 4

    agg = bh.get_aggregate_stats()
    assert agg["partition_count"] == 2
    assert agg["accepted_calls"] >= 1
    assert "critical" in agg["partitions"]


def test_partitioned_bulkhead_unknown_partition_raises():
    bh = PartitionedBulkhead(partitions={"default": 1}, name="part2")
    with pytest.raises(ValueError, match="Unknown partition"):
        bh.try_enter("missing")


def test_adaptive_adjust_capacity_down_and_up():
    bh = AdaptiveBulkhead(
        initial_capacity=10,
        min_capacity=5,
        max_capacity=20,
        name="adaptive",
        adjustment_window=2,
    )

    bh.ewma_error_rate = 0.4
    bh._adjust_capacity()
    lowered = bh.current_capacity
    assert 5 <= lowered < 10

    bh.ewma_error_rate = 0.0
    bh.ewma_response_time = 20.0
    bh.current_capacity = 10
    bh._adjust_capacity()
    assert bh.current_capacity > 10


def test_adaptive_execute_triggers_periodic_adjustment(monkeypatch):
    bh = AdaptiveBulkhead(
        initial_capacity=2,
        min_capacity=1,
        max_capacity=4,
        name="adaptive-window",
        adjustment_window=2,
    )
    called = {"count": 0}

    def _mark_adjust():
        called["count"] += 1

    monkeypatch.setattr(bh, "_adjust_capacity", _mark_adjust)

    assert bh.execute(lambda: "ok") == "ok"
    assert bh.execute(lambda: "ok2") == "ok2"
    assert called["count"] == 1


def test_adaptive_execute_raises_when_enter_fails(monkeypatch):
    bh = AdaptiveBulkhead(
        initial_capacity=3,
        min_capacity=1,
        max_capacity=5,
        name="adaptive-full",
    )
    bh._bulkhead._current_count = 3
    monkeypatch.setattr(bh, "enter", lambda timeout_ms=None: False)

    with pytest.raises(BulkheadFullException) as exc:
        bh.execute(lambda: "never")

    assert exc.value.max_concurrent == 3
    assert exc.value.current_count == 3


def test_registry_health_check_flags_utilization_and_reject_rate():
    class _StatBulkhead:
        def get_stats(self):
            return {
                "utilization": 0.95,
                "rejected_calls": 2,
                "total_calls": 10,
            }

    registry = BulkheadRegistry()
    registry.register("hot", _StatBulkhead())

    health = registry.health_check()
    issues = {(i["issue"], i["bulkhead"]) for i in health["issues"]}
    assert ("high_utilization", "hot") in issues
    assert ("high_reject_rate", "hot") in issues


def test_decorator_queue_registers_and_executes():
    @bulkhead(
        max_concurrent=1,
        name="decorator_queue",
        bulkhead_type=BulkheadType.QUEUE,
        queue_size=2,
        max_wait_ms=10,
    )
    def _work(x):
        return x * 2

    assert _work(3) == 6
    assert isinstance(_work.bulkhead, QueueBulkhead)
    assert BulkheadRegistry().get("decorator_queue") is _work.bulkhead


def test_decorator_falls_back_to_semaphore_for_other_type():
    @bulkhead(
        max_concurrent=1,
        name="decorator_fallback",
        bulkhead_type=BulkheadType.PARTITIONED,
    )
    def _work():
        return "ok"

    assert _work() == "ok"
    assert isinstance(_work.bulkhead, SemaphoreBulkhead)
