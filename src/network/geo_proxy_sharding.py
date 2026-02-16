"""
Geo-Sharded Proxy Pool Manager for x0tta6bl4.

Provides:
- Geographic distribution of proxy pools
- Locality-aware proxy selection
- Cross-region failover with latency optimization
- Regional rate limiting and quotas
- Health monitoring per region
- Metrics and analytics
"""

import asyncio
import logging
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.network.residential_proxy_manager import (DomainReputation,
                                                   ProxyEndpoint, ProxyStatus,
                                                   ResidentialProxyManager,
                                                   TLSFingerprintRandomizer)

logger = logging.getLogger(__name__)


class Region(Enum):
    """Geographic regions for proxy sharding."""

    US_EAST = "us-east-1"
    US_WEST = "us-west-2"
    EU_WEST = "eu-west-1"
    EU_CENTRAL = "eu-central-1"
    ASIA_PACIFIC = "ap-southeast-1"
    ASIA_NORTHEAST = "ap-northeast-1"


# Latency matrix between regions (estimated milliseconds)
INTER_REGION_LATENCY = {
    (Region.US_EAST, Region.US_WEST): 70,
    (Region.US_EAST, Region.EU_WEST): 80,
    (Region.US_EAST, Region.EU_CENTRAL): 90,
    (Region.US_EAST, Region.ASIA_PACIFIC): 200,
    (Region.US_EAST, Region.ASIA_NORTHEAST): 180,
    (Region.US_WEST, Region.EU_WEST): 140,
    (Region.US_WEST, Region.EU_CENTRAL): 150,
    (Region.US_WEST, Region.ASIA_PACIFIC): 160,
    (Region.US_WEST, Region.ASIA_NORTHEAST): 120,
    (Region.EU_WEST, Region.EU_CENTRAL): 20,
    (Region.EU_WEST, Region.ASIA_PACIFIC): 200,
    (Region.EU_WEST, Region.ASIA_NORTHEAST): 250,
    (Region.EU_CENTRAL, Region.ASIA_PACIFIC): 180,
    (Region.EU_CENTRAL, Region.ASIA_NORTHEAST): 230,
    (Region.ASIA_PACIFIC, Region.ASIA_NORTHEAST): 80,
}


def get_region_latency(from_region: Region, to_region: Region) -> int:
    """Get estimated latency between two regions."""
    if from_region == to_region:
        return 0

    key = (from_region, to_region)
    reverse_key = (to_region, from_region)

    return INTER_REGION_LATENCY.get(key) or INTER_REGION_LATENCY.get(reverse_key, 100)


@dataclass
class RegionalQuota:
    """Rate limiting quota for a region."""

    region: Region
    max_requests_per_minute: int = 1000
    max_requests_per_hour: int = 50000
    max_bandwidth_mbps: float = 100.0

    # Current usage tracking
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    minute_start: float = field(default_factory=time.time)
    hour_start: float = field(default_factory=time.time)

    def record_request(self):
        """Record a request and update counters."""
        now = time.time()

        # Reset minute counter if needed
        if now - self.minute_start >= 60:
            self.requests_this_minute = 0
            self.minute_start = now

        # Reset hour counter if needed
        if now - self.hour_start >= 3600:
            self.requests_this_hour = 0
            self.hour_start = now

        self.requests_this_minute += 1
        self.requests_this_hour += 1

    @property
    def is_rate_limited(self) -> bool:
        """Check if region is rate limited."""
        return (
            self.requests_this_minute >= self.max_requests_per_minute
            or self.requests_this_hour >= self.max_requests_per_hour
        )

    @property
    def utilization(self) -> float:
        """Get current utilization (0.0 to 1.0)."""
        minute_util = self.requests_this_minute / self.max_requests_per_minute
        hour_util = self.requests_this_hour / self.max_requests_per_hour
        return max(minute_util, hour_util)


