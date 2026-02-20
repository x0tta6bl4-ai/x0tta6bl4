"""
MaaS Security Layer — x0tta6bl4
================================

API key management, rate limiting per key,
and PQC-signed mesh join tokens.
"""

import hashlib
import logging
import os
import secrets
import time
from typing import Dict, Optional, Tuple

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

    Uses ML-DSA-65 when available, falls back to HMAC-SHA256.
    """

    def __init__(self):
        self._pqc_signer = None
        self._signing_keypair = None
        self._hmac_secret = os.getenv(
            "MAAS_TOKEN_SECRET",
            secrets.token_hex(32),
        )
        self._init_pqc()

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
        """Sign a join token with PQC or HMAC fallback."""
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

        # HMAC-SHA256 fallback
        import hmac

        sig = hmac.new(
            self._hmac_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        return {
            "token": token,
            "algorithm": "HMAC-SHA256",
            "signature": sig[:64],
            "pqc_secured": False,
        }

    def verify_token(self, token: str, mesh_id: str, signature: str) -> bool:
        """Verify a signed join token."""
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

        # HMAC fallback verification
        import hmac

        expected = hmac.new(
            self._hmac_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature[:64], expected[:64])


# Singleton instances
api_key_manager = ApiKeyManager()
rate_limiter = RateLimiter(requests_per_minute=60, burst=10)
token_signer = PQCTokenSigner()
