"""
Centralized Configuration Management for x0tta6bl4
=================================================
Uses environment variables for all sensitive configuration.
All secrets must be provided via .env file or environment.
"""

import os
from typing import Dict, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    See .env.example for all available configuration options.
    """

    # ─────────────────────────────────────────
    # Environment
    # ─────────────────────────────────────────
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    # ─────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./x0tta6bl4.db", validation_alias="DATABASE_URL"
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Normalize database URL value."""
        return v

    # ─────────────────────────────────────────
    # Security & Authentication
    # ─────────────────────────────────────────
    flask_secret_key: Optional[str] = Field(
        default=None, validation_alias="FLASK_SECRET_KEY"
    )
    jwt_secret_key: Optional[str] = Field(
        default=None, validation_alias="JWT_SECRET_KEY"
    )
    csrf_secret_key: Optional[str] = Field(
        default=None, validation_alias="CSRF_SECRET_KEY"
    )

    @field_validator(
        "flask_secret_key", "jwt_secret_key", "csrf_secret_key", mode="before"
    )
    @classmethod
    def validate_secrets(cls, v: Optional[str]) -> Optional[str]:
        """Normalize secret values. Production validation is in model_validator."""
        # Just normalize the value - production requirements are enforced
        # in validate_production_requirements model_validator which has access
        # to self.environment and can provide accurate error messages.
        return v

    # ─────────────────────────────────────────
    # Telegram Bot
    # ─────────────────────────────────────────
    telegram_bot_token: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )

    # ─────────────────────────────────────────
    # Cryptocurrency
    # ─────────────────────────────────────────
    usdt_trc20_wallet: Optional[str] = Field(
        default=None, validation_alias="USDT_TRC20_WALLET"
    )
    ton_wallet: Optional[str] = Field(default=None, validation_alias="TON_WALLET")
    tron_api_key: Optional[str] = Field(default=None, validation_alias="TRON_API_KEY")
    ton_api_key: Optional[str] = Field(default=None, validation_alias="TON_API_KEY")

    # ─────────────────────────────────────────
    # Blockchain
    # ─────────────────────────────────────────
    operator_private_key: Optional[str] = Field(
        default=None, validation_alias="OPERATOR_PRIVATE_KEY"
    )
    contract_address: Optional[str] = Field(
        default=None, validation_alias="CONTRACT_ADDRESS"
    )
    rpc_url: Optional[str] = Field(default=None, validation_alias="RPC_URL")

    @field_validator("operator_private_key", mode="before")
    @classmethod
    def validate_private_key(cls, v: Optional[str]) -> Optional[str]:
        """Normalize private key value."""
        return v

    @model_validator(mode="after")
    def validate_production_requirements(self):
        """
        Enforce production requirements based on resolved settings values.

        This must rely on `self.environment` rather than raw process env vars,
        because Settings values can come from `.env` files and explicit kwargs.
        """
        if not self.is_production():
            return self

        missing: list[str] = []
        if not self.flask_secret_key:
            missing.append("FLASK_SECRET_KEY")
        if not self.jwt_secret_key:
            missing.append("JWT_SECRET_KEY")
        if not self.csrf_secret_key:
            missing.append("CSRF_SECRET_KEY")
        if not self.operator_private_key:
            missing.append("OPERATOR_PRIVATE_KEY")

        violations: list[str] = []
        if missing:
            violations.append(
                f"Secret key must be set in production: {', '.join(missing)}"
            )
        if "x0tta6bl4_password" in self.database_url:
            violations.append(
                "Hardcoded database password detected! Use DATABASE_URL env var."
            )

        if violations:
            raise ValueError(" | ".join(violations))

        return self

    # ─────────────────────────────────────────
    # Node Configuration
    # ─────────────────────────────────────────
    node_id: str = Field(default="node-001", validation_alias="NODE_ID")
    socks_port: int = Field(default=10809, validation_alias="SOCKS_PORT")
    dashboard_port: int = Field(default=8080, validation_alias="DASHBOARD_PORT")
    bootstrap_nodes: Optional[str] = Field(
        default=None, validation_alias="BOOTSTRAP_NODES"
    )

    # ─────────────────────────────────────────
    # FastAPI
    # ─────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")  # nosec B104
    api_port: int = Field(default=8080, validation_alias="API_PORT")

    # ─────────────────────────────────────────
    # Stripe Payment
    # ─────────────────────────────────────────
    stripe_secret_key: Optional[str] = Field(
        default=None, validation_alias="STRIPE_SECRET_KEY"
    )
    stripe_publishable_key: Optional[str] = Field(
        default=None, validation_alias="STRIPE_PUBLISHABLE_KEY"
    )
    stripe_price_id: Optional[str] = Field(
        default=None, validation_alias="STRIPE_PRICE_ID"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None, validation_alias="STRIPE_WEBHOOK_SECRET"
    )
    stripe_success_url: Optional[str] = Field(
        default=None, validation_alias="STRIPE_SUCCESS_URL"
    )
    stripe_cancel_url: Optional[str] = Field(
        default=None, validation_alias="STRIPE_CANCEL_URL"
    )

    # ─────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # ─────────────────────────────────────────
    # Optional: External Integrations
    # ─────────────────────────────────────────
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    sendgrid_api_key: Optional[str] = Field(
        default=None, validation_alias="SENDGRID_API_KEY"
    )
    otel_enabled: bool = Field(default=False, validation_alias="OTEL_ENABLED")
    otel_jaeger_url: Optional[str] = Field(
        default=None, validation_alias="OTEL_JAEGER_URL"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment.lower() == "staging"

    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.environment.lower() == "testing"

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        lower_value = value.strip().lower()
        if lower_value in {"1", "true", "yes", "on"}:
            return True
        if lower_value in {"0", "false", "no", "off"}:
            return False
        return default

    def security_profile(self) -> Dict[str, bool]:
        """
        Resolve security flags for dev/staging/prod with optional env overrides.
        """
        defaults = {
            "pqc_required": False,
            "mtls_enabled": False,
            "rate_limit_enabled": True,
            "request_validation_enabled": True,
        }

        if self.is_testing():
            defaults.update(
                {
                    "pqc_required": False,
                    "mtls_enabled": False,
                    "rate_limit_enabled": False,
                    "request_validation_enabled": False,
                }
            )
        elif self.is_development():
            defaults.update(
                {
                    "pqc_required": False,
                    "mtls_enabled": False,
                    "rate_limit_enabled": True,
                    "request_validation_enabled": True,
                }
            )
        elif self.is_staging():
            defaults.update(
                {
                    "pqc_required": True,
                    "mtls_enabled": True,
                    "rate_limit_enabled": True,
                    "request_validation_enabled": True,
                }
            )
        elif self.is_production():
            defaults.update(
                {
                    "pqc_required": True,
                    "mtls_enabled": True,
                    "rate_limit_enabled": True,
                    "request_validation_enabled": True,
                }
            )

        return {
            "pqc_required": self._env_bool("PQC_REQUIRED", defaults["pqc_required"]),
            "mtls_enabled": self._env_bool("MTLS_ENABLED", defaults["mtls_enabled"]),
            "rate_limit_enabled": self._env_bool(
                "RATE_LIMIT_ENABLED", defaults["rate_limit_enabled"]
            ),
            "request_validation_enabled": self._env_bool(
                "REQUEST_VALIDATION_ENABLED", defaults["request_validation_enabled"]
            ),
        }


# Global settings instance (loaded once at startup)
settings = Settings(_env_file=".env")

# Log configuration on startup (redact sensitive values)
if os.getenv("ENVIRONMENT") != "testing":
    print("✅ Configuration loaded from environment")
    if settings.is_production():
        print("🔒 PRODUCTION MODE - All secrets required")
    else:
        print("🔓 DEVELOPMENT MODE - Using defaults where available")
