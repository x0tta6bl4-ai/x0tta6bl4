"""Unit tests for src.network.obfuscation.domain_fronting module.

Tests HTTP-based obfuscation/deobfuscation and domain fronting transport.
"""

import os
import socket
import ssl
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

from src.network.obfuscation.domain_fronting import (DomainFrontingSocket,
                                                     DomainFrontingTransport)

FRONT = "cdn.example.com"
BACKEND = "secret-backend.mesh.local"


# ===========================================================================
# TestDomainFrontingTransportInit
# ===========================================================================


class TestDomainFrontingTransportInit:

    def test_stores_domains(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        assert t.front_domain == FRONT
        assert t.backend_domain == BACKEND

    def test_creates_ssl_context(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        assert isinstance(t.context, ssl.SSLContext)

    def test_ssl_context_disables_hostname_check(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        assert t.context.check_hostname is False
        assert t.context.verify_mode == ssl.CERT_NONE


# ===========================================================================
# TestObfuscate
# ===========================================================================


class TestObfuscate:

    def setup_method(self):
        self.t = DomainFrontingTransport(FRONT, BACKEND)

    def test_starts_with_post_request_line(self):
        out = self.t.obfuscate(b"data")
        assert out.startswith(b"POST /data HTTP/1.1\r\n")

    def test_contains_host_header_with_backend(self):
        out = self.t.obfuscate(b"data")
        assert f"Host: {BACKEND}\r\n".encode() in out

    def test_contains_content_length(self):
        data = b"hello world"
        out = self.t.obfuscate(data)
        assert f"Content-Length: {len(data)}\r\n".encode() in out

    def test_ends_with_original_data(self):
        data = b"my payload bytes"
        out = self.t.obfuscate(data)
        assert out.endswith(data)

    def test_headers_and_body_separated_by_crlf_crlf(self):
        data = b"payload"
        out = self.t.obfuscate(data)
        header_end = out.find(b"\r\n\r\n")
        assert header_end > 0
        body = out[header_end + 4 :]
        assert body == data


# ===========================================================================
# TestDeobfuscate
# ===========================================================================


class TestDeobfuscate:

    def setup_method(self):
        self.t = DomainFrontingTransport(FRONT, BACKEND)

    def test_strips_http_headers_returns_body(self):
        raw = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"
        assert self.t.deobfuscate(raw) == b"hello"

    def test_returns_data_as_is_when_no_separator(self):
        raw = b"no headers here"
        assert self.t.deobfuscate(raw) == raw

    def test_works_with_response_like_data(self):
        body = b'{"status":"ok"}'
        raw = b"HTTP/1.1 200 OK\r\nServer: nginx\r\n\r\n" + body
        assert self.t.deobfuscate(raw) == body

    def test_handles_empty_body_after_headers(self):
        raw = b"HTTP/1.1 204 No Content\r\n\r\n"
        assert self.t.deobfuscate(raw) == b""


# ===========================================================================
# TestObfuscateDeobfuscateRoundTrip
# ===========================================================================


class TestObfuscateDeobfuscateRoundTrip:

    def setup_method(self):
        self.t = DomainFrontingTransport(FRONT, BACKEND)

    def test_roundtrip_short_data(self):
        data = b"short"
        assert self.t.deobfuscate(self.t.obfuscate(data)) == data

    def test_roundtrip_binary_data(self):
        data = bytes(range(256))
        assert self.t.deobfuscate(self.t.obfuscate(data)) == data

    def test_roundtrip_large_data(self):
        data = os.urandom(5000)
        assert self.t.deobfuscate(self.t.obfuscate(data)) == data


# ===========================================================================
# TestWrapSocket
# ===========================================================================


class TestWrapSocket:
    """Test wrap_socket method.

    Note: DomainFrontingSocket.__init__ has the same C-level ``timeout``
    read-only descriptor issue as FakeTLSSocket. We test via ssl context
    mock and verify the call without fully constructing the socket.
    """

    def test_wrap_socket_calls_ssl_context(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        mock_sock = MagicMock()
        mock_tls_sock = MagicMock()
        t.context = MagicMock()
        t.context.wrap_socket.return_value = mock_tls_sock

        # The DomainFrontingSocket init will fail on self.timeout, but
        # we can verify that ssl wrap_socket was called correctly.
        try:
            t.wrap_socket(mock_sock)
        except AttributeError:
            pass  # Expected: C-level timeout is not writable

        t.context.wrap_socket.assert_called_once_with(
            mock_sock,
            server_hostname=FRONT,
            do_handshake_on_connect=True,
        )

    def test_transport_has_callable_wrap_socket(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        assert callable(t.wrap_socket)


# ===========================================================================
# TestDomainFrontingSocket
# ===========================================================================


class TestDomainFrontingSocket:

    def test_is_subclass_of_socket(self):
        assert issubclass(DomainFrontingSocket, socket.socket)

    def test_transport_has_wrap_socket_method(self):
        t = DomainFrontingTransport(FRONT, BACKEND)
        assert callable(getattr(t, "wrap_socket", None))

    def test_transport_extends_obfuscation_base(self):
        from src.network.obfuscation.base import ObfuscationTransport

        assert issubclass(DomainFrontingTransport, ObfuscationTransport)

    def test_socket_init_hits_timeout_attribute_error(self):
        raw_a, raw_b = socket.socketpair()
        tls_sock = MagicMock()
        try:
            with pytest.raises(AttributeError):
                DomainFrontingSocket(raw_a, DomainFrontingTransport(FRONT, BACKEND), tls_sock)
        finally:
            try:
                raw_a.close()
            except OSError:
                pass  # fd taken by DomainFrontingSocket.__init__ via super().__init__(fileno=...)
            try:
                raw_b.close()
            except OSError:
                pass

    def test_send_success_and_tls_error(self):
        wrapped = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped._buffer = b""
        wrapped._raw_sock = MagicMock()
        wrapped._tls_sock = MagicMock()

        payload = b"secret-data"
        sent_len = wrapped.send(payload)
        assert sent_len == len(payload)
        wrapped._tls_sock.sendall.assert_called_once()

        wrapped_err = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped_err._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped_err._buffer = b""
        wrapped_err._raw_sock = MagicMock()
        wrapped_err._tls_sock = MagicMock()
        wrapped_err._tls_sock.sendall.side_effect = ssl.SSLError("bad tls")
        with pytest.raises(socket.error, match="TLS Error"):
            wrapped_err.send(b"x")

    def test_recv_parser_variants(self):
        wrapped = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped._buffer = b""
        wrapped._raw_sock = MagicMock()
        wrapped._tls_sock = MagicMock()
        wrapped._tls_sock.recv.side_effect = [
            b"",
            b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc",
            b"HTTP/1.1 200 OK\r\nContent-Length: 3",
        ]

        assert wrapped.recv(4096) == b""
        assert wrapped.recv(4096) == b"abc"
        assert wrapped.recv(4096) == b""

    def test_recv_ssl_want_read_and_other_ssl_error(self):
        wrapped_want = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped_want._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped_want._buffer = b""
        wrapped_want._raw_sock = MagicMock()
        wrapped_want._tls_sock = MagicMock()
        want_read = ssl.SSLError(ssl.SSL_ERROR_WANT_READ, "want read")
        wrapped_want._tls_sock.recv.side_effect = want_read
        assert wrapped_want.recv(1024) == b""

        wrapped_err = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped_err._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped_err._buffer = b""
        wrapped_err._raw_sock = MagicMock()
        wrapped_err._tls_sock = MagicMock()
        wrapped_err._tls_sock.recv.side_effect = ssl.SSLError(ssl.SSL_ERROR_SSL, "fail")
        with pytest.raises(socket.error, match="TLS Error"):
            wrapped_err.recv(1024)

    def test_close_and_getattr_passthrough(self):
        wrapped = DomainFrontingSocket.__new__(DomainFrontingSocket)
        wrapped._transport = DomainFrontingTransport(FRONT, BACKEND)
        wrapped._buffer = b""
        wrapped._raw_sock = MagicMock()
        wrapped._tls_sock = MagicMock()
        wrapped._tls_sock.marker = "tls-ok"

        wrapped.close()
        wrapped._tls_sock.close.assert_called_once()
        assert wrapped.marker == "tls-ok"
