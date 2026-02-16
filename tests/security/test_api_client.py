import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.security.spiffe.workload.api_client import (JWTSVID, X509SVID,
                                                     WorkloadAPIClient)


@pytest.fixture(autouse=True)
def setup_env_vars():
    """Set up and tear down environment variables for each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_path(mocker):
    """Mocks pathlib.Path for testing trust bundle loading."""
    mock_file = MagicMock(spec=Path)
    mock_file.read_bytes.return_value = b"""-----BEGIN CERTIFICATE-----
TEST_CA_CERT
-----END CERTIFICATE-----"""
    mocker.patch("pathlib.Path", return_value=mock_file)
    return mock_file


@pytest.fixture
def mock_x509_certificate(mocker):
    """Mocks x509.Certificate for certificate validation tests."""
    mock_cert = MagicMock(spec=X509SVID)
    mock_cert.not_valid_before = datetime.utcnow() - timedelta(days=1)
    mock_cert.not_valid_after = datetime.utcnow() + timedelta(days=1)
    mock_cert.is_expired.return_value = False
    mock_cert.spiffe_id = "spiffe://test.mesh/workload/valid"

    # Mock extension methods if needed, for SAN checks
    mock_san_ext = MagicMock()
    mock_san_ext.get_values_for_type.return_value = [
        "spiffe://test.mesh/workload/valid"
    ]
    mock_cert.extensions.get_extension_for_oid.return_value = mock_san_ext

    mocker.patch("cryptography.x509.load_pem_x509_certificate", return_value=mock_cert)
    mocker.patch("cryptography.x509.load_der_x509_certificate", return_value=mock_cert)
    return mock_cert


# --- WorkloadAPIClient.__init__ Tests ---


def test_init_mock_mode_default_warning(caplog):
    """Test default initialization in mock mode (SDK unavailable, no explicit force mock)."""
    with (
        patch(
            "src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", new=False
        ),
        patch(
            "src.security.spiffe.workload.api_client.SpiffeWorkloadApiClient", new=None
        ),
    ):
        with caplog.at_level(logging.WARNING):
            client = WorkloadAPIClient()
            assert client._force_mock_spiffe is True
            assert "Workload API client initialized in MOCK mode" in caplog.text
            assert "SPIFFE SDK not available" in caplog.text
            # assert "SPIFFE endpoint socket not configured" in caplog.text # This warning is conditionally skipped by app logic


def test_init_force_mock_mode(caplog):
    """Test initialization with X0TTA6BL4_FORCE_MOCK_SPIFFE=true."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    with (
        patch(
            "src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", new=False
        ),
        patch(
            "src.security.spiffe.workload.api_client.SpiffeWorkloadApiClient", new=None
        ),
    ):
        with caplog.at_level(logging.WARNING):
            client = WorkloadAPIClient()
            assert client._force_mock_spiffe is True
            assert "Workload API client initialized in MOCK mode" in caplog.text
            assert (
                "SPIFFE SDK not available" not in caplog.text
            )  # Warning should be suppressed
            assert (
                "SPIFFE endpoint socket not configured" not in caplog.text
            )  # Warning should be suppressed


def test_init_production_force_mock_error():
    """Test initialization in production mode with X0TTA6BL4_FORCE_MOCK_SPIFFE=true."""
    os.environ["X0TTA6BL4_PRODUCTION"] = "true"
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    with pytest.raises(
        RuntimeError,
        match="CRITICAL SECURITY ERROR: Mock SPIFFE mode is FORBIDDEN in production!",
    ):
        WorkloadAPIClient()


def test_init_production_no_sdk_error():
    """Test initialization in production mode without SPIFFE SDK."""
    os.environ["X0TTA6BL4_PRODUCTION"] = "true"
    with (
        patch(
            "src.security.spiffe.workload.api_client.SPIFFE_SDK_AVAILABLE", new=False
        ),
        patch(
            "src.security.spiffe.workload.api_client.SpiffeWorkloadApiClient", new=None
        ),
    ):
        with pytest.raises(
            ImportError, match="The 'spiffe' SDK is REQUIRED in production."
        ):
            WorkloadAPIClient()


