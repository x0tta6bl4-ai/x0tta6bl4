"""
Comprehensive test suite for Reputation Scoring System.

Tests:
- Exponential decay formulas
- Proxy trust scoring
- Block detection with recovery
- Statistical anomaly detection
"""

import time
from unittest.mock import Mock

import pytest

from src.network.reputation_scoring import (DomainReputation, ProxyTrustScore,
                                            ReputationEvent, ReputationLevel,
                                            ReputationScoringSystem)


class TestReputationLevel:
    """Test reputation level classification."""

    def test_from_score_excellent(self):
        """Test EXCELLENT level classification."""
        assert ReputationLevel.from_score(0.95) == ReputationLevel.EXCELLENT
        assert ReputationLevel.from_score(1.0) == ReputationLevel.EXCELLENT

    def test_from_score_good(self):
        """Test GOOD level classification."""
        assert ReputationLevel.from_score(0.8) == ReputationLevel.GOOD
        assert ReputationLevel.from_score(0.7) == ReputationLevel.GOOD

    def test_from_score_poor(self):
        """Test POOR level classification."""
        assert ReputationLevel.from_score(0.4) == ReputationLevel.POOR

    def test_from_score_bad(self):
        """Test BAD level classification."""
        assert ReputationLevel.from_score(0.1) == ReputationLevel.BAD


class TestDomainReputation:
    """Test domain reputation tracking."""

    def test_initial_score(self):
        """Test initial reputation score."""
        rep = DomainReputation(domain="test.com")
        assert rep.score == 0.5
        assert rep.get_level() == ReputationLevel.FAIR

    def test_success_boost(self):
        """Test score boost on success."""
        rep = DomainReputation(domain="test.com")

        event = ReputationEvent(timestamp=time.time(), success=True, latency_ms=100.0)
        rep.record_event(event)

        assert rep.score > 0.5
        assert rep.success_streak == 1
        assert rep.failure_streak == 0

    def test_failure_penalty(self):
        """Test score penalty on failure."""
        rep = DomainReputation(domain="test.com")

        event = ReputationEvent(
            timestamp=time.time(), success=False, latency_ms=0.0, error_type="timeout"
        )
        rep.record_event(event)

        assert rep.score < 0.5
        assert rep.failure_streak == 1
        assert rep.success_streak == 0

    def test_block_penalty(self):
        """Test additional penalty for blocks."""
        rep = DomainReputation(domain="test.com")

        event = ReputationEvent(
            timestamp=time.time(), success=False, latency_ms=0.0, error_type="blocked"
        )
        rep.record_event(event)

        # Block should have extra penalty
        assert rep.block_events == 1
        assert rep.score < 0.4  # Significant penalty

    def test_exponential_decay(self):
        """Test exponential decay over time."""
        rep = DomainReputation(domain="test.com", decay_factor=0.95)

        # Build up score
        for _ in range(10):
            event = ReputationEvent(
                timestamp=time.time(), success=True, latency_ms=100.0
            )
            rep.record_event(event)

        initial_score = rep.score
        assert initial_score > 0.8

        # Simulate time passing (1 day)
        rep.last_access = time.time() - 86400

        # New event should trigger decay
        event = ReputationEvent(timestamp=time.time(), success=True, latency_ms=100.0)
        rep.record_event(event)

        # Score should have decayed
        assert rep.score < initial_score * 0.96

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        rep = DomainReputation(domain="test.com")

        # Add 8 successes, 2 failures
        for i in range(10):
            event = ReputationEvent(
                timestamp=time.time(), success=i < 8, latency_ms=100.0
            )
            rep.record_event(event)

        assert rep.get_success_rate() == 0.8
        assert rep.get_success_rate(window=5) == 1.0  # Last 5 all success

    def test_risk_score_calculation(self):
        """Test risk score calculation."""
        rep = DomainReputation(domain="test.com")

        # Initially low risk
        initial_risk = rep.get_risk_score()
        assert initial_risk < 0.5

        # Add failures to increase risk
        for _ in range(5):
            event = ReputationEvent(
                timestamp=time.time(),
                success=False,
                latency_ms=0.0,
                error_type="blocked",
            )
            rep.record_event(event)

        risk = rep.get_risk_score()
        assert risk > 0.5  # Higher risk

    def test_event_retention(self):
        """Test that old events are retained but limited."""
        rep = DomainReputation(domain="test.com")

        # Add 150 events
        for i in range(150):
            event = ReputationEvent(
                timestamp=time.time() + i, success=True, latency_ms=100.0
            )
            rep.record_event(event)

        # Should keep only last 100
        assert len(rep.events) == 100


