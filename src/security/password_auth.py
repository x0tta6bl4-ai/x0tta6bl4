"""
Shared password helpers for MaaS auth flows.

Provides:
  - bcrypt hashing for new passwords
  - backward-compatible verification for legacy plaintext values
  - signal to rehash legacy values after successful login
"""

from __future__ import annotations

import secrets
from typing import Tuple

import bcrypt


def hash_password(password: str) -> str:
    """Hash plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> Tuple[bool, bool]:
    """
    Verify password with bcrypt.

    Returns:
        (is_valid, should_rehash)

    Note: plaintext fallback removed — all passwords must be bcrypt hashes.
    Accounts with non-bcrypt hashes (e.g. OIDC sentinel) will fail verification,
    which is the correct and secure behaviour.
    """
    if not stored_hash.startswith("$2"):
        # Not a bcrypt hash (could be OIDC sentinel "OIDC_USER" or legacy plaintext).
        # Reject unconditionally — do not accept plaintext credentials.
        return False, False
    try:
        is_valid = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        return is_valid, False
    except Exception:
        return False, False
