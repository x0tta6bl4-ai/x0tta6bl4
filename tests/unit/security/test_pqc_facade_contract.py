"""Facade representation tests; native cryptography is covered by Hypothesis CI."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.security.pqc.simple import PQC
from src.security.pqc.types import PQCKeyPair


def test_sign_returns_bytes_and_preserves_native_signature():
    pqc = PQC()
    pqc._dsa = Mock()
    pqc._dsa.sign.return_value = SimpleNamespace(signature_bytes=b"signature")
    assert pqc.sign(b"payload", b"secret") == b"signature"
    pqc._dsa.sign.assert_called_once_with(b"payload", b"secret")


def test_wrong_algorithm_rejected_before_backend_without_secret_disclosure():
    pqc = PQC()
    pqc._dsa = Mock()
    key = PQCKeyPair("ML-KEM-768", b"public", b"private-secret")
    with pytest.raises(TypeError, match="supplied to sign") as error:
        pqc.sign(b"payload", key)
    assert "private-secret" not in str(error.value)
    assert "private-secret" not in repr(key)
    pqc._dsa.sign.assert_not_called()


def test_dsa_keypair_is_normalized_to_secret_bytes():
    pqc = PQC()
    pqc._dsa = Mock()
    pqc._dsa.sign.return_value = SimpleNamespace(signature_bytes=b"signature")
    key = PQCKeyPair("ML-DSA-65", b"public", b"secret")
    assert pqc.sign(b"payload", key) == b"signature"
    pqc._dsa.sign.assert_called_once_with(b"payload", b"secret")
