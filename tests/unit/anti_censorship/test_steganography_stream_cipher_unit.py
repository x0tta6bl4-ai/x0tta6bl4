from src.anti_censorship.steganography import (
    EmbeddingResult,
    ExtractionResult,
    SteganographyEngine,
    SteganographyCarrier,
    SteganographyConfig,
    SteganographyType,
)
from src.coordination.events import EventBus, EventType


class _DummyCarrier(SteganographyCarrier):
    def get_capacity(self, carrier_data: bytes) -> int:
        return len(carrier_data)

    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        return EmbeddingResult(success=True, carrier_data=carrier_data)

    def extract(self, carrier_data: bytes) -> ExtractionResult:
        return ExtractionResult(success=True, hidden_data=carrier_data)


def test_stream_cipher_roundtrip_uses_nonce_and_decrypts():
    carrier = _DummyCarrier(SteganographyConfig(encryption_key=b"test-key"))
    key = carrier._derive_key()
    plaintext = b"secret-payload"

    encrypted_1 = carrier._stream_cipher_encrypt(plaintext, key)
    encrypted_2 = carrier._stream_cipher_encrypt(plaintext, key)

    assert encrypted_1 != encrypted_2
    assert len(encrypted_1) == len(plaintext) + carrier._STREAM_NONCE_SIZE
    assert carrier._stream_cipher_decrypt(encrypted_1, key) == plaintext
    assert carrier._stream_cipher_decrypt(encrypted_2, key) == plaintext


def test_stream_cipher_decrypt_rejects_too_short_payload():
    carrier = _DummyCarrier()
    key = carrier._derive_key()
    assert carrier._stream_cipher_decrypt(b"short", key) == b""


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="anti-censorship-steganography-engine",
            limit=20,
        )
    ]


def test_engine_embed_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    engine = SteganographyEngine(
        SteganographyConfig(use_encryption=True, encryption_key=b"secret-key"),
        event_bus=bus,
    )
    carrier = b"cover text " * 200
    hidden = b"hidden-local-stego-payload"

    result = engine.embed(carrier, hidden, SteganographyType.TEXT)
    payload = _payloads(bus)[0]
    text = repr(payload)

    assert result.success is True
    assert payload["component"] == "anti_censorship.steganography"
    assert payload["operation"] == "embed"
    assert payload["status"] == "embedded"
    assert payload["service_name"] == "anti-censorship-steganography-engine"
    assert payload["layer"] == "anti_censorship_steganography_local_evidence"
    assert payload["carrier_type"] == "text"
    assert payload["config"]["encryption_key_present"] is True
    assert payload["config"]["raw_encryption_key_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["carrier_bytes_redacted"] is True
    assert payload["hidden_data_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["external_dpi_tested"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "hidden-local-stego-payload" not in text
    assert "secret-key" not in text
    assert "cover text" not in text


def test_engine_extract_failure_redacts_payload_and_error_message(tmp_path):
    bus = EventBus(str(tmp_path))
    engine = SteganographyEngine(
        SteganographyConfig(use_encryption=False),
        event_bus=bus,
    )

    result = engine.extract(b"carrier-with-no-hidden-data", SteganographyType.TEXT)
    payload = _payloads(bus)[0]

    assert result.success is False
    assert payload["operation"] == "extract"
    assert payload["status"] == "extract_failed"
    assert payload["carrier_type"] == "text"
    assert payload["error_message_redacted"] is True
    assert payload["hidden_data_present"] is False
    assert payload["extracted_data_redacted"] is True
    assert "carrier-with-no-hidden-data" not in repr(payload)
    assert result.error_message not in repr(payload)


def test_engine_unsupported_carrier_publishes_failed_event(tmp_path):
    bus = EventBus(str(tmp_path))
    engine = SteganographyEngine(event_bus=bus)

    result = engine.embed(b"carrier", b"secret", "unsupported")  # type: ignore[arg-type]
    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="anti-censorship-steganography-engine",
        limit=10,
    )

    assert result.success is False
    assert len(failed_events) == 1
    payload = failed_events[0].data
    assert payload["operation"] == "embed"
    assert payload["status"] == "unsupported"
    assert payload["carrier_type"] == "unsupported"
    assert payload["payloads_redacted"] is True
    assert "secret" not in repr(payload)


def test_engine_create_covert_channel_records_local_intent_not_delivery(tmp_path):
    bus = EventBus(str(tmp_path))
    engine = SteganographyEngine(
        SteganographyConfig(use_encryption=False),
        event_bus=bus,
    )

    result = engine.create_covert_channel(
        b"covert-channel-secret",
        SteganographyType.PROTOCOL,
    )
    payload = _payloads(bus)[0]

    assert result.success is True
    assert payload["operation"] == "create_covert_channel"
    assert payload["status"] == "created"
    assert payload["carrier_type"] == "protocol"
    assert payload["generated_cover_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert "covert-channel-secret" not in repr(payload)
    assert "covert.example.com" not in repr(payload)
