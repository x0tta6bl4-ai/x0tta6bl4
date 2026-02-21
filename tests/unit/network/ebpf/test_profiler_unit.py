from __future__ import annotations

import builtins
import socket
import subprocess
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

import src.network.ebpf.profiler as mod


def _advancing_time(step: float = 0.11):
    state = {"t": 0.0}

    def _time():
        state["t"] += step
        return state["t"]

    return _time


class _Process:
    def __init__(self, cpu_values):
        self.cpu_values = list(cpu_values)
        self.i = 0

    def cpu_percent(self, interval=0.1):
        value = self.cpu_values[min(self.i, len(self.cpu_values) - 1)]
        self.i += 1
        return value

    def memory_info(self):
        return SimpleNamespace(rss=150 * 1024 * 1024)


def _make_result(target_met: bool) -> mod.CPUProfileResult:
    return mod.CPUProfileResult(
        timestamp=datetime(2026, 2, 16, 12, 0, 0),
        duration_seconds=1.0,
        avg_cpu_percent=1.2,
        max_cpu_percent=2.3,
        cpu_percentiles={"p50": 1.0, "p95": 2.0, "p99": 2.2},
        memory_mb=10.0,
        samples_collected=5,
        ebpf_programs_active=1,
        overhead_estimate=1.0 if target_met else 3.0,
        target_met=target_met,
    )


def test_measure_baseline_with_process_and_with_fallback(monkeypatch):
    profiler = mod.EBPFProfiler(process_name="x0tta6bl4")

    process = _Process([10.0, 20.0, 30.0])
    monkeypatch.setattr(profiler, "_find_process", lambda: process)
    monkeypatch.setattr(mod.time, "time", _advancing_time(0.11))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    avg_cpu, avg_mem = profiler.measure_baseline(duration=0.3)
    assert avg_cpu > 0.0
    assert avg_mem > 0.0
    assert profiler.baseline_cpu == avg_cpu
    assert profiler.baseline_memory == avg_mem

    profiler2 = mod.EBPFProfiler(process_name="x0tta6bl4")
    monkeypatch.setattr(profiler2, "_find_process", lambda: None)
    monkeypatch.setattr(mod.psutil, "cpu_percent", lambda interval=0.1: 5.0)
    monkeypatch.setattr(mod.time, "time", _advancing_time(0.11))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    avg_cpu2, avg_mem2 = profiler2.measure_baseline(duration=0.3)
    assert avg_cpu2 == 5.0
    assert avg_mem2 == 0.0


def test_profile_overhead_with_and_without_samples(monkeypatch):
    profiler = mod.EBPFProfiler(process_name="x0tta6bl4")
    profiler.baseline_cpu = 1.0

    process = _Process([5.0, 7.0, 9.0])
    monkeypatch.setattr(profiler, "_find_process", lambda: process)
    monkeypatch.setattr(mod.time, "time", _advancing_time(0.11))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    result = profiler.profile_overhead(duration=0.3, ebpf_programs_count=2)
    assert result.samples_collected > 0
    assert result.avg_cpu_percent > 0.0
    assert "p95" in result.cpu_percentiles
    assert result.ebpf_programs_active == 2

    profiler2 = mod.EBPFProfiler(process_name="x0tta6bl4")
    profiler2.baseline_cpu = 0.0
    monkeypatch.setattr(profiler2, "_find_process", lambda: None)
    monkeypatch.setattr(mod.time, "time", _advancing_time(0.11))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    empty = profiler2.profile_overhead(duration=0.3, ebpf_programs_count=1)
    assert empty.samples_collected == 0
    assert empty.target_met is False


def test_find_process_matches_name_and_handles_process_errors(monkeypatch):
    profiler = mod.EBPFProfiler(process_name="needle")

    class _BadProc:
        @property
        def info(self):
            raise mod.psutil.NoSuchProcess(pid=1)

    good_proc = SimpleNamespace(info={"name": "other", "cmdline": ["run", "needle"]})

    monkeypatch.setattr(mod.psutil, "process_iter", lambda _attrs: [_BadProc(), good_proc])
    found = profiler._find_process()
    assert found is good_proc

    monkeypatch.setattr(mod.psutil, "process_iter", lambda _attrs: [])
    assert profiler._find_process() is None


def test_profile_network_impact_paths(monkeypatch):
    profiler = mod.EBPFProfiler(process_name="x0tta6bl4")

    class _RunResult:
        returncode = 0
        stdout = "rtt min/avg/max/mdev = 0.1/0.2/0.3/0.4 ms"

    class _Sock:
        def sendto(self, data, addr):
            return len(data)

        def close(self):
            return None

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _RunResult())
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: _Sock())
    monkeypatch.setattr(mod.time, "time", _advancing_time(0.005))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    metrics = profiler.profile_network_impact(duration=0.02, packet_rate=100)
    assert metrics["baseline_latency_ms"] == 0.2
    assert metrics["ebpf_latency_ms"] > metrics["baseline_latency_ms"]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ping fail")),
    )
    defaults = profiler.profile_network_impact(duration=0.01, packet_rate=100)
    assert defaults["baseline_throughput_mbps"] == 100.0
    assert defaults["ebpf_throughput_mbps"] == 98.0


def test_generate_report_and_empty_result():
    profiler = mod.EBPFProfiler(process_name="x0tta6bl4")

    assert profiler.generate_report([]) == "No profiling results available."

    report = profiler.generate_report([_make_result(target_met=False)])
    assert "eBPF Telemetry CPU Overhead Profiling Report" in report
    assert "NOT MET" in report


def test_main_entry_point_success_and_failure(monkeypatch, tmp_path):
    class _ProfilerOK:
        def __init__(self, process_name="x0tta6bl4"):
            self.process_name = process_name

        def measure_baseline(self, duration=10.0):
            return (0.5, 10.0)

        def profile_overhead(self, duration=60.0, ebpf_programs_count=1):
            return _make_result(target_met=True)

        def generate_report(self, results):
            return "REPORT_OK"

    class _ProfilerFail(_ProfilerOK):
        def profile_overhead(self, duration=60.0, ebpf_programs_count=1):
            return _make_result(target_met=False)

        def generate_report(self, results):
            return "REPORT_FAIL"

    monkeypatch.setattr(
        builtins,
        "exit",
        lambda code=0: (_ for _ in ()).throw(SystemExit(code)),
    )

    out_path = tmp_path / "report.txt"
    monkeypatch.setattr(mod, "EBPFProfiler", _ProfilerOK)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profiler",
            "--duration",
            "0.1",
            "--baseline-duration",
            "0.1",
            "--programs",
            "2",
            "--output",
            str(out_path),
            "--process",
            "app",
        ],
    )

    with pytest.raises(SystemExit) as ok_exit:
        mod.main()
    assert ok_exit.value.code == 0
    assert out_path.read_text() == "REPORT_OK"

    monkeypatch.setattr(mod, "EBPFProfiler", _ProfilerFail)
    monkeypatch.setattr(sys, "argv", ["profiler", "--duration", "0.1"])

    with pytest.raises(SystemExit) as fail_exit:
        mod.main()
    assert fail_exit.value.code == 1
