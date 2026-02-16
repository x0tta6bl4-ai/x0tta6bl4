import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from datetime import datetime

from src.security.production_hardening import (InputValidator,
                                               ProductionHardeningManager,
                                               RateLimiter, RateLimitPolicy,
                                               RequestAuditor,
                                               SecretVaultManager,
                                               SecurityViolation,
                                               get_hardening_manager)


def test_security_violation_defaults() -> None:
    violation = SecurityViolation(
        timestamp=datetime.utcnow(),
        violation_type="auth",
        severity="high",
        description="denied",
        source="api",
    )
    assert violation.violation_type == "auth"
    assert violation.metadata == {}


def test_secret_vault_store_hashes_and_truncates() -> None:
    vault = SecretVaultManager()
    vault.store_secret("k", "super-secret", rotation_days=30)
    stored = vault.secrets["k"]
    assert stored["value"] != "super-secret"
    assert len(stored["value"]) == 32
    assert stored["rotation_days"] == 30
    assert isinstance(stored["created_at"], str)


def test_secret_vault_retrieve_and_rotate() -> None:
    vault = SecretVaultManager()
    vault.store_secret("token", "old")
    old_value = vault.retrieve_secret("token")
    assert old_value is not None
    assert vault.rotate_secret("token", "new") is True
    assert vault.retrieve_secret("token") != old_value
    assert vault.rotate_secret("missing", "x") is False
    assert vault.retrieve_secret("missing") is None


def test_rate_limiter_allows_without_policy() -> None:
    limiter = RateLimiter()
    assert limiter.is_allowed("no-policy", "client-a") is True


def test_rate_limiter_respects_limit_and_window_cleanup() -> None:
    limiter = RateLimiter()
    limiter.set_policy("api", RateLimitPolicy(max_requests=2, window_seconds=60))
    assert limiter.is_allowed("api", "c1") is True
    assert limiter.is_allowed("api", "c1") is True
    assert limiter.is_allowed("api", "c1") is False

    bucket = limiter.buckets["api:c1"]
    now = datetime.utcnow().timestamp()
    bucket.clear()
    bucket.append(now - 120)
    bucket.append(now - 61)
    assert limiter.is_allowed("api", "c1") is True


def test_input_validator_string_and_array_types() -> None:
    validator = InputValidator(max_string_length=5, max_array_length=2)
    assert validator.validate_string("ok") is True
    assert validator.validate_string("too-long") is False
    assert validator.validate_string(123) is False
    assert validator.validate_string("abcdef", max_length=10) is True
    assert validator.validate_array([1, 2]) is True
    assert validator.validate_array([1, 2, 3]) is False
    assert validator.validate_array("bad") is False
    assert validator.validate_array([1, 2, 3], max_length=4) is True


def test_input_validator_json_and_ipv4() -> None:
    validator = InputValidator()
    assert validator.validate_json('{"a": 1}') is True
    assert validator.validate_json("{bad json}") is False
    assert validator.validate_ipv4("127.0.0.1") is True
    assert validator.validate_ipv4("1.2.3") is False
    assert validator.validate_ipv4("1.2.3.256") is False
    assert validator.validate_ipv4("1.2.three.4") is False


def test_request_auditor_log_and_no_suspicious() -> None:
    auditor = RequestAuditor()
    auditor.log_request("GET", "/h", "10.0.0.1", 200, 1.5)
    assert len(auditor.requests) == 1
    assert auditor.requests[0]["method"] == "GET"
    assert auditor.detect_suspicious_patterns() == []


def test_request_auditor_detects_high_rate_per_ip() -> None:
    auditor = RequestAuditor()
    for _ in range(101):
        auditor.log_request("POST", "/api", "10.0.0.2", 429, 20.0)
    for _ in range(50):
        auditor.log_request("GET", "/api", "10.0.0.3", 200, 10.0)
    suspicious = auditor.detect_suspicious_patterns()
    assert len(suspicious) == 1
    assert suspicious[0]["type"] == "high_request_rate"
    assert suspicious[0]["ip"] == "10.0.0.2"
    assert suspicious[0]["count"] == 101


def test_manager_security_status_contains_timestamp_and_patterns() -> None:
    manager = ProductionHardeningManager()
    status = manager.get_security_status()
    assert "timestamp" in status
    assert "suspicious_patterns" in status
    assert isinstance(status["suspicious_patterns"], list)


def test_get_hardening_manager_singleton(monkeypatch) -> None:
    import src.security.production_hardening as module

    monkeypatch.setattr(module, "_manager", None)
    first = get_hardening_manager()
    second = get_hardening_manager()
    assert isinstance(first, ProductionHardeningManager)
    assert first is second
