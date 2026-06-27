from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from src.coordination.events import EventBus, EventType
from src.network.obfuscation.http_steganography import HTTPSteganography


def _extract_params(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return {key: value[0] for key, value in qs.items()}


def test_round_trip_encapsulation_decapsulation():
    stego = HTTPSteganography()
    payload = b"mesh-secret-\x00\x01\x02-binary"

    wrapped = stego.encapsulate(payload)
    params = _extract_params(wrapped["url"])
    restored = stego.decapsulate(params)

    assert restored == payload


def test_decapsulate_invalid_payload_returns_empty_bytes():
    stego = HTTPSteganography()
    restored = stego.decapsulate({"x0t_id": "%%%notbase64%%%", "payload": "???"})
    assert restored == b""


def test_encapsulate_rejects_oversized_payload():
    stego = HTTPSteganography()
    oversized = b"x" * (HTTPSteganography.MAX_DATA_BYTES + 1)

    with pytest.raises(ValueError):
        stego.encapsulate(oversized)


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="http-steganography-transport",
            limit=20,
        )
    ]


def test_encapsulate_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    stego = HTTPSteganography(event_bus=bus)
    secret_payload = b"private-mesh-payload"
    target_url = "https://front.example/private/path?token=secret-token"

    wrapped = stego.encapsulate(secret_payload, target_url=target_url)
    payload = _payloads(bus)[0]
    text = repr(payload)

    assert wrapped["method"] == "GET"
    assert payload["component"] == "network.obfuscation.http_steganography"
    assert payload["operation"] == "encapsulate"
    assert payload["status"] == "encapsulated"
    assert payload["service_name"] == "http-steganography-transport"
    assert payload["layer"] == "network_http_steganography_local_evidence"
    assert payload["http"]["method"] == "GET"
    assert payload["http"]["query_params_total"] == 3
    assert payload["target_url"]["host_hash"]
    assert payload["target_url"]["path_hash"]
    assert payload["target_url"]["raw_target_url_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["raw_query_values_redacted"] is True
    assert payload["raw_headers_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "private-mesh-payload" not in text
    assert "front.example" not in text
    assert "secret-token" not in text


def test_decapsulate_success_and_malformed_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    stego = HTTPSteganography(event_bus=bus)

    secret_payload = b"decoded-secret-payload-that-crosses-split"
    wrapped = stego.encapsulate(secret_payload)
    params = _extract_params(wrapped["url"])
    assert stego.decapsulate(params) == secret_payload
    assert stego.decapsulate({"x0t_id": "%%%notbase64%%%", "payload": "???"}) == b""

    payloads = _payloads(bus)
    decapsulated = [p for p in payloads if p["operation"] == "decapsulate"]

    assert [p["status"] for p in decapsulated] == ["decapsulated", "malformed"]
    assert decapsulated[0]["query"]["id_param_present"] is True
    assert decapsulated[0]["query"]["payload_param_present"] is True
    assert decapsulated[0]["payloads_redacted"] is True
    assert decapsulated[1]["error"] == {
        "type": "Base64DecodeError",
        "message_redacted": True,
    }
    assert "decoded-secret-payload-that-crosses-split" not in repr(decapsulated)
    assert "%%%notbase64%%%" not in repr(decapsulated)


def test_encapsulate_invalid_type_publishes_failed_event(tmp_path):
    bus = EventBus(str(tmp_path))
    stego = HTTPSteganography(event_bus=bus)

    with pytest.raises(TypeError):
        stego.encapsulate("not-bytes")  # type: ignore[arg-type]

    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="http-steganography-transport",
        limit=10,
    )

    assert len(failed_events) == 1
    payload = failed_events[0].data
    assert payload["operation"] == "encapsulate"
    assert payload["status"] == "failed"
    assert payload["input"]["bytes_like"] is False
    assert payload["error"]["type"] == "TypeError"
