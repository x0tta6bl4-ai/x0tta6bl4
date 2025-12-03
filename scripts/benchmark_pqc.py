#!/usr/bin/env python3
"""
x0tta6bl4 PQC Benchmark
Compares Kyber768 vs RSA-2048 performance.

Run: python3 scripts/benchmark_pqc.py
"""
import time
import statistics
from typing import Tuple, List

# Try to import PQC
try:
    import oqs
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    print("❌ liboqs not available. Install with: pip install liboqs-python")
    exit(1)

# Try to import RSA
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    RSA_AVAILABLE = True
except ImportError:
    RSA_AVAILABLE = False
    print("⚠️ cryptography not available for RSA comparison")


def benchmark_kyber(iterations: int = 100) -> dict:
    """Benchmark Kyber768 operations."""
    keygen_times = []
    encap_times = []
    decap_times = []
    
    for _ in range(iterations):
        # Key generation
        start = time.perf_counter()
        kem = oqs.KeyEncapsulation("Kyber768")
        public_key = kem.generate_keypair()
        private_key = kem.export_secret_key()
        keygen_times.append((time.perf_counter() - start) * 1000)
        
        # Encapsulation
        kem2 = oqs.KeyEncapsulation("Kyber768")
        start = time.perf_counter()
        ciphertext, shared_secret1 = kem2.encap_secret(public_key)
        encap_times.append((time.perf_counter() - start) * 1000)
        
        # Decapsulation
        start = time.perf_counter()
        shared_secret2 = kem.decap_secret(ciphertext)
        decap_times.append((time.perf_counter() - start) * 1000)
        
        assert shared_secret1 == shared_secret2, "Shared secrets don't match!"
    
    return {
        "algorithm": "Kyber768",
        "keygen_ms": statistics.mean(keygen_times),
        "encap_ms": statistics.mean(encap_times),
        "decap_ms": statistics.mean(decap_times),
        "total_ms": statistics.mean(keygen_times) + statistics.mean(encap_times) + statistics.mean(decap_times),
        "public_key_bytes": len(public_key),
        "private_key_bytes": len(private_key),
        "ciphertext_bytes": len(ciphertext),
        "shared_secret_bytes": len(shared_secret1),
    }


def benchmark_rsa(iterations: int = 100) -> dict:
    """Benchmark RSA-2048 operations."""
    if not RSA_AVAILABLE:
        return None
    
    keygen_times = []
    encrypt_times = []
    decrypt_times = []
    
    for _ in range(iterations):
        # Key generation
        start = time.perf_counter()
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        keygen_times.append((time.perf_counter() - start) * 1000)
        
        # Encryption (simulate key encapsulation with 32-byte secret)
        message = b"x" * 32  # 32-byte shared secret
        start = time.perf_counter()
        ciphertext = public_key.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        encrypt_times.append((time.perf_counter() - start) * 1000)
        
        # Decryption
        start = time.perf_counter()
        decrypted = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        decrypt_times.append((time.perf_counter() - start) * 1000)
        
        assert decrypted == message, "Decryption failed!"
    
    # Get key sizes
    from cryptography.hazmat.primitives import serialization
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return {
        "algorithm": "RSA-2048",
        "keygen_ms": statistics.mean(keygen_times),
        "encap_ms": statistics.mean(encrypt_times),
        "decap_ms": statistics.mean(decrypt_times),
        "total_ms": statistics.mean(keygen_times) + statistics.mean(encrypt_times) + statistics.mean(decrypt_times),
        "public_key_bytes": len(pub_bytes),
        "private_key_bytes": len(priv_bytes),
        "ciphertext_bytes": len(ciphertext),
        "shared_secret_bytes": 32,
    }


def print_comparison(kyber: dict, rsa: dict):
    """Print formatted comparison."""
    print("\n" + "=" * 70)
    print("🔐 x0tta6bl4 POST-QUANTUM CRYPTOGRAPHY BENCHMARK")
    print("=" * 70)
    
    print(f"\n{'Operation':<20} {'Kyber768':>15} {'RSA-2048':>15} {'Speedup':>15}")
    print("-" * 70)
    
    # Key generation
    speedup = rsa["keygen_ms"] / kyber["keygen_ms"]
    print(f"{'Key Generation':<20} {kyber['keygen_ms']:>12.3f}ms {rsa['keygen_ms']:>12.3f}ms {speedup:>12.1f}x faster")
    
    # Encapsulation
    speedup = rsa["encap_ms"] / kyber["encap_ms"]
    print(f"{'Encapsulation':<20} {kyber['encap_ms']:>12.3f}ms {rsa['encap_ms']:>12.3f}ms {speedup:>12.1f}x faster")
    
    # Decapsulation
    speedup = rsa["decap_ms"] / kyber["decap_ms"]
    print(f"{'Decapsulation':<20} {kyber['decap_ms']:>12.3f}ms {rsa['decap_ms']:>12.3f}ms {speedup:>12.1f}x faster")
    
    # Total
    speedup = rsa["total_ms"] / kyber["total_ms"]
    print("-" * 70)
    print(f"{'TOTAL':<20} {kyber['total_ms']:>12.3f}ms {rsa['total_ms']:>12.3f}ms {speedup:>12.1f}x faster")
    
    print(f"\n{'Key Sizes':<20} {'Kyber768':>15} {'RSA-2048':>15}")
    print("-" * 70)
    print(f"{'Public Key':<20} {kyber['public_key_bytes']:>12} B {rsa['public_key_bytes']:>12} B")
    print(f"{'Private Key':<20} {kyber['private_key_bytes']:>12} B {rsa['private_key_bytes']:>12} B")
    print(f"{'Ciphertext':<20} {kyber['ciphertext_bytes']:>12} B {rsa['ciphertext_bytes']:>12} B")
    
    print("\n" + "=" * 70)
    print("🛡️  SECURITY COMPARISON")
    print("=" * 70)
    print(f"{'Property':<30} {'Kyber768':>18} {'RSA-2048':>18}")
    print("-" * 70)
    print(f"{'Quantum-Safe':<30} {'✅ YES':>18} {'❌ NO':>18}")
    print(f"{'NIST Standard':<30} {'✅ FIPS 203 (2024)':>18} {'⚠️ Legacy':>18}")
    print(f"{'Security Level':<30} {'Level 3 (AES-192)':>18} {'~112 bits':>18}")
    print(f"{'Broken by Quantum':<30} {'Never':>18} {'~Minutes':>18}")
    
    print("\n" + "=" * 70)
    print("✅ CONCLUSION: Kyber768 is {:.0f}x faster AND quantum-safe!".format(speedup))
    print("=" * 70)


def main():
    print("🔬 Running benchmark (100 iterations each)...")
    print("   This may take a minute...\n")
    
    iterations = 100
    
    print("⏱️  Benchmarking Kyber768...")
    kyber = benchmark_kyber(iterations)
    
    if RSA_AVAILABLE:
        print("⏱️  Benchmarking RSA-2048...")
        rsa_result = benchmark_rsa(iterations)
        print_comparison(kyber, rsa_result)
    else:
        print("\n🔐 Kyber768 Results:")
        print(f"   Key Generation: {kyber['keygen_ms']:.3f}ms")
        print(f"   Encapsulation:  {kyber['encap_ms']:.3f}ms")
        print(f"   Decapsulation:  {kyber['decap_ms']:.3f}ms")
        print(f"   Total:          {kyber['total_ms']:.3f}ms")


if __name__ == "__main__":
    main()
