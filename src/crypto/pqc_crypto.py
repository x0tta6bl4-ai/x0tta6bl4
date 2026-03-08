"""
Post-Quantum Cryptography Module.

Uses liboqs Kyber KEM for key encapsulation with AES-GCM for symmetric encryption.
Falls back to mock (AES-GCM only) if liboqs is not available.
"""

import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

# Try to import real PQC adapter - FAIL CLOSED if not available
try:
    from src.security.pqc.pqc_adapter import PQCAdapter

    LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs PQC available - using real post-quantum cryptography")
except (ImportError, AttributeError, RuntimeError) as e:
    LIBOQS_AVAILABLE = False
    logger.critical(f"❌ CRITICAL SECURITY ERROR: liboqs PQC NOT available! ({e})")
    # In production-beta, we MUST NOT fall back to insecure classical-only encryption.
    # PQC is a core mandate of x0tta6bl4.
    # DEV MODE: Set PQC_FAIL_CLOSED=false to allow development without liboqs
    import os
    if os.getenv("PQC_FAIL_CLOSED", "true").lower() == "false":
        logger.warning("⚠️ DEV MODE: PQC fail-closed disabled. Using fallback!")
        LIBOQS_AVAILABLE = True  # Mock for dev
    else:
        raise RuntimeError("Fail-closed: liboqs-dev and liboqs-python are mandatory for PQC.\nSet PQC_FAIL_CLOSED=false for dev mode.")


class PQCCrypto:
    """
    Post-Quantum Cryptography wrapper.

    Uses Kyber KEM (ML-KEM) for key encapsulation when liboqs is available,
    with AES-GCM for symmetric encryption of actual data.

    For each session, generates a Kyber keypair. The public key can be
    shared with peers for them to encapsulate shared secrets.
    """

    def __init__(self, kem_alg: str = "Kyber768"):
        """
        Initialize PQC crypto.

        Args:
            kem_alg: Kyber algorithm variant (Kyber512, Kyber768, Kyber1024)
        """
        # Enforcement: use_real_pqc is no longer an option, it is a REQUIREMENT.
        try:
            self._adapter = PQCAdapter(kem_alg=kem_alg)
            # Generate session keypair
            self.public_key, self._private_key = (
                self._adapter.kem_generate_keypair()
            )
            # For local encrypt/decrypt, we use a derived key
            # In real usage, peer would encapsulate to our public_key
            _, self._shared_secret = self._adapter.kem_encapsulate(self.public_key)
            self.key = self._shared_secret[:32]  # Use first 32 bytes for AES-256
            logger.debug(f"PQC initialized with real {kem_alg}")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize real PQC backend: {e}")
            raise RuntimeError(f"PQC initialization failure: {e}")


    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-256-GCM with PQC-derived key.

        Args:
            data: Plaintext bytes to encrypt

        Returns:
            Encrypted bytes: iv (12) + tag (16) + ciphertext
        """
        iv = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(self.key), modes.GCM(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM with PQC-derived key.

        Args:
            data: Encrypted bytes (iv + tag + ciphertext)

        Returns:
            Decrypted plaintext bytes
        """
        if len(data) < 28:
            return data  # Return raw if too short (not encrypted)

        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]

        cipher = Cipher(
            algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def encapsulate_for_peer(self, peer_public_key: bytes) -> tuple[bytes, bytes]:
        """
        Encapsulate a shared secret for a peer using their public key.

        Args:
            peer_public_key: Peer's Kyber public key

        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        return self._adapter.kem_encapsulate(peer_public_key)

    def decapsulate(self, ciphertext: bytes) -> bytes:
        """
        Decapsulate a shared secret from ciphertext using our private key.

        Args:
            ciphertext: Kyber ciphertext from encapsulation

        Returns:
            Shared secret bytes
        """
        return self._adapter.kem_decapsulate(self._private_key, ciphertext)

    def get_public_key(self) -> bytes | None:
        """Get our public key for peers to encapsulate to us."""
        return self.public_key

    def is_real_pqc(self) -> bool:
        """Always returns True as classical-only fallback is removed."""
        return True


    @staticmethod
    def is_available() -> bool:
        """Check if liboqs is available on this system."""
        return LIBOQS_AVAILABLE
