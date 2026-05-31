import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
from src.coordination.events import EventBus, EventType
from src.network.ebpf.telemetry import map_reader as mod
from src.network.ebpf.telemetry.models import TelemetryConfig
from src.network.ebpf.telemetry.security import SecurityManager


def _reader(tmp_path, monkeypatch, *, bpftool_available=False):
    monkeypatch.setattr(
        mod.MapReader,
        "_check_bpftool",
        lambda _self: bpftool_available,
    )
    config = TelemetryConfig(read_timeout=0.1)
    return mod.MapReader(
        config,
        SecurityManager(config),
        event_bus=EventBus(project_root=str(tmp_path)),
    )


def _events(reader, limit=10):
    return reader.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-map-reader",
        limit=limit,
    )


def _stage_payload(reader, stage):
    matches = [event.data for event in _events(reader, limit=20) if event.data["stage"] == stage]
    assert matches, f"missing stage {stage}"
    return matches[-1]


def test_bpftool_probe_publishes_returncode_and_redacted_output(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("X0TTA6BL4_SERVICE_SPIFFE_ID", "spiffe://secret/map-reader")
    monkeypatch.setenv("X0TTA6BL4_SERVICE_DID", "did:mesh:secret-map-reader")
    monkeypatch.setenv(
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    )
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

    config = TelemetryConfig(read_timeout=0.1)
    reader = mod.MapReader(
        config,
        SecurityManager(config),
        event_bus=EventBus(project_root=str(tmp_path)),
    )

    assert reader.bpftool_available is True
    payload = _stage_payload(reader, "bpftool_probe_completed")
    assert payload["service_name"] == "ebpf-map-reader"
    assert payload["layer"] == "network_ebpf_map_reader_observed_state"
    assert payload["operation"] == "check_bpftool"
    assert payload["returncode"] == 0
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        secret_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sample_redacted"] is True
    assert payload["identity"]["spiffe_id_configured"] is True
    assert payload["identity"]["redacted"] is True
    text = str(payload)
    assert secret_stdout not in text
    assert secret_stderr not in text
    assert "spiffe://secret" not in text
    assert "did:mesh:secret" not in text
    assert "0xeeee" not in text


def test_read_map_all_backends_failed_publishes_redacted_empty_evidence(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_name = "secret_process_map"

    result = reader.read_map(None, map_name)

    assert result == {}
    events = _events(reader, limit=5)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "map_read_empty"
    assert payload["backend"] == "none"
    assert payload["result"] == "empty"
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_name_redacted"] is True
    assert payload["bcc_available"] is False
    assert payload["bpftool_available"] is False
    assert payload["payloads_redacted"] is True
    assert payload["safe_observation"] is True
    assert map_name not in str(payload)


def test_bpftool_map_read_success_publishes_redacted_output_and_result_keys(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_name = "secret_process_map"
    secret_key = "secret_peer_key"
    stdout = json.dumps({"data": [{"key": secret_key, "value": 7}]})
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(returncode=0, stdout=stdout, stderr=""),
    )

    result = reader.read_map_via_bpftool(map_name)

    assert result == {secret_key: 7}
    payload = _stage_payload(reader, "bpftool_map_read_completed")
    assert payload["operation"] == "read_map_via_bpftool"
    assert payload["returncode"] == 0
    assert payload["raw_entries_count"] == 1
    assert payload["stdout_metadata"]["bytes"] == len(stdout.encode("utf-8"))
    assert payload["result_key_hashes"]["hashes"] == [
        hashlib.sha256(secret_key.encode("utf-8")).hexdigest()
    ]
    text = str(payload)
    assert map_name not in text
    assert secret_key not in text


def test_bpftool_map_read_failure_publishes_returncode_and_redacted_stderr(
    monkeypatch,
    tmp_path,
):
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

    payload = _stage_payload(reader, "bpftool_map_read_failed")
    assert payload["returncode"] == 7
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        secret_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sha256"] == hashlib.sha256(
        secret_stderr.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert map_name not in text
    assert secret_stdout not in text
    assert secret_stderr not in text


def test_bpftool_map_read_timeout_publishes_redacted_failure(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_name = "secret_timeout_map"

    def _timeout(*args, **kwargs):
        raise mod.subprocess.TimeoutExpired(["bpftool", "secret"], 0.1)

    monkeypatch.setattr(mod.subprocess, "run", _timeout)

    with pytest.raises(RuntimeError, match="bpftool timeout reading map"):
        reader.read_map_via_bpftool(map_name)

    payload = _stage_payload(reader, "bpftool_map_read_timeout")
    assert payload["returncode"] == 124
    assert payload["error_type"] == "TimeoutExpired"
    assert payload["error_message_redacted"] is True
    assert map_name not in str(payload)


def test_read_map_bcc_failure_bpftool_success_publishes_backend_evidence(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    reader = _reader(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_latency_map"

    with (
        patch.object(
            reader,
            "read_map_via_bcc",
            side_effect=RuntimeError("secret bcc failure"),
        ),
        patch.object(reader, "read_map_via_bpftool", return_value={"k": 1}),
    ):
        result = reader.read_map(object(), map_name)

    assert result == {"k": 1}
    events = _events(reader, limit=5)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "map_read_succeeded"
    assert payload["backend"] == "bpftool"
    assert payload["reason"] == "bcc_failed_bpftool_succeeded"
    assert payload["result_count"] == 1
    assert payload["bpf_program_present"] is True
    assert payload["bcc_error_type"] == "RuntimeError"
    assert payload["bcc_error_message_redacted"] is True
    assert map_name not in str(payload)
    assert "secret bcc failure" not in str(payload)
