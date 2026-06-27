#!/usr/bin/env python3
"""Unit tests for x0tta6bl4 Hybrid TLS module."""

import json
import os
from unittest.mock import MagicMock

import pytest

try:
    import oqs

    HAS_KEYENCAPSULATION = hasattr(oqs, "KeyEncapsulation")
    HAS_SIGNATURE = hasattr(oqs, "Signature")
except ImportError:
    HAS_KEYENCAPSULATION = False
    HAS_SIGNATURE = False

from src.security.pqc.hybrid_tls import (HybridTLSContext, hybrid_decrypt,
                                         hybrid_encrypt, hybrid_handshake,
                                         measure_handshake_overhead)
from src.security.pqc.hybrid_tls_demo import generate_report


@pytest.fixture
def mock_oqs_key_encapsulation(monkeypatch):
    """Mock the PQC adapter boundary used by HybridTLSContext."""

    class _FakePQCAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def kem_generate_keypair(self):
            return b"mock_kem_public_key", b"mock_kem_private_key"

        def sig_generate_keypair(self):
            return b"mock_sig_public_key", b"mock_sig_private_key"

        def kem_encapsulate(self, _public_key):
            return b"mock_ciphertext", b"mock_shared_secret"

        def kem_decapsulate(self, _private_key, _ciphertext):
            return b"mock_shared_secret"

        def sig_sign(self, _message, _private_key):
            return b"mock_signature"

        def sig_verify(self, _message, _signature, _public_key):
            return True

    monkeypatch.setattr("src.security.pqc.hybrid_tls.PQCAdapter", _FakePQCAdapter)
    yield _FakePQCAdapter


@pytest.fixture
def mock_oqs_signature():
    """Kept for existing test signatures; PQC is mocked at adapter boundary."""
    yield MagicMock()


@pytest.mark.skipif(
    not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available"
)
def test_handshake_agreement(mock_oqs_key_encapsulation, mock_oqs_signature):
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    client_session_key, server_session_key = hybrid_handshake(client, server)

    assert (
        client.session_key
        == server.session_key
        == client_session_key
        == server_session_key
    )


@pytest.mark.skipif(
    not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available"
)
def test_encrypt_decrypt_roundtrip(mock_oqs_key_encapsulation, mock_oqs_signature):
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    session_key, _ = hybrid_handshake(client, server)

    payloads = [
        b"mesh heartbeat",
        b"node-7 to node-3",
        b"topology update",
        b"x" * 1000,
    ]

    for plaintext in payloads:
        ciphertext = hybrid_encrypt(session_key, plaintext)
        decrypted = hybrid_decrypt(session_key, ciphertext)
        assert decrypted == plaintext


@pytest.mark.skipif(
    not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available"
)
def test_handshake_performance_sla(mock_oqs_key_encapsulation, mock_oqs_signature):
    overhead_ms = measure_handshake_overhead()
    sla_ms = float(os.getenv("HYBRID_TLS_HANDSHAKE_SLA_MS", "250"))
    assert overhead_ms < sla_ms


@pytest.mark.skipif(
    not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available"
)
def test_mesh_heartbeat_report_generation(
    tmp_path, mock_oqs_key_encapsulation, mock_oqs_signature
):
    report_path = tmp_path / "hybrid_tls_report.json"
    report = generate_report(path=str(report_path))

    assert report["test"] == "Hybrid TLS (ECDHE + Kyber + Dilithium)"
    assert report["results"]["handshake"] == "✓ PASS"
    assert isinstance(report["results"]["handshake_ms"], float)

    on_disk = json.loads(report_path.read_text())
    assert on_disk["results"]["handshake_ms"] == report["results"]["handshake_ms"]