class TestProxyTrustScore:
    """Test proxy trust scoring."""

    def test_initial_scores(self):
        """Test initial trust scores."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        assert score.trust_score == 0.5
        assert score.reliability_score == 0.5
        assert score.performance_score == 0.5

    def test_successful_requests_boost_trust(self):
        """Test that successful requests increase trust."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        # Record successful requests
        for i in range(20):
            score.record_result(success=True, latency_ms=100.0 + i)

        assert score.total_requests == 20
        assert score.successful_requests == 20
        assert score.trust_score > 0.5
        assert score.reliability_score > 0.5

    def test_failures_reduce_trust(self):
        """Test that failures reduce trust."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        # Record mixed results
        for i in range(20):
            score.record_result(success=i < 10, latency_ms=100.0)  # 50% success

        assert score.trust_score < 0.5
        assert score.reliability_score == 0.5

    def test_blocks_severely_penalize(self):
        """Test that blocks severely penalize trust."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        # Record mostly successful but with blocks
        for i in range(20):
            score.record_result(
                success=i < 18,
                latency_ms=100.0,
                error_type="blocked" if i >= 18 else None,
            )

        assert score.blocked_requests == 2
        assert score.trust_score < 0.6  # Penalized for blocks

    def test_performance_scoring_latency_tiers(self):
        """Test performance scoring based on latency tiers."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        # Excellent latency (< 100ms)
        for _ in range(10):
            score.record_result(success=True, latency_ms=50.0)
        assert score.performance_score == 1.0

        # Reset and test good latency (100-300ms)
        score2 = ProxyTrustScore(proxy_id="test-proxy-2")
        for _ in range(10):
            score2.record_result(success=True, latency_ms=200.0)
        assert score2.performance_score == 0.9

        # Test poor latency (> 1000ms)
        score3 = ProxyTrustScore(proxy_id="test-proxy-3")
        for _ in range(10):
            score3.record_result(success=True, latency_ms=1500.0)
        assert score3.performance_score < 0.5

    def test_latency_history_retention(self):
        """Test latency history retention."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        # Add 150 latency samples
        for i in range(150):
            score.record_result(success=True, latency_ms=float(i))

        # Should keep only last 100
        assert len(score.latency_history) == 100
        assert score.latency_history[0] == 50.0  # First retained

    def test_error_breakdown(self):
        """Test error type tracking."""
        score = ProxyTrustScore(proxy_id="test-proxy")

        score.record_result(success=False, latency_ms=0.0, error_type="timeout")
        score.record_result(success=False, latency_ms=0.0, error_type="timeout")
        score.record_result(success=False, latency_ms=0.0, error_type="blocked")

        breakdown = score.get_error_breakdown()
        assert breakdown["timeout"] == 2
        assert breakdown["blocked"] == 1


