"""
Hybrid Post-Quantum Cryptography
=================================

Implements hybrid mode: Classical (X25519) + Post-Quantum (ML-KEM-768)
for maximum security and compatibility.
"""
import logging
import hashlib
import secrets
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("⚠️ cryptography library not available. Install with: pip install cryptography")

from src.security.post_quantum_liboqs import (
    LibOQSBackend,
    PQKeyPair,
    LIBOQS_AVAILABLE
)

logger = logging.getLogger(__name__)


@dataclass
class HybridKeyPair:
    """Hybrid keypair (Classical + Post-Quantum)."""
    classical_public: bytes
    classical_private: bytes
    pq_public: bytes
    pq_private: bytes
    key_id: str


@dataclass
class HybridCiphertext:
    """Hybrid ciphertext (Classical + PQ)."""
    classical_ciphertext: bytes
    pq_ciphertext: bytes
    combined_secret: bytes


class HybridPQEncryption:
    """
    Hybrid Classical + Post-Quantum Encryption.
    
    Combines:
    - Classical: X25519 (for compatibility)
    - Post-Quantum: ML-KEM-768 (for quantum resistance)
    
    Security = MAX(classical, post-quantum)
    """
    
    def __init__(self, kem_algorithm: str = "ML-KEM-768"):
        """
        Initialize hybrid encryption.
        
        Args:
            kem_algorithm: PQC KEM algorithm
        """
        if not LIBOQS_AVAILABLE:
            raise RuntimeError("liboqs-python required for hybrid encryption")
        
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("cryptography library required for hybrid encryption")
        
        self.pq_backend = LibOQSBackend(kem_algorithm=kem_algorithm)
        self.kem_algorithm = kem_algorithm
        
        logger.info(f"✅ Hybrid PQ Encryption initialized: {kem_algorithm} + X25519")
    
    def generate_hybrid_keypair(self) -> HybridKeyPair:
        """
        Generate hybrid keypair (Classical + PQ).
        
        Returns:
            HybridKeyPair
        """
        # Post-Quantum keypair (ML-KEM-768)
        pq_keypair = self.pq_backend.generate_kem_keypair()
        
        # Classical keypair (X25519)
        classical_private = X25519PrivateKey.generate()
        classical_public = classical_private.public_key()
        
        # Serialize classical keys
        classical_private_bytes = classical_private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        classical_public_bytes = classical_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Generate key_id from both public keys
        combined_public = classical_public_bytes + pq_keypair.public_key
        key_id = hashlib.sha256(combined_public).hexdigest()[:16]
        
        return HybridKeyPair(
            classical_public=classical_public_bytes,
            classical_private=classical_private_bytes,
            pq_public=pq_keypair.public_key,
            pq_private=pq_keypair.private_key,
            key_id=key_id
        )
    
    def hybrid_encapsulate(
        self,
        peer_classical_public: bytes,
        peer_pq_public: bytes
    ) -> Tuple[bytes, HybridCiphertext]:
        """
        Hybrid key encapsulation.
        
        Combines X25519 and ML-KEM-768 for maximum security.
        
        Args:
            peer_classical_public: Peer's X25519 public key
            peer_pq_public: Peer's ML-KEM-768 public key
            
        Returns:
            (combined_secret, hybrid_ciphertext)
        """
        # Post-Quantum encapsulation (ML-KEM-768)
        pq_secret, pq_ciphertext = self.pq_backend.kem_encapsulate(peer_pq_public)
        
        # Classical encapsulation (X25519)
        # Generate ephemeral keypair
        ephemeral_private = X25519PrivateKey.generate()
        ephemeral_public = ephemeral_private.public_key()
        
        # Perform X25519 key exchange
        peer_public_key = X25519PublicKey.from_public_bytes(peer_classical_public)
        classical_secret = ephemeral_private.exchange(peer_public_key)
        
        # Serialize ephemeral public key (for transmission)
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Combine secrets: SHA-256(pq_secret || classical_secret)
        combined_secret = hashlib.sha256(pq_secret + classical_secret).digest()
        
        # Create hybrid ciphertext
        hybrid_ciphertext = HybridCiphertext(
            classical_ciphertext=ephemeral_public_bytes,
            pq_ciphertext=pq_ciphertext,
            combined_secret=combined_secret
        )
        
        return combined_secret, hybrid_ciphertext
    
    def hybrid_decapsulate(
        self,
        hybrid_ciphertext: HybridCiphertext,
        classical_private: bytes,
        pq_private: bytes
    ) -> bytes:
        """
        Hybrid key decapsulation.
        
        Args:
            hybrid_ciphertext: Hybrid ciphertext
            classical_private: Our X25519 private key
            pq_private: Our ML-KEM-768 private key
            
        Returns:
            combined_secret
        """
        # Post-Quantum decapsulation
        pq_secret = self.pq_backend.kem_decapsulate(pq_private, hybrid_ciphertext.pq_ciphertext)
        
        # Classical decapsulation (X25519)
        our_private_key = X25519PrivateKey.from_private_bytes(classical_private)
        peer_ephemeral_public = X25519PublicKey.from_public_bytes(
            hybrid_ciphertext.classical_ciphertext
        )
        classical_secret = our_private_key.exchange(peer_ephemeral_public)
        
        # Combine secrets
        combined_secret = hashlib.sha256(pq_secret + classical_secret).digest()
        
        return combined_secret
    
    def get_public_keys(self, keypair: HybridKeyPair) -> Dict[str, str]:
        """
        Get public keys for sharing.
        
        Args:
            keypair: Hybrid keypair
            
        Returns:
            Dict with public keys
        """
        return {
            "classical_public_key": keypair.classical_public.hex(),
            "pq_public_key": keypair.pq_public.hex(),
            "key_id": keypair.key_id,
            "algorithm": f"hybrid_X25519_{self.kem_algorithm}"
        }


