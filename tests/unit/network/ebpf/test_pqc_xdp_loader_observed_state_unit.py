import hashlib
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.pqc_xdp_loader import (
    PQC_XDP_LOADER_SERVICE_NAME,
    PQCXDPLoader,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=PQC_XDP_LOADER_SERVICE_NAME,
        limit=50,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _bare_loader(bus):
    loader = object.__new__(PQCXDPLoader)
    loader.event_bus = bus
    loader.event_project_root = "."
    loader.source_agent = PQC_XDP_LOADER_SERVICE_NAME
    loader.interface = "secret0"
    return loader


@patch("src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE", True)
@patch("src.network.ebpf.pqc_xdp_loader.get_pqc_gateway")
@patch("src.network.ebpf.pqc_xdp_loader.BPF")
def test_pqc_xdp_load_attach_publishes_redacted_evidence(
    mock_bpf,
    mock_gateway,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret0"
    mock_bpf_instance = MagicMock()
    mock_bpf.return_value = mock_bpf_instance
    mock_gateway.return_value = MagicMock()

    loader = PQCXDPLoader(interface=interface, event_bus=bus)

    assert loader.interface == interface
    mock_bpf.assert_called_once()
    mock_bpf_instance.attach_xdp.assert_called_once()

    payload = _stage_payload(bus, "pqc_xdp_attach_succeeded")
    assert payload["operation"] == "attach_xdp"
    assert payload["status"] == "success"
    assert payload["read_only"] is False
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["function_name_redacted"] is True
    assert payload["program_path_redacted"] is True
    assert payload["identity"]["redacted"] is True
    assert interface not in str(payload)
    assert "xdp_pqc_verify_prog" not in str(payload)
    assert "#include" not in str(payload)


def test_update_pqc_sessions_publishes_redacted_map_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = _bare_loader(bus)
    old_key = b"old-secret-session"
    new_key = b"new-secret-session"
    secret_value = "secret-session-value"
    mock_map = MagicMock()
    mock_map.keys.return_value = [old_key]
    loader.pqc_sessions_map = mock_map

    loader.update_pqc_sessions(
        {
            new_key: {
                "mac_key": [1] * 16,
                "verified": 1,
                "peer_id_hash": 123,
                "secret_marker": secret_value,
            }
        }
    )

    payload = _stage_payload(bus, "pqc_sessions_update_succeeded")
    assert payload["operation"] == "update_pqc_sessions"
    assert payload["status"] == "success"
    assert payload["parsed_summary"]["deleted_count"] == 1
    assert payload["parsed_summary"]["write_count"] == 1
    assert payload["session_key_hashes"] == [hashlib.sha256(new_key).hexdigest()]
    assert payload["existing_key_hashes"] == [hashlib.sha256(old_key).hexdigest()]
    assert payload["session_values_redacted"] is True
    assert new_key.hex() not in str(payload)
    assert old_key.hex() not in str(payload)
    assert secret_value not in str(payload)


def test_update_pqc_sessions_no_map_publishes_redacted_failure(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = _bare_loader(bus)
    loader.pqc_sessions_map = None
    session_key = b"missing-map-session"

    loader.update_pqc_sessions({session_key: {"secret": "must-not-leak"}})

    payload = _stage_payload(bus, "pqc_sessions_update_no_map")
    assert payload["status"] == "failure"
    assert payload["parsed_summary"] == {
        "updated": False,
        "reason": "map_uninitialized",
    }
    assert payload["session_key_hashes"] == [hashlib.sha256(session_key).hexdigest()]
    assert session_key.hex() not in str(payload)
    assert "must-not-leak" not in str(payload)


def test_create_pqc_session_failure_publishes_redacted_error(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = _bare_loader(bus)
    loader.pqc_gateway = MagicMock()
    peer_id = "secret-peer-id"
    error_message = "secret peer creation failed"
    loader.pqc_gateway.create_session.side_effect = RuntimeError(error_message)

    assert loader.create_pqc_session(peer_id) is None

    payload = _stage_payload(bus, "pqc_session_create_failed")
    assert payload["status"] == "failure"
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["error"]["message_redacted"] is True
    assert payload["peer_id_hash"] == hashlib.sha256(
        peer_id.encode("utf-8")
    ).hexdigest()
    assert peer_id not in str(payload)
    assert error_message not in str(payload)


def test_cleanup_publishes_redacted_bcc_cleanup_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = _bare_loader(bus)
    loader.bpf = MagicMock()

    loader.cleanup()

    payload = _stage_payload(bus, "pqc_xdp_cleanup_succeeded")
    assert payload["operation"] == "cleanup"
    assert payload["status"] == "success"
    assert payload["parsed_summary"] == {"cleanup": True, "xdp_removed": True}
    assert payload["interface_hash"] == hashlib.sha256(b"secret0").hexdigest()
    assert "secret0" not in str(payload)
