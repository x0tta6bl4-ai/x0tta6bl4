"""
Unit tests for Zero Trust Enforcement.

Tests the Zero Trust enforcement engine including:
- Policy evaluation
- Trust scoring
- Isolation management
- Enforcement statistics
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

try:
    from src.security.zero_trust.enforcement import (
        ZeroTrustEnforcer,
        TrustScore,
        EnforcementResult,
        get_zero_trust_enforcer
    )
    ZERO_TRUST_AVAILABLE = True
except ImportError:
    ZERO_TRUST_AVAILABLE = False
    ZeroTrustEnforcer = None  # type: ignore
    TrustScore = None  # type: ignore
    EnforcementResult = None  # type: ignore


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available")
class TestZeroTrustEnforcer:
    """Unit tests for ZeroTrustEnforcer"""
    
    @pytest.fixture
    def enforcer(self):
        """Create Zero Trust Enforcer instance"""
        with patch('src.security.zero_trust.enforcement.ZeroTrustValidator'), \
             patch('src.security.zero_trust.enforcement.AutoIsolationManager'), \
             patch('src.security.zero_trust.enforcement.ContinuousVerificationEngine'), \
             patch('src.security.zero_trust.enforcement.get_policy_engine') as mock_gpe:
            mock_gpe.return_value = Mock()
            return ZeroTrustEnforcer()
    
    def test_enforcer_initialization(self, enforcer):
        """Test enforcer initialization"""
        assert enforcer is not None
        assert enforcer.enforcement_stats["total_requests"] == 0
        assert enforcer.enforcement_stats["allowed"] == 0
        assert enforcer.enforcement_stats["denied"] == 0
    
    def test_enforce_allow(self, enforcer):
        """Test enforcement for allowed access"""
        # Mock sub-components to allow access
        enforcer.isolation_manager.get_isolation_status.return_value = None
        enforcer.validator.validate_connection.return_value = True
        mock_decision = Mock(allowed=True, reason="allowed")
        enforcer.policy_engine.evaluate.return_value = mock_decision
        with patch.object(enforcer, '_calculate_trust_score', return_value=TrustScore.HIGH):
            result = enforcer.enforce(
                peer_spiffe_id="spiffe://x0tta6bl4.mesh/workload/api",
                resource="/api/v1/health"
            )

            assert result.allowed is True
            assert result.trust_score == TrustScore.HIGH
            assert enforcer.enforcement_stats["allowed"] > 0

    def test_enforce_deny(self, enforcer):
        """Test enforcement for denied access via policy"""
        enforcer.isolation_manager.get_isolation_status.return_value = None
        enforcer.validator.validate_connection.return_value = True
        mock_decision = Mock(allowed=False, reason="policy denied")
        enforcer.policy_engine.evaluate.return_value = mock_decision
        result = enforcer.enforce(
            peer_spiffe_id="spiffe://x0tta6bl4.mesh/workload/unknown",
            resource="/api/v1/admin"
        )

        assert result.allowed is False
        assert enforcer.enforcement_stats["denied"] > 0
    
    def test_trust_score_calculation(self, enforcer):
        """Test trust score calculation"""
        peer_id = "spiffe://x0tta6bl4.mesh/workload/test"
        
        # Initial score
        score1 = enforcer._calculate_trust_score(peer_id)
        assert score1 in [TrustScore.LOW, TrustScore.MEDIUM]
        
        # Improve score with successful accesses
        for _ in range(10):
            enforcer._update_trust_score(peer_id, 0.05)
        
        score2 = enforcer._calculate_trust_score(peer_id)
        assert score2.value >= score1.value
    
    def test_trust_score_update(self, enforcer):
        """Test trust score update"""
        peer_id = "spiffe://x0tta6bl4.mesh/workload/test"
        
        initial_score = enforcer.trust_scores.get(peer_id, 0.5)
        
        # Update score
        enforcer._update_trust_score(peer_id, 0.1)
        
        new_score = enforcer.trust_scores.get(peer_id)
        assert new_score > initial_score
        assert new_score <= 1.0
    
    def test_enforcement_statistics(self, enforcer):
        """Test enforcement statistics"""
        # Mock sub-components to allow access
        enforcer.isolation_manager.get_isolation_status.return_value = None
        enforcer.validator.validate_connection.return_value = True
        mock_decision = Mock(allowed=True, reason="allowed")
        enforcer.policy_engine.evaluate.return_value = mock_decision

        for i in range(10):
            peer_id = f"spiffe://x0tta6bl4.mesh/workload/node-{i}"
            enforcer.enforce(peer_id, "/api/v1/health")

        stats = enforcer.get_enforcement_stats()

        assert stats["total_requests"] == 10
        assert stats["total_requests"] == stats["allowed"] + stats["denied"]
        assert "allow_rate" in stats
        assert "deny_rate" in stats
        assert "tracked_peers" in stats


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available")
class TestTrustScore:
    """Unit tests for TrustScore enum"""
    
    def test_trust_score_values(self):
        """Test TrustScore enum values"""
        assert TrustScore.UNTRUSTED.value == 0
        assert TrustScore.LOW.value == 1
        assert TrustScore.MEDIUM.value == 2
        assert TrustScore.HIGH.value == 3
        assert TrustScore.TRUSTED.value == 4


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available")
class TestEnforcementResult:
    """Unit tests for EnforcementResult"""
    
    def test_enforcement_result_creation(self):
        """Test EnforcementResult creation"""
        result = EnforcementResult(
            allowed=True,
            trust_score=TrustScore.HIGH,
            reason="Access granted"
        )
        
        assert result.allowed is True
        assert result.trust_score == TrustScore.HIGH
        assert result.reason == "Access granted"


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust enforcement not available")
class TestGetZeroTrustEnforcer:
    """Unit tests for get_zero_trust_enforcer singleton"""
    
    def test_singleton_pattern(self):
        """Test that get_zero_trust_enforcer returns singleton"""
        import src.security.zero_trust.enforcement as enf_module
        enf_module._zero_trust_enforcer = None  # Reset singleton
        with patch('src.security.zero_trust.enforcement.ZeroTrustValidator'), \
             patch('src.security.zero_trust.enforcement.AutoIsolationManager'), \
             patch('src.security.zero_trust.enforcement.ContinuousVerificationEngine'):
            enforcer1 = get_zero_trust_enforcer()
            enforcer2 = get_zero_trust_enforcer()

            # Should be the same instance
            assert enforcer1 is enforcer2
        enf_module._zero_trust_enforcer = None  # Cleanup

