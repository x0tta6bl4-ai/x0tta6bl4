"""
Unit tests for src/core/settings.py

Covers: Settings(BaseSettings) default values, environment helpers
(is_production, is_development, is_testing), database URL validation,
secret requirement in production, field aliases, private key validator.
"""

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

import pytest
from pydantic import ValidationError

from src.core.settings import Settings

# ────────────────────────────────────────────
# Default values (non-production)
# ────────────────────────────────────────────


class TestSettingsDefaults:
    def _make_settings(self, monkeypatch, **env_overrides):
        """Create a fresh Settings instance with controlled env vars."""
        # Ensure we are NOT in production for default tests
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("DEBUG", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.delenv("NODE_ID", raising=False)
        monkeypatch.delenv("SOCKS_PORT", raising=False)
        monkeypatch.delenv("DASHBOARD_PORT", raising=False)
        monkeypatch.delenv("API_HOST", raising=False)
        monkeypatch.delenv("API_PORT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("CONTRACT_ADDRESS", raising=False)
        monkeypatch.delenv("RPC_URL", raising=False)
        monkeypatch.delenv("BOOTSTRAP_NODES", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("USDT_TRC20_WALLET", raising=False)
        monkeypatch.delenv("TON_WALLET", raising=False)
        monkeypatch.delenv("TRON_API_KEY", raising=False)
        monkeypatch.delenv("TON_API_KEY", raising=False)
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("STRIPE_SUCCESS_URL", raising=False)
        monkeypatch.delenv("STRIPE_CANCEL_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("OTEL_JAEGER_URL", raising=False)

        for k, v in env_overrides.items():
            monkeypatch.setenv(k, v)

        return Settings(_env_file=None)

    def test_environment_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.environment == "development"

    def test_debug_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.debug is False

    def test_database_url_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.database_url == "sqlite:///./x0tta6bl4.db"

    def test_node_id_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.node_id == "node-001"

    def test_socks_port_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.socks_port == 10809

    def test_dashboard_port_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.dashboard_port == 8080

    def test_api_host_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.api_host == "0.0.0.0"

    def test_api_port_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.api_port == 8080

    def test_log_level_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.log_level == "INFO"

    def test_otel_enabled_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.otel_enabled is False

    def test_optional_fields_default_to_none(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.flask_secret_key is None
        assert s.jwt_secret_key is None
        assert s.csrf_secret_key is None
        assert s.telegram_bot_token is None
        assert s.usdt_trc20_wallet is None
        assert s.ton_wallet is None
        assert s.tron_api_key is None
        assert s.ton_api_key is None
        assert s.operator_private_key is None
        assert s.contract_address is None
        assert s.rpc_url is None
        assert s.bootstrap_nodes is None
        assert s.stripe_secret_key is None
        assert s.stripe_publishable_key is None
        assert s.stripe_price_id is None
        assert s.stripe_webhook_secret is None
        assert s.stripe_success_url is None
        assert s.stripe_cancel_url is None
        assert s.redis_url is None
        assert s.sendgrid_api_key is None
        assert s.otel_jaeger_url is None


# ────────────────────────────────────────────
# Environment from env vars (aliases)
# ────────────────────────────────────────────


class TestSettingsFromEnvVars:
    def _make_settings(self, monkeypatch, **env_vars):
        # Clear production-related vars first
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)

        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

        return Settings(_env_file=None)

    def test_environment_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, ENVIRONMENT="staging")
        assert s.environment == "staging"

    def test_debug_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, DEBUG="true")
        assert s.debug is True

    def test_database_url_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, DATABASE_URL="postgresql://localhost/mydb")
        assert s.database_url == "postgresql://localhost/mydb"

    def test_node_id_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, NODE_ID="mesh-42")
        assert s.node_id == "mesh-42"

    def test_socks_port_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, SOCKS_PORT="1080")
        assert s.socks_port == 1080

    def test_api_port_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, API_PORT="9090")
        assert s.api_port == 9090

    def test_log_level_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, LOG_LEVEL="DEBUG")
        assert s.log_level == "DEBUG"

    def test_stripe_keys_from_env(self, monkeypatch):
        s = self._make_settings(
            monkeypatch,
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLISHABLE_KEY="pk_test_456",
        )
        assert s.stripe_secret_key == "sk_test_123"
        assert s.stripe_publishable_key == "pk_test_456"

    def test_telegram_token_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, TELEGRAM_BOT_TOKEN="123:abc")
        assert s.telegram_bot_token == "123:abc"

    def test_redis_url_from_env(self, monkeypatch):
        s = self._make_settings(monkeypatch, REDIS_URL="redis://localhost:6379/0")
        assert s.redis_url == "redis://localhost:6379/0"


