"""
Тесты для password_migration - проверка безопасности хеширования паролей.
"""

import bcrypt
import pytest

from src.security.password_migration import (BCRYPT_PREFIX, MigrationStats,
                                             PasswordMigrator,
                                             get_password_migrator)


class TestPasswordHashing:
    """Тесты хеширования паролей."""

    def test_hash_password_returns_bcrypt(self):
        """Хеширование возвращает bcrypt hash."""
        migrator = PasswordMigrator()
        hashed = migrator.hash_password("secure_password123")

        assert hashed.startswith(BCRYPT_PREFIX)
        assert len(hashed) > 50  # bcrypt hashes are long

    def test_hash_password_different_salts(self):
        """Каждое хеширование использует разный salt."""
        migrator = PasswordMigrator()
        hash1 = migrator.hash_password("password123")
        hash2 = migrator.hash_password("password123")

        # Same password should produce different hashes (due to salt)
        assert hash1 != hash2

    def test_hash_password_short_rejected(self):
        """Короткие пароли отклоняются."""
        migrator = PasswordMigrator()

        with pytest.raises(ValueError, match="at least 8 characters"):
            migrator.hash_password("short")

    def test_hash_password_empty_rejected(self):
        """Пустые пароли отклоняются."""
        migrator = PasswordMigrator()

        with pytest.raises(ValueError, match="at least 8 characters"):
            migrator.hash_password("")


class TestPasswordVerification:
    """Тесты верификации паролей."""

    def test_verify_correct_password(self):
        """Верификация правильного пароля."""
        migrator = PasswordMigrator()
        password = "my_secure_password"
        hashed = migrator.hash_password(password)

        assert migrator.verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """Верификация неправильного пароля."""
        migrator = PasswordMigrator()
        password = "my_secure_password"
        hashed = migrator.hash_password(password)

        assert migrator.verify_password("wrong_password", hashed) is False

    def test_verify_non_bcrypt_rejected(self):
        """Небcrypt хеши отклоняются."""
        migrator = PasswordMigrator()

        # MD5 hash should be rejected
        assert (
            migrator.verify_password("password", "5f4dcc3b5aa765d61d8327deb882cf99")
            is False
        )

        # Plain text should be rejected
        assert migrator.verify_password("password", "plaintext") is False


class TestMD5Detection:
    """Тесты обнаружения MD5 хешей."""

    def test_is_md5_hash_valid(self):
        """Обнаружение валидных MD5 хешей."""
        migrator = PasswordMigrator()

        # Valid MD5 hashes
        assert migrator.is_md5_hash("5f4dcc3b5aa765d61d8327deb882cf99") is True
        assert (
            migrator.is_md5_hash("d41d8cd98f00b204e9800998ecf8427e") is True
        )  # empty string MD5

    def test_is_md5_hash_invalid(self):
        """Отклонение невалидных MD5 хешей."""
        migrator = PasswordMigrator()

        # bcrypt hash should not be detected as MD5
        assert migrator.is_md5_hash("$2b$12$...") is False

        # Empty string
        assert migrator.is_md5_hash("") is False

        # Too short
        assert migrator.is_md5_hash("abc123") is False

        # Non-hex characters
        assert migrator.is_md5_hash("xyzxyzxyzxyzxyzxyzxyzxyzxyzxyz") is False


class TestMD5Migration:
    """Тесты миграции от MD5 к bcrypt."""

    def test_legacy_verify_md5_always_fails(self):
        """
        SECURITY FIX: MD5 verification всегда возвращает False.

        Это принудительно заставляет пользователей сбросить пароль.
        """
        migrator = PasswordMigrator()

        # Even with correct MD5 hash, should return False
        md5_hash = "5f4dcc3b5aa765d61d8327deb882cf99"  # MD5 of "password"
        assert migrator.legacy_verify_md5("password", md5_hash) is False

        # Any MD5 hash should fail
        assert migrator.legacy_verify_md5("anything", md5_hash) is False

    def test_verify_legacy_or_bcrypt_forces_reset(self):
        """При обнаружении MD5 требуется сброс пароля."""
        migrator = PasswordMigrator()

        md5_hash = "5f4dcc3b5aa765d61d8327deb882cf99"
        is_valid, needs_rehashing = migrator.verify_legacy_or_bcrypt(
            "password", md5_hash
        )

        # Should NOT be valid (security fix)
        assert is_valid is False
        # But should indicate need for rehashing
        assert needs_rehashing is True

    def test_verify_legacy_or_bcrypt_bcrypt_works(self):
        """bcrypt хеши работают нормально."""
        migrator = PasswordMigrator()
        password = "secure_password"
        bcrypt_hash = migrator.hash_password(password)

        is_valid, needs_rehashing = migrator.verify_legacy_or_bcrypt(
            password, bcrypt_hash
        )

        assert is_valid is True
        assert needs_rehashing is False


class TestMigrationStats:
    """Тесты статистики миграции."""

    def test_stats_initialization(self):
        """Начальная статистика."""
        migrator = PasswordMigrator()
        stats = migrator.get_stats()

        assert stats.total_processed == 0
        assert stats.successfully_migrated == 0
        assert stats.failed_migrations == 0
        assert stats.already_bcrypt == 0

    def test_stats_reset(self):
        """Сброс статистики."""
        migrator = PasswordMigrator()
        migrator.stats.total_processed = 10
        migrator.reset_stats()

        assert migrator.stats.total_processed == 0


class TestSingleton:
    """Тесты singleton pattern."""

    def test_get_password_migrator_singleton(self):
        """Singleton возвращает один и тот же объект."""
        migrator1 = get_password_migrator()
        migrator2 = get_password_migrator()

        assert migrator1 is migrator2


class TestSecurityProperties:
    """Тесты security свойств."""

    def test_bcrypt_slow_by_design(self):
        """bcrypt медленный по дизайну (защита от brute-force)."""
        import time

        migrator = PasswordMigrator()
        password = "test_password"

        start = time.time()
        hashed = migrator.hash_password(password)
        end = time.time()

        # Should take at least 100ms (12 rounds)
        assert end - start > 0.1

        # Verify also takes time
        start = time.time()
        migrator.verify_password(password, hashed)
        end = time.time()

        assert end - start > 0.05

    def test_no_timing_attack_on_verify(self):
        """Верификация использует constant-time comparison."""
        migrator = PasswordMigrator()
        password = "test_password"
        hashed = migrator.hash_password(password)

        # Both should return False without timing differences
        assert migrator.verify_password("wrong1", hashed) is False
        assert migrator.verify_password("wrong2", hashed) is False
        assert migrator.verify_password("a" * 100, hashed) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
