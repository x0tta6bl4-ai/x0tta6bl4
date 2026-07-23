"""
Backward-compatible PQC API owned by the canonical ``src.security.pqc`` package.

The old implementations lived under ``src.libx0t.security``.  This module keeps
their public API stable while moving the implementation into the canonical PQC
package, so ``src.security.pqc`` no longer imports legacy modules to initialize.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .adapter import is_liboqs_available
from .types import PQCEncapsulationResult, PQCKeyPair, PQCSignature

logger = logging.getLogger(__name__)

try:
    import oqs
    KeyEncapsulation = oqs.KeyEncapsulation
    Signature = oqs.Signature
except (ImportError, AttributeError):
    KeyEncapsulation = None
    Signature = None

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    x25519 = None  # type: ignore[assignment]
    AESGCM = None  # type: ignore[assignment]
    HKDF = None  # type: ignore[assignment]
    CRYPTOGRAPHY_AVAILABLE = False

LIBOQS_AVAILABLE = (
    is_liboqs_available()
    and KeyEncapsulation is not None
    and Signature is not None
)

_LEGACY_POST_QUANTUM_AVAILABLE = True
_LEGACY_PQC_CORE_AVAILABLE = True


class PQAlgorithm(Enum):
    """Legacy post-quantum algorithm enum."""

    ML_KEM_512 = "ML-KEM-512"
    ML_KEM_768 = "ML-KEM-768"
    ML_KEM_1024 = "ML-KEM-1024"

    ML_DSA_44 = "ML-DSA-44"
    ML_DSA_65 = "ML-DSA-65"
    ML_DSA_87 = "ML-DSA-87"

    FALCON_512 = "Falcon-512"
    FALCON_1024 = "Falcon-1024"
    SPHINCS_PLUS_SHA2_128F = "SPHINCS+-SHA2-128f-simple"
    SPHINCS_PLUS_SHA2_192F = "SPHINCS+-SHA2-192f-simple"

    KYBER_768 = "ML-KEM-768"
    DILITHIUM_3 = "ML-DSA-65"
    HYBRID = "hybrid"


@dataclass
class PQKeyPair:
    """Legacy post-quantum key pair."""

    public_key: bytes
    private_key: bytes
    algorithm: PQAlgorithm
    key_id: str


@dataclass
class PQCiphertext:
    """Legacy post-quantum ciphertext wrapper."""

    ciphertext: bytes
    encapsulated_key: bytes
    algorithm: PQAlgorithm


_LEGACY_KEM_MAP = {
    "Kyber512": "ML-KEM-512",
    "Kyber768": "ML-KEM-768",
    "Kyber1024": "ML-KEM-1024",
}
_LEGACY_SIG_MAP = {
    "Dilithium2": "ML-DSA-44",
    "Dilithium3": "ML-DSA-65",
    "Dilithium5": "ML-DSA-87",
}


def _require_liboqs(import_error: bool = True) -> None:
    if LIBOQS_AVAILABLE:
        return
    message = "liboqs-python not installed. Install with: pip install liboqs-python"
    if import_error:
        raise ImportError(message)
    raise RuntimeError("liboqs not available. Cannot initialize PQMeshSecurityLibOQS")


def _require_cryptography() -> None:
    if not CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError("cryptography library required for hybrid encryption")


def _kem_algorithm_enum(name: str) -> PQAlgorithm:
    normalized = _LEGACY_KEM_MAP.get(name, name)
    if normalized == "ML-KEM-512":
        return PQAlgorithm.ML_KEM_512
    if normalized == "ML-KEM-1024":
        return PQAlgorithm.ML_KEM_1024
    try:
        return PQAlgorithm(normalized)
    except ValueError:
        logger.warning("Unknown KEM algorithm %s, using ML-KEM-768", name)
        return PQAlgorithm.ML_KEM_768


def _sig_algorithm_enum(name: str) -> PQAlgorithm:
    normalized = _LEGACY_SIG_MAP.get(name, name)
    if normalized == "ML-DSA-44":
        return PQAlgorithm.ML_DSA_44
    if normalized == "ML-DSA-87":
        return PQAlgorithm.ML_DSA_87
    try:
        return PQAlgorithm(normalized)
    except ValueError:
        logger.warning("Unknown signature algorithm %s, using ML-DSA-65", name)
        return PQAlgorithm.ML_DSA_65


def _derive_key(secret: bytes, info: bytes) -> bytes:
    _require_cryptography()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    ).derive(secret)


class LibOQSBackend:
    """Legacy liboqs backend facade."""

    def __init__(
        self, kem_algorithm: str = "ML-KEM-768", sig_algorithm: str = "ML-DSA-65"
    ):
        _require_liboqs(import_error=True)
        self.kem_algorithm = _LEGACY_KEM_MAP.get(kem_algorithm, kem_algorithm)
        self.sig_algorithm = _LEGACY_SIG_MAP.get(sig_algorithm, sig_algorithm)

    def generate_kem_keypair(self) -> PQKeyPair:
        kem = KeyEncapsulation(self.kem_algorithm)
        keypair_result = kem.generate_keypair()
        if isinstance(keypair_result, tuple):
            public_key, private_key = keypair_result
        else:
            public_key = keypair_result
            private_key = kem.export_secret_key()

        return PQKeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=_kem_algorithm_enum(self.kem_algorithm),
            key_id=hashlib.sha256(public_key).hexdigest()[:32],
        )

    def generate_sig_keypair(self) -> PQKeyPair:
        return self.generate_signature_keypair()

    def kem_encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        kem = KeyEncapsulation(self.kem_algorithm)
        ciphertext, shared_secret = kem.encap_secret(public_key)
        return shared_secret, ciphertext

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        shared_secret, ciphertext = self.kem_encapsulate(public_key)
        return ciphertext, shared_secret

    def kem_decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        kem = KeyEncapsulation(self.kem_algorithm, private_key)
        return kem.decap_secret(ciphertext)

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        return self.kem_decapsulate(private_key, ciphertext)

    def generate_signature_keypair(self) -> PQKeyPair:
        sig = Signature(self.sig_algorithm)
        public_key = sig.generate_keypair()
        private_key = sig.export_secret_key()
        return PQKeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=_sig_algorithm_enum(self.sig_algorithm),
            key_id=hashlib.sha256(public_key).hexdigest()[:32],
        )

    def sign(self, message: bytes, private_key: bytes) -> bytes:
        sig = Signature(self.sig_algorithm, private_key)
        return sig.sign(message)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        sig = Signature(self.sig_algorithm)
        return bool(sig.verify(message, signature, public_key))


class HybridPQEncryption:
    """Legacy hybrid X25519 + ML-KEM encryption facade."""

    def __init__(self, kem_algorithm: str = "Kyber768"):
        if not LIBOQS_AVAILABLE:
            raise ImportError("liboqs-python required for hybrid encryption")
        _require_cryptography()
        self.pq_backend = LibOQSBackend(kem_algorithm=kem_algorithm)
        self.kem_algorithm = kem_algorithm

    def generate_hybrid_keypair(self) -> dict[str, Any]:
        pq_keypair = self.pq_backend.generate_kem_keypair()

        classical_private_key = x25519.X25519PrivateKey.generate()
        classical_public_key = classical_private_key.public_key()

        classical_private_bytes = classical_private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        classical_public_bytes = classical_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return {
            "type": "hybrid_keypair",
            "pq": {
                "public_key": pq_keypair.public_key.hex(),
                "private_key": pq_keypair.private_key.hex(),
                "algorithm": pq_keypair.algorithm.value,
            },
            "classical": {
                "public_key": classical_public_bytes.hex(),
                "private_key": classical_private_bytes.hex(),
            },
            "key_id": pq_keypair.key_id,
        }

    def encapsulate(self, peer_keypair: dict[str, Any]) -> tuple[bytes, bytes]:
        pq_public = bytes.fromhex(peer_keypair["pq"]["public_key"])
        classical_public = bytes.fromhex(peer_keypair["classical"]["public_key"])
        shared_secret, ciphertexts = self.hybrid_encapsulate(
            pq_public, classical_public
        )
        ciphertext = ciphertexts["pq"] + ciphertexts["classical"]
        return ciphertext, shared_secret

    def decapsulate(self, ciphertext: bytes, peer_keypair: dict[str, Any]) -> bytes:
        pq_private = bytes.fromhex(peer_keypair["pq"]["private_key"])
        classical_private = bytes.fromhex(peer_keypair["classical"]["private_key"])

        _, probe = self.hybrid_encapsulate(
            bytes.fromhex(peer_keypair["pq"]["public_key"]),
            bytes.fromhex(peer_keypair["classical"]["public_key"]),
        )
        pq_len = len(probe["pq"])
        ciphertexts = {"pq": ciphertext[:pq_len], "classical": ciphertext[pq_len:]}
        return self.hybrid_decapsulate(ciphertexts, pq_private, classical_private)

    def hybrid_encrypt(self, plaintext: bytes, shared_secret: bytes) -> bytes:
        key = _derive_key(shared_secret, b"x0tta6bl4-hybrid-encryption")
        nonce = os.urandom(12)
        return nonce + AESGCM(key).encrypt(nonce, plaintext, None)

    def hybrid_decrypt(self, ciphertext: bytes, shared_secret: bytes) -> bytes:
        key = _derive_key(shared_secret, b"x0tta6bl4-hybrid-encryption")
        nonce, encrypted = ciphertext[:12], ciphertext[12:]
        return AESGCM(key).decrypt(nonce, encrypted, None)

    def hybrid_encapsulate(
        self, pq_public_key: bytes, classical_public_key: bytes
    ) -> tuple[bytes, dict[str, bytes]]:
        pq_secret, pq_ciphertext = self.pq_backend.kem_encapsulate(pq_public_key)

        ephemeral_private = x25519.X25519PrivateKey.generate()
        ephemeral_public = ephemeral_private.public_key()
        peer_classical_public = x25519.X25519PublicKey.from_public_bytes(
            classical_public_key
        )
        classical_shared = ephemeral_private.exchange(peer_classical_public)

        classical_secret = _derive_key(
            classical_shared, b"x0tta6bl4-classical-secret"
        )
        classical_ciphertext = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        combined_secret = _derive_key(
            pq_secret + classical_secret, b"x0tta6bl4-combined-secret"
        )

        return combined_secret, {
            "pq": pq_ciphertext,
            "classical": classical_ciphertext,
        }

    def hybrid_decapsulate(
        self,
        ciphertexts: dict[str, bytes],
        pq_private_key: bytes,
        classical_private_key: bytes,
    ) -> bytes:
        pq_secret = self.pq_backend.kem_decapsulate(pq_private_key, ciphertexts["pq"])

        my_classical_private = x25519.X25519PrivateKey.from_private_bytes(
            classical_private_key
        )
        peer_ephemeral_public = x25519.X25519PublicKey.from_public_bytes(
            ciphertexts["classical"]
        )
        classical_shared = my_classical_private.exchange(peer_ephemeral_public)

        classical_secret = _derive_key(
            classical_shared, b"x0tta6bl4-classical-secret"
        )
        return _derive_key(
            pq_secret + classical_secret, b"x0tta6bl4-combined-secret"
        )

    def _classical_encrypt(self, message: bytes, public_key: bytes) -> bytes:
        raw_key = hashlib.sha256(public_key).digest()
        aes_key = _derive_key(raw_key, b"x0tta6bl4-classical-aes-key")
        nonce = os.urandom(12)
        return nonce + AESGCM(aes_key).encrypt(nonce, message, None)

    def _classical_decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        private_obj = x25519.X25519PrivateKey.from_private_bytes(private_key)
        public_key_bytes = private_obj.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        raw_key = hashlib.sha256(public_key_bytes).digest()
        aes_key = _derive_key(raw_key, b"x0tta6bl4-classical-aes-key")
        nonce, encrypted = ciphertext[:12], ciphertext[12:]
        return AESGCM(aes_key).decrypt(nonce, encrypted, None)


class PQMeshSecurityLibOQS:
    """Legacy mesh-level PQC security facade."""

    def __init__(
        self,
        node_id: str,
        kem_algorithm: str = "ML-KEM-768",
        sig_algorithm: str = "ML-DSA-65",
    ):
        _require_liboqs(import_error=False)
        _require_cryptography()

        kem_algorithm = _LEGACY_KEM_MAP.get(kem_algorithm, kem_algorithm)
        sig_algorithm = _LEGACY_SIG_MAP.get(sig_algorithm, sig_algorithm)

        self.node_id = node_id
        self.pq_backend = LibOQSBackend(
            kem_algorithm=kem_algorithm,
            sig_algorithm=sig_algorithm,
        )
        self.hybrid = HybridPQEncryption(kem_algorithm=kem_algorithm)
        self.hybrid_cipher = self.hybrid
        self.kem_keypair = self.pq_backend.generate_kem_keypair()
        self.sig_keypair = self.pq_backend.generate_signature_keypair()
        self.classical_private = x25519.X25519PrivateKey.generate()
        self.classical_public = self.classical_private.public_key()
        self._peer_keys: dict[str, bytes] = {}

    def generate_kem_keypair(self) -> bytes:
        self.kem_keypair = self.pq_backend.generate_kem_keypair()
        return self.kem_keypair.public_key

    def kem_encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        return self.pq_backend.kem_encapsulate(public_key)

    def kem_decapsulate(self, ciphertext: bytes) -> bytes | None:
        try:
            return self.pq_backend.kem_decapsulate(
                self.kem_keypair.private_key,
                ciphertext,
            )
        except (ValueError, TypeError, RuntimeError, OSError):
            return None

    def sign(self, message: bytes) -> bytes:
        if message is None:
            raise TypeError("message cannot be None")
        return self.sign_beacon(message)

    def verify(
        self, message: bytes, signature: bytes, public_key: bytes | None = None
    ) -> bool:
        if message is None or signature is None:
            raise TypeError("message/signature cannot be None")
        key = public_key or self.sig_keypair.public_key
        return self.verify_beacon(message, signature, key)

    def get_public_keys(self) -> dict[str, str]:
        classical_public_bytes = self.classical_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "node_id": self.node_id,
            "kem_public_key": self.kem_keypair.public_key.hex(),
            "sig_public_key": self.sig_keypair.public_key.hex(),
            "classical_public_key": classical_public_bytes.hex(),
            "kem_algorithm": self.kem_keypair.algorithm.value,
            "sig_algorithm": self.sig_keypair.algorithm.value,
            "key_id": self.kem_keypair.key_id,
        }

    async def establish_secure_channel(
        self, peer_id: str, peer_public_keys: dict[str, str]
    ) -> bytes:
        kem_public = bytes.fromhex(peer_public_keys["kem_public_key"])
        classical_public_hex = peer_public_keys.get("classical_public_key")
        if classical_public_hex:
            classical_public = bytes.fromhex(classical_public_hex)
        else:
            classical_public = (
                x25519.X25519PrivateKey.generate()
                .public_key()
                .public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            )

        shared_secret, _ = self.hybrid.hybrid_encapsulate(
            kem_public,
            classical_public,
        )
        self._peer_keys[peer_id] = shared_secret
        return shared_secret

    def sign_beacon(self, beacon_data: bytes) -> bytes:
        return self.pq_backend.sign(beacon_data, self.sig_keypair.private_key)

    def verify_beacon(
        self, beacon_data: bytes, signature: bytes, peer_public_key: bytes
    ) -> bool:
        return self.pq_backend.verify(beacon_data, signature, peer_public_key)

    def encrypt_for_peer(self, peer_id: str, plaintext: bytes) -> bytes:
        key = self._peer_keys.get(peer_id)
        if not key:
            raise ValueError(f"No shared key with {peer_id}")
        aes_key = _derive_key(key, b"x0tta6bl4-peer-aes-key")
        nonce = os.urandom(12)
        return nonce + AESGCM(aes_key).encrypt(nonce, plaintext, None)

    def decrypt_from_peer(self, peer_id: str, ciphertext: bytes) -> bytes:
        key = self._peer_keys.get(peer_id)
        if not key:
            raise ValueError(f"No shared key with {peer_id}")
        aes_key = _derive_key(key, b"x0tta6bl4-peer-aes-key")
        nonce, encrypted = ciphertext[:12], ciphertext[12:]
        return AESGCM(aes_key).decrypt(nonce, encrypted, None)

    def get_security_level(self) -> dict[str, Any]:
        return {
            "algorithm": (
                f"hybrid_{self.kem_keypair.algorithm.value}_"
                f"{self.sig_keypair.algorithm.value}"
            ),
            "pq_security_level": "NIST Level 3",
            "kem_algorithm": self.kem_keypair.algorithm.value,
            "sig_algorithm": self.sig_keypair.algorithm.value,
            "key_exchange": "quantum_safe",
            "peers_with_pq": len(self._peer_keys),
        }


class PQCKeyExchange:
    """Legacy ML-KEM helper backed by the captured liboqs class."""

    ALGORITHM = "ML-KEM-768"

    def __init__(self):
        self.enabled = bool(LIBOQS_AVAILABLE and KeyEncapsulation is not None)
        self.key_cache: dict[str, PQCKeyPair] = {}

    def generate_keypair(
        self, key_id: str = "", validity_days: int = 365
    ) -> PQCKeyPair:
        if not self.enabled:
            raise RuntimeError("PQC not available")

        kem = KeyEncapsulation(self.ALGORITHM)
        keypair_result = kem.generate_keypair()
        if isinstance(keypair_result, tuple):
            public_key, secret_key = keypair_result
        else:
            public_key = keypair_result
            secret_key = kem.export_secret_key()

        if not key_id:
            key_id = hashlib.sha256(public_key).hexdigest()[:32]

        created = datetime.utcnow()
        keypair = PQCKeyPair(
            algorithm=self.ALGORITHM,
            public_key=public_key,
            secret_key=secret_key,
            created_at=created,
            expires_at=created + timedelta(days=validity_days),
            key_id=key_id,
        )
        self.key_cache[key_id] = keypair
        return keypair

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        if not self.enabled:
            raise RuntimeError("PQC not available")
        kem = KeyEncapsulation(self.ALGORITHM)
        ciphertext, shared_secret = kem.encap_secret(public_key)
        return ciphertext, shared_secret

    def encapsulate_legacy(self, public_key: bytes) -> tuple[bytes, bytes]:
        """Encapsulate and return (shared_secret, ciphertext) for legacy PQC contract."""
        res = self.encapsulate(public_key)
        if isinstance(res, PQCEncapsulationResult):
            return res.shared_secret, res.ciphertext
        ciphertext, shared_secret = res
        return shared_secret, ciphertext

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        if not self.enabled:
            raise RuntimeError("PQC not available")
        kem = KeyEncapsulation(self.ALGORITHM, secret_key)
        return kem.decap_secret(ciphertext)


class PQCDigitalSignature:
    """Legacy ML-DSA helper backed by the captured liboqs class."""

    ALGORITHM = "ML-DSA-65"

    def __init__(self):
        self.enabled = bool(LIBOQS_AVAILABLE and Signature is not None)
        self.key_cache: dict[str, PQCKeyPair] = {}

    def generate_keypair(
        self, key_id: str = "", validity_days: int = 365
    ) -> PQCKeyPair:
        if not self.enabled:
            raise RuntimeError("PQC not available")

        sig = Signature(self.ALGORITHM)
        public_key = sig.generate_keypair()
        secret_key = sig.export_secret_key()

        if not key_id:
            key_id = hashlib.sha256(public_key).hexdigest()[:32]

        created = datetime.utcnow()
        keypair = PQCKeyPair(
            algorithm=self.ALGORITHM,
            public_key=public_key,
            secret_key=secret_key,
            created_at=created,
            expires_at=created + timedelta(days=validity_days),
            key_id=key_id,
        )
        self.key_cache[key_id] = keypair
        return keypair

    def sign(
        self, message: bytes, secret_key: bytes, key_id: str = ""
    ) -> PQCSignature:
        if not self.enabled:
            raise RuntimeError("PQC not available")

        sig = Signature(self.ALGORITHM, secret_key)
        signature = sig.sign(message)
        return PQCSignature(
            algorithm=self.ALGORITHM,
            signature_bytes=signature,
            message_hash=hashlib.sha256(message).digest(),
            timestamp=datetime.utcnow(),
            signer_key_id=key_id,
        )

    def verify(
        self, message: bytes, signature_bytes: bytes, public_key: bytes
    ) -> bool:
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            sig = Signature(self.ALGORITHM)
            return bool(sig.verify(message, signature_bytes, public_key))
        except (ValueError, TypeError, RuntimeError, OSError):
            return False


class PQCHybridScheme:
    """Legacy helper that combines compatibility KEM and DSA wrappers."""

    def __init__(self, enable_pqc: bool = True):
        self.enable_pqc = enable_pqc and LIBOQS_AVAILABLE
        self.kem = PQCKeyExchange() if self.enable_pqc else None
        self.dsa = PQCDigitalSignature() if self.enable_pqc else None

    def setup_secure_channel(self) -> dict[str, Any]:
        if not self.kem:
            return {"method": "classical", "status": "no_pqc_available"}

        try:
            client_keypair = self.kem.generate_keypair(key_id="client_ephemeral")
            server_keypair = self.kem.generate_keypair(key_id="server_ephemeral")
            ciphertext, client_secret = self.kem.encapsulate(
                server_keypair.public_key
            )
            server_secret = self.kem.decapsulate(
                server_keypair.secret_key,
                ciphertext,
            )
            if client_secret != server_secret:
                raise ValueError("Shared secret mismatch")
            return {
                "method": "pqc_hybrid",
                "algorithm": "ML-KEM-768",
                "shared_secret_len": len(client_secret),
                "client_public_key_len": len(client_keypair.public_key),
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except (OSError, ValueError, TypeError, RuntimeError, KeyError) as exc:
            logger.error("Failed to setup secure channel: %s", exc)
            return {"method": "fallback", "error": str(exc), "status": "failed"}

    def sign_certificate(self, cert_data: bytes) -> PQCSignature:
        if not self.dsa:
            raise RuntimeError("PQC signature not available")
        keypair = self.dsa.generate_keypair(key_id="cert_signer")
        return self.dsa.sign(cert_data, keypair.secret_key, keypair.key_id)

    def verify_certificate(
        self, cert_data: bytes, signature_bytes: bytes, public_key: bytes
    ) -> bool:
        if not self.dsa:
            raise RuntimeError("PQC signature not available")
        return self.dsa.verify(cert_data, signature_bytes, public_key)


_pqc_key_exchange: PQCKeyExchange | None = None
_pqc_digital_signature: PQCDigitalSignature | None = None
_pqc_hybrid: PQCHybridScheme | None = None


def get_pqc_key_exchange() -> PQCKeyExchange:
    global _pqc_key_exchange
    if _pqc_key_exchange is None:
        _pqc_key_exchange = PQCKeyExchange()
    return _pqc_key_exchange


def get_pqc_digital_signature() -> PQCDigitalSignature:
    global _pqc_digital_signature
    if _pqc_digital_signature is None:
        _pqc_digital_signature = PQCDigitalSignature()
    return _pqc_digital_signature


def get_pqc_hybrid() -> PQCHybridScheme:
    global _pqc_hybrid
    if _pqc_hybrid is None:
        _pqc_hybrid = PQCHybridScheme()
    return _pqc_hybrid


def test_pqc_availability() -> dict[str, Any]:
    try:
        hybrid = get_pqc_hybrid()
        if not hybrid.enable_pqc:
            return {
                "status": "disabled",
                "reason": "liboqs not available",
                "fallback": "classical_crypto",
            }

        result = hybrid.setup_secure_channel()
        return {
            "status": "operational",
            "key_exchange": result,
            "algorithms": ["ML-KEM-768", "ML-DSA-65"],
            "timestamp": datetime.utcnow().isoformat(),
        }
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as exc:
        logger.error("PQC test failed: %s", exc)
        return {"status": "error", "error": str(exc), "fallback": "classical_crypto"}


__all__ = [
    "LIBOQS_AVAILABLE",
    "LibOQSBackend",
    "HybridPQEncryption",
    "PQMeshSecurityLibOQS",
    "PQAlgorithm",
    "PQKeyPair",
    "PQCiphertext",
    "PQCHybridScheme",
    "get_pqc_key_exchange",
    "get_pqc_digital_signature",
    "get_pqc_hybrid",
    "test_pqc_availability",
]
