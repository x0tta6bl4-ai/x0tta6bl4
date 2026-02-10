"""Unit tests for src.network.obfuscation.shadowsocks module.

Tests ChaCha20-Poly1305 AEAD obfuscation with real crypto round-trips.
"""

import os
import socket
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from src.network.obfuscation.shadowsocks import (
        ShadowsocksTransport,
        ShadowsocksSocket,
    )
    from cryptography.exceptions import InvalidTag
    SS_AVAILABLE = True
except ImportError as exc:
    SS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not SS_AVAILABLE, reason="shadowsocks module not available")


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
