"""Focused unit tests for anti_censorship detector/transports modules."""

from __future__ import annotations

import struct

import pytest

from src.coordination.events import EventBus

censorship = pytest.importorskip("src.anti_censorship.censorship_detector")
transports = pytest.importorskip("src.anti_censorship.transports")


def _payloads(bus: EventBus, source_agent: str) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(source_agent=source_agent, limit=30)
    ]


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


def test_detect_tcp_blocking_publishes_redacted_local_evidence(tmp_path, monkeypatch):
    bus = EventBus(str(tmp_path))

    class _Sock:
        def settimeout(self, _timeout):
            return None

        def connect(self, _addr):
            raise ConnectionResetError("SECRET-RST-ERROR")

        def close(self):
            return None

    monkeypatch.setattr(censorship.socket, "socket", lambda *_a, **_k: _Sock())
    monkeypatch.setattr(censorship.time, "sleep", lambda *_a, **_k: None)

    detector = censorship.CensorshipDetector(
        censorship.ProbeConfig(retries=3, tcp_timeout=0.01),
        event_bus=bus,
    )
    result = detector.detect_tcp_blocking("secret.blocked.example", 443)
    payload = _payloads(bus, "anti-censorship-censorship-detector")[0]
    text = repr(payload)

    assert result.is_blocked is True
    assert payload["operation"] == "detect_tcp_blocking"
    assert payload["status"] == "observed"
    assert payload["service_name"] == "anti-censorship-censorship-detector"
    assert payload["layer"] == "anti_censorship_censorship_detector_local_evidence"
    assert payload["blocking_type"] == "tcp_reset"
    assert payload["local_probe_blocked"] is True
    assert payload["target_hash"]
    assert payload["target_redacted"] is True
    assert payload["raw_attempts_redacted"] is True
    assert payload["raw_errors_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["external_dpi_tested"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "secret.blocked.example" not in text
    assert "SECRET-RST-ERROR" not in text


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


def test_detect_http_blocking_redacts_url_headers_and_redirect(tmp_path, monkeypatch):
    bus = EventBus(str(tmp_path))

    class _Resp:
        status_code = 302
        headers = {
            "Location": "https://isp.example/SECRET-BLOCK-PAGE",
            "X-Secret": "SECRET-HEADER-VALUE",
        }
        text = "blocked"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: _Resp())

    detector = censorship.CensorshipDetector(event_bus=bus)
    detector.detect_http_blocking(
        "https://secret-target.example/path",
        expected_content="ok",
    )
    payload = _payloads(bus, "anti-censorship-censorship-detector")[0]
    text = repr(payload)

    assert payload["operation"] == "detect_http_blocking"
    assert payload["blocking_type"] == "http_blocking"
    assert payload["redirect_location_present"] is True
    assert payload["raw_response_headers_redacted"] is True
    assert payload["raw_redirect_location_redacted"] is True
    assert "secret-target.example" not in text
    assert "SECRET-BLOCK-PAGE" not in text
    assert "SECRET-HEADER-VALUE" not in text


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


def test_summary_and_clear_publish_bounded_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    detector = censorship.CensorshipDetector(event_bus=bus)
    detector._results = [
        censorship.DetectionResult(
            blocking_type=censorship.BlockingType.DNS_MANIPULATION,
            is_blocked=True,
            confidence=0.9,
            target="secret.summary.example",
        )
    ]

    summary = detector.get_summary()
    detector.clear_results()
    payloads = _payloads(bus, "anti-censorship-censorship-detector")

    assert summary["total_tests"] == 1
    assert [payload["operation"] for payload in payloads] == [
        "get_summary",
        "clear_results",
    ]
    assert payloads[0]["result_type_counts"] == {"dns_manipulation": 1}
    assert payloads[1]["cleared_count"] == 1
    assert "secret.summary.example" not in repr(payloads)


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


def test_transport_factory_and_stats_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    transport = transports.create_transport(
        "obfs4",
        node_id=b"SECRET-NODE-ID",
        private_key=b"SECRET-PRIVATE-KEY-000000000000",
        event_bus=bus,
    )

    stats = transport.get_stats()
    payloads = _payloads(bus, "anti-censorship-pluggable-transport")
    text = repr(payloads)

    assert stats["type"] == transports.TransportType.OBFS4.value
    assert [payload["operation"] for payload in payloads] == [
        "create_transport",
        "get_stats",
    ]
    assert payloads[0]["status"] == "created"
    assert payloads[0]["service_name"] == "anti-censorship-pluggable-transport"
    assert payloads[0]["layer"] == "anti_censorship_pluggable_transport_local_evidence"
    assert payloads[0]["config"]["node_id_present"] is True
    assert payloads[0]["config"]["private_key_present"] is True
    assert payloads[0]["config"]["raw_keys_redacted"] is True
    assert payloads[0]["config"]["raw_node_id_redacted"] is True
    assert payloads[1]["bytes_sent_bucket"] == "zero"
    assert payloads[1]["dataplane_confirmed"] is False
    assert payloads[1]["dpi_bypass_confirmed"] is False
    assert payloads[1]["bypass_confirmed"] is False
    assert payloads[1]["external_dpi_tested"] is False
    assert "SECRET-NODE-ID" not in text
    assert "SECRET-PRIVATE-KEY" not in text


def test_meek_transport_config_evidence_redacts_front_domain_and_broker(tmp_path):
    bus = EventBus(str(tmp_path))
    transport = transports.create_transport(
        "meek",
        front_domain="secret-front.example",
        meek_url="https://secret-meek.example/path",
        broker_url="https://secret-broker.example",
        event_bus=bus,
    )

    transport.get_stats()
    payloads = _payloads(bus, "anti-censorship-pluggable-transport")
    text = repr(payloads)

    assert payloads[0]["config"]["front_domain_present"] is True
    assert payloads[0]["config"]["meek_url_present"] is True
    assert payloads[0]["config"]["broker_url_present"] is True
    assert payloads[0]["config"]["raw_domains_redacted"] is True
    assert payloads[0]["config"]["raw_urls_redacted"] is True
    assert "secret-front.example" not in text
    assert "secret-meek.example" not in text
    assert "secret-broker.example" not in text
