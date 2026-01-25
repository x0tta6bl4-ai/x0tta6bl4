#!/usr/bin/env python3
"""
x0tta6bl4 Hybrid TLS Proof of Concept
======================================

Демонстрирует гибридный ECDHE + PQC (Kyber/Dilithium) для mesh heartbeats.
Использует библиотеку OQS.
"""

import json
import time
from datetime import datetime
from .hybrid_tls import HybridTLSContext, hybrid_handshake, hybrid_encrypt, hybrid_decrypt, hybrid_sign, hybrid_verify, measure_handshake_overhead


def demo_mesh_handshake_and_encryption():
    print("\n" + "=" * 70)
    print("x0tta6bl4 Hybrid TLS (ECDHE + Kyber + Dilithium) - Full Demo")
    print("=" * 70)

    # 1. Инициализация узлов
    print("\n[1] Initialize nodes (client and server)")
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    print("    ✓ Client and Server contexts created.")

    # 2. Рукопожатие
    print("\n[2] Perform hybrid handshake")
    start_handshake = time.time()
    client_key, server_key = hybrid_handshake(client, server)
    handshake_elapsed = (time.time() - start_handshake) * 1000
    print(f"    ✓ Handshake complete in {handshake_elapsed:.2f} ms")
    print(f"    ✓ Client session key: {client_key.hex()[:32]}...")
    print(f"    ✓ Server session key: {server_key.hex()[:32]}...")
    if client_key != server_key:
        raise RuntimeError("Session keys do not match!")
    print("    ✓ Session keys match.")

    # 3. Подпись и верификация сообщения
    print("\n[3] Sign and verify a message with Dilithium")
    message = b"This is a test heartbeat message for x0tta6bl4"
    print(f"    - Original message: '{message.decode()}'")
    signature = hybrid_sign(client, message)
    print(f"    - Signature created (length: {len(signature)} bytes)")
    is_valid = hybrid_verify(server, message, signature)
    if not is_valid:
        raise RuntimeError("Signature verification failed!")
    print("    ✓ Signature verified successfully.")

    # 4. Шифрование и дешифрование
    print("\n[4] Encrypt and decrypt message with session key")
    encrypted_data = hybrid_encrypt(client_key, message)
    print(f"    - Encrypted data length: {len(encrypted_data)} bytes")
    decrypted_data = hybrid_decrypt(server_key, encrypted_data)
    print(f"    - Decrypted message: '{decrypted_data.decode()}'")
    if message != decrypted_data:
        raise RuntimeError("Decrypted data does not match original message!")
    print("    ✓ Encryption/Decryption successful.")
    
    print("\n[5] Performance Metrics")
    overhead_ms = measure_handshake_overhead()
    print(f"    • Average handshake time: {overhead_ms:.2f}ms (target <100ms)")

    return {
        "status": "SUCCESS",
        "handshake_ms": overhead_ms,
        "keys_match": client_key == server_key,
        "signature_valid": is_valid,
    }


def generate_report(path: str = "reports/pqc/hybrid_tls_report.json"):
    result = demo_mesh_handshake_and_encryption()
    report = {
        "test_date": datetime.now().isoformat(),
        "test": "Hybrid TLS (ECDHE + Kyber + Dilithium)",
        "results": {
            "handshake": "✓ PASS" if result["keys_match"] else "✗ FAIL",
            "signature_verification": "✓ PASS" if result["signature_valid"] else "✗ FAIL",
            "handshake_ms": result["handshake_ms"],
        },
    }

    print("\n" + "=" * 70)
    print("Test Report")
    print("=" * 70)
    print(json.dumps(report, indent=2))

    import os
    os.makedirs("reports/pqc", exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Report saved: {path}")
    return report


if __name__ == "__main__":
    generate_report()
