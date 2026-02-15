"""
Integration tests for Vault integration.

These tests verify the end-to-end workflow of the Vault integration,
including client initialization, authentication, secret operations,
and monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from src.config.vault_config import VaultIntegrationConfig, load_vault_config
from src.security.vault_client import (VaultAuthError, VaultClient,
                                       VaultSecretError)
from src.security.vault_monitoring import (VaultHealthMonitor,
                                           VaultMetricsReporter)
from src.security.vault_secrets import SecretInjector, VaultSecretManager


@pytest.mark.asyncio
class TestVaultIntegrationWorkflow:
    """Test complete Vault integration workflows."""

    async def test_full_workflow(
        self, vault_integration_config, mock_hvac_client, mock_kubernetes_auth
    ):
        """Test complete workflow from connection to secret retrieval."""
        with patch("src.security.vault_client.hvac.Client") as mock_hvac:
            with patch("src.security.vault_client.Kubernetes") as mock_k8s_class:
                mock_hvac.return_value = mock_hvac_client
                mock_k8s_class.return_value = mock_kubernetes_auth

                # 1. Create client
                client = VaultClient(
                    vault_addr=vault_integration_config.client.vault_addr,
                    k8s_role=vault_integration_config.client.k8s_role,
                )

                # 2. Connect and authenticate
                with patch("builtins.open", mock_open(read_data="test-jwt")):
                    await client.connect()

                assert client.authenticated is True

                # 3. Create secret manager
                manager = VaultSecretManager(client)

                # 4. Mock secret retrieval
                mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
                    "data": {
                        "data": {
                            "username": "testuser",
                            "password": "testpass",
                        }
                    }
                }

                # 5. Retrieve credentials
                creds = await manager.get_database_credentials("test-db")
                assert creds.username == "testuser"
                assert creds.password == "testpass"

                # 6. Cleanup
                await client.close()

    async def test_health_monitor_integration(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test health monitor with real client."""
        mock_hvac_client.sys.read_health_status.return_value = {
            "initialized": True,
            "sealed": False,
        }

        health_changes = []

        def on_health_change(healthy):
            health_changes.append(healthy)

        monitor = VaultHealthMonitor(
            authenticated_vault_client,
            check_interval=1,
            on_health_change=on_health_change,
        )

        # Start monitoring
        await monitor.start()

        # Wait for one check
        await asyncio.sleep(1.5)

        # Stop monitoring
        await monitor.stop()

        # Verify health was checked
        assert mock_hvac_client.sys.read_health_status.called

    async def test_metrics_reporter_integration(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test metrics reporter with real client."""
        mock_hvac_client.sys.read_health_status.return_value = {
            "initialized": True,
            "sealed": False,
        }

        reporter = VaultMetricsReporter(authenticated_vault_client)

        # Test health summary
        summary = await reporter.get_health_summary()

        assert summary["vault_addr"] == authenticated_vault_client.vault_addr
        assert summary["authenticated"] is True
        assert "cache_stats" in summary

    async def test_concurrent_secret_access(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test concurrent secret access."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"key": "value"}}
        }

        # Access secrets concurrently
        async def get_secret(i):
            return await authenticated_vault_client.get_secret(f"proxy/test{i}")

        tasks = [get_secret(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(r == {"key": "value"} for r in results)

    async def test_token_refresh_during_operations(
        self, authenticated_vault_client, mock_kubernetes_auth
    ):
        """Test token refresh doesn't break ongoing operations."""
        # Set token as expired
        authenticated_vault_client.token_expiry = datetime.now() - timedelta(seconds=1)

        jwt_content = "test-jwt-token"

        with patch("builtins.open", mock_open(read_data=jwt_content)):
            # This should trigger refresh
            await authenticated_vault_client._ensure_authenticated()

        assert mock_kubernetes_auth.login.called


@pytest.mark.asyncio
class TestVaultErrorHandling:
    """Test error handling in integration scenarios."""

    async def test_graceful_degradation_on_vault_unavailable(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test graceful degradation when Vault is unavailable."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "Connection refused"
        )

        with pytest.raises(VaultSecretError):
            await authenticated_vault_client.get_secret("proxy/test")

        # Client should be in degraded state
        assert authenticated_vault_client.is_degraded is True

    async def test_recovery_after_vault_restored(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test recovery after Vault becomes available."""
        # First call fails
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = [
            Exception("Connection refused"),
            {"data": {"data": {"key": "value"}}},
        ]

        # First attempt should fail
        with pytest.raises(VaultSecretError):
            await authenticated_vault_client.get_secret("proxy/test", use_cache=False)

        # Second attempt should succeed
        result = await authenticated_vault_client.get_secret(
            "proxy/test", use_cache=False
        )
        assert result == {"key": "value"}

    async def test_cache_fallback_on_vault_error(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test using cached values when Vault is unavailable."""
        # First, populate cache
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"key": "cached-value"}}
        }
        await authenticated_vault_client.get_secret("proxy/cached")

        # Now Vault fails
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "Connection refused"
        )

        # Should return cached value
        result = await authenticated_vault_client.get_secret("proxy/cached")
        assert result == {"key": "cached-value"}


