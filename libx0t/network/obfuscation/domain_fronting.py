"""
Domain Fronting Transport for x0tta6bl4 Mesh.
Encapsulates traffic in HTTP/TLS requests to a CDN, hiding the true destination.
"""

import socket
import ssl
from typing import Optional

from .base import ObfuscationTransport


def _parse_content_length(headers: bytes) -> Optional[int]:
    for line in headers.split(b"\r\n"):
        if b":" not in line:
            continue
        name, value = line.split(b":", 1)
        if name.strip().lower() != b"content-length":
            continue
        try:
            return max(0, int(value.strip()))
        except ValueError:
            return None
    return None


def _extract_http_body(buffer: bytes) -> tuple[Optional[bytes], bytes]:
    header_end = buffer.find(b"\r\n\r\n")
    if header_end == -1:
        return None, buffer

    headers = buffer[:header_end]
    body_start = header_end + 4
    content_length = _parse_content_length(headers)
    if content_length is None:
        return buffer[body_start:], b""

    body_end = body_start + content_length
    if len(buffer) < body_end:
        return None, buffer
    return buffer[body_start:body_end], buffer[body_end:]


class DomainFrontingSocket(socket.socket):
    """
    Socket wrapper that performs Domain Fronting.
    1. Wraps connection in real TLS with 'front' SNI.
    2. Encapsulates writes in HTTP POST requests with 'backend' Host header.
    3. Decapsulates reads from HTTP Responses.
    """

    def __init__(
        self,
        sock: socket.socket,
        transport: "DomainFrontingTransport",
        tls_sock: socket.socket,
    ):
        self._raw_sock = sock
        self._tls_sock = tls_sock
        self._transport = transport
        self._buffer = b""

        try:
            super().__init__(fileno=sock.fileno())
        except Exception:
            pass
        self._timeout = sock.gettimeout()

    def settimeout(self, value: float | None) -> None:
        self._timeout = value
        self._tls_sock.settimeout(value)

    def gettimeout(self) -> float | None:
        return self._tls_sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        # Encapsulate in HTTP POST
        # Each send is framed as a discrete HTTP request for this transport mode.

        body = data
        headers = (
            f"POST /data HTTP/1.1\r\n"
            f"Host: {self._transport.backend_domain}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        ).encode("ascii")

        full_packet = headers + body

        # Send over TLS socket
        try:
            self._tls_sock.sendall(full_packet)
            return len(data)  # Return original length to satisfy socket interface
        except ssl.SSLError as e:
            # Handle TLS errors
            raise socket.error(f"TLS Error: {e}")

    def recv(self, bufsize: int, flags=0) -> bytes:
        # We need to read HTTP responses and extract body.
        # HTTP/1.1 200 OK ... \r\n\r\n[BODY]

        try:
            body, remaining = _extract_http_body(self._buffer)
            if body is not None:
                self._buffer = remaining
                return body

            # Read chunk from TLS
            chunk = self._tls_sock.recv(bufsize)
            if not chunk:
                return b""

            self._buffer += chunk

            body, remaining = _extract_http_body(self._buffer)
            if body is None:
                return b""
            self._buffer = remaining
            return body

        except ssl.SSLError as e:
            if e.errno == ssl.SSL_ERROR_WANT_READ:
                return b""
            raise socket.error(f"TLS Error: {e}")

    def close(self):
        self._tls_sock.close()

    def __getattr__(self, name):
        return getattr(self._tls_sock, name)


class DomainFrontingTransport(ObfuscationTransport):
    """
    Domain Fronting Transport.
    Connects via TLS to a CDN IP, but masquerades as a legit domain (SNI).
    The Host header targets the hidden backend.
    """

    def __init__(
        self,
        front_domain: str,
        backend_domain: str,
        ca_bundle: str | None = None,
        verify_certs: bool = True,
    ):
        self.front_domain = front_domain
        self.backend_domain = backend_domain
        if not verify_certs:
            raise ValueError(
                "verify_certs=False is not allowed for DomainFrontingTransport"
            )

        self.context = ssl.create_default_context()
        self.context.check_hostname = True
        self.context.verify_mode = ssl.CERT_REQUIRED
        if ca_bundle:
            self.context.load_verify_locations(ca_bundle)

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        # Wrap in real TLS with SNI = front_domain
        tls_sock = self.context.wrap_socket(
            sock, server_hostname=self.front_domain, do_handshake_on_connect=True
        )
        return DomainFrontingSocket(sock, self, tls_sock)

    def obfuscate(self, data: bytes) -> bytes:
        headers = (
            f"POST /data HTTP/1.1\r\n"
            f"Host: {self.backend_domain}\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"\r\n"
        ).encode("ascii")
        return headers + data

    def deobfuscate(self, data: bytes) -> bytes:
        # Strip headers
        if data.find(b"\r\n\r\n") != -1:
            body, _remaining = _extract_http_body(data)
            return body or b""
        return data