# ────────────────────────────────────────────
# Environment helpers
# ────────────────────────────────────────────


class TestEnvironmentHelpers:
    def _make_settings(self, monkeypatch, environment):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", environment)

        # If production, provide required secrets
        if environment.lower() == "production":
            monkeypatch.setenv("FLASK_SECRET_KEY", "prod-flask-key")
            monkeypatch.setenv("JWT_SECRET_KEY", "prod-jwt-key")
            monkeypatch.setenv("CSRF_SECRET_KEY", "prod-csrf-key")
            monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xdeadbeef")

        return Settings(_env_file=None)

    def test_is_production(self, monkeypatch):
        s = self._make_settings(monkeypatch, "production")
        assert s.is_production() is True
        assert s.is_development() is False
        assert s.is_testing() is False

    def test_is_development(self, monkeypatch):
        s = self._make_settings(monkeypatch, "development")
        assert s.is_development() is True
        assert s.is_production() is False
        assert s.is_testing() is False

    def test_is_testing(self, monkeypatch):
        s = self._make_settings(monkeypatch, "testing")
        assert s.is_testing() is True
        assert s.is_production() is False
        assert s.is_development() is False

    def test_case_insensitive(self, monkeypatch):
        s = self._make_settings(monkeypatch, "Production")
        # is_production lower-cases first
        assert s.is_production() is True

    def test_unknown_environment(self, monkeypatch):
        s = self._make_settings(monkeypatch, "staging")
        assert s.is_production() is False
        assert s.is_development() is False
        assert s.is_testing() is False

    def test_is_staging(self, monkeypatch):
        s = self._make_settings(monkeypatch, "staging")
        assert s.is_staging() is True
        assert s.is_production() is False


