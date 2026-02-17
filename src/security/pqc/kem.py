"""
ML-KEM-768 Key Encapsulation Mechanism.

NIST FIPS 203 compliant key exchange.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from .types import PQCKeyPair, PQCEncapsulationResult, PQCAlgorithm
from .adapter import PQCAdapter, is_liboqs_available
from .secure_storage import get_secure_storage, SecureKeyHandle

logger = logging.getLogger(__name__)


class PQCKeyExchange:
    """
    ML-KEM-768 Key Encapsulation Mechanism.
    
    NIST FIPS 203 compliant key exchange for quantum-resistant
    secure channel establishment.
    
    SECURITY: Uses SecureKeyStorage for encrypted in-memory key storage
    (CVE-2026-PQC-001 mitigation).
    
    Usage:
        kem = PQCKeyExchange()
        
        # Generate keypair
        keypair = kem.generate_keypair()
        
        # Encapsulate (sender side)
        ciphertext, shared_secret = kem.encapsulate(peer_public_key)
        
        # Decapsulate (receiver side)
        shared_secret = kem.decapsulate(secret_key, ciphertext)
    """
    
    DEFAULT_ALGORITHM = "ML-KEM-768"
    
    def __init__(self, algorithm: str = DEFAULT_ALGORITHM):
        """
        Initialize KEM.
        
        Args:
            algorithm: KEM algorithm (ML-KEM-512, ML-KEM-768, ML-KEM-1024)
        """
        self.algorithm = algorithm
        self.enabled = is_liboqs_available()
        self._adapter: Optional[PQCAdapter] = None
        
        # SECURITY: Use secure storage instead of plain dict
        self._secure_storage = get_secure_storage()
        self._key_handles: Dict[str, SecureKeyHandle] = {}
        
        if self.enabled:
            try:
                self._adapter = PQCAdapter(kem_alg=algorithm)
                logger.info(f"PQCKeyExchange initialized with {algorithm}")
            except Exception as e:
                logger.warning(f"Failed to initialize PQC adapter: {e}")
                self.enabled = False
        else:
            logger.warning("liboqs not available - PQC KEM disabled")
    
    def generate_keypair(
        self,
        key_id: str = "",
        validity_days: int = 365
    ) -> PQCKeyPair:
        """
        Generate ML-KEM keypair.
        
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
            public_key, secret_key = self._adapter.kem_generate_keypair()
            
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
    
    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate shared secret with public key.
        
        Args:
            public_key: Peer's ML-KEM public key
        
        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot encapsulate")
        
        try:
            ciphertext, shared_secret = self._adapter.kem_encapsulate(public_key)
            logger.debug(f"Encapsulated {len(shared_secret)} byte shared secret")
            return ciphertext, shared_secret
            
        except Exception as e:
            logger.error(f"Failed to encapsulate: {e}")
            raise
    
    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate shared secret from ciphertext.
        
        Args:
            secret_key: Our ML-KEM secret key
            ciphertext: Encapsulated ciphertext from peer
        
        Returns:
            Shared secret bytes
        """
        if not self.enabled:
            raise RuntimeError("PQC not available - cannot decapsulate")
        
        try:
            shared_secret = self._adapter.kem_decapsulate(secret_key, ciphertext)
            logger.debug(f"Decapsulated {len(shared_secret)} byte shared secret")
            return shared_secret
            
        except Exception as e:
            logger.error(f"Failed to decapsulate: {e}")
            raise
    
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
        
        # Reconstruct keypair (public key not stored in secure storage)
        # Note: This requires storing public key separately or in metadata
        # For now, return None as public key is not available
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
        """Check if KEM is available."""
        return self.enabled
