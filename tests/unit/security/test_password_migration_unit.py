"""Unit tests for password migration helpers."""

import pytest

from src.security.password_migration import (PasswordMigrator,
                                             get_password_migrator)


def test_hash_and_verify_password_bcrypt():
    migrator = PasswordMigrator()
    hashed = migrator.hash_password("secure-pass-123")

    assert hashed.startswith("$2b$")
    assert migrator.verify_password("secure-pass-123", hashed) is True
    assert migrator.verify_password("wrong-pass", hashed) is False


def test_md5_hash_is_detected_and_forced_reset():
    migrator = PasswordMigrator()
    md5_hash = "5f4dcc3b5aa765d61d8327deb882cf99"

    assert migrator.is_md5_hash(md5_hash) is True
    is_valid, needs_rehash = migrator.verify_legacy_or_bcrypt("password", md5_hash)
    assert is_valid is False
    assert needs_rehash is True


def test_short_password_is_rejected():
    migrator = PasswordMigrator()
    with pytest.raises(ValueError, match="at least 8"):
        migrator.hash_password("short")


def test_singleton_password_migrator():
    assert get_password_migrator() is get_password_migrator()
