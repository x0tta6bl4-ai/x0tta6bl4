"""
Simple PQC wrapper - lightweight KEM interface.

This module provides the simplified PQC class from libx0t/crypto/pqc.py,
consolidated into the canonical src.security.pqc package.

For new code, prefer PQCKeyExchange from .kem which provides:
- SecureKeyStorage for encrypted key storage
- Key expiration tracking
- Full NIST FIPS 203 compliance

Usage:
    from src.security.pqc.simple import PQC

    # Check if liboqs is available
    pqc = PQC("ML-KEM-768")

    # Generate keypair
    public_key, private_key = pqc.generate_keypair()

    # Encapsulate
    shared_secret, ciphertext = pqc.encapsulate(peer_public_key)

    # Decapsulate
    shared_secret = pqc.decapsulate(ciphertext, private_key)
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class PQC:
    """PQC key exchange wrapper with fail-closed defaults.

    Supports ML-KEM-768 (Kyber768) and ML-KEM-512/1024.

    Fail-closed behavior:
    - If liboqs is not installed, secure operations are disabled
    - Insecure simulation only available via X0T_ALLOW_INSECURE_PQC_SIM=1

    Migration path:
        Old: from libx0t.crypto.pqc import PQC
        New: from src.security.pqc.simple import PQC
    """

    _INSECURE_SIM_ENV = "X0T_ALLOW_INSECURE_PQC_SIM"

    # Legacy name mappings
    ALGORITHM_MAP = {
        "Kyber768": "ML-KEM-768",
        "Kyber512": "ML-KEM-512",
        "Kyber1024": "ML-KEM-1024",
        "ML-KEM-768": "ML-KEM-768",
        "ML-KEM-512": "ML-KEM-512",
        "ML-KEM-1024": "ML-KEM-1024",
    }

    def __init__(self, algorithm: str = "ML-KEM-768"):
        """Initialize PQC wrapper.

        Args:
            algorithm: KEM algorithm name (ML-KEM-768, ML-KEM-512, ML-KEM-1024)
                       Also accepts legacy names: Kyber768, Kyber512, Kyber1024
        """
        self.algorithm = algorithm
        self.liboqs_available = False
        self.allow_insecure_simulation = self._env_flag(self._INSECURE_SIM_ENV)
        self._oqs_module: Any | None = None
        self._resolved_algorithm: str | None = None
        self._check_liboqs()

    @staticmethod
    def _env_flag(name: str) -> bool:
        raw = os.environ.get(name, "")
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _algorithm_candidates(self) -> list[str]:
        resolved = self.ALGORITHM_MAP.get(self.algorithm, self.algorithm)
        if resolved != self.algorithm:
            return [resolved, self.algorithm]
        return [self.algorithm]

    def _check_liboqs(self) -> None:
        try:
            self._oqs_module = importlib.import_module("oqs")
            self.liboqs_available = True
            logger.info("liboqs available. Using real post-quantum KEM.")
        except ImportError:
            self._oqs_module = None
            self.liboqs_available = False
            if self.allow_insecure_simulation:
                logger.warning(
                    "liboqs not found. Insecure simulation enabled via %s.",
                    self._INSECURE_SIM_ENV,
                )
            else:
                logger.warning(
                    "liboqs not found. Secure operations are disabled; set %s=1 only for dev/test.",
                    self._INSECURE_SIM_ENV,
                )

    def _require_backend(self) -> str:
        if self.liboqs_available and self._oqs_module is not None:
            return "oqs"
        if self.allow_insecure_simulation:
            return "simulation"
        raise RuntimeError(
            "PQC backend unavailable: liboqs is not installed. "
            f"To use dev-only simulation set {self._INSECURE_SIM_ENV}=1."
        )

    def _new_kem(self, secret_key: bytes | None = None) -> Any:
        if self._oqs_module is None:
            raise RuntimeError("liboqs module is unavailable")
        last_error: Exception | None = None
        for candidate in self._algorithm_candidates():
            try:
                if secret_key is None:
                    kem = self._oqs_module.KeyEncapsulation(candidate)
                else:
                    kem = self._oqs_module.KeyEncapsulation(candidate, secret_key=secret_key)
                self._resolved_algorithm = candidate
                return kem
            except Exception as exc:
                last_error = exc
        raise RuntimeError(
            f"No supported KEM mechanism found for algorithm '{self.algorithm}'. "
            f"Tried {self._algorithm_candidates()}."
        ) from last_error

    @staticmethod
    def _sim_public_from_private(private_key: bytes) -> bytes:
        return hashlib.sha256(b"X0T_SIM_PUB" + private_key).digest()

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate KEM public/private keypair.

        Returns:
            Tuple of (public_key, private_key)
        """
        backend = self._require_backend()
        if backend == "oqs":
            kem = self._new_kem()
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
            return public_key, private_key

        # Dev-only deterministic simulation API (not cryptographically secure).
        private_key = os.urandom(32)
        public_key = self._sim_public_from_private(private_key)
        return public_key, private_key

    def encapsulate(self, peer_public_key: bytes) -> tuple[bytes, bytes]:
        """Encapsulate to peer public key.

        Args:
            peer_public_key: Peer public key

        Returns:
            Tuple of (shared_secret, ciphertext)
        """
        backend = self._require_backend()
        if backend == "oqs":
            kem = self._new_kem()
            ciphertext, shared_secret = kem.encap_secret(peer_public_key)
            return shared_secret, ciphertext

        eph_private = os.urandom(32)
        eph_public = self._sim_public_from_private(eph_private)
        shared_secret = hashlib.sha256(
            b"X0T_SIM_SHARED" + peer_public_key + eph_public
        ).digest()
        ciphertext = eph_public
        return shared_secret, ciphertext

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Decapsulate ciphertext using private key.

        Args:
            ciphertext: Encapsulated ciphertext
            private_key: Our private key

        Returns:
            Shared secret bytes
        """
        backend = self._require_backend()
        if backend == "oqs":
            kem = self._new_kem(secret_key=private_key)
            return kem.decap_secret(ciphertext)

        local_public = self._sim_public_from_private(private_key)
        return hashlib.sha256(
            b"X0T_SIM_SHARED" + local_public + ciphertext
        ).digest()

    @property
    def is_available(self) -> bool:
        """Check if real PQC is available (not simulation)."""
        return self.liboqs_available
