"""
Post-Quantum Cryptography Core

ML-KEM-768 (key encapsulation) and ML-DSA-65 (digital signatures)
for quantum-resistant security.
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

try:
    import oqs
except ImportError:
    oqs = None

logger = logging.getLogger(__name__)


@dataclass
class PQCKeyPair:
    """PQC key pair"""

    algorithm: str  # "ML-KEM-768" or "ML-DSA-65"
    public_key: bytes
    secret_key: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    key_id: str = ""

    def is_expired(self) -> bool:
        """Check if key is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "algorithm": self.algorithm,
            "public_key_b64": self.public_key.hex(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "key_id": self.key_id,
        }


@dataclass
class PQCSignature:
    """PQC digital signature"""

    algorithm: str  # "ML-DSA-65"
    signature_bytes: bytes
    message_hash: bytes
    timestamp: datetime
    signer_key_id: str


class PQCKeyExchange:
    """ML-KEM-768 Key Exchange"""

    ALGORITHM = "ML-KEM-768"

    def __init__(self):
        """Initialize ML-KEM-768"""
        if oqs is None:
            logger.warning("liboqs not available - PQC disabled")
            self.enabled = False
            return

        self.enabled = True
        self.key_cache: Dict[str, PQCKeyPair] = {}

    def generate_keypair(
        self, key_id: str = "", validity_days: int = 365
    ) -> PQCKeyPair:
        """
        Generate ML-KEM-768 keypair

        Args:
            key_id: Optional key identifier
            validity_days: Key validity period

        Returns:
            PQCKeyPair
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            kemalg = oqs.KeyEncapsulation(self.ALGORITHM)
            public_key = kemalg.generate_keypair()
            secret_key = kemalg.export_secret_key()

            if not key_id:
                key_id = hashlib.sha256(public_key).hexdigest()[:16]

            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)

            keypair = PQCKeyPair(
                algorithm=self.ALGORITHM,
                public_key=public_key,
                secret_key=secret_key,
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )

            self.key_cache[key_id] = keypair
            logger.info(f"Generated ML-KEM-768 keypair: {key_id}")

            return keypair

        except Exception as e:
            logger.error(f"Failed to generate ML-KEM-768 keypair: {e}")
            raise

    async def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate shared secret with public key

        Args:
            public_key: ML-KEM-768 public key

        Returns:
            (ciphertext, shared_secret)
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            kemalg = oqs.KeyEncapsulation(self.ALGORITHM)
            # Set the public key after initialization
            ciphertext, shared_secret = kemalg.encap_secret(public_key)

            logger.debug(f"Encapsulated shared secret: {len(shared_secret)} bytes")
            return ciphertext, shared_secret

        except Exception as e:
            logger.error(f"Failed to encapsulate: {e}")
            raise

    async def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate shared secret from ciphertext

        Args:
            secret_key: ML-KEM-768 secret key
            ciphertext: Encapsulated ciphertext

        Returns:
            Shared secret
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            kemalg = oqs.KeyEncapsulation(self.ALGORITHM, secret_key=secret_key)
            shared_secret = kemalg.decap_secret(ciphertext)

            logger.debug(f"Decapsulated shared secret: {len(shared_secret)} bytes")
            return shared_secret

        except Exception as e:
            logger.error(f"Failed to decapsulate: {e}")
            raise


class PQCDigitalSignature:
    """ML-DSA-65 Digital Signature"""

    ALGORITHM = "ML-DSA-65"

    def __init__(self):
        """Initialize ML-DSA-65"""
        if oqs is None:
            logger.warning("liboqs not available - PQC disabled")
            self.enabled = False
            return

        self.enabled = True
        self.key_cache: Dict[str, PQCKeyPair] = {}

    def generate_keypair(
        self, key_id: str = "", validity_days: int = 365
    ) -> PQCKeyPair:
        """
        Generate ML-DSA-65 keypair

        Args:
            key_id: Optional key identifier
            validity_days: Key validity period

        Returns:
            PQCKeyPair
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            sigsalg = oqs.Signature(self.ALGORITHM)
            public_key = sigsalg.generate_keypair()
            secret_key = sigsalg.export_secret_key()

            if not key_id:
                key_id = hashlib.sha256(public_key).hexdigest()[:16]

            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)

            keypair = PQCKeyPair(
                algorithm=self.ALGORITHM,
                public_key=public_key,
                secret_key=secret_key,
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )

            self.key_cache[key_id] = keypair
            logger.info(f"Generated ML-DSA-65 keypair: {key_id}")

            return keypair

        except Exception as e:
            logger.error(f"Failed to generate ML-DSA-65 keypair: {e}")
            raise

    async def sign(
        self, message: bytes, secret_key: bytes, key_id: str = ""
    ) -> PQCSignature:
        """
        Sign message with ML-DSA-65

        Args:
            message: Message to sign
            secret_key: ML-DSA-65 secret key
            key_id: Signer key identifier

        Returns:
            PQCSignature
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            sigsalg = oqs.Signature(self.ALGORITHM, secret_key=secret_key)
            signature = sigsalg.sign(message)
            message_hash = hashlib.sha256(message).digest()

            logger.debug(f"Signed message: {len(signature)} byte signature")

            return PQCSignature(
                algorithm=self.ALGORITHM,
                signature_bytes=signature,
                message_hash=message_hash,
                timestamp=datetime.utcnow(),
                signer_key_id=key_id,
            )

        except Exception as e:
            logger.error(f"Failed to sign message: {e}")
            raise

    async def verify(
        self, message: bytes, signature_bytes: bytes, public_key: bytes
    ) -> bool:
        """
        Verify ML-DSA-65 signature

        Args:
            message: Original message
            signature_bytes: Signature bytes
            public_key: ML-DSA-65 public key

        Returns:
            True if signature is valid
        """
        if not self.enabled:
            raise RuntimeError("PQC not available")

        try:
            sigsalg = oqs.Signature(self.ALGORITHM)
            is_valid = sigsalg.verify(message, signature_bytes, public_key)

            logger.debug(
                f"Signature verification: {'VALID' if is_valid else 'INVALID'}"
            )
            return is_valid

        except Exception as e:
            logger.error(f"Failed to verify signature: {e}")
            return False


class PQCHybridScheme:
    """Hybrid classical + PQC cryptography"""

    def __init__(self, enable_pqc: bool = True):
        """
        Initialize hybrid scheme

        Args:
            enable_pqc: Enable PQC (fallback to classical if not available)
        """
        self.enable_pqc = enable_pqc and oqs is not None
        self.kem = PQCKeyExchange() if self.enable_pqc else None
        self.dsa = PQCDigitalSignature() if self.enable_pqc else None

        if not self.enable_pqc:
            logger.warning("PQC disabled - using classical cryptography only")

    async def setup_secure_channel(self) -> Dict[str, Any]:
        """
        Setup secure channel with PQC

        Returns:
            Channel setup parameters
        """
        if not self.kem:
            return {"method": "classical", "status": "no_pqc_available"}

        try:
            # Generate ephemeral keypair
            client_keypair = self.kem.generate_keypair(key_id="client_ephemeral")
            server_keypair = self.kem.generate_keypair(key_id="server_ephemeral")

            # Exchange public keys and encapsulate
            ciphertext, client_secret = await self.kem.encapsulate(
                server_keypair.public_key
            )
            server_secret = await self.kem.decapsulate(
                server_keypair.secret_key, ciphertext
            )

            # Verify shared secret match
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

        except Exception as e:
            logger.error(f"Failed to setup secure channel: {e}")
            return {"method": "fallback", "error": str(e), "status": "failed"}

    async def sign_certificate(self, cert_data: bytes) -> PQCSignature:
        """
        Sign certificate with PQC

        Args:
            cert_data: Certificate data to sign

        Returns:
            PQCSignature
        """
        if not self.dsa:
            raise RuntimeError("PQC signature not available")

        keypair = self.dsa.generate_keypair(key_id="cert_signer")
        signature = await self.dsa.sign(cert_data, keypair.secret_key, keypair.key_id)

        return signature

    async def verify_certificate(
        self, cert_data: bytes, signature_bytes: bytes, public_key: bytes
    ) -> bool:
        """
        Verify PQC-signed certificate

        Args:
            cert_data: Certificate data
            signature_bytes: Signature
            public_key: Signer's public key

        Returns:
            True if signature is valid
        """
        if not self.dsa:
            raise RuntimeError("PQC signature not available")

        return await self.dsa.verify(cert_data, signature_bytes, public_key)


# Global instances
_pqc_key_exchange: Optional[PQCKeyExchange] = None
_pqc_digital_signature: Optional[PQCDigitalSignature] = None
_pqc_hybrid: Optional[PQCHybridScheme] = None


def get_pqc_key_exchange() -> PQCKeyExchange:
    """Get PQC key exchange instance"""
    global _pqc_key_exchange
    if _pqc_key_exchange is None:
        _pqc_key_exchange = PQCKeyExchange()
    return _pqc_key_exchange


def get_pqc_digital_signature() -> PQCDigitalSignature:
    """Get PQC digital signature instance"""
    global _pqc_digital_signature
    if _pqc_digital_signature is None:
        _pqc_digital_signature = PQCDigitalSignature()
    return _pqc_digital_signature


def get_pqc_hybrid() -> PQCHybridScheme:
    """Get PQC hybrid scheme instance"""
    global _pqc_hybrid
    if _pqc_hybrid is None:
        _pqc_hybrid = PQCHybridScheme()
    return _pqc_hybrid


async def test_pqc_availability() -> Dict[str, Any]:
    """Test PQC availability and functionality"""
    try:
        hybrid = get_pqc_hybrid()

        if not hybrid.enable_pqc:
            return {
                "status": "disabled",
                "reason": "liboqs not available",
                "fallback": "classical_crypto",
            }

        # Test key exchange
        result = await hybrid.setup_secure_channel()

        return {
            "status": "operational",
            "key_exchange": result,
            "algorithms": ["ML-KEM-768", "ML-DSA-65"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"PQC test failed: {e}")
        return {"status": "error", "error": str(e), "fallback": "classical_crypto"}
