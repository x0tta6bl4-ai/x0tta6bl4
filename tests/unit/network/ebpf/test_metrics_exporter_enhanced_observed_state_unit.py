import hashlib
import subprocess
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.metrics_exporter_enhanced import EBPFMetricsExporterEnhanced


def _exporter(tmp_path):
    return EBPFMetricsExporterEnhanced(
        prometheus_port=19091,
        event_bus=EventBus(project_root=str(tmp_path)),
    )


def _events(exporter):
    return exporter.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-metrics-exporter-enhanced",
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
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_metrics_export_enhanced"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["map_name_redacted"] is True
    assert constraints["result_payload_redacted"] is True


def test_enhanced_bpftool_wrapper_success_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_enhanced_map"
    raw_output = "secret raw map"

    with patch.object(
        exporter,
        "_read_map_via_bpftool",
        return_value={"raw_output": raw_output, "map_id": 7},
    ):
        result = exporter._read_map_via_bpftool_with_timeout(map_name)

    assert result == {"raw_output": raw_output, "map_id": 7}
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "enhanced_metrics_map_read_succeeded"
    assert payload["status"] == "success"
    assert payload["backend"] == "bpftool"
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_name_redacted"] is True
    assert payload["result_shape"]["type"] == "dict"
    assert payload["result_shape"]["count"] == 2
    assert payload["result_shape"]["keys_redacted"] is True
    assert payload["result_payload_redacted"] is True
    assert payload["identity"]["redacted"] is True
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert raw_output not in str(payload)


def test_enhanced_bpftool_wrapper_empty_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_empty_enhanced_map"

    with patch.object(exporter, "_read_map_via_bpftool", return_value=None):
        result = exporter._read_map_via_bpftool_with_timeout(map_name)

    assert result is None
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "enhanced_metrics_map_read_empty"
    assert payload["status"] == "empty"
    assert payload["reason"] == "bpftool_read_returned_none"
    assert payload["result_shape"] == {"type": "none", "count": 0}
    _assert_thinking_context(payload)
    assert map_name not in str(payload)


def test_enhanced_bpftool_wrapper_timeout_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_timeout_enhanced_map"

    with patch.object(
        exporter,
        "_read_map_via_bpftool",
        side_effect=subprocess.TimeoutExpired(cmd="bpftool", timeout=5),
    ):
        result = exporter._read_map_via_bpftool_with_timeout(map_name)

    assert result is None
    assert exporter.error_count.timeout == 1
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "enhanced_metrics_map_read_timeout"
    assert payload["status"] == "failure"
    assert payload["error_type"] == "TimeoutExpired"
    assert payload["error_message_redacted"] is True
    assert "error_message_hash" in payload
    assert map_name not in str(payload)


def test_enhanced_bpftool_wrapper_error_publishes_redacted_evidence(tmp_path):
    exporter = _exporter(tmp_path)
    map_name = "secret_error_enhanced_map"
    error_message = "secret enhanced failure"

    with patch.object(
        exporter,
        "_read_map_via_bpftool",
        side_effect=RuntimeError(error_message),
    ):
        result = exporter._read_map_via_bpftool_with_timeout(map_name)

    assert result is None
    assert exporter.error_count.map_read == 1
    payload = _events(exporter)[-1].data
    assert payload["stage"] == "enhanced_metrics_map_read_failed"
    assert payload["status"] == "failure"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message_hash"] == hashlib.sha256(
        error_message.encode("utf-8")
    ).hexdigest()
    assert payload["error_message_redacted"] is True
    assert map_name not in str(payload)
    assert error_message not in str(payload)
