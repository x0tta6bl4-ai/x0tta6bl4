"""Security module for Vault Integration and secret management."""
from __future__ import annotations

try:
    from .vault_auth import K8sAuthConfig, K8sAuthHandler
    from .vault_client import VaultAuthError, VaultClient, VaultSecretError
    from .vault_monitoring import VaultHealthMonitor
    from .vault_secrets import SecretInjector, SecretType, VaultSecretManager

    __all__ = [
        "VaultClient",
        "VaultAuthError",
        "VaultSecretError",
        "K8sAuthHandler",
        "K8sAuthConfig",
        "VaultSecretManager",
        "SecretInjector",
        "SecretType",
        "VaultHealthMonitor",
    ]
except Exception:  # pragma: no cover - optional dependency path
    VaultAuthError = Exception  # type: ignore[misc,assignment]
    VaultClient = None  # type: ignore[misc,assignment]
    VaultSecretError = Exception  # type: ignore[misc,assignment]
    K8sAuthHandler = None  # type: ignore[misc,assignment]
    K8sAuthConfig = None  # type: ignore[misc,assignment]
    VaultSecretManager = None  # type: ignore[misc,assignment]
    SecretInjector = None  # type: ignore[misc,assignment]
    SecretType = None  # type: ignore[misc,assignment]
    VaultHealthMonitor = None  # type: ignore[misc,assignment]
    __all__ = []
