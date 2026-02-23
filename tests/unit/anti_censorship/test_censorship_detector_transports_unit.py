"""Focused unit tests for anti_censorship detector/transports modules."""

from __future__ import annotations

import struct

import pytest

censorship = pytest.importorskip("src.anti_censorship.censorship_detector")
transports = pytest.importorskip("src.anti_censorship.transports")


def test_detection_result_and_summary_lifecycle():
    detector = censorship.CensorshipDetector()
    result = censorship.DetectionResult(
        blocking_type=censorship.BlockingType.DNS_MANIPULATION,
        is_blocked=True,
        confidence=0.9,
        target="example.com",
        details={"k": "v"},
    )
    as_dict = result.to_dict()
    assert as_dict["blocking_type"] == "dns_manipulation"
    assert as_dict["is_blocked"] is True

    detector._results = [result]
    summary = detector.get_summary()
    assert summary["total_tests"] == 1
    assert summary["blocked_count"] == 1
    assert summary["by_type"]["dns_manipulation"] == 1

    detector.clear_results()
    assert detector.get_summary()["total_tests"] == 0


def test_detect_tcp_blocking_reset_path(monkeypatch):
    class _Sock:
        def settimeout(self, _timeout):
            return None

        def connect(self, _addr):
            raise ConnectionResetError("rst")

        def close(self):
            return None

    monkeypatch.setattr(censorship.socket, "socket", lambda *_a, **_k: _Sock())
    monkeypatch.setattr(censorship.time, "sleep", lambda *_a, **_k: None)

    detector = censorship.CensorshipDetector(censorship.ProbeConfig(retries=3, tcp_timeout=0.01))
    result = detector.detect_tcp_blocking("blocked.example", 443)

    assert result.blocking_type == censorship.BlockingType.TCP_RESET
    assert result.is_blocked is True
    assert result.confidence == 0.9


def test_detect_http_blocking_status_and_redirect(monkeypatch):
    class _Resp:
        def __init__(self, status_code, location="", text="blocked"):
            self.status_code = status_code
            self.headers = {"Location": location} if location else {}
            self.text = text

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: _Resp(302, location="https://isp.example/block-page"),
    )

    detector = censorship.CensorshipDetector()
    result = detector.detect_http_blocking("https://target.example", expected_content="ok")

    assert result.blocking_type == censorship.BlockingType.HTTP_BLOCKING
    assert result.is_blocked is True
    assert result.details["redirect_location"].endswith("block-page")


def test_run_full_scan_and_summary(monkeypatch):
    detector = censorship.CensorshipDetector()

    def _none(target):
        return censorship.DetectionResult(
            blocking_type=censorship.BlockingType.NONE,
            is_blocked=False,
            confidence=0.0,
            target=target,
        )

    monkeypatch.setattr(detector, "detect_dns_manipulation", lambda target: _none(target))
    monkeypatch.setattr(detector, "detect_tcp_blocking", lambda target, port: _none(f"{target}:{port}"))
    monkeypatch.setattr(detector, "detect_tls_interception", lambda target: _none(target))
    monkeypatch.setattr(detector, "detect_http_blocking", lambda url: _none(url))
    monkeypatch.setattr(detector, "detect_throttling", lambda target: _none(target))

    results = detector.run_full_scan(["a.example", "b.example"], include_throttling=True)
    assert len(results) == 10

    summary = detector.get_summary()
    assert summary["total_tests"] == 10
    assert summary["blocked_count"] == 0


def test_create_transport_and_obfs4_packet_helpers():
    obfs4 = transports.create_transport("obfs4")
    meek = transports.create_transport("meek", front_domain="cdn.example")
    snowflake = transports.create_transport("snowflake", broker_url="https://broker")

    assert isinstance(obfs4, transports.OBFS4Transport)
    assert isinstance(meek, transports.MeekTransport)
    assert isinstance(snowflake, transports.SnowflakeTransport)

    handshake = obfs4._generate_handshake()
    size = struct.unpack(">H", handshake[:2])[0]
    assert size == len(handshake) - 2

    key = b"k" * 32
    obfs4._send_key = key
    obfs4._receive_key = key
    payload = b"hello-anti-censorship"
    encrypted = obfs4._encrypt_packet(payload)
    decrypted = obfs4._decrypt_packet(encrypted)
    assert decrypted == payload

    stats = obfs4.get_stats()
    assert stats["type"] == transports.TransportType.OBFS4.value
    assert stats["connected"] is False


def test_create_transport_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unsupported transport type"):
        transports.create_transport("invalid-transport")
