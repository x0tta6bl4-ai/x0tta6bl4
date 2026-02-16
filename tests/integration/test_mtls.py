import ssl
from unittest.mock import MagicMock, patch

import pytest

from src.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.security.spiffe.mtls.tls_context import MTLSContext, TLSRole
from src.security.spiffe.workload.api_client import X509SVID


@patch("src.security.spiffe.controller.spiffe_controller.WorkloadAPIClient")
@patch("src.security.spiffe.controller.spiffe_controller.SPIREAgentManager")
def test_get_mtls_http_client_success(MockAgentManager, MockWorkloadAPIClient):
    """
    Test that the get_mtls_http_client context manager correctly
    orchestrates creating and cleaning up an mTLS-configured httpx.Client.
    """
    # Arrange
    controller = SPIFFEController()

    # Mock the identity returned by the controller
    mock_svid = MagicMock(spec=X509SVID)
    mock_svid.spiffe_id = "spiffe://x0tta6bl4.mesh/test"
    controller.get_identity = MagicMock(return_value=mock_svid)

    # Mock the MTLSContext and its underlying ssl.SSLContext
    mock_ssl_context = MagicMock(spec=ssl.SSLContext)
    mock_mtls_context = MagicMock(spec=MTLSContext)
    mock_mtls_context.ssl_context = mock_ssl_context

    # Mock the build_mtls_context function to return our mocked context
    mock_build_context = MagicMock(return_value=mock_mtls_context)

    # Mock the httpx.Client and configure it as a context manager
    mock_http_client = MagicMock()
    mock_http_client.__enter__.return_value = mock_http_client

    with (
        patch(
            "src.security.spiffe.controller.spiffe_controller.build_mtls_context",
            mock_build_context,
        ),
        patch("httpx.Client", return_value=mock_http_client) as MockHttpxClient,
    ):

        # Act
        with controller.get_mtls_http_client(timeout=30) as client:
            # Assertions during context execution
            controller.get_identity.assert_called_once()
            mock_build_context.assert_called_once_with(mock_svid, role=TLSRole.CLIENT)

            # Check that workload_api.trust_bundle_path was accessed for load_verify_locations
            # This is an indirect way to check the logic inside the method
            assert controller.workload_api.trust_bundle_path is not None

            MockHttpxClient.assert_called_once_with(verify=mock_ssl_context, timeout=30)
            assert client == mock_http_client

    # Assertions after exiting context
    # Check that the cleanup method on our MTLSContext mock was called
    mock_mtls_context.cleanup.assert_called_once()
