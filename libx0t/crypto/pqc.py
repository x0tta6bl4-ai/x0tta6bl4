from __future__ import annotations

import hashlib
import importlib
import logging
import os
from typing import Any

logger = logging.getLogger("x0t.crypto")


class PQC:
    """PQC key exchange wrapper with fail-closed defaults."""

    _INSECURE_SIM_ENV = "X0T_ALLOW_INSECURE_PQC_SIM"

    def __init__(self, algorithm: str = "Kyber768"):
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
        if self.algorithm == "Kyber768":
            return ["Kyber768", "ML-KEM-768"]
        if self.algorithm == "ML-KEM-768":
            return ["ML-KEM-768", "Kyber768"]
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
            except Exception as exc:  # pragma: no cover - backend-dependent
                last_error = exc
        raise RuntimeError(
            f"No supported KEM mechanism found for algorithm '{self.algorithm}'. "
            f"Tried {self._algorithm_candidates()}."
        ) from last_error

    @staticmethod
    def _sim_public_from_private(private_key: bytes) -> bytes:
        return hashlib.sha256(b"X0T_SIM_PUB" + private_key).digest()

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate KEM public/private keypair."""
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
        """Encapsulate to peer public key; returns (shared_secret, ciphertext)."""
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
        """Decapsulate ciphertext using private key; returns shared secret."""
        backend = self._require_backend()
        if backend == "oqs":
            kem = self._new_kem(secret_key=private_key)
            return kem.decap_secret(ciphertext)

        local_public = self._sim_public_from_private(private_key)
        return hashlib.sha256(
            b"X0T_SIM_SHARED" + local_public + ciphertext
        ).digest()
