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
    Verify password with bcrypt and support legacy plaintext fallback.

    Returns:
        (is_valid, should_rehash)
    """
    try:
        is_valid = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        return is_valid, False
    except ValueError:
        # Legacy rows could contain plaintext password (historical behavior).
        if isinstance(stored_hash, str) and secrets.compare_digest(password, stored_hash):
            return True, True
        return False, False
    except Exception:
        return False, False
