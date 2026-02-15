"""
Tests for Geo-Sharded Proxy Pool Manager.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.network.geo_proxy_sharding import (GeoCrossRegionLoadBalancer,
                                            GeoProxyShardManager, Region,
                                            RegionalProxyPool, RegionalQuota,
                                            create_geo_proxy_manager,
                                            get_region_latency)
from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus


class TestRegion:
    """Tests for Region enum."""

    def test_all_regions_exist(self):
        """Test all expected regions exist."""
        assert Region.US_EAST.value == "us-east-1"
        assert Region.US_WEST.value == "us-west-2"
        assert Region.EU_WEST.value == "eu-west-1"
        assert Region.EU_CENTRAL.value == "eu-central-1"
        assert Region.ASIA_PACIFIC.value == "ap-southeast-1"
        assert Region.ASIA_NORTHEAST.value == "ap-northeast-1"


class TestGetRegionLatency:
    """Tests for inter-region latency calculation."""

    def test_same_region_zero_latency(self):
        """Test zero latency for same region."""
        assert get_region_latency(Region.US_EAST, Region.US_EAST) == 0

    def test_cross_region_latency(self):
        """Test latency between different regions."""
        latency = get_region_latency(Region.US_EAST, Region.US_WEST)
        assert latency > 0
        assert latency == 70

    def test_symmetric_latency(self):
        """Test latency is symmetric."""
        lat1 = get_region_latency(Region.US_EAST, Region.EU_WEST)
        lat2 = get_region_latency(Region.EU_WEST, Region.US_EAST)
        assert lat1 == lat2


class TestRegionalQuota:
    """Tests for RegionalQuota."""

    def test_initial_state(self):
        """Test initial quota state."""
        quota = RegionalQuota(region=Region.US_EAST)

        assert quota.requests_this_minute == 0
        assert quota.requests_this_hour == 0
        assert quota.is_rate_limited is False
        assert quota.utilization == 0.0

    def test_record_request(self):
        """Test request recording."""
        quota = RegionalQuota(region=Region.US_EAST)

        quota.record_request()

        assert quota.requests_this_minute == 1
        assert quota.requests_this_hour == 1

    def test_rate_limiting(self):
        """Test rate limiting activation."""
        quota = RegionalQuota(
            region=Region.US_EAST, max_requests_per_minute=10, max_requests_per_hour=100
        )

        # Make requests up to limit
        for _ in range(10):
            quota.record_request()

        assert quota.is_rate_limited is True

    def test_utilization_calculation(self):
        """Test utilization calculation."""
        quota = RegionalQuota(
            region=Region.US_EAST,
            max_requests_per_minute=100,
            max_requests_per_hour=1000,
        )

        for _ in range(50):
            quota.record_request()

        # 50/100 = 0.5 for minute utilization
        assert quota.utilization == pytest.approx(0.5, abs=0.01)

    def test_counter_reset_after_minute(self):
        """Test minute counter reset."""
        quota = RegionalQuota(region=Region.US_EAST)

        quota.record_request()
        quota.minute_start = time.time() - 61  # Simulate minute passed

        quota.record_request()

        assert quota.requests_this_minute == 1  # Should be reset


class TestRegionalProxyPool:
    """Tests for RegionalProxyPool."""

    @pytest.fixture
    def pool(self):
        return RegionalProxyPool(region=Region.US_EAST)

    @pytest.fixture
    def healthy_proxy(self):
        proxy = ProxyEndpoint(
            id="test-proxy",
            host="proxy.example.com",
            port=8080,
            status=ProxyStatus.HEALTHY,
        )
        return proxy

    def test_add_proxy(self, pool, healthy_proxy):
        """Test adding proxy to pool."""
        pool.add_proxy(healthy_proxy)

        assert len(pool.proxies) == 1
        assert pool.total_count == 1
        assert healthy_proxy.region == Region.US_EAST.value

    def test_get_healthy_proxies(self, pool, healthy_proxy):
        """Test getting healthy proxies."""
        unhealthy_proxy = ProxyEndpoint(
            id="unhealthy",
            host="proxy2.example.com",
            port=8080,
            status=ProxyStatus.UNHEALTHY,
        )

        pool.add_proxy(healthy_proxy)
        pool.add_proxy(unhealthy_proxy)

        healthy = pool.get_healthy_proxies()

        assert len(healthy) == 1
        assert healthy[0].id == "test-proxy"
        assert pool.healthy_count == 1

    def test_get_available_proxies(self, pool, healthy_proxy):
        """Test getting available (healthy + not rate limited) proxies."""
        pool.add_proxy(healthy_proxy)

        available = pool.get_available_proxies()

        assert len(available) == 1

    def test_is_available(self, pool, healthy_proxy):
        """Test pool availability check."""
        # Empty pool is not available
        assert pool.is_available is False

        pool.add_proxy(healthy_proxy)
        pool.update_metrics()

        assert pool.is_available is True

    def test_health_score_calculation(self, pool, healthy_proxy):
        """Test health score calculation."""
        pool.add_proxy(healthy_proxy)
        healthy_proxy.success_count = 90
        healthy_proxy.failure_count = 10

        pool.update_metrics()

        # Should have positive health score
        assert pool.health_score > 0

    def test_record_request(self, pool, healthy_proxy):
        """Test request recording in pool."""
        pool.add_proxy(healthy_proxy)

        pool.record_request(healthy_proxy, success=True, latency_ms=100.0)

        assert len(pool.request_history) == 1
        assert pool.request_history[0]["success"] is True


class TestGeoProxyShardManager:
    """Tests for GeoProxyShardManager."""

    @pytest.fixture
    def manager(self):
        return GeoProxyShardManager(default_region=Region.US_EAST)

    @pytest.fixture
    def sample_proxy(self):
        return ProxyEndpoint(
            id="proxy-1",
            host="proxy.example.com",
            port=8080,
            status=ProxyStatus.HEALTHY,
        )

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.default_region == Region.US_EAST
        assert len(manager.pools) == len(Region)

    def test_add_proxy_to_region(self, manager, sample_proxy):
        """Test adding proxy to specific region."""
        manager.add_proxy_to_region(sample_proxy, Region.US_EAST)

        pool = manager.pools[Region.US_EAST]
        assert pool.total_count == 1
        assert sample_proxy.region == Region.US_EAST.value

    def test_add_proxies_from_config(self, manager):
        """Test adding proxies from configuration."""
        config = {
            "us-east-1": [
                {"id": "proxy-1", "host": "p1.example.com", "port": 8080},
                {"id": "proxy-2", "host": "p2.example.com", "port": 8080},
            ],
            "eu-west-1": [
                {"id": "proxy-3", "host": "p3.example.com", "port": 8080},
            ],
        }

        manager.add_proxies_from_config(config)

        assert manager.pools[Region.US_EAST].total_count == 2
        assert manager.pools[Region.EU_WEST].total_count == 1

    def test_get_nearest_regions(self, manager):
        """Test getting nearest regions."""
        nearest = manager.get_nearest_regions(Region.US_EAST, count=3)

        assert len(nearest) == 3
        # US_WEST should be among nearest to US_EAST
        assert Region.US_WEST in nearest

    def test_domain_affinity(self, manager):
        """Test domain affinity setting and retrieval."""
        manager.set_domain_affinity("google.com", Region.US_WEST)

        assert manager.get_domain_region("google.com") == Region.US_WEST
        assert manager.get_domain_region("unknown.com") is None

    @pytest.mark.asyncio
    async def test_select_proxy_from_empty_pool(self, manager):
        """Test proxy selection from empty pool."""
        proxy = await manager.select_proxy()

        assert proxy is None

    @pytest.mark.asyncio
    async def test_select_proxy_success(self, manager, sample_proxy):
        """Test successful proxy selection."""
        manager.add_proxy_to_region(sample_proxy, Region.US_EAST)
        sample_proxy.success_count = 10  # Make it look healthy
        manager.pools[Region.US_EAST].update_metrics()

        proxy = await manager.select_proxy(preferred_region=Region.US_EAST)

        assert proxy is not None
        assert proxy.id == sample_proxy.id
        assert manager.total_requests == 1
        assert manager.successful_requests == 1

    @pytest.mark.asyncio
    async def test_select_proxy_with_failover(self, manager, sample_proxy):
        """Test proxy selection with failover."""
        # Add proxy only to EU region
        manager.add_proxy_to_region(sample_proxy, Region.EU_WEST)
        sample_proxy.success_count = 10
        manager.pools[Region.EU_WEST].update_metrics()

        # Request US region - should failover to EU
        proxy = await manager.select_proxy(
            preferred_region=Region.US_EAST, allow_failover=True
        )

        assert proxy is not None
        assert manager.failover_count == 1

    @pytest.mark.asyncio
    async def test_select_proxy_no_failover(self, manager, sample_proxy):
        """Test proxy selection without failover."""
        manager.add_proxy_to_region(sample_proxy, Region.EU_WEST)

        proxy = await manager.select_proxy(
            preferred_region=Region.US_EAST, allow_failover=False
        )

        assert proxy is None

    def test_get_region_stats(self, manager, sample_proxy):
        """Test getting region statistics."""
        manager.add_proxy_to_region(sample_proxy, Region.US_EAST)
        manager.pools[Region.US_EAST].update_metrics()

        stats = manager.get_region_stats(Region.US_EAST)

        assert stats["region"] == "us-east-1"
        assert stats["total_proxies"] == 1

    def test_get_all_stats(self, manager, sample_proxy):
        """Test getting all statistics."""
        manager.add_proxy_to_region(sample_proxy, Region.US_EAST)

        stats = manager.get_all_stats()

        assert "total_requests" in stats
        assert "regions" in stats
        assert "us-east-1" in stats["regions"]

    def test_get_metrics_prometheus(self, manager, sample_proxy):
        """Test Prometheus metrics format."""
        manager.add_proxy_to_region(sample_proxy, Region.US_EAST)

        metrics = manager.get_metrics_prometheus()

        assert "geo_proxy_total_requests" in metrics
        assert "geo_proxy_pool_health_score" in metrics
        assert 'region="us-east-1"' in metrics


class TestGeoCrossRegionLoadBalancer:
    """Tests for GeoCrossRegionLoadBalancer."""

    @pytest.fixture
    def manager(self):
        manager = GeoProxyShardManager(default_region=Region.US_EAST)
        # Add healthy proxies to multiple regions
        for region in [Region.US_EAST, Region.EU_WEST, Region.ASIA_PACIFIC]:
            proxy = ProxyEndpoint(
                id=f"proxy-{region.value}",
                host=f"{region.value}.example.com",
                port=8080,
                status=ProxyStatus.HEALTHY,
            )
            proxy.success_count = 10
            manager.add_proxy_to_region(proxy, region)
            manager.pools[region].update_metrics()
        return manager

    @pytest.fixture
    def balancer(self, manager):
        return GeoCrossRegionLoadBalancer(
            shard_manager=manager,
            strategy=GeoCrossRegionLoadBalancer.Strategy.LOCALITY_FIRST,
            local_region=Region.US_EAST,
        )

    @pytest.mark.asyncio
    async def test_locality_first_strategy(self, balancer):
        """Test locality-first strategy."""
        region = await balancer.select_region()

        assert region == Region.US_EAST

    @pytest.mark.asyncio
    async def test_round_robin_strategy(self, manager):
        """Test round-robin strategy."""
        balancer = GeoCrossRegionLoadBalancer(
            shard_manager=manager,
            strategy=GeoCrossRegionLoadBalancer.Strategy.ROUND_ROBIN,
        )

        regions = []
        for _ in range(6):
            region = await balancer.select_region()
            regions.append(region)

        # Should cycle through regions
        assert len(set(regions)) >= 2

    @pytest.mark.asyncio
    async def test_latency_based_strategy(self, manager):
        """Test latency-based strategy."""
        # Set different latencies
        manager.pools[Region.US_EAST].avg_latency_ms = 200
        manager.pools[Region.EU_WEST].avg_latency_ms = 50
        manager.pools[Region.ASIA_PACIFIC].avg_latency_ms = 300

        balancer = GeoCrossRegionLoadBalancer(
            shard_manager=manager,
            strategy=GeoCrossRegionLoadBalancer.Strategy.LATENCY_BASED,
        )

        region = await balancer.select_region()

        assert region == Region.EU_WEST  # Lowest latency

    @pytest.mark.asyncio
    async def test_cost_optimized_strategy(self, manager):
        """Test cost-optimized strategy."""
        balancer = GeoCrossRegionLoadBalancer(
            shard_manager=manager,
            strategy=GeoCrossRegionLoadBalancer.Strategy.COST_OPTIMIZED,
        )
        balancer.region_costs[Region.US_EAST] = 0.5
        balancer.region_costs[Region.EU_WEST] = 1.5
        balancer.region_costs[Region.ASIA_PACIFIC] = 2.0

        region = await balancer.select_region()

        assert region == Region.US_EAST  # Cheapest

    @pytest.mark.asyncio
    async def test_get_proxy(self, balancer):
        """Test getting proxy through load balancer."""
        proxy = await balancer.get_proxy()

        assert proxy is not None


class TestCreateGeoProxyManager:
    """Tests for factory function."""

    def test_create_with_config(self):
        """Test creating manager with configuration."""
        config = {
            "regions": {
                "us-east-1": [
                    {"id": "p1", "host": "proxy1.com", "port": 8080},
                ],
                "eu-west-1": [
                    {"id": "p2", "host": "proxy2.com", "port": 8080},
                ],
            },
            "domain_affinity": {
                "google.com": "us-east-1",
            },
        }

        manager = create_geo_proxy_manager(config, default_region="us-east-1")

        assert manager.default_region == Region.US_EAST
        assert manager.pools[Region.US_EAST].total_count == 1
        assert manager.pools[Region.EU_WEST].total_count == 1
        assert manager.get_domain_region("google.com") == Region.US_EAST

    def test_create_with_unknown_region(self):
        """Test creating manager with unknown region defaults."""
        manager = create_geo_proxy_manager({}, default_region="unknown-region")

        assert manager.default_region == Region.US_EAST  # Fallback


class TestGeoShardingIntegration:
    """Integration tests for geo-sharding."""

    @pytest.mark.asyncio
    async def test_full_request_flow(self):
        """Test complete request flow with geo-sharding."""
        manager = GeoProxyShardManager()

        # Add proxies to multiple regions
        for i, region in enumerate([Region.US_EAST, Region.EU_WEST]):
            proxy = ProxyEndpoint(
                id=f"proxy-{i}",
                host=f"proxy{i}.example.com",
                port=8080,
                status=ProxyStatus.HEALTHY,
            )
            proxy.success_count = 10
            manager.add_proxy_to_region(proxy, region)
            manager.pools[region].update_metrics()

        # Make multiple requests
        selected_regions = set()
        for _ in range(10):
            proxy = await manager.select_proxy(allow_failover=True)
            if proxy:
                selected_regions.add(proxy.region)

        assert len(selected_regions) >= 1
        assert manager.total_requests == 10

    @pytest.mark.asyncio
    async def test_health_degradation_failover(self):
        """Test failover when primary region health degrades."""
        manager = GeoProxyShardManager(
            default_region=Region.US_EAST, failover_threshold=0.5
        )

        # Add healthy proxy to backup region
        backup_proxy = ProxyEndpoint(
            id="backup",
            host="backup.example.com",
            port=8080,
            status=ProxyStatus.HEALTHY,
        )
        backup_proxy.success_count = 100
        manager.add_proxy_to_region(backup_proxy, Region.EU_WEST)
        manager.pools[Region.EU_WEST].update_metrics()

        # Add unhealthy proxy to primary region
        primary_proxy = ProxyEndpoint(
            id="primary",
            host="primary.example.com",
            port=8080,
            status=ProxyStatus.UNHEALTHY,
        )
        manager.add_proxy_to_region(primary_proxy, Region.US_EAST)
        manager.pools[Region.US_EAST].update_metrics()

        # Request should fail over
        proxy = await manager.select_proxy(
            preferred_region=Region.US_EAST, allow_failover=True
        )

        assert proxy is not None
        assert proxy.id == "backup"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
