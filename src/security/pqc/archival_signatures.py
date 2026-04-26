"""
PQC Archival Signatures — x0tta6bl4
=====================================
Long-term archival signatures using SPHINCS+ (SLH-DSA, FIPS 205).

SPHINCS+ is a hash-based signature scheme with conservative security
assumptions — no lattice assumptions, suitable for 20+ year archival.

Use cases:
  - Firmware/SBOM attestation (long-term integrity)
  - DAO governance proposal finalization
  - Audit log sealing
  - Certificate chain anchoring

Note: SPHINCS+ signatures are larger (~8-50 KB) and slower than
Dilithium/ML-DSA, so this is NOT for high-frequency operations.
Use ML-DSA-65 for routine signing (heartbeats, tokens, etc.).
"""

import hashlib
import hmac
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# SPHINCS+ parameter sets (NIST SLH-DSA)
SPHINCS_PARAMS = {
    "SLH-DSA-SHA2-128s": {
        "security_level": 1,
        "sig_size_bytes": 7856,
        "pk_size_bytes": 32,
        "sk_size_bytes": 64,
        "hash": "sha256",
        "variant": "small",
    },
    "SLH-DSA-SHA2-128f": {
        "security_level": 1,
        "sig_size_bytes": 17088,
        "pk_size_bytes": 32,
        "sk_size_bytes": 64,
        "hash": "sha256",
        "variant": "fast",
    },
    "SLH-DSA-SHA2-192s": {
        "security_level": 3,
        "sig_size_bytes": 16224,
        "pk_size_bytes": 48,
        "sk_size_bytes": 96,
        "hash": "sha256",
        "variant": "small",
    },
    "SLH-DSA-SHA2-256s": {
        "security_level": 5,
        "sig_size_bytes": 29792,
        "pk_size_bytes": 64,
        "sk_size_bytes": 128,
        "hash": "sha256",
        "variant": "small",
    },
}

# Default for archival: Level 3 small (good balance of security/size)
DEFAULT_ALGORITHM = "SLH-DSA-SHA2-192s"

# Try to load liboqs for real SPHINCS+
_OQS_AVAILABLE: bool | None = None


def _check_oqs() -> bool:
    global _OQS_AVAILABLE
    if _OQS_AVAILABLE is None:
        try:
            os.environ.setdefault("OQS_DISABLE_AUTO_INSTALL", "1")
            import oqs  # noqa: F401
            _OQS_AVAILABLE = True
        except (ImportError, RuntimeError):
            _OQS_AVAILABLE = False
    return _OQS_AVAILABLE


class ArchivalKeyPair:
    """SPHINCS+ key pair for archival signing."""

    def __init__(
        self,
        algorithm: str,
        public_key: bytes,
        secret_key: bytes,
        key_id: str,
    ):
        self.algorithm = algorithm
        self.public_key = public_key
        self.secret_key = secret_key
        self.key_id = key_id
        self.created_at = datetime.utcnow().isoformat()

    def to_public_dict(self) -> dict[str, Any]:
        """Return public portion (safe to share)."""
        return {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "public_key_hex": self.public_key.hex(),
            "created_at": self.created_at,
        }


class ArchivalSignature:
    """A SPHINCS+ signature with metadata."""

    def __init__(
        self,
        signature: bytes,
        algorithm: str,
        key_id: str,
        message_hash: str,
    ):
        self.signature = signature
        self.algorithm = algorithm
        self.key_id = key_id
        self.message_hash = message_hash
        self.created_at = datetime.utcnow().isoformat()
        self.signature_size_bytes = len(signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "signature_hex": self.signature.hex(),
            "message_hash": self.message_hash,
            "signature_size_bytes": self.signature_size_bytes,
            "created_at": self.created_at,
        }


