"""
PQC Adapter - liboqs Python bindings wrapper.

Provides unified interface to liboqs library for post-quantum cryptography.
"""
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

# Global availability flag
_LIBOQS_AVAILABLE: Optional[bool] = None


def is_liboqs_available() -> bool:
    """
    Check if liboqs is available.
    
    Returns:
        True if liboqs is installed and functional
    """
    global _LIBOQS_AVAILABLE
    
    if _LIBOQS_AVAILABLE is not None:
        return _LIBOQS_AVAILABLE
    
    try:
        import oqs
        # Test basic functionality
        _LIBOQS_AVAILABLE = True
        logger.debug("liboqs is available")
    except ImportError:
        _LIBOQS_AVAILABLE = False
        logger.debug("liboqs not available - PQC features disabled")
    
    return _LIBOQS_AVAILABLE


def get_supported_kem_algorithms() -> List[str]:
    """
    Get list of supported KEM algorithms.
    
    Returns:
        List of KEM algorithm names
    """
    if not is_liboqs_available():
        return []
    
    try:
        import oqs
        if hasattr(oqs, "get_enabled_kem_mechanisms"):
            return list(oqs.get_enabled_kem_mechanisms())
    except Exception as e:
        logger.error(f"Failed to get KEM mechanisms: {e}")
    
    return []


def get_supported_sig_algorithms() -> List[str]:
    """
    Get list of supported signature algorithms.
    
    Returns:
        List of signature algorithm names
    """
    if not is_liboqs_available():
        return []
    
    try:
        import oqs
        if hasattr(oqs, "get_enabled_sig_mechanisms"):
            return list(oqs.get_enabled_sig_mechanisms())
    except Exception as e:
        logger.error(f"Failed to get signature mechanisms: {e}")
    
    return []


