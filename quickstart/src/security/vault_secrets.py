"""
High-level secret management API for Vault.

This module provides convenient abstractions for managing different types
of secrets in Vault, including database credentials, API keys, certificates,
and tokens. It also includes a secret injector for integrating secrets into
application configuration.
"""
from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"vault-secret-manager:{_safe_hash(id(vault_client))}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "vault_secret_manager_init",
                "goal": "Initialize Vault secret path manager safely",
                "signals": {
                    "base_path_hash": _safe_hash(self._base_path),
                    "secret_type_count_bucket": _safe_count_bucket(
                        len(self._secret_paths)
                    ),
                },
                "safety_boundary": (
                    "Keep secret names, Vault paths, credential values, certificates, "
                    "tokens, and encryption keys out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_secret_names": True,
                    "redact_vault_paths": True,
                    "redact_credential_values": True,
                    "redact_certificates": True,
                    "redact_tokens": True,
                    "redact_encryption_keys": True,
                    "preserve_secret_operation_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and secret type labels.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
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

        credentials = DatabaseCredentials(
            username=data.get("username", ""),
            password=data.get("password", ""),
            host=data.get("host"),
            port=data.get("port"),
            database=data.get("database"),
            connection_string=data.get("connection_string"),
        )
        self._record_thinking(
            "vault_database_credentials_retrieved",
            "Retrieve database credentials safely",
            {
                "secret_type": SecretType.DATABASE.value,
                "secret_name_hash": _safe_hash(db_name),
                "field_count_bucket": _safe_count_bucket(len(data)),
                "has_username": bool(credentials.username),
                "has_password": bool(credentials.password),
                "has_connection_string": bool(credentials.connection_string),
            },
        )
        return credentials

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
        self._record_thinking(
            "vault_database_credentials_stored",
            "Store database credentials safely",
            {
                "secret_type": SecretType.DATABASE.value,
                "secret_name_hash": _safe_hash(db_name),
                "field_count_bucket": _safe_count_bucket(len(secret_data)),
                "field_hashes": [_safe_hash(key) for key in sorted(secret_data)[:20]],
            },
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

        credentials = ApiCredentials(
            api_key=data.get("api_key", ""),
            api_secret=data.get("api_secret"),
            api_token=data.get("api_token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
        )
        self._record_thinking(
            "vault_api_credentials_retrieved",
            "Retrieve API credentials safely",
            {
                "secret_type": SecretType.API_KEY.value,
                "secret_name_hash": _safe_hash(api_name),
                "field_count_bucket": _safe_count_bucket(len(data)),
                "has_api_key": bool(credentials.api_key),
                "has_api_secret": bool(credentials.api_secret),
                "has_api_token": bool(credentials.api_token),
                "has_client_secret": bool(credentials.client_secret),
            },
        )
        return credentials

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
        self._record_thinking(
            "vault_api_credentials_stored",
            "Store API credentials safely",
            {
                "secret_type": SecretType.API_KEY.value,
                "secret_name_hash": _safe_hash(api_name),
                "field_count_bucket": _safe_count_bucket(len(credentials.to_dict())),
            },
        )
        logger.info("Stored API credentials for %s", api_name)

    async def get_proxy_credentials(self) -> Dict[str, str]:
        """Get proxy-api service credentials.

        Returns:
            Dictionary with proxy credentials
        """
        credentials = await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.CREDENTIALS]}/proxy-api"
        )
        self._record_thinking(
            "vault_proxy_credentials_retrieved",
            "Retrieve proxy credentials safely",
            {
                "secret_type": SecretType.CREDENTIALS.value,
                "secret_name_hash": _safe_hash("proxy-api"),
                "field_count_bucket": _safe_count_bucket(len(credentials)),
            },
        )
        return credentials

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
        self._record_thinking(
            "vault_proxy_credentials_rotated",
            "Rotate proxy credentials safely",
            {
                "secret_type": SecretType.CREDENTIALS.value,
                "secret_name_hash": _safe_hash("proxy-api"),
                "field_count_bucket": _safe_count_bucket(len(new_credentials)),
                "field_hashes": [
                    _safe_hash(key) for key in sorted(new_credentials.keys())[:20]
                ],
            },
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

        certificate = TLSCertificate(
            certificate=data.get("certificate", ""),
            private_key=data.get("private_key", ""),
            ca_chain=data.get("ca_chain"),
        )
        self._record_thinking(
            "vault_tls_certificate_retrieved",
            "Retrieve TLS certificate safely",
            {
                "secret_type": SecretType.CERTIFICATE.value,
                "secret_name_hash": _safe_hash(cert_name),
                "field_count_bucket": _safe_count_bucket(len(data)),
                "has_certificate": bool(certificate.certificate),
                "has_private_key": bool(certificate.private_key),
                "has_ca_chain": bool(certificate.ca_chain),
            },
        )
        return certificate

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
        self._record_thinking(
            "vault_tls_certificate_stored",
            "Store TLS certificate safely",
            {
                "secret_type": SecretType.CERTIFICATE.value,
                "secret_name_hash": _safe_hash(cert_name),
                "field_count_bucket": _safe_count_bucket(len(certificate.to_dict())),
            },
        )
        logger.info("Stored TLS certificate for %s", cert_name)

    async def get_encryption_key(self, key_name: str) -> str:
        """Get encryption key from Vault.

        Args:
            key_name: Key identifier

        Returns:
            Encryption key string
        """
        key = await self.vault_client.get_secret(
            f"{self._secret_paths[SecretType.ENCRYPTION_KEY]}/{key_name}",
            secret_key="key",
        )
        self._record_thinking(
            "vault_encryption_key_retrieved",
            "Retrieve encryption key safely",
            {
                "secret_type": SecretType.ENCRYPTION_KEY.value,
                "secret_name_hash": _safe_hash(key_name),
                "hit": key is not None,
            },
        )
        return key

    async def list_secrets(self, secret_type: SecretType) -> List[str]:
        """List available secrets of a given type.

        Args:
            secret_type: Type of secrets to list

        Returns:
            List of secret names
        """
        path = self._secret_paths[secret_type]
        try:
            secrets = await self.vault_client.list_secrets(path)
            self._record_thinking(
                "vault_secrets_listed",
                "List Vault secrets safely",
                {
                    "secret_type": secret_type.value,
                    "path_hash": _safe_hash(path),
                    "secret_count_bucket": _safe_count_bucket(len(secrets)),
                },
            )
            return secrets
        except Exception as e:
            self._record_thinking(
                "vault_secrets_list_failed",
                "Record Vault secret list failure safely",
                {
                    "secret_type": secret_type.value,
                    "path_hash": _safe_hash(path),
                    "error_type": type(e).__name__,
                },
            )
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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"secret-injector:{_safe_hash(id(secret_manager))}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "secret_injector_init",
                "goal": "Initialize secret injection safely",
                "signals": {"secret_manager_present": secret_manager is not None},
                "safety_boundary": (
                    "Keep secret names, base config values, injected credentials, "
                    "certificates, and private keys out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_secret_names": True,
                    "redact_config_values": True,
                    "redact_credentials": True,
                    "redact_certificates": True,
                    "redact_private_keys": True,
                    "preserve_injection_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and config key hashes.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
        before_keys = set(config)
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
        injected = {k: v for k, v in config.items() if v is not None}
        self._record_thinking(
            "database_config_injected",
            "Inject database configuration safely",
            {
                "secret_name_hash": _safe_hash(db_name),
                "input_key_count_bucket": _safe_count_bucket(len(before_keys)),
                "output_key_count_bucket": _safe_count_bucket(len(injected)),
                "input_key_hashes": [_safe_hash(key) for key in sorted(before_keys)[:20]],
                "output_key_hashes": [
                    _safe_hash(key) for key in sorted(injected.keys())[:20]
                ],
                "has_connection_string": "connection_string" in injected,
            },
        )
        return injected

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
        before_keys = set(config)
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
        injected = {k: v for k, v in config.items() if v is not None}
        self._record_thinking(
            "api_config_injected",
            "Inject API configuration safely",
            {
                "secret_name_hash": _safe_hash(api_name),
                "input_key_count_bucket": _safe_count_bucket(len(before_keys)),
                "output_key_count_bucket": _safe_count_bucket(len(injected)),
                "input_key_hashes": [_safe_hash(key) for key in sorted(before_keys)[:20]],
                "output_key_hashes": [
                    _safe_hash(key) for key in sorted(injected.keys())[:20]
                ],
                "has_api_secret": "api_secret" in injected,
                "has_client_secret": "client_secret" in injected,
            },
        )
        return injected

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
        before_keys = set(config)
        certificate = await self.secret_manager.get_tls_certificate(cert_name)

        config.update(
            {
                "cert_pem": certificate.certificate,
                "key_pem": certificate.private_key,
                "ca_pem": certificate.ca_chain,
            }
        )

        # Remove None values
        injected = {k: v for k, v in config.items() if v is not None}
        self._record_thinking(
            "tls_config_injected",
            "Inject TLS configuration safely",
            {
                "secret_name_hash": _safe_hash(cert_name),
                "input_key_count_bucket": _safe_count_bucket(len(before_keys)),
                "output_key_count_bucket": _safe_count_bucket(len(injected)),
                "input_key_hashes": [_safe_hash(key) for key in sorted(before_keys)[:20]],
                "output_key_hashes": [
                    _safe_hash(key) for key in sorted(injected.keys())[:20]
                ],
                "has_cert_pem": "cert_pem" in injected,
                "has_key_pem": "key_pem" in injected,
            },
        )
        return injected

