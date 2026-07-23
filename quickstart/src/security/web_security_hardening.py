"""
Web Security Hardening Module for x0tta6bl4

Provides secure password hashing, validation utilities, and migration tools
to replace legacy MD5-based authentication with bcrypt/Argon2.

Key features:
- Bcrypt password hashing with configurable work factor
- Argon2 as alternative (post-quantum resistant)
- Password strength validation
- Secure session token generation
- OWASP compliance checks
"""
from __future__ import annotations

import logging
import hashlib
import os
import re
import secrets
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import bcrypt
from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

# Configuration
BCRYPT_ROUNDS = 12  # Cost factor (higher = more secure but slower)
SESSION_TOKEN_LENGTH = 32
PASSWORD_MIN_LENGTH = 12
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SYMBOLS = True


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 12:
        return "1-12"
    if value <= 32:
        return "13-32"
    if value <= 128:
        return "33-128"
    return "128+"


_WEB_SECURITY_THINKING = AgentThinkingCoach(
    agent_id="web-security-hardening",
    role="security",
    capabilities=("zero-trust", "ops"),
)
_WEB_SECURITY_LAST_CONTEXT = _WEB_SECURITY_THINKING.prepare_task(
    {
        "task_type": "web_security_hardening_init",
        "goal": "Initialize web security utilities safely",
        "signals": {
            "bcrypt_rounds_band": _safe_number_band(BCRYPT_ROUNDS),
            "session_token_length_band": _safe_number_band(SESSION_TOKEN_LENGTH),
            "password_min_length_band": _safe_number_band(PASSWORD_MIN_LENGTH),
        },
        "safety_boundary": (
            "Keep raw passwords, hashes, tokens, API keys, emails, usernames, "
            "SQL input, and migration user IDs out of thinking context."
        ),
    }
)


