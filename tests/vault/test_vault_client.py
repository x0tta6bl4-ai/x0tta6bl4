"""
Unit tests for VaultClient.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, mock_open
from hvac.exceptions import InvalidPath, VaultError

from src.security.vault_client import (
    VaultClient,
    VaultAuthError,
    VaultSecretError,
)


@pytest.mark.asyncio
class TestVaultClientInitialization:
    """Test VaultClient initialization."""
    
    async def test_client_initialization(self, vault_client_config):
        """Test client initialization with config."""
        client = VaultClient(
            vault_addr=vault_client_config.vault_addr,
            k8s_role=vault_client_config.k8s_role,
        )
        
        assert client.vault_addr == vault_client_config.vault_addr
        assert client.k8s_role == vault_client_config.k8s_role
        assert client.client is None
        assert client._authenticated is False
        assert client._degraded is False
        await client.close()
    
    async def test_client_default_values(self):
        """Test client default configuration values."""
        client = VaultClient(
            vault_addr="https://vault:8200",
            k8s_role="proxy-api",
        )
        
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client.retry_backoff == 2.0
        assert client.cache_ttl == 3600
        assert client.token_refresh_threshold == 0.8
        await client.close()


@pytest.mark.asyncio
class TestVaultAuthentication:
    """Test Vault authentication."""
    
    async def test_successful_authentication(
        self, vault_client, mock_hvac_client, mock_kubernetes_auth
    ):
        """Test successful Vault authentication."""
        jwt_content = "test-jwt-token"
        
        with patch('builtins.open', mock_open(read_data=jwt_content)):
            await vault_client.connect()
        
        assert vault_client.token == 'test-token-12345'
        assert vault_client.token_ttl == 3600
        assert vault_client._authenticated is True
        assert vault_client.token_expiry is not None
        
        # Verify token expiry is set correctly (80% of TTL)
        expected_expiry = datetime.now() + timedelta(seconds=2880)
        assert abs((vault_client.token_expiry - expected_expiry).total_seconds()) < 5
    
    async def test_authentication_idempotent(
        self, vault_client, mock_hvac_client, mock_kubernetes_auth
    ):
        """Test that connect() is idempotent."""
        jwt_content = "test-jwt-token"
        
        with patch('builtins.open', mock_open(read_data=jwt_content)):
            await vault_client.connect()
            await vault_client.connect()  # Second call should be no-op
        
        # Should only authenticate once
        assert mock_kubernetes_auth.login.call_count == 1
    
    async def test_authentication_with_jwt_file_error(
        self, vault_client, mock_hvac_client
    ):
        """Test authentication failure when JWT file is missing."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            with pytest.raises(VaultAuthError) as exc_info:
                await vault_client.connect()
        
        assert "JWT token not found" in str(exc_info.value)
    
    async def test_authentication_retry_on_failure(
        self, vault_client, mock_hvac_client, mock_kubernetes_auth
    ):
        """Test retry logic on authentication failure."""
        mock_kubernetes_auth.login.side_effect = [
            Exception("First attempt failed"),
            Exception("Second attempt failed"),
            {'auth': {'client_token': 'test-token', 'lease_duration': 3600}},
        ]
        
        jwt_content = "test-jwt-token"
        
        with patch('builtins.open', mock_open(read_data=jwt_content)):
            await vault_client.connect()
        
        assert mock_kubernetes_auth.login.call_count == 3
        assert vault_client._authenticated is True


