# Post-Quantum Cryptography Compliance Reference

## NIST Standards (x0tta6bl4 Requirements)

### FIPS 203: ML-KEM (Key Encapsulation)
- **Required**: ML-KEM-768 (Security Level 3)
- **Implementation**: `src/crypto/pqc_crypto.py`, `src/security/post_quantum.py`
- **Key sizes**: Public key 1184 bytes, ciphertext 1088 bytes, shared secret 32 bytes
- **Verification**: Encapsulated key must decrypt correctly with matching private key

### FIPS 204: ML-DSA (Digital Signatures)
- **Required**: ML-DSA-65 (Security Level 3)
- **Implementation**: `src/security/post_quantum.py`
- **Signature size**: 3293 bytes
- **Verification**: Signature must verify against the public key and message

### Hybrid Mode (Required)
- Classical + PQC combined
- TLS: X25519 + ML-KEM-768 for key exchange
- Signatures: Ed25519 + ML-DSA-65
- Implementation: `src/security/pqc/hybrid_tls.py`

## Encryption Requirements

| Context | Algorithm | Mode | Key Size | Nonce |
|---------|-----------|------|----------|-------|
| Data at rest | AES | GCM | 256-bit | 12 bytes, unique per encryption |
| Data in transit | AES | GCM | 256-bit | 12 bytes, unique per message |
| Key exchange | ML-KEM | 768 | N/A | N/A |
| Signatures | ML-DSA | 65 | N/A | N/A |
| Password hashing | bcrypt | N/A | N/A | Random salt per hash |

## Forbidden Algorithms
- XOR cipher (not encryption)
- RC4 (broken)
- DES / 3DES (weak key size)
- AES-ECB (no diffusion)
- AES-CBC without HMAC (not authenticated)
- MD5 for authentication (collision attacks)
- SHA1 for authentication (SHAttered attack)
- `random.random()` for key generation (predictable)

## Certificate Chain Validation
- Must use cryptographic verification: `cert.verify_directly_issued_by(ca_cert)`
- Must NOT use issuer/subject name matching as sole validation
- Must verify the full chain from leaf to trusted root
- Must check certificate expiry dates
- Must check SPIFFE ID format: `spiffe://{trust_domain}/{path}`
