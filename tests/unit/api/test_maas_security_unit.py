"""
Unit tests for src/api/maas_security.py

Classes under test (no HTTP router — pure utility):
  ApiKeyManager  — key generation, format validation, hashing
  RateLimiter    — token bucket algorithm, per-key rate limiting
  PQCTokenSigner — sign/verify join tokens (PQC with HMAC-SHA256 fallback)
  OIDCValidator  — OIDC JWT validation (requires env vars to enable)

No TestClient needed — these are direct class-level unit tests.
Vault is unavailable in tests → PQCTokenSigner falls back to HMAC-SHA256.
"""

import hashlib
import hmac
import os
import time
from unittest.mock import MagicMock, patch

import pytest

# Set env before importing so OIDC/Vault paths use safe defaults
os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("MAAS_TOKEN_SECRET", "test-unit-secret-key")

from src.api.maas_security import (
    ApiKeyManager,
    OIDCClaims,
    OIDCValidator,
    PQCTokenSigner,
    RateLimiter,
)


# ---------------------------------------------------------------------------
# ApiKeyManager
# ---------------------------------------------------------------------------

class TestApiKeyManager:
    def test_generate_has_correct_prefix(self):
        key = ApiKeyManager.generate()
        assert key.startswith("x0t_")

    def test_generate_minimum_length(self):
        key = ApiKeyManager.generate()
        assert len(key) >= 16

    def test_generate_token_urlsafe_length(self):
        """secrets.token_urlsafe(32) produces ~43 base64url chars."""
        key = ApiKeyManager.generate()
        # prefix(4) + urlsafe(32 bytes ≈ 43 chars) = ~47 chars
        assert len(key) >= 40

    def test_generate_unique(self):
        """Each call returns a different key."""
        keys = {ApiKeyManager.generate() for _ in range(10)}
        assert len(keys) == 10

    def test_is_valid_format_valid_key(self):
        key = ApiKeyManager.generate()
        assert ApiKeyManager.is_valid_format(key) is True

    def test_is_valid_format_wrong_prefix(self):
        assert ApiKeyManager.is_valid_format("sk_test_abcdefghij") is False

    def test_is_valid_format_too_short(self):
        assert ApiKeyManager.is_valid_format("x0t_abc") is False

    def test_is_valid_format_not_a_string(self):
        assert ApiKeyManager.is_valid_format(12345) is False
        assert ApiKeyManager.is_valid_format(None) is False

    def test_is_valid_format_empty_string(self):
        assert ApiKeyManager.is_valid_format("") is False

    def test_hash_key_returns_sha256_hex(self):
        key = "x0t_testkey"
        result = ApiKeyManager.hash_key(key)
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert result == expected

    def test_hash_key_length(self):
        result = ApiKeyManager.hash_key(ApiKeyManager.generate())
        assert len(result) == 64  # SHA256 hex = 64 chars

    def test_hash_key_deterministic(self):
        key = "x0t_same_key"
        assert ApiKeyManager.hash_key(key) == ApiKeyManager.hash_key(key)

    def test_hash_key_different_keys_differ(self):
        h1 = ApiKeyManager.hash_key(ApiKeyManager.generate())
        h2 = ApiKeyManager.hash_key(ApiKeyManager.generate())
        assert h1 != h2


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_first_request_always_allowed(self):
        rl = RateLimiter(requests_per_minute=10, burst=5)
        assert rl.check("key-new") is True

    def test_first_request_initializes_bucket(self):
        rl = RateLimiter(requests_per_minute=10, burst=5)
        rl.check("key-init")
        assert "key-init" in rl._buckets

    def test_burst_requests_allowed(self):
        """burst=5 → can make 5 requests back-to-back."""
        rl = RateLimiter(requests_per_minute=60, burst=5)
        for _ in range(5):
            rl.check("key-burst")

    def test_rate_limit_exceeded_raises_429(self):
        """Exhaust burst then next request raises 429."""
        from fastapi import HTTPException
        rl = RateLimiter(requests_per_minute=60, burst=3)
        for _ in range(3):
            rl.check("key-exhaust")
        with pytest.raises(HTTPException) as exc:
            rl.check("key-exhaust")
        assert exc.value.status_code == 429

    def test_rate_limit_exception_has_retry_after_header(self):
        from fastapi import HTTPException
        rl = RateLimiter(requests_per_minute=60, burst=2)
        for _ in range(2):
            rl.check("key-header")
        with pytest.raises(HTTPException) as exc:
            rl.check("key-header")
        assert "Retry-After" in exc.value.headers

    def test_different_keys_independent(self):
        """Rate limit on key-a doesn't affect key-b."""
        from fastapi import HTTPException
        rl = RateLimiter(requests_per_minute=60, burst=2)
        for _ in range(2):
            rl.check("key-a")
        with pytest.raises(HTTPException):
            rl.check("key-a")
        # key-b should still work
        assert rl.check("key-b") is True

    def test_tokens_replenish_over_time(self):
        """After waiting, tokens are replenished."""
        rl = RateLimiter(requests_per_minute=600, burst=2)  # 10/sec
        for _ in range(2):
            rl.check("key-time")
        # Simulate time passing: manually set last_time to 1 second ago
        tokens, _ = rl._buckets["key-time"]
        rl._buckets["key-time"] = (tokens, time.monotonic() - 1.0)
        # Should be allowed now
        assert rl.check("key-time") is True

    def test_cleanup_removes_stale_entries(self):
        rl = RateLimiter(requests_per_minute=60, burst=5)
        rl.check("key-stale")
        # Make the entry look old
        tokens, _ = rl._buckets["key-stale"]
        rl._buckets["key-stale"] = (tokens, time.monotonic() - 7200)
        rl.cleanup(max_age_seconds=3600)
        assert "key-stale" not in rl._buckets

    def test_cleanup_keeps_fresh_entries(self):
        rl = RateLimiter(requests_per_minute=60, burst=5)
        rl.check("key-fresh")
        rl.cleanup(max_age_seconds=3600)
        assert "key-fresh" in rl._buckets


