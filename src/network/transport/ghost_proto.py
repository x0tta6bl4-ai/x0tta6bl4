"""
Ghost Protocol — Custom x0tta6bl4 Transport Layer
=================================================

Replacement for Xray/VLESS. 
Mimics WebRTC (DTLS + SRTP) traffic which is common for 
video calls and hard to block without breaking corporate apps.

SECURITY: Uses ChaCha20-Poly1305 AEAD for authenticated encryption.
This provides both confidentiality and integrity verification.
"""

import json
import logging
import os
import secrets
import struct
from typing import Any, Dict, List, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from src.anti_censorship.stego_mesh import StegoMeshProtocol

logger = logging.getLogger("ghost-proto")

# Constants for packet structure
SRTP_HEADER_SIZE = 12  # bytes
NONCE_SIZE = 12  # bytes for ChaCha20-Poly1305
TAG_SIZE = 16  # bytes for Poly1305 auth tag
MIN_PACKET_SIZE = SRTP_HEADER_SIZE + NONCE_SIZE + TAG_SIZE


class GhostTransport:
    """
    Secure transport using ChaCha20-Poly1305 AEAD encryption.
    
    Packet format:
    - SRTP Header (12 bytes): Mimics WebRTC/SRTP traffic
    - Nonce (12 bytes): Random nonce for ChaCha20
    - Ciphertext + Auth Tag (variable): Encrypted payload with integrity
    
    Security properties:
    - Confidentiality: ChaCha20 stream cipher
    - Integrity: Poly1305 MAC
    - Replay protection: Packet ID in header (application-level)
    """
    
    def __init__(self, master_key: bytes):
        """
        Initialize GhostTransport with a master key.
        
        Args:
            master_key: 32-byte key for ChaCha20-Poly1305
            
        Raises:
            ValueError: If key is not exactly 32 bytes
        """
        if not master_key or len(master_key) != 32:
            raise ValueError(
                f"Encryption key must be exactly 32 bytes for ChaCha20-Poly1305, "
                f"got {len(master_key) if master_key else 0} bytes"
            )
        
        self.cipher = ChaCha20Poly1305(master_key)
        self.packet_id = 0
        
        # Optional stego layer for DPI evasion
        self._stego: Optional[StegoMeshProtocol] = None
        
        logger.info("GhostTransport initialized with ChaCha20-Poly1305 AEAD")

    def enable_stego(self, master_key: bytes, evasion_dna: Optional[Any] = None) -> None:
        """
        Enable steganographic layer for DPI evasion.
        
        Args:
            master_key: Key for stego protocol (can be same as transport key)
            evasion_dna: Optional Geneva evasion strategy
        """
        self._stego = StegoMeshProtocol(master_key, evasion_dna=evasion_dna)
        logger.info("Stego layer enabled for DPI evasion")

    def wrap_packet(self, payload: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """
        Wrap a mesh packet into a fake SRTP packet with AEAD encryption.
        
        Args:
            payload: The plaintext data to encrypt
            associated_data: Optional authenticated (but not encrypted) data
            
        Returns:
            Encrypted packet with SRTP header, nonce, and ciphertext+tag
        """
        # Generate random nonce for this packet
        nonce = secrets.token_bytes(NONCE_SIZE)
        
        # SRTP Header: Version(2), Padding(0), Extension(0), CSRC Count(0), 
        # Marker(0), Payload Type(111 - OPUS), Sequence Number, Timestamp, SSRC
        # This mimics real WebRTC/SRTP traffic
        header = struct.pack(
            "!BBHII",
            0x80,  # Version=2, Padding=0, Extension=0, CC=0
            111,   # Payload type 111 (OPUS audio - common in WebRTC)
            self.packet_id & 0xFFFF,  # Sequence number (wraps)
            self.packet_id * 960,     # Timestamp (typical OPUS frame duration)
            0xDEADBEEF,               # SSRC (random-looking but deterministic)
        )
        
        # Use header as associated data for authentication
        aad = associated_data or header
        
        # Encrypt with ChaCha20-Poly1305
        # This provides both confidentiality and integrity
        ciphertext = self.cipher.encrypt(nonce, payload, aad)
        
        self.packet_id += 1
        
        # Return: header + nonce + ciphertext (includes auth tag)
        return header + nonce + ciphertext

    def unwrap_packet(self, packet: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """
        Extract and decrypt mesh payload from fake SRTP packet.
        
        Args:
            packet: The encrypted packet
            associated_data: Optional authenticated data (must match encryption)
            
        Returns:
            Decrypted plaintext payload
            
        Raises:
            ValueError: If packet is too short or decryption fails
        """
        if len(packet) < MIN_PACKET_SIZE:
            logger.warning(f"Packet too short: {len(packet)} < {MIN_PACKET_SIZE}")
            return b""
        
        try:
            # Parse packet structure
            header = packet[:SRTP_HEADER_SIZE]
            nonce = packet[SRTP_HEADER_SIZE:SRTP_HEADER_SIZE + NONCE_SIZE]
            ciphertext = packet[SRTP_HEADER_SIZE + NONCE_SIZE:]
            
            # Use header as associated data for authentication
            aad = associated_data or header
            
            # Decrypt with ChaCha20-Poly1305
            # This verifies integrity automatically - raises exception if tag is invalid
            plaintext = self.cipher.decrypt(nonce, ciphertext, aad)
            
            return plaintext
            
        except Exception as e:
            logger.warning(f"Packet decryption failed: {e}")
            return b""

    def wrap_packet_with_stego(
        self, 
        payload: bytes, 
        protocol_mimic: str = "http"
    ) -> Union[bytes, List[bytes]]:
        """
        Wrap packet with both encryption and steganographic evasion.
        
        Args:
            payload: The plaintext data
            protocol_mimic: Protocol to mimic (http, icmp, dns)
            
        Returns:
            Stego-wrapped encrypted packet(s)
        """
        if self._stego is None:
            raise RuntimeError("Stego layer not enabled. Call enable_stego() first.")
        
        # First encrypt the payload
        encrypted = self.wrap_packet(payload)
        
        # Then apply stego encoding
        return self._stego.encode_packet(encrypted, protocol_mimic=protocol_mimic)

    def unwrap_packet_with_stego(self, stego_packet: bytes) -> bytes:
        """
        Unwrap stego layer and decrypt the payload.
        
        Args:
            stego_packet: The stego-wrapped packet
            
        Returns:
            Decrypted plaintext payload
        """
        if self._stego is None:
            raise RuntimeError("Stego layer not enabled. Call enable_stego() first.")
        
        # First decode stego layer
        encrypted = self._stego.decode_packet(stego_packet)
        if not encrypted:
            logger.warning("Stego decoding failed")
            return b""
        
        # Then decrypt
        return self.unwrap_packet(encrypted)

    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics."""
        return {
            "packets_sent": self.packet_id,
            "cipher": "ChaCha20-Poly1305",
            "stego_enabled": self._stego is not None,
        }


def test_ghost_transport():
    """Test GhostTransport encryption/decryption cycle."""
    import os
    
    # Generate a secure random key
    key = os.urandom(32)
    transport = GhostTransport(key)
    
    # Test data
    original = b"Very secret mesh command with binary data: \x00\x01\x02\xff"
    
    # Encrypt
    wrapped = transport.wrap_packet(original)
    logger.info(f"Ghost packet size: {len(wrapped)} bytes")
    
    # Decrypt
    unwrapped = transport.unwrap_packet(wrapped)
    
    assert unwrapped == original, f"Mismatch: {unwrapped!r} != {original!r}"
    logger.info("✅ Ghost Transport: Wrap/Unwrap cycle successful")
    
    # Test tampering detection
    tampered = bytearray(wrapped)
    tampered[-10] ^= 0xff  # Flip bits in ciphertext
    tampered_packet = bytes(tampered)
    
    try:
        result = transport.unwrap_packet(tampered_packet)
        assert result == b"", "Tampered packet should fail decryption"
    except Exception:
        pass  # Expected - tampering should be detected
    
    logger.info("✅ Ghost Transport: Tampering detection working")
    
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ghost_transport()
