#!/usr/bin/env python3
"""Unit tests for x0tta6bl4 Hybrid TLS module."""

import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

try:
    import oqs
    HAS_KEYENCAPSULATION = hasattr(oqs, 'KeyEncapsulation')
    HAS_SIGNATURE = hasattr(oqs, 'Signature')
except ImportError:
    HAS_KEYENCAPSULATION = False
    HAS_SIGNATURE = False

from src.security.pqc.hybrid_tls import (
    HybridTLSContext,
    hybrid_handshake,
    hybrid_encrypt,
    hybrid_decrypt,
    measure_handshake_overhead,
)
from src.security.pqc.hybrid_tls_demo import generate_report


@pytest.fixture
def mock_oqs_key_encapsulation():
    """Mock oqs.KeyEncapsulation for tests."""
    with patch('src.security.pqc.pqc_adapter.oqs.KeyEncapsulation') as mock_kem:
        mock_kem_instance = MagicMock()
        mock_kem_instance.generate_keypair.return_value = (b"mock_public_key", b"mock_private_key")
        shared_secret = b"mock_shared_secret"
        mock_kem_instance.encap_secret.return_value = (b"mock_ciphertext", shared_secret)
        mock_kem_instance.decap_secret.return_value = shared_secret
        mock_kem.return_value.__enter__.return_value = mock_kem_instance
        yield mock_kem_instance


@pytest.fixture
def mock_oqs_signature():
    """Mock oqs.Signature for tests."""
    with patch('src.security.pqc.pqc_adapter.oqs.Signature') as mock_sig:
        mock_sig_instance = MagicMock()
        mock_sig_instance.generate_keypair.return_value = (b"mock_public_key", b"mock_private_key")
        mock_sig_instance.sign.return_value = b"mock_signature"
        mock_sig_instance.verify.return_value = True
        mock_sig.return_value.__enter__.return_value = mock_sig_instance
        yield mock_sig_instance


@pytest.mark.skipif(not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available")
def test_handshake_agreement(mock_oqs_key_encapsulation, mock_oqs_signature):
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    client_session_key, server_session_key = hybrid_handshake(client, server)

    assert client.session_key == server.session_key == client_session_key == server_session_key


@pytest.mark.skipif(not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available")
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


@pytest.mark.skipif(not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available")
def test_handshake_performance_sla(mock_oqs_key_encapsulation, mock_oqs_signature):
    overhead_ms = measure_handshake_overhead()
    assert overhead_ms < 100.0


@pytest.mark.skipif(not HAS_KEYENCAPSULATION, reason="oqs.KeyEncapsulation not available")
def test_mesh_heartbeat_report_generation(tmp_path, mock_oqs_key_encapsulation, mock_oqs_signature):
    report_path = tmp_path / "hybrid_tls_report.json"
    report = generate_report(path=str(report_path))

    assert report["test"] == "Hybrid TLS (ECDHE + Kyber + Dilithium)"
    assert report["results"]["handshake"] == "✓ PASS"
    assert isinstance(report["results"]["handshake_ms"], float)

    on_disk = json.loads(report_path.read_text())
    assert on_disk["results"]["handshake_ms"] == report["results"]["handshake_ms"]
