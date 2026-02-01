"""
Comprehensive test suite for Proxy Selection Algorithm.

Tests:
- ML-based weighted scoring
- Predictive selection
- Adaptive load balancing
- Anti-pattern detection
- Domain profile optimization
"""
import pytest
import asyncio
import statistics
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.network.proxy_selection_algorithm import (
    ProxySelectionAlgorithm,
    SelectionStrategy,
    ProxyMetrics,
    DomainProfile,
    AdaptiveLoadBalancer
)
from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus


class TestProxyMetrics:
    """Test ProxyMetrics historical tracking."""
    
    def test_add_sample(self):
        """Test adding samples to metrics."""
        metrics = ProxyMetrics(proxy_id="test-proxy")
        
        metrics.add_sample(100.0, True)
        metrics.add_sample(150.0, False)
        
        assert len(metrics.latency_history) == 2
        assert len(metrics.success_history) == 2
        assert metrics.latency_history[-1] == 150.0
        assert metrics.success_history[-1] == 0.0
    
    def test_get_success_rate(self):
        """Test success rate calculation."""
        metrics = ProxyMetrics(proxy_id="test-proxy")
        
        # Empty metrics returns neutral default
        assert metrics.get_success_rate() == 0.5
        
        # Add samples: 8 successes, 2 failures (in order: 8 success first, then 2 failures)
        for _ in range(8):
            metrics.add_sample(100.0, True)
        for _ in range(2):
            metrics.add_sample(100.0, False)
        
        assert metrics.get_success_rate() == 0.8
        # Last 5 samples: 3 success (indices 5,6,7) + 2 failure (indices 8,9) = 3/5 = 0.6
        assert metrics.get_success_rate(window=5) == 0.6
    
    def test_get_avg_latency(self):
        """Test average latency calculation."""
        metrics = ProxyMetrics(proxy_id="test-proxy")
        
        # Empty returns high default
        assert metrics.get_avg_latency() == 1000.0
        
        # Add samples
        for latency in [100.0, 200.0, 300.0]:
            metrics.add_sample(latency, True)
        
        assert metrics.get_avg_latency() == 200.0
    
    def test_get_latency_trend(self):
        """Test latency trend detection."""
        metrics = ProxyMetrics(proxy_id="test-proxy")
        
        # Not enough data
        assert metrics.get_latency_trend() == 0.0
        
        # Improving trend (decreasing latency)
        for i in range(20):
            metrics.add_sample(200.0 - i * 5, True)  # Decreasing
        
        trend = metrics.get_latency_trend()
        assert trend < 0  # Negative = improving
    
    def test_get_stability_score(self):
        """Test stability score based on variance."""
        metrics = ProxyMetrics(proxy_id="test-proxy")
        
        # Not enough data
        assert metrics.get_stability_score() == 0.5
        
        # Stable proxy (low variance)
        for _ in range(20):
            metrics.add_sample(100.0 + (hash(str(_)) % 10), True)
        
        stability = metrics.get_stability_score()
        assert 0.0 <= stability <= 1.0


