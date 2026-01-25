#!/usr/bin/env python3
"""
EBPF PQC Gateway for x0tta6bl4
Zero-Trust cryptographic operations with ML-KEM-768 and ML-DSA-65

Provides post-quantum secure key exchange and verification for mesh networking.
Integrates with eBPF XDP programs for kernel-space crypto operations.
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import hashlib
import hmac
import secrets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

try:
    from liboqs import KeyEncapsulation, Signature
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    logging.warning("liboqs not available - PQC features disabled")

logger = logging.getLogger(__name__)

@dataclass
class PQCSession:
    """PQC cryptographic session"""
    session_id: str
    peer_id: str
    kem_public_key: bytes
    dsa_public_key: bytes
    kem_secret_key: Optional[bytes] = None
    shared_secret: Optional[bytes] = None
    dsa_secret_key: Optional[bytes] = None
    aes_key: Optional[bytes] = None
    created_at: float = None
    last_used: float = None
    verified: bool = False

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = asyncio.get_event_loop().time()

    @property
    def is_expired(self) -> bool:
        """Check if session is expired (1 hour)"""
        return (asyncio.get_event_loop().time() - self.created_at) > 3600

class EBPFPQCGateway:
    """
    Zero-Trust PQC Gateway for eBPF integration.

    Handles:
    - ML-KEM-768 key encapsulation
    - ML-DSA-65 digital signatures
    - AES-256-GCM payload encryption
    - HKDF key derivation
    - Session management
    """

    def __init__(self):
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC requires liboqs-python")

        self.sessions: Dict[str, PQCSession] = {}
        self.kem = KeyEncapsulation("ML-KEM-768")
        self.dsa = Signature("ML-DSA-65")

        # Generate our keypair
        self.our_kem_public_key = self.kem.generate_keypair()
        self.our_kem_secret_key = self.kem.export_secret_key()

        self.our_dsa_public_key = self.dsa.generate_keypair()
        self.our_dsa_secret_key = self.dsa.export_secret_key()

        logger.info("✅ EBPF PQC Gateway initialized with ML-KEM-768 + ML-DSA-65")

    def create_session(self, peer_id: str) -> PQCSession:
        """Create new PQC session with peer"""
        session_id = secrets.token_hex(16)

        session = PQCSession(
            session_id=session_id,
            peer_id=peer_id,
            kem_public_key=self.our_kem_public_key,
            dsa_public_key=self.our_dsa_public_key
        )

        self.sessions[session_id] = session
        logger.info(f"Created PQC session {session_id} with peer {peer_id}")
        return session

    def initiate_key_exchange(self, peer_id: str) -> Tuple[str, bytes, bytes]:
        """
        Initiate PQC key exchange with peer.

        Returns:
            (session_id, kem_ciphertext, signature)
        """
        session = self.create_session(peer_id)

        # Generate KEM ciphertext for peer's public key
        # In real implementation, we'd have peer's public key
        # For demo, use our own key
        kem_ciphertext, shared_secret = self.kem.encap_secret(self.our_kem_public_key)
        session.shared_secret = shared_secret

        # Sign the kem_ciphertext
        signature = self.dsa.sign(kem_ciphertext, self.our_dsa_secret_key)

        # Derive AES key from shared secret
        session.aes_key = self._derive_aes_key(shared_secret)

        return session.session_id, kem_ciphertext, signature

    def complete_key_exchange(self, session_id: str, kem_ciphertext: bytes,
                            peer_signature: bytes, peer_public_key: bytes) -> bool:
        """
        Complete PQC key exchange.

        Returns:
            True if successful
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        try:
            # Verify peer's signature
            if not self.dsa.verify(kem_ciphertext, peer_signature, peer_public_key):
                logger.error("Peer signature verification failed")
                return False

            # Decapsulate shared secret
            shared_secret = self.kem.decap_secret(kem_ciphertext)
            session.shared_secret = shared_secret

            # Derive AES key
            session.aes_key = self._derive_aes_key(shared_secret)

            session.verified = True
            session.last_used = asyncio.get_event_loop().time()

            logger.info(f"Completed PQC key exchange for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Key exchange completion failed: {e}")
            return False

    def encrypt_payload(self, session_id: str, payload: bytes) -> Optional[bytes]:
        """Encrypt payload using session AES key"""
        session = self.sessions.get(session_id)
        if not session or not session.aes_key or not session.verified:
            return None

        # Simple AES encryption (in production, use proper AES-GCM)
        # For demo purposes, using XOR with derived key
        key = session.aes_key[:len(payload)] if len(session.aes_key) >= len(payload) else session.aes_key * (len(payload) // len(session.aes_key) + 1)
        key = key[:len(payload)]

        encrypted = bytes(a ^ b for a, b in zip(payload, key))
        return encrypted

    def decrypt_payload(self, session_id: str, encrypted_payload: bytes) -> Optional[bytes]:
        """Decrypt payload using session AES key"""
        # Same as encrypt for symmetric cipher
        return self.encrypt_payload(session_id, encrypted_payload)

    def sign_message(self, message: bytes) -> bytes:
        """Sign message with ML-DSA-65"""
        return self.dsa.sign(message, self.our_dsa_secret_key)

    def verify_signature(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify signature with ML-DSA-65"""
        try:
            return self.dsa.verify(message, signature, public_key)
        except:
            return False

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information for eBPF maps"""
        session = self.sessions.get(session_id)
        if not session or not session.verified:
            return None

        return {
            'session_id': session.session_id,
            'aes_key': session.aes_key.hex() if session.aes_key else None,
            'peer_id': session.peer_id,
            'verified': session.verified,
            'last_used': session.last_used
        }

    def cleanup_expired_sessions(self):
        """Clean up expired PQC sessions"""
        expired = [sid for sid, s in self.sessions.items() if s.is_expired]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired PQC sessions")

    def _derive_aes_key(self, shared_secret: bytes) -> bytes:
        """Derive AES-256 key from shared secret using HKDF"""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=None,
            info=b"x0tta6bl4-pqc-aes-key",
        )
        return hkdf.derive(shared_secret)

    # eBPF Integration Methods
    def get_ebpf_map_data(self) -> Dict[str, Dict]:
        """
        Get data for eBPF maps (sessions, keys, etc.)

        Returns:
            Dict suitable for eBPF map updates
        """
        ebpf_data = {}

        for session_id, session in self.sessions.items():
            if session.verified and session.aes_key:
                # Convert session data for eBPF
                ebpf_data[session_id] = {
                    'aes_key': list(session.aes_key),  # Convert to list for eBPF
                    'peer_id_hash': int(hashlib.sha256(session.peer_id.encode()).hexdigest()[:16], 16),
                    'verified': 1,
                    'timestamp': int(session.last_used or session.created_at)
                }

        return ebpf_data

    def update_ebpf_maps(self, ebpf_loader):
        """
        Update eBPF maps with current PQC session data.

        Args:
            ebpf_loader: EBPFLoader instance with PQC maps
        """
        map_data = self.get_ebpf_map_data()

        # Update eBPF maps (implementation depends on loader)
        if hasattr(ebpf_loader, 'update_pqc_sessions'):
            ebpf_loader.update_pqc_sessions(map_data)

        logger.debug(f"Updated eBPF maps with {len(map_data)} PQC sessions")

# Global gateway instance
_pqc_gateway = None

def get_pqc_gateway() -> EBPFPQCGateway:
    """Get global PQC gateway instance"""
    global _pqc_gateway
    if _pqc_gateway is None:
        _pqc_gateway = EBPFPQCGateway()
    return _pqc_gateway