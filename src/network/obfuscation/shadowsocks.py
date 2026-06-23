"""
Shadowsocks Transport for x0tta6bl4 Mesh.
Implements a Shadowsocks-compatible obfuscation layer (AEAD ChaCha20-Poly1305).
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import socket
import struct
import time
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity
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

    def __init__(
        self,
        password: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        password_source = "argument" if password is not None else "environment_or_generated"
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
                password_source = "generated"
            else:
                password_source = "environment"

        self.password = password.encode("utf-8")
        self.password_source = password_source
        # Pre-derive master key from password?
        # SS usually derives per-session key from (Master Key + Salt).
        # Master Key is derived from Password.
        self.master_key = self._kdf(self.password, b"ss-subkey", 32)

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize Shadowsocks EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _key_metadata(self) -> Dict[str, Any]:
        return {
            "password_present": bool(self.password),
            "password_source": self.password_source,
            "password_length_bucket": _byte_count_bucket(len(self.password)),
            "master_key_present": bool(self.master_key),
            "master_key_length_bucket": _byte_count_bucket(len(self.master_key)),
            "raw_password_redacted": True,
            "raw_keys_redacted": True,
        }

    def _publish_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.obfuscation.shadowsocks",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "key_material": self._key_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
            "raw_keys_redacted": True,
            "crypto_material_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": SHADOWSOCKS_TRANSPORT_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value == "failed"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish Shadowsocks evidence: %s", exc)
            return None

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
        started_at = time.monotonic()
        wrapped = ShadowsocksSocket(sock, self)
        self._publish_evidence(
            operation="wrap_socket",
            status_value="wrapped",
            started_at=started_at,
            metadata={
                "socket": {
                    "fileno_present": hasattr(sock, "fileno"),
                    "raw_peer_redacted": True,
                },
            },
        )
        return wrapped

    def frame(self, data: bytes) -> bytes:
        """Encrypt and length-prefix one plaintext message for stream sockets."""
        started_at = time.monotonic()
        packet = self.obfuscate(data)
        frame = struct.pack("!I", len(packet)) + packet
        self._publish_evidence(
            operation="frame",
            status_value="framed",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "packet_bytes_bucket": _byte_count_bucket(len(packet)),
                "frame_bytes_bucket": _byte_count_bucket(len(frame)),
                "length_prefix_present": True,
            },
        )
        return frame

    def frame(self, data: bytes) -> bytes:
        """Encrypt and length-prefix one plaintext message for stream sockets."""
        packet = self.obfuscate(data)
        return struct.pack("!I", len(packet)) + packet

    def obfuscate(self, data: bytes) -> bytes:
        """
        Encrypts data into a Shadowsocks-like packet.
        Format: [Salt 32] [Nonce 12] [Tag 16] [Ciphertext]
        """
        started_at = time.monotonic()
        salt = secrets.token_bytes(32)
        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)

        nonce = secrets.token_bytes(12)

        # ChaCha20Poly1305 encrypt returns ciphertext + tag appended?
        # No, usually just ciphertext with tag.
        # cryptography's encrypt(nonce, data, aad) returns ciphertext + tag (16 bytes).
        ciphertext_with_tag = cipher.encrypt(nonce, data, None)

        packet = salt + nonce + ciphertext_with_tag
        self._publish_evidence(
            operation="obfuscate",
            status_value="encrypted",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "output_bytes_bucket": _byte_count_bucket(len(packet)),
                "crypto": {
                    "salt_present": True,
                    "nonce_present": True,
                    "tag_present": True,
                    "cipher": "chacha20_poly1305",
                    "raw_crypto_material_redacted": True,
                },
            },
        )
        return packet

    def deobfuscate(self, data: bytes) -> bytes:
        """Decrypts packet."""
        started_at = time.monotonic()
        if len(data) < (32 + 12 + 16):
            self._publish_evidence(
                operation="deobfuscate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "crypto": {
                        "packet_too_short": True,
                        "raw_crypto_material_redacted": True,
                    },
                },
                error_type="ValueError",
            )
            raise ValueError("Data too short for Shadowsocks packet")

        salt = data[:32]
        nonce = data[32:44]
        ciphertext_with_tag = data[44:]

        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)

        try:
            plaintext = cipher.decrypt(nonce, ciphertext_with_tag, None)
        except Exception as exc:
            self._publish_evidence(
                operation="deobfuscate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "crypto": {
                        "packet_too_short": False,
                        "salt_present": True,
                        "nonce_present": True,
                        "tag_present": len(ciphertext_with_tag) >= 16,
                        "raw_crypto_material_redacted": True,
                    },
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="deobfuscate",
            status_value="decrypted",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "output_bytes_bucket": _byte_count_bucket(len(plaintext)),
                "crypto": {
                    "salt_present": True,
                    "nonce_present": True,
                    "tag_present": True,
                    "raw_crypto_material_redacted": True,
                },
            },
        )
        return plaintext