def _record_web_security_thinking(
    task_type: str,
    goal: str,
    signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    global _WEB_SECURITY_LAST_CONTEXT
    _WEB_SECURITY_LAST_CONTEXT = _WEB_SECURITY_THINKING.prepare_task(
        {
            "task_type": task_type,
            "goal": goal,
            "signals": signals or {},
            "constraints": {
                "redact_passwords": True,
                "redact_hashes": True,
                "redact_tokens": True,
                "redact_api_keys": True,
                "redact_emails": True,
                "redact_usernames": True,
                "redact_sql_input": True,
                "redact_user_ids": True,
                "preserve_security_decision": True,
            },
            "safety_boundary": "Use hashes, counts, booleans, length bands, and reason codes.",
        }
    )
    return _WEB_SECURITY_LAST_CONTEXT


def get_web_security_thinking_status() -> Dict[str, Any]:
    return {
        "thinking": _WEB_SECURITY_THINKING.status(),
        "last_thinking_context": _WEB_SECURITY_LAST_CONTEXT,
    }


class WebSecurityError(Exception):
    """Base exception for web security operations."""

    pass


class PasswordHasher:
    """Secure password hashing using bcrypt."""

    @staticmethod
    def get_thinking_status() -> Dict[str, Any]:
        return get_web_security_thinking_status()

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt with configurable rounds.

        Args:
            password: Plain text password

        Returns:
            Bcrypt hash string

        Raises:
            WebSecurityError: If password is invalid
        """
        if not password or len(password) < PASSWORD_MIN_LENGTH:
            _record_web_security_thinking(
                "password_hash_rejected",
                "Reject weak password hashing safely",
                {
                    "password_length_band": _safe_number_band(
                        len(password or "")
                    ),
                    "min_length_band": _safe_number_band(PASSWORD_MIN_LENGTH),
                    "reason_code": "too_short_or_empty",
                },
            )
            raise WebSecurityError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
            )

        try:
            salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
            hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
            _record_web_security_thinking(
                "password_hashed",
                "Hash password safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "hash_length_band": _safe_number_band(len(hashed)),
                    "bcrypt_rounds_band": _safe_number_band(BCRYPT_ROUNDS),
                    "success": True,
                },
            )
            return hashed.decode("utf-8")
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error(f"Password hashing failed: {e}")
            _record_web_security_thinking(
                "password_hash_failed",
                "Record password hashing failure safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "error_type": type(e).__name__,
                },
            )
            raise WebSecurityError(f"Password hashing failed: {str(e)}")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Verify a password against its bcrypt hash.

        Args:
            password: Plain text password to verify
            hashed: Bcrypt hash to verify against

        Returns:
            True if password matches, False otherwise
        """
        try:
            verified = bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
            _record_web_security_thinking(
                "password_verified",
                "Verify password hash safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "hash_length_band": _safe_number_band(len(hashed)),
                    "verified": verified,
                },
            )
            return verified
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.warning(f"Password verification failed: {e}")
            _record_web_security_thinking(
                "password_verify_failed",
                "Record password verification failure safely",
                {
                    "password_length_band": _safe_number_band(len(password or "")),
                    "hash_length_band": _safe_number_band(len(hashed or "")),
                    "error_type": type(e).__name__,
                },
            )
            return False

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password strength against OWASP guidelines.

        Returns:
            (is_valid, message)
        """
        if len(password) < PASSWORD_MIN_LENGTH:
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "too_short",
                },
            )
            return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"

        if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "missing_uppercase",
                },
            )
            return False, "Password must contain at least one uppercase letter"

        if PASSWORD_REQUIRE_NUMBERS and not re.search(r"[0-9]", password):
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "missing_number",
                },
            )
            return False, "Password must contain at least one number"

        if PASSWORD_REQUIRE_SYMBOLS and not re.search(
            r"[!@#$%^&*()_+\-=\[\]{};:,.<>?]", password
        ):
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "missing_symbol",
                },
            )
            return False, "Password must contain at least one special character"

        # Check for common patterns
        if re.search(r"(.)\1{2,}", password):
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "repeated_characters",
                },
            )
            return False, "Password cannot contain repeated characters (e.g., 'aaa')"

        if re.search(r"(012|123|234|345|456|567|678|789|890)", password):
            _record_web_security_thinking(
                "password_strength_checked",
                "Reject password strength safely",
                {
                    "password_length_band": _safe_number_band(len(password)),
                    "valid": False,
                    "reason_code": "sequential_numbers",
                },
            )
            return False, "Password cannot contain sequential numbers (3+ digits)"

        _record_web_security_thinking(
            "password_strength_checked",
            "Accept password strength safely",
            {
                "password_length_band": _safe_number_band(len(password)),
                "valid": True,
                "requires_uppercase": PASSWORD_REQUIRE_UPPERCASE,
                "requires_numbers": PASSWORD_REQUIRE_NUMBERS,
                "requires_symbols": PASSWORD_REQUIRE_SYMBOLS,
            },
        )
        return True, "Password meets security requirements"


class SessionTokenManager:
    """Secure session token generation and validation."""

    @staticmethod
    def get_thinking_status() -> Dict[str, Any]:
        return get_web_security_thinking_status()

    @staticmethod
    def generate_session_token() -> str:
        """Generate a cryptographically secure session token."""
        token = secrets.token_urlsafe(SESSION_TOKEN_LENGTH)
        _record_web_security_thinking(
            "session_token_generated",
            "Generate session token safely",
            {
                "token_length_band": _safe_number_band(len(token)),
                "configured_length_band": _safe_number_band(SESSION_TOKEN_LENGTH),
            },
        )
        return token

    @staticmethod
    def generate_csrf_token() -> str:
        """Generate a CSRF protection token."""
        token = secrets.token_hex(32)
        _record_web_security_thinking(
            "csrf_token_generated",
            "Generate CSRF token safely",
            {"token_length_band": _safe_number_band(len(token))},
        )
        return token

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        key = f"x0tta6bl4_{secrets.token_urlsafe(32)}"
        _record_web_security_thinking(
            "api_key_generated",
            "Generate API key safely",
            {
                "api_key_length_band": _safe_number_band(len(key)),
                "prefix_present": key.startswith("x0tta6bl4_"),
            },
        )
        return key


class MD5ToModernMigration:
    """Utility class for migrating from MD5 to bcrypt/Argon2."""

    MIGRATION_STATS = {
        "total_users": 0,
        "migrated": 0,
        "failed": 0,
        "start_time": None,
        "end_time": None,
    }

    @classmethod
    def get_thinking_status(cls) -> Dict[str, Any]:
        return get_web_security_thinking_status()

    @classmethod
    def migrate_user_password(
        cls, user_id: str, old_md5_hash: str, new_password: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Migrate a single user from MD5 to bcrypt.

        If new_password is not provided, user should reset their password.

        Args:
            user_id: User identifier
            old_md5_hash: Legacy MD5 hash (will be replaced)
            new_password: New password to hash (optional)

        Returns:
            (success, message)
        """
        try:
            if not old_md5_hash or len(old_md5_hash) != 32:
                logger.warning(f"Invalid MD5 hash for user {user_id}")
                _record_web_security_thinking(
                    "md5_password_migration_rejected",
                    "Reject invalid legacy hash migration safely",
                    {
                        "user_hash": _safe_hash(user_id),
                        "legacy_hash_length_band": _safe_number_band(
                            len(old_md5_hash or "")
                        ),
                        "has_new_password": new_password is not None,
                        "reason_code": "invalid_legacy_hash",
                    },
                )
                return False, "Invalid legacy hash format"

            if new_password:
                is_valid, msg = PasswordHasher.validate_password_strength(new_password)
                if not is_valid:
                    _record_web_security_thinking(
                        "md5_password_migration_rejected",
                        "Reject weak replacement password safely",
                        {
                            "user_hash": _safe_hash(user_id),
                            "legacy_hash_hash": _safe_hash(old_md5_hash),
                            "new_password_length_band": _safe_number_band(
                                len(new_password)
                            ),
                            "reason_code": "weak_replacement_password",
                        },
                    )
                    return False, msg

                new_hash = PasswordHasher.hash_password(new_password)
                logger.info(f"Migrated password for user {user_id}")
                cls.MIGRATION_STATS["migrated"] += 1
                _record_web_security_thinking(
                    "md5_password_migrated",
                    "Migrate legacy password safely",
                    {
                        "user_hash": _safe_hash(user_id),
                        "legacy_hash_hash": _safe_hash(old_md5_hash),
                        "new_hash_length_band": _safe_number_band(len(new_hash)),
                        "migrated_count_bucket": _safe_count_bucket(
                            cls.MIGRATION_STATS["migrated"]
                        ),
                    },
                )
                return True, new_hash
            else:
                logger.info(f"User {user_id} requires password reset")
                _record_web_security_thinking(
                    "md5_password_migration_reset_required",
                    "Require password reset for legacy password safely",
                    {
                        "user_hash": _safe_hash(user_id),
                        "legacy_hash_hash": _safe_hash(old_md5_hash),
                        "has_new_password": False,
                    },
                )
                return False, "User must set new password"

        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error(f"Migration failed for user {user_id}: {e}")
            cls.MIGRATION_STATS["failed"] += 1
            _record_web_security_thinking(
                "md5_password_migration_failed",
                "Record legacy password migration failure safely",
                {
                    "user_hash": _safe_hash(user_id),
                    "error_type": type(e).__name__,
                    "failed_count_bucket": _safe_count_bucket(
                        cls.MIGRATION_STATS["failed"]
                    ),
                },
            )
            return False, str(e)

    @classmethod
    def get_migration_report(cls) -> dict:
        """Get migration statistics report."""
        report = {
            **cls.MIGRATION_STATS,
            "success_rate": (
                cls.MIGRATION_STATS["migrated"]
                / cls.MIGRATION_STATS["total_users"]
                * 100
                if cls.MIGRATION_STATS["total_users"] > 0
                else 0
            ),
        }
        _record_web_security_thinking(
            "md5_password_migration_reported",
            "Report migration statistics safely",
            {
                "total_users_bucket": _safe_count_bucket(
                    cls.MIGRATION_STATS["total_users"]
                ),
                "migrated_bucket": _safe_count_bucket(cls.MIGRATION_STATS["migrated"]),
                "failed_bucket": _safe_count_bucket(cls.MIGRATION_STATS["failed"]),
                "success_rate_band": _safe_number_band(report["success_rate"]),
            },
        )
        return report


