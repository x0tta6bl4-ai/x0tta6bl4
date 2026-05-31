import importlib
import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.coordination.events import EventBus, EventType
from src.anti_censorship.stego_mesh import StegoMeshProtocol


def test_import_smoke():
    try:
        mod = importlib.import_module("src.anti_censorship.stego_mesh")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="anti-censorship-stego-mesh",
            limit=20,
        )
    ]


def test_encode_packet_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    protocol = StegoMeshProtocol(b"k" * 32, event_bus=bus)
    secret_payload = b"SECRET_LOCAL_STEGO_PAYLOAD"

    encoded = protocol.encode_packet(secret_payload, "http")
    payload = _payloads(bus)[0]
    text = repr(payload)

    assert isinstance(encoded, bytes)
    assert payload["component"] == "anti_censorship.stego_mesh"
    assert payload["operation"] == "encode_packet"
    assert payload["status"] == "encoded"
    assert payload["service_name"] == "anti-censorship-stego-mesh"
    assert payload["layer"] == "anti_censorship_stego_mesh_local_evidence"
    assert payload["protocol_mimic"] == "http"
    assert payload["crypto"]["nonce_present"] is True
    assert payload["crypto"]["hmac_present"] is True
    assert payload["key_material"]["raw_key_material_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["raw_packets_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["external_dpi_tested"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "SECRET_LOCAL_STEGO_PAYLOAD" not in text
    assert "kkkkkkkk" not in text
    assert "HTTP/1.1" not in text


def test_dpi_probe_is_recorded_as_local_marker_probe_not_bypass(tmp_path):
    bus = EventBus(str(tmp_path))
    protocol = StegoMeshProtocol(b"k" * 32, event_bus=bus)

    result = protocol.test_dpi_evasion(b"SECRET_DPI_PROBE_PAYLOAD", "dns")
    payload = [p for p in _payloads(bus) if p["operation"] == "test_dpi_evasion"][0]

    assert result in {True, False}
    assert payload["status"] in {"local_probe_passed", "local_probe_failed"}
    assert payload["protocol_mimic"] == "dns"
    assert payload["local_marker_probe"] is True
    assert payload["external_dpi_tested"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["dataplane_confirmed"] is False
    assert "SECRET_DPI_PROBE_PAYLOAD" not in repr(payload)


def test_decode_marker_missing_publishes_redacted_observed_state(tmp_path):
    bus = EventBus(str(tmp_path))
    protocol = StegoMeshProtocol(b"k" * 32, event_bus=bus)

    decoded = protocol.decode_packet(b"raw-secret-without-stego-marker")
    payload = _payloads(bus)[0]

    assert decoded is None
    assert payload["operation"] == "decode_packet"
    assert payload["status"] == "marker_missing"
    assert payload["marker_present"] is False
    assert payload["raw_packets_redacted"] is True
    assert payload["dpi_bypass_confirmed"] is False
    assert "raw-secret-without-stego-marker" not in repr(payload)


def test_encode_invalid_payload_type_publishes_failed_event(tmp_path):
    bus = EventBus(str(tmp_path))
    protocol = StegoMeshProtocol(b"k" * 32, event_bus=bus)

    with pytest.raises(TypeError):
        protocol.encode_packet("not-bytes")  # type: ignore[arg-type]

    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="anti-censorship-stego-mesh",
        limit=10,
    )

    assert len(failed_events) == 1
    payload = failed_events[0].data
    assert payload["operation"] == "encode_packet"
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "TypeError"
    assert payload["payloads_redacted"] is True
