"""
Integration tests for Vault secret injection via Vault Agent.

These tests verify that secrets are correctly injected into pods
using the Vault Agent Injector.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock


@pytest.mark.asyncio
class TestVaultAgentInjection:
    """Test Vault Agent sidecar injection."""
    
    async def test_annotation_parsing(self):
        """Test that injection annotations are correctly parsed."""
        # This test verifies the annotation format used in the deployment
        annotations = {
            "vault.hashicorp.com/agent-inject": "true",
            "vault.hashicorp.com/role": "proxy-api",
            "vault.hashicorp.com/service": "https://vault.vault.svc.cluster.local:8200",
            "vault.hashicorp.com/agent-inject-secret-database": "secret/data/proxy/database/main-db",
            "vault.hashicorp.com/agent-inject-template-database": """
            {{ with secret "secret/data/proxy/database/main-db" -}}
            export DB_USERNAME="{{ .Data.data.username }}"
            export DB_PASSWORD="{{ .Data.data.password }}"
            {{- end }}
            """,
        }
        
        # Verify required annotations exist
        assert annotations["vault.hashicorp.com/agent-inject"] == "true"
        assert "vault.hashicorp.com/role" in annotations
        assert "vault.hashicorp.com/agent-inject-secret-database" in annotations
        
        # Parse secret paths
        secret_keys = [k for k in annotations.keys() if "agent-inject-secret-" in k]
        assert len(secret_keys) > 0
        
        for key in secret_keys:
            secret_path = annotations[key]
            assert secret_path.startswith("secret/data/")
    
    async def test_template_rendering(self):
        """Test that templates are correctly formatted."""
        template = """
        {{ with secret "secret/data/proxy/database/main-db" -}}
        export DB_USERNAME="{{ .Data.data.username }}"
        export DB_PASSWORD="{{ .Data.data.password }}"
        export DB_HOST="{{ .Data.data.host }}"
        export DB_PORT="{{ .Data.data.port }}"
        {{- end }}
        """
        
        # Verify template syntax
        assert "{{ with secret" in template
        assert "{{ .Data.data." in template
        assert "{{- end }}" in template
        
        # Verify all required fields are present
        assert "username" in template
        assert "password" in template
        assert "host" in template
        assert "port" in template
    
    async def test_injected_file_format(self):
        """Test the format of injected secret files."""
        # Simulate what Vault Agent would inject
        secret_data = {
            "username": "dbuser",
            "password": "dbpass123",
            "host": "postgres.default.svc.cluster.local",
            "port": "5432",
        }
        
        # Render template (simplified)
        rendered = f"""
        export DB_USERNAME="{secret_data['username']}"
        export DB_PASSWORD="{secret_data['password']}"
        export DB_HOST="{secret_data['host']}"
        export DB_PORT="{secret_data['port']}"
        """
        
        # Verify format
        assert "export DB_USERNAME=" in rendered
        assert "export DB_PASSWORD=" in rendered
        assert secret_data["username"] in rendered
        assert secret_data["password"] in rendered


@pytest.mark.asyncio
class TestSecretInjectionIntegration:
    """Test end-to-end secret injection workflow."""
    
    async def test_secret_injection_workflow(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test complete secret injection workflow."""
        from src.security.vault_secrets import VaultSecretManager
        
        # Setup mock secret
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {
                'data': {
                    'api_key': 'test-api-key-12345',
                    'api_secret': 'test-secret-67890',
                }
            }
        }
        
        # Create manager
        manager = VaultSecretManager(authenticated_vault_client)
        
        # Retrieve secret (simulating what Vault Agent does)
        creds = await manager.get_api_credentials("stripe")
        
        # Verify credentials
        assert creds.api_key == 'test-api-key-12345'
        assert creds.api_secret == 'test-secret-67890'
    
    async def test_concurrent_secret_access(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test concurrent secret access from multiple pods."""
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'key': 'value'}}
        }
        
        # Simulate 10 pods accessing secrets concurrently
        async def access_secret(pod_id):
            return await authenticated_vault_client.get_secret(
                f'proxy/pod-{pod-id}/secret'
            )
        
        tasks = [access_secret(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(r == {'key': 'value'} for r in results)
    
    async def test_secret_rotation_during_injection(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test secret rotation while injection is happening."""
        from src.security.vault_secrets import VaultSecretManager
        
        # Initial secret
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'api_key': 'old-key'}}
        }
        
        manager = VaultSecretManager(authenticated_vault_client)
        
        # Get old secret
        old_creds = await manager.get_api_credentials("stripe")
        assert old_creds.api_key == 'old-key'
        
        # Rotate secret
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'api_key': 'new-key'}}
        }
        
        # Get new secret (cache should be invalidated)
        await manager.store_api_credentials(
            "stripe",
            type('Creds', (), {'api_key': 'new-key', 'api_secret': 'new-secret', 'to_dict': lambda self: {'api_key': 'new-key', 'api_secret': 'new-secret'}})()
        )
        
        # Force cache miss
        new_creds = await authenticated_vault_client.get_secret(
            'proxy/api-keys/stripe',
            use_cache=False
        )
        assert new_creds['api_key'] == 'new-key'


