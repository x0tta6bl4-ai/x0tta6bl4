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

    def __init__(self, algorithm: str = "ML-KEM-768") -> None:
        self.available = is_liboqs_available()
        self.algorithm = algorithm or self.ALGORITHM
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
        kp = self.kem.generate_keypair()
        if hasattr(kp, "public_key") and hasattr(kp, "secret_key"):
            return (kp.public_key, kp.secret_key)
        return kp

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        res = self.kem.encapsulate(public_key)
        if hasattr(res, "ciphertext") and hasattr(res, "shared_secret"):
            return (res.shared_secret, res.ciphertext)
        if isinstance(res, tuple) and len(res) == 2:
            a, b = res
            if len(a) > len(b):
                return (b, a)
            return (a, b)
        return res

    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        if len(ciphertext) > len(secret_key):
            ciphertext, secret_key = secret_key, ciphertext
        try:
            return self.kem.decapsulate(secret_key, ciphertext)
        except (TypeError, ValueError, Exception):
            return self.kem.decapsulate(ciphertext, secret_key)

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        return self.dsa.sign(message, secret_key)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        return self.dsa.verify(message, signature, public_key)