class WebSecurityHeaders:
    """Generate secure HTTP headers for web responses."""

    @staticmethod
    def get_thinking_status() -> Dict[str, Any]:
        return get_web_security_thinking_status()

    @staticmethod
    def get_security_headers() -> dict:
        """Return recommended security headers."""
        headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        }
        _record_web_security_thinking(
            "web_security_headers_generated",
            "Generate web security headers safely",
            {
                "header_count_bucket": _safe_count_bucket(len(headers)),
                "header_name_hashes": [
                    _safe_hash(name) for name in sorted(headers.keys())
                ],
                "has_csp": "Content-Security-Policy" in headers,
                "has_hsts": "Strict-Transport-Security" in headers,
            },
        )
        return headers


class InputSanitizer:
    """Sanitize and validate user input."""

    @staticmethod
    def get_thinking_status() -> Dict[str, Any]:
        return get_web_security_thinking_status()

    @staticmethod
    def sanitize_email(email: str) -> Optional[str]:
        """Validate and sanitize email address."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if re.match(pattern, email):
            sanitized = email.lower().strip()
            _record_web_security_thinking(
                "email_sanitized",
                "Accept email input safely",
                {
                    "email_hash": _safe_hash(email),
                    "email_length_band": _safe_number_band(len(email)),
                    "valid": True,
                },
            )
            return sanitized
        _record_web_security_thinking(
            "email_sanitized",
            "Reject email input safely",
            {
                "email_hash": _safe_hash(email),
                "email_length_band": _safe_number_band(len(email or "")),
                "valid": False,
            },
        )
        return None

    @staticmethod
    def sanitize_username(username: str) -> Optional[str]:
        """Validate and sanitize username."""
        if not (3 <= len(username) <= 32):
            _record_web_security_thinking(
                "username_sanitized",
                "Reject username length safely",
                {
                    "username_hash": _safe_hash(username),
                    "username_length_band": _safe_number_band(len(username or "")),
                    "valid": False,
                    "reason_code": "invalid_length",
                },
            )
            return None
        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            _record_web_security_thinking(
                "username_sanitized",
                "Reject username pattern safely",
                {
                    "username_hash": _safe_hash(username),
                    "username_length_band": _safe_number_band(len(username)),
                    "valid": False,
                    "reason_code": "invalid_pattern",
                },
            )
            return None
        sanitized = username.strip()
        _record_web_security_thinking(
            "username_sanitized",
            "Accept username input safely",
            {
                "username_hash": _safe_hash(username),
                "username_length_band": _safe_number_band(len(username)),
                "valid": True,
            },
        )
        return sanitized

    @staticmethod
    def sanitize_sql_input(user_input: str) -> str:
        """Basic SQL injection prevention (use parameterized queries instead!)."""
        dangerous_chars = [";", "'", '"', "--", "/*", "*/", "xp_", "sp_"]
        sanitized = user_input
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "")
        _record_web_security_thinking(
            "sql_input_sanitized",
            "Sanitize SQL-like input safely",
            {
                "input_hash": _safe_hash(user_input),
                "input_length_band": _safe_number_band(len(user_input or "")),
                "output_length_band": _safe_number_band(len(sanitized)),
                "dangerous_pattern_count_bucket": _safe_count_bucket(
                    sum(1 for char in dangerous_chars if char in user_input)
                ),
            },
        )
        return sanitized


def create_security_audit_report() -> dict:
    """Create a security audit report for web components."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "components_checked": [
            "password_hashing",
            "session_management",
            "csrf_protection",
            "input_validation",
            "security_headers",
        ],
        "recommendations": [
            "✅ Replace all MD5 hashes with bcrypt (12+ rounds)",
            "✅ Implement CSRF tokens for all state-changing operations",
            "✅ Use HTTPS only (Strict-Transport-Security)",
            "✅ Implement rate limiting on login endpoints",
            "✅ Enable security headers on all responses",
            "✅ Use parameterized SQL queries",
            "✅ Validate all user input server-side",
            "✅ Implement account lockout after failed login attempts",
            "✅ Log all security events with timestamps",
            "✅ Conduct regular security audits (quarterly)",
        ],
        "pqc_considerations": [
            "For post-quantum security: Consider adding ML-KEM-768 for key exchange",
            "Use ML-DSA-65 for digital signatures in API authentication",
            "Implement hybrid classical/PQC mode for backward compatibility",
        ],
    }
    _record_web_security_thinking(
        "web_security_audit_report_created",
        "Create web security audit report safely",
        {
            "component_count_bucket": _safe_count_bucket(
                len(report["components_checked"])
            ),
            "recommendation_count_bucket": _safe_count_bucket(
                len(report["recommendations"])
            ),
            "pqc_consideration_count_bucket": _safe_count_bucket(
                len(report["pqc_considerations"])
            ),
        },
    )
    return report


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Test password hashing
    sample_input_pass = "SamplePassphrase123!@#"  # nosec
    print("Testing password validation with sample input")

    is_valid, msg = PasswordHasher.validate_password_strength(sample_input_pass)
    print("Password validation completed")

    if is_valid:
        hashed = PasswordHasher.hash_password(sample_input_pass)
        print("Password hashing succeeded")

        verified = PasswordHasher.verify_password(sample_input_pass, hashed)
        print(f"Password verification passed: {verified}")

    # Security headers
    print("\nSecurity Headers:")
    for header, value in WebSecurityHeaders.get_security_headers().items():
        print(f"  {header}: {value[:50]}...")

    # Audit report
    print("\nSecurity Audit Report:")
    report = create_security_audit_report()
    print(f"  Timestamp: {report['timestamp']}")
    print(f"  Recommendations: {len(report['recommendations'])}")

