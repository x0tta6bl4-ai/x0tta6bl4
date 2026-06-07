import hashlib
import json
import struct
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.stigmergy_bridge import (
    StigmergyBridge,
    _bpftool_dump_map,
)
from src.network.routing.stigmergy import StigmergyRouter


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-stigmergy-bridge",
        limit=20,
    )


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "coordinator"
    assert "mape_k" in techniques
    assert "reverse_planning" in techniques
    assert "causal_analysis" in techniques
    assert "zero_trust_review" in techniques
    assert "weighted_decision_matrix" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_stigmergy_bridge_operation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["stage"] == payload["stage"]
    assert constraints["output_redacted"] is True
    assert "extra_keys" in constraints


def test_bpftool_dump_map_success_publishes_redacted_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    map_name = "secret_stigmergy_map"
    secret_payload = "secret raw map payload"
    ip_bytes = list(struct.pack("<I", 0x0100000A))
    val_bytes = list(struct.pack("<Q", 5))
    stdout = json.dumps(
        [{"key": ip_bytes, "value": val_bytes, "note": secret_payload}]
    )
    mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")

    with patch(
        "src.network.ebpf.stigmergy_bridge.subprocess.run",
        return_value=mock_result,
    ):
        result = _bpftool_dump_map(map_name, event_bus=bus)

    assert result == {0x0100000A: 5}
    payload = _events(bus)[-1].data
    assert payload["stage"] == "stigmergy_map_dump_succeeded"
    assert payload["operation"] == "bpftool_map_dump"
    assert payload["status"] == "success"
    assert payload["returncode"] == 0
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["map_name_redacted"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["parsed_summary"]["entries_total"] == 1
    assert payload["parsed_summary"]["counter_entries"] == 1
    assert payload["identity"]["redacted"] is True
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert secret_payload not in str(payload)


def test_bpftool_dump_map_failure_publishes_returncode_and_redacted_output(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    map_name = "secret_missing_stigmergy_map"
    stderr = "secret bpftool failure"
    mock_result = MagicMock(returncode=2, stdout="", stderr=stderr)

    with patch(
        "src.network.ebpf.stigmergy_bridge.subprocess.run",
        return_value=mock_result,
    ):
        result = _bpftool_dump_map(map_name, event_bus=bus)

    assert result == {}
    payload = _events(bus)[-1].data
    assert payload["stage"] == "stigmergy_map_dump_failed"
    assert payload["status"] == "failure"
    assert payload["returncode"] == 2
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert map_name not in str(payload)
    assert stderr not in str(payload)


def test_simulation_reinforcement_publishes_redacted_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    router = StigmergyRouter("node-test")
    bridge = StigmergyBridge(router, event_bus=bus)
    dest_id = "secret-peer"
    next_hop = "secret-hop"

    bridge.record_ack(dest_id, next_hop)
    bridge.record_timeout(dest_id, next_hop)

    events = _events(bus)
    ack_payload = events[-2].data
    timeout_payload = events[-1].data
    assert ack_payload["stage"] == "stigmergy_sim_ack_reinforced"
    assert ack_payload["read_only"] is False
    assert ack_payload["parsed_summary"]["reinforcement_success"] is True
    assert ack_payload["dest_id_hash"] == hashlib.sha256(
        dest_id.encode("utf-8")
    ).hexdigest()
    assert timeout_payload["stage"] == "stigmergy_sim_timeout_reinforced"
    assert timeout_payload["parsed_summary"]["reinforcement_success"] is False
    _assert_thinking_context(ack_payload)
    _assert_thinking_context(timeout_payload)
    assert dest_id not in str(ack_payload)
    assert next_hop not in str(ack_payload)
    assert dest_id not in str(timeout_payload)
    assert next_hop not in str(timeout_payload)


def test_ebpf_snapshot_reinforcement_publishes_redacted_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    router = StigmergyRouter("node-ebpf")
    bridge = StigmergyBridge(router, event_bus=bus)
    peer_id = "secret-peer-1"
    ip_addr = "10.0.0.1"
    ip_u32 = 0x0A000001
    bridge.register_peer(peer_id, ip_addr)
    bridge._last_snapshot = {ip_u32: 0}

    with patch(
        "src.network.ebpf.stigmergy_bridge._bpftool_dump_map",
        return_value={ip_u32: 10},
    ):
        bridge._process_ebpf_snapshot()

    payload = _events(bus)[-1].data
    assert payload["stage"] == "stigmergy_ebpf_delta_reinforced"
    assert payload["source_mode"] == "ebpf_snapshot"
    assert payload["parsed_summary"]["delta_packets"] == 10
    assert payload["parsed_summary"]["total_packets"] == 10
    assert payload["parsed_summary"]["peer_known"] is True
    assert payload["dest_id_hash"] == hashlib.sha256(
        peer_id.encode("utf-8")
    ).hexdigest()
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_addr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert peer_id not in str(payload)
    assert ip_addr not in str(payload)


def test_xdp_attach_publishes_redacted_command_outcome(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    router = StigmergyRouter("node-xdp")
    interface = "secret0"
    ebpf_object = tmp_path / "secret_stigmergy_counter.bpf.o"
    bridge = StigmergyBridge(
        router,
        interface=interface,
        ebpf_object=ebpf_object,
        event_bus=bus,
    )
    stdout = "secret attach stdout"
    mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")

    with patch(
        "src.network.ebpf.stigmergy_bridge.subprocess.run",
        return_value=mock_result,
    ):
        assert bridge._try_attach_xdp() is True

    payload = _events(bus)[-1].data
    assert payload["stage"] == "stigmergy_xdp_attach_succeeded"
    assert payload["operation"] == "xdp_attach"
    assert payload["read_only"] is False
    assert payload["returncode"] == 0
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["ebpf_object_hash"] == hashlib.sha256(
        str(ebpf_object).encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert str(ebpf_object) not in str(payload)
    assert stdout not in str(payload)


def test_xdp_detach_publishes_redacted_command_outcome(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    router = StigmergyRouter("node-xdp")
    interface = "secret1"
    bridge = StigmergyBridge(router, interface=interface, event_bus=bus)
    stderr = "secret detach stderr"
    mock_result = MagicMock(returncode=3, stdout="", stderr=stderr)

    with patch(
        "src.network.ebpf.stigmergy_bridge.subprocess.run",
        return_value=mock_result,
    ):
        bridge._try_detach_xdp()

    payload = _events(bus)[-1].data
    assert payload["stage"] == "stigmergy_xdp_detach_failed"
    assert payload["operation"] == "xdp_detach"
    assert payload["status"] == "failure"
    assert payload["returncode"] == 3
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert stderr not in str(payload)
