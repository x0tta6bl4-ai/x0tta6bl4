"""
Vault configuration management.

This module provides configuration classes and utilities for Vault
integration, including environment-based configuration loading.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class VaultClientConfig:
    """Configuration for VaultClient.

    Attributes:
        vault_addr: Vault server address
        vault_namespace: Vault Enterprise namespace (optional)
        k8s_role: Kubernetes auth role name
        k8s_jwt_path: Path to service account JWT
        verify_ca: Path to CA cert for TLS verification
        max_retries: Number of retry attempts
        retry_delay: Initial retry delay (seconds)
        retry_backoff: Backoff multiplier
        cache_ttl: Cache TTL (seconds)
        token_refresh_threshold: Token refresh threshold (0-1)
    """

    vault_addr: str = "https://vault:8200"
    vault_namespace: Optional[str] = None
    k8s_role: str = "proxy-api"
    k8s_jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    verify_ca: Optional[str] = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    cache_ttl: int = 3600
    token_refresh_threshold: float = 0.8

    @classmethod
    def from_env(cls) -> "VaultClientConfig":
        """Create configuration from environment variables.

        Environment variables:
            VAULT_ADDR: Vault server address
            VAULT_NAMESPACE: Vault namespace
            VAULT_K8S_ROLE: Kubernetes auth role
            VAULT_K8S_JWT_PATH: JWT token path
            VAULT_VERIFY_CA: CA certificate path
            VAULT_MAX_RETRIES: Max retry attempts
            VAULT_RETRY_DELAY: Initial retry delay
            VAULT_CACHE_TTL: Cache TTL in seconds
            VAULT_TOKEN_REFRESH_THRESHOLD: Token refresh threshold

        Returns:
            VaultClientConfig instance
        """
        return cls(
            vault_addr=os.getenv("VAULT_ADDR", cls.vault_addr),
            vault_namespace=os.getenv("VAULT_NAMESPACE"),
            k8s_role=os.getenv("VAULT_K8S_ROLE", cls.k8s_role),
            k8s_jwt_path=os.getenv("VAULT_K8S_JWT_PATH", cls.k8s_jwt_path),
            verify_ca=os.getenv("VAULT_VERIFY_CA", cls.verify_ca),
            max_retries=int(os.getenv("VAULT_MAX_RETRIES", cls.max_retries)),
            retry_delay=float(os.getenv("VAULT_RETRY_DELAY", cls.retry_delay)),
            retry_backoff=float(os.getenv("VAULT_RETRY_BACKOFF", cls.retry_backoff)),
            cache_ttl=int(os.getenv("VAULT_CACHE_TTL", cls.cache_ttl)),
            token_refresh_threshold=float(
                os.getenv("VAULT_TOKEN_REFRESH_THRESHOLD", cls.token_refresh_threshold)
            ),
        )


@dataclass
class VaultMonitorConfig:
    """Configuration for VaultHealthMonitor.

    Attributes:
        check_interval: Seconds between health checks
        token_warning_threshold: Seconds before expiry to warn
        enabled: Whether monitoring is enabled
    """

    check_interval: int = 60
    token_warning_threshold: int = 300  # 5 minutes
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "VaultMonitorConfig":
        """Create configuration from environment variables.

        Environment variables:
            VAULT_MONITOR_INTERVAL: Health check interval
            VAULT_TOKEN_WARNING_THRESHOLD: Token warning threshold
            VAULT_MONITOR_ENABLED: Enable monitoring

        Returns:
            VaultMonitorConfig instance
        """
        return cls(
            check_interval=int(os.getenv("VAULT_MONITOR_INTERVAL", cls.check_interval)),
            token_warning_threshold=int(
                os.getenv("VAULT_TOKEN_WARNING_THRESHOLD", cls.token_warning_threshold)
            ),
            enabled=os.getenv("VAULT_MONITOR_ENABLED", "true").lower() == "true",
        )


@dataclass
class VaultPaths:
    """Vault secret paths configuration.

    Defines the path structure for different secret types in Vault KV v2.
    """

    base_path: str = "secret/data/proxy"
    database_path: str = "secret/data/proxy/database"
    api_keys_path: str = "secret/data/proxy/api-keys"
    credentials_path: str = "secret/data/proxy/credentials"
    certificates_path: str = "secret/data/proxy/certificates"
    tokens_path: str = "secret/data/proxy/tokens"
    encryption_path: str = "secret/data/proxy/encryption"

    def get_database_path(self, db_name: str) -> str:
        """Get path for database credentials."""
        return f"{self.database_path}/{db_name}"

    def get_api_key_path(self, api_name: str) -> str:
        """Get path for API credentials."""
        return f"{self.api_keys_path}/{api_name}"

    def get_certificate_path(self, cert_name: str) -> str:
        """Get path for TLS certificate."""
        return f"{self.certificates_path}/{cert_name}"


@dataclass
class VaultIntegrationConfig:
    """Complete Vault integration configuration.

    Combines all Vault-related configurations into a single object.
    """

    client: VaultClientConfig = field(default_factory=VaultClientConfig)
    monitor: VaultMonitorConfig = field(default_factory=VaultMonitorConfig)
    paths: VaultPaths = field(default_factory=VaultPaths)

    @classmethod
    def from_env(cls) -> "VaultIntegrationConfig":
        """Create complete configuration from environment."""
        return cls(
            client=VaultClientConfig.from_env(),
            monitor=VaultMonitorConfig.from_env(),
            paths=VaultPaths(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        return {
            "client": {
                "vault_addr": self.client.vault_addr,
                "vault_namespace": self.client.vault_namespace,
                "k8s_role": self.client.k8s_role,
                "max_retries": self.client.max_retries,
                "retry_delay": self.client.retry_delay,
                "cache_ttl": self.client.cache_ttl,
            },
            "monitor": {
                "check_interval": self.monitor.check_interval,
                "enabled": self.monitor.enabled,
            },
            "paths": {
                "base_path": self.paths.base_path,
            },
        }


def load_vault_config() -> VaultIntegrationConfig:
    """Load Vault configuration from environment.

    This is the main entry point for loading Vault configuration.
    It reads all relevant environment variables and returns a complete
    configuration object.

    Returns:
        VaultIntegrationConfig instance
    """
    config = VaultIntegrationConfig.from_env()

    logger.info(
        "Loaded Vault configuration: addr=%s, role=%s, namespace=%s",
        config.client.vault_addr,
        config.client.k8s_role,
        config.client.vault_namespace or "(none)",
    )

    return config


def validate_vault_config(config: VaultIntegrationConfig) -> list:
    """Validate Vault configuration.

    Args:
        config: Configuration to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate client config
    if not config.client.vault_addr:
        errors.append("VAULT_ADDR is required")
    elif not config.client.vault_addr.startswith(("http://", "https://")):
        errors.append("VAULT_ADDR must start with http:// or https://")

    if not config.client.k8s_role:
        errors.append("VAULT_K8S_ROLE is required")

    if config.client.max_retries < 0:
        errors.append("VAULT_MAX_RETRIES must be non-negative")

    if config.client.cache_ttl < 0:
        errors.append("VAULT_CACHE_TTL must be non-negative")

    if not 0 <= config.client.token_refresh_threshold <= 1:
        errors.append("VAULT_TOKEN_REFRESH_THRESHOLD must be between 0 and 1")

    return errors
