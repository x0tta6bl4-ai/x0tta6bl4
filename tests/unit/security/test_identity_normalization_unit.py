"""Unit tests for identity normalization CVE-2020-12812 protections."""

import pytest

from src.security.identity_normalization import (enforce_lowercase_rule,
                                                 get_identity_hash,
                                                 is_system_identifier,
                                                 normalize_identity,
                                                 validate_identifier)


def test_normalize_identity_canonicalizes_and_hashes():
    token, canonical = normalize_identity("  Alice.Admin-01  ")
    assert canonical == "alice.admin-01"
    assert isinstance(token, bytes)
    assert len(token) == 32


def test_normalize_identity_same_hash_for_different_case():
    token1, canonical1 = normalize_identity("User.Name")
    token2, canonical2 = normalize_identity("user.name")
    assert canonical1 == canonical2 == "user.name"
    assert token1 == token2


def test_normalize_identity_rejects_invalid_symbols():
    with pytest.raises(ValueError):
        normalize_identity("bad!name")


def test_validate_identifier_requires_pre_lowercased_input():
    assert validate_identifier("valid.name_01") is True
    assert validate_identifier("Invalid.Name_01") is False
    assert validate_identifier("") is False


def test_enforce_lowercase_rule_rejects_uppercase():
    with pytest.raises(ValueError, match="contains uppercase"):
        enforce_lowercase_rule("AdminUser", context="auth")


def test_enforce_lowercase_rule_returns_normalized_value():
    assert enforce_lowercase_rule("user.name  ") == "user.name"


def test_get_identity_hash_is_stable_and_case_insensitive():
    h1 = get_identity_hash("SYSTEM.USER")
    h2 = get_identity_hash("system.user")
    assert h1 == h2
    assert len(h1) == 64


def test_system_identifier_check_is_case_insensitive():
    assert is_system_identifier("X0TTA6BL4") is True
    assert is_system_identifier("hip3.14cirz") is True
    assert is_system_identifier("external-service") is False