class PQCAdapter:
    """
    Adapter for liboqs Python bindings.
    
    Provides unified interface for post-quantum cryptography operations:
    - Key Encapsulation Mechanism (KEM): ML-KEM-768 (Kyber768)
    - Digital Signatures: ML-DSA-65 (Dilithium3)
    
    Supports both NIST FIPS 203/204 names and legacy names.
    
    Usage:
        adapter = PQCAdapter(kem_alg="ML-KEM-768", sig_alg="ML-DSA-65")
        
        # KEM operations
        public_key, secret_key = adapter.kem_generate_keypair()
        ciphertext, shared_secret = adapter.kem_encapsulate(public_key)
        shared_secret = adapter.kem_decapsulate(secret_key, ciphertext)
        
        # Signature operations
        public_key, secret_key = adapter.sig_generate_keypair()
        signature = adapter.sig_sign(message, secret_key)
        is_valid = adapter.sig_verify(message, signature, public_key)
    """
    
    # Legacy name mappings (old → NIST standard)
    LEGACY_KEM_MAP = {
        "Kyber768": "ML-KEM-768",
        "Kyber512": "ML-KEM-512",
        "Kyber1024": "ML-KEM-1024",
    }
    
    LEGACY_SIG_MAP = {
        "Dilithium2": "ML-DSA-44",
        "Dilithium3": "ML-DSA-65",
        "Dilithium5": "ML-DSA-87",
    }
    
    def __init__(
        self,
        kem_alg: str = "ML-KEM-768",
        sig_alg: str = "ML-DSA-65"
    ):
        """
        Initialize PQC adapter.
        
        Args:
            kem_alg: KEM algorithm (default: ML-KEM-768, NIST FIPS 203 Level 3)
            sig_alg: Signature algorithm (default: ML-DSA-65, NIST FIPS 204 Level 3)
        
        Raises:
            RuntimeError: If liboqs is not available or algorithm not supported
        """
        if not is_liboqs_available():
            raise RuntimeError("liboqs not available - cannot initialize PQC adapter")
        
        # Convert legacy names to NIST standard names
        kem_alg = self.LEGACY_KEM_MAP.get(kem_alg, kem_alg)
        sig_alg = self.LEGACY_SIG_MAP.get(sig_alg, sig_alg)
        
        # Validate algorithms
        self._validate_algorithms(kem_alg, sig_alg)
        
        self.kem_alg = kem_alg
        self.sig_alg = sig_alg
        
        logger.info(f"PQCAdapter initialized: KEM={kem_alg}, SIG={sig_alg}")
    
    def _validate_algorithms(self, kem_alg: str, sig_alg: str):
        """Validate that algorithms are supported."""
        import oqs
        
        # Get supported mechanisms
        kem_mechanisms = []
        sig_mechanisms = []
        
        if hasattr(oqs, "get_enabled_kem_mechanisms"):
            kem_mechanisms = oqs.get_enabled_kem_mechanisms()
        
        if hasattr(oqs, "get_enabled_sig_mechanisms"):
            sig_mechanisms = oqs.get_enabled_sig_mechanisms()
        
        # Check KEM
        if kem_mechanisms and kem_alg not in kem_mechanisms:
            # Try legacy name
            legacy_name = next(
                (k for k, v in self.LEGACY_KEM_MAP.items() if v == kem_alg),
                None
            )
            if legacy_name and legacy_name in kem_mechanisms:
                self.kem_alg = legacy_name
            else:
                logger.warning(
                    f"KEM algorithm {kem_alg} not in supported list, "
                    f"will try at runtime"
                )
        
        # Check signature
        if sig_mechanisms and sig_alg not in sig_mechanisms:
            # Try legacy name
            legacy_name = next(
                (k for k, v in self.LEGACY_SIG_MAP.items() if v == sig_alg),
                None
            )
            if legacy_name and legacy_name in sig_mechanisms:
                self.sig_alg = legacy_name
            else:
                logger.warning(
                    f"Signature algorithm {sig_alg} not in supported list, "
                    f"will try at runtime"
                )
    
    # =========================================================================
    # Key Encapsulation Mechanism (KEM)
    # =========================================================================
    
    def kem_generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate KEM keypair.
        
        Returns:
            Tuple of (public_key, secret_key)
        """
        import oqs
        
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            public_key = kem.generate_keypair()
            secret_key = kem.export_secret_key()
            logger.debug(f"Generated {self.kem_alg} keypair")
            return public_key, secret_key
    
    def kem_encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate shared secret.
        
        Args:
            public_key: Peer's public key
        
        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        import oqs
        
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key)
            logger.debug(f"Encapsulated {len(shared_secret)} byte secret")
            return ciphertext, shared_secret
    
    def kem_decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate shared secret.
        
        Args:
            secret_key: Our secret key
            ciphertext: Encapsulated ciphertext
        
        Returns:
            Shared secret
        """
        import oqs
        
        with oqs.KeyEncapsulation(self.kem_alg, secret_key=secret_key) as kem:
            shared_secret = kem.decap_secret(ciphertext)
            logger.debug(f"Decapsulated {len(shared_secret)} byte secret")
            return shared_secret
    
    # =========================================================================
    # Digital Signature Algorithm
    # =========================================================================
    
    def sig_generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate signature keypair.
        
        Returns:
            Tuple of (public_key, secret_key)
        """
        import oqs
        
        with oqs.Signature(self.sig_alg) as sig:
            public_key = sig.generate_keypair()
            secret_key = sig.export_secret_key()
            logger.debug(f"Generated {self.sig_alg} keypair")
            return public_key, secret_key
    
    def sig_sign(self, message: bytes, secret_key: bytes) -> bytes:
        """
        Sign message.
        
        Args:
            message: Message to sign
            secret_key: Signing key
        
        Returns:
            Signature bytes
        """
        import oqs
        
        with oqs.Signature(self.sig_alg, secret_key=secret_key) as sig:
            signature = sig.sign(message)
            logger.debug(f"Created {len(signature)} byte signature")
            return signature
    
    def sig_verify(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes
    ) -> bool:
        """
        Verify signature.
        
        Args:
            message: Original message
            signature: Signature to verify
            public_key: Signer's public key
        
        Returns:
            True if signature is valid
        """
        import oqs
        
        with oqs.Signature(self.sig_alg) as sig:
            try:
                is_valid = sig.verify(message, signature, public_key)
                result = "valid" if is_valid else "invalid"
                logger.debug(f"Signature verification: {result}")
                return is_valid
            except oqs.MechanismNotSupportedError as e:
                logger.error(f"Mechanism not supported: {e}")
                return False
            except Exception as e:
                logger.error(f"Signature verification failed: {e}")
                return False


# Convenience functions
def create_kem_adapter(algorithm: str = "ML-KEM-768") -> PQCAdapter:
    """Create KEM-only adapter."""
    return PQCAdapter(kem_alg=algorithm)


def create_sig_adapter(algorithm: str = "ML-DSA-65") -> PQCAdapter:
    """Create signature-only adapter."""
    return PQCAdapter(sig_alg=algorithm)
