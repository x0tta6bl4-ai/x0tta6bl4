# Post-Quantum Cryptographic Algorithms

## NIST Standardized (FIPS 203 / 204)

### ML-KEM (Module-Lattice Key Encapsulation)

Formerly Kyber. FIPS 203. Used for key exchange.

| Parameter Set | Security Level | Public Key | Ciphertext | Shared Secret |
|---------------|---------------|------------|------------|---------------|
| ML-KEM-512 | 1 | 800 B | 768 B | 32 B |
| **ML-KEM-768** | **3 (recommended)** | **1184 B** | **1088 B** | **32 B** |
| ML-KEM-1024 | 5 | 1568 B | 1568 B | 32 B |

x0tta6bl4 uses **ML-KEM-768** (Level 3) for all key encapsulation.

### ML-DSA (Module-Lattice Digital Signature)

Formerly Dilithium. FIPS 204. Used for signing.

| Parameter Set | Security Level | Public Key | Signature |
|---------------|---------------|------------|-----------|
| ML-DSA-44 | 2 | 1312 B | 2420 B |
| **ML-DSA-65** | **3 (recommended)** | **1952 B** | **3293 B** |
| ML-DSA-87 | 5 | 2592 B | 4595 B |

x0tta6bl4 uses **ML-DSA-65** (Level 3) for all digital signatures.

## Hybrid Mode

x0tta6bl4 combines classical + post-quantum for defense in depth:

| Operation | Classical | Post-Quantum | Combined |
|-----------|-----------|--------------|----------|
| Key Exchange | X25519 | ML-KEM-768 | Both shared secrets XOR'd |
| Signing | Ed25519 | ML-DSA-65 | Both signatures required |
| TLS | ECDHE | ML-KEM-768 | Hybrid handshake |

## Key Rotation Protocol

1. Node generates new ML-KEM-768 + ML-DSA-65 keypairs
2. Signs new public keys with old ML-DSA-65 key (chain of trust)
3. Broadcasts signed key update via mesh routing (HELLO packet)
4. Peers verify signature, update key store
5. Re-establish secure channels with new keys
6. Old keys zeroed from memory

## Forbidden (DO NOT USE)

- RSA alone (quantum-vulnerable via Shor's algorithm)
- ECDH/ECDSA alone (quantum-vulnerable)
- AES-128 (use AES-256 for quantum margin)
- SHA-1 (collision attacks)
- MD5 (broken)
- XOR "encryption" (not encryption)
- `random.random()` for key material (use `secrets` or `os.urandom`)
