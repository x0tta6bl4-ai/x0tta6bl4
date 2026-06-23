import hashlib
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf import bcc_probes as probes_mod
from src.network.ebpf.bcc_probes import (
    BCC_PROBES_SERVICE_NAME,
    MeshNetworkProbes,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=BCC_PROBES_SERVICE_NAME,
        limit=80,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _bare_probes(bus, interface="secret-bcc0"):
    probes = object.__new__(MeshNetworkProbes)
    probes.interface = interface
    probes.prometheus_port = 19090
    probes.event_bus = bus
    probes.event_project_root = "."
    probes.source_agent = BCC_PROBES_SERVICE_NAME
    probes.running = False
    probes.current_latency = 0.0
    probes.current_congestion = 0.0
    probes.latency_bpf = None
    probes.congestion_bpf = None
    return probes


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "monitoring"
    assert "mape_k" in techniques
    assert "causal_analysis" in techniques
    assert "zero_trust_review" in techniques
    assert "chaos_driven_design" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_bcc_probe_observation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["interface_redacted"] is True


def test_bcc_unavailable_publishes_redacted_load_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret-bcc0"

    with patch.object(probes_mod, "BPF", None):
        probes = MeshNetworkProbes(
            interface=interface,
            prometheus_port=19090,
            event_bus=bus,
            start_prometheus_server=False,
        )

    assert probes.latency_bpf is None
    assert probes.congestion_bpf is None

    latency_payload = _stage_payload(bus, "bcc_latency_probe_bcc_unavailable")
    congestion_payload = _stage_payload(bus, "bcc_congestion_probe_bcc_unavailable")

    assert latency_payload["operation"] == "load_latency_probe"
    assert latency_payload["status"] == "failure"
    assert latency_payload["returncode"] == 1
    assert latency_payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert latency_payload["bpf_source_redacted"] is True
    assert congestion_payload["parsed_summary"]["reason"] == "bcc_unavailable"
    _assert_thinking_context(latency_payload)
    _assert_thinking_context(congestion_payload)
    assert interface not in str(latency_payload)
    assert interface not in str(congestion_payload)
    assert "BPF_HASH" not in str(latency_payload)
    assert "BPF_HASH" not in str(congestion_payload)


def test_bpf_load_success_publishes_redacted_source_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret-bcc1"
    latency_bpf = MagicMock()
    congestion_bpf = MagicMock()
    mock_bpf = MagicMock(side_effect=[latency_bpf, congestion_bpf])

    with patch.object(probes_mod, "BPF", mock_bpf):
        probes = MeshNetworkProbes(
            interface=interface,
            prometheus_port=19091,
            event_bus=bus,
            start_prometheus_server=False,
        )

    assert probes.latency_bpf is latency_bpf
    assert probes.congestion_bpf is congestion_bpf
    assert mock_bpf.call_count == 2

    latency_payload = _stage_payload(bus, "bcc_latency_probe_loaded")
    congestion_payload = _stage_payload(bus, "bcc_congestion_probe_loaded")

    assert latency_payload["status"] == "success"
    assert latency_payload["returncode"] == 0
    assert latency_payload["read_only"] is False
    assert latency_payload["bpf_source_hash"]
    assert congestion_payload["bpf_source_hash"]
    assert interface not in str(latency_payload)
    assert "tracepoint/net/netif_receive_skb" not in str(latency_payload)
    assert "kprobe/dev_queue_xmit" not in str(congestion_payload)


def test_poll_once_updates_metrics_and_redacts_trace_lines(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    probes = _bare_probes(bus)
    probes.latency_bpf = MagicMock()
    probes.congestion_bpf = MagicMock()
    probes.latency_bpf.trace_read.return_value = [
        "latency: 12345\n",
        "latency: not-int secret-latency-line",
    ]
    probes.congestion_bpf.trace_read.return_value = [
        "queue_len ifindex=3 len=7",
        "queue_len ifindex=3 len=secret-queue-line",
    ]
    latency_gauge = MagicMock()
    congestion_gauge = MagicMock()

    with patch.object(probes_mod.PACKET_LATENCY, "labels", return_value=latency_gauge):
        with patch.object(
            probes_mod.QUEUE_CONGESTION,
            "labels",
            return_value=congestion_gauge,
        ):
            summary = probes.poll_once()

    assert summary["latency_events_parsed"] == 1
    assert summary["congestion_events_parsed"] == 1
    assert summary["parse_errors"] == 2
    assert probes.current_latency == 12345
    assert probes.current_congestion == 7
    latency_gauge.set.assert_called_once_with(12345)
    congestion_gauge.set.assert_called_once_with(7)

    payload = _stage_payload(bus, "bcc_probes_trace_poll_completed")
    assert payload["operation"] == "poll_once"
    assert payload["status"] == "partial"
    assert payload["returncode"] == 1
    assert payload["trace_line_hashes"]["count"] == 4
    assert payload["output"]["stdout_chars"] > 0
    assert payload["trace_lines_redacted"] is True
    _assert_thinking_context(payload)
    assert "secret-bcc0" not in str(payload)
    assert "secret-latency-line" not in str(payload)
    assert "secret-queue-line" not in str(payload)


def test_trace_read_failure_publishes_redacted_error(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    probes = _bare_probes(bus)
    probes.latency_bpf = MagicMock()
    probes.latency_bpf.trace_read.side_effect = RuntimeError("secret trace failure")

    summary = probes.poll_once()

    assert summary["events_read"] == 0
    payload = _stage_payload(bus, "bcc_probe_trace_read_failed")
    assert payload["operation"] == "trace_read"
    assert payload["status"] == "failure"
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["error"]["message_redacted"] is True
    assert "secret trace failure" not in str(payload)


def test_metrics_snapshot_and_cleanup_publish_redacted_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    probes = _bare_probes(bus)
    probes.current_latency = 456.0
    probes.current_congestion = 8.0
    probes.latency_bpf = MagicMock()
    probes.congestion_bpf = MagicMock()

    assert probes.get_current_metrics() == {
        "avg_latency_ns": 456.0,
        "queue_congestion": 8.0,
    }
    probes.cleanup()

    metrics_payload = _stage_payload(bus, "bcc_probes_metrics_snapshot_read")
    cleanup_payload = _stage_payload(bus, "bcc_probes_cleanup_completed")

    assert metrics_payload["parsed_summary"]["avg_latency_ns"] == 456.0
    assert cleanup_payload["parsed_summary"] == {
        "cleanup": True,
        "cleaned_count": 2,
        "skipped_count": 0,
    }
    assert cleanup_payload["cleaned_program_hashes"]["count"] == 2
    assert "latency_probe" not in str(cleanup_payload)
    assert "congestion_probe" not in str(cleanup_payload)
    assert "secret-bcc0" not in str(cleanup_payload)
