"""
ML-DSA-65 Digital Signature Algorithm.

NIST FIPS 204 compliant digital signatures.
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .types import PQCKeyPair, PQCSignature
from .adapter import PQCAdapter, is_liboqs_available
from .secure_storage import get_secure_storage, SecureKeyHandle

logger = logging.getLogger(__name__)


class PQCDigitalSignature:
    """
    ML-DSA-65 Digital Signature Algorithm.
    
    NIST FIPS 204 compliant digital signatures for quantum-resistant
    authentication and integrity.
    
    SECURITY: Uses SecureKeyStorage for encrypted in-memory key storage
    (CVE-2026-PQC-001 mitigation).
    
    Usage:
        dsa = PQCDigitalSignature()
        
        # Generate keypair
        keypair = dsa.generate_keypair()
        
        # Sign message
        signature = dsa.sign(message, keypair.secret_key)
        
        # Verify signature
        is_valid = dsa.verify(message, signature.signature_bytes, keypair.public_key)
    """
    
    DEFAULT_ALGORITHM = "ML-DSA-65"
    
    def __init__(self, algorithm: str = DEFAULT_ALGORITHM):
        """
        Initialize DSA.
        
        Args:
            algorithm: DSA algorithm (ML-DSA-44, ML-DSA-65, ML-DSA-87)
        """
        self.algorithm = algorithm
        self.enabled = is_liboqs_available()
        self._adapter: Optional[PQCAdapter] = None
        
        # SECURITY: Use secure storage instead of plain dict
        self._secure_storage = get_secure_storage()
        self._key_handles: Dict[str, SecureKeyHandle] = {}
        
        if self.enabled:
            try:
                self._adapter = PQCAdapter(sig_alg=algorithm)
                logger.info(f"PQCDigitalSignature initialized with {algorithm}")
            except Exception as e:
                logger.warning(f"Failed to initialize PQC adapter: {e}")
                self.enabled = False
        else:
            logger.warning("liboqs not available - PQC DSA disabled")
    
    def generate_keypair(
        self,
        key_id: str = "",
        validity_days: int = 365
    ) -> PQCKeyPair:
        """
        Generate ML-DSA keypair.
        
        Args:
            key_id: Optional key identifier
            validity_days: Key validity period in days
        
        Returns:
            PQCKeyPair with public and secret keys
            
        SECURITY: Secret key is stored in encrypted SecureKeyStorage
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot generate keypair")
        
        try:
            public_key, secret_key = self._adapter.sig_generate_keypair()
            
            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)
            
            # SECURITY: Store secret key in secure storage
            if key_id:
                handle = self._secure_storage.store_key(
                    key_id=key_id,
                    secret_key=secret_key,
                    algorithm=self.algorithm,
                    validity_days=validity_days
                )
                self._key_handles[key_id] = handle
            
            keypair = PQCKeyPair(
                algorithm=self.algorithm,
                public_key=public_key,
                secret_key=secret_key,  # Returned for immediate use
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )
            
            logger.info(f"Generated {self.algorithm} keypair: {keypair.key_id}")
            return keypair
            
        except Exception as e:
            logger.error(f"Failed to generate keypair: {e}")
            raise
    
    def sign(
        self,
        message: bytes,
        secret_key: bytes,
        key_id: str = ""
    ) -> PQCSignature:
        """
        Sign message with ML-DSA.
        
        Args:
            message: Message to sign
            secret_key: ML-DSA secret key
            key_id: Signer key identifier
        
        Returns:
            PQCSignature with signature bytes
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot sign")
        
        try:
            signature_bytes = self._adapter.sig_sign(message, secret_key)
            message_hash = hashlib.sha256(message).digest()
            
            signature = PQCSignature(
                algorithm=self.algorithm,
                signature_bytes=signature_bytes,
                message_hash=message_hash,
                timestamp=datetime.utcnow(),
                signer_key_id=key_id,
            )
            
            logger.debug(f"Signed message: {len(signature_bytes)} byte signature")
            return signature
            
        except Exception as e:
            logger.error(f"Failed to sign message: {e}")
            raise
    
    def verify(
        self,
        message: bytes,
        signature_bytes: bytes,
        public_key: bytes
    ) -> bool:
        """
        Verify ML-DSA signature.
        
        Args:
            message: Original message
            signature_bytes: Signature bytes
            public_key: Signer's ML-DSA public key
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot verify")
        
        try:
            is_valid = self._adapter.sig_verify(message, signature_bytes, public_key)
            
            result = "VALID" if is_valid else "INVALID"
            logger.debug(f"Signature verification: {result}")
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to verify signature: {e}")
            return False
    
    def get_cached_keypair(self, key_id: str) -> Optional[PQCKeyPair]:
        """
        Get cached keypair by ID.
        
        SECURITY: Retrieves secret key from secure storage.
        """
        handle = self._key_handles.get(key_id)
        if not handle:
            return None
        
        # Retrieve secret key from secure storage
        secret_key = self._secure_storage.get_key(handle)
        if secret_key is None:
            return None
        
        # Note: Public key not stored separately
        logger.warning("Public key not available for cached keypair %s", key_id)
        return None
    
    def get_secret_key(self, key_id: str) -> Optional[bytes]:
        """
        Get secret key from secure storage.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Secret key bytes or None if not found
        """
        handle = self._key_handles.get(key_id)
        if not handle:
            return None
        return self._secure_storage.get_key(handle)
    
    def clear_cache(self):
        """Clear all cached keys securely."""
        for key_id in list(self._key_handles.keys()):
            handle = self._key_handles[key_id]
            self._secure_storage.delete_key(handle)
        self._key_handles.clear()
        logger.debug("Cleared all cached keys securely")
    
    def is_available(self) -> bool:
        """Check if DSA is available."""
        return self.enabled