@pytest.mark.asyncio
class TestVaultSecretRetrieval:
    """Test secret retrieval operations."""
    
    async def test_get_secret_success(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test successful secret retrieval."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        result = await authenticated_vault_client.get_secret('proxy/database/main')
        
        assert result == sample_database_credentials
        mock_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path='proxy/database/main'
        )
    
    async def test_get_secret_specific_key(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test retrieving specific key from secret."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        result = await authenticated_vault_client.get_secret(
            'proxy/database/main',
            secret_key='username'
        )
        
        assert result == 'dbuser'
    
    async def test_get_secret_not_found(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test secret not found error."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath()
        
        with pytest.raises(VaultSecretError) as exc_info:
            await authenticated_vault_client.get_secret('proxy/nonexistent')
        
        assert "Secret not found" in str(exc_info.value)
    
    async def test_get_secret_vault_error(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test Vault error during secret retrieval."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = VaultError("Connection refused")
        
        with pytest.raises(VaultSecretError) as exc_info:
            await authenticated_vault_client.get_secret('proxy/test')
        
        assert "Retrieval failed" in str(exc_info.value)
    
    async def test_get_secret_caching(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test secret caching behavior."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        # First call - should hit Vault
        result1 = await authenticated_vault_client.get_secret('proxy/cached')
        assert result1 == sample_database_credentials
        
        # Second call - should use cache
        result2 = await authenticated_vault_client.get_secret('proxy/cached')
        assert result2 == sample_database_credentials
        
        # Vault API should only be called once
        assert mock_hvac_client.secrets.kv.v2.read_secret_version.call_count == 1
    
    async def test_get_secret_cache_bypass(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test bypassing cache with use_cache=False."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        # First call
        await authenticated_vault_client.get_secret('proxy/nocache')
        
        # Second call with cache bypass
        await authenticated_vault_client.get_secret('proxy/nocache', use_cache=False)
        
        # Vault API should be called twice
        assert mock_hvac_client.secrets.kv.v2.read_secret_version.call_count == 2


@pytest.mark.asyncio
class TestVaultSecretStorage:
    """Test secret storage operations."""
    
    async def test_put_secret_success(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test successful secret storage."""
        secret_data = {'key': 'value', 'secret': 'data'}
        
        await authenticated_vault_client.put_secret('proxy/new-secret', secret_data)
        
        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path='proxy/new-secret',
            secret=secret_data,
        )
    
    async def test_put_secret_invalidates_cache(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test that put_secret invalidates cache."""
        # First, cache a secret
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        await authenticated_vault_client.get_secret('proxy/to-update')
        
        # Update the secret
        new_data = {'updated': 'data'}
        await authenticated_vault_client.put_secret('proxy/to-update', new_data)
        
        # Cache should be invalidated
        assert 'proxy/to-update' not in authenticated_vault_client._secret_cache
    
    async def test_delete_secret_success(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test successful secret deletion."""
        await authenticated_vault_client.delete_secret('proxy/to-delete')
        
        mock_hvac_client.secrets.kv.v2.delete_secret_version.assert_called_once_with(
            path='proxy/to-delete'
        )


@pytest.mark.asyncio
class TestVaultTokenRefresh:
    """Test token refresh behavior."""
    
    async def test_token_refresh_on_expiry(
        self, authenticated_vault_client, mock_kubernetes_auth
    ):
        """Test automatic token refresh when token expires."""
        # Set token as expired
        authenticated_vault_client.token_expiry = datetime.now() - timedelta(seconds=1)
        
        jwt_content = "test-jwt-token"
        
        with patch('builtins.open', mock_open(read_data=jwt_content)):
            with patch.object(authenticated_vault_client, '_authenticate') as mock_auth:
                await authenticated_vault_client._ensure_authenticated()
                
                mock_auth.assert_called_once()
    
    async def test_cache_clear_on_token_refresh(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test that cache is cleared on token refresh."""
        # Populate cache
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        await authenticated_vault_client.get_secret('proxy/cached')
        
        # Trigger refresh
        authenticated_vault_client.token_expiry = datetime.now() - timedelta(seconds=1)
        
        jwt_content = "test-jwt-token"
        
        with patch('builtins.open', mock_open(read_data=jwt_content)):
            await authenticated_vault_client._ensure_authenticated()
        
        # Cache should be cleared
        assert len(authenticated_vault_client._secret_cache) == 0


@pytest.mark.asyncio
class TestVaultHealthCheck:
    """Test health check functionality."""
    
    async def test_health_check_success(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test successful health check."""
        mock_hvac_client.sys.read_health_status.return_value = {
            'initialized': True,
            'sealed': False,
        }
        
        is_healthy = await authenticated_vault_client.health_check()
        
        assert is_healthy is True
        assert authenticated_vault_client.is_degraded is False
    
    async def test_health_check_sealed(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test health check when Vault is sealed."""
        mock_hvac_client.sys.read_health_status.return_value = {
            'initialized': True,
            'sealed': True,
        }
        
        is_healthy = await authenticated_vault_client.health_check()
        
        assert is_healthy is False
        assert authenticated_vault_client.is_degraded is True
    
    async def test_health_check_not_initialized(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test health check when Vault is not initialized."""
        mock_hvac_client.sys.read_health_status.return_value = {
            'initialized': False,
            'sealed': True,
        }
        
        is_healthy = await authenticated_vault_client.health_check()
        
        assert is_healthy is False
    
    async def test_health_check_client_not_connected(self, vault_client):
        """Test health check when client is not connected."""
        is_healthy = await vault_client.health_check()
        
        assert is_healthy is False


@pytest.mark.asyncio
class TestVaultCache:
    """Test caching functionality."""
    
    async def test_cache_stats(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test cache statistics."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        # Initial stats
        stats = authenticated_vault_client.get_cache_stats()
        assert stats['cached_secrets'] == 0
        
        # Add to cache
        await authenticated_vault_client.get_secret('proxy/test1')
        await authenticated_vault_client.get_secret('proxy/test2')
        
        stats = authenticated_vault_client.get_cache_stats()
        assert stats['cached_secrets'] == 2
    
    async def test_cache_expiry(
        self, authenticated_vault_client, mock_hvac_client, sample_database_credentials
    ):
        """Test cache expiry."""
        # Set very short cache TTL
        authenticated_vault_client.cache_ttl = 0
        
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': sample_database_credentials}
        }
        
        # First call
        await authenticated_vault_client.get_secret('proxy/expiring')
        
        # Wait for expiry
        await asyncio.sleep(0.1)
        
        # Second call - should hit Vault again
        await authenticated_vault_client.get_secret('proxy/expiring')
        
        assert mock_hvac_client.secrets.kv.v2.read_secret_version.call_count == 2


@pytest.mark.asyncio
class TestVaultClientClose:
    """Test client cleanup."""
    
    async def test_close_clears_resources(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test that close() clears all resources."""
        await authenticated_vault_client.close()
        
        assert authenticated_vault_client.client is None
        assert authenticated_vault_client._authenticated is False
        assert len(authenticated_vault_client._secret_cache) == 0
        mock_hvac_client.close.assert_called_once()
    
    async def test_close_idempotent(self, authenticated_vault_client):
        """Test that close() is idempotent."""
        await authenticated_vault_client.close()
        await authenticated_vault_client.close()  # Should not raise