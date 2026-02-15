"""
Security module for Vault Integration and secret management.
"""

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
