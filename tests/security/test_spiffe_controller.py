import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import src.security.spiffe.controller.spiffe_controller as spiffe_controller_module

spiffe_controller_module.OPTIMIZATIONS_AVAILABLE = (
    False  # Force disable optimizations for testing
)

from src.security.spiffe.agent.manager import AttestationStrategy
from src.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.security.spiffe.mtls.tls_context import MTLSContext, TLSRole
from src.security.spiffe.server.client import SPIREServerEntry
from src.security.spiffe.workload import X509SVID


@pytest.fixture
def mock_spire_agent_manager():
    """Mocks SPIREAgentManager."""
    agent_manager = MagicMock()
    agent_manager.start.return_value = True
    agent_manager.attest_node.return_value = True
    agent_manager.stop.return_value = True
    agent_manager.health_check.return_value = True
    return agent_manager


@pytest.fixture
def mock_workload_api_client():
    """Mocks WorkloadAPIClient."""
    workload_api = MagicMock()

    # Mock X509SVID
    mock_svid = MagicMock(spec=X509SVID)
    mock_svid.spiffe_id = "spiffe://test.mesh/workload/test"
    mock_svid.expiry = datetime.utcnow() + timedelta(hours=1)
    mock_svid.is_expired.return_value = False
    mock_svid.ttl = 3600

    workload_api.fetch_x509_svid.return_value = mock_svid
    workload_api.trust_bundle_path = None
    workload_api.validate_peer_svid.return_value = True
    return workload_api


@pytest.fixture
def mock_spire_server_client():
    """Mocks SPIREServerClient."""
    server_client = MagicMock()
    server_client.create_entry.return_value = "entry_id_123"
    server_client.list_entries.return_value = []
    server_client.get_server_status.return_value = {"status": "healthy"}
    return server_client


@pytest.fixture
def mock_certificate_validator():
    """Mocks CertificateValidator."""
    cert_validator = MagicMock()
    cert_validator.validate_certificate.return_value = (
        True,
        "spiffe://test.mesh/peer",
        None,
    )
    return cert_validator


@pytest.fixture
def spiffe_controller(
    mock_spire_agent_manager,
    mock_workload_api_client,
    mock_spire_server_client,
    mock_certificate_validator,
    mocker,
):
    """Fixture for SPIFFEController with mocked dependencies."""
    mocker.patch(
        "src.security.spiffe.controller.spiffe_controller.SPIREAgentManager",
        return_value=mock_spire_agent_manager,
    )
    mocker.patch(
        "src.security.spiffe.controller.spiffe_controller.WorkloadAPIClient",
        return_value=mock_workload_api_client,
    )
    mocker.patch(
        "src.security.spiffe.controller.spiffe_controller.SPIREServerClient",
        return_value=mock_spire_server_client,
    )
    mocker.patch(
        "src.security.spiffe.controller.spiffe_controller.CertificateValidator",
        return_value=mock_certificate_validator,
    )

    mocker.patch.dict(
        os.environ,
        {
            "SPIRE_MAX_TOKEN_TTL": "1h",
            "SPIRE_TOKEN_CACHE_SIZE": "100",
            "SPIRE_JWT_CACHE_SIZE": "50",
            "SPIRE_CONCURRENT_RPCS": "10",
            "SPIRE_PRIMARY_REGION": "us-test",
            "SPIRE_FALLBACK_REGIONS": "eu-test,asia-test",
        },
    )

    controller = SPIFFEController(trust_domain="test.mesh", enable_optimizations=True)
    return controller


def test_controller_initialization(
    spiffe_controller,
    mock_spire_agent_manager,
    mock_workload_api_client,
    mock_spire_server_client,
    mock_certificate_validator,
):
    """Test basic initialization of the SPIFFEController."""
    assert spiffe_controller.trust_domain == "test.mesh"
    assert spiffe_controller.agent == mock_spire_agent_manager
    assert spiffe_controller.workload_api == mock_workload_api_client
    assert spiffe_controller.server_client == mock_spire_server_client
    assert spiffe_controller.cert_validator == mock_certificate_validator
    assert spiffe_controller.optimizations is None


def test_controller_initialize_success(
    spiffe_controller, mock_spire_agent_manager, mock_workload_api_client
):
    """Test successful initialization of SPIFFE infrastructure."""
    result = spiffe_controller.initialize(
        attestation_strategy=AttestationStrategy.JOIN_TOKEN, token="test-token"
    )
    mock_spire_agent_manager.start.assert_called_once()
    mock_spire_agent_manager.attest_node.assert_called_once_with(
        AttestationStrategy.JOIN_TOKEN, token="test-token"
    )
    mock_workload_api_client.fetch_x509_svid.assert_called_once()
    assert spiffe_controller.current_identity is not None
    assert result is True


def test_controller_initialize_agent_start_fail(
    spiffe_controller, mock_spire_agent_manager
):
    """Test initialization failure if agent fails to start."""
    spiffe_controller.agent.start.return_value = False
    result = spiffe_controller.initialize()
    assert result is False


def test_controller_initialize_attestation_fail(
    spiffe_controller, mock_spire_agent_manager
):
    """Test initialization failure if node attestation fails."""
    spiffe_controller.agent.attest_node.return_value = False
    result = spiffe_controller.initialize()
    assert result is False


def test_controller_get_identity_not_provisioned(spiffe_controller):
    """Test get_identity before identity is provisioned."""
    spiffe_controller.current_identity = None
    with pytest.raises(RuntimeError, match="Identity not provisioned"):
        spiffe_controller.get_identity()


def test_controller_get_identity_no_renewal_needed(
    spiffe_controller, mock_workload_api_client
):
    """Test get_identity when no renewal is needed."""
    spiffe_controller.initialize(
        attestation_strategy=AttestationStrategy.JOIN_TOKEN, token="test-token"
    )

    mock_workload_api_client.fetch_x509_svid.reset_mock()

    spiffe_controller._should_renew = MagicMock(return_value=False)
    identity = spiffe_controller.get_identity()
    assert identity.spiffe_id == "spiffe://test.mesh/workload/test"
    spiffe_controller._should_renew.assert_called_once()
    mock_workload_api_client.fetch_x509_svid.assert_not_called()


def test_controller_should_renew(spiffe_controller):
    """Test _should_renew logic."""
    spiffe_controller.initialize(
        attestation_strategy=AttestationStrategy.JOIN_TOKEN, token="test-token"
    )

    # Not due for renewal
    spiffe_controller.current_identity.expiry = datetime.utcnow() + timedelta(
        minutes=45
    )
    assert not spiffe_controller._should_renew()

    # Due for renewal
    spiffe_controller.current_identity.expiry = datetime.utcnow() + timedelta(
        minutes=20
    )
    assert spiffe_controller._should_renew()

    # Expired
    spiffe_controller.current_identity.expiry = datetime.utcnow() - timedelta(minutes=1)
    assert spiffe_controller._should_renew()
