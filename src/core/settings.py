"""
Centralized Configuration Management for x0tta6bl4
=================================================
Uses environment variables for all sensitive configuration.
All secrets must be provided via .env file or environment.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


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
    database_url: str = Field(default="sqlite:///./x0tta6bl4.db", validation_alias="DATABASE_URL")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Prevent hardcoded passwords in production."""
        if "x0tta6bl4_password" in v and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("❌ Hardcoded database password detected! Use DATABASE_URL env var.")
        return v

    # ─────────────────────────────────────────
    # Security & Authentication
    # ─────────────────────────────────────────
    flask_secret_key: Optional[str] = Field(default=None, validation_alias="FLASK_SECRET_KEY")
    jwt_secret_key: Optional[str] = Field(default=None, validation_alias="JWT_SECRET_KEY")
    csrf_secret_key: Optional[str] = Field(default=None, validation_alias="CSRF_SECRET_KEY")

    @field_validator("flask_secret_key", "jwt_secret_key", "csrf_secret_key", mode="before")
    @classmethod
    def validate_secrets(cls, v: Optional[str]) -> Optional[str]:
        """Warn if secrets are not set in production."""
        if os.getenv("ENVIRONMENT") == "production" and not v:
            raise ValueError(f"❌ Secret key must be set in production")
        return v

    # ─────────────────────────────────────────
    # Telegram Bot
    # ─────────────────────────────────────────
    telegram_bot_token: Optional[str] = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")

    # ─────────────────────────────────────────
    # Cryptocurrency
    # ─────────────────────────────────────────
    usdt_trc20_wallet: Optional[str] = Field(default=None, validation_alias="USDT_TRC20_WALLET")
    ton_wallet: Optional[str] = Field(default=None, validation_alias="TON_WALLET")
    tron_api_key: Optional[str] = Field(default=None, validation_alias="TRON_API_KEY")
    ton_api_key: Optional[str] = Field(default=None, validation_alias="TON_API_KEY")

    # ─────────────────────────────────────────
    # Blockchain
    # ─────────────────────────────────────────
    operator_private_key: Optional[str] = Field(default=None, validation_alias="OPERATOR_PRIVATE_KEY")
    contract_address: Optional[str] = Field(default=None, validation_alias="CONTRACT_ADDRESS")
    rpc_url: Optional[str] = Field(default="https://sepolia.base.org", validation_alias="RPC_URL")

    @field_validator("operator_private_key", mode="before")
    @classmethod
    def validate_private_key(cls, v: Optional[str]) -> Optional[str]:
        """Warn if private key is not set."""
        if not v and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("❌ OPERATOR_PRIVATE_KEY must be set in production")
        return v

    # ─────────────────────────────────────────
    # Node Configuration
    # ─────────────────────────────────────────
    node_id: str = Field(default="node-001", validation_alias="NODE_ID")
    socks_port: int = Field(default=10809, validation_alias="SOCKS_PORT")
    dashboard_port: int = Field(default=8080, validation_alias="DASHBOARD_PORT")
    bootstrap_nodes: str = Field(
        default="89.125.1.107:10809,62.133.60.252:10809",
        validation_alias="BOOTSTRAP_NODES"
    )

    # ─────────────────────────────────────────
    # FastAPI
    # ─────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    # ─────────────────────────────────────────
    # Stripe Payment
    # ─────────────────────────────────────────
    stripe_secret_key: Optional[str] = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(default=None, validation_alias="STRIPE_PUBLISHABLE_KEY")
    stripe_price_id: Optional[str] = Field(default=None, validation_alias="STRIPE_PRICE_ID")
    stripe_webhook_secret: Optional[str] = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")
    stripe_success_url: str = Field(
        default="https://yourdomain.com/?success=1",
        validation_alias="STRIPE_SUCCESS_URL"
    )
    stripe_cancel_url: str = Field(
        default="https://yourdomain.com/?canceled=1",
        validation_alias="STRIPE_CANCEL_URL"
    )

    # ─────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # ─────────────────────────────────────────
    # Optional: External Integrations
    # ─────────────────────────────────────────
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    sendgrid_api_key: Optional[str] = Field(default=None, validation_alias="SENDGRID_API_KEY")
    otel_enabled: bool = Field(default=False, validation_alias="OTEL_ENABLED")
    otel_jaeger_url: Optional[str] = Field(default=None, validation_alias="OTEL_JAEGER_URL")

    # ─────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables

    # ─────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.environment.lower() == "testing"


# Global settings instance (loaded once at startup)
settings = Settings()

# Log configuration on startup (redact sensitive values)
if os.getenv("ENVIRONMENT") != "testing":
    print("✅ Configuration loaded from environment")
    if settings.is_production():
        print("🔒 PRODUCTION MODE - All secrets required")
    else:
        print("🔓 DEVELOPMENT MODE - Using defaults where available")
