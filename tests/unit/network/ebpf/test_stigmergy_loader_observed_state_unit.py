import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.coordination.events import EventBus, EventType
from src.network.ebpf.stigmergy_loader import (
    EBPF_STIGMERGY_LOADER_SERVICE_NAME,
    StigmergyBPF,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=EBPF_STIGMERGY_LOADER_SERVICE_NAME,
        limit=50,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


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
    assert "chaos_driven_design" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_stigmergy_loader_operation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["stage"] == payload["stage"]
    assert constraints["interface_redacted"] is True
    assert "interface_hash" in constraints


class _MutableMap:
    def __init__(self, rows):
        self.rows = dict(rows)
        self.updated = {}
        self.deleted = []

    def items(self):
        return list(self.rows.items())

    def __setitem__(self, key, value):
        self.updated[key] = value
        self.rows[key] = SimpleNamespace(value=value)

    def __delitem__(self, key):
        self.deleted.append(key)
        del self.rows[key]


class _RouteKey:
    def __init__(self, value):
        self.value = value


@patch("src.network.ebpf.stigmergy_loader.BCC_AVAILABLE", True)
@patch("src.network.ebpf.stigmergy_loader.BPF")
def test_load_publishes_redacted_xdp_attach_evidence(mock_bpf, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret0"
    mock_bpf.XDP = 1
    mock_bpf_instance = MagicMock()
    mock_bpf.return_value = mock_bpf_instance

    loader = StigmergyBPF(interface=interface, event_bus=bus)
    loader.load()

    mock_bpf.assert_called_once()
    mock_bpf_instance.load_func.assert_called_once_with("xdp_prog", mock_bpf.XDP)
    mock_bpf_instance.attach_xdp.assert_called_once()

    payload = _stage_payload(bus, "stigmergy_xdp_attach_succeeded")
    assert payload["operation"] == "load"
    assert payload["status"] == "success"
    assert payload["read_only"] is False
    assert payload["identity"]["redacted"] is True
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["program_path_redacted"] is True
    assert payload["function_name_redacted"] is True
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert "stigmergy_kern.c" not in str(payload)
    assert "xdp_prog" not in str(payload)


def test_bcc_unavailable_publishes_redacted_failure(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret1"
    loader = StigmergyBPF(interface=interface, event_bus=bus)

    with patch("src.network.ebpf.stigmergy_loader.BCC_AVAILABLE", False):
        with pytest.raises(RuntimeError):
            loader.load()

    payload = _stage_payload(bus, "stigmergy_bcc_unavailable")
    assert payload["status"] == "failure"
    assert payload["parsed_summary"] == {"bcc_available": False, "loaded": False}
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert "stigmergy_kern.c" not in str(payload)


def test_unload_publishes_redacted_detach_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    interface = "secret2"
    bpf = MagicMock()
    loader = StigmergyBPF(interface=interface, event_bus=bus)
    loader.bpf = bpf
    loader.running = True

    loader.unload()

    bpf.remove_xdp.assert_called_once_with(interface, 0)
    assert loader.running is False
    payload = _stage_payload(bus, "stigmergy_xdp_detach_succeeded")
    assert payload["operation"] == "unload"
    assert payload["read_only"] is False
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)


def test_get_stats_returns_raw_stats_but_event_redacts_routes(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    route_ip = "10.0.0.1"
    route_key = _RouteKey(0x0A000001)
    route_value = SimpleNamespace(value=77)
    pheromone_map = _MutableMap({route_key: route_value})
    bpf = MagicMock()
    bpf.get_table.return_value = pheromone_map
    loader = StigmergyBPF(interface="secret3", event_bus=bus)
    loader.bpf = bpf

    assert loader.get_stats() == {route_ip: 77}

    payload = _stage_payload(bus, "stigmergy_stats_read")
    assert payload["operation"] == "get_stats"
    assert payload["read_only"] is True
    assert payload["parsed_summary"]["route_count"] == 1
    assert payload["route_key_hashes"]["hashes"] == [
        hashlib.sha256(str(route_key.value).encode("utf-8")).hexdigest()
    ]
    assert payload["route_ips_redacted"] is True
    _assert_thinking_context(payload)
    assert route_ip not in str(payload)
    assert "pheromone_map" not in str(payload)


@pytest.mark.asyncio
async def test_evaporation_tick_publishes_redacted_map_mutation_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    update_key = b"secret-update-route"
    delete_key = b"secret-delete-route"
    pheromone_map = _MutableMap(
        {
            update_key: SimpleNamespace(value=100),
            delete_key: SimpleNamespace(value=4),
        }
    )
    bpf = MagicMock()
    bpf.get_table.return_value = pheromone_map
    loader = StigmergyBPF(interface="secret4", event_bus=bus)
    loader.bpf = bpf
    loader.running = True

    async def stop_after_sleep(_seconds):
        loader.running = False

    with patch("src.network.ebpf.stigmergy_loader.asyncio.sleep", stop_after_sleep):
        await loader.evaporation_loop()

    assert pheromone_map.updated[update_key] == 90
    assert delete_key in pheromone_map.deleted
    payload = _stage_payload(bus, "stigmergy_evaporation_tick_succeeded")
    assert payload["operation"] == "evaporation_loop"
    assert payload["read_only"] is False
    assert payload["parsed_summary"]["scanned_count"] == 2
    assert payload["parsed_summary"]["updated_count"] == 1
    assert payload["parsed_summary"]["deleted_count"] == 1
    assert payload["updated_key_hashes"]["hashes"] == [
        hashlib.sha256(update_key).hexdigest()
    ]
    assert payload["deleted_key_hashes"]["hashes"] == [
        hashlib.sha256(delete_key).hexdigest()
    ]
    assert payload["map_keys_redacted"] is True
    _assert_thinking_context(payload)
    assert update_key.decode("utf-8") not in str(payload)
    assert delete_key.decode("utf-8") not in str(payload)
    assert "pheromone_map" not in str(payload)
