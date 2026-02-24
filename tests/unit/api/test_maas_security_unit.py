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
            # Mark as already initialised so the real _init_pqc won't overwrite
            # our None values when sign_token/verify_token call self._init_pqc().
            s._pqc_initialized = True
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

    # ------------------------------------------------------------------
    # _fetch_jwks branches
    # ------------------------------------------------------------------

    def test_fetch_jwks_returns_cache_when_fresh(self):
        """Cache hit path: _jwks_cache populated and TTL not expired."""
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://cache.example.com",
            "OIDC_CLIENT_ID": "c1",
        }):
            v = OIDCValidator()
        cached = {"keys": [{"kid": "cached-k"}]}
        v._jwks_cache = cached
        v._jwks_fetched_at = time.monotonic()  # just now → still fresh
        v._jwks_uri = "https://cache.example.com/jwks"
        result = v._fetch_jwks()
        assert result is cached

    def test_fetch_jwks_discovery_failure_raises_503(self):
        """No _jwks_uri, httpx.get raises → HTTPException 503."""
        from fastapi import HTTPException
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://disc-fail.example.com",
            "OIDC_CLIENT_ID": "c2",
        }):
            v = OIDCValidator()
        v._jwks_uri = None
        v._jwks_cache = None
        with patch("httpx.get", side_effect=Exception("connection refused")):
            with pytest.raises(HTTPException) as exc:
                v._fetch_jwks()
            assert exc.value.status_code == 503
            assert "discovery" in exc.value.detail.lower()

    def test_fetch_jwks_fetch_failure_raises_503(self):
        """_jwks_uri set but httpx.get for JWKS raises → HTTPException 503."""
        from fastapi import HTTPException
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://jwks-fail.example.com",
            "OIDC_CLIENT_ID": "c3",
        }):
            v = OIDCValidator()
        v._jwks_uri = "https://jwks-fail.example.com/jwks"
        v._jwks_cache = None
        with patch("httpx.get", side_effect=Exception("JWKS endpoint down")):
            with pytest.raises(HTTPException) as exc:
                v._fetch_jwks()
            assert exc.value.status_code == 503
            assert "jwks" in exc.value.detail.lower()

    # ------------------------------------------------------------------
    # validate() branches requiring a valid JWT header but failing later
    # ------------------------------------------------------------------

    def _enabled_validator(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://test.example.com",
            "OIDC_CLIENT_ID": "test-client",
        }):
            return OIDCValidator()

    def test_validate_no_matching_jwks_key_raises_401(self):
        """kid in header doesn't match any key in JWKS → 401."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "other-kid"}]})
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "no-such-kid", "alg": "RS256"}):
            with pytest.raises(HTTPException) as exc:
                v.validate("header.payload.sig")
            assert exc.value.status_code == 401
            assert "No matching JWKS key" in exc.value.detail

    def test_validate_expired_token_raises_401(self):
        """jwt.ExpiredSignatureError → HTTPException 401 with 'expired'."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode",
                                  side_effect=pyjwt.ExpiredSignatureError()):
                    with pytest.raises(HTTPException) as exc:
                        v.validate("expired.jwt.token")
                    assert exc.value.status_code == 401
                    assert "expired" in exc.value.detail.lower()

    def test_validate_audience_mismatch_raises_401(self):
        """jwt.InvalidAudienceError → HTTPException 401 with 'audience'."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode",
                                  side_effect=pyjwt.InvalidAudienceError()):
                    with pytest.raises(HTTPException) as exc:
                        v.validate("aud.jwt.token")
                    assert exc.value.status_code == 401
                    assert "audience" in exc.value.detail.lower()

    def test_validate_issuer_mismatch_raises_401(self):
        """jwt.InvalidIssuerError → HTTPException 401 with 'issuer'."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode",
                                  side_effect=pyjwt.InvalidIssuerError()):
                    with pytest.raises(HTTPException) as exc:
                        v.validate("iss.jwt.token")
                    assert exc.value.status_code == 401
                    assert "issuer" in exc.value.detail.lower()

    def test_validate_generic_jwt_error_raises_401(self):
        """Generic jwt.PyJWTError → HTTPException 401 with 'invalid'."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode",
                                  side_effect=pyjwt.PyJWTError("bad sig")):
                    with pytest.raises(HTTPException) as exc:
                        v.validate("bad.jwt.token")
                    assert exc.value.status_code == 401
                    assert "invalid" in exc.value.detail.lower()

    def test_validate_missing_sub_claim_raises_401(self):
        """Claims without 'sub' → HTTPException 401 mentioning 'sub'."""
        import jwt as pyjwt
        from fastapi import HTTPException
        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        claims_no_sub = {"email": "user@test.com", "iat": 1, "exp": 9999999999}
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode", return_value=claims_no_sub):
                    with pytest.raises(HTTPException) as exc:
                        v.validate("nosub.jwt.token")
                    assert exc.value.status_code == 401
                    assert "sub" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# OIDCValidator — additional branch coverage
# ---------------------------------------------------------------------------

class TestOIDCValidatorAdditionalBranches:
    """Cover branches not exercised by TestOIDCValidator."""

    def _enabled_validator(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://extra.example.com",
            "OIDC_CLIENT_ID": "extra-client",
        }):
            return OIDCValidator()

    def test_fetch_jwks_with_preknown_uri_success(self):
        """_jwks_uri already set, cache stale → fetches JWKS directly (lines 266-271)."""
        import jwt as pyjwt
        v = self._enabled_validator()
        v._jwks_uri = "https://extra.example.com/jwks"
        v._jwks_cache = None
        v._jwks_fetched_at = 0.0

        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_jwks
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = v._fetch_jwks()

        assert result == fake_jwks
        assert v._jwks_cache == fake_jwks
        # Only one httpx.get call (skipped discovery since _jwks_uri was set)
        assert mock_get.call_count == 1
        mock_get.assert_called_once_with("https://extra.example.com/jwks", timeout=5.0)

    def test_validate_no_kid_in_header_uses_first_valid_key(self):
        """When header has no 'kid', code tries all JWKS keys (not kid → True branch)."""
        import jwt as pyjwt
        from fastapi import HTTPException

        v = self._enabled_validator()
        mock_key = MagicMock()
        jwks = {"keys": [{"kty": "RSA"}]}  # No 'kid' in key → no-kid matching
        v._fetch_jwks = MagicMock(return_value=jwks)
        claims = {"sub": "user-1", "email": "u@t.com", "name": "U", "iat": 1, "exp": 9999999999}

        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"alg": "RS256"}):  # no 'kid' field
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode", return_value=claims):
                    result = v.validate("no-kid.jwt.token")

        assert result.sub == "user-1"

    def test_validate_preferred_username_fallback_for_email(self):
        """When 'email' claim is empty, preferred_username is used."""
        import jwt as pyjwt

        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        # email is empty → should fall back to preferred_username
        claims = {
            "sub": "u1",
            "email": "",
            "preferred_username": "myuser",
            "name": "My User",
            "iat": 1,
            "exp": 9999999999,
        }
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode", return_value=claims):
                    result = v.validate("pu.jwt.token")

        assert result.email == "myuser"

    def test_validate_given_name_fallback_for_name(self):
        """When 'name' claim is empty, given_name is used."""
        import jwt as pyjwt

        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        claims = {
            "sub": "u2",
            "email": "u2@test.com",
            "name": "",            # empty → should fall back to given_name
            "given_name": "Alice",
            "iat": 1,
            "exp": 9999999999,
        }
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode", return_value=claims):
                    result = v.validate("gn.jwt.token")

        assert result.name == "Alice"

    def test_validate_sub_used_as_email_fallback(self):
        """When both email and preferred_username are empty, sub is used as email."""
        import jwt as pyjwt

        v = self._enabled_validator()
        mock_key = MagicMock()
        v._fetch_jwks = MagicMock(return_value={"keys": [{"kid": "k1"}]})
        claims = {
            "sub": "sub-used-as-email",
            "email": "",
            "preferred_username": "",
            "name": "Test",
            "iat": 1,
            "exp": 9999999999,
        }
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"kid": "k1", "alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               return_value=mock_key):
                with patch.object(pyjwt, "decode", return_value=claims):
                    result = v.validate("sub-email.jwt.token")

        assert result.email == "sub-used-as-email"


# ---------------------------------------------------------------------------
# PQCTokenSigner — verify_token PQC exception path + _get_hmac_secret Vault
# ---------------------------------------------------------------------------

class TestPQCVerifyToken:
    """verify_token() branches: PQC verify raises → HMAC fallback."""

    def test_verify_token_pqc_raises_falls_through_to_hmac(self):
        """When PQC signer raises on verify(), falls through to HMAC check."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()
            signer._pqc_initialized = True  # prevent real _init_pqc from overwriting

        signer._get_hmac_secret = lambda: "test-secret"
        signer._pqc_signer = MagicMock()
        signer._pqc_signer.verify.side_effect = Exception("PQC verify failed")
        signer._signing_keypair = MagicMock()

        token = "join-token"
        mesh_id = "mesh-1"
        # Compute the expected HMAC signature as the signer would
        import hmac as hmac_mod
        import hashlib
        payload = f"{mesh_id}:{token}".encode()
        expected_sig = hmac_mod.new("test-secret".encode(), payload, hashlib.sha256).hexdigest()

        # verify_token with PQC raising should fall back to HMAC
        result = signer.verify_token(token, mesh_id, expected_sig)
        assert result is True

    def test_verify_token_hmac_mismatch_returns_false(self):
        """Wrong signature → HMAC comparison fails → returns False."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()

        signer._pqc_signer = None
        signer._signing_keypair = None
        signer._get_hmac_secret = lambda: "correct-secret"

        result = signer.verify_token("token", "mesh", "wrong-signature" * 4)
        assert result is False


# ---------------------------------------------------------------------------
# PQCTokenSigner — _get_hmac_secret Vault success path
# ---------------------------------------------------------------------------

class TestPQCTokenSignerVault:
    def test_get_hmac_secret_vault_success(self):
        """When Vault returns data, _get_hmac_secret returns the secret."""
        vault_response = {
            "data": {"data": {"secret": "vault-derived-secret"}}
        }
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = vault_response

        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()

        with patch("hvac.Client", return_value=mock_client):
            secret = signer._get_hmac_secret()

        assert secret == "vault-derived-secret"

    def test_get_hmac_secret_vault_failure_uses_env_fallback(self):
        """When Vault raises, _get_hmac_secret falls back to env var."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()

        with patch("hvac.Client", side_effect=Exception("vault down")):
            with patch.dict(os.environ, {"MAAS_TOKEN_SECRET": "env-fallback-secret"}):
                secret = signer._get_hmac_secret()

        assert secret == "env-fallback-secret"

    def test_sign_token_pqc_exception_falls_through_to_hmac(self):
        """PQC signer raises on sign() → falls through to HMAC-SHA256."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()
            signer._pqc_initialized = True  # prevent real _init_pqc from overwriting

        mock_pqc = MagicMock()
        mock_pqc.sign.side_effect = Exception("PQC unavailable")
        signer._pqc_signer = mock_pqc
        signer._signing_keypair = MagicMock()
        signer._get_hmac_secret = lambda: "test-secret"

        result = signer.sign_token("mytoken", "mesh-1")
        # Should fall back to HMAC
        assert result["algorithm"] == "HMAC-SHA256"
        assert result["pqc_secured"] is False


# ---------------------------------------------------------------------------
# PQC success paths and OIDC discovery cold-start
# ---------------------------------------------------------------------------

class TestPQCSuccessPaths:
    """Cover PQC sign/verify success paths (lines 147-160 and 182-188)."""

    def test_sign_token_pqc_success_returns_pqc_secured(self):
        """PQC signer and keypair present, sign() succeeds → pqc_secured=True."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()
            signer._pqc_initialized = True  # prevent real _init_pqc from overwriting

        mock_sig = MagicMock()
        mock_sig.signature_bytes = b"\xab" * 64
        mock_sig.signer_key_id = "maas-token-signer"
        mock_pqc = MagicMock()
        mock_pqc.sign.return_value = mock_sig
        signer._pqc_signer = mock_pqc
        signer._signing_keypair = MagicMock()

        result = signer.sign_token("tok1", "mesh-xyz")

        assert result["pqc_secured"] is True
        assert result["algorithm"] == "ML-DSA-65"
        assert result["token"] == "tok1"
        mock_pqc.sign.assert_called_once()

    def test_verify_token_pqc_success_returns_true(self):
        """PQC signer present, verify() returns True → verify_token returns True."""
        with patch("src.api.maas_security.PQCTokenSigner._init_pqc", lambda self: None):
            signer = PQCTokenSigner()
            signer._pqc_initialized = True  # prevent real _init_pqc from overwriting

        mock_pqc = MagicMock()
        mock_pqc.verify.return_value = True
        signer._pqc_signer = mock_pqc
        signer._signing_keypair = MagicMock()

        # Provide a valid hex signature (64 chars = 32 bytes)
        hex_sig = "ab" * 32
        result = signer.verify_token("tok1", "mesh-xyz", hex_sig)

        assert result is True
        mock_pqc.verify.assert_called_once()


