"""Unit tests for src.network.obfuscation.faketls module."""

import socket
import struct

import pytest

from src.network.obfuscation.faketls import FakeTLSSocket, FakeTLSTransport


# ---------------------------------------------------------------------------
# TestFakeTLSTransportInit
# ---------------------------------------------------------------------------


class TestFakeTLSTransportInit:
    """Tests for FakeTLSTransport constructor."""

    def test_default_sni_is_cloudflare(self):
        transport = FakeTLSTransport()
        assert transport.sni == b"www.cloudflare.com"

    def test_custom_sni_stored_as_bytes(self):
        transport = FakeTLSTransport(sni="example.org")
        assert transport.sni == b"example.org"
        assert isinstance(transport.sni, bytes)


# ---------------------------------------------------------------------------
# TestObfuscate
# ---------------------------------------------------------------------------


class TestObfuscate:
    """Tests for FakeTLSTransport.obfuscate."""

    def setup_method(self):
        self.transport = FakeTLSTransport()

    def test_obfuscate_prepends_five_byte_header(self):
        data = b"hello mesh"
        result = self.transport.obfuscate(data)
        assert len(result) == 5 + len(data)
        assert result[5:] == data

    def test_obfuscate_first_byte_is_application_data(self):
        result = self.transport.obfuscate(b"payload")
        assert result[0] == 0x17

    def test_obfuscate_version_bytes_are_tls_12(self):
        result = self.transport.obfuscate(b"payload")
        version = struct.unpack("!H", result[1:3])[0]
        assert version == 0x0303

    def test_obfuscate_length_field_matches_data_length(self):
        data = b"a]b]c]d]e]f"
        result = self.transport.obfuscate(data)
        encoded_length = struct.unpack("!H", result[3:5])[0]
        assert encoded_length == len(data)


# ---------------------------------------------------------------------------
# TestDeobfuscate
# ---------------------------------------------------------------------------


class TestDeobfuscate:
    """Tests for FakeTLSTransport.deobfuscate."""

    def setup_method(self):
        self.transport = FakeTLSTransport()

    def test_strips_header_when_starts_with_0x17_and_long_enough(self):
        payload = b"inner data here"
        header = struct.pack("!BHH", 0x17, 0x0303, len(payload))
        full_record = header + payload
        result = self.transport.deobfuscate(full_record)
        assert result == payload

    def test_returns_data_as_is_when_not_starting_with_0x17(self):
        data = b"\x16\x03\x03\x00\x05hello"
        result = self.transport.deobfuscate(data)
        assert result == data

    def test_returns_data_as_is_when_too_short(self):
        short_data = b"\x17\x03"
        result = self.transport.deobfuscate(short_data)
        assert result == short_data


# ---------------------------------------------------------------------------
# TestObfuscateDeobfuscateRoundTrip
# ---------------------------------------------------------------------------


class TestObfuscateDeobfuscateRoundTrip:
    """Round-trip tests for obfuscate -> deobfuscate."""

    def setup_method(self):
        self.transport = FakeTLSTransport()

    def test_roundtrip_short_data(self):
        data = b"short"
        obfuscated = self.transport.obfuscate(data)
        result = self.transport.deobfuscate(obfuscated)
        assert result == data

    def test_roundtrip_empty_data(self):
        data = b""
        obfuscated = self.transport.obfuscate(data)
        assert len(obfuscated) == 5
        result = self.transport.deobfuscate(obfuscated)
        assert result == b""

    def test_roundtrip_large_data(self):
        data = b"\xab" * 1000
        obfuscated = self.transport.obfuscate(data)
        result = self.transport.deobfuscate(obfuscated)
        assert result == data


# ---------------------------------------------------------------------------
# TestGenerateClientHello
# ---------------------------------------------------------------------------


