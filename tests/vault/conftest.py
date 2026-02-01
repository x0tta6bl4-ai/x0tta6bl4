"""
Pytest fixtures for Vault integration tests.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Generator

# Import the modules under test
from src.security.vault_client import VaultClient, VaultAuthError, VaultSecretError
from src.security.vault_auth import K8sAuthHandler, K8sAuthConfig
from src.security.vault_secrets import (
    VaultSecretManager,
    SecretInjector,
    SecretType,
    DatabaseCredentials,
    ApiCredentials,
    TLSCertificate,
)
from src.security.vault_monitoring import VaultHealthMonitor, VaultMetricsReporter
from src.config.vault_config import (
    VaultClientConfig,
    VaultMonitorConfig,
    VaultIntegrationConfig,
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def vault_client_config():
    """Create a test Vault client configuration."""
    return VaultClientConfig(
        vault_addr="https://vault-test:8200",
        vault_namespace="test",
        k8s_role="test-role",
        k8s_jwt_path="/tmp/test-jwt",
        verify_ca=None,  # Disable TLS verification for tests
        max_retries=2,
        retry_delay=0.1,
        retry_backoff=1.0,
        cache_ttl=60,
        token_refresh_threshold=0.8,
    )


@pytest.fixture
def mock_hvac_client():
    """Create a mock hvac Client."""
    mock_client = Mock()
    
    # Mock adapter for Kubernetes auth
    mock_adapter = Mock()
    mock_client.adapter = mock_adapter
    
    # Mock secrets KV v2
    mock_secrets = Mock()
    mock_kv = Mock()
    mock_v2 = Mock()
    mock_secrets.kv = mock_kv
    mock_kv.v2 = mock_v2
    mock_client.secrets = mock_secrets
    
    # Mock sys for health checks
    mock_sys = Mock()
    mock_client.sys = mock_sys
    
    return mock_client


@pytest.fixture
def mock_kubernetes_auth():
    """Create a mock Kubernetes auth method."""
    mock_auth = Mock()
    mock_auth.login.return_value = {
        'auth': {
            'client_token': 'test-token-12345',
            'lease_duration': 3600,
        }
    }
    return mock_auth


@pytest.fixture
def vault_client(vault_client_config, mock_hvac_client, mock_kubernetes_auth):
    """Create a VaultClient with mocked dependencies."""
    with patch('src.security.vault_client.hvac.Client') as mock_hvac:
        with patch('src.security.vault_client.Kubernetes') as mock_k8s_class:
            mock_hvac.return_value = mock_hvac_client
            mock_k8s_class.return_value = mock_kubernetes_auth
            
            client = VaultClient(
                vault_addr=vault_client_config.vault_addr,
                vault_namespace=vault_client_config.vault_namespace,
                k8s_role=vault_client_config.k8s_role,
                k8s_jwt_path=vault_client_config.k8s_jwt_path,
                verify_ca=vault_client_config.verify_ca,
                max_retries=vault_client_config.max_retries,
                retry_delay=vault_client_config.retry_delay,
                retry_backoff=vault_client_config.retry_backoff,
                cache_ttl=vault_client_config.cache_ttl,
                token_refresh_threshold=vault_client_config.token_refresh_threshold,
            )
            yield client


@pytest.fixture
def authenticated_vault_client(vault_client, mock_hvac_client, mock_kubernetes_auth):
    """Create an already authenticated VaultClient."""
    # Set up the client as if connect() was called
    vault_client.client = mock_hvac_client
    vault_client._k8s_auth = mock_kubernetes_auth
    vault_client.token = 'test-token-12345'
    vault_client.token_ttl = 3600
    vault_client.token_expiry = datetime.now() + timedelta(seconds=2880)  # 80% of 3600
    vault_client._authenticated = True
    vault_client._degraded = False
    return vault_client


@pytest.fixture
def k8s_auth_config():
    """Create a test K8s auth configuration."""
    return K8sAuthConfig(
        role="test-role",
        jwt_path="/tmp/test-jwt",
        ca_cert_path="/tmp/test-ca.crt",
        namespace_path="/tmp/test-namespace",
        token_expiry_days=1,
    )


@pytest.fixture
def k8s_auth_handler(k8s_auth_config, tmp_path):
    """Create a K8sAuthHandler with temporary files."""
    # Create temporary files
    jwt_file = tmp_path / "test-jwt"
    jwt_file.write_text("test-jwt-token")
    
    ca_file = tmp_path / "test-ca.crt"
    ca_file.write_text("test-ca-cert")
    
    ns_file = tmp_path / "test-namespace"
    ns_file.write_text("test-namespace")
    
    config = K8sAuthConfig(
        role=k8s_auth_config.role,
        jwt_path=str(jwt_file),
        ca_cert_path=str(ca_file),
        namespace_path=str(ns_file),
    )
    
    return K8sAuthHandler(config)


@pytest.fixture
def secret_manager(authenticated_vault_client):
    """Create a VaultSecretManager with authenticated client."""
    return VaultSecretManager(authenticated_vault_client)


@pytest.fixture
def secret_injector(secret_manager):
    """Create a SecretInjector."""
    return SecretInjector(secret_manager)


@pytest.fixture
def health_monitor(authenticated_vault_client):
    """Create a VaultHealthMonitor."""
    return VaultHealthMonitor(
        authenticated_vault_client,
        check_interval=1,
    )


@pytest.fixture
def metrics_reporter(authenticated_vault_client):
    """Create a VaultMetricsReporter."""
    return VaultMetricsReporter(authenticated_vault_client)


@pytest.fixture
def sample_database_credentials():
    """Create sample database credentials."""
    return {
        'username': 'dbuser',
        'password': 'dbpass123',
        'host': 'db.example.com',
        'port': 5432,
        'database': 'mydb',
        'connection_string': 'postgresql://dbuser:dbpass123@db.example.com:5432/mydb',
    }


@pytest.fixture
def sample_api_credentials():
    """Create sample API credentials."""
    return {
        'api_key': 'api-key-12345',
        'api_secret': 'api-secret-67890',
        'client_id': 'client-123',
        'client_secret': 'client-secret-456',
    }


@pytest.fixture
def sample_tls_certificate():
    """Create sample TLS certificate."""
    return {
        'certificate': '-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----',
        'private_key': '-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----',
        'ca_chain': '-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----',
    }


@pytest.fixture
def mock_secret_response(sample_database_credentials):
    """Create a mock secret response from Vault."""
    return {
        'data': {
            'data': sample_database_credentials,
            'metadata': {
                'version': 1,
                'created_time': datetime.now().isoformat(),
            }
        }
    }


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset Prometheus registry before each test."""
    # Import here to avoid issues if prometheus_client is not installed
    try:
        from prometheus_client import REGISTRY
        # Collect all collectors to clear
        collectors = list(REGISTRY._collector_to_names.keys())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass
    except ImportError:
        pass
    yield


@pytest.fixture
def vault_integration_config():
    """Create a complete Vault integration configuration."""
    return VaultIntegrationConfig(
        client=VaultClientConfig(
            vault_addr="https://vault-test:8200",
            k8s_role="test-role",
        ),
        monitor=VaultMonitorConfig(
            check_interval=30,
            enabled=True,
        ),
    )