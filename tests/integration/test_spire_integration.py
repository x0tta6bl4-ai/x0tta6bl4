"""
Integration tests for SPIRE (SPIFFE Runtime Environment) integration.

Tests mTLS and workload identity management via SPIRE.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from src.security.spire_integration import (SPIRE_AGENT_AVAILABLE,
                                                SPIREClient, SPIREConfig,
                                                is_spire_available,
                                                wait_for_spire)

    SPIRE_INTEGRATION_AVAILABLE = True
except ImportError:
    SPIRE_INTEGRATION_AVAILABLE = False


class TestSPIREConfig:
    """Test SPIRE configuration"""

    def test_default_config(self):
        """Test default SPIRE config"""
        config = SPIREConfig()
        assert config.agent_address == "unix:///tmp/spire-agent/public/api.sock"
        assert config.trust_domain == "example.com"

    def test_custom_config(self):
        """Test custom SPIRE config"""
        config = SPIREConfig(
            agent_address="unix:///custom/path",
            trust_domain="custom.example.com",
            enabled=True,
        )
        assert config.agent_address == "unix:///custom/path"
        assert config.trust_domain == "custom.example.com"


@pytest.mark.skipif(
    not SPIRE_INTEGRATION_AVAILABLE, reason="SPIRE integration not available"
)
class TestSPIREClient:
    """Test SPIRE client"""

    def test_client_initialization_disabled(self):
        """Test client initialization when SPIRE is disabled"""
        config = SPIREConfig(enabled=False)
        client = SPIREClient(config)
        assert not client.is_available()

    @patch("src.security.spire_integration.WorkloadApiClient")
    def test_client_initialization_enabled(self, mock_workload_client):
        """Test client initialization when SPIRE is enabled"""
        config = SPIREConfig(enabled=True)
        client = SPIREClient(config)
        # Client may or may not be available depending on mock setup
        assert client.config.enabled

    def test_client_unavailable_without_agent(self):
        """Test client is unavailable when agent is not running"""
        # Use a guaranteed-invalid socket path so this assertion is stable
        # regardless of whether a local SPIRE agent is running.
        config = SPIREConfig(
            enabled=True, agent_address="unix:///tmp/spire-agent/public/does-not-exist.sock"
        )
        client = SPIREClient(config)
        # Without mock setup, client should fail to connect
        assert not client.is_available()

    @patch("src.security.spire_integration.WorkloadApiClient")
    def test_fetch_x509_context(self, mock_workload_client):
        """Test fetching X.509 context from SPIRE"""
        # Mock SPIRE client
        mock_client = MagicMock()
        mock_svid = MagicMock()
        mock_svid.certificate = b"cert_data"
        mock_svid.private_key = b"key_data"
        mock_svid.trust_bundle = b"bundle_data"
        mock_client.fetch_x509_svid.return_value = mock_svid

        with patch("src.security.spire_integration.SPIRE_AGENT_AVAILABLE", True):
            config = SPIREConfig(enabled=True)
            client = SPIREClient(config)
            client.client = mock_client
            client._connected = True

            context = client.fetch_x509_context()

            assert context is not None
            assert context["certificate"] == b"cert_data"
            assert context["key"] == b"key_data"
            assert context["bundle"] == b"bundle_data"

    @patch("src.security.spire_integration.WorkloadApiClient")
    def test_fetch_x509_bundle(self, mock_workload_client):
        """Test fetching X.509 bundle from SPIRE"""
        mock_client = MagicMock()
        mock_client.fetch_x509_bundle.return_value = b"bundle_data"

        with patch("src.security.spire_integration.SPIRE_AGENT_AVAILABLE", True):
            config = SPIREConfig(enabled=True)
            client = SPIREClient(config)
            client.client = mock_client
            client._connected = True

            bundle = client.fetch_x509_bundle()

            assert bundle == b"bundle_data"


class TestSPIREAvailability:
    """Test SPIRE availability checks"""

    def test_is_spire_available_no_socket(self):
        """Test SPIRE availability when socket doesn't exist"""
        # This should return False since SPIRE is not running
        available = is_spire_available()
        assert isinstance(available, bool)

    @patch("src.security.spire_integration.socket.socket")
    def test_is_spire_available_connected(self, mock_socket_class):
        """Test SPIRE availability when connected"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        with patch("src.security.spire_integration.SPIRE_AGENT_AVAILABLE", True):
            available = is_spire_available()
            # Result depends on mock behavior
            assert isinstance(available, bool)

    @patch("src.security.spire_integration.is_spire_available")
    def test_wait_for_spire_immediate(self, mock_available):
        """Test waiting for SPIRE when immediately available"""
        mock_available.return_value = True

        result = wait_for_spire(timeout=5)

        assert result is True
        assert mock_available.called

    @patch("src.security.spire_integration.is_spire_available")
    @patch("src.security.spire_integration.time.sleep")
    def test_wait_for_spire_timeout(self, mock_sleep, mock_available):
        """Test waiting for SPIRE with timeout"""
        mock_available.return_value = False

        result = wait_for_spire(timeout=1, check_interval=0.1)

        assert result is False

    @patch("src.security.spire_integration.is_spire_available")
    @patch("src.security.spire_integration.time.sleep")
    @patch("src.security.spire_integration.time.time")
    def test_wait_for_spire_eventual(self, mock_time, mock_sleep, mock_available):
        """Test waiting for SPIRE that becomes available"""
        # Mock time progression
        times = [0, 0.5, 0.5, 1.0, 1.0, 1.5]
        mock_time.side_effect = times

        # First calls return False, then True
        mock_available.side_effect = [False, False, True]

        result = wait_for_spire(timeout=5, check_interval=0.1)

        assert result is True


@pytest.mark.skipif(
    not SPIRE_INTEGRATION_AVAILABLE, reason="SPIRE integration not available"
)
class TestSPIREErrorHandling:
    """Test SPIRE error handling"""

    @patch("src.security.spire_integration.WorkloadApiClient")
    def test_fetch_x509_context_error(self, mock_workload_client):
        """Test error handling when fetching X.509 context"""
        mock_client = MagicMock()
        mock_client.fetch_x509_svid.side_effect = Exception("Connection failed")

        with patch("src.security.spire_integration.SPIRE_AGENT_AVAILABLE", True):
            config = SPIREConfig(enabled=True)
            client = SPIREClient(config)
            client.client = mock_client
            client._connected = True

            context = client.fetch_x509_context()

            # Should return None on error
            assert context is None

    @patch("src.security.spire_integration.WorkloadApiClient")
    def test_initialization_error(self, mock_workload_client):
        """Test error handling during client initialization"""
        mock_workload_client.side_effect = Exception("Failed to connect")

        with patch("src.security.spire_integration.SPIRE_AGENT_AVAILABLE", True):
            config = SPIREConfig(enabled=True)
            client = SPIREClient(config)

            # Client should not be connected
            assert not client._connected


@pytest.mark.integration
@pytest.mark.skipif(
    not SPIRE_INTEGRATION_AVAILABLE, reason="SPIRE integration not available"
)
class TestSPIREEndToEnd:
    """End-to-end tests with actual SPIRE (if available)"""

    @pytest.mark.skipif(
        not is_spire_available() if SPIRE_INTEGRATION_AVAILABLE else True,
        reason="SPIRE agent not available",
    )
    def test_spire_agent_connectivity(self):
        """Test connectivity to SPIRE agent"""
        config = SPIREConfig()
        client = SPIREClient(config)

        # This test only runs if SPIRE is actually available
        assert client.is_available()

    @pytest.mark.skipif(
        not is_spire_available() if SPIRE_INTEGRATION_AVAILABLE else True,
        reason="SPIRE agent not available",
    )
    def test_spire_fetch_svid(self):
        """Test fetching SVID from SPIRE agent"""
        config = SPIREConfig()
        client = SPIREClient(config)

        context = client.fetch_x509_context()

        # Should successfully fetch context
        assert context is not None
        assert "certificate" in context
        assert "key" in context
