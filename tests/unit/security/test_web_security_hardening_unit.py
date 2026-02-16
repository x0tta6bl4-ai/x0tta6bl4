import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""Unit tests for src/security/web_security_hardening.py"""

from unittest.mock import MagicMock, patch

import pytest


class TestWebSecurityError:
    """Tests for WebSecurityError exception."""

    def test_is_exception(self):
        from src.security.web_security_hardening import WebSecurityError

        assert issubclass(WebSecurityError, Exception)

    def test_message(self):
        from src.security.web_security_hardening import WebSecurityError

        err = WebSecurityError("test error")
        assert str(err) == "test error"


class TestPasswordHasher:
    """Tests for PasswordHasher class."""

    def test_hash_password_success(self):
        from src.security.web_security_hardening import PasswordHasher

        mock_salt = b"$2b$12$saltsaltsaltsaltsaltsa"
        mock_hash = b"$2b$12$saltsaltsaltsaltsaltsa/hashedpasswordhash123"

        with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
            mock_bcrypt.gensalt.return_value = mock_salt
            mock_bcrypt.hashpw.return_value = mock_hash

            result = PasswordHasher.hash_password("StrongPass123!@#")
            assert result == mock_hash.decode("utf-8")
            mock_bcrypt.gensalt.assert_called_once_with(rounds=12)
            mock_bcrypt.hashpw.assert_called_once_with(
                "StrongPass123!@#".encode("utf-8"), mock_salt
            )

    def test_hash_password_too_short(self):
        from src.security.web_security_hardening import (PasswordHasher,
                                                         WebSecurityError)

        with pytest.raises(WebSecurityError, match="at least 12 characters"):
            PasswordHasher.hash_password("short")

    def test_hash_password_empty(self):
        from src.security.web_security_hardening import (PasswordHasher,
                                                         WebSecurityError)

        with pytest.raises(WebSecurityError, match="at least 12 characters"):
            PasswordHasher.hash_password("")

    def test_hash_password_none(self):
        from src.security.web_security_hardening import (PasswordHasher,
                                                         WebSecurityError)

        with pytest.raises(WebSecurityError):
            PasswordHasher.hash_password(None)

    def test_hash_password_bcrypt_failure(self):
        from src.security.web_security_hardening import (PasswordHasher,
                                                         WebSecurityError)

        with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
            mock_bcrypt.gensalt.side_effect = RuntimeError("bcrypt error")

            with pytest.raises(WebSecurityError, match="Password hashing failed"):
                PasswordHasher.hash_password("StrongPass123!@#")

    def test_verify_password_match(self):
        from src.security.web_security_hardening import PasswordHasher

        with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
            mock_bcrypt.checkpw.return_value = True
            result = PasswordHasher.verify_password("password", "$2b$12$hash")
            assert result is True
            mock_bcrypt.checkpw.assert_called_once_with(b"password", b"$2b$12$hash")

    def test_verify_password_no_match(self):
        from src.security.web_security_hardening import PasswordHasher

        with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
            mock_bcrypt.checkpw.return_value = False
            result = PasswordHasher.verify_password("wrong", "$2b$12$hash")
            assert result is False

    def test_verify_password_exception_returns_false(self):
        from src.security.web_security_hardening import PasswordHasher

        with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
            mock_bcrypt.checkpw.side_effect = ValueError("corrupt hash")
            result = PasswordHasher.verify_password("password", "bad")
            assert result is False

    def test_validate_strength_valid(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("Str0ng!Pass_x")
        assert is_valid is True
        assert "meets security requirements" in msg

    def test_validate_strength_too_short(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("Sh0rt!")
        assert is_valid is False
        assert "at least 12" in msg

    def test_validate_strength_no_uppercase(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("alllowercase1!")
        assert is_valid is False
        assert "uppercase" in msg

    def test_validate_strength_no_number(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("NoNumbersHere!")
        assert is_valid is False
        assert "number" in msg

    def test_validate_strength_no_symbol(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("NoSymbolsHere1")
        assert is_valid is False
        assert "special character" in msg

    def test_validate_strength_repeated_chars(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("Paaassword12!@")
        assert is_valid is False
        assert "repeated" in msg

    def test_validate_strength_sequential_numbers(self):
        from src.security.web_security_hardening import PasswordHasher

        is_valid, msg = PasswordHasher.validate_password_strength("Password123!xy")
        assert is_valid is False
        assert "sequential" in msg


class TestSessionTokenManager:
    """Tests for SessionTokenManager class."""

    def test_generate_session_token(self):
        from src.security.web_security_hardening import SessionTokenManager

        with patch("src.security.web_security_hardening.secrets") as mock_secrets:
            mock_secrets.token_urlsafe.return_value = "mock_session_token_abc123"
            token = SessionTokenManager.generate_session_token()
            assert token == "mock_session_token_abc123"
            mock_secrets.token_urlsafe.assert_called_once_with(32)

    def test_generate_csrf_token(self):
        from src.security.web_security_hardening import SessionTokenManager

        with patch("src.security.web_security_hardening.secrets") as mock_secrets:
            mock_secrets.token_hex.return_value = "abcdef0123456789" * 4
            token = SessionTokenManager.generate_csrf_token()
            assert token == "abcdef0123456789" * 4
            mock_secrets.token_hex.assert_called_once_with(32)

    def test_generate_api_key_prefix(self):
        from src.security.web_security_hardening import SessionTokenManager

        with patch("src.security.web_security_hardening.secrets") as mock_secrets:
            mock_secrets.token_urlsafe.return_value = "random_key_data"
            key = SessionTokenManager.generate_api_key()
            assert key.startswith("x0tta6bl4_")
            assert key == "x0tta6bl4_random_key_data"
            mock_secrets.token_urlsafe.assert_called_once_with(32)


class TestMD5ToModernMigration:
    """Tests for MD5ToModernMigration class."""

    def setup_method(self):
        """Reset migration stats before each test."""
        from src.security.web_security_hardening import MD5ToModernMigration

        MD5ToModernMigration.MIGRATION_STATS = {
            "total_users": 0,
            "migrated": 0,
            "failed": 0,
            "start_time": None,
            "end_time": None,
        }

    def test_migrate_invalid_md5_hash_empty(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        success, msg = MD5ToModernMigration.migrate_user_password("user1", "")
        assert success is False
        assert "Invalid legacy hash" in msg

    def test_migrate_invalid_md5_hash_wrong_length(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        success, msg = MD5ToModernMigration.migrate_user_password("user1", "short")
        assert success is False
        assert "Invalid legacy hash" in msg

    def test_migrate_no_new_password(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        success, msg = MD5ToModernMigration.migrate_user_password("user1", md5_hash)
        assert success is False
        assert "must set new password" in msg

    def test_migrate_with_weak_password(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        success, msg = MD5ToModernMigration.migrate_user_password(
            "user1", md5_hash, "weak"
        )
        assert success is False
        assert "at least 12" in msg

    def test_migrate_with_strong_password(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        mock_hash = "$2b$12$hashed_output"

        with patch(
            "src.security.web_security_hardening.PasswordHasher.hash_password",
            return_value=mock_hash,
        ):
            success, new_hash = MD5ToModernMigration.migrate_user_password(
                "user1", md5_hash, "Str0ng!Pass_x"
            )
            assert success is True
            assert new_hash == mock_hash
            assert MD5ToModernMigration.MIGRATION_STATS["migrated"] == 1

    def test_migrate_exception_increments_failed(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        md5_hash = "d41d8cd98f00b204e9800998ecf8427e"

        with patch(
            "src.security.web_security_hardening.PasswordHasher.validate_password_strength",
            return_value=(True, "ok"),
        ):
            with patch(
                "src.security.web_security_hardening.PasswordHasher.hash_password",
                side_effect=RuntimeError("hash fail"),
            ):
                success, msg = MD5ToModernMigration.migrate_user_password(
                    "user1", md5_hash, "Str0ng!Pass_x"
                )
                assert success is False
                assert "hash fail" in msg
                assert MD5ToModernMigration.MIGRATION_STATS["failed"] == 1

    def test_get_migration_report_zero_users(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        report = MD5ToModernMigration.get_migration_report()
        assert report["success_rate"] == 0
        assert report["total_users"] == 0
        assert report["migrated"] == 0

    def test_get_migration_report_with_users(self):
        from src.security.web_security_hardening import MD5ToModernMigration

        MD5ToModernMigration.MIGRATION_STATS["total_users"] = 10
        MD5ToModernMigration.MIGRATION_STATS["migrated"] = 7
        MD5ToModernMigration.MIGRATION_STATS["failed"] = 3
        report = MD5ToModernMigration.get_migration_report()
        assert report["success_rate"] == 70.0
        assert report["total_users"] == 10


class TestWebSecurityHeaders:
    """Tests for WebSecurityHeaders class."""

    def test_get_security_headers_keys(self):
        from src.security.web_security_hardening import WebSecurityHeaders

        headers = WebSecurityHeaders.get_security_headers()
        assert "Strict-Transport-Security" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers
        assert "Content-Security-Policy" in headers

    def test_hsts_header_value(self):
        from src.security.web_security_hardening import WebSecurityHeaders

        headers = WebSecurityHeaders.get_security_headers()
        hsts = headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_frame_options_deny(self):
        from src.security.web_security_hardening import WebSecurityHeaders

        headers = WebSecurityHeaders.get_security_headers()
        assert headers["X-Frame-Options"] == "DENY"

    def test_content_type_nosniff(self):
        from src.security.web_security_hardening import WebSecurityHeaders

        headers = WebSecurityHeaders.get_security_headers()
        assert headers["X-Content-Type-Options"] == "nosniff"

    def test_csp_default_self(self):
        from src.security.web_security_hardening import WebSecurityHeaders

        headers = WebSecurityHeaders.get_security_headers()
        csp = headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp


class TestInputSanitizer:
    """Tests for InputSanitizer class."""

    def test_sanitize_email_valid(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_email("User@Example.COM")
        assert result == "user@example.com"

    def test_sanitize_email_valid_with_plus(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_email("user+tag@example.com")
        assert result == "user+tag@example.com"

    def test_sanitize_email_invalid_no_at(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_email("userexample.com")
        assert result is None

    def test_sanitize_email_invalid_no_domain(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_email("user@")
        assert result is None

    def test_sanitize_email_invalid_with_space(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_email("user @example.com")
        assert result is None

    def test_sanitize_username_valid(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_username("good_user-1")
        assert result == "good_user-1"

    def test_sanitize_username_too_short(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_username("ab")
        assert result is None

    def test_sanitize_username_too_long(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_username("a" * 33)
        assert result is None

    def test_sanitize_username_invalid_chars(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_username("bad user!")
        assert result is None

    def test_sanitize_sql_input_strips_semicolons(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_sql_input("SELECT * FROM users;")
        assert ";" not in result

    def test_sanitize_sql_input_strips_quotes(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_sql_input("' OR '1'='1")
        assert "'" not in result

    def test_sanitize_sql_input_strips_comments(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_sql_input("admin'--")
        assert "--" not in result
        assert "'" not in result

    def test_sanitize_sql_input_strips_stored_proc(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_sql_input("xp_cmdshell")
        assert "xp_" not in result

    def test_sanitize_sql_input_clean_string_unchanged(self):
        from src.security.web_security_hardening import InputSanitizer

        result = InputSanitizer.sanitize_sql_input("hello world")
        assert result == "hello world"


class TestCreateSecurityAuditReport:
    """Tests for create_security_audit_report function."""

    def test_report_has_timestamp(self):
        from src.security.web_security_hardening import \
            create_security_audit_report

        report = create_security_audit_report()
        assert "timestamp" in report
        assert isinstance(report["timestamp"], str)

    def test_report_has_components(self):
        from src.security.web_security_hardening import \
            create_security_audit_report

        report = create_security_audit_report()
        assert "components_checked" in report
        components = report["components_checked"]
        assert "password_hashing" in components
        assert "session_management" in components
        assert "input_validation" in components

    def test_report_has_recommendations(self):
        from src.security.web_security_hardening import \
            create_security_audit_report

        report = create_security_audit_report()
        assert "recommendations" in report
        assert len(report["recommendations"]) > 0

    def test_report_has_pqc_considerations(self):
        from src.security.web_security_hardening import \
            create_security_audit_report

        report = create_security_audit_report()
        assert "pqc_considerations" in report
        assert len(report["pqc_considerations"]) > 0
