import os
import socket

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.obfuscation.simple import XORSocket, SimpleXORTransport


def test_transport_obfuscate_and_deobfuscate_roundtrip():
    transport = SimpleXORTransport("key")
    payload = b"mesh-packet"

    obfuscated = transport.obfuscate(payload)
    restored = transport.deobfuscate(obfuscated)

    assert obfuscated != payload
    assert restored == payload


def test_xorsocket_init_raises_timeout_attribute_error():
    left, right = socket.socketpair()
    try:
        with pytest.raises(AttributeError):
            XORSocket(left, b"k")
    finally:
        try:
            left.close()
        except OSError:
            pass  # fd taken by XORSocket.__init__ via super().__init__(fileno=...)
        try:
            right.close()
        except OSError:
            pass


def test_xorsocket_init_handles_super_init_failure_before_timeout():
    class _BadFilenoSocket:
        def fileno(self):
            raise OSError("bad fd")

        def gettimeout(self):
            return None

    with pytest.raises(AttributeError):
        XORSocket(_BadFilenoSocket(), b"k")


def test_xorsocket_send_recv_close_and_getattr_passthrough():
    class _FakeSocket:
        marker = "socket-ok"

        def __init__(self):
            self.sent = []
            self.to_recv = []
            self.closed = False

        def send(self, data, flags=0):
            self.sent.append((data, flags))
            return len(data)

        def recv(self, _bufsize, _flags=0):
            return self.to_recv.pop(0) if self.to_recv else b""

        def close(self):
            self.closed = True

    wrapped = XORSocket.__new__(XORSocket)
    wrapped._sock = _FakeSocket()
    wrapped._key = b"\x01\x02"
    wrapped._key_len = 2

    payload = b"\x10\x20\x30"
    encrypted = wrapped._xor(payload)
    assert encrypted == bytes([0x11, 0x22, 0x31])

    sent_len = wrapped.send(payload)
    assert sent_len == len(payload)
    assert wrapped._sock.sent == [(encrypted, 0)]

    expected_incoming = b"\xAA\xBB"
    wrapped._sock.to_recv = [wrapped._xor(expected_incoming)]
    assert wrapped.recv(1024) == expected_incoming

    wrapped.close()
    assert wrapped._sock.closed is True
    assert wrapped.marker == "socket-ok"


def test_wrap_socket_delegates_to_xorsocket_constructor():
    transport = SimpleXORTransport("secret")
    left, right = socket.socketpair()
    try:
        with pytest.raises(AttributeError):
            transport.wrap_socket(left)
    finally:
        try:
            left.close()
        except OSError:
            pass  # fd taken by XORSocket.__init__ via super().__init__(fileno=...)
        try:
            right.close()
        except OSError:
            pass