class TestSecurityProfile:
    def test_development_security_profile_defaults(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

        profile = Settings(_env_file=None).security_profile()
        assert profile["pqc_required"] is False
        assert profile["mtls_enabled"] is False
        assert profile["rate_limit_enabled"] is True
        assert profile["request_validation_enabled"] is True

    def test_staging_security_profile_defaults(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "staging")

        profile = Settings(_env_file=None).security_profile()
        assert profile["pqc_required"] is True
        assert profile["mtls_enabled"] is True
        assert profile["rate_limit_enabled"] is True
        assert profile["request_validation_enabled"] is True

    def test_testing_security_profile_defaults(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "testing")

        profile = Settings(_env_file=None).security_profile()
        assert profile["pqc_required"] is False
        assert profile["mtls_enabled"] is False
        assert profile["rate_limit_enabled"] is False
        assert profile["request_validation_enabled"] is False

    def test_security_profile_env_override(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "k4")
        monkeypatch.setenv("MTLS_ENABLED", "false")
        monkeypatch.setenv("PQC_REQUIRED", "false")

        profile = Settings(_env_file=None).security_profile()
        assert profile["mtls_enabled"] is False
        assert profile["pqc_required"] is False


# ────────────────────────────────────────────
# Database URL validation
# ────────────────────────────────────────────


class TestDatabaseUrlValidation:
    def test_hardcoded_password_blocked_in_production(self, monkeypatch):
        """In production, database URL containing 'x0tta6bl4_password' is rejected."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:x0tta6bl4_password@host/db"
        )

        with pytest.raises(ValidationError, match="Hardcoded database password"):
            Settings(_env_file=None)

    def test_hardcoded_password_allowed_in_development(self, monkeypatch):
        """In development, hardcoded password is allowed (for local dev)."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:x0tta6bl4_password@host/db"
        )

        s = Settings(_env_file=None)
        assert "x0tta6bl4_password" in s.database_url

    def test_normal_database_url_accepted_in_production(self, monkeypatch):
        """A safe database URL passes validation in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:secure_pass@host/db")

        s = Settings(_env_file=None)
        assert s.database_url == "postgresql://user:secure_pass@host/db"

    def test_hardcoded_password_blocked_when_environment_from_env_file(
        self, monkeypatch, tmp_path
    ):
        """Production checks must work when environment is loaded from _env_file."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        env_file = tmp_path / "prod.env"
        env_file.write_text(
            "\n".join(
                [
                    "ENVIRONMENT=production",
                    "FLASK_SECRET_KEY=k1",
                    "JWT_SECRET_KEY=k2",
                    "CSRF_SECRET_KEY=k3",
                    "OPERATOR_PRIVATE_KEY=0xkey",
                    "DATABASE_URL=postgresql://user:x0tta6bl4_password@host/db",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="Hardcoded database password"):
            Settings(_env_file=env_file)


# ────────────────────────────────────────────
# Secret validation in production
# ────────────────────────────────────────────


class TestSecretValidation:
    def test_missing_flask_secret_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")

        with pytest.raises(ValidationError, match="Secret key must be set"):
            Settings(_env_file=None)

    def test_missing_jwt_secret_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")

        with pytest.raises(ValidationError, match="Secret key must be set"):
            Settings(_env_file=None)

    def test_missing_csrf_secret_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")

        with pytest.raises(ValidationError, match="Secret key must be set"):
            Settings(_env_file=None)

    def test_all_secrets_present_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "prod-flask")
        monkeypatch.setenv("JWT_SECRET_KEY", "prod-jwt")
        monkeypatch.setenv("CSRF_SECRET_KEY", "prod-csrf")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xkey")

        s = Settings(_env_file=None)
        assert s.flask_secret_key == "prod-flask"
        assert s.jwt_secret_key == "prod-jwt"
        assert s.csrf_secret_key == "prod-csrf"

    def test_secrets_not_required_in_development(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)

        s = Settings(_env_file=None)
        assert s.flask_secret_key is None
        assert s.jwt_secret_key is None
        assert s.csrf_secret_key is None

    def test_missing_secrets_blocked_when_environment_from_env_file(
        self, monkeypatch, tmp_path
    ):
        """Production checks must work when environment is loaded from _env_file."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        env_file = tmp_path / "prod_missing_secrets.env"
        env_file.write_text(
            "\n".join(
                [
                    "ENVIRONMENT=production",
                    "OPERATOR_PRIVATE_KEY=0xkey",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="Secret key must be set in production"):
            Settings(_env_file=env_file)


# ────────────────────────────────────────────
# Private key validation
# ────────────────────────────────────────────


class TestPrivateKeyValidation:
    def test_missing_private_key_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)

        with pytest.raises(ValidationError, match="OPERATOR_PRIVATE_KEY"):
            Settings(_env_file=None)

    def test_private_key_present_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "k1")
        monkeypatch.setenv("JWT_SECRET_KEY", "k2")
        monkeypatch.setenv("CSRF_SECRET_KEY", "k3")
        monkeypatch.setenv("OPERATOR_PRIVATE_KEY", "0xdeadbeef")

        s = Settings(_env_file=None)
        assert s.operator_private_key == "0xdeadbeef"

    def test_private_key_not_required_in_development(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)

        s = Settings(_env_file=None)
        assert s.operator_private_key is None

    def test_missing_private_key_blocked_when_environment_from_env_file(
        self, monkeypatch, tmp_path
    ):
        """Production checks must work when environment is loaded from _env_file."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        env_file = tmp_path / "prod_missing_key.env"
        env_file.write_text(
            "\n".join(
                [
                    "ENVIRONMENT=production",
                    "FLASK_SECRET_KEY=k1",
                    "JWT_SECRET_KEY=k2",
                    "CSRF_SECRET_KEY=k3",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="OPERATOR_PRIVATE_KEY"):
            Settings(_env_file=env_file)


# ────────────────────────────────────────────
# Config class behavior
# ────────────────────────────────────────────


class TestConfigBehavior:
    def test_extra_env_vars_ignored(self, monkeypatch):
        """The extra='ignore' setting means unknown env vars don't cause errors."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
        monkeypatch.setenv("TOTALLY_UNKNOWN_VAR", "whatever")

        s = Settings(_env_file=None)
        assert not hasattr(s, "totally_unknown_var")

    def test_case_insensitive_env_vars(self, monkeypatch):
        """Config has case_sensitive=False."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)

        s = Settings(_env_file=None)
        # The Config class sets case_sensitive=False
        assert s.model_config.get("case_sensitive") is False
