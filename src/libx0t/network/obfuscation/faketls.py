"""
FakeTLS Transport for x0tta6bl4 Mesh.
Wraps traffic in realistic TLS 1.3 records to bypass DPI.
"""

import os
import secrets
import socket
import struct
from typing import Optional

from .base import ObfuscationTransport


class FakeTLSSocket(socket.socket):
    """Socket wrapper that wraps data in TLS Application Data records."""

    def __init__(self, sock: socket.socket, transport: "FakeTLSTransport"):
        self._sock = sock
        self._transport = transport
        self._handshake_sent = False
        self._handshake_received = False

        try:
            super().__init__(fileno=sock.fileno())
        except Exception:
            pass
        self.timeout = sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        if not self._handshake_sent:
            # In a real implementation, we would send ClientHello here
            # For this basic version, we assume the 'obfuscate' method handles packet format
            # But 'obfuscate' is stateless.
            # We need to send ClientHello prefix if this is the start of stream.
            client_hello = self._transport.generate_client_hello()
            self._sock.send(client_hello, flags)
            self._handshake_sent = True

        # Wrap actual data in TLS Application Data record
        encrypted_record = self._transport.obfuscate(data)
        return self._sock.send(encrypted_record, flags)

    def recv(self, bufsize: int, flags=0) -> bytes:
        # Simplified recv: read header, then body
        # Real implementation needs buffering because TCP stream doesn't guarantee packet boundaries

        if not self._handshake_received:
            # Swallow ServerHello
            # In this simplified fake transport, we assume the peer sends a ServerHello
            # that we need to discard.
            # Read 5 byte header
            header = self._sock.recv(5, flags)
            if not header:
                return b""
            content_type, version, length = struct.unpack("!BHH", header)

            if content_type == 0x16:  # Handshake
                # Read body and ignore
                _ = self._sock.recv(length, flags)
                self._handshake_received = True
            else:
                # Maybe we missed it or it wasn't sent, put back?
                # For now assume protocol strictness
                pass

        # Read App Data Header
        header = self._sock.recv(5, flags)
        if not header:
            return b""
        content_type, version, length = struct.unpack("!BHH", header)

        if content_type == 0x17:  # Application Data
            data = self._sock.recv(length, flags)
            return self._transport.deobfuscate(data)

        return b""

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

    def __init__(self, sni: str = "www.cloudflare.com"):
        # Default changed from google.com to cloudflare.com to avoid Google Cloud conflicts
        self.sni = sni.encode("utf-8")

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return FakeTLSSocket(sock, self)

    def generate_client_hello(self) -> bytes:
        """Generates a realistic TLS 1.3 ClientHello."""
        # 1. TLS Record Header
        # Content Type: Handshake (22)
        # Version: TLS 1.0 (0x0301) for compatibility or 1.2 (0x0303)
        # Length: TBD

        # 2. Handshake Header
        # Type: ClientHello (1)
        # Length: TBD

        # 3. ClientHello Body
        # Legacy Version: 0x0303 (TLS 1.2)
        # Random: 32 bytes
        # Session ID: 32 bytes random (or 0 length)
        # Cipher Suites: e.g. TLS_AES_128_GCM_SHA256 (0x1301) etc.
        # Compression: 0x00 (Null)
        # Extensions

        # Construct Extensions
        extensions = b""

        # SNI Extension
        # Type (0x0000), Length, List Length, Name Type (0 host_name), Name Length, Name
        sni_len = len(self.sni)
        sni_ext = (
            struct.pack("!HHBH", 0x0000, sni_len + 5, sni_len + 3, 0x00)
            + struct.pack("!H", sni_len)
            + self.sni
        )
        extensions += sni_ext

        # Supported Versions (TLS 1.3)
        # Type (0x002b), Length, List Length, TLS 1.3 (0x0304)
        sup_ver_ext = struct.pack("!HHBH", 0x002B, 3, 2, 0x0304)
        extensions += sup_ver_ext

        # Key Share (Dummy)
        # Type (0x0033) ...
        # Simplified for brevity, using just SNI and Supported Versions for MVP

        # Construct ClientHello Body
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

        return record_header + full_handshake

    def obfuscate(self, data: bytes) -> bytes:
        """Wraps data in TLS 1.3 Application Data record."""
        # Content Type: Application Data (23)
        # Version: TLS 1.2 (0x0303) - standard for TLS 1.3 records
        # Length
        length = len(data)
        header = struct.pack("!BHH", 0x17, 0x0303, length)
        return header + data

    def deobfuscate(self, data: bytes) -> bytes:
        """Unwraps data (assumes header was already stripped by socket recv logic)."""
        # Since `recv` logic in FakeTLSSocket handles stripping,
        # this method might just return data if passed raw payload.
        # However, if passed full record:
        if len(data) > 5 and data[0] == 0x17:
            return data[5:]
        return data
