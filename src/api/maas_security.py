"""
MaaS Security Layer — x0tta6bl4
================================

API key management, rate limiting per key,
PQC-signed mesh join tokens, and OIDC SSO validation.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

import hvac
import httpx
import jwt
from fastapi import HTTPException

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _is_production_mode() -> bool:
    """Detect production mode from standard environment switches."""
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    if env in {"production", "prod", "live"}:
        return True
    return os.getenv("X0TTA6BL4_PRODUCTION", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_key(key: str, stored_hash: str | None) -> bool:
        if not key or not stored_hash:
            return False
        return secrets.compare_digest(ApiKeyManager.hash_key(key), stored_hash)

    @staticmethod
    def fingerprint_from_hash(stored_hash: str | None) -> str:
        return (stored_hash or "")[:12]


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
        self.vault_token = os.getenv("VAULT_TOKEN", "")
        self._ephemeral_hmac_secret: Optional[str] = None
        self._pqc_initialized = False
        self.source_agent = "maas-pqc-token-signer"
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "pqc", "api-security"),
            extra_techniques=("reverse_planning",),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return hashlib.sha256(value).hexdigest()
        return hashlib.sha256(
            str(value).encode("utf-8", errors="replace")
        ).hexdigest()

    def _record_thinking(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "maas_pqc_token_signer_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                "raw_join_token_redacted": True,
                "raw_mesh_id_redacted": True,
                "raw_secret_redacted": True,
                "hmac_fallback_is_not_pqc_secured": True,
                "local_signature_is_not_external_trust_finality": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local MaaS token signing decisions, algorithm choice, "
                "fallback reason, and hashed identifiers. HMAC-SHA256 fallback is "
                "not PQC-secured and no returned token proves external trust finality."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose token signer thinking state without tokens, mesh IDs, or secrets."""
        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
            "pqc_initialized": self._pqc_initialized,
            "pqc_signer_available": self._pqc_signer is not None,
        }

    def _get_hmac_secret(self) -> str:
        """Retrieve HMAC secret from Vault with env fallback for dev."""
        try:
            client = hvac.Client(url=self.vault_url, token=self.vault_token)
            # Use 'maas' mount, 'signing-key' path
            read_response = client.secrets.kv.v2.read_secret_version(path='signing-key', mount_point='maas')
            self._record_thinking(
                operation="get_hmac_secret",
                goal="load MaaS HMAC fallback secret from Vault",
                constraints={
                    "secret_source": "vault",
                    "vault_url_hash": self._hash_value(self.vault_url),
                },
            )
            return read_response['data']['data']['secret']
        except Exception as e:
            logger.debug(f"[MaaS Security] Vault access failed, using fallback: {e}")
            env_secret = os.getenv("MAAS_TOKEN_SECRET", "").strip()
            if env_secret:
                self._record_thinking(
                    operation="get_hmac_secret",
                    goal="use configured environment HMAC fallback secret",
                    constraints={
                        "secret_source": "env",
                        "vault_error_type": type(e).__name__,
                    },
                )
                return env_secret
            if _is_production_mode():
                self._record_thinking(
                    operation="get_hmac_secret",
                    goal="fail closed because production HMAC fallback secret is missing",
                    constraints={
                        "secret_source": "missing",
                        "production_mode": True,
                        "vault_error_type": type(e).__name__,
                    },
                )
                raise RuntimeError(
                    "MAAS_TOKEN_SECRET must be configured when Vault is unavailable in production"
                ) from e
            if not self._ephemeral_hmac_secret:
                self._ephemeral_hmac_secret = secrets.token_hex(32)
                logger.warning(
                    "[MaaS Security] Vault unavailable and MAAS_TOKEN_SECRET is unset. "
                    "Using ephemeral in-memory fallback secret for non-production mode."
                )
            self._record_thinking(
                operation="get_hmac_secret",
                goal="use ephemeral non-production HMAC fallback secret",
                constraints={
                    "secret_source": "ephemeral_non_production",
                    "production_mode": False,
                    "vault_error_type": type(e).__name__,
                },
            )
            return self._ephemeral_hmac_secret

    def _init_pqc(self):
        """Try to initialize PQC signer."""
        if self._pqc_initialized:
            return
        try:
            from src.libx0t.security.pqc_core import PQCDigitalSignature

            self._pqc_signer = PQCDigitalSignature()
            self._signing_keypair = self._pqc_signer.generate_keypair(
                key_id="maas-token-signer"
            )
            self._pqc_initialized = True
            logger.info("[MaaS Security] PQC ML-DSA-65 token signing initialized")
            self._record_thinking(
                operation="init_pqc",
                goal="initialize local PQC token signer",
                constraints={"pqc_signer_available": True, "algorithm": "ML-DSA-65"},
            )
        except (ImportError, Exception) as e:
            logger.warning(
                f"[MaaS Security] PQC not available, using HMAC-SHA256: {e}"
            )
            self._pqc_signer = None
            self._pqc_initialized = True
            self._record_thinking(
                operation="init_pqc",
                goal="record PQC signer unavailable and require explicit HMAC fallback label",
                constraints={
                    "pqc_signer_available": False,
                    "fallback_algorithm": "HMAC-SHA256",
                    "error_type": type(e).__name__,
                },
            )

    def sign_token(self, token: str, mesh_id: str) -> Dict:
        """Sign a join token with PQC or dynamic HMAC fallback."""
        self._init_pqc()
        payload = f"{mesh_id}:{token}".encode()
        self._record_thinking(
            operation="sign_token",
            goal="sign MaaS mesh join token without exposing token or mesh ID",
            constraints={
                "token_hash": self._hash_value(token),
                "mesh_id_hash": self._hash_value(mesh_id),
                "pqc_signer_available": self._pqc_signer is not None,
            },
        )

        if self._pqc_signer and self._signing_keypair:
            try:
                sig = self._pqc_signer.sign(
                    payload,
                    self._signing_keypair.secret_key,
                    key_id="maas-token-signer",
                )
                self._record_thinking(
                    operation="sign_token",
                    goal="return local PQC token signature with explicit claim boundary",
                    constraints={
                        "token_hash": self._hash_value(token),
                        "mesh_id_hash": self._hash_value(mesh_id),
                        "algorithm": "ML-DSA-65",
                        "pqc_secured": True,
                    },
                )
                return {
                    "token": token,
                    "algorithm": "ML-DSA-65",
                    # Keep full signature to make verification cryptographically sound.
                    "signature": sig.signature_bytes.hex(),
                    "signer_key_id": sig.signer_key_id,
                    "pqc_secured": True,
                    "pqc_fallback": False,
                    "security_claim_boundary": (
                        "Local ML-DSA-65 signature only; not external trust finality."
                    ),
                }
            except Exception as e:
                logger.error(f"[MaaS Security] PQC signing failed: {e}")
                self._record_thinking(
                    operation="sign_token",
                    goal="record PQC signing failure before HMAC fallback",
                    constraints={
                        "token_hash": self._hash_value(token),
                        "mesh_id_hash": self._hash_value(mesh_id),
                        "error_type": type(e).__name__,
                        "fallback_algorithm": "HMAC-SHA256",
                    },
                )

        # Dynamic HMAC-SHA256 from Vault
        import hmac
        secret = self._get_hmac_secret()
        sig = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        self._record_thinking(
            operation="sign_token",
            goal="return HMAC fallback token signature with non-PQC claim boundary",
            constraints={
                "token_hash": self._hash_value(token),
                "mesh_id_hash": self._hash_value(mesh_id),
                "algorithm": "HMAC-SHA256",
                "pqc_secured": False,
            },
        )

        return {
            "token": token,
            "algorithm": "HMAC-SHA256",
            "signature": sig[:64],
            "pqc_secured": False,
            "pqc_fallback": True,
            "security_claim_boundary": (
                "HMAC-SHA256 fallback only; not PQC-secured or external trust finality."
            ),
        }

    def verify_token(self, token: str, mesh_id: str, signature: str) -> bool:
        """Verify a signed join token using dynamic secret."""
        self._init_pqc()
        payload = f"{mesh_id}:{token}".encode()
        signature_hex = (signature or "").strip()
        self._record_thinking(
            operation="verify_token",
            goal="verify MaaS mesh join token signature without exposing inputs",
            constraints={
                "token_hash": self._hash_value(token),
                "mesh_id_hash": self._hash_value(mesh_id),
                "signature_hash": self._hash_value(signature_hex),
                "pqc_signer_available": self._pqc_signer is not None,
            },
        )

        if self._pqc_signer and self._signing_keypair:
            try:
                result = self._pqc_signer.verify(
                    payload,
                    bytes.fromhex(signature_hex),
                    self._signing_keypair.public_key,
                )
                self._record_thinking(
                    operation="verify_token",
                    goal="record local PQC token verification result",
                    constraints={
                        "algorithm": "ML-DSA-65",
                        "verification_result": bool(result),
                    },
                )
                return result
            except Exception:
                pass

        # Dynamic HMAC verification
        import hmac
        secret = self._get_hmac_secret()
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        result = hmac.compare_digest(signature_hex[:64], expected[:64])
        self._record_thinking(
            operation="verify_token",
            goal="record HMAC fallback token verification result",
            constraints={
                "algorithm": "HMAC-SHA256",
                "pqc_secured": False,
                "verification_result": bool(result),
            },
        )
        return result


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

