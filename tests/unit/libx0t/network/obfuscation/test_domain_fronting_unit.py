import socket
import ssl
from unittest.mock import MagicMock

import pytest

from libx0t.network.obfuscation.domain_fronting import (
    DomainFrontingSocket,
    DomainFrontingTransport,
)


FRONT = "cdn.example.com"
BACKEND = "backend.mesh.local"


def test_deobfuscate_respects_content_length():
    transport = DomainFrontingTransport(FRONT, BACKEND)
    raw = (
        b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n"
        b"hello"
        b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nbye"
    )

    assert transport.deobfuscate(raw) == b"hello"


def test_deobfuscate_returns_empty_for_incomplete_body():
    transport = DomainFrontingTransport(FRONT, BACKEND)

    assert transport.deobfuscate(
        b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhe"
    ) == b""


def test_recv_waits_for_full_body_and_keeps_buffered_response():
    wrapped = DomainFrontingSocket.__new__(DomainFrontingSocket)
    wrapped._transport = DomainFrontingTransport(FRONT, BACKEND)
    wrapped._buffer = b""
    wrapped._raw_sock = MagicMock()
    wrapped._tls_sock = MagicMock()
    wrapped._tls_sock.recv.side_effect = [
        b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhe",
        b"lloHTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nbye",
    ]

    assert wrapped.recv(4096) == b""
    assert wrapped.recv(4096) == b"hello"
    assert wrapped.recv(4096) == b"bye"


def test_transport_rejects_disabled_certificate_verification():
    with pytest.raises(ValueError, match="verify_certs=False is not allowed"):
        DomainFrontingTransport(FRONT, BACKEND, verify_certs=False)


def test_recv_converts_non_want_read_ssl_error_to_socket_error():
    wrapped = DomainFrontingSocket.__new__(DomainFrontingSocket)
    wrapped._transport = DomainFrontingTransport(FRONT, BACKEND)
    wrapped._buffer = b""
    wrapped._raw_sock = MagicMock()
    wrapped._tls_sock = MagicMock()
    wrapped._tls_sock.recv.side_effect = ssl.SSLError(ssl.SSL_ERROR_SSL, "fail")

    with pytest.raises(socket.error, match="TLS Error"):
        wrapped.recv(1024)
