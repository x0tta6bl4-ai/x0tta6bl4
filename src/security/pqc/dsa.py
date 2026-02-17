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

logger = logging.getLogger(__name__)


class PQCDigitalSignature:
    """
    ML-DSA-65 Digital Signature Algorithm.
    
    NIST FIPS 204 compliant digital signatures for quantum-resistant
    authentication and integrity.
    
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
        self._key_cache: Dict[str, PQCKeyPair] = {}
        
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
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot generate keypair")
        
        try:
            public_key, secret_key = self._adapter.sig_generate_keypair()
            
            created = datetime.utcnow()
            expires = created + timedelta(days=validity_days)
            
            keypair = PQCKeyPair(
                algorithm=self.algorithm,
                public_key=public_key,
                secret_key=secret_key,
                created_at=created,
                expires_at=expires,
                key_id=key_id,
            )
            
            if key_id:
                self._key_cache[key_id] = keypair
            
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
        """Get cached keypair by ID."""
        return self._key_cache.get(key_id)
    
    def clear_cache(self):
        """Clear keypair cache."""
        self._key_cache.clear()
        logger.debug("Cleared keypair cache")
    
    def is_available(self) -> bool:
        """Check if DSA is available."""
        return self.enabled