@dataclass
class RegionalProxyPool:
    """Proxy pool for a specific geographic region."""

    region: Region
    proxies: List[ProxyEndpoint] = field(default_factory=list)
    quota: RegionalQuota = field(
        default_factory=lambda: RegionalQuota(region=Region.US_EAST)
    )

    # Health metrics
    healthy_count: int = 0
    total_count: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0

    # Request history for analytics
    request_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.quota = RegionalQuota(region=self.region)

    def add_proxy(self, proxy: ProxyEndpoint):
        """Add proxy to pool."""
        proxy.region = self.region.value
        self.proxies.append(proxy)
        self.total_count = len(self.proxies)

    def get_healthy_proxies(self) -> List[ProxyEndpoint]:
        """Get list of healthy proxies."""
        healthy = [p for p in self.proxies if p.status == ProxyStatus.HEALTHY]
        self.healthy_count = len(healthy)
        return healthy

    def get_available_proxies(self) -> List[ProxyEndpoint]:
        """Get healthy proxies that are not rate limited."""
        return [p for p in self.get_healthy_proxies() if not p.is_rate_limited()]

    def update_metrics(self):
        """Update pool metrics."""
        healthy = self.get_healthy_proxies()

        if healthy:
            latencies = [p.response_time_ms for p in healthy if p.response_time_ms > 0]
            if latencies:
                self.avg_latency_ms = statistics.mean(latencies)

            total_success = sum(p.success_count for p in healthy)
            total_failure = sum(p.failure_count for p in healthy)
            total = total_success + total_failure

            if total > 0:
                self.success_rate = total_success / total

    def record_request(self, proxy: ProxyEndpoint, success: bool, latency_ms: float):
        """Record request for analytics."""
        self.quota.record_request()

        record = {
            "timestamp": time.time(),
            "proxy_id": proxy.id,
            "success": success,
            "latency_ms": latency_ms,
        }

        self.request_history.append(record)

        # Keep only last 1000 records
        if len(self.request_history) > 1000:
            self.request_history = self.request_history[-1000:]

    @property
    def is_available(self) -> bool:
        """Check if pool has available capacity."""
        return self.healthy_count > 0 and not self.quota.is_rate_limited

    @property
    def health_score(self) -> float:
        """Calculate overall health score (0.0 to 1.0)."""
        if self.total_count == 0:
            return 0.0

        health_ratio = self.healthy_count / self.total_count
        utilization_penalty = self.quota.utilization * 0.3

        return max(0.0, health_ratio * self.success_rate - utilization_penalty)


