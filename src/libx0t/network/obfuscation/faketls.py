"""
FakeTLS Transport for x0tta6bl4 Mesh.
Wraps traffic in realistic TLS 1.3 records to bypass DPI.
"""
from __future__ import annotations

import secrets
import socket
import struct

from .base import ObfuscationTransport


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

    def __init__(self, sni: str = "www.cloudflare.com"):
        # Default changed from google.com to cloudflare.com to avoid Google Cloud conflicts
        self.sni = sni.encode("utf-8")

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return FakeTLSSocket(sock, self)

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

        return record_header + full_handshake

    def obfuscate(self, data: bytes) -> bytes:
        """Wraps data in TLS 1.3 Application Data record."""
        if len(data) > 0xFFFF:
            raise ValueError("FakeTLS record payload exceeds 65535 bytes")
        length = len(data)
        header = struct.pack("!BHH", 0x17, 0x0303, length)
        return header + data

    def deobfuscate(self, data: bytes) -> bytes:
        """Unwrap an application-data TLS record or pass through raw payload."""
        if len(data) >= 5 and data[0] == 0x17:
            _content_type, _version, length = struct.unpack("!BHH", data[:5])
            if len(data) - 5 < length:
                raise ValueError("Incomplete FakeTLS application data record")
            return data[5 : 5 + length]
        return data

