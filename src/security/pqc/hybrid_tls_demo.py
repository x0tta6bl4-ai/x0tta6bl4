#!/usr/bin/env python3
"""
x0tta6bl4 Hybrid TLS Proof of Concept
======================================

Демонстрирует гибридный ECDHE + PQC-симуляция для mesh heartbeats.
Не использует external dependencies (чистый Python).
"""

import json
import time
from datetime import datetime
from .hybrid_tls import HybridTLSContext, hybrid_handshake, hybrid_encrypt, hybrid_decrypt, measure_handshake_overhead


def demo_mesh_handshake_and_encryption():
    print("\n" + "=" * 70)
    print("x0tta6bl4 Hybrid TLS (ECDHE + Kyber) - Mesh Heartbeat Encryption")
    print("=" * 70)

    print("\n[1] Initialize nodes")
    node1 = HybridTLSContext("node-1")
    node2 = HybridTLSContext("node-2")

    print("\n[2] Exchange public keys & establish session")
    node1_pubkeys = node1.get_public_keys_pem()
    node2_pubkeys = node2.get_public_keys_pem()
    node1.set_peer_public_keys(node2_pubkeys["ecc_public"], node2_pubkeys["kyber_public"])
    node2.set_peer_public_keys(node1_pubkeys["ecc_public"], node1_pubkeys["kyber_public"])

    start = time.time()
    key1 = node1.compute_session_key()
    key2 = node2.compute_session_key()
    elapsed = (time.time() - start) * 1000

    print(f"    ✓ Node-1 session_key: {key1.hex()[:32]}...")
    print(f"    ✓ Node-2 session_key: {key2.hex()[:32]}...")

    if key1 != key2:
        raise RuntimeError("Session keys do not match in demo")

    print("\n[3] Node-1 sends encrypted heartbeat to Node-2")
    heartbeat = {
        "from": "node-1",
        "to": "node-2",
        "timestamp": datetime.now().isoformat(),
        "rssi": -72,
        "snr": 12,
        "battery": 95,
    }

    plaintext = json.dumps(heartbeat).encode()
    encrypted = hybrid_encrypt(key1, plaintext)
    decrypted = hybrid_decrypt(key2, encrypted)
    decoded = json.loads(decrypted.decode())

    if decoded != heartbeat:
        raise RuntimeError("Heartbeat mismatch after decrypt")

    print("    ✓ Encryption/Decryption SUCCESS")

    print("\n[4] Performance Metrics")
    overhead_ms = measure_handshake_overhead()
    print(f"    • Handshake time: {overhead_ms:.2f}ms (target <100ms)")

    return {
        "status": "SUCCESS",
        "handshake_ms": overhead_ms,
        "keys_match": key1 == key2,
    }


def generate_report(path: str = "reports/pqc/hybrid_tls_report.json"):
    result = demo_mesh_handshake_and_encryption()
    report = {
        "test_date": datetime.now().isoformat(),
        "test": "Hybrid TLS (ECDHE + Kyber)",
        "results": {
            "handshake": "✓ PASS",
            "keys_match": result["keys_match"],
            "handshake_ms": result["handshake_ms"],
        },
    }

    print(json.dumps(report, indent=2))

    import os
    os.makedirs("reports/pqc", exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Report saved: {path}")
    return report


if __name__ == "__main__":
    generate_report()
