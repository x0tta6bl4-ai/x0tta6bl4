"""Unit tests for src.network.obfuscation.shadowsocks module.

Tests ChaCha20-Poly1305 AEAD obfuscation with real crypto round-trips.
"""

import os
import socket
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

from cryptography.exceptions import InvalidTag

from src.network.obfuscation.shadowsocks import (ShadowsocksSocket,
                                                 ShadowsocksTransport)


# ===========================================================================
# TestShadowsocksTransportInit
# ===========================================================================


class TestShadowsocksTransportInit:

    def test_explicit_password_derives_master_key(self):
        t = ShadowsocksTransport(password="my-secret")
        assert t.master_key is not None
        assert len(t.master_key) == 32

    def test_password_stored_as_bytes(self):
        t = ShadowsocksTransport(password="hello")
        assert t.password == b"hello"

    def test_master_key_is_32_bytes(self):
        t = ShadowsocksTransport(password="test-password")
        assert isinstance(t.master_key, bytes)
        assert len(t.master_key) == 32

    def test_without_password_generates_random(self, monkeypatch):
        """Without password or env var, a random password is generated."""
        monkeypatch.delenv("X0TTA6BL4_SHADOWSOCKS_PASSWORD", raising=False)
        t = ShadowsocksTransport(password=None)
        assert t.master_key is not None
        assert len(t.master_key) == 32


# ===========================================================================
# TestKdf
# ===========================================================================


class TestKdf:

    def test_returns_bytes_of_requested_length(self):
        t = ShadowsocksTransport(password="kdf-test")
        key = t._kdf(b"material", b"salt", 32)
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_different_material_different_output(self):
        t = ShadowsocksTransport(password="kdf-test")
        k1 = t._kdf(b"material-A", b"salt", 32)
        k2 = t._kdf(b"material-B", b"salt", 32)
        assert k1 != k2


# ===========================================================================
# TestDeriveSessionKey
# ===========================================================================


class TestDeriveSessionKey:

    def test_returns_32_byte_key(self):
        t = ShadowsocksTransport(password="session-test")
        key = t.derive_session_key(b"\x00" * 32)
        assert len(key) == 32

    def test_different_salts_different_keys(self):
        t = ShadowsocksTransport(password="session-test")
        k1 = t.derive_session_key(b"\x00" * 32)
        k2 = t.derive_session_key(b"\xff" * 32)
        assert k1 != k2


# ===========================================================================
# TestObfuscate
# ===========================================================================


class TestObfuscate:

    def test_output_at_least_60_bytes(self):
        t = ShadowsocksTransport(password="obs-test")
        out = t.obfuscate(b"")
        # 32 salt + 12 nonce + 16 tag = 60 minimum
        assert len(out) >= 60

    def test_first_32_bytes_differ_between_calls(self):
        t = ShadowsocksTransport(password="obs-test")
        out1 = t.obfuscate(b"data")
        out2 = t.obfuscate(b"data")
        # Random salt → first 32 bytes should differ
        assert out1[:32] != out2[:32]

    def test_output_length_correct(self):
        t = ShadowsocksTransport(password="obs-test")
        data = b"hello world"
        out = t.obfuscate(data)
        # Format: [Salt 32] [Nonce 12] [Ciphertext + Tag(16)]
        expected_len = 32 + 12 + len(data) + 16
        assert len(out) == expected_len

    def test_empty_data_produces_60_byte_output(self):
        t = ShadowsocksTransport(password="obs-test")
        out = t.obfuscate(b"")
        assert len(out) == 60  # 32 + 12 + 0 + 16


# ===========================================================================
# TestDeobfuscate
# ===========================================================================


class TestDeobfuscate:

    def test_raises_on_data_too_short(self):
        t = ShadowsocksTransport(password="deobs-test")
        with pytest.raises(ValueError, match="too short"):
            t.deobfuscate(b"\x00" * 59)

    def test_raises_on_tampered_ciphertext(self):
        t = ShadowsocksTransport(password="deobs-test")
        ct = t.obfuscate(b"original data")
        # Tamper with the ciphertext (flip last byte before tag)
        tampered = ct[:-1] + bytes([ct[-1] ^ 0xFF])
        with pytest.raises(InvalidTag):
            t.deobfuscate(tampered)

    def test_raises_with_wrong_password(self):
        t1 = ShadowsocksTransport(password="password-A")
        t2 = ShadowsocksTransport(password="password-B")
        ct = t1.obfuscate(b"secret")
        with pytest.raises(InvalidTag):
            t2.deobfuscate(ct)


# ===========================================================================
# TestObfuscateDeobfuscateRoundTrip
# ===========================================================================