# ---------------------------------------------------------------------------
# PQCTokenSigner
# ---------------------------------------------------------------------------

class TestPQCTokenSigner:
    @pytest.fixture
    def signer(self):
        """
        PQCTokenSigner with PQC disabled (ImportError path → HMAC-SHA256 fallback).
        _get_hmac_secret is patched to always return a plain string — this avoids
        the test pollution issue where tests/api/conftest.py mocks hvac in sys.modules,
        causing hvac.Client() to return a MagicMock that doesn't raise, which makes
        _get_hmac_secret() return a MagicMock instead of a string.
        """
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            s = PQCTokenSigner()
            s._pqc_signer = None
            s._signing_keypair = None
        s._get_hmac_secret = lambda: "test-unit-secret-key"
        return s

    def test_sign_token_returns_dict(self, signer):
        result = signer.sign_token("mytoken123", "mesh-abc")
        assert isinstance(result, dict)

    def test_sign_token_has_token_field(self, signer):
        result = signer.sign_token("mytoken123", "mesh-abc")
        assert result["token"] == "mytoken123"

    def test_sign_token_hmac_algorithm(self, signer):
        result = signer.sign_token("mytoken123", "mesh-abc")
        assert result["algorithm"] == "HMAC-SHA256"

    def test_sign_token_not_pqc_secured(self, signer):
        result = signer.sign_token("mytoken123", "mesh-abc")
        assert result["pqc_secured"] is False

    def test_sign_token_signature_present(self, signer):
        result = signer.sign_token("mytoken123", "mesh-abc")
        assert "signature" in result
        assert len(result["signature"]) > 0

    def test_verify_token_valid(self, signer):
        token = "join-token-xyz"
        mesh_id = "mesh-test-001"
        signed = signer.sign_token(token, mesh_id)
        assert signer.verify_token(token, mesh_id, signed["signature"]) is True

    def test_verify_token_wrong_token(self, signer):
        signed = signer.sign_token("correct-token", "mesh-test")
        assert signer.verify_token("wrong-token", "mesh-test", signed["signature"]) is False

    def test_verify_token_wrong_mesh(self, signer):
        signed = signer.sign_token("mytoken", "mesh-real")
        assert signer.verify_token("mytoken", "mesh-fake", signed["signature"]) is False

    def test_verify_token_tampered_signature(self, signer):
        signed = signer.sign_token("mytoken", "mesh-abc")
        bad_sig = "a" * 64
        assert signer.verify_token("mytoken", "mesh-abc", bad_sig) is False

    def test_sign_different_meshes_different_sigs(self, signer):
        s1 = signer.sign_token("tok", "mesh-1")
        s2 = signer.sign_token("tok", "mesh-2")
        assert s1["signature"] != s2["signature"]

    def test_sign_same_inputs_deterministic(self, signer):
        """HMAC is deterministic for same inputs."""
        s1 = signer.sign_token("tok", "mesh-x")
        s2 = signer.sign_token("tok", "mesh-x")
        assert s1["signature"] == s2["signature"]