def test_init_production_no_endpoint_error():
    """Test initialization in production mode without SPIFFE_ENDPOINT_SOCKET."""
    os.environ["X0TTA6BL4_PRODUCTION"] = "true"
    os.environ["SPIFFE_ENDPOINT_SOCKET"] = ""  # Ensure it's empty
    with pytest.raises(
        ValueError, match="SPIFFE endpoint socket is REQUIRED in production"
    ):
        WorkloadAPIClient()


def test_init_trust_bundle_path():
    """Test initialization with explicit trust_bundle_path."""
    mock_path_obj = MagicMock(spec=Path)
    mock_path_obj.read_bytes.return_value = b"mock cert data"
    with patch("pathlib.Path", return_value=mock_path_obj):
        client = WorkloadAPIClient(trust_bundle_path=Path("/tmp/bundle.pem"))
        assert client.trust_bundle_path == Path("/tmp/bundle.pem")


def test_init_trust_bundle_env_var():
    """Test initialization with SPIFFE_TRUST_BUNDLE_PATH env var."""
    os.environ["SPIFFE_TRUST_BUNDLE_PATH"] = "/env/bundle.pem"
    client = WorkloadAPIClient()
    assert client.trust_bundle_path == Path("/env/bundle.pem")


# --- _mock_fetch_x509_svid Tests ---


def test_mock_fetch_x509_svid():
    """Test the internal mock method for X.509 SVID."""
    client = WorkloadAPIClient()  # This will initialize in mock mode
    svid = client._mock_fetch_x509_svid()
    assert svid.spiffe_id == "spiffe://mock.domain/workload/mock-app"
    assert svid.private_key == b"MOCK_PRIVATE_KEY"
    assert not svid.is_expired()


# --- fetch_x509_svid Tests (Mock Mode) ---


def test_fetch_x509_svid_mock_mode():
    """Test fetch_x509_svid in mock mode."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    client = WorkloadAPIClient()
    svid = client.fetch_x509_svid()
    assert svid.spiffe_id == "spiffe://mock.domain/workload/mock-app"
    assert not svid.is_expired()
    assert client.current_svid == svid  # Should cache the SVID


def test_fetch_x509_svid_mock_mode_cache():
    """Test fetch_x509_svid in mock mode uses cache."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    client = WorkloadAPIClient()
    first_svid = client.fetch_x509_svid()
    second_svid = client.fetch_x509_svid()  # Should return cached SVID
    assert (
        first_svid.spiffe_id == second_svid.spiffe_id
        and first_svid.private_key == second_svid.private_key
    )


# --- _mock_fetch_jwt_svid Tests ---


def test_mock_fetch_jwt_svid():
    """Test the internal mock method for JWT SVID."""
    client = WorkloadAPIClient()
    audience = ["aud1", "aud2"]
    jwt_svid = client._mock_fetch_jwt_svid(audience)
    assert jwt_svid.spiffe_id == "spiffe://mock.domain/workload/mock-app"
    assert jwt_svid.token == "MOCK_JWT_TOKEN"
    assert jwt_svid.audience == audience
    assert not jwt_svid.is_expired()


# --- fetch_jwt_svid Tests (Mock Mode) ---


def test_fetch_jwt_svid_mock_mode():
    """Test fetch_jwt_svid in mock mode."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    client = WorkloadAPIClient()
    audience = ["aud1"]
    jwt_svid = client.fetch_jwt_svid(audience)
    assert jwt_svid.spiffe_id == "spiffe://mock.domain/workload/mock-app"
    assert jwt_svid.token == "MOCK_JWT_TOKEN"
    assert jwt_svid.audience == audience
    assert not jwt_svid.is_expired()
    assert client._jwt_cache[("aud1",)] == jwt_svid  # Should cache the JWT SVID


def test_fetch_jwt_svid_mock_mode_cache():
    """Test fetch_jwt_svid in mock mode uses cache."""
    os.environ["X0TTA6BL4_FORCE_MOCK_SPIFFE"] = "true"
    client = WorkloadAPIClient()
    audience = ["aud1", "aud2"]
    first_jwt = client.fetch_jwt_svid(audience)
    second_jwt = client.fetch_jwt_svid(audience)
    assert (
        first_jwt.spiffe_id == second_jwt.spiffe_id
        and first_jwt.token == second_jwt.token
    )
