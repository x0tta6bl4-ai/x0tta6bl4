"""Unit tests for src/security/pqc/secure_storage.py"""
import os
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import pytest

from src.security.pqc.secure_storage import SecureKeyStorage, SecureKeyHandle, get_secure_storage


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    SecureKeyStorage._instance = None
    import src.security.pqc.secure_storage as mod
    mod._global_storage = None
    yield
    SecureKeyStorage._instance = None
    mod._global_storage = None


class TestSecureKeyHandle:
    """Tests for SecureKeyHandle dataclass."""

    def test_is_expired_false(self):
        handle = SecureKeyHandle(
            key_id="k1",
            algorithm="ML-KEM-768",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert handle.is_expired() is False

    def test_is_expired_true(self):
        handle = SecureKeyHandle(
            key_id="k1",
            algorithm="ML-KEM-768",
            created_at=datetime.utcnow() - timedelta(days=2),
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert handle.is_expired() is True


class TestSecureKeyStorageSingleton:
    """Tests for singleton pattern."""

    def test_singleton(self):
        s1 = SecureKeyStorage()
        s2 = SecureKeyStorage()
        assert s1 is s2

    def test_get_secure_storage_returns_instance(self):
        storage = get_secure_storage()
        assert isinstance(storage, SecureKeyStorage)

    def test_get_secure_storage_same_instance(self):
        s1 = get_secure_storage()
        s2 = get_secure_storage()
        assert s1 is s2


class TestSecureKeyStorageOperations:
    """Tests for store/get/delete operations."""

    def test_store_and_get_key(self):
        storage = SecureKeyStorage()
        secret = secrets.token_bytes(32)
        handle = storage.store_key("k1", secret, "ML-KEM-768", validity_days=365)

        assert handle.key_id == "k1"
        assert handle.algorithm == "ML-KEM-768"

        retrieved = storage.get_key(handle)
        assert retrieved == secret

    def test_store_overwrites_existing(self):
        storage = SecureKeyStorage()
        storage.store_key("k1", b"secret1", "ML-KEM-768")
        handle = storage.store_key("k1", b"secret2", "ML-KEM-768")
        assert storage.get_key(handle) == b"secret2"

    def test_get_key_not_found(self):
        storage = SecureKeyStorage()
        handle = SecureKeyHandle(
            key_id="missing",
            algorithm="ML-KEM-768",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert storage.get_key(handle) is None

    def test_get_key_expired(self):
        storage = SecureKeyStorage()
        handle = storage.store_key("k1", b"secret", "ML-KEM-768", validity_days=365)
        # Force expire
        handle.expires_at = datetime.utcnow() - timedelta(days=1)
        assert storage.get_key(handle) is None

    def test_delete_key(self):
        storage = SecureKeyStorage()
        handle = storage.store_key("k1", b"secret", "ML-KEM-768")
        assert storage.delete_key(handle) is True
        assert storage.get_key(handle) is None

    def test_delete_key_not_found(self):
        storage = SecureKeyStorage()
        handle = SecureKeyHandle(
            key_id="missing",
            algorithm="ML-KEM-768",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert storage.delete_key(handle) is False

    def test_list_keys(self):
        storage = SecureKeyStorage()
        storage.store_key("k1", b"s1", "ML-KEM-768")
        storage.store_key("k2", b"s2", "ML-DSA-65")

        keys = storage.list_keys()
        assert "k1" in keys
        assert "k2" in keys
        assert keys["k1"]["algorithm"] == "ML-KEM-768"
        assert keys["k2"]["algorithm"] == "ML-DSA-65"
        assert keys["k1"]["key_size"] == 2
        assert keys["k2"]["key_size"] == 2

    def test_clear_all(self):
        storage = SecureKeyStorage()
        storage.store_key("k1", b"s1", "ML-KEM-768")
        storage.store_key("k2", b"s2", "ML-DSA-65")

        count = storage.clear_all()
        assert count == 2
        assert len(storage.list_keys()) == 0

    def test_get_key_handle(self):
        storage = SecureKeyStorage()
        storage.store_key("k1", b"s1", "ML-KEM-768")
        handle = storage.get_key_handle("k1")
        assert handle is not None
        assert handle.key_id == "k1"

    def test_get_key_handle_missing(self):
        storage = SecureKeyStorage()
        assert storage.get_key_handle("nope") is None


class TestSecureKeyStorageTemporaryKey:
    """Tests for temporary_key context manager."""

    def test_temporary_key(self):
        storage = SecureKeyStorage()
        with storage.temporary_key(b"temp_secret", "ML-KEM-768") as handle:
            assert handle.key_id.startswith("temp-")
            retrieved = storage.get_key(handle)
            assert retrieved == b"temp_secret"
        # After context exit, key should be deleted
        assert storage.get_key(handle) is None


class TestSecureKeyStorageSecureZero:
    """Tests for secure zeroization."""

    def test_secure_zero(self):
        storage = SecureKeyStorage()
        data = bytearray(b"\xff" * 10)
        storage._secure_zero(data)
        assert all(b == 0 for b in data)


class TestSecureKeyStorageEncryption:
    """Tests for encrypt/decrypt roundtrip."""

    def test_encrypt_decrypt_roundtrip(self):
        storage = SecureKeyStorage()
        original = secrets.token_bytes(64)
        encrypted, tag = storage._encrypt_key(original)
        decrypted = storage._decrypt_key(encrypted, tag)
        assert decrypted == original

    def test_different_nonces(self):
        storage = SecureKeyStorage()
        data = b"same_data"
        enc1, tag1 = storage._encrypt_key(data)
        enc2, tag2 = storage._encrypt_key(data)
        # Different nonces mean different ciphertexts
        assert enc1 != enc2


class TestCleanupOnExit:
    """Tests for cleanup."""

    def test_cleanup_on_exit(self):
        storage = SecureKeyStorage()
        storage.store_key("k1", b"secret", "ML-KEM-768")
        storage._cleanup_on_exit()
        assert len(storage.list_keys()) == 0