class TestGenerateClientHello:
    """Tests for FakeTLSTransport.generate_client_hello."""

    def setup_method(self):
        self.transport = FakeTLSTransport()
        self.hello = self.transport.generate_client_hello()

    def test_first_byte_is_handshake_content_type(self):
        assert self.hello[0] == 0x16

    def test_record_version_is_tls_10(self):
        version = struct.unpack("!H", self.hello[1:3])[0]
        assert version == 0x0301

    def test_record_length_matches_remainder(self):
        record_length = struct.unpack("!H", self.hello[3:5])[0]
        actual_remainder = len(self.hello) - 5
        assert record_length == actual_remainder

    def test_contains_sni_string_in_body(self):
        assert b"www.cloudflare.com" in self.hello

    def test_handshake_type_is_client_hello(self):
        # Byte 5 (first byte after record header) is the handshake type
        assert self.hello[5] == 0x01

    def test_custom_sni_appears_in_hello(self):
        transport = FakeTLSTransport(sni="my.custom.domain.com")
        hello = transport.generate_client_hello()
        assert b"my.custom.domain.com" in hello

    def test_client_hello_contains_tls13_extensions(self):
        extension_types = _client_hello_extension_types(self.hello)

        assert {0x0000, 0x000A, 0x000D, 0x0010, 0x002B, 0x0033}.issubset(
            extension_types
        )


# ---------------------------------------------------------------------------
# TestFakeTLSSocket
# ---------------------------------------------------------------------------