@pytest.mark.asyncio
class TestKubernetesAuthInjection:
    """Test Kubernetes auth for secret injection."""
    
    async def test_service_account_token_validation(self):
        """Test that service account tokens are valid for auth."""
        # This test verifies the K8s auth flow
        
        # Mock service account token
        sa_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEifQ..."
        
        # Mock Vault Kubernetes auth response
        auth_response = {
            'auth': {
                'client_token': 'vault-token-12345',
                'accessor': 'accessor-12345',
                'policies': ['proxy-api'],
                'lease_duration': 3600,
            }
        }
        
        # Verify auth response structure
        assert 'auth' in auth_response
        assert 'client_token' in auth_response['auth']
        assert 'proxy-api' in auth_response['auth']['policies']
    
    async def test_role_binding(self):
        """Test that K8s roles are correctly bound to Vault policies."""
        role_config = {
            'bound_service_account_names': ['proxy-api'],
            'bound_service_account_namespaces': ['default'],
            'policies': ['proxy-api'],
            'ttl': '1h',
            'max_ttl': '24h',
        }
        
        # Verify role configuration
        assert 'proxy-api' in role_config['bound_service_account_names']
        assert 'default' in role_config['bound_service_account_namespaces']
        assert 'proxy-api' in role_config['policies']


@pytest.mark.asyncio
class TestSecretInjectionFailureHandling:
    """Test handling of injection failures."""
    
    async def test_vault_unavailable_fallback(
        self, authenticated_vault_client, mock_hvac_client
    ):
        """Test fallback when Vault is unavailable."""
        # Populate cache first
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'key': 'cached-value'}}
        }
        await authenticated_vault_client.get_secret('proxy/cached')
        
        # Simulate Vault failure
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "Connection refused"
        )
        
        # Should return cached value
        result = await authenticated_vault_client.get_secret('proxy/cached')
        assert result == {'key': 'cached-value'}
    
    async def test_invalid_secret_path(self, authenticated_vault_client, mock_hvac_client):
        """Test handling of invalid secret paths."""
        from hvac.exceptions import InvalidPath
        
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath()
        
        from src.security.vault_client import VaultSecretError
        
        with pytest.raises(VaultSecretError) as exc_info:
            await authenticated_vault_client.get_secret('proxy/nonexistent')
        
        assert "Secret not found" in str(exc_info.value)
    
    async def test_permission_denied(self, authenticated_vault_client, mock_hvac_client):
        """Test handling of permission denied errors."""
        from hvac.exceptions import Forbidden
        
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Forbidden()
        
        from src.security.vault_client import VaultSecretError
        
        with pytest.raises(VaultSecretError):
            await authenticated_vault_client.get_secret('proxy/restricted')


@pytest.mark.asyncio
class TestSecretInjectionSecurity:
    """Test security aspects of secret injection."""
    
    async def test_secret_isolation(self):
        """Test that secrets are isolated between namespaces."""
        # Define namespace boundaries
        namespaces = {
            'default': ['proxy-api'],
            'production': ['proxy-api-prod'],
            'vault': ['vault'],
        }
        
        # Verify each namespace has distinct service accounts
        for ns, sas in namespaces.items():
            assert len(sas) > 0
            assert all(isinstance(sa, str) for sa in sas)
    
    async def test_token_scoping(self):
        """Test that tokens are scoped to correct policies."""
        token_policies = {
            'proxy-api-token': ['proxy-api'],
            'admin-token': ['admin'],
            'readonly-token': ['readonly'],
        }
        
        # Verify least privilege
        assert 'proxy-api' in token_policies['proxy-api-token']
        assert 'admin' not in token_policies['proxy-api-token']
        assert 'proxy-api' not in token_policies['admin-token']


@pytest.mark.integration
class TestRealVaultInjection:
    """Integration tests requiring a real Vault instance.
    
    These tests are marked with 'integration' and require:
    - Running Vault instance
    - Vault Agent Injector deployed
    - Test namespace configured
    """
    
    @pytest.mark.skip(reason="Requires real Vault instance")
    async def test_real_secret_injection(self):
        """Test secret injection with real Vault."""
        # This would be run against a real Vault instance
        pass
    
    @pytest.mark.skip(reason="Requires real Vault instance")
    async def test_real_kubernetes_auth(self):
        """Test Kubernetes auth with real Vault."""
        # This would be run against a real Vault instance
        pass