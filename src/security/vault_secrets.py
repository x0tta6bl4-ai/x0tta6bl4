"""
High-level secret management API for Vault.

This module provides convenient abstractions for managing different types
of secrets in Vault, including database credentials, API keys, certificates,
and tokens. It also includes a secret injector for integrating secrets into
application configuration.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets managed by Vault."""

    DATABASE = "database"
    API_KEY = "api_key"
    CREDENTIALS = "credentials"
    CERTIFICATE = "certificate"
    TOKEN = "token"
    ENCRYPTION_KEY = "encryption_key"


@dataclass
class DatabaseCredentials:
    """Database connection credentials."""

    username: str
    password: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    connection_string: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "username": self.username,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "connection_string": self.connection_string,
        }


@dataclass
class ApiCredentials:
    """API authentication credentials."""

    api_key: str
    api_secret: Optional[str] = None
    api_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "api_token": self.api_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }


@dataclass
class TLSCertificate:
    """TLS certificate data."""

    certificate: str
    private_key: str
    ca_chain: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "certificate": self.certificate,
            "private_key": self.private_key,
            "ca_chain": self.ca_chain,
        }


class VaultSecretManager:
    """High-level API for managing secrets in Vault.

    This manager provides convenient methods for retrieving and storing
    different types of secrets with consistent path conventions.

    Example:
        >>> from src.security.vault_client import VaultClient
        >>> client = VaultClient(vault_addr="https://vault:8200")
        >>> await client.connect()
        >>>
        >>> manager = VaultSecretManager(client)
        >>> db_creds = await manager.get_database_credentials("main-db")
        >>> api_creds = await manager.get_api_credentials("stripe")
    """

    def __init__(self, vault_client):
        """Initialize secret manager.

        Args:
            vault_client: Initialized VaultClient instance
        """
        self.vault_client = vault_client
        self._base_path = "proxy"
        self._secret_paths = {
            SecretType.DATABASE: f"{self._base_path}/database",
            SecretType.API_KEY: f"{self._base_path}/api-keys",
            SecretType.CREDENTIALS: f"{self._base_path}/credentials",
            SecretType.CERTIFICATE: f"{self._base_path}/certificates",
            SecretType.TOKEN: f"{self._base_path}/tokens",
            SecretType.ENCRYPTION_KEY: f"{self._base_path}/encryption",
        }

    async def get_database_credentials(self, db_name: str) -> DatabaseCredentials:
        """Get database credentials from Vault.

        Args:
            db_name: Database identifier (e.g., "main-db", "analytics-db")

        Returns:
            DatabaseCredentials object

        Raises:
            VaultSecretError: If credentials cannot be retrieved
        """
        data = await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.DATABASE]}/{db_name}"
        )

        return DatabaseCredentials(
            username=data.get("username", ""),
            password=data.get("password", ""),
            host=data.get("host"),
            port=data.get("port"),
            database=data.get("database"),
            connection_string=data.get("connection_string"),
        )

    async def store_database_credentials(
        self, db_name: str, credentials: DatabaseCredentials
    ) -> None:
        """Store database credentials in Vault.

        Args:
            db_name: Database identifier
            credentials: Database credentials to store
        """
        secret_data = credentials if isinstance(credentials, dict) else credentials.to_dict()
        await self.vault_client.put_secret(
            f"{self._secret_paths[SecretType.DATABASE]}/{db_name}",
            secret_data,
        )
        logger.info("Stored database credentials for %s", db_name)

    async def get_api_credentials(self, api_name: str) -> ApiCredentials:
        """Get API credentials from Vault.

        Args:
            api_name: API identifier (e.g., "stripe", "sendgrid")

        Returns:
            ApiCredentials object
        """
        data = await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.API_KEY]}/{api_name}"
        )

        return ApiCredentials(
            api_key=data.get("api_key", ""),
            api_secret=data.get("api_secret"),
            api_token=data.get("api_token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
        )

    async def store_api_credentials(
        self, api_name: str, credentials: ApiCredentials
    ) -> None:
        """Store API credentials in Vault.

        Args:
            api_name: API identifier
            credentials: API credentials to store
        """
        await self.vault_client.put_secret(
            f"{self._secret_paths[SecretType.API_KEY]}/{api_name}",
            credentials.to_dict(),
        )
        logger.info("Stored API credentials for %s", api_name)

    async def get_proxy_credentials(self) -> Dict[str, str]:
        """Get proxy-api service credentials.

        Returns:
            Dictionary with proxy credentials
        """
        return await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.CREDENTIALS]}/proxy-api"
        )

    async def rotate_proxy_credentials(self, new_credentials: Dict[str, str]) -> None:
        """Rotate proxy-api credentials.

        This operation should be performed by an admin or automated
        rotation service. The new credentials take effect immediately.

        Args:
            new_credentials: New credential values
        """
        await self.vault_client.put_secret(
            f"{self._secret_paths[SecretType.CREDENTIALS]}/proxy-api", new_credentials
        )
        logger.info("Proxy credentials rotated successfully")

    async def get_tls_certificate(self, cert_name: str) -> TLSCertificate:
        """Get TLS certificate from Vault.

        Args:
            cert_name: Certificate identifier (e.g., "api-server", "internal-mtls")

        Returns:
            TLSCertificate object
        """
        data = await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.CERTIFICATE]}/{cert_name}"
        )

        return TLSCertificate(
            certificate=data.get("certificate", ""),
            private_key=data.get("private_key", ""),
            ca_chain=data.get("ca_chain"),
        )

    async def store_tls_certificate(
        self, cert_name: str, certificate: TLSCertificate
    ) -> None:
        """Store TLS certificate in Vault.

        Args:
            cert_name: Certificate identifier
            certificate: TLS certificate data
        """
        await self.vault_client.put_secret(
            f"{self._secret_paths[SecretType.CERTIFICATE]}/{cert_name}",
            certificate.to_dict(),
        )
        logger.info("Stored TLS certificate for %s", cert_name)

    async def get_encryption_key(self, key_name: str) -> str:
        """Get encryption key from Vault.

        Args:
            key_name: Key identifier

        Returns:
            Encryption key string
        """
        return await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.ENCRYPTION_KEY]}/{key_name}",
            secret_key="key",
        )

    async def list_secrets(self, secret_type: SecretType) -> List[str]:
        """List available secrets of a given type.

        Args:
            secret_type: Type of secrets to list

        Returns:
            List of secret names
        """
        path = self._secret_paths[secret_type]
        try:
            return await self.vault_client.list_secrets(path)
        except Exception as e:
            logger.warning("Failed to list secrets at %s: %s", path, e)
            return []


