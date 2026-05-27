"""
Shadowsocks Transport for x0tta6bl4 Mesh.
Implements a Shadowsocks-compatible obfuscation layer (AEAD ChaCha20-Poly1305).
"""

import logging
import os
import secrets
import socket
import struct
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .base import ObfuscationTransport

logger = logging.getLogger(__name__)
_TRUE_VALUES = {"1", "true", "yes", "on"}
MAX_FRAME_SIZE = 16 * 1024 * 1024


def _production_mode_enabled() -> bool:
    return os.getenv("X0TTA6BL4_PRODUCTION", "false").strip().lower() in _TRUE_VALUES


class ShadowsocksSocket(socket.socket):
    """Socket wrapper that applies framed Shadowsocks AEAD packets."""

    def __init__(self, sock: socket.socket, transport: "ShadowsocksTransport"):
        self._sock = sock
        self._transport = transport
        self._buffer = b""

    def send(self, data: bytes, flags=0) -> int:
        frame = self._transport.frame(data)
        self._sock.sendall(frame)
        return len(data)

    def sendall(self, data: bytes, flags=0) -> None:
        self.send(data, flags)

    def recv(self, bufsize: int, flags=0) -> bytes:
        if self._buffer:
            out = self._buffer[:bufsize]
            self._buffer = self._buffer[bufsize:]
            return out

        try:
            packet = self._read_frame(flags)
            if packet is None:
                return b""
            plaintext = self._transport.deobfuscate(packet)
        except Exception:
            return b""  # Decryption failed

        out = plaintext[:bufsize]
        self._buffer = plaintext[bufsize:]
        return out

    def _recv_exact(self, length: int, flags=0) -> Optional[bytes]:
        chunks = []
        remaining = length
        while remaining > 0:
            chunk = self._sock.recv(remaining, flags)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_frame(self, flags=0) -> Optional[bytes]:
        header = self._recv_exact(4, flags)
        if header is None:
            return None
        frame_len = struct.unpack("!I", header)[0]
        if frame_len <= 0 or frame_len > MAX_FRAME_SIZE:
            raise ValueError("Invalid Shadowsocks frame size")
        return self._recv_exact(frame_len, flags)

    def close(self) -> None:
        self._sock.close()

    def fileno(self) -> int:
        return self._sock.fileno()

    def settimeout(self, value) -> None:
        self._sock.settimeout(value)

    def gettimeout(self):
        return self._sock.gettimeout()

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
                if _production_mode_enabled():
                    raise RuntimeError(
                        "X0TTA6BL4_SHADOWSOCKS_PASSWORD is required in production"
                    )
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
            algorithm=hashes.SHA1(),  # nosec B303
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

    def frame(self, data: bytes) -> bytes:
        """Encrypt and length-prefix one plaintext message for stream sockets."""
        packet = self.obfuscate(data)
        return struct.pack("!I", len(packet)) + packet

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
