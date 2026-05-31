import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.loader.map_manager import EBPFMapManager


def _manager(tmp_path, monkeypatch, *, bpftool_available=True):
    monkeypatch.setattr(
        EBPFMapManager,
        "_check_bpftool",
        lambda _self: bpftool_available,
    )
    return EBPFMapManager(event_bus=EventBus(project_root=str(tmp_path)))


def _events(manager):
    return manager.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-loader-map-manager",
        limit=20,
    )


def test_read_map_success_publishes_redacted_bpftool_evidence(
    tmp_path,
    monkeypatch,
):
    manager = _manager(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_packet_stats"
    stdout = json.dumps(
        [
            {"key": "0", "value": "100", "note": "secret read payload"},
            {"key": [1, 2], "value": "200"},
        ]
    )

    with patch(
        "src.network.ebpf.loader.map_manager.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    ):
        result = manager.read_map(map_name)

    assert result == {"0": "100", "1_2": "200"}
    payload = _events(manager)[-1].data
    assert payload["stage"] == "loader_map_manager_map_read_succeeded"
    assert payload["operation"] == "bpftool_map_dump"
    assert payload["command"] == [
        "bpftool",
        "map",
        "dump",
        "name",
        "[redacted]",
        "--json",
    ]
    assert payload["map_name_hash"] == hashlib.sha256(
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["parsed_summary"]["result_count"] == 2
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert map_name not in str(payload)
    assert "secret read payload" not in str(payload)
    assert stdout not in str(payload)


def test_update_entry_success_publishes_redacted_write_evidence(
    tmp_path,
    monkeypatch,
):
    manager = _manager(tmp_path, monkeypatch, bpftool_available=True)
    map_name = "secret_mesh_routes"
    key = "10.10.10.10"
    value = "secret-next-hop"
    stdout = "secret update output"

    with patch(
        "src.network.ebpf.loader.map_manager.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    ):
        assert manager.update_entry(map_name, key, value) is True

    payload = _events(manager)[-1].data
    assert payload["stage"] == "loader_map_manager_map_update_succeeded"
    assert payload["operation"] == "bpftool_map_update"
    assert payload["read_only"] is False
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
        map_name.encode("utf-8")
    ).hexdigest()
    assert payload["key_hash"] == hashlib.sha256(key.encode("utf-8")).hexdigest()
    assert payload["value_hash"] == hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert map_name not in str(payload)
    assert key not in str(payload)
    assert value not in str(payload)
    assert stdout not in str(payload)


def test_list_maps_success_publishes_bounded_output_metadata(
    tmp_path,
    monkeypatch,
):
    manager = _manager(tmp_path, monkeypatch, bpftool_available=True)
    stdout = json.dumps([{"id": 7, "name": "secret_runtime_map"}])

    with patch(
        "src.network.ebpf.loader.map_manager.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    ):
        result = manager.list_maps()

    assert result == [{"id": 7, "name": "secret_runtime_map"}]
    payload = _events(manager)[-1].data
    assert payload["stage"] == "loader_map_manager_map_list_succeeded"
    assert payload["operation"] == "bpftool_map_list"
    assert payload["parsed_summary"]["result_count"] == 1
    assert payload["map_names_redacted"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert "secret_runtime_map" not in str(payload)
    assert stdout not in str(payload)


def test_update_routes_unavailable_publishes_redacted_route_evidence(
    tmp_path,
    monkeypatch,
):
    manager = _manager(tmp_path, monkeypatch, bpftool_available=False)
    routes = {"10.20.30.40": "secret-iface"}

    assert manager.update_routes(routes) is False

    payload = _events(manager)[-1].data
    assert payload["stage"] == "loader_map_manager_route_update_unavailable"
    assert payload["operation"] == "bpftool_route_update"
    assert payload["read_only"] is False
    assert payload["bpftool_available"] is False
    assert payload["map_name_hash"] == hashlib.sha256(b"mesh_routes").hexdigest()
    assert payload["route_selectors_redacted"] is True
    assert payload["parsed_summary"] == {"routes_total": 1, "routes_updated": 0}
    assert "10.20.30.40" not in str(payload)
    assert "secret-iface" not in str(payload)
