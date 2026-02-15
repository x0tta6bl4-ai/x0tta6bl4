import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.security.spiffe.workload.api_client import (JWTSVID,
                                                     SPIFFE_SDK_AVAILABLE,
                                                     X509SVID,
                                                     WorkloadAPIClient)

# Mock SVID attributes returned by the mocked SDK
MOCK_SPIFFE_ID = "spiffe://x0tta6bl4.mesh/node/mock"
MOCK_CERT_CHAIN = [b"MOCK_CERT"]
MOCK_PRIVATE_KEY = b"MOCK_KEY"
MOCK_EXPIRY = datetime.utcnow() + timedelta(hours=1)
MOCK_JWT_TOKEN = "MOCK_JWT_TOKEN"


@pytest.mark.skipif(
    SPIFFE_SDK_AVAILABLE, reason="spiffe SDK is installed, skipping mock client tests"
)
@pytest.fixture
def mock_spiffe_sdk():
    """Mocks the py-spiffe WorkloadApiClient and its availability flag."""
    # This mock will be used for the `with SpiffeWorkloadApiClient() as client:` block
    mock_sdk_instance = MagicMock()

    # Mock the return value of fetch_x509_svid
    mock_x509_svid_obj = MagicMock()
    mock_x509_svid_obj.spiffe_id = MOCK_SPIFFE_ID
    mock_x509_svid_obj.cert_chain = MOCK_CERT_CHAIN
    mock_x509_svid_obj.private_key = MOCK_PRIVATE_KEY
    mock_x509_svid_obj.expiry = MOCK_EXPIRY
    mock_sdk_instance.fetch_x509_svid.return_value = mock_x509_svid_obj

    # Mock the return value of fetch_jwt_svid
    mock_jwt_svid_obj = MagicMock()
    mock_jwt_svid_obj.spiffe_id = MOCK_SPIFFE_ID
    mock_jwt_svid_obj.token = MOCK_JWT_TOKEN
    mock_jwt_svid_obj.expiry = MOCK_EXPIRY
    mock_jwt_svid_obj.audience = ["aud1"]
    mock_sdk_instance.fetch_jwt_svid.return_value = mock_jwt_svid_obj

    with (
        patch("src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", True),
        patch(
            "src.security.spiffe.workload.api_client.SpiffeWorkloadApiClient"
        ) as MockSpiffeClient,
    ):

        # Make the class itself return the mocked instance when used in a 'with' statement
        MockSpiffeClient.return_value.__enter__.return_value = mock_sdk_instance
        yield mock_sdk_instance


@pytest.fixture
def spiffe_socket_env(monkeypatch):
    """Sets the SPIFFE_ENDPOINT_SOCKET environment variable."""
    socket_path = "/tmp/dummy_spire_agent.sock"
    monkeypatch.setenv("SPIFFE_ENDPOINT_SOCKET", socket_path)
    return socket_path


def test_init_fails_if_sdk_not_available_in_production(monkeypatch):
    """Verify WorkloadAPIClient raises ImportError if the SDK is missing in production mode."""
    # Enable production mode and disable force mock
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")
    monkeypatch.delenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", raising=False)
    with patch("src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", False):
        with pytest.raises(ImportError, match="REQUIRED in production"):
            WorkloadAPIClient()


def test_init_fails_if_socket_not_configured_in_production(monkeypatch):
    """Verify WorkloadAPIClient raises ValueError if the socket is not set in production mode."""
    # Enable production mode and disable force mock
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")
    monkeypatch.delenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", raising=False)
    monkeypatch.delenv("SPIFFE_ENDPOINT_SOCKET", raising=False)
    with patch("src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", True):
        with pytest.raises(ValueError, match="REQUIRED in production"):
            WorkloadAPIClient()


def test_init_uses_mock_mode_when_sdk_not_available(monkeypatch):
    """Verify WorkloadAPIClient uses mock mode when SDK is not available in dev mode."""
    # Disable production mode
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")
    monkeypatch.delenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", raising=False)
    monkeypatch.delenv("SPIFFE_ENDPOINT_SOCKET", raising=False)
    with patch("src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", False):
        # Should not raise, should use mock mode
        client = WorkloadAPIClient()
        assert client._force_mock_spiffe is True


def test_fetch_x509_svid_success(mock_spiffe_sdk, spiffe_socket_env, monkeypatch):
    """Test successful fetching of an X.509 SVID using the mocked SDK."""
    # Use force mock mode for testing
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
    client = WorkloadAPIClient()
    svid = client.fetch_x509_svid()

    # Assert that the returned SVID is valid
    assert isinstance(svid, X509SVID)
    assert svid.spiffe_id.startswith("spiffe://")
    assert len(svid.cert_chain) > 0
    assert len(svid.private_key) > 0
    assert not svid.is_expired()


def test_fetch_jwt_svid_success(mock_spiffe_sdk, spiffe_socket_env, monkeypatch):
    """Test successful fetching of a JWT SVID using the mocked SDK."""
    # Use force mock mode for testing
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
    client = WorkloadAPIClient()
    audience = ["aud1"]
    jwt_svid = client.fetch_jwt_svid(audience)

    # Assert that the returned SVID is valid
    assert isinstance(jwt_svid, JWTSVID)
    assert jwt_svid.spiffe_id.startswith("spiffe://")
    assert len(jwt_svid.token) > 0
    assert jwt_svid.audience == audience
    assert not jwt_svid.is_expired()


def test_validate_peer_svid_logic(spiffe_socket_env, monkeypatch):
    """
    Test the peer validation logic. This logic is independent of the fetch mechanism,
    but we still need to instantiate the client correctly.
    """
    # Use force mock mode for testing
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
    client = WorkloadAPIClient()

    # --- Test cases from the original test file ---

    # 1. Valid peer SVID
    peer = X509SVID(
        spiffe_id="spiffe://x0tta6bl4.mesh/peer",
        cert_chain=[
            b"MOCK_CERT"
        ],  # Content doesn't matter much for this part of the test
        private_key=b"K",
        expiry=datetime.utcnow() + timedelta(hours=1),
    )
    assert client.validate_peer_svid(peer) is True

    # 2. Valid peer SVID with correct expected ID
    assert (
        client.validate_peer_svid(peer, expected_id="spiffe://x0tta6bl4.mesh") is True
    )

    # 3. Invalid peer SVID with wrong expected ID
    assert client.validate_peer_svid(peer, expected_id="spiffe://other.domain") is False

    # 4. Expired peer SVID
    expired_peer = X509SVID(
        spiffe_id="spiffe://x0tta6bl4.mesh/peer",
        cert_chain=[b"C"],
        private_key=b"K",
        expiry=datetime.utcnow() - timedelta(minutes=1),
    )
    assert client.validate_peer_svid(expired_peer) is False
