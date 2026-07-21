"""
FakeTLS Transport for x0tta6bl4 Mesh.
Wraps traffic in TLS-looking records.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import socket
import struct
import time
from typing import Any, Dict, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity
from .base import ObfuscationTransport

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "faketls-transport"
_SERVICE_LAYER = "network_faketls_transport_local_evidence"
FAKETLS_TRANSPORT_CLAIM_BOUNDARY = (
    "Local FakeTLS record wrapping evidence only. It records local TLS-looking "
    "record generation/parsing metadata, byte-count buckets, duration, SNI "
    "presence/hash, and redacted service identity presence; it does not expose "
    "payload bytes, raw SNI values, socket peer addresses, or prove DPI bypass, "
    "censorship bypass, remote reachability, packet delivery, anonymity, "
    "provider health, client installation, or production customer traffic use."
)


def _sha256_prefix(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _byte_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value <= 64:
        return "tiny"
    if value <= 512:
        return "small"
    if value <= 1500:
        return "mtu"
    if value <= 8192:
        return "chunk"
    if value <= 0xFFFF:
        return "large_record"
    return "too_large"


class FakeTLSSocket(socket.socket):
    """Socket wrapper that wraps data in TLS Application Data records."""

    def __init__(self, sock: socket.socket, transport: "FakeTLSTransport"):
        self._sock = sock
        self._transport = transport
        self._handshake_sent = False
        self._handshake_received = False
        self._buffer = b""

    def fileno(self) -> int:
        return self._sock.fileno()

    def settimeout(self, value: float | None) -> None:
        self._sock.settimeout(value)

    def gettimeout(self) -> float | None:
        return self._sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        if not self._handshake_sent:
            client_hello = self._transport.generate_client_hello()
            self._sock.sendall(client_hello)
            self._handshake_sent = True

        encrypted_record = self._transport.obfuscate(data)
        self._sock.sendall(encrypted_record)
        return len(data)

    def sendall(self, data: bytes, flags=0) -> None:
        self.send(data, flags)

    def recv(self, bufsize: int, flags=0) -> bytes:
        buffer = self.__dict__.get("_buffer", b"")
        if buffer:
            out = buffer[:bufsize]
            self._buffer = buffer[bufsize:]
            return out

        while True:
            record = self._read_record(flags)
            if record is None:
                return b""
            content_type = record[0]
            if content_type == 0x16 and not self._handshake_received:
                self._handshake_received = True
                continue
            if content_type != 0x17:
                return b""

            plaintext = self._transport.deobfuscate(record)
            out = plaintext[:bufsize]
            self._buffer = plaintext[bufsize:]
            return out

    def _recv_exact(self, length: int, flags=0) -> bytes | None:
        chunks = []
        remaining = length
        while remaining > 0:
            chunk = self._sock.recv(remaining, flags)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_record(self, flags=0) -> bytes | None:
        header = self._recv_exact(5, flags)
        if header is None:
            return None
        _content_type, _version, length = struct.unpack("!BHH", header)
        body = self._recv_exact(length, flags)
        if body is None:
            return None
        return header + body

    def close(self) -> None:
        self._sock.close()

    def __getattr__(self, name):
        return getattr(self._sock, name)


class FakeTLSTransport(ObfuscationTransport):
    """
    FakeTLS Transport.
    Wraps packets in TLS 1.3 headers.

    Note: This does NOT provide encryption! It relies on the underlying
    protocol (e.g. Yggdrasil/Batman) being already encrypted.
    It only provides obfuscation against DPI.
    """

    def __init__(
        self,
        sni: str = "www.cloudflare.com",
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        # Default changed from google.com to cloudflare.com to avoid Google Cloud conflicts
        self.sni = sni.encode("utf-8")
        self.event_bus = event_bus
        self.event_project_root = event_project_root

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize FakeTLS EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _sni_metadata(self) -> Dict[str, Any]:
        sni_text = self.sni.decode("utf-8", errors="replace")
        return {
            "present": bool(self.sni),
            "length_bucket": _byte_count_bucket(len(self.sni)),
            "hash": _sha256_prefix(sni_text),
            "raw_sni_redacted": True,
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
            "component": "network.obfuscation.faketls",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "sni": self._sni_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
            "raw_parameters_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": FAKETLS_TRANSPORT_CLAIM_BOUNDARY,
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
            logger.error("Failed to publish FakeTLS evidence: %s", exc)
            return None

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        started_at = time.monotonic()
        wrapped = FakeTLSSocket(sock, self)
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

    def _extension(self, extension_type: int, body: bytes) -> bytes:
        return struct.pack("!HH", extension_type, len(body)) + body

    def _extension(self, extension_type: int, body: bytes) -> bytes:
        return struct.pack("!HH", extension_type, len(body)) + body

    def generate_client_hello(self) -> bytes:
        """Generates a realistic TLS 1.3 ClientHello."""
        extensions = b""

        sni_len = len(self.sni)
        sni_body = (
            struct.pack("!H", sni_len + 3)
            + b"\x00"
            + struct.pack("!H", sni_len)
            + self.sni
        )
        extensions += self._extension(0x0000, sni_body)

        extensions += self._extension(0x002B, b"\x02\x03\x04")

        supported_groups = struct.pack("!H", 4) + struct.pack("!HH", 0x001D, 0x0017)
        extensions += self._extension(0x000A, supported_groups)

        key_share_entry = struct.pack("!HH", 0x001D, 32) + secrets.token_bytes(32)
        key_share_body = struct.pack("!H", len(key_share_entry)) + key_share_entry
        extensions += self._extension(0x0033, key_share_body)

        sig_algs = struct.pack("!H", 6) + struct.pack("!HHH", 0x0403, 0x0804, 0x0807)
        extensions += self._extension(0x000D, sig_algs)

        alpn_names = b"\x02h2\x08http/1.1"
        alpn_body = struct.pack("!H", len(alpn_names)) + alpn_names
        extensions += self._extension(0x0010, alpn_body)

        random_bytes = secrets.token_bytes(32)
        session_id = secrets.token_bytes(32)
        cipher_suites = b"\x13\x01\x13\x02\x13\x03\xc0\x2b\xc0\x2f\xcc\xa9\xcc\xa8"
        compression = b"\x00"

        handshake_body = (
            struct.pack("!H", 0x0303)
            + random_bytes
            + struct.pack("B", 32)
            + session_id
            + struct.pack("!H", len(cipher_suites))
            + cipher_suites
            + struct.pack("B", 1)
            + compression
            + struct.pack("!H", len(extensions))
            + extensions
        )

        # Handshake Header
        handshake_header = (
            struct.pack("!B", 0x01) + struct.pack("!I", len(handshake_body))[1:]
        )  # 3 bytes length

        full_handshake = handshake_header + handshake_body

        # Record Header
        record_header = struct.pack("!BHH", 0x16, 0x0301, len(full_handshake))

        hello = record_header + full_handshake
        self._publish_evidence(
            operation="generate_client_hello",
            status_value="generated",
            started_at=started_at,
            metadata={
                "record": {
                    "content_type": "handshake",
                    "output_bytes_bucket": _byte_count_bucket(len(hello)),
                    "extensions_present": True,
                    "random_fields_present": True,
                    "raw_record_redacted": True,
                },
            },
        )
        return hello

    def obfuscate(self, data: bytes) -> bytes:
        """Wraps data in TLS 1.3 Application Data record."""
        if len(data) > 0xFFFF:
            raise ValueError("FakeTLS record payload exceeds 65535 bytes")
        length = len(data)
        header = struct.pack("!BHH", 0x17, 0x0303, length)
        record = header + data
        self._publish_evidence(
            operation="obfuscate",
            status_value="wrapped",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "output_bytes_bucket": _byte_count_bucket(len(record)),
                "record": {
                    "content_type": "application_data",
                    "legacy_version": "tls12",
                    "raw_record_redacted": True,
                },
            },
        )
        return record

    def deobfuscate(self, data: bytes) -> bytes:
        """Unwrap an application-data TLS record or pass through raw payload."""
        if len(data) >= 5 and data[0] == 0x17:
            _content_type, _version, length = struct.unpack("!BHH", data[:5])
            if len(data) - 5 < length:
                raise ValueError("Incomplete FakeTLS application data record")
            return data[5 : 5 + length]
        return data