class HybridPQMeshSecurity:
    """
    Hybrid Post-Quantum Mesh Security.
    
    Uses hybrid mode (X25519 + ML-KEM-768) for maximum security
    and backward compatibility.
    """
    
    def __init__(
        self,
        node_id: str,
        kem_algorithm: str = "ML-KEM-768"
    ):
        """
        Initialize hybrid PQ mesh security.
        
        Args:
            node_id: Node identifier
            kem_algorithm: PQC KEM algorithm
        """
        self.node_id = node_id
        self.hybrid = HybridPQEncryption(kem_algorithm=kem_algorithm)
        
        # Generate hybrid keypair
        self.keypair = self.hybrid.generate_hybrid_keypair()
        
        # Session keys with peers
        self._peer_keys: Dict[str, bytes] = {}
        
        logger.info(f"✅ Hybrid PQ Mesh Security initialized for {node_id}")
    
    def get_public_keys(self) -> Dict[str, str]:
        """Get public keys for sharing."""
        return self.hybrid.get_public_keys(self.keypair)
    
    async def establish_secure_channel(
        self,
        peer_id: str,
        peer_public_keys: Dict
    ) -> bytes:
        """
        Establish hybrid secure channel with peer.
        
        Args:
            peer_id: Peer identifier
            peer_public_keys: Peer's public keys (classical + pq)
            
        Returns:
            shared_secret
        """
        peer_classical_public = bytes.fromhex(peer_public_keys["classical_public_key"])
        peer_pq_public = bytes.fromhex(peer_public_keys["pq_public_key"])
        
        # Hybrid encapsulation
        shared_secret, _ = self.hybrid.hybrid_encapsulate(
            peer_classical_public,
            peer_pq_public
        )
        
        self._peer_keys[peer_id] = shared_secret
        
        logger.info(f"✅ Established hybrid PQ-secure channel with {peer_id}")
        
        return shared_secret
    
    def get_security_level(self) -> Dict[str, Any]:
        """Get security level information."""
        return {
            "algorithm": f"hybrid_X25519_{self.hybrid.kem_algorithm}",
            "security_level": "MAX(classical, post-quantum)",
            "classical": "X25519",
            "post_quantum": self.hybrid.kem_algorithm,
            "quantum_safe": True,
            "backward_compatible": True,
            "peers_with_hybrid": len(self._peer_keys)
        }

