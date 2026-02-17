import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.core.memory_profiler as memory_profiler
from src.core.memory_profiler import MemoryProfiler, MemoryStats


def _make_profiler(
    monkeypatch: pytest.MonkeyPatch, *, enable_tracemalloc: bool
) -> MemoryProfiler:
    process = MagicMock()
    process.memory_info.return_value = SimpleNamespace(
        rss=200 * 1024 * 1024, vms=512 * 1024 * 1024
    )
    process.cpu_percent.return_value = 12.5
    monkeypatch.setattr(memory_profiler.psutil, "Process", lambda: process)
    return MemoryProfiler(enable_tracemalloc=enable_tracemalloc)


def test_get_current_stats_without_tracemalloc(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    stats = profiler.get_current_stats()
    assert isinstance(stats, MemoryStats)
    assert stats.rss_mb == pytest.approx(200.0)
    assert stats.vms_mb == pytest.approx(512.0)
    assert stats.tracemalloc_mb == 0
    assert stats.peak_tracemalloc_mb == 0
    assert stats.cpu_percent == pytest.approx(12.5)


def test_get_current_stats_with_tracemalloc(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler.enable_tracemalloc = True
    monkeypatch.setattr(
        memory_profiler.tracemalloc,
        "get_traced_memory",
        lambda: (5 * 1024 * 1024, 9 * 1024 * 1024),
    )
    stats = profiler.get_current_stats()
    assert stats.tracemalloc_mb == pytest.approx(5.0)
    assert stats.peak_tracemalloc_mb == pytest.approx(9.0)


def test_get_current_stats_tracemalloc_error_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler.enable_tracemalloc = True
    monkeypatch.setattr(
        memory_profiler.tracemalloc,
        "get_traced_memory",
        lambda: (_ for _ in ()).throw(RuntimeError("trace failed")),
    )

    caplog.set_level("WARNING")
    stats = profiler.get_current_stats()
    assert stats.tracemalloc_mb == 0
    assert stats.peak_tracemalloc_mb == 0
    assert "Failed to get tracemalloc stats" in caplog.text


def test_log_memory_usage_emits_info(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    caplog.set_level("INFO")
    profiler.log_memory_usage("check")
    assert "check: RSS=200.0MB" in caplog.text


def test_start_monitoring_starts_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    started = {"value": False}

    class DummyThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started["value"] = True

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(memory_profiler.threading, "Thread", DummyThread)
    profiler.start_monitoring(interval_seconds=1.5)
    assert profiler._monitoring is True
    assert started["value"] is True
    profiler.stop_monitoring()


def test_start_monitoring_when_already_running_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler._monitoring = True
    caplog.set_level("WARNING")
    profiler.start_monitoring()
    assert "already running" in caplog.text


def test_stop_monitoring_joins_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    joined = {"value": False}

    class DummyThread:
        def join(self, timeout=None):
            joined["value"] = True

    profiler._monitoring = True
    profiler._monitor_thread = DummyThread()
    profiler.stop_monitoring()
    assert profiler._monitoring is False
    assert joined["value"] is True


def test_stop_monitoring_noop_when_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler._monitoring = False
    profiler._monitor_thread = None
    profiler.stop_monitoring()
    assert profiler._monitoring is False


def test_monitor_loop_caps_history_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler._stats_history = [MemoryStats(1, 1, 0, 0, 0, 0) for _ in range(1000)]

    def fake_stats():
        profiler._monitoring = False
        return MemoryStats(900, 1000, 0, 0, 1, 123.0)

    monkeypatch.setattr(profiler, "get_current_stats", fake_stats)
    monkeypatch.setattr(memory_profiler.time, "sleep", lambda _: None)
    caplog.set_level("WARNING")
    profiler._monitoring = True
    profiler._monitor_loop(interval=0.0)
    assert len(profiler._stats_history) == 1000
    assert "High memory usage detected" in caplog.text


def test_monitor_loop_logs_error_on_stats_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)

    def _raise():
        raise RuntimeError("stats failed")

    def _sleep(_):
        profiler._monitoring = False

    monkeypatch.setattr(profiler, "get_current_stats", _raise)
    monkeypatch.setattr(memory_profiler.time, "sleep", _sleep)
    caplog.set_level("ERROR")

    profiler._monitoring = True
    profiler._monitor_loop(interval=0.0)
    assert "Error in memory monitoring: stats failed" in caplog.text


def test_get_memory_report_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    assert profiler.get_memory_report() == {"error": "Tracemalloc not enabled"}


def test_get_memory_report_success(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler.enable_tracemalloc = True

    @dataclass
    class _TB:
        filename: str
        lineno: int

    @dataclass
    class _Stat:
        size: int
        count: int
        traceback: list[_TB]

    class _Snapshot:
        def statistics(self, _):
            return [
                _Stat(
                    size=1024 * 1024,
                    count=3,
                    traceback=[_TB(filename="a.py", lineno=10)],
                ),
                _Stat(
                    size=2 * 1024 * 1024,
                    count=1,
                    traceback=[_TB(filename="b.py", lineno=20)],
                ),
            ]

    monkeypatch.setattr(
        memory_profiler.tracemalloc, "take_snapshot", lambda: _Snapshot()
    )
    monkeypatch.setattr(
        profiler,
        "get_current_stats",
        lambda: MemoryStats(10, 20, 1, 2, 3, 4),
    )
    report = profiler.get_memory_report()
    assert report["total_tracked"] == 2
    assert len(report["top_allocations"]) == 2
    assert report["top_allocations"][0]["file"] == "a.py"
    assert report["current_stats"].rss_mb == 10


def test_get_memory_report_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler.enable_tracemalloc = True
    monkeypatch.setattr(
        memory_profiler.tracemalloc,
        "take_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert profiler.get_memory_report() == {"error": "boom"}


def test_global_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    monkeypatch.setattr(memory_profiler, "_memory_profiler", fake)
    assert memory_profiler.get_memory_profiler() is fake
    memory_profiler.log_memory_usage("x")
    fake.log_memory_usage.assert_called_once_with("x")


def test_get_stats_history_returns_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    profiler = _make_profiler(monkeypatch, enable_tracemalloc=False)
    profiler._stats_history = [MemoryStats(1, 2, 0, 0, 0, 1.0)]

    history = profiler.get_stats_history()
    assert history == profiler._stats_history
    assert history is not profiler._stats_history
