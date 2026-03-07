from __future__ import annotations

from urllib.parse import parse_qs, urlparse

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

    try:
        stego.encapsulate(oversized)
        assert False, "Expected ValueError for oversized payload"
    except ValueError:
        pass

