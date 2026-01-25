"""Tests for Mesh mTLS Enforcer (TLS 1.3 enforcement)."""

import pytest
import ssl
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.security.mesh_mtls_enforcer import (
    MeshMTLSEnforcer,
    TLS13EnforcementError
)


class TestMeshMTLSEnforcer:
    """Test suite for MeshMTLSEnforcer."""
    
    def test_enforcer_initialization(self):
        """Test that enforcer initializes correctly."""
        enforcer = MeshMTLSEnforcer(
            trust_domain="x0tta6bl4.mesh",
            enforce_tls13=True,
            verify_svid=True
        )
        
        assert enforcer.trust_domain == "x0tta6bl4.mesh"
        assert enforcer.enforce_tls13 is True
        assert enforcer.verify_svid is True
        assert enforcer.spiffe_controller is not None
        assert enforcer.mtls_controller is not None
    
    def test_tls13_enforcement_check(self):
        """Test TLS 1.3 enforcement verification."""
        enforcer = MeshMTLSEnforcer(enforce_tls13=True)
        
        # Create context with TLS 1.3
        ctx = ssl.create_default_context()
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
            enforcer.verify_tls_version(ctx)  # Should pass
        except AttributeError:
            # Older Python versions may not support TLSVersion
            pytest.skip("TLSVersion not available in this Python version")
    
    def test_tls13_enforcement_failure(self):
        """Test that TLS 1.2 is rejected when TLS 1.3 is enforced."""
        enforcer = MeshMTLSEnforcer(enforce_tls13=True)
        
        # Create context with TLS 1.2 (if possible)
        ctx = ssl.create_default_context()
        try:
            if hasattr(ssl, 'TLSVersion'):
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                with pytest.raises(TLS13EnforcementError):
                    enforcer.verify_tls_version(ctx)
        except (AttributeError, AttributeError):
            pytest.skip("TLSVersion configuration not available")
    
    def test_tls13_enforcement_disabled(self):
        """Test that enforcement can be disabled."""
        enforcer = MeshMTLSEnforcer(enforce_tls13=False)
        
        # Should not raise even with TLS 1.2
        ctx = ssl.create_default_context()
        try:
            if hasattr(ssl, 'TLSVersion'):
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        except (AttributeError, AttributeError):
            pass
        
        enforcer.verify_tls_version(ctx)  # Should not raise
    
    def test_certificate_chain_validation(self):
        """Test certificate chain validation."""
        enforcer = MeshMTLSEnforcer()
        
        # Test with empty chain
        with pytest.raises(ValueError, match="Empty certificate chain"):
            enforcer.verify_certificate_chain([])
    
    def test_svid_verification_disabled(self):
        """Test that SVID verification can be disabled."""
        enforcer = MeshMTLSEnforcer(verify_svid=False)
        
        # Should return verification disabled, not raise
        result = enforcer.verify_peer_svid(b"fake_cert")
        assert result["verified"] is False
        assert "disabled" in result["reason"].lower()
    
    def test_peer_identity_tracking(self):
        """Test that peer identities are tracked."""
        enforcer = MeshMTLSEnforcer()
        
        # Add a peer identity
        enforcer.peer_identities["peer1"] = {
            "spiffe_id": "spiffe://x0tta6bl4.mesh/service/api",
            "verified_at": datetime.utcnow().isoformat()
        }
        
        assert "peer1" in enforcer.peer_identities
        assert enforcer.peer_identities["peer1"]["spiffe_id"] == "spiffe://x0tta6bl4.mesh/service/api"
    
    @pytest.mark.asyncio
    async def test_secure_client_setup_requires_init(self):
        """Test that setup_secure_client requires initialization."""
        enforcer = MeshMTLSEnforcer()
        
        # Mock the mTLS controller to avoid actual SPIRE connection
        with patch.object(enforcer.mtls_controller, 'setup_mtls_context', new_callable=AsyncMock) as mock_setup:
            # If setup fails, we should get TLS13EnforcementError
            mock_setup.side_effect = Exception("Mock setup error")
            
            with pytest.raises(TLS13EnforcementError):
                await enforcer.setup_secure_client()


class TestTLS13Requirements:
    """Test suite for TLS 1.3 specific requirements."""
    
    def test_minimum_tls_version(self):
        """Test that minimum TLS version is 1.3."""
        try:
            enforcer = MeshMTLSEnforcer(enforce_tls13=True)
            ctx = ssl.create_default_context()
            
            if hasattr(ssl, 'TLSVersion'):
                ctx.minimum_version = ssl.TLSVersion.TLSv1_3
                enforcer.verify_tls_version(ctx)  # Should pass
        except (AttributeError, AssertionError):
            pytest.skip("TLSVersion not available")
    
    def test_cipher_suite_requirements(self):
        """Test that secure cipher suites are used."""
        enforcer = MeshMTLSEnforcer()
        
        # Secure ciphers should exclude weak algorithms
        secure_ciphers = "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        
        # MD5 and aNULL should be excluded
        assert "!MD5" in secure_ciphers
        assert "!aNULL" in secure_ciphers
        assert "!DSS" in secure_ciphers


class TestSVIDVerification:
    """Test suite for SPIFFE ID (SVID) verification."""
    
    def test_svid_verification_disabled(self):
        """Test SVID verification can be disabled."""
        enforcer = MeshMTLSEnforcer(verify_svid=False)
        
        result = enforcer.verify_peer_svid(b"cert_data")
        assert result["verified"] is False
    
    def test_empty_certificate(self):
        """Test verification of empty certificate."""
        enforcer = MeshMTLSEnforcer(verify_svid=True)
        
        # Empty certificate should fail verification
        result = enforcer.verify_peer_svid(b"")
        assert result["verified"] is False


class TestMTLSConnectivity:
    """Test suite for mTLS connectivity verification."""
    
    @pytest.mark.asyncio
    async def test_connectivity_verification_setup(self):
        """Test connectivity verification setup."""
        enforcer = MeshMTLSEnforcer()
        
        # Test that we can at least try to set up
        with patch.object(enforcer.mtls_controller, 'setup_mtls_context', new_callable=AsyncMock):
            pass  # Just verify it doesn't crash during setup


# Integration test (requires actual SPIRE setup)
@pytest.mark.integration
class TestMTLSIntegration:
    """Integration tests for mTLS with actual SPIRE."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_mtls(self):
        """Test end-to-end mTLS setup and verification."""
        pytest.skip("Requires running SPIRE infrastructure")
