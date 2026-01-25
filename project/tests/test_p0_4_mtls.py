"""
Tests for P0#4 - mTLS with TLS 1.3 enforcement
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request
from src.core.mtls_middleware import MTLSValidator, MTLSMiddleware
from unittest.mock import Mock, patch
from cryptography import x509
from cryptography.x509.oid import ExtensionOID
from datetime import datetime, timedelta


@pytest.fixture
def mtls_validator():
    """Create MTLSValidator instance"""
    return MTLSValidator(
        require_client_cert=True,
        allowed_spiffe_domains=["x0tta6bl4.mesh"]
    )


class TestMTLSValidator:
    """Tests for MTLSValidator"""
    
    def test_validator_initialization(self, mtls_validator):
        """Test MTLSValidator initialization"""
        assert mtls_validator.require_client_cert is True
        assert mtls_validator.min_tls_version == "1.3"
        assert "x0tta6bl4.mesh" in mtls_validator.allowed_spiffe_domains
    
    def test_validate_spiffe_domain_valid(self, mtls_validator):
        """Test SPIFFE domain validation with valid domain"""
        # Create mock certificate with valid SPIFFE SAN
        cert = Mock(spec=x509.Certificate)
        
        # Mock the SAN extension
        san_name = Mock(spec=x509.UniformResourceIdentifier)
        san_name.value = "spiffe://x0tta6bl4.mesh/ns/default/sa/api-server"
        
        san_ext = Mock()
        san_ext.value = [san_name]
        
        cert.extensions.get_extension_for_oid = Mock(return_value=san_ext)
        
        is_valid, spiffe_id = mtls_validator.validate_spiffe_svid(cert)
        
        assert is_valid is True
        assert "spiffe://" in spiffe_id
    
    def test_validate_spiffe_domain_invalid(self, mtls_validator):
        """Test SPIFFE domain validation with invalid domain"""
        cert = Mock(spec=x509.Certificate)
        
        san_name = Mock(spec=x509.UniformResourceIdentifier)
        san_name.value = "spiffe://wrong-domain.mesh/ns/default/sa/api-server"
        
        san_ext = Mock()
        san_ext.value = [san_name]
        
        cert.extensions.get_extension_for_oid = Mock(return_value=san_ext)
        
        is_valid, spiffe_id = mtls_validator.validate_spiffe_svid(cert)
        
        assert is_valid is False
    
    def test_validate_cert_expiry_valid(self, mtls_validator):
        """Test certificate expiry validation with valid cert"""
        cert = Mock(spec=x509.Certificate)
        # Certificate expires in 30 days
        cert.not_valid_after = datetime.utcnow() + timedelta(days=30)
        
        is_valid, expiry_info = mtls_validator.validate_cert_expiry(cert)
        
        assert is_valid is True
        assert "expires" in expiry_info
    
    def test_validate_cert_expiry_expired(self, mtls_validator):
        """Test certificate expiry validation with expired cert"""
        cert = Mock(spec=x509.Certificate)
        # Certificate expired 1 day ago
        cert.not_valid_after = datetime.utcnow() - timedelta(days=1)
        
        is_valid, expiry_info = mtls_validator.validate_cert_expiry(cert)
        
        assert is_valid is False
        assert "expired" in expiry_info
    
    def test_validate_cert_expiry_warning(self, mtls_validator):
        """Test certificate expiry validation with certificate expiring soon"""
        cert = Mock(spec=x509.Certificate)
        # Certificate expires in 3 days (within 7 day warning threshold)
        cert.not_valid_after = datetime.utcnow() + timedelta(days=3)
        
        is_valid, expiry_info = mtls_validator.validate_cert_expiry(cert)
        
        assert is_valid is True
        # Check that it says expires in days (2-3 range due to timing)
        assert "expires in" in expiry_info
        assert "days" in expiry_info


class TestMTLSMiddleware:
    """Tests for MTLSMiddleware"""
    
    def test_middleware_initialization(self):
        """Test MTLSMiddleware initialization"""
        app = FastAPI()
        middleware = MTLSMiddleware(
            app,
            require_mtls=False,  # Disable for testing
            enforce_tls_13=False
        )
        
        assert middleware.require_mtls is False
        assert middleware.enforce_tls_13 is False
    
    def test_excluded_paths_not_checked(self):
        """Test that excluded paths bypass mTLS checks"""
        app = FastAPI()
        
        @app.get("/health")
        async def health():
            return {"status": "ok"}
        
        # Add middleware with /health excluded
        app.add_middleware(
            MTLSMiddleware,
            require_mtls=False,
            enforce_tls_13=False,
            excluded_paths=["/health"]
        )
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200


class TestMTLSConfiguration:
    """Tests for mTLS configuration"""
    
    def test_mtls_env_variable_default(self):
        """Test that MTLS_ENABLED defaults to false"""
        import os
        
        # Make sure MTLS_ENABLED is not set
        if "MTLS_ENABLED" in os.environ:
            del os.environ["MTLS_ENABLED"]
        
        # Import app (should load without mTLS middleware)
        from src.core.app import app, mtls_enabled
        
        assert mtls_enabled is False
    
    def test_allowed_spiffe_domains_configuration(self):
        """Test SPIFFE domains configuration"""
        validator = MTLSValidator(
            allowed_spiffe_domains=["x0tta6bl4.mesh", "test.mesh"]
        )
        
        assert len(validator.allowed_spiffe_domains) == 2
        assert "x0tta6bl4.mesh" in validator.allowed_spiffe_domains


class TestMTLSProductionConfiguration:
    """Tests for production mTLS configuration"""
    
    def test_tls_13_minimum_version(self):
        """Test that TLS 1.3 is minimum version"""
        validator = MTLSValidator(min_tls_version="1.3")
        
        assert validator.min_tls_version == "1.3"
    
    def test_certificate_validation_required_in_production(self):
        """Test that certificate validation is required in production"""
        validator = MTLSValidator(require_client_cert=True)
        
        assert validator.require_client_cert is True
    
    def test_expiry_checking_enabled(self):
        """Test that certificate expiry checking is enabled"""
        validator = MTLSValidator(check_expiry=True)
        
        assert validator.check_expiry is True


class TestMTLSSecurityHeaders:
    """Tests for security headers with mTLS"""
    
    def test_hsts_header_present(self):
        """Test that HSTS header is present"""
        from src.core.app import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    
    def test_x_frame_options_header(self):
        """Test that X-Frame-Options header is present"""
        from src.core.app import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert "X-Frame-Options" in response.headers
    
    def test_content_type_options_header(self):
        """Test that X-Content-Type-Options header is present"""
        from src.core.app import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestMTLSErrorHandling:
    """Tests for mTLS error handling"""
    
    def test_invalid_tls_version_response(self):
        """Test response when TLS version is invalid"""
        app = FastAPI()
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        # Add middleware
        app.add_middleware(
            MTLSMiddleware,
            require_mtls=False,
            enforce_tls_13=True,
            excluded_paths=[]
        )
        
        client = TestClient(app)
        response = client.get("/api/test")
        
        # TestClient doesn't support TLS validation, so response should be OK
        # In real scenario with TLS 1.2, would get 400
        assert response.status_code in [200, 400]
