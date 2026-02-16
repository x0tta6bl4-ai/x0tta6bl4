"""
Integration tests for Zero Trust Enforcement.

Tests the complete Zero Trust enforcement flow including:
- Policy evaluation
- Trust scoring
- Isolation management
- Continuous verification
"""

import asyncio
from typing import Any, Dict

import pytest

try:
    from src.security.zero_trust.enforcement import (TrustScore,
                                                     ZeroTrustEnforcer,
                                                     get_zero_trust_enforcer)

    ZERO_TRUST_AVAILABLE = True
except ImportError:
    ZERO_TRUST_AVAILABLE = False
    ZeroTrustEnforcer = None  # type: ignore
    TrustScore = None  # type: ignore


@pytest.mark.skipif(
    not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available"
)
class TestZeroTrustEnforcementIntegration:
    """Integration tests for Zero Trust Enforcement"""

    @pytest.fixture
    def enforcer(self):
        """Create Zero Trust Enforcer instance"""
        return ZeroTrustEnforcer()

    def test_enforcement_flow_allow(self, enforcer):
        """Test complete enforcement flow for allowed access"""
        # Simulate valid peer
        peer_spiffe_id = "spiffe://x0tta6bl4.mesh/workload/api"
        resource = "/api/v1/health"

        result = enforcer.enforce(peer_spiffe_id=peer_spiffe_id, resource=resource)

        assert result.allowed is True
        assert result.trust_score in [
            TrustScore.MEDIUM,
            TrustScore.HIGH,
            TrustScore.TRUSTED,
        ]
        assert result.reason == "Access granted"

    def test_enforcement_flow_deny(self, enforcer):
        """Test complete enforcement flow for denied access"""
        # Simulate invalid peer (multiple times to lower trust score)
        peer_spiffe_id = "spiffe://x0tta6bl4.mesh/workload/unknown"

        # Multiple failed attempts
        for _ in range(5):
            result = enforcer.enforce(
                peer_spiffe_id=peer_spiffe_id, resource="/api/v1/admin"
            )

        # Should eventually be denied or isolated
        final_result = enforcer.enforce(
            peer_spiffe_id=peer_spiffe_id, resource="/api/v1/admin"
        )

        # Either denied or isolated
        assert final_result.allowed is False or final_result.isolation_level is not None

    def test_trust_score_evolution(self, enforcer):
        """Test trust score evolution over time"""
        peer_spiffe_id = "spiffe://x0tta6bl4.mesh/workload/test"

        # Initial access
        result1 = enforcer.enforce(peer_spiffe_id, "/api/v1/health")
        initial_score = result1.trust_score

        # Multiple successful accesses
        for _ in range(10):
            result = enforcer.enforce(peer_spiffe_id, "/api/v1/health")
            assert result.allowed is True

        # Final access
        result2 = enforcer.enforce(peer_spiffe_id, "/api/v1/health")
        final_score = result2.trust_score

        # Trust score should improve or stay the same
        assert final_score.value >= initial_score.value

    def test_enforcement_statistics(self, enforcer):
        """Test enforcement statistics tracking"""
        # Perform multiple enforcements
        for i in range(10):
            peer_id = f"spiffe://x0tta6bl4.mesh/workload/node-{i}"
            enforcer.enforce(peer_id, "/api/v1/health")

        stats = enforcer.get_enforcement_stats()

        assert stats["total_requests"] == 10
        assert stats["total_requests"] == stats["allowed"] + stats["denied"]
        assert "allow_rate" in stats
        assert "deny_rate" in stats
        assert "tracked_peers" in stats


@pytest.mark.skipif(
    not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available"
)
class TestZeroTrustEnforcementE2E:
    """End-to-end tests for Zero Trust Enforcement"""

    @pytest.mark.asyncio
    async def test_complete_security_flow(self):
        """Test complete security flow with Zero Trust"""
        enforcer = get_zero_trust_enforcer()

        # Valid peer
        valid_peer = "spiffe://x0tta6bl4.mesh/workload/api"
        result = enforcer.enforce(valid_peer, "/api/v1/health")

        assert result.allowed is True

        # Check statistics
        stats = enforcer.get_enforcement_stats()
        assert stats["total_requests"] > 0
