#!/usr/bin/env python3
"""Unit tests for x0tta6bl4 Hybrid TLS module."""

import json
from datetime import datetime

from src.security.pqc.hybrid_tls import (
    HybridTLSContext,
    hybrid_handshake,
    hybrid_encrypt,
    hybrid_decrypt,
    measure_handshake_overhead,
)
from src.security.pqc.hybrid_tls_demo import generate_report


def test_handshake_agreement():
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    session_key = hybrid_handshake(client, server)

    assert client.session_key == server.session_key == session_key


def test_encrypt_decrypt_roundtrip():
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    session_key = hybrid_handshake(client, server)

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


def test_handshake_performance_sla():
    overhead_ms = measure_handshake_overhead()
    assert overhead_ms < 100.0


def test_mesh_heartbeat_report_generation(tmp_path):
    report_path = tmp_path / "hybrid_tls_report.json"
    report = generate_report(path=str(report_path))

    assert report["test"] == "Hybrid TLS (ECDHE + Kyber)"
    assert report["results"]["handshake"] == "✓ PASS"
    assert isinstance(report["results"]["handshake_ms"], float)

    on_disk = json.loads(report_path.read_text())
    assert on_disk["results"]["handshake_ms"] == report["results"]["handshake_ms"]
