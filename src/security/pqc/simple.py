"""Simple unified PQC wrapper for backward compatibility.

Usage:
    from src.security.pqc.simple import PQC
    pqc = PQC()
    print(pqc.algorithm)
    print(pqc.available)
"""

from __future__ import annotations

from src.security.pqc.adapter import is_liboqs_available
from src.security.pqc.compat import (
    PQCDigitalSignature,
    PQCKeyExchange,
    get_pqc_digital_signature,
    get_pqc_key_exchange,
)
from src.security.pqc.types import PQCEncapsulationResult, PQCKeyPair

__all__ = ["PQC"]


class PQC:
    """Unified post-quantum cryptography wrapper.

    Combines ML-KEM-768 key exchange and ML-DSA-65 digital signatures
    behind a single interface for backward compatibility.
    """

    ALGORITHM = "ML-KEM-768"

    def __init__(self, algorithm: str = "ML-KEM-768") -> None:
        self.available = is_liboqs_available()
        self.algorithm = algorithm or self.ALGORITHM
        self._kem: PQCKeyExchange | None = None
        self._dsa: PQCDigitalSignature | None = None

    @property
    def kem(self) -> PQCKeyExchange:
        if self._kem is None:
            if not self.available:
                raise RuntimeError("PQC not available - liboqs missing")
            self._kem = get_pqc_key_exchange()
        return self._kem

    @property
    def dsa(self) -> PQCDigitalSignature:
        if self._dsa is None:
            if not self.available:
                raise RuntimeError("PQC not available - liboqs missing")
            self._dsa = get_pqc_digital_signature()
        return self._dsa

    def generate_keypair(self) -> tuple[bytes, bytes]:
        kp = self.kem.generate_keypair()
        if isinstance(kp, PQCKeyPair):
            return (kp.public_key, kp.secret_key)
        return kp

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        res = self.kem.encapsulate(public_key)
        if isinstance(res, PQCEncapsulationResult):
            return (res.shared_secret, res.ciphertext)
        # PQCKeyExchange.encapsulate returns (ciphertext, shared_secret).
        # Legacy PQC interface contract expects (shared_secret, ciphertext).
        ciphertext, shared_secret = res
        return (shared_secret, ciphertext)

    def decapsulate(self, ciphertext: bytes, secret_key: bytes | PQCKeyPair) -> bytes:
        # Normalize PQCKeyPair object if supplied instead of raw secret key bytes
        if isinstance(secret_key, PQCKeyPair):
            secret_key = secret_key.secret_key
        # PQCKeyExchange.decapsulate expects (secret_key, ciphertext)
        return self.kem.decapsulate(secret_key, ciphertext)

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        return self.dsa.sign(message, secret_key)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        return self.dsa.verify(message, signature, public_key)
