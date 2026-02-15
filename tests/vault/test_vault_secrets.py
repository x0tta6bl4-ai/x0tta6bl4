"""
Unit tests for VaultSecretManager and SecretInjector.
"""

from unittest.mock import AsyncMock

import pytest

from src.security.vault_client import VaultSecretError
from src.security.vault_secrets import (ApiCredentials, DatabaseCredentials,
                                        SecretInjector, SecretType,
                                        TLSCertificate, VaultSecretManager)


@pytest.mark.asyncio
class TestVaultSecretManager:
    """Test VaultSecretManager."""

    async def test_manager_initialization(self, authenticated_vault_client):
        """Test manager initialization."""
        manager = VaultSecretManager(authenticated_vault_client)

        assert manager.vault_client == authenticated_vault_client
        assert manager._base_path == "proxy"
        assert SecretType.DATABASE in manager._secret_paths

    async def test_get_database_credentials(
        self, secret_manager, mock_hvac_client, sample_database_credentials
    ):
        """Test retrieving database credentials."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_database_credentials}
        }

        creds = await secret_manager.get_database_credentials("main-db")

        assert isinstance(creds, DatabaseCredentials)
        assert creds.username == "dbuser"
        assert creds.password == "dbpass123"
        assert creds.host == "db.example.com"
        assert creds.port == 5432

    async def test_store_database_credentials(self, secret_manager, mock_hvac_client):
        """Test storing database credentials."""
        creds = DatabaseCredentials(
            username="newuser",
            password="newpass",
            host="new.example.com",
        )

        await secret_manager.store_database_credentials("new-db", creds)

        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        call_args = mock_hvac_client.secrets.kv.v2.create_or_update_secret.call_args
        assert "new-db" in call_args[1]["path"]

    async def test_get_api_credentials(
        self, secret_manager, mock_hvac_client, sample_api_credentials
    ):
        """Test retrieving API credentials."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_api_credentials}
        }

        creds = await secret_manager.get_api_credentials("stripe")

        assert isinstance(creds, ApiCredentials)
        assert creds.api_key == "api-key-12345"
        assert creds.api_secret == "api-secret-67890"
        assert creds.client_id == "client-123"

    async def test_store_api_credentials(self, secret_manager, mock_hvac_client):
        """Test storing API credentials."""
        creds = ApiCredentials(
            api_key="new-key",
            api_secret="new-secret",
        )

        await secret_manager.store_api_credentials("new-api", creds)

        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    async def test_get_proxy_credentials(self, secret_manager, mock_hvac_client):
        """Test retrieving proxy credentials."""
        mock_data = {"api_key": "proxy-key", "secret": "proxy-secret"}
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": mock_data}
        }

        creds = await secret_manager.get_proxy_credentials()

        assert creds["api_key"] == "proxy-key"
        assert creds["secret"] == "proxy-secret"

    async def test_rotate_proxy_credentials(self, secret_manager, mock_hvac_client):
        """Test rotating proxy credentials."""
        new_creds = {"api_key": "new-key", "secret": "new-secret"}

        await secret_manager.rotate_proxy_credentials(new_creds)

        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        call_args = mock_hvac_client.secrets.kv.v2.create_or_update_secret.call_args
        assert call_args[1]["secret"] == new_creds

    async def test_get_tls_certificate(
        self, secret_manager, mock_hvac_client, sample_tls_certificate
    ):
        """Test retrieving TLS certificate."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_tls_certificate}
        }

        cert = await secret_manager.get_tls_certificate("api-server")

        assert isinstance(cert, TLSCertificate)
        assert "TEST" in cert.certificate
        assert "TEST" in cert.private_key
        assert "CA" in cert.ca_chain

    async def test_store_tls_certificate(self, secret_manager, mock_hvac_client):
        """Test storing TLS certificate."""
        cert = TLSCertificate(
            certificate="-----BEGIN CERTIFICATE-----\nNEW\n-----END CERTIFICATE-----",
            private_key="-----BEGIN PRIVATE KEY-----\nNEW\n-----END PRIVATE KEY-----",
        )

        await secret_manager.store_tls_certificate("new-cert", cert)

        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    async def test_get_encryption_key(self, secret_manager, mock_hvac_client):
        """Test retrieving encryption key."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"key": "super-secret-key-12345"}}
        }

        key = await secret_manager.get_encryption_key("master-key")

        assert key == "super-secret-key-12345"

    async def test_list_secrets_success(self, secret_manager, mock_hvac_client):
        """Test listing secrets."""
        mock_hvac_client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["db1", "db2", "db3"]}
        }

        secrets = await secret_manager.list_secrets(SecretType.DATABASE)

        assert secrets == ["db1", "db2", "db3"]

    async def test_list_secrets_empty(self, secret_manager, mock_hvac_client):
        """Test listing secrets when empty."""
        mock_hvac_client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": []}
        }

        secrets = await secret_manager.list_secrets(SecretType.API_KEY)

        assert secrets == []

    async def test_list_secrets_error(self, secret_manager, mock_hvac_client):
        """Test listing secrets with error."""
        mock_hvac_client.secrets.kv.v2.list_secrets.side_effect = Exception(
            "Vault error"
        )

        secrets = await secret_manager.list_secrets(SecretType.CERTIFICATE)

        assert secrets == []


