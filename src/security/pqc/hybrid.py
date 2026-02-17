"""
Hybrid Classical + Post-Quantum Cryptography.

Combines classical algorithms (X25519, Ed25519) with PQC (ML-KEM, ML-DSA)
for defense-in-depth security.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .types import PQCKeyPair, PQCSignature
from .kem import PQCKeyExchange
from .dsa import PQCDigitalSignature
from .adapter import is_liboqs_available

logger = logging.getLogger(__name__)


@dataclass
class HybridKeyPair:
    """Hybrid keypair combining classical and PQC keys."""
    classical_keypair: PQCKeyPair
    pqc_keypair: PQCKeyPair
    algorithm: str
    created_at: datetime
    expires_at: datetime
    key_id: str = ""
    
    @property
    def public_key(self) -> bytes:
        """Combined public key (classical || PQC)."""
        return self.classical_keypair.public_key + self.pqc_keypair.public_key
    
    @property
    def secret_key(self) -> bytes:
        """Combined secret key (classical || PQC)."""
        return self.classical_keypair.secret_key + self.pqc_keypair.secret_key


@dataclass
class HybridSignature:
    """Hybrid signature combining classical and PQC signatures."""
    classical_signature: bytes
    pqc_signature: bytes
    algorithm: str
    message_hash: bytes
    timestamp: datetime
    signer_key_id: str = ""
    
    @property
    def signature_bytes(self) -> bytes:
        """Combined signature (classical || PQC)."""
        return self.classical_signature + self.pqc_signature


class HybridKeyExchange:
    """
    Hybrid Key Encapsulation (X25519 + ML-KEM-768).
    
    Provides defense-in-depth: if either algorithm is broken,
    the other still protects the communication.
    
    Usage:
        hybrid = HybridKeyExchange()
        
        # Generate keypair
        keypair = hybrid.generate_keypair()
        
        # Encapsulate
        ciphertext, shared_secret = hybrid.encapsulate(peer_public_key)
        
        # Decapsulate
        shared_secret = hybrid.decapsulate(secret_key, ciphertext)
    """
    
    ALGORITHM = "X25519-ML-KEM-768"
    
    def __init__(self):
        """Initialize hybrid key exchange."""
        self.enabled = is_liboqs_available()
        self._pqc_kem: Optional[PQCKeyExchange] = None
        
        if self.enabled:
            try:
                self._pqc_kem = PQCKeyExchange()
                logger.info("HybridKeyExchange initialized (X25519 + ML-KEM-768)")
            except Exception as e:
                logger.warning(f"Failed to initialize PQC KEM: {e}")
                self.enabled = False
        else:
            logger.warning("liboqs not available - hybrid KEM disabled")
    
    def generate_keypair(
        self,
        key_id: str = "",
        validity_days: int = 365
    ) -> HybridKeyPair:
        """
        Generate hybrid keypair.
        
        Args:
            key_id: Optional key identifier
            validity_days: Key validity period
        
        Returns:
            HybridKeyPair with classical and PQC keys
        """
        if not self.enabled:
            raise RuntimeError("Hybrid KEM not available")
        
        try:
            # Generate X25519 keypair (using cryptography library)
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            classical_private = X25519PrivateKey.generate()
            classical_public = classical_private.public_key()
            
            classical_keypair = PQCKeyPair(
                algorithm="X25519",
                public_key=classical_public.public_bytes_raw(),
                secret_key=classical_private.private_bytes_raw(),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=validity_days),
                key_id=f"{key_id}_x25519",
            )
            
            # Generate ML-KEM-768 keypair
            pqc_keypair = self._pqc_kem.generate_keypair(
                key_id=f"{key_id}_mlkem",
                validity_days=validity_days
            )
            
            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)
            
            hybrid_keypair = HybridKeyPair(
                classical_keypair=classical_keypair,
                pqc_keypair=pqc_keypair,
                algorithm=self.ALGORITHM,
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )
            
            logger.info(f"Generated hybrid keypair: {key_id}")
            return hybrid_keypair
            
        except Exception as e:
            logger.error(f"Failed to generate hybrid keypair: {e}")
            raise
    
    def encapsulate(self, peer_public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Hybrid encapsulation.
        
        Args:
            peer_public_key: Combined peer public key (X25519 || ML-KEM)
        
        Returns:
            Tuple of (combined_ciphertext, shared_secret)
        """
        if not self.enabled:
            raise RuntimeError("Hybrid KEM not available")
        
        try:
            # Split peer public key
            x25519_size = 32  # X25519 public key size
            peer_x25519 = peer_public_key[:x25519_size]
            peer_mlkem = peer_public_key[x25519_size:]
            
            # X25519 encapsulation (ECDH)
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            our_private = X25519PrivateKey.generate()
            our_public = our_private.public_key()
            
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
            peer_x25519_public = X25519PublicKey.from_public_bytes(peer_x25519)
            x25519_shared = our_private.exchange(peer_x25519_public)
            
            x25519_ciphertext = our_public.public_bytes_raw()
            
            # ML-KEM encapsulation
            mlkem_ciphertext, mlkem_shared = self._pqc_kem.encapsulate(peer_mlkem)
            
            # Combine shared secrets using HKDF
            combined_secret = self._derive_hybrid_secret(
                x25519_shared, mlkem_shared
            )
            
            # Combine ciphertexts
            combined_ciphertext = x25519_ciphertext + mlkem_ciphertext
            
            logger.debug(f"Hybrid encapsulation: {len(combined_ciphertext)} byte ciphertext")
            return combined_ciphertext, combined_secret
            
        except Exception as e:
            logger.error(f"Failed hybrid encapsulation: {e}")
            raise
    
    def decapsulate(
        self,
        secret_key: bytes,
        ciphertext: bytes
    ) -> bytes:
        """
        Hybrid decapsulation.
        
        Args:
            secret_key: Combined secret key (X25519 || ML-KEM)
            ciphertext: Combined ciphertext (X25519 || ML-KEM)
        
        Returns:
            Shared secret
        """
        if not self.enabled:
            raise RuntimeError("Hybrid KEM not available")
        
        try:
            # Split keys and ciphertext
            x25519_size = 32
            mlkem_ct_size = 1088  # ML-KEM-768 ciphertext size
            
            x25519_secret = secret_key[:x25519_size]
            mlkem_secret = secret_key[x25519_size:]
            
            x25519_ct = ciphertext[:x25519_size]
            mlkem_ct = ciphertext[x25519_size:x25519_size + mlkem_ct_size]
            
            # X25519 decapsulation (ECDH)
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
            our_private = X25519PrivateKey.from_private_bytes(x25519_secret)
            peer_public = X25519PublicKey.from_public_bytes(x25519_ct)
            x25519_shared = our_private.exchange(peer_public)
            
            # ML-KEM decapsulation
            mlkem_shared = self._pqc_kem.decapsulate(mlkem_secret, mlkem_ct)
            
            # Combine shared secrets
            combined_secret = self._derive_hybrid_secret(
                x25519_shared, mlkem_shared
            )
            
            logger.debug("Hybrid decapsulation successful")
            return combined_secret
            
        except Exception as e:
            logger.error(f"Failed hybrid decapsulation: {e}")
            raise
    
    def _derive_hybrid_secret(
        self,
        classical_secret: bytes,
        pqc_secret: bytes
    ) -> bytes:
        """Derive combined secret using HKDF with random salt.
        
        SECURITY FIX (CVE-2026-PQC-002): Use random salt for each key derivation
        to prevent key recovery attacks if one shared secret is compromised.
        """
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        combined = classical_secret + pqc_secret
        
        # SECURITY: Generate random salt for each derivation
        # This provides forward secrecy even if one secret is compromised
        salt = secrets.token_bytes(32)
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"hybrid-x25519-mlkem768",
            backend=default_backend()
        )
        
        return hkdf.derive(combined)
    
    def is_available(self) -> bool:
        """Check if hybrid KEM is available."""
        return self.enabled


