import hashlib
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.map_manager import EBPFMapManager


def _manager(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    EBPFMapManager.configure_event_bus(event_bus=bus)
    return EBPFMapManager, bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-attestation-map-manager",
        limit=20,
    )


def test_update_attestation_success_publishes_redacted_evidence(tmp_path):
    manager, bus = _manager(tmp_path)
    ip_address = "10.20.30.40"
    stdout = "secret update output"

    with patch(
        "src.network.ebpf.map_manager.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    ):
        assert manager.update_attestation(ip_address, True) is True

    payload = _events(bus)[-1].data
    assert payload["stage"] == "attestation_map_update_succeeded"
    assert payload["operation"] == "bpftool_attestation_update"
    assert payload["read_only"] is False
    assert payload["returncode"] == 0
    assert payload["command"] == [
        "bpftool",
        "map",
        "update",
        "name",
        "[redacted]",
        "key",
        "[redacted]",
        "value",
        "[redacted]",
    ]
    assert payload["map_name_hash"] == hashlib.sha256(
        b"attested_nodes_map"
    ).hexdigest()
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert payload["key_hex_hash"] == hashlib.sha256(
        b"0x0a 0x14 0x1e 0x28"
    ).hexdigest()
    assert payload["value_hash"] == hashlib.sha256(b"0x01").hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert ip_address not in str(payload)
    assert "0x0a 0x14 0x1e 0x28" not in str(payload)
    assert "attested_nodes_map" not in str(payload)
    assert stdout not in str(payload)


def test_remove_node_failure_publishes_redacted_delete_evidence(tmp_path):
    manager, bus = _manager(tmp_path)
    ip_address = "10.1.2.3"
    stderr = "secret delete failure"

    with patch(
        "src.network.ebpf.map_manager.subprocess.run",
        return_value=SimpleNamespace(returncode=2, stdout="", stderr=stderr),
    ):
        assert manager.remove_node(ip_address) is False

    payload = _events(bus)[-1].data
    assert payload["stage"] == "attestation_map_delete_failed"
    assert payload["operation"] == "bpftool_attestation_delete"
    assert payload["status"] == "failure"
    assert payload["command"] == [
        "bpftool",
        "map",
        "delete",
        "name",
        "[redacted]",
        "key",
        "[redacted]",
    ]
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert payload["key_hex_hash"] == hashlib.sha256(
        b"0x0a 0x01 0x02 0x03"
    ).hexdigest()
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    assert ip_address not in str(payload)
    assert "0x0a 0x01 0x02 0x03" not in str(payload)
    assert stderr not in str(payload)


def test_invalid_ip_publishes_redacted_key_parse_failure(tmp_path):
    manager, bus = _manager(tmp_path)
    ip_address = "secret-invalid-ip"

    assert manager.update_attestation(ip_address, False) is False

    payload = _events(bus)[-1].data
    assert payload["stage"] == "attestation_map_update_key_parse_failed"
    assert payload["operation"] == "bpftool_attestation_update"
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert payload["parsed_summary"] == {"updated": False, "is_attested": False}
    assert ip_address not in str(payload)


def test_update_attestation_timeout_publishes_redacted_error_evidence(tmp_path):
    manager, bus = _manager(tmp_path)
    ip_address = "192.0.2.10"
    timeout = subprocess.TimeoutExpired(
        cmd="bpftool",
        timeout=5,
        output="secret timeout output",
        stderr="secret timeout stderr",
    )

    with patch("src.network.ebpf.map_manager.subprocess.run", side_effect=timeout):
        assert manager.update_attestation(ip_address, True) is False

    payload = _events(bus)[-1].data
    assert payload["stage"] == "attestation_map_update_timeout"
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["command"] == [
        "bpftool",
        "map",
        "update",
        "name",
        "[redacted]",
        "key",
        "[redacted]",
        "value",
        "[redacted]",
    ]
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        b"secret timeout output"
    ).hexdigest()
    assert ip_address not in str(payload)
    assert "secret timeout output" not in str(payload)
    assert "secret timeout stderr" not in str(payload)