class SecretInjector:
    """Inject secrets into application configuration.

    This class provides methods to seamlessly integrate Vault secrets
    into application configuration dictionaries without exposing
    sensitive values in code or environment variables.

    Example:
        >>> manager = VaultSecretManager(client)
        >>> injector = SecretInjector(manager)
        >>>
        >>> db_config = {'pool_size': 10}
        >>> db_config = await injector.inject_database_config(
        ...     "main-db", db_config
        ... )
        >>> # db_config now contains username, password, connection_string
    """

    def __init__(self, secret_manager: VaultSecretManager):
        """Initialize secret injector.

        Args:
            secret_manager: VaultSecretManager instance
        """
        self.secret_manager = secret_manager

    async def inject_database_config(
        self, db_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inject database secrets into configuration.

        Args:
            db_name: Database identifier
            config: Base configuration dictionary

        Returns:
            Configuration with injected credentials
        """
        credentials = await self.secret_manager.get_database_credentials(db_name)

        config.update(
            {
                "username": credentials.username,
                "password": credentials.password,
                "host": credentials.host,
                "port": credentials.port,
                "database": credentials.database,
                "connection_string": credentials.connection_string,
            }
        )

        # Remove None values
        return {k: v for k, v in config.items() if v is not None}

    async def inject_api_config(
        self, api_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inject API credentials into configuration.

        Args:
            api_name: API identifier
            config: Base configuration dictionary

        Returns:
            Configuration with injected credentials
        """
        credentials = await self.secret_manager.get_api_credentials(api_name)

        config.update(
            {
                "api_key": credentials.api_key,
                "api_secret": credentials.api_secret,
                "api_token": credentials.api_token,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            }
        )

        # Remove None values
        return {k: v for k, v in config.items() if v is not None}

    async def inject_tls_config(
        self, cert_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inject TLS certificate into configuration.

        Args:
            cert_name: Certificate identifier
            config: Base configuration dictionary

        Returns:
            Configuration with injected certificate data
        """
        certificate = await self.secret_manager.get_tls_certificate(cert_name)

        config.update(
            {
                "cert_pem": certificate.certificate,
                "key_pem": certificate.private_key,
                "ca_pem": certificate.ca_chain,
            }
        )

        # Remove None values
        return {k: v for k, v in config.items() if v is not None}
