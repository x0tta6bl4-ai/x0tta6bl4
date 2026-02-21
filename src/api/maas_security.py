"""
MaaS Security Layer — x0tta6bl4
================================

API key management, rate limiting per key,
PQC-signed mesh join tokens, and OIDC SSO validation.
"""

import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import hvac
import httpx
import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class ApiKeyManager:
    """
    API key issuance and validation.

    Key format: x0t_{base64url(32 bytes)}
    Total length: ~48 characters
    """

    PREFIX = "x0t_"

    @staticmethod
    def generate() -> str:
        """Generate a new cryptographically secure API key."""
        return f"{ApiKeyManager.PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def is_valid_format(key: str) -> bool:
        """Check if key matches expected format."""
        return (
            isinstance(key, str)
            and len(key) >= 16
            and key.startswith(ApiKeyManager.PREFIX)
        )

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash API key for storage (never store plaintext)."""
        return hashlib.sha256(key.encode()).hexdigest()


class RateLimiter:
    """
    Per-API-key rate limiting.

    Uses token bucket algorithm for smooth rate limiting.
    """

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.rpm = requests_per_minute
        self.burst = burst
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key → (tokens, last_time)

    def check(self, api_key: str) -> bool:
        """
        Check if request is allowed.

        Returns True if allowed, raises HTTPException if rate limited.
        """
        now = time.monotonic()

        if api_key not in self._buckets:
            self._buckets[api_key] = (self.burst - 1, now)
            return True

        tokens, last_time = self._buckets[api_key]
        elapsed = now - last_time
        tokens = min(self.burst, tokens + elapsed * (self.rpm / 60.0))

        if tokens < 1:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": str(int(60 / self.rpm))},
            )

        self._buckets[api_key] = (tokens - 1, now)
        return True

    def cleanup(self, max_age_seconds: float = 3600.0):
        """Remove stale entries."""
        now = time.monotonic()
        stale = [
            k for k, (_, t) in self._buckets.items()
            if now - t > max_age_seconds
        ]
        for k in stale:
            del self._buckets[k]


class PQCTokenSigner:
    """
    PQC-signed join tokens for mesh networks.
    Secrets are retrieved from HashiCorp Vault.
    """

    def __init__(self):
        self._pqc_signer = None
        self._signing_keypair = None
        self.vault_url = os.getenv("VAULT_URL", "http://localhost:8200")
        self.vault_token = os.getenv("VAULT_TOKEN", "x0t-master-token")
        self._init_pqc()

    def _get_hmac_secret(self) -> str:
        """Retrieve HMAC secret from Vault with env fallback for dev."""
        try:
            client = hvac.Client(url=self.vault_url, token=self.vault_token)
            # Use 'maas' mount, 'signing-key' path
            read_response = client.secrets.kv.v2.read_secret_version(path='signing-key', mount_point='maas')
            return read_response['data']['data']['secret']
        except Exception as e:
            logger.debug(f"[MaaS Security] Vault access failed, using fallback: {e}")
            return os.getenv("MAAS_TOKEN_SECRET", "dev-fallback-secret-non-prod")

    def _init_pqc(self):
        """Try to initialize PQC signer."""
        try:
            from src.libx0t.security.pqc_core import PQCDigitalSignature

            self._pqc_signer = PQCDigitalSignature()
            self._signing_keypair = self._pqc_signer.generate_keypair(
                key_id="maas-token-signer"
            )
            logger.info("[MaaS Security] PQC ML-DSA-65 token signing initialized")
        except (ImportError, Exception) as e:
            logger.warning(
                f"[MaaS Security] PQC not available, using HMAC-SHA256: {e}"
            )
            self._pqc_signer = None

    def sign_token(self, token: str, mesh_id: str) -> Dict:
        """Sign a join token with PQC or dynamic HMAC fallback."""
        payload = f"{mesh_id}:{token}".encode()

        if self._pqc_signer and self._signing_keypair:
            try:
                sig = self._pqc_signer.sign(
                    payload,
                    self._signing_keypair.secret_key,
                    key_id="maas-token-signer",
                )
                return {
                    "token": token,
                    "algorithm": "ML-DSA-65",
                    "signature": sig.signature_bytes.hex()[:64] + "...",
                    "signer_key_id": sig.signer_key_id,
                    "pqc_secured": True,
                }
            except Exception as e:
                logger.error(f"[MaaS Security] PQC signing failed: {e}")

        # Dynamic HMAC-SHA256 from Vault
        import hmac
        secret = self._get_hmac_secret()
        sig = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        return {
            "token": token,
            "algorithm": "HMAC-SHA256",
            "signature": sig[:64],
            "pqc_secured": False,
        }

    def verify_token(self, token: str, mesh_id: str, signature: str) -> bool:
        """Verify a signed join token using dynamic secret."""
        payload = f"{mesh_id}:{token}".encode()

        if self._pqc_signer and self._signing_keypair:
            try:
                return self._pqc_signer.verify(
                    payload,
                    bytes.fromhex(signature),
                    self._signing_keypair.public_key,
                )
            except Exception:
                pass

        # Dynamic HMAC verification
        import hmac
        secret = self._get_hmac_secret()
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature[:64], expected[:64])


class OIDCClaims:
    """Validated OIDC token claims."""

    def __init__(self, sub: str, email: str, name: str, issuer: str, raw: Dict[str, Any]):
        self.sub = sub
        self.email = email
        self.name = name
        self.issuer = issuer
        self.raw = raw


class OIDCValidator:
    """
    OIDC JWT validation for enterprise SSO.

    Supports any standards-compliant OIDC provider:
    Google, Azure AD, Okta, Auth0, Keycloak, etc.

    Config (env vars):
        OIDC_ISSUER      — e.g. https://accounts.google.com
        OIDC_CLIENT_ID   — your app's client_id (audience claim)
        OIDC_AUDIENCE    — override audience check (optional)
    """

    WELL_KNOWN_SUFFIX = "/.well-known/openid-configuration"
    JWKS_CACHE_TTL = 3600  # seconds

    def __init__(self):
        self.issuer = os.getenv("OIDC_ISSUER", "").rstrip("/")
        self.client_id = os.getenv("OIDC_CLIENT_ID", "")
        self.audience = os.getenv("OIDC_AUDIENCE", self.client_id)
        self._jwks_uri: Optional[str] = None
        self._jwks_cache: Optional[Dict] = None
        self._jwks_fetched_at: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)

    def get_config(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "issuer": self.issuer or None,
            "client_id": self.client_id or None,
            "scopes": ["openid", "email", "profile"],
        }

    def _fetch_jwks(self) -> Dict:
        """Fetch JWKS from provider. Cached for JWKS_CACHE_TTL seconds."""
        now = time.monotonic()
        if self._jwks_cache and (now - self._jwks_fetched_at) < self.JWKS_CACHE_TTL:
            return self._jwks_cache

        if not self._jwks_uri:
            discovery_url = self.issuer + self.WELL_KNOWN_SUFFIX
            try:
                resp = httpx.get(discovery_url, timeout=5.0)
                resp.raise_for_status()
                self._jwks_uri = resp.json()["jwks_uri"]
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"OIDC discovery failed: {e}",
                )

        try:
            resp = httpx.get(self._jwks_uri, timeout=5.0)
            resp.raise_for_status()
            self._jwks_cache = resp.json()
            self._jwks_fetched_at = now
            return self._jwks_cache
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"JWKS fetch failed: {e}",
            )

    def validate(self, id_token: str) -> OIDCClaims:
        """
        Validate an OIDC ID token and return verified claims.
        Raises HTTPException on failure.
        """
        if not self.enabled:
            raise HTTPException(
                status_code=501,
                detail="OIDC SSO is not configured. Set OIDC_ISSUER and OIDC_CLIENT_ID.",
            )

        jwks = self._fetch_jwks()

        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.exceptions.DecodeError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token header: {e}")

        # Find matching key
        kid = header.get("kid")
        signing_key = None
        for key_data in jwks.get("keys", []):
            if not kid or key_data.get("kid") == kid:
                try:
                    signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                    break
                except Exception:
                    continue

        if signing_key is None:
            raise HTTPException(status_code=401, detail="No matching JWKS key found")

        try:
            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["sub", "iat", "exp"]},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="OIDC token expired")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="OIDC token audience mismatch")
        except jwt.InvalidIssuerError:
            raise HTTPException(status_code=401, detail="OIDC token issuer mismatch")
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=f"OIDC token invalid: {e}")

        sub = claims.get("sub", "")
        email = claims.get("email", "") or claims.get("preferred_username", "") or sub
        name = claims.get("name", "") or claims.get("given_name", "") or email

        if not sub:
            raise HTTPException(status_code=401, detail="OIDC token missing 'sub' claim")

        return OIDCClaims(sub=sub, email=email, name=name, issuer=self.issuer, raw=claims)


# Singleton instances
api_key_manager = ApiKeyManager()
rate_limiter = RateLimiter(requests_per_minute=60, burst=10)
token_signer = PQCTokenSigner()
oidc_validator = OIDCValidator()
