"""Unit tests for src/security/pqc/dsa.py"""
import os
import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import pytest


class TestPQCDigitalSignatureInit:
    """Tests for PQCDigitalSignature initialization."""

    @patch("src.security.pqc.dsa.get_secure_storage")
    @patch("src.security.pqc.dsa.is_liboqs_available", return_value=False)
    def test_init_without_liboqs(self, mock_avail, mock_storage):
        from src.security.pqc.dsa import PQCDigitalSignature
        dsa = PQCDigitalSignature()
        assert dsa.enabled is False
        assert dsa._adapter is None

    @patch("src.security.pqc.dsa.get_secure_storage")
    @patch("src.security.pqc.dsa.PQCAdapter")
    @patch("src.security.pqc.dsa.is_liboqs_available", return_value=True)
    def test_init_with_liboqs(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.dsa import PQCDigitalSignature
        dsa = PQCDigitalSignature()
        assert dsa.enabled is True
        mock_adapter_cls.assert_called_once_with(sig_alg="ML-DSA-65")

    @patch("src.security.pqc.dsa.get_secure_storage")
    @patch("src.security.pqc.dsa.PQCAdapter")
    @patch("src.security.pqc.dsa.is_liboqs_available", return_value=True)
    def test_init_custom_algorithm(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.dsa import PQCDigitalSignature
        dsa = PQCDigitalSignature(algorithm="ML-DSA-87")
        assert dsa.algorithm == "ML-DSA-87"
        mock_adapter_cls.assert_called_once_with(sig_alg="ML-DSA-87")

    @patch("src.security.pqc.dsa.get_secure_storage")
    @patch("src.security.pqc.dsa.PQCAdapter", side_effect=Exception("init fail"))
    @patch("src.security.pqc.dsa.is_liboqs_available", return_value=True)
    def test_init_adapter_failure_disables(self, mock_avail, mock_adapter_cls, mock_storage):
        from src.security.pqc.dsa import PQCDigitalSignature
        dsa = PQCDigitalSignature()
        assert dsa.enabled is False


class TestPQCDigitalSignatureOperations:
    """Tests for sign/verify/generate operations."""

    def _make_dsa(self):
        """Create a DSA instance with mocked adapter."""
        with patch("src.security.pqc.dsa.get_secure_storage") as mock_storage, \
             patch("src.security.pqc.dsa.PQCAdapter") as mock_adapter_cls, \
             patch("src.security.pqc.dsa.is_liboqs_available", return_value=True):
            mock_adapter = MagicMock()
            mock_adapter_cls.return_value = mock_adapter
            mock_store = MagicMock()
            mock_storage.return_value = mock_store
            from src.security.pqc.dsa import PQCDigitalSignature
            dsa = PQCDigitalSignature()
        return dsa, mock_adapter, mock_store

    def test_generate_keypair(self):
        dsa, mock_adapter, _ = self._make_dsa()
        mock_adapter.sig_generate_keypair.return_value = (b"pub123", b"sec456")

        keypair = dsa.generate_keypair()
        assert keypair.public_key == b"pub123"
        assert keypair.secret_key == b"sec456"
        assert keypair.algorithm == "ML-DSA-65"

    def test_generate_keypair_with_key_id_stores_securely(self):
        dsa, mock_adapter, mock_store = self._make_dsa()
        mock_adapter.sig_generate_keypair.return_value = (b"pub", b"sec")
        mock_handle = MagicMock()
        mock_store.store_key.return_value = mock_handle

        keypair = dsa.generate_keypair(key_id="test-key", validity_days=30)
        mock_store.store_key.assert_called_once_with(
            key_id="test-key",
            secret_key=b"sec",
            algorithm="ML-DSA-65",
            validity_days=30,
        )
        assert dsa._key_handles["test-key"] is mock_handle

    def test_generate_keypair_disabled_raises(self):
        with patch("src.security.pqc.dsa.get_secure_storage"), \
             patch("src.security.pqc.dsa.is_liboqs_available", return_value=False):
            from src.security.pqc.dsa import PQCDigitalSignature
            dsa = PQCDigitalSignature()
        with pytest.raises(RuntimeError, match="PQC not available"):
            dsa.generate_keypair()

    def test_sign(self):
        dsa, mock_adapter, _ = self._make_dsa()
        mock_adapter.sig_sign.return_value = b"signature_bytes"

        message = b"hello world"
        sig = dsa.sign(message, b"secret_key", key_id="k1")
        assert sig.signature_bytes == b"signature_bytes"
        assert sig.message_hash == hashlib.sha256(message).digest()
        assert sig.algorithm == "ML-DSA-65"
        assert sig.signer_key_id == "k1"

    def test_sign_disabled_raises(self):
        with patch("src.security.pqc.dsa.get_secure_storage"), \
             patch("src.security.pqc.dsa.is_liboqs_available", return_value=False):
            from src.security.pqc.dsa import PQCDigitalSignature
            dsa = PQCDigitalSignature()
        with pytest.raises(RuntimeError, match="PQC not available"):
            dsa.sign(b"msg", b"key")

    def test_verify_valid(self):
        dsa, mock_adapter, _ = self._make_dsa()
        mock_adapter.sig_verify.return_value = True

        result = dsa.verify(b"msg", b"sig", b"pubkey")
        assert result is True
        mock_adapter.sig_verify.assert_called_once_with(b"msg", b"sig", b"pubkey")

    def test_verify_invalid(self):
        dsa, mock_adapter, _ = self._make_dsa()
        mock_adapter.sig_verify.return_value = False

        result = dsa.verify(b"msg", b"sig", b"pubkey")
        assert result is False

    def test_verify_exception_returns_false(self):
        dsa, mock_adapter, _ = self._make_dsa()
        mock_adapter.sig_verify.side_effect = Exception("verify error")

        result = dsa.verify(b"msg", b"sig", b"pubkey")
        assert result is False

    def test_verify_disabled_raises(self):
        with patch("src.security.pqc.dsa.get_secure_storage"), \
             patch("src.security.pqc.dsa.is_liboqs_available", return_value=False):
            from src.security.pqc.dsa import PQCDigitalSignature
            dsa = PQCDigitalSignature()
        with pytest.raises(RuntimeError, match="PQC not available"):
            dsa.verify(b"msg", b"sig", b"pubkey")


class TestPQCDigitalSignatureCache:
    """Tests for key caching."""

    def _make_dsa(self):
        with patch("src.security.pqc.dsa.get_secure_storage") as mock_storage, \
             patch("src.security.pqc.dsa.PQCAdapter") as mock_adapter_cls, \
             patch("src.security.pqc.dsa.is_liboqs_available", return_value=True):
            mock_adapter = MagicMock()
            mock_adapter_cls.return_value = mock_adapter
            mock_store = MagicMock()
            mock_storage.return_value = mock_store
            from src.security.pqc.dsa import PQCDigitalSignature
            dsa = PQCDigitalSignature()
        return dsa, mock_adapter, mock_store

    def test_get_cached_keypair_no_handle(self):
        dsa, _, _ = self._make_dsa()
        assert dsa.get_cached_keypair("nonexistent") is None

    def test_get_cached_keypair_returns_none(self):
        """get_cached_keypair always returns None (public key not stored)."""
        dsa, _, mock_store = self._make_dsa()
        handle = MagicMock()
        dsa._key_handles["k1"] = handle
        mock_store.get_key.return_value = b"secret"
        # Even with valid secret key, returns None because public key not stored
        assert dsa.get_cached_keypair("k1") is None

    def test_get_secret_key(self):
        dsa, _, mock_store = self._make_dsa()
        handle = MagicMock()
        dsa._key_handles["k1"] = handle
        mock_store.get_key.return_value = b"the_secret"
        assert dsa.get_secret_key("k1") == b"the_secret"

    def test_get_secret_key_no_handle(self):
        dsa, _, _ = self._make_dsa()
        assert dsa.get_secret_key("missing") is None

    def test_clear_cache(self):
        dsa, _, mock_store = self._make_dsa()
        h1, h2 = MagicMock(), MagicMock()
        dsa._key_handles = {"k1": h1, "k2": h2}
        dsa.clear_cache()
        assert mock_store.delete_key.call_count == 2
        assert len(dsa._key_handles) == 0

    def test_is_available(self):
        dsa, _, _ = self._make_dsa()
        assert dsa.is_available() is True
