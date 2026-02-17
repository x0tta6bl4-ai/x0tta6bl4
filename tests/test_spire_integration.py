"""
Integration Tests for SPIRE/SPIFFE

These tests require a running SPIRE deployment.
Run with: pytest tests/test_spire_integration.py -m integration

Prerequisites:
1. SPIRE Server and Agent running
2. SPIFFE_ENDPOINT_SOCKET environment variable set
3. Workload entry created for this test

Docker setup:
    cd deployment/spire
    docker compose up -d
    ./quickstart.sh docker
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Skip all tests if SPIRE not available
pytestmark = pytest.mark.skipif(
    os.getenv("SPIRE_INTEGRATION_TESTS") != "true",
    reason="SPIRE integration tests disabled. Set SPIRE_INTEGRATION_TESTS=true to enable."
)


class TestSPIREWorkloadAPI:
    """Tests for SPIRE Workload API integration."""
    
    @pytest.fixture
    def workload_api_client(self):
        """Create WorkloadAPI client for testing."""
        from src.security.spiffe.workload.api_client import WorkloadAPIClient
        return WorkloadAPIClient()
    
    def test_fetch_x509_svid(self, workload_api_client):
        """Test fetching X.509 SVID from SPIRE Agent."""
        svid = workload_api_client.fetch_x509_svid()
        
        # Verify SVID structure
        assert svid is not None
        assert svid.spiffe_id.startswith("spiffe://")
        assert len(svid.cert_chain) > 0
        assert svid.expiry > datetime.now()
    
    def test_fetch_jwt_svid(self, workload_api_client):
        """Test fetching JWT SVID from SPIRE Agent."""
        audience = ["test-service"]
        jwt_svid = workload_api_client.fetch_jwt_svid(audience)
        
        # Verify JWT SVID structure
        assert jwt_svid is not None
        assert jwt_svid.spiffe_id.startswith("spiffe://")
        assert len(jwt_svid.token) > 0
    
    def test_svid_not_expired(self, workload_api_client):
        """Test that fetched SVID is not expired."""
        svid = workload_api_client.fetch_x509_svid()
        
        # SVID should have at least 1 hour remaining
        min_ttl = timedelta(hours=1)
        assert svid.expiry > datetime.now() + min_ttl
    
    def test_validate_peer_svid(self, workload_api_client):
        """Test peer SVID validation."""
        # Fetch our own SVID for testing
        svid = workload_api_client.fetch_x509_svid()
        
        # Validate against itself
        is_valid = workload_api_client.validate_peer_svid(
            svid, 
            expected_id=svid.spiffe_id
        )
        
        assert is_valid is True


class TestSPIFFEAutoRenew:
    """Tests for automatic SVID renewal."""
    
    @pytest.fixture
    def auto_renew_service(self, workload_api_client):
        """Create auto-renew service for testing."""
        from src.security.spiffe.workload.auto_renew import SPIFFEAutoRenew, AutoRenewConfig
        
        config = AutoRenewConfig(
            renewal_threshold=0.5,  # Renew at 50% TTL
            check_interval=60.0,    # Check every minute
        )
        return SPIFFEAutoRenew(workload_api_client, config)
    
    def test_auto_renew_initialization(self, auto_renew_service):
        """Test auto-renew service initialization."""
        assert auto_renew_service is not None
        assert auto_renew_service.config.renewal_threshold == 0.5
    
    @pytest.mark.asyncio
    async def test_auto_renew_start_stop(self, auto_renew_service):
        """Test starting and stopping auto-renew service."""
        await auto_renew_service.start()
        assert auto_renew_service._running is True
        
        await auto_renew_service.stop()
        assert auto_renew_service._running is False


class TestSPIREHealthChecker:
    """Tests for SPIRE health checking."""
    
    @pytest.fixture
    def health_checker(self):
        """Create health checker for testing."""
        from src.security.spiffe.production_integration import SPIREHealthChecker, SPIREConfig
        
        config = SPIREConfig()
        return SPIREHealthChecker(config)
    
    @pytest.mark.asyncio
    async def test_check_server_health(self, health_checker):
        """Test SPIRE Server health check."""
        is_healthy = await health_checker.check_server_health()
        
        # Server should be healthy in integration test environment
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_check_agent_health(self, health_checker):
        """Test SPIRE Agent health check."""
        is_healthy = await health_checker.check_agent_health()
        
        # Agent should be healthy in integration test environment
        assert is_healthy is True


class TestmTLSWithSPIRE:
    """Tests for mTLS using SPIRE-issued certificates."""
    
    @pytest.fixture
    def mtls_context(self, workload_api_client):
        """Create mTLS context from SPIRE credentials."""
        from src.security.spiffe.mtls.tls_context import build_mtls_context
        
        svid = workload_api_client.fetch_x509_svid()
        return build_mtls_context(svid)
    
    def test_mtls_context_creation(self, mtls_context):
        """Test mTLS context creation from SVID."""
        assert mtls_context is not None
        assert mtls_context.ssl_context is not None
        assert mtls_context.spiffe_id.startswith("spiffe://")
    
    def test_mtls_context_ssl_setup(self, mtls_context):
        """Test SSL context is properly configured."""
        import ssl
        
        ssl_ctx = mtls_context.ssl_context
        
        # Verify TLS 1.2+ is enforced
        assert ssl_ctx.minimum_version >= ssl.TLSVersion.TLSv1_2
        
        # Verify client certificate is loaded
        assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED


class TestZeroTrustWithSPIFFE:
    """Tests for Zero Trust validation with SPIFFE."""
    
    @pytest.fixture
    def validator(self):
        """Create Zero Trust validator."""
        from src.security.zero_trust.validator import ZeroTrustValidator
        
        return ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")
    
    def test_validate_same_trust_domain(self, validator, workload_api_client):
        """Test validation of peer in same trust domain."""
        svid = workload_api_client.fetch_x509_svid()
        
        is_valid = validator.validate_connection(
            peer_spiffe_id=svid.spiffe_id,
            peer_svid=svid
        )
        
        assert is_valid is True
    
    def test_reject_different_trust_domain(self, validator):
        """Test rejection of peer from different trust domain."""
        # SPIFFE ID from different trust domain
        fake_spiffe_id = "spiffe://evil.com/workload/attacker"
        
        is_valid = validator.validate_connection(
            peer_spiffe_id=fake_spiffe_id
        )
        
        assert is_valid is False
    
    def test_get_current_identity(self, validator):
        """Test getting current workload identity."""
        identity = validator.get_current_identity()
        
        assert identity is not None
        assert "spiffe_id" in identity
        assert identity["spiffe_id"].startswith("spiffe://")


class TestMAPEKSPIFFEIntegration:
    """Tests for MAPE-K loop with SPIFFE integration."""
    
    @pytest.fixture
    def mapek_loop(self):
        """Create MAPE-K loop with SPIFFE integration."""
        from src.self_healing.mape_k_spiffe_integration import SPIFFEMapEKLoop
        
        return SPIFFEMapEKLoop(trust_domain="x0tta6bl4.mesh")
    
    @pytest.mark.asyncio
    async def test_initialize(self, mapek_loop):
        """Test MAPE-K loop initialization with SPIFFE."""
        await mapek_loop.initialize()
        
        assert mapek_loop.spiffe_controller is not None
    
    @pytest.mark.asyncio
    async def test_monitor_phase(self, mapek_loop):
        """Test monitor phase of MAPE-K loop."""
        await mapek_loop.initialize()
        
        monitor_result = await mapek_loop._monitor()
        
        assert monitor_result is not None
        assert "workloads" in monitor_result
    
    @pytest.mark.asyncio
    async def test_analyze_phase(self, mapek_loop):
        """Test analyze phase of MAPE-K loop."""
        await mapek_loop.initialize()
        
        monitor_result = await mapek_loop._monitor()
        analyze_result = await mapek_loop._analyze(monitor_result)
        
        assert analyze_result is not None


# Fixtures for all tests
@pytest.fixture(scope="module")
def workload_api_client():
    """Module-scoped WorkloadAPI client."""
    from src.security.spiffe.workload.api_client import WorkloadAPIClient
    return WorkloadAPIClient()


# Test configuration
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async test"
    )
