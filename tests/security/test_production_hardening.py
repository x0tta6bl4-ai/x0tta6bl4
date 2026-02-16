import pytest

from src.security.production_hardening import (InputValidator,
                                               ProductionHardeningManager,
                                               RateLimiter, RateLimitPolicy,
                                               RequestAuditor,
                                               SecretVaultManager,
                                               SecurityViolation)


class TestSecretVaultManager:
    def test_store_and_retrieve_secret(self):
        vault = SecretVaultManager()
        vault.store_secret("db_password", "secret123")
        assert vault.retrieve_secret("db_password") is not None

    def test_retrieve_nonexistent_secret(self):
        vault = SecretVaultManager()
        assert vault.retrieve_secret("nonexistent") is None

    def test_rotate_secret(self):
        vault = SecretVaultManager()
        vault.store_secret("api_key", "old_key")
        assert vault.rotate_secret("api_key", "new_key")
        assert not vault.rotate_secret("nonexistent", "value")


class TestRateLimiter:
    def test_set_policy(self):
        limiter = RateLimiter()
        policy = RateLimitPolicy(max_requests=10, window_seconds=60)
        limiter.set_policy("api", policy)
        assert limiter.policies["api"] == policy

    def test_allow_within_limit(self):
        limiter = RateLimiter()
        policy = RateLimitPolicy(max_requests=5, window_seconds=60)
        limiter.set_policy("api", policy)

        for _ in range(5):
            assert limiter.is_allowed("api", "client1")

    def test_reject_exceeds_limit(self):
        limiter = RateLimiter()
        policy = RateLimitPolicy(max_requests=3, window_seconds=60)
        limiter.set_policy("api", policy)

        for _ in range(3):
            assert limiter.is_allowed("api", "client1")

        assert not limiter.is_allowed("api", "client1")

    def test_allow_without_policy(self):
        limiter = RateLimiter()
        assert limiter.is_allowed("unmanaged", "client1")


class TestInputValidator:
    def test_validate_string_valid(self):
        validator = InputValidator()
        assert validator.validate_string("hello")

    def test_validate_string_too_long(self):
        validator = InputValidator(max_string_length=5)
        assert not validator.validate_string("hello world")

    def test_validate_array_valid(self):
        validator = InputValidator()
        assert validator.validate_array([1, 2, 3])

    def test_validate_array_too_long(self):
        validator = InputValidator(max_array_length=2)
        assert not validator.validate_array([1, 2, 3])

    def test_validate_json_valid(self):
        validator = InputValidator()
        assert validator.validate_json('{"key": "value"}')

    def test_validate_json_invalid(self):
        validator = InputValidator()
        assert not validator.validate_json("not json")

    def test_validate_ipv4_valid(self):
        validator = InputValidator()
        assert validator.validate_ipv4("192.168.1.1")

    def test_validate_ipv4_invalid(self):
        validator = InputValidator()
        assert not validator.validate_ipv4("256.1.1.1")
        assert not validator.validate_ipv4("1.1.1")


class TestRequestAuditor:
    def test_log_request(self):
        auditor = RequestAuditor()
        auditor.log_request("GET", "/api/users", "192.168.1.1", 200, 45.5)
        assert len(auditor.requests) == 1

    def test_detect_high_request_rate(self):
        auditor = RequestAuditor()
        for i in range(101):
            auditor.log_request("GET", "/api", "192.168.1.1", 200, 10.0)

        suspicious = auditor.detect_suspicious_patterns()
        assert any(p["type"] == "high_request_rate" for p in suspicious)


class TestProductionHardeningManager:
    def test_get_security_status(self):
        manager = ProductionHardeningManager()
        status = manager.get_security_status()
        assert "timestamp" in status
        assert "suspicious_patterns" in status

    def test_integrated_rate_limiting(self):
        manager = ProductionHardeningManager()
        policy = RateLimitPolicy(max_requests=2, window_seconds=60)
        manager.rate_limiter.set_policy("api", policy)

        assert manager.rate_limiter.is_allowed("api", "client1")
        assert manager.rate_limiter.is_allowed("api", "client1")
        assert not manager.rate_limiter.is_allowed("api", "client1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
