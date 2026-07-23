"""
Security utilities for Mesh Router.

Provides HMAC-based packet authentication for secure mesh routing.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PacketSecurity:
    """
    Handles packet signing and verification using HMAC.
    
    Provides authentication for mesh routing packets to prevent
    spoofing and tampering attacks.
    
    Example:
        >>> security = PacketSecurity(shared_secret=b"secret_key")
        >>> signed = security.sign(packet_bytes)
        >>> verified = security.verify(signed)
        >>> assert verified == packet_bytes
    """

    HMAC_SIZE = 32  # SHA-256 produces 32 bytes

    def __init__(self, shared_secret: Optional[bytes] = None):
        """
        Initialize packet security.
        
        Args:
            shared_secret: HMAC key for packet authentication.
                          If None, packets are not signed/verified.
        """
        self._shared_secret = shared_secret

    @property
    def enabled(self) -> bool:
        """Check if security is enabled."""
        return self._shared_secret is not None

    def sign(self, data: bytes) -> bytes:
        """
        Append HMAC signature to packet data.
        
        Args:
            data: Raw packet bytes to sign
            
        Returns:
            Data with HMAC signature appended (or original if security disabled)
        """
        if not self._shared_secret:
            return data
        
        tag = hmac.new(self._shared_secret, data, hashlib.sha256).digest()
        return data + tag

    def verify(self, data: bytes) -> Optional[bytes]:
        """
        Verify and strip HMAC signature.
        
        Args:
            data: Signed packet bytes
            
        Returns:
            Original data without signature, or None if verification fails
        """
        if not self._shared_secret:
            return data
        
        if len(data) < self.HMAC_SIZE:
            logger.warning("Packet too short for HMAC verification")
            return None
        
        payload, tag = data[:-self.HMAC_SIZE], data[-self.HMAC_SIZE:]
        expected = hmac.new(self._shared_secret, payload, hashlib.sha256).digest()
        
        if not hmac.compare_digest(tag, expected):
            logger.warning("Packet HMAC verification failed — dropping")
            return None
        
        return payload

    def rotate_secret(self, new_secret: bytes) -> None:
        """
        Rotate the shared secret.
        
        Args:
            new_secret: New HMAC key
        """
        self._shared_secret = new_secret
        logger.info("Packet security secret rotated")


__all__ = ["PacketSecurity"]

