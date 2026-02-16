"""
Domain Fronting Transport for x0tta6bl4 Mesh.
Encapsulates traffic in HTTP/TLS requests to a CDN, hiding the true destination.
"""

import socket
import ssl
from typing import Optional

from .base import ObfuscationTransport


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
        self.timeout = sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        # Encapsulate in HTTP POST
        # Note: In a real streaming scenario, we might use WebSocket or Chunked encoding.
        # For this MVP, we wrap each send in a discrete HTTP request (REST-like).

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

        # This is a simplified parser for MVP.
        # It assumes the peer sends standard responses.

        try:
            # Read chunk from TLS
            chunk = self._tls_sock.recv(bufsize)
            if not chunk:
                return b""

            self._buffer += chunk

            # Try to find end of headers
            header_end = self._buffer.find(b"\r\n\r\n")
            if header_end != -1:
                # We have headers
                body_start = header_end + 4
                # Parse Content-Length?
                # For MVP we might assume the rest of the buffer is body
                # Real impl needs a state machine.

                # Let's extract what we can
                data = self._buffer[body_start:]
                self._buffer = (
                    b""  # Consume all (assuming 1 req = 1 resp for this transport mode)
                )
                return data

            return b""  # Need more data

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

    def __init__(self, front_domain: str, backend_domain: str):
        self.front_domain = front_domain
        self.backend_domain = backend_domain

        # Setup SSL Context
        self.context = ssl.create_default_context()
        self.context.check_hostname = False  # We are fronting, hostname won't match IP
        self.context.verify_mode = ssl.CERT_NONE  # For MVP/Self-signed mesh

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        # Wrap in real TLS with SNI = front_domain
        tls_sock = self.context.wrap_socket(
            sock, server_hostname=self.front_domain, do_handshake_on_connect=True
        )
        return DomainFrontingSocket(sock, self, tls_sock)

    def obfuscate(self, data: bytes) -> bytes:
        # This transport is stateful (socket wrapper), obfuscate/deobfuscate are mainly for stateless packet modes.
        # If used statelessly (e.g. UDP), we can just frame it in HTTP bytes without TLS?
        # Or assume the caller handles the TLS tunnel.
        # Let's return the HTTP frame.

        headers = (
            f"POST /data HTTP/1.1\r\n"
            f"Host: {self.backend_domain}\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"\r\n"
        ).encode("ascii")
        return headers + data

    def deobfuscate(self, data: bytes) -> bytes:
        # Strip headers
        header_end = data.find(b"\r\n\r\n")
        if header_end != -1:
            return data[header_end + 4 :]
        return data