@pytest.mark.asyncio
class TestSecretInjector:
    """Test SecretInjector."""

    async def test_inject_database_config(
        self, secret_injector, mock_hvac_client, sample_database_credentials
    ):
        """Test injecting database config."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_database_credentials}
        }

        base_config = {"pool_size": 10, "timeout": 30}
        config = await secret_injector.inject_database_config("main-db", base_config)

        assert config["pool_size"] == 10
        assert config["timeout"] == 30
        assert config["username"] == "dbuser"
        assert config["password"] == "dbpass123"
        assert config["host"] == "db.example.com"

    async def test_inject_database_config_removes_none(
        self, secret_injector, mock_hvac_client
    ):
        """Test that None values are removed from config."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "username": "user",
                    "password": "pass",
                    "host": None,  # Should be removed
                }
            }
        }

        base_config = {}
        config = await secret_injector.inject_database_config("db", base_config)

        assert "username" in config
        assert "password" in config
        assert "host" not in config

    async def test_inject_api_config(
        self, secret_injector, mock_hvac_client, sample_api_credentials
    ):
        """Test injecting API config."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_api_credentials}
        }

        base_config = {"timeout": 60}
        config = await secret_injector.inject_api_config("stripe", base_config)

        assert config["timeout"] == 60
        assert config["api_key"] == "api-key-12345"
        assert config["api_secret"] == "api-secret-67890"

    async def test_inject_tls_config(
        self, secret_injector, mock_hvac_client, sample_tls_certificate
    ):
        """Test injecting TLS config."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": sample_tls_certificate}
        }

        base_config = {"verify_mode": "CERT_REQUIRED"}
        config = await secret_injector.inject_tls_config("api-server", base_config)

        assert config["verify_mode"] == "CERT_REQUIRED"
        assert "cert_pem" in config
        assert "key_pem" in config
        assert "ca_pem" in config


@pytest.mark.asyncio
class TestDatabaseCredentials:
    """Test DatabaseCredentials dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        creds = DatabaseCredentials(
            username="user",
            password="pass",
            host="localhost",
            port=5432,
        )

        d = creds.to_dict()

        assert d["username"] == "user"
        assert d["password"] == "pass"
        assert d["host"] == "localhost"
        assert d["port"] == 5432
        assert d["database"] is None

    def test_optional_fields(self):
        """Test credentials with optional fields."""
        creds = DatabaseCredentials(
            username="user",
            password="pass",
        )

        assert creds.host is None
        assert creds.port is None
        assert creds.database is None


@pytest.mark.asyncio
class TestApiCredentials:
    """Test ApiCredentials dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        creds = ApiCredentials(
            api_key="key",
            api_secret="secret",
            client_id="client",
        )

        d = creds.to_dict()

        assert d["api_key"] == "key"
        assert d["api_secret"] == "secret"
        assert d["client_id"] == "client"
        assert d["api_token"] is None


@pytest.mark.asyncio
class TestTLSCertificate:
    """Test TLSCertificate dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        cert = TLSCertificate(
            certificate="CERT",
            private_key="KEY",
            ca_chain="CA",
        )

        d = cert.to_dict()

        assert d["certificate"] == "CERT"
        assert d["private_key"] == "KEY"
        assert d["ca_chain"] == "CA"

    def test_optional_ca_chain(self):
        """Test certificate without CA chain."""
        cert = TLSCertificate(
            certificate="CERT",
            private_key="KEY",
        )

        assert cert.ca_chain is None
