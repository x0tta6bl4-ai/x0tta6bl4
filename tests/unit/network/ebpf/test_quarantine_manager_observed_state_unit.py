import hashlib
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.quarantine_manager import (
    PQC_QUARANTINE_MANAGER_SERVICE_NAME,
    QuarantineManager,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=PQC_QUARANTINE_MANAGER_SERVICE_NAME,
        limit=80,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _software_manager(tmp_path, interface="secret0", threshold=2):
    bus = EventBus(project_root=str(tmp_path))
    with patch("src.network.ebpf.quarantine_manager.BCC_AVAILABLE", False):
        manager = QuarantineManager(
            interface=interface,
            failure_threshold=threshold,
            event_bus=bus,
        )
    return manager, bus


def _bare_manager(bus):
    manager = object.__new__(QuarantineManager)
    manager.interface = "secret0"
    manager.failure_threshold = 2
    manager.bpf = None
    manager.fn = None
    manager._using_software_fallback = False
    manager._blocked_ips = {}
    manager._verification_failures = {}
    manager._bpf_program_path = None
    manager.event_bus = bus
    manager.event_project_root = "."
    manager.source_agent = PQC_QUARANTINE_MANAGER_SERVICE_NAME
    return manager


def test_software_fallback_block_publishes_redacted_evidence(tmp_path):
    manager, bus = _software_manager(tmp_path)
    ip_address = "10.1.2.3"

    manager.block_node(ip_address, level=2)

    payload = _stage_payload(bus, "quarantine_block_software_succeeded")
    assert payload["operation"] == "block_node"
    assert payload["status"] == "success"
    assert payload["read_only"] is False
    assert payload["parsed_summary"] == {"blocked": True, "mode": "software"}
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert ip_address not in str(payload)
    assert "secret0" not in str(payload)


def test_pqc_failure_threshold_publishes_redacted_quarantine_trigger(tmp_path):
    manager, bus = _software_manager(tmp_path, threshold=2)
    peer_id = "secret-peer"
    ip_address = "10.1.2.4"
    reason = "secret-invalid-signature"

    assert manager.record_pqc_verification_result(peer_id, ip_address, False, reason) is False
    assert manager.record_pqc_verification_result(peer_id, ip_address, False, reason) is True

    trigger = _stage_payload(bus, "pqc_quarantine_threshold_triggered")
    assert trigger["operation"] == "record_pqc_verification_result"
    assert trigger["parsed_summary"]["failure_count"] == 2
    assert trigger["parsed_summary"]["quarantine_triggered"] is True
    assert trigger["peer_id_hash"] == hashlib.sha256(
        peer_id.encode("utf-8")
    ).hexdigest()
    assert trigger["reason_hash"] == hashlib.sha256(
        reason.encode("utf-8")
    ).hexdigest()
    assert trigger["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert peer_id not in str(trigger)
    assert reason not in str(trigger)
    assert ip_address not in str(trigger)


def test_xdp_block_unblock_cleanup_publish_redacted_map_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    manager = _bare_manager(bus)
    manager.bpf = MagicMock()
    blocked_map = MagicMock()
    manager.bpf.__getitem__.return_value = blocked_map
    ip_address = "10.9.8.7"

    manager.block_node(ip_address, level=3)
    manager.unblock_node(ip_address)
    manager.cleanup()

    block_payload = _stage_payload(bus, "quarantine_block_xdp_succeeded")
    assert block_payload["source_mode"] == "bcc-map"
    assert block_payload["map_name_redacted"] is True
    assert block_payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert ip_address not in str(block_payload)

    unblock_payload = _stage_payload(bus, "quarantine_unblock_xdp_succeeded")
    assert unblock_payload["parsed_summary"]["unblocked"] is True
    assert ip_address not in str(unblock_payload)

    cleanup_payload = _stage_payload(bus, "quarantine_cleanup_xdp_succeeded")
    assert cleanup_payload["parsed_summary"] == {
        "cleanup": True,
        "xdp_removed": True,
    }
    assert "secret0" not in str(cleanup_payload)


def test_invalid_ip_publishes_redacted_failure(tmp_path):
    manager, bus = _software_manager(tmp_path)
    ip_address = "secret-invalid-ip"

    manager.block_node(ip_address, level=2)

    payload = _stage_payload(bus, "quarantine_block_invalid_ip")
    assert payload["status"] == "failure"
    assert payload["error"]["type"] == "OSError"
    assert payload["ip_address_hash"] == hashlib.sha256(
        ip_address.encode("utf-8")
    ).hexdigest()
    assert ip_address not in str(payload)


def test_get_stats_event_redacts_blocked_ips_and_peer_ids(tmp_path):
    manager, bus = _software_manager(tmp_path)
    ip_address = "10.2.3.4"
    peer_id = "secret-peer"
    manager._blocked_ips[ip_address] = 2
    manager._verification_failures[peer_id] = 1

    stats = manager.get_stats()

    payload = _stage_payload(bus, "quarantine_stats_read")
    assert stats["blocked_ips"] == {ip_address: 2}
    assert stats["verification_failures"] == {peer_id: 1}
    assert payload["blocked_ip_hashes"] == [
        hashlib.sha256(ip_address.encode("utf-8")).hexdigest()
    ]
    assert payload["peer_id_hashes"] == [
        hashlib.sha256(peer_id.encode("utf-8")).hexdigest()
    ]
    assert ip_address not in str(payload)
    assert peer_id not in str(payload)
