import hashlib
from unittest.mock import Mock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.map_reader import EBPFMapReader


def _reader(tmp_path, monkeypatch, *, bpftool_available=True):
    monkeypatch.setattr(
        EBPFMapReader,
        "_check_bpftool",
        lambda _self: bpftool_available,
    )
    return EBPFMapReader(event_bus=EventBus(project_root=str(tmp_path)))


def _events(reader):
    return reader.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-bpftool-map-reader",
        limit=10,
    )


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "monitoring"
    assert "mape_k" in techniques
    assert "mind_maps" in techniques
    assert "graphsage" in techniques
    assert "causal_analysis" in techniques
    assert "zero_trust_review" in techniques
    assert "reverse_planning" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_bpftool_map_reader_operation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["stage"] == payload["stage"]
    assert constraints["map_selector_redacted"] is True
    assert constraints["output_redacted"] is True


def test_read_map_unavailable_publishes_redacted_empty_evidence(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=False)
    map_name = "secret_packet_map"

    result = reader.read_map(map_name=map_name)

    assert result == {}
    events = _events(reader)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "map_read_unavailable"
    assert payload["status"] == "empty"
    assert payload["bpftool_available"] is False
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_selector_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["observed_state"] is True
    assert payload["identity"]["redacted"] is True
    _assert_thinking_context(payload)
    assert map_name not in str(payload)


def test_list_maps_success_publishes_bounded_output_metadata(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=True)
    stdout = '[{"id": 7, "name": "secret_runtime_map"}]'

    with patch(
        "src.network.ebpf.map_reader.subprocess.run",
        return_value=Mock(returncode=0, stdout=stdout, stderr=""),
    ):
        result = reader.list_maps()

    assert result == [{"id": 7, "name": "secret_runtime_map"}]
    events = _events(reader)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "map_list_succeeded"
    assert payload["status"] == "success"
    assert payload["returncode"] == 0
    assert payload["result_count"] == 1
    assert payload["map_names_redacted"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_chars"] == len(stdout)
    _assert_thinking_context(payload)
    assert "secret_runtime_map" not in str(payload)


def test_read_map_name_failure_id_success_redacts_primary_error(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_latency_map"
    primary_stderr = "secret map lookup failed"
    fallback_stdout = '{"data": [{"key": [0], "value": 3}]}'

    with patch(
        "src.network.ebpf.map_reader.subprocess.run",
        side_effect=[
            Mock(returncode=2, stdout="", stderr=primary_stderr),
            Mock(returncode=0, stdout=fallback_stdout, stderr=""),
        ],
    ):
        result = reader.read_map(map_id=42, map_name=map_name)

    assert result == {"data": [{"key": [0], "value": 3}]}
    events = _events(reader)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "map_read_succeeded"
    assert payload["reason"] == "name_failed_id_succeeded"
    assert payload["returncode"] == 0
    assert payload["primary_returncode"] == 2
    assert payload["result_count"] == 1
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_id_hash"] == hashlib.sha256(b"42").hexdigest()
    assert payload["primary_output"]["stderr_sha256"] == hashlib.sha256(
        primary_stderr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert primary_stderr not in str(payload)


def test_counter_map_aggregation_publishes_redacted_counter_evidence(
    monkeypatch,
    tmp_path,
):
    reader = _reader(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_counter_map"

    with patch.object(
        reader,
        "read_map",
        return_value={
            "data": [
                {"key": [1], "value": "5"},
                {"key": [2], "value": 7},
            ]
        },
    ):
        result = reader.read_counter_map(map_name)

    assert result == {"1": 5, "2": 7}
    events = _events(reader)
    assert len(events) == 1
    payload = events[-1].data
    assert payload["stage"] == "counter_map_aggregated"
    assert payload["status"] == "success"
    assert payload["result_count"] == 2
    assert payload["counter_values_redacted"] is True
    assert "counter_values" not in payload
    assert "counters" not in payload
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