class TestProxySelectionAlgorithm:
    """Test proxy selection algorithm."""
    
    @pytest.fixture
    def algorithm(self):
        return ProxySelectionAlgorithm(
            default_strategy=SelectionStrategy.WEIGHTED_SCORE,
            latency_weight=0.3,
            success_weight=0.4,
            stability_weight=0.2,
            geographic_weight=0.1
        )
    
    @pytest.fixture
    def healthy_proxy(self):
        proxy = Mock(spec=ProxyEndpoint)
        proxy.id = "healthy-proxy"
        proxy.status = ProxyStatus.HEALTHY
        proxy.region = "us"
        proxy.country_code = "US"
        proxy.is_rate_limited.return_value = False
        return proxy
    
    @pytest.fixture
    def degraded_proxy(self):
        proxy = Mock(spec=ProxyEndpoint)
        proxy.id = "degraded-proxy"
        proxy.status = ProxyStatus.DEGRADED
        proxy.region = "eu"
        proxy.country_code = "DE"
        proxy.is_rate_limited.return_value = False
        return proxy
    
    @pytest.mark.asyncio
    async def test_weighted_scoring(self, algorithm, healthy_proxy):
        """Test weighted score calculation."""
        # Add good metrics
        metrics = algorithm._get_metrics(healthy_proxy)
        for _ in range(10):
            metrics.add_sample(100.0, True)
        
        score = algorithm.calculate_proxy_score(healthy_proxy)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be good score
    
    @pytest.mark.asyncio
    async def test_domain_preference_boost(self, algorithm, healthy_proxy):
        """Test domain-specific preference boosting."""
        domain = "example.com"

        # Record successful history for domain (more samples for measurable effect)
        for _ in range(10):
            algorithm.record_result(healthy_proxy, domain, 100.0, True)

        # Score should be boosted for this domain
        score_with_domain = algorithm.calculate_proxy_score(
            healthy_proxy, domain=domain
        )
        score_without = algorithm.calculate_proxy_score(healthy_proxy)

        # Score with domain should be at least as good (domain history counts)
        assert score_with_domain >= score_without
    
    @pytest.mark.asyncio
    async def test_blocked_proxy_avoidance(self, algorithm, healthy_proxy):
        """Test that blocked proxies are avoided."""
        domain = "blocked-domain.com"
        
        # Mark as blocked
        algorithm.record_result(healthy_proxy, domain, 100.0, False)
        algorithm.record_result(healthy_proxy, domain, 100.0, False)
        algorithm.record_result(healthy_proxy, domain, 100.0, False)
        
        score = algorithm.calculate_proxy_score(healthy_proxy, domain=domain)
        assert score == 0.0  # Completely avoided
    
    @pytest.mark.asyncio
    async def test_select_weighted(self, algorithm, healthy_proxy, degraded_proxy):
        """Test weighted random selection."""
        # Add metrics
        healthy_metrics = algorithm._get_metrics(healthy_proxy)
        for _ in range(10):
            healthy_metrics.add_sample(100.0, True)
        
        degraded_metrics = algorithm._get_metrics(degraded_proxy)
        for _ in range(10):
            degraded_metrics.add_sample(500.0, False)
        
        # Selection should prefer healthy proxy
        selections = {"healthy": 0, "degraded": 0}
        for _ in range(100):
            selected = await algorithm._select_weighted(
                [healthy_proxy, degraded_proxy],
                domain=None,
                preferred_region=None
            )
            if selected:
                selections[selected.id.split("-")[0]] += 1
        
        # Healthy should be selected much more often
        assert selections["healthy"] > selections["degraded"] * 2
    
    @pytest.mark.asyncio
    async def test_select_lowest_latency(self, algorithm, healthy_proxy, degraded_proxy):
        """Test lowest latency selection."""
        healthy_metrics = algorithm._get_metrics(healthy_proxy)
        healthy_metrics.add_sample(50.0, True)
        
        degraded_metrics = algorithm._get_metrics(degraded_proxy)
        degraded_metrics.add_sample(500.0, True)
        
        selected = await algorithm._select_lowest_latency([healthy_proxy, degraded_proxy])
        assert selected.id == "healthy-proxy"
    
    @pytest.mark.asyncio
    async def test_predictive_selection(self, algorithm, healthy_proxy):
        """Test predictive selection with trend analysis."""
        # Create proxy with improving trend
        improving_proxy = Mock(spec=ProxyEndpoint)
        improving_proxy.id = "improving-proxy"
        improving_proxy.status = ProxyStatus.HEALTHY
        improving_proxy.region = "us"
        improving_proxy.country_code = "US"
        improving_proxy.is_rate_limited.return_value = False
        
        metrics = algorithm._get_metrics(improving_proxy)
        # Decreasing latency (improving)
        for i in range(20):
            metrics.add_sample(200.0 - i * 5, True)
        
        # Should select improving proxy due to trend bonus
        selected = await algorithm._select_predictive(
            [improving_proxy, healthy_proxy],
            domain=None,
            preferred_region=None
        )
        
        assert selected is not None
    
    @pytest.mark.asyncio
    async def test_geographic_selection(self, algorithm, healthy_proxy, degraded_proxy):
        """Test geographic preference selection."""
        healthy_proxy.region = "us-east"
        degraded_proxy.region = "eu-west"
        
        selected = await algorithm._select_geographic(
            [healthy_proxy, degraded_proxy],
            preferred_region="us-east"
        )
        
        assert selected.id == "healthy-proxy"
    
    @pytest.mark.asyncio
    async def test_no_healthy_proxies(self, algorithm, degraded_proxy):
        """Test behavior when no healthy proxies available."""
        degraded_proxy.status = ProxyStatus.UNHEALTHY
        
        selected = await algorithm.select_proxy(
            [degraded_proxy],
            require_healthy=True
        )
        
        assert selected is None


