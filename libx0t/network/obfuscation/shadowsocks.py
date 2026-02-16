"""
Shadowsocks Transport for x0tta6bl4 Mesh.
Implements a Shadowsocks-compatible obfuscation layer (AEAD ChaCha20-Poly1305).
"""

import logging
import os
import secrets
import socket
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .base import ObfuscationTransport

logger = logging.getLogger(__name__)


class ShadowsocksSocket(socket.socket):
    """Socket wrapper that applies Shadowsocks AEAD encryption."""

    def __init__(self, sock: socket.socket, transport: "ShadowsocksTransport"):
        self._sock = sock
        self._transport = transport
        self._salt_sent = False
        self._salt_received = False
        self._buffer = b""

        # ShadowsocksSocket acts as a wrapper, delegating all operations to self._sock.
        # It does NOT re-initialize super() with fileno.
        self._timeout = sock.gettimeout()

    def settimeout(self, value: float | None) -> None:
        self._timeout = value
        self._sock.settimeout(value)

    def gettimeout(self) -> float | None:
        return self._sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        # Track first-write state for compatibility with stream-oriented callers.
        if not self._salt_sent:
            self._session_salt = secrets.token_bytes(32)  # ChaCha20 salt size
            self._salt_sent = True

        # Stateless packet mode: each frame is independently obfuscated.
        encrypted_packet = self._transport.obfuscate(data)
        return self._sock.send(encrypted_packet, flags)

    def recv(self, bufsize: int, flags=0) -> bytes:
        # Read from socket
        data = self._sock.recv(bufsize, flags)
        if not data:
            return b""

        # Deobfuscate (expects Salt+Payload)
        try:
            return self._transport.deobfuscate(data)
        except Exception:
            return b""  # Decryption failed

    def __getattr__(self, name):
        return getattr(self._sock, name)


class ShadowsocksTransport(ObfuscationTransport):
    """
    Shadowsocks Transport (Simplified AEAD).
    Uses ChaCha20-Poly1305.
    Packet Format: [Salt (32)] [Nonce (12)] [Tag (16)] [Encrypted Payload]
    Note: This is a simplified variant for internal mesh usage, slightly different from standard SS
    to avoid implementing the full Chunk-based streaming state machine in Python.
    It treats every obfuscate() call as a discrete message.
    """

    def __init__(self, password: Optional[str] = None):
        # Get password from environment variable if not provided
        if password is None:
            password = os.getenv("X0TTA6BL4_SHADOWSOCKS_PASSWORD")
            if password is None:
                # Fallback to random password for security if not configured
                import secrets

                password = secrets.token_urlsafe(32)
                logger.warning(
                    "Using random Shadowsocks password - please set X0TTA6BL4_SHADOWSOCKS_PASSWORD for production"
                )

        self.password = password.encode("utf-8")
        # Pre-derive master key from password?
        # SS usually derives per-session key from (Master Key + Salt).
        # Master Key is derived from Password.
        self.master_key = self._kdf(self.password, b"ss-subkey", 32)

    def _kdf(self, key_material: bytes, salt: bytes, length: int) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            info=b"ss-subkey",
        )
        return hkdf.derive(key_material)

    def derive_session_key(self, salt: bytes) -> bytes:
        """Derive session key from master key and salt."""
        return self._kdf(self.master_key, salt, 32)

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return ShadowsocksSocket(sock, self)

    def obfuscate(self, data: bytes) -> bytes:
        """
        Encrypts data into a Shadowsocks-like packet.
        Format: [Salt 32] [Nonce 12] [Tag 16] [Ciphertext]
        """
        salt = secrets.token_bytes(32)
        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)

        nonce = secrets.token_bytes(12)

        # ChaCha20Poly1305 encrypt returns ciphertext + tag appended?
        # No, usually just ciphertext with tag.
        # cryptography's encrypt(nonce, data, aad) returns ciphertext + tag (16 bytes).
        ciphertext_with_tag = cipher.encrypt(nonce, data, None)

        return salt + nonce + ciphertext_with_tag

    def deobfuscate(self, data: bytes) -> bytes:
        """Decrypts packet."""
        if len(data) < (32 + 12 + 16):
            raise ValueError("Data too short for Shadowsocks packet")

        salt = data[:32]
        nonce = data[32:44]
        ciphertext_with_tag = data[44:]

        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)

        return cipher.decrypt(nonce, ciphertext_with_tag, None)
