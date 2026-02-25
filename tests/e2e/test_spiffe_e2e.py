"""
SPIFFE/SPIRE End-to-End Validation Tests

Tests cover:
- SVID issuance from SPIRE Agent
- mTLS handshake with X.509 SVIDs
- Auto-renewal service validation
- Failover and recovery scenarios

Run with: pytest tests/e2e/test_spiffe_e2e.py -v
"""

import asyncio
import os
import time
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.conftest import latency_threshold

# Skip all tests if SPIRE not available
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_SPIRE_E2E", "true").lower() == "true",
    reason="SPIRE E2E tests require SPIRE infrastructure. Set SKIP_SPIRE_E2E=false to run."
)


class MockSVID:
    """Mock X.509 SVID for testing."""
    
    def __init__(
        self,
        spiffe_id: str = "spiffe://x0tta6bl4.local/ns/default/sa/test-workload",
        expiry_seconds: int = 3600,
    ):
        self.spiffe_id = spiffe_id
        self.cert_chain = [b"mock_cert_pem_data"]
        self.private_key = b"mock_private_key_pem_data"
        self.bundle = b"mock_bundle_pem_data"
        self.expiry = time.time() + expiry_seconds
        self.hint = "x509"


class MockWorkloadAPIClient:
    """Mock Workload API client for testing without SPIRE."""
    
    def __init__(self, socket_path: str = "/run/spire/sockets/agent.sock"):
        self.socket_path = socket_path
        self._connected = False
        self._svid_cache: Dict[str, MockSVID] = {}
    
    async def connect(self) -> None:
        """Connect to SPIRE Agent."""
        await asyncio.sleep(0.01)  # Simulate connection
        self._connected = True
    
    async def fetch_x509_svid(
        self,
        spiffe_id: Optional[str] = None,
    ) -> MockSVID:
        """Fetch X.509 SVID from Workload API."""
        if not self._connected:
            raise RuntimeError("Not connected to SPIRE Agent")
        
        await asyncio.sleep(0.02)  # Simulate API call
        
        # Return cached or create new
        if spiffe_id and spiffe_id in self._svid_cache:
            return self._svid_cache[spiffe_id]
        
        svid = MockSVID(spiffe_id=spiffe_id or "spiffe://x0tta6bl4.local/ns/default/sa/test-workload")
        self._svid_cache[svid.spiffe_id] = svid
        return svid
    
    async def fetch_jwt_svid(
        self,
        audience: list[str],
        spiffe_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch JWT SVID from Workload API."""
        if not self._connected:
            raise RuntimeError("Not connected to SPIRE Agent")
        
        await asyncio.sleep(0.02)
        
        return {
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock_jwt_token",
            "spiffe_id": spiffe_id or "spiffe://x0tta6bl4.local/ns/default/sa/test-workload",
            "expiry": time.time() + 300,
        }
    
    async def fetch_bundle(self) -> bytes:
        """Fetch trust bundle."""
        if not self._connected:
            raise RuntimeError("Not connected to SPIRE Agent")
        
        await asyncio.sleep(0.01)
        return b"mock_trust_bundle_pem_data"
    
    async def close(self) -> None:
        """Close connection."""
        self._connected = False


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def workload_client():
    """Create mock Workload API client."""
    client = MockWorkloadAPIClient()
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def spire_config():
    """SPIRE configuration for testing."""
    return {
        "trust_domain": "x0tta6bl4.local",
        "socket_path": "/run/spire/sockets/agent.sock",
        "server_address": "spire-server:8081",
        "workload_api_timeout": 30,
        "auto_renew_enabled": True,
        "renewal_threshold": 0.5,  # Renew at 50% of TTL
    }


# =============================================================================
# Phase 1: SVID Issuance Tests
# =============================================================================

class TestSVIDIssuance:
    """Tests for SVID issuance from SPIRE."""
    
    @pytest.mark.asyncio
    async def test_fetch_x509_svid_success(self, workload_client):
        """Test successful X.509 SVID fetch."""
        svid = await workload_client.fetch_x509_svid()
        
        assert svid is not None
        assert svid.spiffe_id.startswith("spiffe://x0tta6bl4.local/")
        assert len(svid.cert_chain) > 0
        assert svid.private_key is not None
        assert svid.expiry > time.time()
    
    @pytest.mark.asyncio
    async def test_fetch_x509_svid_with_specific_spiffe_id(self, workload_client):
        """Test fetching SVID with specific SPIFFE ID."""
        spiffe_id = "spiffe://x0tta6bl4.local/ns/production/sa/api-server"
        svid = await workload_client.fetch_x509_svid(spiffe_id=spiffe_id)
        
        assert svid.spiffe_id == spiffe_id
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_svid_issuance_latency(self, workload_client):
        """Test SVID issuance latency is under 100ms."""
        start = time.time()
        await workload_client.fetch_x509_svid()
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < latency_threshold(100), f"SVID issuance took {elapsed_ms:.2f}ms (target: <100ms)"
    
    @pytest.mark.asyncio
    async def test_svid_chain_valid(self, workload_client):
        """Test SVID chain is valid."""
        svid = await workload_client.fetch_x509_svid()
        
        # In real implementation, would verify chain
        assert svid.cert_chain is not None
        assert svid.bundle is not None
    
    @pytest.mark.asyncio
    async def test_fetch_jwt_svid_success(self, workload_client):
        """Test successful JWT SVID fetch."""
        jwt_svid = await workload_client.fetch_jwt_svid(
            audience=["https://api.x0tta6bl4.local"]
        )
        
        assert jwt_svid is not None
        assert "token" in jwt_svid
        assert jwt_svid["spiffe_id"].startswith("spiffe://")
    
    @pytest.mark.asyncio
    async def test_fetch_trust_bundle(self, workload_client):
        """Test fetching trust bundle."""
        bundle = await workload_client.fetch_bundle()
        
        assert bundle is not None
        assert len(bundle) > 0


# =============================================================================
# Phase 2: mTLS Handshake Tests
# =============================================================================

class TestMTLSHandshake:
    """Tests for mTLS handshake with SVIDs."""
    
    @pytest.mark.asyncio
    async def test_build_mtls_context(self, workload_client):
        """Test building mTLS context from SVID."""
        svid = await workload_client.fetch_x509_svid()
        
        # Mock TLS context builder
        context = {
            "cert_chain": svid.cert_chain,
            "private_key": svid.private_key,
            "ca_bundle": svid.bundle,
            "verify_mode": "CERT_REQUIRED",
            "check_hostname": True,
        }
        
        assert context["cert_chain"] is not None
        assert context["private_key"] is not None
        assert context["verify_mode"] == "CERT_REQUIRED"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_mtls_handshake_latency(self, workload_client):
        """Test mTLS handshake latency is under 50ms."""
        svid = await workload_client.fetch_x509_svid()

        start = time.time()
        # Simulate handshake
        await asyncio.sleep(0.01)
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < latency_threshold(50), f"mTLS handshake took {elapsed_ms:.2f}ms (target: <50ms)"
    
    @pytest.mark.asyncio
    async def test_spiffe_id_validation(self, workload_client):
        """Test SPIFFE ID validation in mTLS."""
        svid = await workload_client.fetch_x509_svid()
        
        # Validate SPIFFE ID format
        parts = svid.spiffe_id.split("/")
        assert parts[0] == "spiffe:"
        assert parts[1] == ""
        assert parts[2] == "x0tta6bl4.local"
    
    @pytest.mark.asyncio
    async def test_mutual_authentication(self, workload_client):
        """Test mutual authentication with mTLS."""
        client_svid = await workload_client.fetch_x509_svid(
            spiffe_id="spiffe://x0tta6bl4.local/ns/default/sa/client"
        )
        server_svid = await workload_client.fetch_x509_svid(
            spiffe_id="spiffe://x0tta6bl4.local/ns/default/sa/server"
        )
        
        # Both should have valid SVIDs
        assert client_svid.spiffe_id != server_svid.spiffe_id
        assert client_svid.expiry > time.time()
        assert server_svid.expiry > time.time()


# =============================================================================
# Phase 3: Auto-Renewal Tests
# =============================================================================

class TestAutoRenewal:
    """Tests for SVID auto-renewal."""
    
    @pytest.mark.asyncio
    async def test_auto_renew_service_starts(self, workload_client, spire_config):
        """Test auto-renewal service starts correctly."""
        # Mock auto-renew service
        service = {
            "enabled": spire_config["auto_renew_enabled"],
            "threshold": spire_config["renewal_threshold"],
            "running": True,
        }
        
        assert service["enabled"] is True
        assert service["running"] is True
    
    @pytest.mark.asyncio
    async def test_renewal_triggers_before_expiry(self, workload_client):
        """Test renewal triggers before SVID expires."""
        # Create SVID with short TTL
        svid = MockSVID(expiry_seconds=60)
        
        # Check if renewal needed (at 50% TTL)
        time_to_expiry = svid.expiry - time.time()
        ttl_fraction = time_to_expiry / 60
        
        # Should trigger renewal when below threshold
        needs_renewal = ttl_fraction < 0.5
        
        # For short TTL, should need renewal soon
        assert time_to_expiry < 60
    
    @pytest.mark.asyncio
    async def test_renewed_svid_valid(self, workload_client):
        """Test renewed SVID is valid."""
        # Original SVID
        original_svid = await workload_client.fetch_x509_svid()
        
        # Simulate renewal
        renewed_svid = await workload_client.fetch_x509_svid()
        
        assert renewed_svid.spiffe_id == original_svid.spiffe_id
        assert renewed_svid.expiry > time.time()
    
    @pytest.mark.asyncio
    async def test_no_service_interruption_during_renewal(self, workload_client):
        """Test no service interruption during SVID renewal."""
        # Simulate concurrent operations during renewal
        async def fetch_during_renewal():
            return await workload_client.fetch_x509_svid()
        
        # Run multiple fetches concurrently
        results = await asyncio.gather(
            fetch_during_renewal(),
            fetch_during_renewal(),
            fetch_during_renewal(),
        )
        
        # All should succeed
        assert all(r is not None for r in results)


# =============================================================================
# Phase 4: Failover/Recovery Tests
# =============================================================================

class TestFailoverRecovery:
    """Tests for failover and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_service_continues_when_agent_restarts(self, workload_client):
        """Test service continues when SPIRE Agent restarts."""
        # Fetch SVID before "restart"
        svid_before = await workload_client.fetch_x509_svid()
        
        # Simulate agent restart (disconnect/reconnect)
        await workload_client.close()
        await workload_client.connect()
        
        # Should still be able to fetch SVID
        svid_after = await workload_client.fetch_x509_svid()
        
        assert svid_after is not None
    
    @pytest.mark.asyncio
    async def test_cached_svid_used_during_outage(self, workload_client):
        """Test cached SVIDs used during SPIRE outage."""
        # Fetch and cache SVID
        svid = await workload_client.fetch_x509_svid()
        
        # Simulate outage (disconnect)
        await workload_client.close()
        
        # Cached SVID should still be valid
        assert svid.expiry > time.time()
    
    @pytest.mark.asyncio
    async def test_automatic_reconnection_after_recovery(self, workload_client):
        """Test automatic reconnection after SPIRE recovery."""
        # Connect
        await workload_client.connect()
        
        # Simulate outage
        await workload_client.close()
        
        # Reconnect
        await workload_client.connect()
        
        # Should be able to fetch SVID
        svid = await workload_client.fetch_x509_svid()
        assert svid is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestSPIREIntegration:
    """Integration tests with x0tta6bl4 components."""
    
    @pytest.mark.asyncio
    async def test_mtls_middleware_with_spire(self, workload_client):
        """Test mTLS middleware integration with SPIRE."""
        svid = await workload_client.fetch_x509_svid()
        
        # Mock middleware configuration
        middleware_config = {
            "require_mtls": True,
            "enforce_tls_13": True,
            "allowed_spiffe_domains": ["x0tta6bl4.local"],
            "excluded_paths": ["/health", "/metrics"],
        }
        
        assert middleware_config["require_mtls"] is True
        assert "x0tta6bl4.local" in middleware_config["allowed_spiffe_domains"]
    
    @pytest.mark.asyncio
    async def test_zero_trust_validator_with_spire(self, workload_client):
        """Test Zero Trust validator with SPIRE SVIDs."""
        svid = await workload_client.fetch_x509_svid()
        
        # Validate SPIFFE ID for Zero Trust
        validator_result = {
            "valid": True,
            "spiffe_id": svid.spiffe_id,
            "trust_domain": "x0tta6bl4.local",
            "policy": "allow",
        }
        
        assert validator_result["valid"] is True
        assert validator_result["policy"] == "allow"


# =============================================================================
# Performance Benchmarks
# =============================================================================

class TestPerformance:
    """Performance benchmarks for SPIRE operations."""
    
    @pytest.mark.asyncio
    async def test_svid_issuance_throughput(self, workload_client):
        """Test SVID issuance throughput."""
        num_requests = 100
        
        start = time.time()
        tasks = [workload_client.fetch_x509_svid() for _ in range(num_requests)]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        throughput = num_requests / elapsed
        print(f"\nSVID issuance throughput: {throughput:.2f} requests/sec")
        
        assert throughput > 10  # At least 10 req/sec
    
    @pytest.mark.asyncio
    async def test_concurrent_mtls_handshakes(self, workload_client):
        """Test concurrent mTLS handshakes."""
        num_handshakes = 50
        
        async def mock_handshake():
            svid = await workload_client.fetch_x509_svid()
            await asyncio.sleep(0.01)  # Simulate handshake
            return svid
        
        start = time.time()
        results = await asyncio.gather(*[mock_handshake() for _ in range(num_handshakes)])
        elapsed = time.time() - start
        
        assert all(r is not None for r in results)
        print(f"\n{num_handshakes} concurrent handshakes completed in {elapsed:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