class TestOIDCValidatorDiscoveryColdStart:
    """Cover _fetch_jwks() full cold-start path: discovery succeeds, then JWKS fetched."""

    def test_fetch_jwks_discovery_then_jwks_success(self):
        """_jwks_uri=None → discovery fetched → _jwks_uri set → JWKS fetched (lines 254-271)."""
        import jwt as pyjwt

        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://coldstart.example.com",
            "OIDC_CLIENT_ID": "cold-client",
        }):
            v = OIDCValidator()
        v._jwks_uri = None
        v._jwks_cache = None
        v._jwks_fetched_at = 0.0

        discovery_payload = {"jwks_uri": "https://coldstart.example.com/jwks"}
        jwks_payload = {"keys": [{"kid": "cs-k1", "kty": "RSA"}]}

        discovery_resp = MagicMock()
        discovery_resp.json.return_value = discovery_payload
        discovery_resp.raise_for_status = MagicMock()

        jwks_resp = MagicMock()
        jwks_resp.json.return_value = jwks_payload
        jwks_resp.raise_for_status = MagicMock()

        # First call → discovery URL, second call → JWKS URL
        with patch("httpx.get", side_effect=[discovery_resp, jwks_resp]) as mock_get:
            result = v._fetch_jwks()

        assert result == jwks_payload
        assert v._jwks_uri == "https://coldstart.example.com/jwks"
        assert mock_get.call_count == 2


