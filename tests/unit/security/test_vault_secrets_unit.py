"""Unit tests for Vault secret manager and injector."""

from unittest.mock import AsyncMock

import pytest

from src.security.vault_secrets import (ApiCredentials, DatabaseCredentials,
                                        SecretInjector, SecretType,
                                        VaultSecretManager)


@pytest.mark.asyncio
async def test_get_and_store_database_credentials():
    client = AsyncMock()
    client.get_secret.return_value = {
        "username": "u",
        "password": "p",
        "host": "db.local",
        "port": 5432,
        "database": "main",
    }
    mgr = VaultSecretManager(client)

    creds = await mgr.get_database_credentials("main-db")
    assert isinstance(creds, DatabaseCredentials)
    assert creds.username == "u"

    await mgr.store_database_credentials("main-db", creds)
    client.put_secret.assert_called()


@pytest.mark.asyncio
async def test_get_and_store_api_credentials():
    client = AsyncMock()
    client.get_secret.return_value = {"api_key": "k", "api_secret": "s"}
    mgr = VaultSecretManager(client)

    creds = await mgr.get_api_credentials("stripe")
    assert isinstance(creds, ApiCredentials)
    assert creds.api_key == "k"

    await mgr.store_api_credentials("stripe", creds)
    client.put_secret.assert_called()


@pytest.mark.asyncio
async def test_list_secrets_returns_empty_on_failure():
    client = AsyncMock()
    client.list_secrets.side_effect = RuntimeError("vault down")
    mgr = VaultSecretManager(client)

    result = await mgr.list_secrets(SecretType.API_KEY)
    assert result == []


@pytest.mark.asyncio
async def test_secret_injector_merges_config_and_strips_none():
    client = AsyncMock()
    mgr = VaultSecretManager(client)
    mgr.get_database_credentials = AsyncMock(
        return_value=DatabaseCredentials(
            username="user",
            password="pass",
            host="localhost",
            port=5432,
            database="db",
            connection_string=None,
        )
    )
    injector = SecretInjector(mgr)

    cfg = await injector.inject_database_config("main-db", {"pool_size": 5})
    assert cfg["username"] == "user"
    assert cfg["pool_size"] == 5
    assert "connection_string" not in cfg