@pytest.mark.asyncio
class TestVaultConfiguration:
    """Test configuration loading and validation."""

    def test_load_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("VAULT_ADDR", "https://vault-test:8200")
        monkeypatch.setenv("VAULT_K8S_ROLE", "test-role")
        monkeypatch.setenv("VAULT_CACHE_TTL", "1800")

        config = load_vault_config()

        assert config.client.vault_addr == "https://vault-test:8200"
        assert config.client.k8s_role == "test-role"
        assert config.client.cache_ttl == 1800

    def test_config_validation_valid(self):
        """Test validation of valid configuration."""
        from src.config.vault_config import validate_vault_config

        config = VaultIntegrationConfig()
        errors = validate_vault_config(config)

        assert len(errors) == 0

    def test_config_validation_missing_addr(self):
        """Test validation with missing Vault address."""
        from src.config.vault_config import validate_vault_config

        config = VaultIntegrationConfig()
        config.client.vault_addr = ""
        errors = validate_vault_config(config)

        assert any("VAULT_ADDR" in e for e in errors)

    def test_config_validation_invalid_threshold(self):
        """Test validation with invalid refresh threshold."""
        from src.config.vault_config import validate_vault_config

        config = VaultIntegrationConfig()
        config.client.token_refresh_threshold = 1.5
        errors = validate_vault_config(config)

        assert any("threshold" in e.lower() for e in errors)


@pytest.mark.asyncio
class TestVaultSecretRotation:
    """Test secret rotation workflows."""

    async def test_database_credentials_rotation(
        self, secret_manager, mock_hvac_client
    ):
        """Test rotating database credentials."""
        # Store initial credentials
        initial_creds = {
            "username": "olduser",
            "password": "oldpass",
        }
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": initial_creds}
        }

        old_creds = await secret_manager.get_database_credentials("main-db")
        assert old_creds.username == "olduser"

        # Rotate credentials
        new_creds = {
            "username": "newuser",
            "password": "newpass",
        }
        await secret_manager.store_database_credentials("main-db", new_creds)

        # Verify new credentials are stored
        call_args = mock_hvac_client.secrets.kv.v2.create_or_update_secret.call_args
        assert call_args[1]["secret"]["username"] == "newuser"

    async def test_api_key_rotation(self, secret_manager, mock_hvac_client):
        """Test rotating API keys."""
        # Rotate API key
        new_creds = ApiCredentials(
            api_key="new-api-key",
            api_secret="new-api-secret",
        )

        await secret_manager.store_api_credentials("stripe", new_creds)

        # Verify rotation
        call_args = mock_hvac_client.secrets.kv.v2.create_or_update_secret.call_args
        assert call_args[1]["secret"]["api_key"] == "new-api-key"


# Helper function for mock_open
from unittest.mock import mock_open
