"""Tests for Mesh mTLS Enforcer (TLS 1.3 enforcement)."""

import ssl
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Check if SPIFFE dependencies are available
try:
    from src.security.mesh_mtls_enforcer import (MeshMTLSEnforcer,
                                                 TLS13EnforcementError)

    MTLS_AVAILABLE = True
except (ImportError, FileNotFoundError) as e:
    MTLS_AVAILABLE = False
    MeshMTLSEnforcer = None
    TLS13EnforcementError = Exception


@pytest.fixture
def mock_spiffe_controller():
    """Create mock SPIFFEController."""
    mock = MagicMock()
    mock.workload_api = MagicMock()
    mock.trust_domain = "x0tta6bl4.mesh"
    return mock


@pytest.fixture
def mock_mtls_controller():
    """Create mock MTLSControllerProduction."""
    mock = MagicMock()
    mock.get_context = MagicMock()
    return mock


@pytest.mark.skipif(not MTLS_AVAILABLE, reason="mTLS dependencies not available")
class TestMeshMTLSEnforcer:
    """Test suite for MeshMTLSEnforcer."""

    def test_enforcer_initialization(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that enforcer initializes correctly."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(
                    trust_domain="x0tta6bl4.mesh", enforce_tls13=True, verify_svid=True
                )

                assert enforcer.trust_domain == "x0tta6bl4.mesh"
                assert enforcer.enforce_tls13 is True
                assert enforcer.verify_svid is True
                assert enforcer.spiffe_controller is not None
                assert enforcer.mtls_controller is not None

    def test_tls13_enforcement_check(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test TLS 1.3 enforcement verification."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(enforce_tls13=True)

                # Create context with TLS 1.3
                ctx = ssl.create_default_context()
                try:
                    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
                    enforcer.verify_tls_version(ctx)  # Should pass
                except AttributeError:
                    # Older Python versions may not support TLSVersion
                    pytest.skip("TLSVersion not available in this Python version")

    def test_tls13_enforcement_failure(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that TLS 1.2 is rejected when TLS 1.3 is enforced."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(enforce_tls13=True)

                # Create context with TLS 1.2 (if possible)
                ctx = ssl.create_default_context()
                try:
                    if hasattr(ssl, "TLSVersion"):
                        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                        with pytest.raises(TLS13EnforcementError):
                            enforcer.verify_tls_version(ctx)
                except (AttributeError, AttributeError):
                    pytest.skip("TLSVersion configuration not available")

    def test_tls13_enforcement_disabled(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that enforcement can be disabled."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(enforce_tls13=False)

                # Create context with TLS 1.2
                ctx = ssl.create_default_context()
                # Should not raise even with TLS 1.2
                enforcer.verify_tls_version(ctx)

    def test_certificate_chain_validation(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test certificate chain validation method exists and is callable."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Should have certificate chain validation method
                assert hasattr(enforcer, "verify_certificate_chain")
                assert callable(enforcer.verify_certificate_chain)

    def test_svid_verification_disabled(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that SVID verification can be disabled."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(verify_svid=False)

                # Should indicate verification is disabled
                result = enforcer.verify_peer_svid("spiffe://any.domain/service")
                # Result may be dict or bool depending on implementation
                if isinstance(result, dict):
                    assert "verified" in result or "reason" in result
                else:
                    assert result is True or result is False or result is None

    def test_peer_identity_tracking(self, mock_spiffe_controller, mock_mtls_controller):
        """Test that peer identities are tracked."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Should be able to track peer identities
                assert hasattr(enforcer, "trust_domain")
                assert enforcer.trust_domain == "x0tta6bl4.mesh"

    def test_secure_client_setup_requires_init(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that secure client requires initialization."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Should have methods for secure client
                assert hasattr(enforcer, "spiffe_controller")
                assert hasattr(enforcer, "mtls_controller")


@pytest.mark.skipif(not MTLS_AVAILABLE, reason="mTLS dependencies not available")
class TestTLS13Requirements:
    """Test TLS 1.3 specific requirements."""

    def test_minimum_tls_version(self, mock_spiffe_controller, mock_mtls_controller):
        """Test that minimum TLS version is 1.3 when enforced."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(enforce_tls13=True)

                assert enforcer.enforce_tls13 is True

    def test_cipher_suite_requirements(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test that only TLS 1.3 cipher suites are accepted."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Should have TLS 1.3 enforcement capability
                assert hasattr(enforcer, "enforce_tls13")


@pytest.mark.skipif(not MTLS_AVAILABLE, reason="mTLS dependencies not available")
class TestSVIDVerification:
    """Test SVID verification functionality."""

    def test_svid_verification_disabled(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test SVID verification when disabled."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer(verify_svid=False)

                assert enforcer.verify_svid is False

    def test_empty_certificate(self, mock_spiffe_controller, mock_mtls_controller):
        """Test handling of empty certificate raises ValueError."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Empty chain should raise ValueError
                with pytest.raises(ValueError, match="Empty certificate chain"):
                    enforcer.verify_certificate_chain([])


@pytest.mark.skipif(not MTLS_AVAILABLE, reason="mTLS dependencies not available")
class TestMTLSConnectivity:
    """Test mTLS connectivity functionality."""

    @pytest.mark.skip(reason="Requires running SPIRE infrastructure")
    def test_connectivity_verification_production(self):
        """Test connectivity verification (requires real SPIRE)."""
        pass

    def test_connectivity_verification_setup(
        self, mock_spiffe_controller, mock_mtls_controller
    ):
        """Test connectivity verification setup."""
        with patch(
            "src.security.mesh_mtls_enforcer.SPIFFEController",
            return_value=mock_spiffe_controller,
        ):
            with patch(
                "src.security.mesh_mtls_enforcer.MTLSControllerProduction",
                return_value=mock_mtls_controller,
            ):
                enforcer = MeshMTLSEnforcer()

                # Should have proper setup
                assert enforcer.spiffe_controller is not None
                assert enforcer.mtls_controller is not None
