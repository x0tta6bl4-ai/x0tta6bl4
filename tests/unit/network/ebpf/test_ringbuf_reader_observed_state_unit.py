import hashlib
import struct
from unittest.mock import Mock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf import ringbuf_reader as mod


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-ringbuf-reader",
        limit=10,
    )


def test_read_via_bpftool_success_publishes_redacted_map_check_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    map_name = "secret_ringbuf_map"
    reader = mod.RingBufferReader(map_name, event_bus=bus)
    stdout = "id 9 name secret_ringbuf_map type ringbuf"

    with patch(
        "src.network.ebpf.ringbuf_reader.subprocess.run",
        return_value=Mock(returncode=0, stdout=stdout, stderr=""),
    ):
        result = reader.read_via_bpftool()

    assert result == {
        "map_name": map_name,
        "exists": True,
        "note": "Use read_via_bcc() for actual event reading",
    }
    events = _events(bus)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "ringbuf_map_exists"
    assert payload["status"] == "success"
    assert payload["backend"] == "bpftool"
    assert payload["returncode"] == 0
    assert payload["bpftool_can_read_events"] is False
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_name_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["identity"]["redacted"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert map_name not in str(payload)
    assert stdout not in str(payload)


def test_read_via_bpftool_not_found_redacts_stderr(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    map_name = "secret_missing_ringbuf"
    stderr = "secret ringbuf map not found"
    reader = mod.RingBufferReader(map_name, event_bus=bus)

    with patch(
        "src.network.ebpf.ringbuf_reader.subprocess.run",
        return_value=Mock(returncode=2, stdout="", stderr=stderr),
    ):
        result = reader.read_via_bpftool()

    assert result is None
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ringbuf_map_missing"
    assert payload["status"] == "empty"
    assert payload["returncode"] == 2
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    assert map_name not in str(payload)
    assert stderr not in str(payload)


def test_read_via_bcc_unavailable_publishes_empty_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)
    bus = EventBus(project_root=str(tmp_path))
    map_name = "secret_bcc_ringbuf"
    reader = mod.RingBufferReader(map_name, event_bus=bus)

    reader.read_via_bcc(object())

    payload = _events(bus)[-1].data
    assert payload["stage"] == "ringbuf_bcc_unavailable"
    assert payload["status"] == "empty"
    assert payload["backend"] == "bcc"
    assert payload["bcc_available"] is False
    assert map_name not in str(payload)


def test_read_via_bcc_handler_failure_redacts_event_payload(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    bus = EventBus(project_root=str(tmp_path))
    reader = mod.RingBufferReader("secret_live_ringbuf", event_bus=bus)
    event_type = "secret_handler_type"

    def failing_handler(_event):
        raise RuntimeError("secret handler failure")

    reader.register_handler(event_type, failing_handler)

    class FakeRingBuffer:
        def open_ring_buffer(self, callback):
            data = struct.pack("IIHBBQ", 1, 2, 3, 4, 0, 5)
            callback(7, data, len(data))

        def poll(self, timeout=100):
            raise AssertionError("poll should not run while reader.running is false")

    class FakeBPF:
        def get_table(self, name):
            assert name == "secret_live_ringbuf"
            return FakeRingBuffer()

    reader.read_via_bcc(FakeBPF())

    events = _events(bus)
    stages = [event.data["stage"] for event in events]
    assert "ringbuf_handler_failed" in stages
    assert "ringbuf_bcc_opened" in stages
    failure_payload = next(
        event.data for event in events if event.data["stage"] == "ringbuf_handler_failed"
    )
    assert failure_payload["status"] == "failure"
    assert failure_payload["event_payload_redacted"] is True
    assert failure_payload["handler_event_type_hash"] == hashlib.sha256(
        event_type.encode("utf-8")
    ).hexdigest()
    assert failure_payload["event_size_bytes"] == struct.calcsize("IIHBBQ")
    assert failure_payload["cpu_id"] == 7
    assert "secret_live_ringbuf" not in str(failure_payload)
    assert event_type not in str(failure_payload)
    assert "secret handler failure" not in str(failure_payload)


def test_perf_event_callback_publishes_redacted_event_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    event_type = "secret_perf_events"
    reader = mod.PerfEventReader(event_type, event_bus=bus)

    reader._process_perf_event(3, b"secret raw perf bytes", 21)

    payload = _events(bus)[-1].data
    assert payload["stage"] == "perf_event_seen"
    assert payload["status"] == "success"
    assert payload["event_payload_redacted"] is True
    assert payload["event_type_hash"] == hashlib.sha256(
        event_type.encode("utf-8")
    ).hexdigest()
    assert payload["event_size_bytes"] == 21
    assert payload["cpu_id"] == 3
    assert event_type not in str(payload)
    assert "secret raw perf bytes" not in str(payload)
