"""
Centralized environment configuration for x0tta6bl4.
Replaces scattered os.getenv() calls with a single validated settings object.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int = 0) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float = 0.0) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class VPNSettings:
    server: str = field(default_factory=lambda: os.environ.get("VPN_SERVER", "89.125.1.107"))
    port: int = field(default_factory=lambda: _env_int("VPN_PORT", 443))
    socks_port: int = field(default_factory=lambda: _env_int("VPN_SOCKS_PORT", 10808))
    socks_candidates: str = field(default_factory=lambda: os.environ.get("VPN_SOCKS_PORT_CANDIDATES", "10918,10818,10808,10809,10924,40467"))
    obfuscation_key: str = field(default_factory=lambda: os.environ.get("VPN_OBFUSCATION_MASTER_KEY", ""))
    ghost_auth_key: str = field(default_factory=lambda: os.environ.get("GHOST_VPN_AUTH_KEY", ""))


@dataclass(frozen=True)
class DatabaseSettings:
    url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:////mnt/projects/x0tta6bl4.db"))
    pool_size: int = field(default_factory=lambda: _env_int("DB_POOL_SIZE", 20))
    max_overflow: int = field(default_factory=lambda: _env_int("DB_MAX_OVERFLOW", 10))
    cb_failure_threshold: int = field(default_factory=lambda: _env_int("DB_CB_FAILURE_THRESHOLD", 5))
    cb_recovery_timeout: int = field(default_factory=lambda: _env_int("DB_CB_RECOVERY_TIMEOUT", 60))


@dataclass(frozen=True)
class RedisSettings:
    url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@dataclass(frozen=True)
class SecuritySettings:
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET_KEY", ""))
    csrf_secret: str = field(default_factory=lambda: os.environ.get("CSRF_SECRET_KEY", ""))
    api_key_secret: str = field(default_factory=lambda: os.environ.get("API_KEY_SECRET", ""))
    admin_token: str = field(default_factory=lambda: os.environ.get("ADMIN_TOKEN", ""))
    mtls_enabled: bool = field(default_factory=lambda: _env_bool("MTLS_ENABLED", False))
    pqc_fail_closed: bool = field(default_factory=lambda: _env_bool("PQC_FAIL_CLOSED", True))


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    bot_username: str = field(default_factory=lambda: os.environ.get("BOT_USERNAME", ""))
    polling_enabled: bool = field(default_factory=lambda: _env_bool("TELEGRAM_POLLING_ENABLED", True))


@dataclass(frozen=True)
class StripeSettings:
    secret_key: str = field(default_factory=lambda: os.environ.get("STRIPE_SECRET_KEY", ""))
    webhook_secret: str = field(default_factory=lambda: os.environ.get("STRIPE_WEBHOOK_SECRET", ""))


@dataclass(frozen=True)
class MeshSettings:
    post_heal_probe: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE", False))
    post_heal_probe_target: str = field(default_factory=lambda: os.environ.get("X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE_TARGET", ""))
    allow_unverified_restore: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_ALLOW_UNVERIFIED_RESTORE", False))


@dataclass(frozen=True)
class SPIRESettings:
    server_url: str = field(default_factory=lambda: os.environ.get("SPIRE_SERVER_URL", "https://localhost:8081"))
    trust_domain: str = field(default_factory=lambda: os.environ.get("SPIRE_TRUST_DOMAIN", "x0tta6bl4.mesh"))
    agent_socket: str = field(default_factory=lambda: os.environ.get("SPIRE_AGENT_SOCKET", "/run/spire/sockets/agent.sock"))


@dataclass(frozen=True)
class VaultSettings:
    url: str = field(default_factory=lambda: os.environ.get("VAULT_URL", "http://localhost:8200"))
    token: str = field(default_factory=lambda: os.environ.get("VAULT_DEV_ROOT_TOKEN_ID", ""))
    kv_mount: str = field(default_factory=lambda: os.environ.get("VAULT_KV_MOUNT", "secret"))


@dataclass(frozen=True)
class OTelSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("OTEL_ENABLED", False))
    endpoint: str = field(default_factory=lambda: os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"))
    service_name: str = field(default_factory=lambda: os.environ.get("OTEL_SERVICE_NAME", "x0tta6bl4"))


@dataclass(frozen=True)
class FeatureFlags:
    byzantine: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_BYZANTINE", False))
    dao: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_DAO", False))
    ebpf: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_EBPF", False))
    failover: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_FAILOVER", False))
    federated_learning: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_FL", False))
    graphsage: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_GRAPHSAGE", False))
    pqc_beacons: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_PQC_BEACONS", False))
    production: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_PRODUCTION", False))
    spiffe: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_FEATURE_SPIFFE", False))


@dataclass(frozen=True)
class AppSettings:
    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    metrics_port: int = field(default_factory=lambda: _env_int("METRICS_PORT", 9090))
    mesh_port: int = field(default_factory=lambda: _env_int("MESH_PORT", 4001))
    allow_canary_live: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_ALLOW_CANARY_LIVE_ACTIONS", False))
    allow_multi_cloud_live: bool = field(default_factory=lambda: _env_bool("X0TTA6BL4_ALLOW_MULTI_CLOUD_LIVE_ACTIONS", False))
    light_mode: bool = field(default_factory=lambda: _env_bool("MAAS_LIGHT_MODE", False))

    vpn: VPNSettings = field(default_factory=VPNSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    stripe: StripeSettings = field(default_factory=StripeSettings)
    mesh: MeshSettings = field(default_factory=MeshSettings)
    spire: SPIRESettings = field(default_factory=SPIRESettings)
    vault: VaultSettings = field(default_factory=VaultSettings)
    otel: OTelSettings = field(default_factory=OTelSettings)
    features: FeatureFlags = field(default_factory=FeatureFlags)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


def get_settings() -> AppSettings:
    """Get or create the global settings singleton."""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = AppSettings()
    return get_settings._instance


settings = get_settings()

