import hashlib
import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from src.coordination.events import EventBus, EventType
from src.network.ebpf.metrics_exporter import (
    BpftoolError,
    EBPFMetricsExporter,
    ParseError,
    TimeoutError,
)


def _exporter(tmp_path):
    return EBPFMetricsExporter(
        prometheus_port=19090,
        event_bus=EventBus(project_root=str(tmp_path)),
    )


def _events(exporter):
    return exporter.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-metrics-exporter",
        limit=10,
    )


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "monitoring"
    assert "mape_k" in techniques
    assert "causal_analysis" in techniques
    assert "zero_trust_review" in techniques
    assert "chaos_driven_design" in techniques
    assert thinking["applied"]["framing"]["problem"] == "ebpf_metrics_export"
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["map_name_redacted"] is True


def test_bpftool_map_read_success_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_metrics_map"
    show_stdout = json.dumps([{"id": 42, "name": map_name}])
    dump_stdout = json.dumps([{"key": 0, "value": [10, 20]}])

    with patch(
        "src.network.ebpf.metrics_exporter.subprocess.run",
        side_effect=[
            Mock(returncode=0, stdout=show_stdout, stderr=""),
            Mock(returncode=0, stdout=dump_stdout, stderr=""),
        ],
    ):
        result = exporter._read_map_via_bpftool(map_name)

    assert result == {"raw_output": dump_stdout, "map_id": 42}
    events = _events(exporter)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "metrics_map_read_succeeded"
    assert payload["status"] == "success"
    assert payload["backend"] == "bpftool"
    assert payload["show_returncode"] == 0
    assert payload["dump_returncode"] == 0
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_id_hash"] == hashlib.sha256(b"42").hexdigest()
    assert payload["show_output"]["stdout_sha256"] == hashlib.sha256(
        show_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["dump_output"]["stdout_sha256"] == hashlib.sha256(
        dump_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert payload["payloads_redacted"] is True
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert dump_stdout not in str(payload)


def test_bpftool_map_missing_publishes_redacted_empty_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_missing_metrics_map"
    stderr = "secret map not found"

    with patch(
        "src.network.ebpf.metrics_exporter.subprocess.run",
        return_value=Mock(returncode=1, stdout="", stderr=stderr),
    ):
        result = exporter._read_map_via_bpftool(map_name)

    assert result is None
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "metrics_map_lookup_missing"
    assert payload["status"] == "empty"
    assert payload["show_returncode"] == 1
    assert payload["show_output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert stderr not in str(payload)


def test_bpftool_map_lookup_parse_failure_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_bad_json_map"
    show_stdout = "secret non-json output"

    with patch(
        "src.network.ebpf.metrics_exporter.subprocess.run",
        return_value=Mock(returncode=0, stdout=show_stdout, stderr=""),
    ):
        with pytest.raises(ParseError):
            exporter._read_map_via_bpftool(map_name)

    payload = _events(exporter)[-1].data
    assert payload["stage"] == "metrics_map_lookup_parse_failed"
    assert payload["status"] == "failure"
    assert payload["error_type"] == "JSONDecodeError"
    assert payload["show_output"]["stdout_sha256"] == hashlib.sha256(
        show_stdout.encode("utf-8")
    ).hexdigest()
    assert map_name not in str(payload)
    assert show_stdout not in str(payload)


def test_bpftool_map_dump_failure_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_dump_fail_map"
    dump_stderr = "secret dump failure"

    with patch(
        "src.network.ebpf.metrics_exporter.subprocess.run",
        side_effect=[
            Mock(returncode=0, stdout=json.dumps([{"id": 7}]), stderr=""),
            Mock(returncode=3, stdout="", stderr=dump_stderr),
        ],
    ):
        with pytest.raises(BpftoolError):
            exporter._read_map_via_bpftool(map_name)

    payload = _events(exporter)[-1].data
    assert payload["stage"] == "metrics_map_dump_failed"
    assert payload["status"] == "failure"
    assert payload["dump_returncode"] == 3
    assert payload["map_id_hash"] == hashlib.sha256(b"7").hexdigest()
    assert payload["dump_output"]["stderr_sha256"] == hashlib.sha256(
        dump_stderr.encode("utf-8")
    ).hexdigest()
    assert map_name not in str(payload)
    assert dump_stderr not in str(payload)


@patch("src.network.ebpf.metrics_exporter.subprocess.run", side_effect=FileNotFoundError)
def test_bpftool_unavailable_publishes_degraded_evidence(_mock_run, tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_no_bpftool_map"

    result = exporter._read_map_via_bpftool(map_name)

    assert result is None
    assert exporter.prometheus.degradation.bpftool_available is False
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "metrics_bpftool_unavailable"
    assert payload["status"] == "empty"
    assert payload["bpftool_available"] is False
    assert payload["error_type"] == "FileNotFoundError"
    assert map_name not in str(payload)


@patch(
    "src.network.ebpf.metrics_exporter.subprocess.run",
    side_effect=subprocess.TimeoutExpired(cmd="bpftool", timeout=5),
)
def test_bpftool_timeout_publishes_redacted_failure_evidence(_mock_run, tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_timeout_map"

    with pytest.raises(TimeoutError):
        exporter._read_map_via_bpftool(map_name)

    payload = _events(exporter)[-1].data
    assert payload["stage"] == "metrics_map_read_timeout"
    assert payload["status"] == "failure"
    assert payload["error_type"] == "TimeoutExpired"
    assert payload["error_message_redacted"] is True
    assert map_name not in str(payload)
