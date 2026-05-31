import hashlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.coordination.events import EventBus, EventType
from src.network.ebpf import telemetry_module as mod


def _events(reader):
    return reader.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod.EBPF_TELEMETRY_MODULE_SERVICE_NAME,
        limit=50,
    )


def _stage_payload(reader, stage):
    matches = [event.data for event in _events(reader) if event.data["stage"] == stage]
    assert matches, f"missing stage {stage}"
    return matches[-1]


def _reader(tmp_path, monkeypatch, *, bpftool_available=False):
    monkeypatch.setattr(
        mod.MapReader,
        "_check_bpftool",
        lambda _self: bpftool_available,
    )
    config = mod.TelemetryConfig(read_timeout=0.1)
    return mod.MapReader(
        config,
        mod.SecurityManager(config),
        event_bus=EventBus(project_root=str(tmp_path)),
    )


def test_bpftool_probe_publishes_redacted_command_output(monkeypatch, tmp_path):
    secret_stdout = "bpftool secret version"
    secret_stderr = "secret warning"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(
            returncode=0,
            stdout=secret_stdout,
            stderr=secret_stderr,
        ),
    )

    config = mod.TelemetryConfig()
    reader = mod.MapReader(
        config,
        mod.SecurityManager(config),
        event_bus=EventBus(project_root=str(tmp_path)),
    )

    assert reader.bpftool_available is True
    payload = _stage_payload(reader, "telemetry_bpftool_probe_completed")
    assert payload["service_name"] == mod.EBPF_TELEMETRY_MODULE_SERVICE_NAME
    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["bpftool_available"] is True
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        secret_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sample_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert secret_stdout not in str(payload)
    assert secret_stderr not in str(payload)


def test_bpftool_map_read_failure_publishes_redacted_output(monkeypatch, tmp_path):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_name = "secret_latency_map"
    secret_stdout = json.dumps({"secret": "value"})
    secret_stderr = "secret bpftool failure"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(
            returncode=7,
            stdout=secret_stdout,
            stderr=secret_stderr,
        ),
    )

    with pytest.raises(RuntimeError, match="bpftool failed"):
        reader.read_map_via_bpftool(map_name)

    payload = _stage_payload(reader, "telemetry_bpftool_map_read_failed")
    assert payload["returncode"] == 7
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["stdout_metadata"]["bytes"] == len(secret_stdout.encode("utf-8"))
    assert payload["stderr_metadata"]["sha256"] == hashlib.sha256(
        secret_stderr.encode("utf-8")
    ).hexdigest()
    assert payload["map_name_redacted"] is True
    assert map_name not in str(payload)
    assert secret_stdout not in str(payload)
    assert secret_stderr not in str(payload)


def test_read_map_bcc_failure_bpftool_success_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    reader = _reader(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_route_map"
    secret_key = "secret_peer_key"

    with (
        patch.object(
            reader,
            "read_map_via_bcc",
            side_effect=RuntimeError("secret bcc failure"),
        ),
        patch.object(reader, "read_map_via_bpftool", return_value={secret_key: 1}),
    ):
        result = reader.read_map(object(), map_name, use_cache=False)

    assert result == {secret_key: 1}
    payload = _stage_payload(reader, "telemetry_map_read_completed")
    assert payload["source_mode"] == "bpftool"
    assert payload["parsed_summary"]["backend"] == "bpftool"
    assert payload["parsed_summary"]["bcc_failed_first"] is True
    assert payload["parsed_summary"]["result_count"] == 1
    assert payload["bcc_error"]["type"] == "RuntimeError"
    assert payload["bcc_error"]["message_redacted"] is True
    assert payload["result_key_hashes"]["hashes"] == [
        hashlib.sha256(secret_key.encode("utf-8")).hexdigest()
    ]
    assert map_name not in str(payload)
    assert secret_key not in str(payload)
    assert "secret bcc failure" not in str(payload)


def test_read_multiple_maps_publishes_redacted_batch_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_names = ["secret_map_a", "secret_map_b"]

    result = reader.read_multiple_maps(None, map_names)

    assert result == {"secret_map_a": {}, "secret_map_b": {}}
    payload = _stage_payload(reader, "telemetry_multiple_maps_read_completed")
    assert payload["parsed_summary"]["maps_requested"] == 2
    assert payload["parsed_summary"]["empty_results"] == 2
    assert payload["map_name_hashes"]["count"] == 2
    assert payload["map_names_redacted"] is True
    assert "secret_map_a" not in str(payload)
    assert "secret_map_b" not in str(payload)


def test_collector_passes_event_bus_to_legacy_map_reader(monkeypatch, tmp_path):
    monkeypatch.setattr(mod.MapReader, "_check_bpftool", lambda _self: False)
    config = mod.TelemetryConfig()
    bus = EventBus(project_root=str(tmp_path))

    collector = mod.EBPFTelemetryCollector(config, event_bus=bus)

    assert collector.event_bus is bus
    assert collector.map_reader.event_bus is bus
