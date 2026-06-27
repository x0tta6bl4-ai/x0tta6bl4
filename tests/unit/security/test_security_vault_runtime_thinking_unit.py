import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.security.production_hardening import (
    ProductionHardeningManager,
    RequestAuditor,
    SecretVaultManager,
)
from src.security.secrets_manager import SecretsManager
from src.security.vault_monitoring import VaultHealthMonitor
from src.security.vault_secrets import (
    ApiCredentials,
    DatabaseCredentials,
    SecretInjector,
    SecretType,
    TLSCertificate,
    VaultSecretManager,
)


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


def test_secrets_manager_thinking_status_redacts_env_secret_and_path():
    with patch.dict(
        "os.environ",
        {"SECRET_PATH_DB_PASSWORD_KEY": "secret-env-password-value"},
        clear=True,
    ):
        manager = SecretsManager()
        assert (
            manager.get_secret("secret/path", "db_password_key")
            == "secret-env-password-value"
        )

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        status,
        "secret/path",
        "db_password_key",
        "SECRET_PATH_DB_PASSWORD_KEY",
        "secret-env-password-value",
    )


class _FakeVaultClient:
    def __init__(self):
        self.put_calls = []

    async def get_secret(self, path, secret_key=None):
        if secret_key == "key":
            return "secret-encryption-key-value"
        if "database" in path:
            return {
                "username": "secret-db-user",
                "password": "secret-db-password",
                "host": "secret-db-host",
                "database": "secret-db-name",
                "connection_string": "secret-db-connection-string",
            }
        if "api-keys" in path:
            return {
                "api_key": "secret-api-key",
                "api_secret": "secret-api-secret",
                "api_token": "secret-api-token",
                "client_secret": "secret-client-secret",
            }
        if "certificates" in path:
            return {
                "certificate": "secret-cert-pem",
                "private_key": "secret-private-key-pem",
                "ca_chain": "secret-ca-chain",
            }
        return {"value": "secret-generic-value"}

    async def put_secret(self, path, value):
        self.put_calls.append((path, value))

    async def list_secrets(self, path):
        return ["secret-listed-name"]


@pytest.mark.asyncio
async def test_vault_secret_manager_and_injector_thinking_status_redacts_values():
    client = _FakeVaultClient()
    manager = VaultSecretManager(client)
    db_creds = await manager.get_database_credentials("secret-main-db")
    await manager.store_api_credentials(
        "secret-stripe",
        ApiCredentials(
            api_key="secret-api-key",
            api_secret="secret-api-secret",
            api_token="secret-api-token",
        ),
    )
    await manager.store_database_credentials("secret-main-db", db_creds)
    await manager.store_tls_certificate(
        "secret-cert-name",
        TLSCertificate(
            certificate="secret-cert-pem",
            private_key="secret-private-key-pem",
            ca_chain="secret-ca-chain",
        ),
    )
    await manager.get_encryption_key("secret-key-name")
    await manager.list_secrets(SecretType.API_KEY)

    manager_status = manager.get_thinking_status()
    _assert_redacted(
        manager_status,
        "secret-main-db",
        "secret-stripe",
        "secret-cert-name",
        "secret-key-name",
        "secret-db-user",
        "secret-db-password",
        "secret-api-key",
        "secret-api-secret",
        "secret-private-key-pem",
        "secret-encryption-key-value",
        "secret-listed-name",
    )

    manager.get_database_credentials = AsyncMock(
        return_value=DatabaseCredentials(
            username="secret-db-user",
            password="secret-db-password",
            host="secret-db-host",
            database="secret-db-name",
            connection_string="secret-db-connection-string",
        )
    )
    injector = SecretInjector(manager)
    config = await injector.inject_database_config(
        "secret-main-db",
        {"existing_secret_config_key": "secret-existing-config-value"},
    )
    assert config["password"] == "secret-db-password"

    injector_status = injector.get_thinking_status()
    assert injector_status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        injector_status,
        "secret-main-db",
        "existing_secret_config_key",
        "secret-existing-config-value",
        "secret-db-user",
        "secret-db-password",
        "secret-db-connection-string",
    )


class _FakeVaultHealthClient:
    vault_addr = "https://secret-vault-address:8200"
    token_expiry = datetime.now() + timedelta(seconds=20)

    def __init__(self):
        self.authenticated = True
        self.is_healthy = True
        self.is_degraded = False
        self.client = object()

    async def health_check(self):
        return True

    def get_cache_stats(self):
        return {"secret-cache-key": "secret-cache-value"}


@pytest.mark.asyncio
async def test_vault_health_monitor_thinking_status_redacts_addr_and_expiry():
    client = _FakeVaultHealthClient()
    monitor = VaultHealthMonitor(
        client,
        check_interval=5,
        token_warning_threshold=30,
        on_token_expiry_warning=lambda: None,
    )

    await monitor._perform_health_check()
    monitor.get_status()

    status = monitor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "https://secret-vault-address:8200",
        "secret-vault-address",
        client.token_expiry.isoformat(),
    )


def test_production_hardening_thinking_status_redacts_secrets_and_requests():
    vault = SecretVaultManager()
    vault.store_secret("secret-local-key", "secret-local-value", rotation_days=45)
    assert vault.retrieve_secret("secret-local-key", "secret-accessor") is not None
    assert vault.rotate_secret("secret-local-key", "secret-new-value") is True

    vault_status = vault.get_thinking_status()
    assert vault_status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        vault_status,
        "secret-local-key",
        "secret-local-value",
        "secret-new-value",
        "secret-accessor",
    )

    auditor = RequestAuditor()
    for _ in range(101):
        auditor.log_request("POST", "/secret-admin-path", "10.9.8.7", 429, 25.0)
    suspicious = auditor.detect_suspicious_patterns()
    assert suspicious[0]["ip"] == "10.9.8.7"

    auditor_status = auditor.get_thinking_status()
    _assert_redacted(auditor_status, "/secret-admin-path", "10.9.8.7")

    manager = ProductionHardeningManager()
    manager.request_auditor = auditor
    manager.get_security_status()
    manager_status = manager.get_thinking_status()
    _assert_redacted(manager_status, "/secret-admin-path", "10.9.8.7")
