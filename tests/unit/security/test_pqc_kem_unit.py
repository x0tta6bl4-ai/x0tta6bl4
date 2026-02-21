"""Unit tests for src/security/pqc/kem.py"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import pytest


class TestPQCKeyExchangeInit:
    """Tests for PQCKeyExchange initialization."""

    @patch("src.security.pqc.kem.get_secure_storage")
    @patch("src.security.pqc.kem.is_liboqs_available", return_value=False)
    def test_init_without_liboqs(self, mock_avail, mock_storage):
        from src.security.pqc.kem import PQCKeyExchange
        kem = PQCKeyExchange()
        assert kem.enabled is False
        assert kem._adapter is None

    @patch("src.security.pqc.kem.get_secure_storage")
    @patch("src.security.pqc.kem.PQCAdapter")
    @patch("src.security.pqc.kem.is_liboqs_available", return_value=True)
    def test_init_with_liboqs(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.kem import PQCKeyExchange
        kem = PQCKeyExchange()
        assert kem.enabled is True
        mock_adapter_cls.assert_called_once_with(kem_alg="ML-KEM-768")

    @patch("src.security.pqc.kem.get_secure_storage")
    @patch("src.security.pqc.kem.PQCAdapter")
    @patch("src.security.pqc.kem.is_liboqs_available", return_value=True)
    def test_init_custom_algorithm(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.kem import PQCKeyExchange
        kem = PQCKeyExchange(algorithm="ML-KEM-1024")
        assert kem.algorithm == "ML-KEM-1024"
        mock_adapter_cls.assert_called_once_with(kem_alg="ML-KEM-1024")

    @patch("src.security.pqc.kem.get_secure_storage")
    @patch("src.security.pqc.kem.PQCAdapter", side_effect=Exception("bad"))
    @patch("src.security.pqc.kem.is_liboqs_available", return_value=True)
    def test_init_adapter_failure_disables(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.kem import PQCKeyExchange
        kem = PQCKeyExchange()
        assert kem.enabled is False


def _make_kem():
    """Create a KEM instance with mocked adapter."""
    with patch("src.security.pqc.kem.get_secure_storage") as mock_storage, \
         patch("src.security.pqc.kem.PQCAdapter") as mock_adapter_cls, \
         patch("src.security.pqc.kem.is_liboqs_available", return_value=True):
        mock_adapter = MagicMock()
        mock_adapter_cls.return_value = mock_adapter
        mock_store = MagicMock()
        mock_storage.return_value = mock_store
        from src.security.pqc.kem import PQCKeyExchange
        kem = PQCKeyExchange()
    return kem, mock_adapter, mock_store


class TestPQCKeyExchangeKeypair:
    """Tests for keypair generation."""

    def test_generate_keypair(self):
        kem, mock_adapter, _ = _make_kem()
        mock_adapter.kem_generate_keypair.return_value = (b"pub", b"sec")

        kp = kem.generate_keypair()
        assert kp.public_key == b"pub"
        assert kp.secret_key == b"sec"
        assert kp.algorithm == "ML-KEM-768"

    def test_generate_keypair_with_key_id(self):
        kem, mock_adapter, mock_store = _make_kem()
        mock_adapter.kem_generate_keypair.return_value = (b"pub", b"sec")
        mock_handle = MagicMock()
        mock_store.store_key.return_value = mock_handle

        kp = kem.generate_keypair(key_id="my-key", validity_days=7)
        mock_store.store_key.assert_called_once_with(
            key_id="my-key",
            secret_key=b"sec",
            algorithm="ML-KEM-768",
            validity_days=7,
        )
        assert kem._key_handles["my-key"] is mock_handle

    def test_generate_keypair_disabled_raises(self):
        with patch("src.security.pqc.kem.get_secure_storage"), \
             patch("src.security.pqc.kem.is_liboqs_available", return_value=False):
            from src.security.pqc.kem import PQCKeyExchange
            kem = PQCKeyExchange()
        with pytest.raises(RuntimeError, match="PQC not available"):
            kem.generate_keypair()

    def test_generate_keypair_adapter_error_propagates(self):
        kem, mock_adapter, _ = _make_kem()
        mock_adapter.kem_generate_keypair.side_effect = RuntimeError("keygen fail")
        with pytest.raises(RuntimeError, match="keygen fail"):
            kem.generate_keypair()


class TestPQCKeyExchangeEncapsDecaps:
    """Tests for encapsulate/decapsulate."""

    def test_encapsulate(self):
        kem, mock_adapter, _ = _make_kem()
        mock_adapter.kem_encapsulate.return_value = (b"ct", b"ss")

        ct, ss = kem.encapsulate(b"pubkey")
        assert ct == b"ct"
        assert ss == b"ss"
        mock_adapter.kem_encapsulate.assert_called_once_with(b"pubkey")

    def test_encapsulate_disabled_raises(self):
        with patch("src.security.pqc.kem.get_secure_storage"), \
             patch("src.security.pqc.kem.is_liboqs_available", return_value=False):
            from src.security.pqc.kem import PQCKeyExchange
            kem = PQCKeyExchange()
        with pytest.raises(RuntimeError, match="PQC not available"):
            kem.encapsulate(b"pubkey")

    def test_decapsulate(self):
        kem, mock_adapter, _ = _make_kem()
        mock_adapter.kem_decapsulate.return_value = b"shared_secret"

        ss = kem.decapsulate(b"secret_key", b"ciphertext")
        assert ss == b"shared_secret"
        mock_adapter.kem_decapsulate.assert_called_once_with(b"secret_key", b"ciphertext")

    def test_decapsulate_disabled_raises(self):
        with patch("src.security.pqc.kem.get_secure_storage"), \
             patch("src.security.pqc.kem.is_liboqs_available", return_value=False):
            from src.security.pqc.kem import PQCKeyExchange
            kem = PQCKeyExchange()
        with pytest.raises(RuntimeError, match="PQC not available"):
            kem.decapsulate(b"sk", b"ct")

    def test_encapsulate_error_propagates(self):
        kem, mock_adapter, _ = _make_kem()
        mock_adapter.kem_encapsulate.side_effect = ValueError("bad key")
        with pytest.raises(ValueError, match="bad key"):
            kem.encapsulate(b"badkey")


class TestPQCKeyExchangeCache:
    """Tests for key caching."""

    def test_get_cached_keypair_no_handle(self):
        kem, _, _ = _make_kem()
        assert kem.get_cached_keypair("x") is None

    def test_get_cached_keypair_returns_none(self):
        kem, _, mock_store = _make_kem()
        handle = MagicMock()
        kem._key_handles["k"] = handle
        mock_store.get_key.return_value = b"secret"
        # Always returns None because public key not stored
        assert kem.get_cached_keypair("k") is None

    def test_get_secret_key(self):
        kem, _, mock_store = _make_kem()
        handle = MagicMock()
        kem._key_handles["k"] = handle
        mock_store.get_key.return_value = b"sec"
        assert kem.get_secret_key("k") == b"sec"

    def test_get_secret_key_missing(self):
        kem, _, _ = _make_kem()
        assert kem.get_secret_key("nope") is None

    def test_clear_cache(self):
        kem, _, mock_store = _make_kem()
        h1, h2 = MagicMock(), MagicMock()
        kem._key_handles = {"a": h1, "b": h2}
        kem.clear_cache()
        assert mock_store.delete_key.call_count == 2
        assert len(kem._key_handles) == 0

    def test_is_available(self):
        kem, _, _ = _make_kem()
        assert kem.is_available() is True
