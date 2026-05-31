import hashlib
import subprocess
from types import SimpleNamespace

from src.coordination.events import EventBus, EventType
from src.network.ebpf import profiler as profiler_mod
from src.network.ebpf.profiler import EBPF_PROFILER_SERVICE_NAME, EBPFProfiler


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=EBPF_PROFILER_SERVICE_NAME,
        limit=80,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _advancing_time(step: float = 0.01):
    state = {"t": 0.0}

    def _time():
        state["t"] += step
        return state["t"]

    return _time


def test_network_impact_publishes_redacted_ping_and_socket_evidence(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    profiler = EBPFProfiler(process_name="secret-profiler", event_bus=bus)

    class _Sock:
        def sendto(self, data, addr):
            return len(data)

        def close(self):
            return None

    ping_stdout = "rtt min/avg/max/mdev = 0.1/0.2/0.3/0.4 ms secret-output"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=ping_stdout,
            stderr="secret-stderr",
        ),
    )
    monkeypatch.setattr(profiler_mod.socket, "socket", lambda *args, **kwargs: _Sock())
    monkeypatch.setattr(profiler_mod.time, "time", _advancing_time(0.005))
    monkeypatch.setattr(profiler_mod.time, "sleep", lambda _s: None)

    metrics = profiler.profile_network_impact(duration=0.02, packet_rate=100)

    assert metrics["baseline_latency_ms"] == 0.2

    ping_payload = _stage_payload(bus, "ebpf_profiler_ping_completed")
    throughput_payload = _stage_payload(
        bus,
        "ebpf_profiler_loopback_throughput_measured",
    )
    final_payload = _stage_payload(bus, "ebpf_profiler_network_impact_profiled")

    assert ping_payload["operation"] == "run_ping_latency_probe"
    assert ping_payload["returncode"] == 0
    assert ping_payload["parsed_summary"]["latency_ms"] == 0.2
    assert ping_payload["output"]["stdout_chars"] == len(ping_stdout)
    assert ping_payload["target_hash"] == hashlib.sha256(b"127.0.0.1").hexdigest()
    assert throughput_payload["parsed_summary"]["packets_sent"] > 0
    assert throughput_payload["payload_redacted"] is True
    assert final_payload["parsed_summary"]["latency_measurement_mode"] == "ping"
    assert final_payload["parsed_summary"]["throughput_measurement_mode"] == "socket"
    payload_text = str(_events(bus))
    assert "secret-profiler" not in payload_text
    assert "secret-output" not in payload_text
    assert "secret-stderr" not in payload_text
    assert "127.0.0.1" not in payload_text


def test_ping_unavailable_publishes_simulated_fallback_evidence(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    profiler = EBPFProfiler(process_name="secret-profiler", event_bus=bus)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            FileNotFoundError("secret ping missing")
        ),
    )

    latency, mode = profiler._run_ping_latency_probe()

    assert latency == 1.0
    assert mode == "simulated"
    payload = _stage_payload(bus, "ebpf_profiler_ping_unavailable")
    assert payload["status"] == "failure"
    assert payload["parsed_summary"]["fallback"] is True
    assert payload["error"]["message_redacted"] is True
    assert "secret ping missing" not in str(payload)
    assert "secret-profiler" not in str(payload)


def test_ping_runtime_failure_profiles_defaults_with_redacted_error(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    profiler = EBPFProfiler(process_name="secret-profiler", event_bus=bus)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("secret ping exploded")
        ),
    )

    metrics = profiler.profile_network_impact(duration=0.01, packet_rate=100)

    assert metrics["baseline_throughput_mbps"] == 100.0
    assert metrics["ebpf_throughput_mbps"] == 98.0
    ping_payload = _stage_payload(bus, "ebpf_profiler_ping_failed")
    failed_payload = _stage_payload(bus, "ebpf_profiler_network_impact_failed")
    final_payload = _stage_payload(bus, "ebpf_profiler_network_impact_profiled")

    assert ping_payload["error"]["message_redacted"] is True
    assert failed_payload["parsed_summary"]["fallback"] is True
    assert final_payload["parsed_summary"]["latency_measurement_mode"] == "simulated"
    assert "secret ping exploded" not in str(_events(bus))
    assert "secret-profiler" not in str(_events(bus))


def test_baseline_and_overhead_summaries_publish_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    profiler = EBPFProfiler(process_name="secret-profiler", event_bus=bus)

    class _Process:
        def __init__(self):
            self.values = [3.0, 5.0, 7.0]
            self.index = 0

        def cpu_percent(self, interval=0.1):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

        def memory_info(self):
            return SimpleNamespace(rss=64 * 1024 * 1024)

    process = _Process()
    monkeypatch.setattr(profiler, "_find_process", lambda: process)
    monkeypatch.setattr(profiler_mod.time, "time", _advancing_time(0.11))
    monkeypatch.setattr(profiler_mod.time, "sleep", lambda _s: None)

    profiler.measure_baseline(duration=0.3)
    result = profiler.profile_overhead(duration=0.3, ebpf_programs_count=2)

    baseline_payload = _stage_payload(bus, "ebpf_profiler_baseline_measured")
    overhead_payload = _stage_payload(bus, "ebpf_profiler_overhead_profiled")

    assert baseline_payload["parsed_summary"]["cpu_samples"] > 0
    assert overhead_payload["parsed_summary"]["samples_collected"] > 0
    assert overhead_payload["parsed_summary"]["ebpf_programs_active"] == 2
    assert result.ebpf_programs_active == 2
    assert baseline_payload["process_name_hash"] == hashlib.sha256(
        b"secret-profiler"
    ).hexdigest()
    assert "secret-profiler" not in str(_events(bus))
