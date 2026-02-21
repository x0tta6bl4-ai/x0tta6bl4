"""Unit tests for PQC data types."""
import os
import pytest
from datetime import datetime, timedelta

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.security.pqc.types import (
    PQCAlgorithm,
    PQCStatus,
    PQCKeyPair,
    PQCSignature,
    PQCEncapsulationResult,
    PQCSession,
)


class TestPQCAlgorithm:
    def test_kem_algorithms(self):
        assert PQCAlgorithm.ML_KEM_768.value == "ML-KEM-768"
        assert PQCAlgorithm.ML_KEM_512.value == "ML-KEM-512"
        assert PQCAlgorithm.ML_KEM_1024.value == "ML-KEM-1024"

    def test_dsa_algorithms(self):
        assert PQCAlgorithm.ML_DSA_44.value == "ML-DSA-44"
        assert PQCAlgorithm.ML_DSA_65.value == "ML-DSA-65"
        assert PQCAlgorithm.ML_DSA_87.value == "ML-DSA-87"


class TestPQCStatus:
    def test_status_values(self):
        assert PQCStatus.AVAILABLE.value == "available"
        assert PQCStatus.UNAVAILABLE.value == "unavailable"
        assert PQCStatus.ERROR.value == "error"
        assert PQCStatus.FALLBACK.value == "fallback"


class TestPQCKeyPair:
    def test_create_keypair(self):
        kp = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"\x01" * 32,
            secret_key=b"\x02" * 32,
        )
        assert kp.algorithm == "ML-KEM-768"
        assert kp.key_id  # auto-generated
        assert len(kp.key_id) == 16

    def test_is_expired_no_expiry(self):
        kp = PQCKeyPair(algorithm="ML-KEM-768", public_key=b"pk", secret_key=b"sk")
        assert not kp.is_expired()

    def test_is_expired_future(self):
        kp = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"pk",
            secret_key=b"sk",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert not kp.is_expired()

    def test_is_expired_past(self):
        kp = PQCKeyPair(
            algorithm="ML-KEM-768",
            public_key=b"pk",
            secret_key=b"sk",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert kp.is_expired()

    def test_is_valid(self):
        kp = PQCKeyPair(algorithm="ML-KEM-768", public_key=b"pk", secret_key=b"sk")
        assert kp.is_valid()

    def test_is_valid_empty_key(self):
        kp = PQCKeyPair(algorithm="ML-KEM-768", public_key=b"", secret_key=b"sk")
        assert not kp.is_valid()

    def test_to_dict(self):
        kp = PQCKeyPair(algorithm="ML-KEM-768", public_key=b"\xab\xcd", secret_key=b"sk")
        d = kp.to_dict()
        assert d["algorithm"] == "ML-KEM-768"
        assert d["public_key_hex"] == "abcd"
        assert "is_expired" in d

    def test_from_dict_roundtrip(self):
        kp = PQCKeyPair(algorithm="ML-KEM-768", public_key=b"\xab\xcd", secret_key=b"\xef")
        d = kp.to_dict()
        d["secret_key_hex"] = kp.secret_key.hex()
        kp2 = PQCKeyPair.from_dict(d)
        assert kp2.algorithm == kp.algorithm
        assert kp2.public_key == kp.public_key


class TestPQCSignature:
    def test_create_and_serialize(self):
        sig = PQCSignature(
            algorithm="ML-DSA-65",
            signature_bytes=b"\x01\x02\x03",
            message_hash=b"\x04\x05\x06",
            signer_key_id="abc",
        )
        d = sig.to_dict()
        assert d["algorithm"] == "ML-DSA-65"
        assert d["signature_hex"] == "010203"
        assert d["signer_key_id"] == "abc"

    def test_from_dict(self):
        d = {
            "algorithm": "ML-DSA-65",
            "signature_hex": "aabb",
            "message_hash_hex": "ccdd",
            "timestamp": datetime.utcnow().isoformat(),
        }
        sig = PQCSignature.from_dict(d)
        assert sig.signature_bytes == b"\xaa\xbb"


class TestPQCEncapsulationResult:
    def test_to_dict(self):
        r = PQCEncapsulationResult(
            ciphertext=b"\x00" * 100,
            shared_secret=b"\x01" * 32,
            algorithm="ML-KEM-768",
        )
        d = r.to_dict()
        assert d["ciphertext_len"] == 100
        assert d["shared_secret_len"] == 32


class TestPQCSession:
    def test_not_expired(self):
        s = PQCSession(
            session_id="s1",
            algorithm="ML-KEM-768",
            shared_secret=b"secret",
            peer_public_key=b"pk",
        )
        assert not s.is_expired()

    def test_expired(self):
        s = PQCSession(
            session_id="s1",
            algorithm="ML-KEM-768",
            shared_secret=b"secret",
            peer_public_key=b"pk",
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
        assert s.is_expired()

    def test_to_dict_no_secret(self):
        s = PQCSession(
            session_id="s1",
            algorithm="ML-KEM-768",
            shared_secret=b"secret",
            peer_public_key=b"\xab",
        )
        d = s.to_dict()
        assert "shared_secret" not in str(d) or "secret" not in d.get("shared_secret", "")
        assert d["session_id"] == "s1"