class GeoProxyShardManager:
    """
    Geo-sharded proxy pool manager with intelligent routing.

    Features:
    - Geographic distribution of proxy pools
    - Locality-aware selection with latency optimization
    - Automatic failover to nearest available region
    - Per-region rate limiting and quotas
    - Cross-region load balancing
    """

    def __init__(
        self,
        default_region: Region = Region.US_EAST,
        health_check_interval: int = 60,
        failover_threshold: float = 0.3,
    ):
        self.default_region = default_region
        self.health_check_interval = health_check_interval
        self.failover_threshold = failover_threshold

        # Regional pools
        self.pools: Dict[Region, RegionalProxyPool] = {}
        for region in Region:
            self.pools[region] = RegionalProxyPool(region=region)

        # Domain to region affinity
        self.domain_region_affinity: Dict[str, Region] = {}

        # TLS fingerprint randomizer
        self.tls_randomizer = TLSFingerprintRandomizer()

        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

        # Metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failover_count = 0

    def add_proxy_to_region(self, proxy: ProxyEndpoint, region: Region):
        """Add proxy to a specific region's pool."""
        self.pools[region].add_proxy(proxy)
        logger.info(f"Added proxy {proxy.id} to region {region.value}")

    def add_proxies_from_config(self, config: Dict[str, List[Dict[str, Any]]]):
        """
        Add proxies from configuration.

        Config format:
        {
            "us-east-1": [
                {"id": "proxy-1", "host": "...", "port": 8080, ...},
                ...
            ],
            "eu-west-1": [...],
        }
        """
        for region_str, proxies_config in config.items():
            try:
                region = Region(region_str)
            except ValueError:
                logger.warning(f"Unknown region: {region_str}, skipping")
                continue

            for proxy_config in proxies_config:
                proxy = ProxyEndpoint(**proxy_config)
                self.add_proxy_to_region(proxy, region)

    async def start(self):
        """Start the geo-sharded proxy manager."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Geo-sharded proxy manager started")

    async def stop(self):
        """Stop the proxy manager."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Geo-sharded proxy manager stopped")

    async def _health_check_loop(self):
        """Background health check for all regional pools."""
        while self._running:
            try:
                await self._check_all_regions()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(10)

    async def _check_all_regions(self):
        """Check health of all regional pools."""
        tasks = []
        for region, pool in self.pools.items():
            for proxy in pool.proxies:
                tasks.append(self._check_proxy_health(proxy, pool))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Update pool metrics
        for pool in self.pools.values():
            pool.update_metrics()

    async def _check_proxy_health(self, proxy: ProxyEndpoint, pool: RegionalProxyPool):
        """Check health of a single proxy."""
        import aiohttp

        try:
            start_time = time.time()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy.to_url(),
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False,
                ) as response:
                    elapsed_ms = (time.time() - start_time) * 1000
                    proxy.response_time_ms = elapsed_ms

                    if response.status == 200:
                        proxy.success_count += 1
                        proxy.failure_count = 0

                        if proxy.status != ProxyStatus.HEALTHY:
                            proxy.status = ProxyStatus.HEALTHY
                            logger.info(
                                f"Proxy {proxy.id} in {pool.region.value} recovered"
                            )
                    else:
                        proxy.failure_count += 1
                        if proxy.failure_count >= 3:
                            proxy.status = ProxyStatus.UNHEALTHY

        except Exception as e:
            proxy.failure_count += 1
            if proxy.failure_count >= 3:
                proxy.status = ProxyStatus.UNHEALTHY
            logger.debug(f"Proxy {proxy.id} health check failed: {e}")

        proxy.last_check = time.time()

    def get_nearest_regions(self, from_region: Region, count: int = 3) -> List[Region]:
        """Get nearest regions sorted by latency."""
        latencies = []
        for region in Region:
            if region != from_region:
                latency = get_region_latency(from_region, region)
                latencies.append((region, latency))

        latencies.sort(key=lambda x: x[1])
        return [r for r, _ in latencies[:count]]

    def set_domain_affinity(self, domain: str, region: Region):
        """Set preferred region for a domain."""
        self.domain_region_affinity[domain] = region

    def get_domain_region(self, domain: str) -> Optional[Region]:
        """Get preferred region for a domain."""
        return self.domain_region_affinity.get(domain)

    async def select_proxy(
        self,
        target_domain: Optional[str] = None,
        preferred_region: Optional[Region] = None,
        require_healthy: bool = True,
        allow_failover: bool = True,
    ) -> Optional[ProxyEndpoint]:
        """
        Select optimal proxy based on locality and health.

        Args:
            target_domain: Target domain for affinity
            preferred_region: Preferred region (overrides domain affinity)
            require_healthy: Only select healthy proxies
            allow_failover: Allow failover to other regions

        Returns:
            Selected proxy or None
        """
        async with self._lock:
            self.total_requests += 1

            # Determine target region
            target_region = (
                preferred_region or self.get_domain_region(target_domain)
                if target_domain
                else None or self.default_region
            )

            # Try primary region first
            proxy = await self._select_from_region(target_region, require_healthy)

            if proxy:
                return proxy

            # Failover to other regions
            if allow_failover:
                self.failover_count += 1
                logger.warning(
                    f"Primary region {target_region.value} unavailable, failing over"
                )

                # Get regions sorted by proximity
                fallback_regions = self.get_nearest_regions(target_region)

                for fallback_region in fallback_regions:
                    proxy = await self._select_from_region(
                        fallback_region, require_healthy
                    )
                    if proxy:
                        logger.info(f"Failed over to region {fallback_region.value}")
                        return proxy

            logger.error("No proxies available in any region")
            return None

    async def _select_from_region(
        self, region: Region, require_healthy: bool = True
    ) -> Optional[ProxyEndpoint]:
        """Select proxy from a specific region."""
        pool = self.pools.get(region)

        if not pool or not pool.is_available:
            return None

        if pool.health_score < self.failover_threshold:
            logger.warning(
                f"Region {region.value} health score too low: {pool.health_score:.2f}"
            )
            return None

        candidates = pool.get_available_proxies() if require_healthy else pool.proxies

        if not candidates:
            return None

        # Weighted selection based on success rate and latency
        weights = []
        for proxy in candidates:
            weight = 1.0

            # Prefer proxies with better success rates
            success_total = proxy.success_count + proxy.failure_count
            if success_total > 0:
                success_rate = proxy.success_count / success_total
                weight *= 0.5 + success_rate * 0.5

            # Prefer proxies with lower latency
            if proxy.response_time_ms > 0:
                latency_factor = max(0.1, 1.0 - (proxy.response_time_ms / 1000))
                weight *= latency_factor

            weights.append(weight)

        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            proxy = random.choice(candidates)
        else:
            r = random.random() * total_weight
            cumulative = 0
            proxy = candidates[-1]
            for i, w in enumerate(weights):
                cumulative += w
                if r <= cumulative:
                    proxy = candidates[i]
                    break

        proxy.record_request()
        self.successful_requests += 1

        return proxy

    def get_region_stats(self, region: Region) -> Dict[str, Any]:
        """Get statistics for a region."""
        pool = self.pools.get(region)
        if not pool:
            return {}

        return {
            "region": region.value,
            "total_proxies": pool.total_count,
            "healthy_proxies": pool.healthy_count,
            "avg_latency_ms": pool.avg_latency_ms,
            "success_rate": pool.success_rate,
            "health_score": pool.health_score,
            "quota_utilization": pool.quota.utilization,
            "is_available": pool.is_available,
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all regions."""
        regions_stats = {
            region.value: self.get_region_stats(region) for region in Region
        }

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failover_count": self.failover_count,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0.0
            ),
            "regions": regions_stats,
        }

    def get_metrics_prometheus(self) -> str:
        """Get metrics in Prometheus format."""
        lines = []

        # Global metrics
        lines.append(f"# HELP geo_proxy_total_requests Total proxy requests")
        lines.append(f"# TYPE geo_proxy_total_requests counter")
        lines.append(f"geo_proxy_total_requests {self.total_requests}")

        lines.append(f"# HELP geo_proxy_successful_requests Successful proxy requests")
        lines.append(f"# TYPE geo_proxy_successful_requests counter")
        lines.append(f"geo_proxy_successful_requests {self.successful_requests}")

        lines.append(f"# HELP geo_proxy_failover_count Regional failover count")
        lines.append(f"# TYPE geo_proxy_failover_count counter")
        lines.append(f"geo_proxy_failover_count {self.failover_count}")

        # Regional metrics
        lines.append(f"# HELP geo_proxy_pool_health_score Regional pool health score")
        lines.append(f"# TYPE geo_proxy_pool_health_score gauge")

        lines.append(f"# HELP geo_proxy_pool_proxies_total Total proxies in pool")
        lines.append(f"# TYPE geo_proxy_pool_proxies_total gauge")

        lines.append(f"# HELP geo_proxy_pool_proxies_healthy Healthy proxies in pool")
        lines.append(f"# TYPE geo_proxy_pool_proxies_healthy gauge")

        lines.append(f"# HELP geo_proxy_pool_latency_avg Average latency in pool")
        lines.append(f"# TYPE geo_proxy_pool_latency_avg gauge")

        for region, pool in self.pools.items():
            region_label = f'region="{region.value}"'
            lines.append(
                f"geo_proxy_pool_health_score{{{region_label}}} {pool.health_score:.4f}"
            )
            lines.append(
                f"geo_proxy_pool_proxies_total{{{region_label}}} {pool.total_count}"
            )
            lines.append(
                f"geo_proxy_pool_proxies_healthy{{{region_label}}} {pool.healthy_count}"
            )
            lines.append(
                f"geo_proxy_pool_latency_avg{{{region_label}}} {pool.avg_latency_ms:.2f}"
            )

        return "\n".join(lines)


class GeoCrossRegionLoadBalancer:
    """
    Load balancer for distributing traffic across geo-sharded proxy pools.

    Strategies:
    - LOCALITY_FIRST: Prefer local region, failover to nearest
    - ROUND_ROBIN: Distribute evenly across regions
    - LATENCY_BASED: Route to lowest latency region
    - COST_OPTIMIZED: Route to cheapest available region
    """

    class Strategy(Enum):
        LOCALITY_FIRST = "locality_first"
        ROUND_ROBIN = "round_robin"
        LATENCY_BASED = "latency_based"
        COST_OPTIMIZED = "cost_optimized"

    def __init__(
        self,
        shard_manager: GeoProxyShardManager,
        strategy: Strategy = Strategy.LOCALITY_FIRST,
        local_region: Region = Region.US_EAST,
    ):
        self.shard_manager = shard_manager
        self.strategy = strategy
        self.local_region = local_region

        # Round-robin state
        self._region_index = 0

        # Cost per region (arbitrary units)
        self.region_costs = {
            Region.US_EAST: 1.0,
            Region.US_WEST: 1.0,
            Region.EU_WEST: 1.2,
            Region.EU_CENTRAL: 1.2,
            Region.ASIA_PACIFIC: 1.5,
            Region.ASIA_NORTHEAST: 1.5,
        }

    async def select_region(
        self,
        target_domain: Optional[str] = None,
    ) -> Region:
        """Select optimal region based on strategy."""
        available_regions = [
            region
            for region, pool in self.shard_manager.pools.items()
            if pool.is_available
        ]

        if not available_regions:
            return self.local_region

        if self.strategy == self.Strategy.LOCALITY_FIRST:
            return self._select_locality_first(available_regions)

        elif self.strategy == self.Strategy.ROUND_ROBIN:
            return self._select_round_robin(available_regions)

        elif self.strategy == self.Strategy.LATENCY_BASED:
            return self._select_latency_based(available_regions)

        elif self.strategy == self.Strategy.COST_OPTIMIZED:
            return self._select_cost_optimized(available_regions)

        return self.local_region

    def _select_locality_first(self, available: List[Region]) -> Region:
        """Select local region first, then nearest."""
        if self.local_region in available:
            return self.local_region

        # Get nearest available region
        nearest = self.shard_manager.get_nearest_regions(self.local_region)
        for region in nearest:
            if region in available:
                return region

        return available[0]

    def _select_round_robin(self, available: List[Region]) -> Region:
        """Select regions in round-robin fashion."""
        self._region_index = (self._region_index + 1) % len(available)
        return available[self._region_index]

    def _select_latency_based(self, available: List[Region]) -> Region:
        """Select region with lowest average latency."""
        best_region = available[0]
        best_latency = float("inf")

        for region in available:
            pool = self.shard_manager.pools[region]
            if pool.avg_latency_ms > 0 and pool.avg_latency_ms < best_latency:
                best_latency = pool.avg_latency_ms
                best_region = region

        return best_region

    def _select_cost_optimized(self, available: List[Region]) -> Region:
        """Select cheapest available region with good health."""
        candidates = [
            (region, self.region_costs.get(region, 1.0))
            for region in available
            if self.shard_manager.pools[region].health_score > 0.5
        ]

        if not candidates:
            return available[0]

        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    async def get_proxy(
        self,
        target_domain: Optional[str] = None,
    ) -> Optional[ProxyEndpoint]:
        """Get proxy using the load balancing strategy."""
        region = await self.select_region(target_domain)

        return await self.shard_manager.select_proxy(
            target_domain=target_domain,
            preferred_region=region,
            allow_failover=True,
        )


# Factory function for easy creation
def create_geo_proxy_manager(
    config: Dict[str, Any],
    default_region: str = "us-east-1",
) -> GeoProxyShardManager:
    """
    Create geo-sharded proxy manager from configuration.

    Args:
        config: Configuration dictionary with regional proxy configs
        default_region: Default region string

    Returns:
        Configured GeoProxyShardManager
    """
    try:
        region = Region(default_region)
    except ValueError:
        region = Region.US_EAST

    manager = GeoProxyShardManager(default_region=region)

    if "regions" in config:
        manager.add_proxies_from_config(config["regions"])

    if "domain_affinity" in config:
        for domain, region_str in config["domain_affinity"].items():
            try:
                manager.set_domain_affinity(domain, Region(region_str))
            except ValueError:
                logger.warning(f"Unknown region for domain {domain}: {region_str}")

    return manager