class TestObfuscateDeobfuscateRoundTrip:

    def test_roundtrip_short_data(self):
        t = ShadowsocksTransport(password="rt-test")
        data = b"hello"
        assert t.deobfuscate(t.obfuscate(data)) == data

    def test_roundtrip_empty_data(self):
        t = ShadowsocksTransport(password="rt-test")
        assert t.deobfuscate(t.obfuscate(b"")) == b""

    def test_roundtrip_large_data(self):
        t = ShadowsocksTransport(password="rt-test")
        data = os.urandom(10000)
        assert t.deobfuscate(t.obfuscate(data)) == data

    def test_roundtrip_binary_data(self):
        t = ShadowsocksTransport(password="rt-test")
        data = bytes(range(256))
        assert t.deobfuscate(t.obfuscate(data)) == data

    def test_different_outputs_same_plaintext(self):
        t = ShadowsocksTransport(password="rt-test")
        data = b"same input"
        ct1 = t.obfuscate(data)
        ct2 = t.obfuscate(data)
        assert ct1 != ct2  # Different salt+nonce
        assert t.deobfuscate(ct1) == data
        assert t.deobfuscate(ct2) == data


# ===========================================================================
# TestWrapSocket
# ===========================================================================


class TestWrapSocket:

    def test_is_subclass_of_socket(self):
        assert issubclass(ShadowsocksSocket, socket.socket)

    def test_transport_has_wrap_socket(self):
        t = ShadowsocksTransport(password="ws-test")
        assert callable(getattr(t, "wrap_socket", None))

    def test_socket_init_hits_timeout_attribute_error(self):
        raw_a, raw_b = socket.socketpair()
        try:
            with pytest.raises(AttributeError):
                ShadowsocksSocket(raw_a, ShadowsocksTransport(password="pw"))
        finally:
            try:
                raw_a.close()
            except OSError:
                pass  # fd taken by ShadowsocksSocket.__init__ via super().__init__(fileno=...)
            try:
                raw_b.close()
            except OSError:
                pass

    def test_send_sets_session_salt_and_uses_transport(self):
        class _Sock:
            def __init__(self):
                self.sent = []

            def send(self, data, flags=0):
                self.sent.append((data, flags))
                return len(data)

        class _Transport:
            def derive_key(self, salt):
                assert len(salt) == 32
                return b"k" * 32

            def obfuscate(self, data):
                return b"enc:" + data

        wrapped = ShadowsocksSocket.__new__(ShadowsocksSocket)
        wrapped._sock = _Sock()
        wrapped._transport = _Transport()
        wrapped._salt_sent = False
        wrapped._salt_received = False
        wrapped._buffer = b""

        out1 = wrapped.send(b"hello")
        out2 = wrapped.send(b"world")

        assert out1 == len(b"enc:hello")
        assert out2 == len(b"enc:world")
        assert wrapped._salt_sent is True
        assert len(wrapped._session_salt) == 32
        assert wrapped._sock.sent == [(b"enc:hello", 0), (b"enc:world", 0)]

    def test_recv_success_and_decrypt_error(self):
        class _Sock:
            def __init__(self):
                self.responses = [b"cipher", b"broken", b""]

            def recv(self, _size, _flags=0):
                return self.responses.pop(0) if self.responses else b""

        class _Transport:
            def __init__(self):
                self.calls = 0

            def deobfuscate(self, data):
                self.calls += 1
                if data == b"broken":
                    raise ValueError("bad")
                return b"plain:" + data

        wrapped = ShadowsocksSocket.__new__(ShadowsocksSocket)
        wrapped._sock = _Sock()
        wrapped._transport = _Transport()
        wrapped._salt_sent = True
        wrapped._salt_received = True
        wrapped._buffer = b""

        assert wrapped.recv(1024) == b"plain:cipher"
        assert wrapped.recv(1024) == b""
        assert wrapped.recv(1024) == b""

    def test_getattr_passthrough_and_wrap_socket_raises(self):
        class _Sock:
            marker = "shadow"

        wrapped = ShadowsocksSocket.__new__(ShadowsocksSocket)
        wrapped._sock = _Sock()
        wrapped._transport = ShadowsocksTransport(password="pw")
        wrapped._salt_sent = True
        wrapped._salt_received = True
        wrapped._buffer = b""
        assert wrapped.marker == "shadow"

        raw_a, raw_b = socket.socketpair()
        try:
            with pytest.raises(AttributeError):
                ShadowsocksTransport(password="pw").wrap_socket(raw_a)
        finally:
            try:
                raw_a.close()
            except OSError:
                pass  # fd taken by ShadowsocksSocket.__init__ via super().__init__(fileno=...)
            try:
                raw_b.close()
            except OSError:
                pass