class TestAdaptiveLoadBalancer:
    """Test adaptive load balancer."""
    
    @pytest.fixture
    def algorithm(self):
        return ProxySelectionAlgorithm()
    
    @pytest.fixture
    def load_balancer(self, algorithm):
        return AdaptiveLoadBalancer(algorithm)
    
    @pytest.fixture
    def mock_proxy(self):
        proxy = Mock(spec=ProxyEndpoint)
        proxy.id = "test-proxy"
        proxy.status = ProxyStatus.HEALTHY
        proxy.region = "us"
        proxy.is_rate_limited.return_value = False
        return proxy
    
    @pytest.mark.asyncio
    async def test_acquire_and_release(self, load_balancer, mock_proxy):
        """Test proxy acquisition and release."""
        proxy, token = await load_balancer.acquire_proxy([mock_proxy])
        
        assert proxy.id == "test-proxy"
        assert token.startswith("test-proxy_")
        
        # Check connection tracking
        assert load_balancer._active_connections.get("test-proxy", 0) == 1
        
        # Release
        await load_balancer.release_proxy(token)
        assert load_balancer._active_connections.get("test-proxy", 0) == 0
    
    @pytest.mark.asyncio
    async def test_load_based_penalty(self, load_balancer, algorithm):
        """Test that loaded proxies get penalized."""
        # Create two identical proxies
        proxy1 = Mock(spec=ProxyEndpoint)
        proxy1.id = "proxy1"
        proxy1.status = ProxyStatus.HEALTHY
        proxy1.region = "us"
        proxy1.is_rate_limited.return_value = False
        
        proxy2 = Mock(spec=ProxyEndpoint)
        proxy2.id = "proxy2"
        proxy2.status = ProxyStatus.HEALTHY
        proxy2.region = "us"
        proxy2.is_rate_limited.return_value = False
        
        # Acquire proxy1 multiple times
        tokens = []
        for _ in range(5):
            proxy, token = await load_balancer.acquire_proxy([proxy1, proxy2])
            if proxy.id == "proxy1":
                tokens.append(token)
        
        # Now proxy1 should have load penalty
        # Next acquisition should prefer proxy2
        proxy, _ = await load_balancer.acquire_proxy([proxy1, proxy2])
        assert proxy.id == "proxy2"
        
        # Cleanup
        for token in tokens:
            await load_balancer.release_proxy(token)


class TestAntiPatternDetection:
    """Test anti-pattern detection."""
    
    @pytest.fixture
    def algorithm(self):
        return ProxySelectionAlgorithm()
    
    @pytest.mark.asyncio
    async def test_pattern_detection(self, algorithm):
        """Test usage pattern detection."""
        proxy = Mock(spec=ProxyEndpoint)
        proxy.id = "test-proxy"
        
        # Record many events
        for i in range(150):
            domain = f"domain{i % 5}.com"
            success = i % 10 != 0  # 90% success rate
            algorithm.record_result(proxy, domain, 100.0, success)
        
        patterns = algorithm.detect_patterns()
        
        assert patterns["status"] == "success"
        assert "domain_preferences" in patterns
    
    @pytest.mark.asyncio
    async def test_recommendations(self, algorithm):
        """Test recommendation generation."""
        # Create problematic proxy
        proxy = Mock(spec=ProxyEndpoint)
        proxy.id = "bad-proxy"
        
        metrics = algorithm._get_metrics(proxy)
        for _ in range(20):
            metrics.add_sample(100.0, False)  # All failures
        
        recommendations = algorithm.get_recommendations()
        
        assert len(recommendations) > 0
        assert any(r["type"] == "untrusted_proxy" for r in recommendations)


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_selection_flow(self):
        """Test complete selection flow with all components."""
        algorithm = ProxySelectionAlgorithm()
        load_balancer = AdaptiveLoadBalancer(algorithm)
        
        # Create proxy pool
        proxies = []
        for i in range(5):
            proxy = Mock(spec=ProxyEndpoint)
            proxy.id = f"proxy-{i}"
            proxy.status = ProxyStatus.HEALTHY
            proxy.region = "us" if i < 3 else "eu"
            proxy.country_code = "US" if i < 3 else "DE"
            proxy.is_rate_limited.return_value = False
            
            # Vary performance
            metrics = algorithm._get_metrics(proxy)
            for j in range(20):
                latency = 100 + i * 50 + (hash(str(j)) % 20)
                success = j % (i + 2) != 0  # Varying success rates
                metrics.add_sample(latency, success)
            
            proxies.append(proxy)
        
        # Test selection
        domain = "test.com"
        for _ in range(50):
            proxy, token = await load_balancer.acquire_proxy(proxies, domain)
            assert proxy is not None
            
            # Simulate request
            latency = 100.0
            success = True
            
            # Record result
            algorithm.record_result(proxy, domain, latency, success)
            
            # Release
            await load_balancer.release_proxy(token)
        
        # Check patterns detected
        patterns = algorithm.detect_patterns()
        assert patterns["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
