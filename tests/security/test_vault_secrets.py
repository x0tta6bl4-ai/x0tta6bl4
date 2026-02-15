import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.security.vault_secrets import (ApiCredentials, DatabaseCredentials,
                                        SecretInjector, SecretType,
                                        TLSCertificate, VaultSecretManager)

# Suppress INFO logs from src.security.vault_secrets for cleaner test output
logging.getLogger("src.security.vault_secrets").setLevel(logging.WARNING)


@pytest.fixture
def mock_vault_client():
    """Fixture to provide a mocked VaultClient instance."""
    client = AsyncMock()
    return client


@pytest.fixture
def vault_manager(mock_vault_client):
    """Fixture to provide a VaultSecretManager instance with a mocked client."""
    return VaultSecretManager(mock_vault_client)


@pytest.fixture
def secret_injector(vault_manager):
    """Fixture to provide a SecretInjector instance."""
    return SecretInjector(vault_manager)


@pytest.mark.asyncio
async def test_vault_secret_manager_init(mock_vault_client):
    """Test initialization of VaultSecretManager."""
    manager = VaultSecretManager(mock_vault_client)
    assert manager.vault_client == mock_vault_client
    # Verify default base path and secret paths
    assert manager._base_path == "proxy"
    assert manager._secret_paths[SecretType.DATABASE] == "proxy/database"


@pytest.mark.asyncio
async def test_get_database_credentials(vault_manager, mock_vault_client):
    """Test retrieving database credentials."""
    mock_vault_client.get_secret.return_value = {
        "username": "test_user",
        "password": "test_password",
        "host": "db.example.com",
        "port": 5432,
        "database": "test_db",
        "connection_string": "postgresql://test_user:test_password@db.example.com:5432/test_db",
    }
    creds = await vault_manager.get_database_credentials("test-db")
    mock_vault_client.get_secret.assert_called_once_with("proxy/database/test-db")
    assert creds.username == "test_user"
    assert creds.password == "test_password"
    assert creds.host == "db.example.com"
    assert creds.database == "test_db"


@pytest.mark.asyncio
async def test_store_database_credentials(vault_manager, mock_vault_client):
    """Test storing database credentials."""
    creds = DatabaseCredentials("new_user", "new_pass", host="new_host")
    await vault_manager.store_database_credentials("new-db", creds)
    mock_vault_client.put_secret.assert_called_once_with(
        "proxy/database/new-db", creds.to_dict()
    )


@pytest.mark.asyncio
async def test_get_api_credentials(vault_manager, mock_vault_client):
    """Test retrieving API credentials."""
    mock_vault_client.get_secret.return_value = {"api_key": "abc", "api_secret": "xyz"}
    creds = await vault_manager.get_api_credentials("stripe-api")
    mock_vault_client.get_secret.assert_called_once_with("proxy/api-keys/stripe-api")
    assert creds.api_key == "abc"
    assert creds.api_secret == "xyz"


@pytest.mark.asyncio
async def test_store_api_credentials(vault_manager, mock_vault_client):
    """Test storing API credentials."""
    creds = ApiCredentials("def", "uvw")
    await vault_manager.store_api_credentials("test-api", creds)
    mock_vault_client.put_secret.assert_called_once_with(
        "proxy/api-keys/test-api", creds.to_dict()
    )


@pytest.mark.asyncio
async def test_get_proxy_credentials(vault_manager, mock_vault_client):
    """Test retrieving proxy credentials."""
    mock_vault_client.get_secret.return_value = {"token": "proxy_token"}
    creds = await vault_manager.get_proxy_credentials()
    mock_vault_client.get_secret.assert_called_once_with("proxy/credentials/proxy-api")
    assert creds == {"token": "proxy_token"}


@pytest.mark.asyncio
async def test_rotate_proxy_credentials(vault_manager, mock_vault_client):
    """Test rotating proxy credentials."""
    new_creds = {"token": "new_proxy_token"}
    await vault_manager.rotate_proxy_credentials(new_creds)
    mock_vault_client.put_secret.assert_called_once_with(
        "proxy/credentials/proxy-api", new_creds
    )


@pytest.mark.asyncio
async def test_get_tls_certificate(vault_manager, mock_vault_client):
    """Test retrieving TLS certificate."""
    mock_vault_client.get_secret.return_value = {
        "certificate": "cert_pem",
        "private_key": "key_pem",
    }
    cert = await vault_manager.get_tls_certificate("web-cert")
    mock_vault_client.get_secret.assert_called_once_with("proxy/certificates/web-cert")
    assert cert.certificate == "cert_pem"
    assert cert.private_key == "key_pem"


@pytest.mark.asyncio
async def test_store_tls_certificate(vault_manager, mock_vault_client):
    """Test storing TLS certificate."""
    cert = TLSCertificate("new_cert", "new_key")
    await vault_manager.store_tls_certificate("new-cert", cert)
    mock_vault_client.put_secret.assert_called_once_with(
        "proxy/certificates/new-cert", cert.to_dict()
    )


@pytest.mark.asyncio
async def test_get_encryption_key(vault_manager, mock_vault_client):
    """Test retrieving encryption key."""
    mock_vault_client.get_secret.return_value = {"key": "enc_key"}
    key = await vault_manager.get_encryption_key("aes-key")
    mock_vault_client.get_secret.assert_called_once_with(
        "proxy/encryption/aes-key", secret_key="key"
    )
    assert key == {"key": "enc_key"}


@pytest.mark.asyncio
async def test_list_secrets(vault_manager, mock_vault_client):
    """Test listing secrets of a specific type."""
    mock_vault_client.list_secrets.return_value = ["secret1", "secret2"]
    secrets_list = await vault_manager.list_secrets(SecretType.API_KEY)
    mock_vault_client.list_secrets.assert_called_once_with("proxy/api-keys")
    assert secrets_list == ["secret1", "secret2"]


@pytest.mark.asyncio
async def test_inject_database_config(secret_injector, vault_manager, mocker):
    """Test injecting database configuration."""
    mocker.patch.object(
        vault_manager,
        "get_database_credentials",
        return_value=DatabaseCredentials("injected_user", "injected_pass"),
    )
    config = {"pool_size": 10}
    updated_config = await secret_injector.inject_database_config("my-db", config)
    assert updated_config["username"] == "injected_user"
    assert updated_config["password"] == "injected_pass"
    assert updated_config["pool_size"] == 10


@pytest.mark.asyncio
async def test_inject_api_config(secret_injector, vault_manager, mocker):
    """Test injecting API configuration."""
    mocker.patch.object(
        vault_manager,
        "get_api_credentials",
        return_value=ApiCredentials("injected_api_key", "injected_api_secret"),
    )
    config = {"timeout": 30}
    updated_config = await secret_injector.inject_api_config("my-api", config)
    assert updated_config["api_key"] == "injected_api_key"
    assert updated_config["api_secret"] == "injected_api_secret"
    assert updated_config["timeout"] == 30


@pytest.mark.asyncio
async def test_inject_tls_config(secret_injector, vault_manager, mocker):
    """Test injecting TLS configuration."""
    mocker.patch.object(
        vault_manager,
        "get_tls_certificate",
        return_value=TLSCertificate("injected_cert", "injected_key"),
    )
    config = {"port": 443}
    updated_config = await secret_injector.inject_tls_config("my-cert", config)
    assert updated_config["cert_pem"] == "injected_cert"
    assert updated_config["key_pem"] == "injected_key"
    assert updated_config["port"] == 443