class ArchivalSigner:
    """
    SPHINCS+ (SLH-DSA) signer for long-term archival integrity.

    In production with liboqs: uses real SPHINCS+ implementation.
    Without liboqs: uses HMAC-SHA512 simulation (NOT quantum-safe,
    but structurally correct for testing/development).
    """

    def __init__(self, algorithm: str = DEFAULT_ALGORITHM):
        if algorithm not in SPHINCS_PARAMS:
            raise ValueError(
                f"Unknown algorithm: {algorithm}. "
                f"Supported: {list(SPHINCS_PARAMS.keys())}"
            )
        self.algorithm = algorithm
        self.params = SPHINCS_PARAMS[algorithm]
        self._use_oqs = _check_oqs() and self._oqs_supports_algorithm(algorithm)

    @staticmethod
    def _oqs_supports_algorithm(algorithm: str) -> bool:
        """Check if liboqs actually supports this SPHINCS+ variant."""
        try:
            import oqs
            oqs_name = ArchivalSigner._to_oqs_name(algorithm)
            if hasattr(oqs, "get_enabled_sig_mechanisms"):
                return oqs_name in oqs.get_enabled_sig_mechanisms()
            # Try creating — if it fails, not supported
            oqs.Signature(oqs_name)
            return True
        except Exception:
            return False

    def generate_keypair(self) -> ArchivalKeyPair:
        """Generate a new SPHINCS+ key pair."""
        key_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]

        if self._use_oqs:
            return self._generate_oqs_keypair(key_id)

        # Simulation: HMAC-based (NOT quantum-safe — dev/test only)
        sk = os.urandom(self.params["sk_size_bytes"])
        pk = hashlib.sha256(sk).digest()[: self.params["pk_size_bytes"]]

        logger.debug(
            "Generated simulated %s keypair (key_id=%s)", self.algorithm, key_id
        )
        return ArchivalKeyPair(
            algorithm=self.algorithm,
            public_key=pk,
            secret_key=sk,
            key_id=key_id,
        )

    def sign(self, message: bytes, keypair: ArchivalKeyPair) -> ArchivalSignature:
        """Sign a message with SPHINCS+ for archival integrity."""
        if keypair.algorithm != self.algorithm:
            raise ValueError(
                f"Key algorithm mismatch: {keypair.algorithm} != {self.algorithm}"
            )

        msg_hash = hashlib.sha256(message).hexdigest()

        if self._use_oqs:
            sig_bytes = self._sign_oqs(message, keypair.secret_key)
        else:
            # Simulation: HMAC-SHA512 (NOT quantum-safe)
            sig_bytes = hmac.new(
                keypair.secret_key, message, hashlib.sha512
            ).digest()

        return ArchivalSignature(
            signature=sig_bytes,
            algorithm=self.algorithm,
            key_id=keypair.key_id,
            message_hash=msg_hash,
        )

    def verify(
        self,
        message: bytes,
        signature: ArchivalSignature,
        public_key: bytes,
    ) -> bool:
        """Verify a SPHINCS+ archival signature."""
        if self._use_oqs:
            return self._verify_oqs(message, signature.signature, public_key)

        # Simulation: cannot verify HMAC without secret key
        # For dev/test, check message hash consistency
        msg_hash = hashlib.sha256(message).hexdigest()
        return msg_hash == signature.message_hash

    def get_algorithm_info(self) -> dict[str, Any]:
        """Return algorithm parameters and availability."""
        return {
            "algorithm": self.algorithm,
            "params": self.params,
            "oqs_available": self._use_oqs,
            "quantum_safe": self._use_oqs,
            "mode": "production" if self._use_oqs else "simulation",
        }

    # --- liboqs-backed implementations ---

    def _generate_oqs_keypair(self, key_id: str) -> ArchivalKeyPair:
        import oqs

        # Map SLH-DSA names to liboqs names
        oqs_name = self._to_oqs_name(self.algorithm)
        signer = oqs.Signature(oqs_name)
        pk = signer.generate_keypair()
        sk = signer.export_secret_key()

        return ArchivalKeyPair(
            algorithm=self.algorithm,
            public_key=bytes(pk),
            secret_key=bytes(sk),
            key_id=key_id,
        )

    def _sign_oqs(self, message: bytes, secret_key: bytes) -> bytes:
        import oqs

        oqs_name = self._to_oqs_name(self.algorithm)
        signer = oqs.Signature(oqs_name, secret_key)
        return bytes(signer.sign(message))

    def _verify_oqs(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        import oqs

        oqs_name = self._to_oqs_name(self.algorithm)
        verifier = oqs.Signature(oqs_name)
        return verifier.verify(message, signature, public_key)

    @staticmethod
    def _to_oqs_name(algorithm: str) -> str:
        """Map NIST SLH-DSA names to liboqs mechanism names."""
        # liboqs uses "SPHINCS+-SHA2-128s-simple" style names
        mapping = {
            "SLH-DSA-SHA2-128s": "SPHINCS+-SHA2-128s-simple",
            "SLH-DSA-SHA2-128f": "SPHINCS+-SHA2-128f-simple",
            "SLH-DSA-SHA2-192s": "SPHINCS+-SHA2-192s-simple",
            "SLH-DSA-SHA2-256s": "SPHINCS+-SHA2-256s-simple",
        }
        return mapping.get(algorithm, algorithm)


def get_supported_archival_algorithms() -> list[str]:
    """Return list of supported archival signature algorithms."""
    return list(SPHINCS_PARAMS.keys())
