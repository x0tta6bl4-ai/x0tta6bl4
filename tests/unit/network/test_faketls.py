import struct
import unittest

from src.coordination.events import EventBus, EventType
from src.network.obfuscation.faketls import FakeTLSTransport


class TestFakeTLS(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTLSTransport(sni="cloudflare.com")

    def test_client_hello_structure(self):
        hello = self.transport.generate_client_hello()

        # Check TLS Record Header
        content_type, version, length = struct.unpack("!BHH", hello[:5])
        self.assertEqual(content_type, 0x16)  # Handshake
        self.assertEqual(version, 0x0301)  # TLS 1.0 legacy version
        self.assertEqual(length, len(hello) - 5)

        # Check Handshake Header
        msg_type = hello[5]
        self.assertEqual(msg_type, 0x01)  # ClientHello

        # Check SNI presence
        self.assertIn(b"cloudflare.com", hello)

    def test_app_data_obfuscation(self):
        payload = b"Sensitive Data"
        obfuscated = self.transport.obfuscate(payload)

        # Check TLS Record Header
        content_type, version, length = struct.unpack("!BHH", obfuscated[:5])
        self.assertEqual(content_type, 0x17)  # Application Data
        self.assertEqual(version, 0x0303)  # TLS 1.2 legacy version
        self.assertEqual(length, len(payload))

        # Check payload
        self.assertEqual(obfuscated[5:], payload)

    def test_deobfuscate_full_record(self):
        payload = b"Hidden"
        obfuscated = self.transport.obfuscate(payload)
        deobfuscated = self.transport.deobfuscate(obfuscated)
        self.assertEqual(deobfuscated, payload)


def test_faketls_event_evidence_redacts_sni_and_payload(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    transport = FakeTLSTransport(sni="secret-sni.example", event_bus=bus)

    record = transport.obfuscate(b"raw-payload-secret")
    assert transport.deobfuscate(record) == b"raw-payload-secret"

    events = bus.get_event_history(source_agent="faketls-transport")
    assert [event.data["operation"] for event in events] == [
        "obfuscate",
        "deobfuscate",
    ]

    for event in events:
        payload = event.data
        assert event.event_type == EventType.PIPELINE_STAGE_END
        assert payload["payloads_redacted"] is True
        assert payload["raw_parameters_redacted"] is True
        assert payload["dataplane_confirmed"] is False
        assert payload["dpi_bypass_confirmed"] is False
        assert payload["bypass_confirmed"] is False
        assert payload["claim_boundary"]

        rendered = repr(payload)
        assert "secret-sni.example" not in rendered
        assert "raw-payload-secret" not in rendered


def test_faketls_incomplete_record_event_is_failed_without_raw_payload(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    transport = FakeTLSTransport(sni="secret-sni.example", event_bus=bus)
    incomplete = b"\x17\x03\x03\x00\x10raw-secret"

    try:
        transport.deobfuscate(incomplete)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for incomplete FakeTLS record")

    event = bus.get_event_history(source_agent="faketls-transport")[-1]
    payload = event.data
    assert event.event_type == EventType.TASK_FAILED
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "ValueError"
    assert payload["error"]["message_redacted"] is True
    assert payload["dpi_bypass_confirmed"] is False
    assert "raw-secret" not in repr(payload)
    assert "secret-sni.example" not in repr(payload)


if __name__ == "__main__":
    unittest.main()
