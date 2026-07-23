"""
SignedRemediationCommand — cryptographically signed remediation commands.

Wraps every healing action in a signed structure (ML-DSA or HMAC-based)
to prevent forged commands via EventBus injection.

Usage:
    cmd = SignedRemediationCommand.sign("rotate all pqc keys", signing_key=key)
    assert cmd.verify(verification_key=vk)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

SIGNED_CMD_SCHEMA = "x0tta6bl4.self_healing.signed_command.v1"
NONCE_BYTES = 16
MAX_NONCE_AGE = 300  # 5 minutes

# In-memory nonce dedup set (class-level, shared across all instances)
_seen_nonces: set[str] = set()


@dataclass
class SignedRemediationCommand:
    """A remediation action wrapped in a verifiable signature envelope.

    Fields:
        action: Human-readable action string (e.g. "rotate all pqc keys")
        timestamp: Unix timestamp of signing
        nonce: Unique nonce for replay protection
        signature: ML-DSA or HMAC signature bytes (empty before signing)
        signing_key_id: Identifier for the key used to sign
        schema: Schema version for forward compatibility
    """

    action: str
    timestamp: float
    nonce: str
    signature: bytes = b""
    signing_key_id: str = ""
    schema: str = SIGNED_CMD_SCHEMA

    @classmethod
    def sign(
        cls,
        action: str,
        *,
        signing_key: bytes,
        signing_key_id: str = "",
        sign_fn: Optional[Callable[[bytes, bytes], bytes]] = None,
        now: Optional[float] = None,
    ) -> SignedRemediationCommand:
        """Create and sign a remediation command.

        Args:
            action: Action string to sign
            signing_key: Key material for signing (HMAC or ML-DSA secret key)
            signing_key_id: Identifier for the signing key
            sign_fn: Custom signing function (key, payload) -> signature.
                      If None, defaults to HMAC-SHA256.
            now: Override timestamp (for deterministic tests)
        """
        ts = now if now is not None else time.time()
        nonce = hashlib.sha256(os.urandom(NONCE_BYTES)).hexdigest()[:16]

        cmd = cls(
            action=action,
            timestamp=ts,
            nonce=nonce,
            signing_key_id=signing_key_id,
        )

        payload = cmd._signing_payload()
        if sign_fn is not None:
            sig = sign_fn(signing_key, payload)
        else:
            sig = hmac.new(signing_key, payload, hashlib.sha256).digest()

        cmd.signature = sig
        return cmd

    def verify(
        self,
        *,
        verification_key: bytes,
        verify_fn: Optional[Callable[[bytes, bytes, bytes], bool]] = None,
        max_age: float = MAX_NONCE_AGE,
    ) -> bool:
        """Verify this command's signature and freshness.

        Args:
            verification_key: Key for verification (HMAC key or ML-DSA public key)
            verify_fn: Custom verify function (key, payload, signature) -> bool.
                       If None, defaults to HMAC-SHA256 constant-time compare.
            max_age: Maximum age in seconds for the command

        Returns:
            True if signature valid, nonce fresh, and not expired
        """
        # Replay protection
        global _seen_nonces
        if self.nonce in _seen_nonces:
            logger.warning("Replay attack detected: nonce %s already seen", self.nonce[:8])
            return False
        _seen_nonces.add(self.nonce)
        # Cap the dedup set to avoid memory leak
        if len(_seen_nonces) > 10000:
            _seen_nonces.clear()

        # Freshness
        age = time.time() - self.timestamp
        if age > max_age:
            logger.warning("Command expired: age=%.1fs > max_age=%.1fs", age, max_age)
            return False
        if age < 0:
            logger.warning("Command from the future: age=%.1fs", age)
            return False

        # Signature verification
        payload = self._signing_payload()
        if verify_fn is not None:
            return verify_fn(verification_key, payload, self.signature)
        else:
            expected = hmac.new(verification_key, payload, hashlib.sha256).digest()
            return hmac.compare_digest(expected, self.signature)

    def _signing_payload(self) -> bytes:
        """Deterministic canonical payload for signature."""
        data = {
            "schema": self.schema,
            "action": self.action,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "signing_key_id": self.signing_key_id,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def clear_nonces(cls) -> None:
        """Clear the dedup set (for testing)."""
        global _seen_nonces
        _seen_nonces.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for transport."""
        return {
            "schema": self.schema,
            "action": self.action,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "signature": self.signature.hex() if self.signature else "",
            "signing_key_id": self.signing_key_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignedRemediationCommand:
        """Deserialize from dict."""
        return cls(
            action=data["action"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            signature=bytes.fromhex(data.get("signature", "")),
            signing_key_id=data.get("signing_key_id", ""),
        )
