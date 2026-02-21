#!/usr/bin/env python3
"""
Post-Quantum Cryptography Demo for x0tta6bl4

This module provides a simple interface to the PQC implementation.
Real implementation is in libx0t/crypto/pqc.py

Run: python3 pqc.py
"""

import sys
import binascii

# Import from the actual implementation location
from libx0t.crypto.pqc import PQC


def demo_kyber768_key_exchange():
    """
    Demonstrate real Kyber768 (NIST FIPS 203) key exchange.
    
    Kyber768 provides NIST Level 3 security (equivalent to AES-192).
    """
    print("=" * 60)
    print("Post-Quantum Cryptography Demo (Kyber768/ML-KEM-768)")
    print("=" * 60)
    
    # Initialize PQC with Kyber768
    pqc = PQC(algorithm="Kyber768")
    
    print("\n[1] Generating keypair...")
    public_key, private_key = pqc.generate_keypair()
    
    print(f"    Public key size:  {len(public_key)} bytes")
    print(f"    Private key size: {len(private_key)} bytes")
    print(f"    Public key (hex): {binascii.hexlify(public_key[:32]).decode()}...")
    
    print("\n[2] Alice encapsulates shared secret...")
    shared_secret_alice, ciphertext = pqc.encapsulate(public_key)
    
    print(f"    Ciphertext size: {len(ciphertext)} bytes")
    print(f"    Shared secret:   {binascii.hexlify(shared_secret_alice).decode()}")
    
    print("\n[3] Bob decapsulates shared secret...")
    shared_secret_bob = pqc.decapsulate(ciphertext, private_key)
    
    print(f"    Shared secret:   {binascii.hexlify(shared_secret_bob).decode()}")
    
    print("\n[4] Verification...")
    if shared_secret_alice == shared_secret_bob:
        print("    ✅ SUCCESS: Shared secrets match!")
        print("    Quantum-safe key exchange completed.")
    else:
        print("    ❌ FAILURE: Shared secrets do not match!")
        return False
    
    return True


if __name__ == "__main__":
    try:
        success = demo_kyber768_key_exchange()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
