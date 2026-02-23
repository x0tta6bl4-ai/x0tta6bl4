from src.anti_censorship.steganography import (
    EmbeddingResult,
    ExtractionResult,
    SteganographyCarrier,
    SteganographyConfig,
)


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
