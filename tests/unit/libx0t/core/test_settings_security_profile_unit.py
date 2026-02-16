import os
import pytest
from pydantic import ValidationError

# Assuming libx0t is in the Python path for testing
from libx0t.core.settings import Settings


# Helper to create a fresh Settings instance with controlled env vars
# and ensure production/secrets-related vars are clean
def _make_settings_for_security_profile(monkeypatch, environment, **env_overrides):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("PQC_REQUIRED", raising=False)
    monkeypatch.delenv("MTLS_ENABLED", raising=False)
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.delenv("REQUEST_VALIDATION_ENABLED", raising=False)
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
    monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)

    monkeypatch.setenv("ENVIRONMENT", environment)

    # Provide required secrets for production/staging to pass validation
    if environment in ["production", "staging"]:
        monkeypatch.setenv("FLASK_SECRET_KEY", "dummy-flask-key")
        monkeypatch.setenv("JWT_SECRET_KEY", "dummy-jwt-key")
        monkeypatch.setenv("CSRF_SECRET_KEY", "dummy-csrf-key")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xdeadbeef")

    for k, v in env_overrides.items():
        monkeypatch.setenv(k, v)

    return Settings(_env_file=None)


class TestSecurityProfileExtended:
    """
    Extended tests for the Settings.security_profile() method.
    """

    def test_production_security_profile_all_true_defaults(self, monkeypatch):
        """
        Verify that in production, all security flags default to True
        when no environment overrides are provided.
        """
        settings = _make_settings_for_security_profile(monkeypatch, "production")
        profile = settings.security_profile()

        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is True
        assert profile["rate_limit_enabled"] is True
        assert profile["request_validation_enabled"] is True

    def test_staging_security_profile_all_true_defaults(self, monkeypatch):
        """
        Verify that in staging, all security flags default to True
        when no environment overrides are provided.
        """
        settings = _make_settings_for_security_profile(monkeypatch, "staging")
        profile = settings.security_profile()

        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is True
        assert profile["rate_limit_enabled"] is True
        assert profile["request_validation_enabled"] is True

    def test_security_profile_staging_env_override(self, monkeypatch):
        """
        Test overriding staging security flags via environment variables.
        """
        settings = _make_settings_for_security_profile(
            monkeypatch,
            "staging",
            PQC_REQUIRED="false",
            MTLS_ENABLED="false",
            RATE_LIMIT_ENABLED="false",
            REQUEST_VALIDATION_ENABLED="false",
        )
        profile = settings.security_profile()

        assert profile["pqc_required"] is False
        assert profile["mtls_enabled"] is False
        assert profile["rate_limit_enabled"] is False
        assert profile["request_validation_enabled"] is False

    def test_security_profile_development_env_override(self, monkeypatch):
        """
        Test overriding development security flags via environment variables.
        """
        settings = _make_settings_for_security_profile(
            monkeypatch,
            "development",
            PQC_REQUIRED="true",
            MTLS_ENABLED="true",
            RATE_LIMIT_ENABLED="false",
        )
        profile = settings.security_profile()

        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is True
        assert profile["rate_limit_enabled"] is False # Overridden
        assert profile["request_validation_enabled"] is True # Not overridden

    def test_security_profile_pqc_required_mixed_case_env(self, monkeypatch):
        """
        Test that boolean environment variable overrides are case-insensitive.
        """
        settings = _make_settings_for_security_profile(
            monkeypatch,
            "production",
            PQC_REQUIRED="True", # Mixed case
            MTLS_ENABLED="fAlSe", # Mixed case
        )
        profile = settings.security_profile()

        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is False

    def test_security_profile_env_override_numeric(self, monkeypatch):
        """
        Test that boolean environment variable overrides work with numeric string (0/1).
        """
        settings = _make_settings_for_security_profile(
            monkeypatch,
            "production",
            PQC_REQUIRED="1",
            MTLS_ENABLED="0",
        )
        profile = settings.security_profile()

        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is False

    def test_security_profile_invalid_env_bool_fallback_to_default(self, monkeypatch):
        """
        Test that invalid boolean env var string falls back to default for the environment.
        """
        settings = _make_settings_for_security_profile(
            monkeypatch,
            "production",
            PQC_REQUIRED="invalid",
        )
        profile = settings.security_profile()
        # In production, PQC_REQUIRED defaults to True, so invalid should result in True
        assert profile["pqc_required"] is True

        settings_dev = _make_settings_for_security_profile(
            monkeypatch,
            "development",
            PQC_REQUIRED="invalid",
        )
        profile_dev = settings_dev.security_profile()
        # In development, PQC_REQUIRED defaults to False, so invalid should result in False
        assert profile_dev["pqc_required"] is False