class HybridSignatureScheme:
    """
    Hybrid Digital Signature (Ed25519 + ML-DSA-65).
    
    Provides defense-in-depth for authentication and integrity.
    
    Usage:
        hybrid = HybridSignatureScheme()
        
        # Generate keypair
        keypair = hybrid.generate_keypair()
        
        # Sign
        signature = hybrid.sign(message, keypair)
        
        # Verify
        is_valid = hybrid.verify(message, signature, public_key)
    """
    
    ALGORITHM = "Ed25519-ML-DSA-65"
    
    def __init__(self):
        """Initialize hybrid signature scheme."""
        self.enabled = is_liboqs_available()
        self._pqc_dsa: Optional[PQCDigitalSignature] = None
        
        if self.enabled:
            try:
                self._pqc_dsa = PQCDigitalSignature()
                logger.info("HybridSignatureScheme initialized (Ed25519 + ML-DSA-65)")
            except Exception as e:
                logger.warning(f"Failed to initialize PQC DSA: {e}")
                self.enabled = False
        else:
            logger.warning("liboqs not available - hybrid DSA disabled")
    
    def generate_keypair(
        self,
        key_id: str = "",
        validity_days: int = 365
    ) -> HybridKeyPair:
        """
        Generate hybrid signing keypair.
        
        Args:
            key_id: Optional key identifier
            validity_days: Key validity period
        
        Returns:
            HybridKeyPair with Ed25519 and ML-DSA keys
        """
        if not self.enabled:
            raise RuntimeError("Hybrid DSA not available")
        
        try:
            # Generate Ed25519 keypair
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            ed_private = Ed25519PrivateKey.generate()
            ed_public = ed_private.public_key()
            
            classical_keypair = PQCKeyPair(
                algorithm="Ed25519",
                public_key=ed_public.public_bytes_raw(),
                secret_key=ed_private.private_bytes_raw(),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=validity_days),
                key_id=f"{key_id}_ed25519",
            )
            
            # Generate ML-DSA-65 keypair
            pqc_keypair = self._pqc_dsa.generate_keypair(
                key_id=f"{key_id}_mldsa",
                validity_days=validity_days
            )
            
            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)
            
            hybrid_keypair = HybridKeyPair(
                classical_keypair=classical_keypair,
                pqc_keypair=pqc_keypair,
                algorithm=self.ALGORITHM,
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )
            
            logger.info(f"Generated hybrid signing keypair: {key_id}")
            return hybrid_keypair
            
        except Exception as e:
            logger.error(f"Failed to generate hybrid signing keypair: {e}")
            raise
    
    def sign(
        self,
        message: bytes,
        keypair: HybridKeyPair
    ) -> HybridSignature:
        """
        Sign with both Ed25519 and ML-DSA.
        
        Args:
            message: Message to sign
            keypair: Hybrid signing keypair
        
        Returns:
            HybridSignature with both signatures
        """
        if not self.enabled:
            raise RuntimeError("Hybrid DSA not available")
        
        try:
            # Ed25519 signature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            ed_private = Ed25519PrivateKey.from_private_bytes(
                keypair.classical_keypair.secret_key
            )
            ed_signature = ed_private.sign(message)
            
            # ML-DSA signature
            pqc_sig = self._pqc_dsa.sign(
                message,
                keypair.pqc_keypair.secret_key,
                keypair.key_id
            )
            
            message_hash = hashlib.sha256(message).digest()
            
            signature = HybridSignature(
                classical_signature=ed_signature,
                pqc_signature=pqc_sig.signature_bytes,
                algorithm=self.ALGORITHM,
                message_hash=message_hash,
                timestamp=datetime.utcnow(),
                signer_key_id=keypair.key_id,
            )
            
            logger.debug(f"Hybrid signature created: {len(signature.signature_bytes)} bytes")
            return signature
            
        except Exception as e:
            logger.error(f"Failed to create hybrid signature: {e}")
            raise
    
    def verify(
        self,
        message: bytes,
        signature: HybridSignature,
        public_key: bytes
    ) -> bool:
        """
        Verify hybrid signature.
        
        Both signatures must be valid for verification to succeed.
        
        Args:
            message: Original message
            signature: Hybrid signature
            public_key: Combined public key (Ed25519 || ML-DSA)
        
        Returns:
            True if both signatures are valid
        """
        if not self.enabled:
            raise RuntimeError("Hybrid DSA not available")
        
        try:
            # Split public key
            ed25519_size = 32  # Ed25519 public key size
            ed_public = public_key[:ed25519_size]
            mldsa_public = public_key[ed25519_size:]
            
            # Verify Ed25519 signature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            ed_public_key = Ed25519PublicKey.from_public_bytes(ed_public)
            
            try:
                ed_public_key.verify(signature.classical_signature, message)
                ed_valid = True
            except Exception:
                ed_valid = False
            
            # Verify ML-DSA signature
            mldsa_valid = self._pqc_dsa.verify(
                message,
                signature.pqc_signature,
                mldsa_public
            )
            
            # Both must be valid
            is_valid = ed_valid and mldsa_valid
            
            result = "VALID" if is_valid else "INVALID"
            logger.debug(f"Hybrid signature verification: {result}")
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed hybrid signature verification: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if hybrid DSA is available."""
        return self.enabled