#!/usr/bin/env python3
"""
x0tta6bl4 Kyber768 Demo
Shows real post-quantum cryptography in action.

Run: python3 scripts/test_kyber.py
"""
import time

print("=" * 60)
print("🔐 x0tta6bl4 POST-QUANTUM CRYPTOGRAPHY DEMO")
print("=" * 60)

# Check liboqs
try:
    import oqs
    print("\n✅ liboqs library loaded")
except ImportError:
    print("\n❌ liboqs not available")
    print("   Install: pip install liboqs-python")
    exit(1)

# Show available algorithms
print(f"\n📋 Available KEMs: {len(oqs.get_enabled_kem_mechanisms())}")
print(f"   Including: Kyber512, Kyber768, Kyber1024")

# Generate keypair
print("\n" + "-" * 60)
print("🔑 STEP 1: Generate Kyber768 Keypair")
print("-" * 60)

start = time.perf_counter()
kem = oqs.KeyEncapsulation("Kyber768")
public_key = kem.generate_keypair()
private_key = kem.export_secret_key()
keygen_time = (time.perf_counter() - start) * 1000

print(f"   Algorithm:    Kyber768 (NIST Level 3)")
print(f"   Public Key:   {len(public_key)} bytes")
print(f"   Private Key:  {len(private_key)} bytes")
print(f"   Time:         {keygen_time:.3f}ms")

# Encapsulate
print("\n" + "-" * 60)
print("📦 STEP 2: Encapsulate Shared Secret")
print("-" * 60)

kem2 = oqs.KeyEncapsulation("Kyber768")
start = time.perf_counter()
ciphertext, shared_secret_sender = kem2.encap_secret(public_key)
encap_time = (time.perf_counter() - start) * 1000

print(f"   Ciphertext:   {len(ciphertext)} bytes")
print(f"   Shared Secret: {len(shared_secret_sender)} bytes")
print(f"   Time:         {encap_time:.3f}ms")
print(f"   Secret (hex): {shared_secret_sender[:16].hex()}...")

# Decapsulate
print("\n" + "-" * 60)
print("🔓 STEP 3: Decapsulate Shared Secret")
print("-" * 60)

start = time.perf_counter()
shared_secret_receiver = kem.decap_secret(ciphertext)
decap_time = (time.perf_counter() - start) * 1000

print(f"   Secret (hex): {shared_secret_receiver[:16].hex()}...")
print(f"   Time:         {decap_time:.3f}ms")

# Verify
print("\n" + "-" * 60)
print("✅ STEP 4: Verify")
print("-" * 60)

if shared_secret_sender == shared_secret_receiver:
    print("   Secrets MATCH! ✅")
    print(f"   Both parties now have the same 256-bit key")
    print(f"   This key is used for AES-256-GCM encryption")
else:
    print("   Secrets DON'T MATCH! ❌")
    exit(1)

# Summary
print("\n" + "=" * 60)
print("📊 SUMMARY")
print("=" * 60)
print(f"""
   Algorithm:        Kyber768 (CRYSTALS-Kyber)
   NIST Standard:    FIPS 203 (August 2024)
   Security Level:   Level 3 (equivalent to AES-192)
   Quantum-Safe:     ✅ YES
   
   Performance:
   - Key Generation: {keygen_time:.3f}ms
   - Encapsulation:  {encap_time:.3f}ms  
   - Decapsulation:  {decap_time:.3f}ms
   - TOTAL:          {keygen_time + encap_time + decap_time:.3f}ms
   
   Key Sizes:
   - Public Key:     {len(public_key)} bytes
   - Private Key:    {len(private_key)} bytes
   - Ciphertext:     {len(ciphertext)} bytes
   - Shared Secret:  {len(shared_secret_sender)} bytes
""")

print("=" * 60)
print("🛡️  This is REAL post-quantum cryptography.")
print("   Protected against quantum computer attacks.")
print("   Used by Google Chrome, Cloudflare, Signal.")
print("=" * 60)
