# PQC Integration — ML-KEM + ML-DSA

## Context

x0tta6bl4 is a self-healing mesh networking platform. All mesh traffic must be protected against both classical and quantum adversaries. We use liboqs (Open Quantum Safe) for post-quantum cryptographic primitives.

The target hardware is consumer-grade (Intel i5, r8169 NIC) under sanctions — no hardware security modules, no TPM, no cloud KMS. The crypto must run in software on every mesh node.

## Architecture Decision

**Hybrid TLS 1.3** with ML-KEM-768 for key encapsulation and ML-DSA-65 for digital signatures. The hybrid design means both classical (X25519/ECDSA) and PQC algorithms run in parallel — a break in one doesn't compromise the channel.

## SPEC

### Module: `src/security/pqc/hybrid_tls.py`

```
class HybridTLS:
    """TLS 1.3 with ML-KEM-768 + X25519 hybrid key exchange."""
    
    @staticmethod
    def create_hybrid_keypair() -> HybridKeyPair
        # Returns (classical_pk, classical_sk, pqc_pk, pqc_sk)
        # X25519 + ML-KEM-768

    @staticmethod
    def hybrid_encapsulate(peer_public_key: HybridPublicKey) -> tuple[bytes, HybridSharedSecret]
        # Encapsulate against both classical + PQC public key
        # Returns (ciphertext, shared_secret)

    @staticmethod
    def hybrid_decapsulate(ciphertext: bytes, keypair: HybridKeyPair) -> HybridSharedSecret
        # Decapsulate ciphertext using both keypairs
```

### Module: `src/security/pqc/hybrid_sign.py`

```
class HybridSigner:
    """ML-DSA-65 + ECDSA hybrid digital signatures."""
    
    @staticmethod
    def sign(data: bytes, signing_key: HybridSigningKey) -> HybridSignature
    @staticmethod
    def verify(data: bytes, signature: HybridSignature, verification_key: HybridVerifyKey) -> bool
```

### Module: `src/security/pqc/pqc_session.py`

```
class PQCSession:
    """PQC-secured session between two mesh nodes."""
    
    async def handshake(self, transport: Transport) -> bool
    async def encrypt(self, plaintext: bytes) -> bytes
    async def decrypt(self, ciphertext: bytes) -> bytes
    def get_session_stats(self) -> SessionStats
```

## CONSTRAINTS

1. **NO stubs.** Every function must have a real implementation using liboqs. No `pass`, no `raise NotImplementedError`, no `return b""`.
2. **NO placeholders.** `TODO`, `FIXME`, `# implement later` are forbidden.
3. **NO mock data.** Keys must be generated, not hardcoded.
4. **Proper error handling.** Cryptography fails — handle invalid keys, corrupt ciphertexts, unsupported parameter sets.
5. **Zero-copy where practical.** Avoid unnecessary byte copies in hot path.
6. **Deterministic tests.** Use seed-based RNG for reproducibility.
7. **Thread-safe.** Sessions can be used from multiple coroutines.

## VERIFICATION

After generation, run:
```bash
python3 -m pytest tests/unit/security/pqc/ -v --tb=short
python3 -c "from src.security.pqc.hybrid_tls import HybridTLS; print('import OK')"
python3 scripts/benchmark_pqc.py  # Expect <50ms handshake
```

## EDGE CASES

1. **liboqs not installed** — graceful import error, not crash.
2. **ML-KEM parameter mismatch** — server and client negotiate, don't hard-fail.
3. **Corrupt ciphertext** — decapsulation fails with clear error, no undefined behavior.
4. **Concurrent handshakes** — no shared state corruption.
5. **Memory exhaustion** — large kyber keys fit in stack, not heap.
