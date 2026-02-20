"""Unit tests for shared MaaS password auth helpers."""

from src.security.password_auth import hash_password, verify_password


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("StrongPassword123!")
    assert hashed.startswith("$2")


def test_verify_password_bcrypt_success_and_failure():
    password = "StrongPassword123!"
    hashed = hash_password(password)

    ok, should_rehash = verify_password(password, hashed)
    assert ok is True
    assert should_rehash is False

    bad_ok, bad_rehash = verify_password("wrong-password", hashed)
    assert bad_ok is False
    assert bad_rehash is False


def test_verify_password_legacy_plaintext_fallback():
    ok, should_rehash = verify_password("legacy_password_123", "legacy_password_123")
    assert ok is True
    assert should_rehash is True


def test_verify_password_invalid_hash_format():
    ok, should_rehash = verify_password("password", "$2b$invalid")
    assert ok is False
    assert should_rehash is False
