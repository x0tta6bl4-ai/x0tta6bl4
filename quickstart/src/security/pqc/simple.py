"""Simple unified PQC wrapper for backward compatibility.

Usage:
    from src.security.pqc.simple import PQC
    pqc = PQC()
    print(pqc.algorithm)
    print(pqc.available)
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.security.pqc.adapter import is_liboqs_available
from src.security.pqc import get_pqc_key_exchange, get_pqc_digital_signature

__all__ = ["PQC"]


class PQC:
    """Unified post-quantum cryptography wrapper.

    Combines ML-KEM-768 key exchange and ML-DSA-65 digital signatures
    behind a single interface for backward compatibility.
    """

    ALGORITHM = "ML-KEM-768"

    def __init__(self) -> None:
        self.available = is_liboqs_available()
        self.algorithm = self.ALGORITHM
        self._kem = None
        self._dsa = None

    @property
    def kem(self) -> Any:
        if self._kem is None:
            if not self.available:
                raise RuntimeError("PQC not available - liboqs missing")
            self._kem = get_pqc_key_exchange()
        return self._kem

    @property
    def dsa(self) -> Any:
        if self._dsa is None:
            if not self.available:
                raise RuntimeError("PQC not available - liboqs missing")
            self._dsa = get_pqc_digital_signature()
        return self._dsa

    def generate_keypair(self) -> tuple[bytes, bytes]:
        return self.kem.generate_keypair()

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        return self.kem.encapsulate(public_key)

    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        return self.kem.decapsulate(ciphertext, secret_key)

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        return self.dsa.sign(message, secret_key)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        return self.dsa.verify(message, signature, public_key)