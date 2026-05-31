import hashlib
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.rate_limiter_manager import (
    EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME,
    RateLimiterManager,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME,
        limit=80,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _software_manager(tmp_path, interface="secret0"):
    bus = EventBus(project_root=str(tmp_path))
    with patch("src.network.ebpf.rate_limiter_manager.BCC_AVAILABLE", False):
        manager = RateLimiterManager(interface=interface, event_bus=bus)
    return manager, bus


def _bare_manager(bus):
    manager = object.__new__(RateLimiterManager)
    manager.interface = "secret-map0"
    manager.bpf = MagicMock()
    manager._software_limiter = None
    manager._using_software_fallback = False
    manager._peer_session_keys = {}
    manager._pqc_session_map_writes = 0
    manager.event_bus = bus
    manager.event_project_root = "."
    manager.source_agent = EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME
    return manager


def test_bcc_unavailable_fallback_publishes_redacted_evidence(tmp_path):
    manager, bus = _software_manager(tmp_path)

    assert manager.is_using_software_fallback is True
    bcc_payload = _stage_payload(bus, "rate_limiter_bcc_unavailable")
    fallback_payload = _stage_payload(bus, "rate_limiter_software_fallback_enabled")

    assert bcc_payload["operation"] == "init_ebpf_or_fallback"
    assert bcc_payload["status"] == "failure"
    assert bcc_payload["interface_hash"] == hashlib.sha256(b"secret0").hexdigest()
    assert fallback_payload["parsed_summary"] == {
        "fallback": True,
        "reason": "bcc_unavailable",
    }
    assert fallback_payload["identity"]["redacted"] is True
    assert "secret0" not in str(bcc_payload)
    assert "secret0" not in str(fallback_payload)


@patch("src.network.ebpf.rate_limiter_manager.BCC_AVAILABLE", True)
@patch("src.network.ebpf.rate_limiter_manager.os.geteuid", return_value=0)
@patch("src.network.ebpf.rate_limiter_manager.BPF")
def test_bpf_load_publishes_redacted_program_evidence(mock_bpf, _geteuid, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret1"
    mock_bpf.SCHED_CLS = 3
    mock_bpf_instance = MagicMock()
    mock_bpf.return_value = mock_bpf_instance

    manager = RateLimiterManager(interface=interface, event_bus=bus)

    assert manager.bpf is mock_bpf_instance
    mock_bpf.assert_called_once()
    mock_bpf_instance.load_func.assert_called_once_with("handle_egress", 3)
    payload = _stage_payload(bus, "rate_limiter_bpf_load_succeeded")
    assert payload["operation"] == "init_ebpf_or_fallback"
    assert payload["status"] == "success"
    assert payload["read_only"] is False
    assert payload["parsed_summary"]["tc_attach_performed"] is False
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["program_path_redacted"] is True
    assert payload["function_name_redacted"] is True
    assert interface not in str(payload)
    assert "rate_limiter.c" not in str(payload)
    assert "handle_egress" not in str(payload)


def test_sync_peer_session_keys_publishes_redacted_counts(tmp_path):
    manager, bus = _software_manager(tmp_path)
    peer_id = "secret-peer"
    rejected_peer = "secret-rejected"
    session_key = b"secret-session-key-32-bytes!!!!"

    assert manager.sync_peer_session_keys(
        {peer_id: session_key, rejected_peer: "not-hex"}
    ) == 1

    payload = _stage_payload(bus, "rate_limiter_peer_session_keys_synced")
    assert payload["operation"] == "sync_peer_session_keys"
    assert payload["parsed_summary"]["input_count"] == 2
    assert payload["parsed_summary"]["accepted_count"] == 1
    assert payload["parsed_summary"]["rejected_count"] == 1
    assert payload["accepted_peer_hashes"]["hashes"] == [
        hashlib.sha256(peer_id.encode("utf-8")).hexdigest()
    ]
    assert payload["rejected_peer_hashes"]["hashes"] == [
        hashlib.sha256(rejected_peer.encode("utf-8")).hexdigest()
    ]
    assert payload["session_key_hashes"]["hashes"] == [
        hashlib.sha256(session_key).hexdigest()
    ]
    assert peer_id not in str(payload)
    assert rejected_peer not in str(payload)
    assert session_key.decode("utf-8") not in str(payload)


def test_check_rate_limit_missing_pqc_session_redacts_peer(tmp_path):
    manager, bus = _software_manager(tmp_path)
    peer_id = "secret-missing-peer"

    assert manager.check_rate_limit(
        packet_size=128,
        peer_id=peer_id,
        require_pqc_session=True,
    ) is False

    payload = _stage_payload(bus, "rate_limiter_pqc_session_key_missing")
    assert payload["operation"] == "check_rate_limit"
    assert payload["status"] == "failure"
    assert payload["parsed_summary"]["allowed"] is False
    assert payload["peer_id_hash"] == hashlib.sha256(
        peer_id.encode("utf-8")
    ).hexdigest()
    assert peer_id not in str(payload)


def test_get_stats_returns_raw_stats_but_event_redacts_peer_ids(tmp_path):
    manager, bus = _software_manager(tmp_path)
    peer_id = "secret-peer-stats"
    manager.sync_peer_session_keys({peer_id: b"x" * 32})

    stats = manager.get_stats()

    payload = _stage_payload(bus, "rate_limiter_stats_read")
    assert stats["peer_session_keys_loaded"] == 1
    assert payload["parsed_summary"]["peer_session_keys_loaded"] == 1
    assert payload["peer_id_hashes"]["hashes"] == [
        hashlib.sha256(peer_id.encode("utf-8")).hexdigest()
    ]
    assert peer_id not in str(payload)
    assert "secret0" not in str(payload)


def test_set_limit_ebpf_map_update_publishes_redacted_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    manager = _bare_manager(bus)
    config_map = MagicMock()
    manager.bpf.__getitem__.return_value = config_map

    manager.set_limit(4096)

    config_map.__setitem__.assert_called_once()
    payload = _stage_payload(bus, "rate_limiter_config_map_updated")
    assert payload["operation"] == "set_limit"
    assert payload["status"] == "success"
    assert payload["read_only"] is False
    assert payload["parsed_summary"]["bytes_per_sec"] == 4096
    assert payload["map_name_hash"] == hashlib.sha256(b"limit_config").hexdigest()
    assert payload["map_name_redacted"] is True
    assert "limit_config" not in str(payload)
    assert "secret-map0" not in str(payload)