class TestOIDCValidatorFromJwkException:
    """Cover the from_jwk() exception → continue path in validate() (line 304)."""

    def _enabled_validator(self):
        with patch.dict(os.environ, {
            "OIDC_ISSUER": "https://fromjwk.example.com",
            "OIDC_CLIENT_ID": "fromjwk-client",
        }):
            return OIDCValidator()

    def test_from_jwk_raises_continue_then_succeeds_with_next_key(self):
        """First key's from_jwk() raises, second key succeeds → claims returned.

        Uses a header with NO 'kid' field so the `not kid` branch is True and
        ALL keys in the JWKS are tried in order.
        """
        import jwt as pyjwt
        v = self._enabled_validator()
        # Two keys, no 'kid' filtering — all will be tried
        jwks = {"keys": [{"kty": "RSA"}, {"kty": "RSA"}]}
        v._fetch_jwks = MagicMock(return_value=jwks)

        good_key = MagicMock()
        claims = {
            "sub": "user-42", "email": "u@t.com", "name": "U", "iat": 1, "exp": 9999999999,
        }

        call_count = [0]

        def from_jwk_side_effect(key_data):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("bad jwk")
            return good_key

        # No 'kid' in header → not kid is True → tries all keys
        with patch.object(pyjwt, "get_unverified_header",
                          return_value={"alg": "RS256"}):
            with patch.object(pyjwt.algorithms.RSAAlgorithm, "from_jwk",
                               side_effect=from_jwk_side_effect):
                with patch.object(pyjwt, "decode", return_value=claims):
                    result = v.validate("test.jwt.token")

        # First key raised (continue), second key succeeded
        assert result.sub == "user-42"
        assert call_count[0] == 2