class TestFakeTLSSocket:
    """Tests for FakeTLSSocket class structure.

    Note: FakeTLSSocket is a composition wrapper. It subclasses socket for
    backward compatibility but delegates actual I/O to the wrapped socket.
    """

    def test_is_subclass_of_socket(self):
        assert issubclass(FakeTLSSocket, socket.socket)

    def test_is_subclass_of_transport_base(self):
        """FakeTLSTransport extends ObfuscationTransport."""
        from src.network.obfuscation.base import ObfuscationTransport

        assert issubclass(FakeTLSTransport, ObfuscationTransport)

    def test_transport_has_wrap_socket_method(self):
        transport = FakeTLSTransport()
        assert callable(getattr(transport, "wrap_socket", None))

    def test_socket_init_wraps_timeout_access(self):
        raw_a, raw_b = socket.socketpair()
        try:
            wrapped = FakeTLSSocket(raw_a, FakeTLSTransport())
            wrapped.settimeout(0.5)
            assert wrapped.gettimeout() == 0.5
        finally:
            try:
                raw_a.close()
            except OSError:
                pass  # fd taken by FakeTLSSocket.__init__ via super().__init__(fileno=...)
            try:
                raw_b.close()
            except OSError:
                pass

    def test_send_injects_handshake_then_data(self):
        class _Sock:
            def __init__(self):
                self.sent = []

            def sendall(self, data):
                self.sent.append((data, 0))

        class _Transport:
            def generate_client_hello(self):
                return b"HELLO"

            def obfuscate(self, data):
                return b"REC:" + data

        wrapped = FakeTLSSocket.__new__(FakeTLSSocket)
        wrapped._sock = _Sock()
        wrapped._transport = _Transport()
        wrapped._handshake_sent = False
        wrapped._handshake_received = False

        sent_len = wrapped.send(b"abc")
        assert sent_len == len(b"abc")
        assert wrapped._sock.sent == [(b"HELLO", 0), (b"REC:abc", 0)]

        wrapped.send(b"xyz")
        assert wrapped._sock.sent[-1] == (b"REC:xyz", 0)

    def test_recv_consumes_server_hello_then_application_record(self):
        class _Sock:
            def __init__(self):
                self.responses = [
                    struct.pack("!BHH", 0x16, 0x0303, 3),
                    b"abc",
                    struct.pack("!BHH", 0x17, 0x0303, 4),
                    b"DATA",
                ]

            def recv(self, _size, _flags=0):
                return self.responses.pop(0) if self.responses else b""

        class _Transport:
            def deobfuscate(self, data):
                return b"plain:" + data[5:]

        wrapped = FakeTLSSocket.__new__(FakeTLSSocket)
        wrapped._sock = _Sock()
        wrapped._transport = _Transport()
        wrapped._handshake_sent = True
        wrapped._handshake_received = False

        out = wrapped.recv(4096)
        assert out == b"plain:DATA"
        assert wrapped._handshake_received is True

    def test_recv_handles_non_handshake_prefix_and_empty_header(self):
        class _Sock:
            def __init__(self):
                self.responses = [
                    struct.pack("!BHH", 0x17, 0x0303, 4),
                    b"ABCD",
                    b"",
                ]

            def recv(self, _size, _flags=0):
                return self.responses.pop(0) if self.responses else b""

        class _Transport:
            def deobfuscate(self, data):
                return data[5:].lower()

        wrapped = FakeTLSSocket.__new__(FakeTLSSocket)
        wrapped._sock = _Sock()
        wrapped._transport = _Transport()
        wrapped._handshake_sent = True
        wrapped._handshake_received = False

        assert wrapped.recv(1024) == b"abcd"
        assert wrapped.recv(1024) == b""

    def test_recv_returns_empty_on_non_app_record_and_getattr_passthrough(self):
        class _Sock:
            marker = "ok"

            def __init__(self):
                self.responses = [struct.pack("!BHH", 0x16, 0x0303, 0)]

            def recv(self, _size, _flags=0):
                return self.responses.pop(0) if self.responses else b""

        wrapped = FakeTLSSocket.__new__(FakeTLSSocket)
        wrapped._sock = _Sock()
        wrapped._transport = FakeTLSTransport()
        wrapped._handshake_sent = True
        wrapped._handshake_received = True

        assert wrapped.recv(1024) == b""
        assert wrapped.marker == "ok"

    def test_recv_returns_empty_when_app_header_missing(self):
        class _Sock:
            def recv(self, _size, _flags=0):
                return b""

        wrapped = FakeTLSSocket.__new__(FakeTLSSocket)
        wrapped._sock = _Sock()
        wrapped._transport = FakeTLSTransport()
        wrapped._handshake_sent = True
        wrapped._handshake_received = True

        assert wrapped.recv(1024) == b""

    def test_wrap_socket_constructs_wrapper_and_propagates_timeout_issue(self):
        raw_a, raw_b = socket.socketpair()
        try:
            transport = FakeTLSTransport()
            wrapped = transport.wrap_socket(raw_a)
            assert wrapped.fileno() == raw_a.fileno()
        finally:
            try:
                raw_a.close()
            except OSError:
                pass  # fd taken by FakeTLSSocket.__init__ via super().__init__(fileno=...)
            try:
                raw_b.close()
            except OSError:
                pass

    def test_wrapped_socket_roundtrip_with_buffering(self):
        raw_a, raw_b = socket.socketpair()
        try:
            left = FakeTLSTransport().wrap_socket(raw_a)
            right = FakeTLSTransport().wrap_socket(raw_b)
            left._handshake_sent = True
            right._handshake_received = True

            assert left.send(b"hello world") == len(b"hello world")
            assert right.recv(5) == b"hello"
            assert right.recv(1024) == b" world"
        finally:
            try:
                raw_a.close()
            except OSError:
                pass
            try:
                raw_b.close()
            except OSError:
                pass


def _client_hello_extension_types(hello: bytes) -> set[int]:
    body = hello[9:]
    pos = 2 + 32
    session_len = body[pos]
    pos += 1 + session_len
    cipher_len = struct.unpack("!H", body[pos : pos + 2])[0]
    pos += 2 + cipher_len
    compression_len = body[pos]
    pos += 1 + compression_len
    ext_len = struct.unpack("!H", body[pos : pos + 2])[0]
    pos += 2
    end = pos + ext_len
    extension_types = set()
    while pos < end:
        ext_type, length = struct.unpack("!HH", body[pos : pos + 4])
        extension_types.add(ext_type)
        pos += 4 + length
    return extension_types