class TestReputationScoringSystem:
    """Test the complete reputation scoring system."""

    @pytest.fixture
    async def system(self):
        """Create a reputation scoring system."""
        return ReputationScoringSystem()

    @pytest.mark.asyncio
    async def test_record_domain_event(self):
        """Test recording domain events."""
        system = ReputationScoringSystem()

        await system.record_domain_event(
            domain="test.com", success=True, latency_ms=100.0, proxy_id="proxy-1"
        )

        rep = system.get_domain_reputation("test.com")
        assert rep is not None
        assert rep.domain == "test.com"
        assert len(rep.events) == 1

    @pytest.mark.asyncio
    async def test_record_proxy_result(self):
        """Test recording proxy results."""
        system = ReputationScoringSystem()

        await system.record_proxy_result(
            proxy_id="proxy-1", success=True, latency_ms=100.0
        )

        score = system.get_proxy_trust("proxy-1")
        assert score is not None
        assert score.proxy_id == "proxy-1"
        assert score.total_requests == 1

    @pytest.mark.asyncio
    async def test_get_high_risk_domains(self):
        """Test identifying high-risk domains."""
        system = ReputationScoringSystem()

        # Create low-risk domain
        for _ in range(10):
            await system.record_domain_event(
                domain="safe.com", success=True, latency_ms=100.0
            )

        # Create high-risk domain
        for _ in range(10):
            await system.record_domain_event(
                domain="risky.com", success=False, latency_ms=0.0, error_type="blocked"
            )

        high_risk = system.get_high_risk_domains(threshold=0.5)
        assert len(high_risk) == 1
        assert high_risk[0].domain == "risky.com"

    @pytest.mark.asyncio
    async def test_get_trusted_proxies(self):
        """Test identifying trusted proxies."""
        system = ReputationScoringSystem()

        # Create trusted proxy
        for _ in range(20):
            await system.record_proxy_result(
                proxy_id="trusted-proxy", success=True, latency_ms=100.0
            )

        # Create untrusted proxy
        for _ in range(20):
            await system.record_proxy_result(
                proxy_id="untrusted-proxy", success=False, latency_ms=0.0
            )

        trusted = system.get_trusted_proxies(min_trust=0.6)
        assert len(trusted) == 1
        assert trusted[0].proxy_id == "trusted-proxy"

    @pytest.mark.asyncio
    async def test_recommendations(self):
        """Test recommendation generation."""
        system = ReputationScoringSystem()

        # Create problematic proxy
        for _ in range(20):
            await system.record_proxy_result(
                proxy_id="bad-proxy", success=False, latency_ms=0.0
            )

        recommendations = system.get_recommendations()

        assert len(recommendations) > 0
        assert any(r["type"] == "untrusted_proxy" for r in recommendations)

    @pytest.mark.asyncio
    async def test_export_stats(self):
        """Test statistics export."""
        system = ReputationScoringSystem()

        # Add some data
        await system.record_domain_event("test.com", True, 100.0)
        await system.record_proxy_result("proxy-1", True, 100.0)

        stats = system.export_stats()

        assert "domains" in stats
        assert "proxies" in stats
        assert stats["domains"]["total"] == 1
        assert stats["proxies"]["total"] == 1


class TestAnomalyDetection:
    """Test anomaly detection capabilities."""

    @pytest.mark.asyncio
    async def test_sudden_spike_detection(self):
        """Test detection of sudden failure spikes."""
        system = ReputationScoringSystem()

        # Normal operation
        for _ in range(20):
            await system.record_proxy_result("proxy-1", True, 100.0)

        # Sudden spike in failures
        for _ in range(10):
            await system.record_proxy_result("proxy-1", False, 0.0)

        score = system.get_proxy_trust("proxy-1")
        # Trust should drop significantly
        assert score.trust_score < 0.6
        assert score.reliability_score < 0.7

    @pytest.mark.asyncio
    async def test_domain_blocking_pattern(self):
        """Test detection of domain blocking patterns."""
        system = ReputationScoringSystem()

        # Domain blocks multiple proxies
        for proxy_id in ["proxy-1", "proxy-2", "proxy-3", "proxy-4"]:
            await system.record_domain_event(
                domain="blocked-site.com",
                success=False,
                latency_ms=0.0,
                proxy_id=proxy_id,
                error_type="blocked",
            )

        rep = system.get_domain_reputation("blocked-site.com")
        assert rep.block_events >= 4
        assert rep.get_risk_score() > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