# ---------------------------------------------------------------------------
# OIDCValidator
# ---------------------------------------------------------------------------

class TestOIDCValidator:
    def test_disabled_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=False):
            # OIDC_ISSUER and OIDC_CLIENT_ID not set
            validator = OIDCValidator()
            assert validator.enabled is False

    def test_enabled_when_vars_set(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://accounts.example.com",
            "OIDC_CLIENT_ID": "my-client-id",
        }):
            validator = OIDCValidator()
            assert validator.enabled is True

    def test_get_config_when_disabled(self):
        with patch.dict(os.environ, {"OIDC_ISSUER": "", "OIDC_CLIENT_ID": ""}):
            validator = OIDCValidator()
            config = validator.get_config()
            assert config["enabled"] is False
            assert config["issuer"] is None
            assert config["client_id"] is None

    def test_get_config_scopes(self):
        validator = OIDCValidator()
        config = validator.get_config()
        assert "openid" in config["scopes"]
        assert "email" in config["scopes"]
        assert "profile" in config["scopes"]

    def test_validate_raises_501_when_disabled(self):
        from fastapi import HTTPException
        with patch.dict(os.environ, {"OIDC_ISSUER": "", "OIDC_CLIENT_ID": ""}):
            validator = OIDCValidator()
            with pytest.raises(HTTPException) as exc:
                validator.validate("fake-id-token")
            assert exc.value.status_code == 501

    def test_get_config_when_enabled(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://accounts.google.com",
            "OIDC_CLIENT_ID": "client-123",
        }):
            validator = OIDCValidator()
            config = validator.get_config()
            assert config["enabled"] is True
            assert config["issuer"] == "https://accounts.google.com"
            assert config["client_id"] == "client-123"

    def test_issuer_trailing_slash_stripped(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://accounts.google.com/",
            "OIDC_CLIENT_ID": "client-abc",
        }):
            validator = OIDCValidator()
            assert not validator.issuer.endswith("/")

    def test_validate_invalid_token_header_raises_401(self):
        from fastapi import HTTPException
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://accounts.example.com",
            "OIDC_CLIENT_ID": "client-xyz",
        }):
            validator = OIDCValidator()
            # Mock _fetch_jwks to avoid network call
            validator._fetch_jwks = MagicMock(return_value={"keys": []})
            with pytest.raises(HTTPException) as exc:
                validator.validate("not-a-valid-jwt")
            assert exc.value.status_code == 401

    def test_oidc_claims_dataclass(self):
        claims = OIDCClaims(
            sub="user-123",
            email="user@example.com",
            name="Test User",
            issuer="https://accounts.example.com",
            raw={"sub": "user-123"},
        )
        assert claims.sub == "user-123"
        assert claims.email == "user@example.com"
        assert claims.name == "Test User"
