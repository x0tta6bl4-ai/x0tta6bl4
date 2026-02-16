import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

import libx0t.network.geo_proxy_sharding as mod
from libx0t.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def _make_proxy(
    proxy_id: str,
    *,
    status: ProxyStatus = ProxyStatus.HEALTHY,
    region: str = "us-east-1",
    response_time_ms: float = 100.0,
    success_count: int = 1,
    failure_count: int = 0,
) -> ProxyEndpoint:
    proxy = ProxyEndpoint(
        id=proxy_id,
        host="127.0.0.1",
        port=8080,
        region=region,
        status=status,
    )
    proxy.response_time_ms = response_time_ms
    proxy.success_count = success_count
    proxy.failure_count = failure_count
    return proxy


def test_region_latency_lookup_paths():
    assert mod.get_region_latency(mod.Region.US_EAST, mod.Region.US_EAST) == 0
    assert mod.get_region_latency(mod.Region.US_EAST, mod.Region.US_WEST) == 70
    assert mod.get_region_latency(mod.Region.US_WEST, mod.Region.US_EAST) == 70

    missing = mod.INTER_REGION_LATENCY.pop(
        (mod.Region.US_EAST, mod.Region.ASIA_NORTHEAST), None
    )
    try:
        assert (
            mod.get_region_latency(mod.Region.US_EAST, mod.Region.ASIA_NORTHEAST) == 100
        )
    finally:
        if missing is not None:
            mod.INTER_REGION_LATENCY[(mod.Region.US_EAST, mod.Region.ASIA_NORTHEAST)] = (
                missing
            )


def test_regional_quota_record_reset_and_limits(monkeypatch):
    quota = mod.RegionalQuota(
        region=mod.Region.US_EAST,
        max_requests_per_minute=2,
        max_requests_per_hour=3,
    )
    quota.minute_start = 0.0
    quota.hour_start = 0.0

    monkeypatch.setattr(mod.time, "time", lambda: 7200.0)
    quota.record_request()
    assert quota.requests_this_minute == 1
    assert quota.requests_this_hour == 1
    assert quota.is_rate_limited is False

    quota.requests_this_minute = 2
    assert quota.is_rate_limited is True
    quota.requests_this_minute = 1
    quota.requests_this_hour = 3
    assert quota.is_rate_limited is True

    quota.requests_this_minute = 1
    quota.requests_this_hour = 1
    util = quota.utilization
    assert 0 < util <= 1.0


def test_regional_proxy_pool_metrics_and_history():
    pool = mod.RegionalProxyPool(region=mod.Region.US_EAST)
    healthy = _make_proxy("healthy", status=ProxyStatus.HEALTHY, response_time_ms=50.0)
    healthy.success_count = 4
    healthy.failure_count = 1
    unhealthy = _make_proxy("bad", status=ProxyStatus.UNHEALTHY)

    pool.add_proxy(healthy)
    pool.add_proxy(unhealthy)
    assert pool.total_count == 2
    assert healthy.region == mod.Region.US_EAST.value

    healthy_list = pool.get_healthy_proxies()
    assert [p.id for p in healthy_list] == ["healthy"]

    healthy.is_rate_limited = lambda: False
    available = pool.get_available_proxies()
    assert [p.id for p in available] == ["healthy"]

    pool.update_metrics()
    assert pool.avg_latency_ms == 50.0
    assert pool.success_rate == pytest.approx(4 / 5)

    pool.request_history = [{}] * 1001
    pool.record_request(healthy, success=True, latency_ms=12.3)
    assert len(pool.request_history) == 1000
    assert pool.request_history[-1]["proxy_id"] == "healthy"

    assert pool.is_available is True
    assert pool.health_score > 0

    empty_pool = mod.RegionalProxyPool(region=mod.Region.US_WEST)
    assert empty_pool.health_score == 0.0


def test_manager_config_region_affinity_stats_and_metrics():
    manager = mod.GeoProxyShardManager(default_region=mod.Region.EU_WEST)

    p1 = _make_proxy("p1")
    manager.add_proxy_to_region(p1, mod.Region.US_EAST)
    assert manager.pools[mod.Region.US_EAST].total_count == 1

    manager.add_proxies_from_config(
        {
            "us-west-2": [{"id": "p2", "host": "10.0.0.2", "port": 8081}],
            "invalid-region": [{"id": "x", "host": "10.0.0.9", "port": 9999}],
        }
    )
    assert manager.pools[mod.Region.US_WEST].total_count == 1

    manager.set_domain_affinity("example.com", mod.Region.US_WEST)
    assert manager.get_domain_region("example.com") == mod.Region.US_WEST
    assert manager.get_domain_region("missing.com") is None

    stats = manager.get_region_stats(mod.Region.US_EAST)
    assert stats["region"] == mod.Region.US_EAST.value
    assert manager.get_region_stats(None) == {}

    manager.total_requests = 4
    manager.successful_requests = 3
    manager.failover_count = 1
    all_stats = manager.get_all_stats()
    assert all_stats["success_rate"] == pytest.approx(0.75)
    assert "us-east-1" in all_stats["regions"]

    prom = manager.get_metrics_prometheus()
    assert "geo_proxy_total_requests 4" in prom
    assert "geo_proxy_failover_count 1" in prom


@pytest.mark.asyncio
async def test_manager_start_stop_and_health_loop_paths(monkeypatch):
    manager = mod.GeoProxyShardManager()

    async def _sleepy_loop():
        try:
            await asyncio.sleep(1000)
        except asyncio.CancelledError:
            raise

    manager._health_check_loop = _sleepy_loop
    await manager.start()
    assert manager._running is True
    assert manager._health_check_task is not None
    await manager.stop()
    assert manager._running is False

    manager2 = mod.GeoProxyShardManager()
    manager2._running = True

    async def _raise_cancel():
        raise asyncio.CancelledError()

    manager2._check_all_regions = _raise_cancel
    await manager2._health_check_loop()

    manager3 = mod.GeoProxyShardManager()
    manager3._running = True
    state = {"calls": 0}

    async def _raise_error():
        state["calls"] += 1
        raise RuntimeError("boom")

    async def _fake_sleep(_seconds):
        manager3._running = False

    manager3._check_all_regions = _raise_error
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)
    await manager3._health_check_loop()
    assert state["calls"] == 1


@pytest.mark.asyncio
async def test_check_all_regions_runs_health_and_updates_metrics(monkeypatch):
    manager = mod.GeoProxyShardManager()
    p1 = _make_proxy("p1")
    p2 = _make_proxy("p2")
    manager.add_proxy_to_region(p1, mod.Region.US_EAST)
    manager.add_proxy_to_region(p2, mod.Region.US_WEST)

    checked = []

    async def _fake_check(proxy, pool):
        checked.append((proxy.id, pool.region.value))

    manager._check_proxy_health = _fake_check

    updates = {"count": 0}
    for pool in manager.pools.values():
        original = pool.update_metrics

        def _wrapped_update(orig=original):
            updates["count"] += 1
            return orig()

        pool.update_metrics = _wrapped_update

    await manager._check_all_regions()
    assert ("p1", mod.Region.US_EAST.value) in checked
    assert ("p2", mod.Region.US_WEST.value) in checked
    assert updates["count"] == len(manager.pools)


class _FakeResponseContext:
    def __init__(self, status: int):
        self._status = status

    async def __aenter__(self):
        return SimpleNamespace(status=self._status)

    async def __aexit__(self, *_args):
        return False


class _FakeSession:
    def __init__(self, status: int):
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def get(self, *_args, **_kwargs):
        return _FakeResponseContext(self._status)


class _FailingSession:
    async def __aenter__(self):
        raise RuntimeError("session failed")

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_check_proxy_health_success_non_200_and_exception(monkeypatch):
    manager = mod.GeoProxyShardManager()
    pool = manager.pools[mod.Region.US_EAST]
    proxy = _make_proxy("p1", status=ProxyStatus.DEGRADED)

    fake_aiohttp_success = SimpleNamespace(
        ClientSession=lambda: _FakeSession(200),
        ClientTimeout=lambda total: SimpleNamespace(total=total),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp_success)
    await manager._check_proxy_health(proxy, pool)
    assert proxy.status == ProxyStatus.HEALTHY
    assert proxy.success_count == 2
    assert proxy.failure_count == 0
    assert proxy.last_check > 0

    proxy2 = _make_proxy("p2", status=ProxyStatus.HEALTHY)
    proxy2.failure_count = 2
    fake_aiohttp_fail = SimpleNamespace(
        ClientSession=lambda: _FakeSession(500),
        ClientTimeout=lambda total: SimpleNamespace(total=total),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp_fail)
    await manager._check_proxy_health(proxy2, pool)
    assert proxy2.failure_count == 3
    assert proxy2.status == ProxyStatus.UNHEALTHY

    proxy3 = _make_proxy("p3", status=ProxyStatus.HEALTHY)
    proxy3.failure_count = 2
    fake_aiohttp_exception = SimpleNamespace(
        ClientSession=lambda: _FailingSession(),
        ClientTimeout=lambda total: SimpleNamespace(total=total),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp_exception)
    await manager._check_proxy_health(proxy3, pool)
    assert proxy3.failure_count == 3
    assert proxy3.status == ProxyStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_select_proxy_primary_failover_and_no_failover(monkeypatch):
    manager = mod.GeoProxyShardManager(default_region=mod.Region.US_EAST)
    selected = _make_proxy("picked")

    async def _fake_select(region, _require_healthy):
        if region == mod.Region.US_EAST:
            return None
        if region == mod.Region.US_WEST:
            return selected
        return None

    manager._select_from_region = _fake_select
    monkeypatch.setattr(
        manager,
        "get_nearest_regions",
        lambda _from_region, count=3: [mod.Region.US_WEST, mod.Region.EU_WEST],
    )
    manager.set_domain_affinity("x.com", mod.Region.US_EAST)
    proxy = await manager.select_proxy(target_domain="x.com", allow_failover=True)
    assert proxy is selected
    assert manager.failover_count == 1
    assert manager.total_requests == 1

    none_proxy = await manager.select_proxy(
        preferred_region=mod.Region.US_EAST,
        allow_failover=False,
    )
    assert none_proxy is None
    assert manager.failover_count == 1


@pytest.mark.asyncio
async def test_select_from_region_paths(monkeypatch):
    manager = mod.GeoProxyShardManager(default_region=mod.Region.US_EAST)
    pool = manager.pools[mod.Region.US_EAST]

    unavailable = await manager._select_from_region(mod.Region.US_EAST)
    assert unavailable is None

    p1 = _make_proxy("p1", status=ProxyStatus.HEALTHY, response_time_ms=100, success_count=5)
    p2 = _make_proxy("p2", status=ProxyStatus.HEALTHY, response_time_ms=200, success_count=1)
    pool.add_proxy(p1)
    pool.add_proxy(p2)
    pool.healthy_count = 2
    pool.total_count = 2
    pool.success_rate = 0.1
    manager.failover_threshold = 0.5

    low_health = await manager._select_from_region(mod.Region.US_EAST)
    assert low_health is None

    manager.failover_threshold = 0.0
    pool.success_rate = 1.0
    p1.is_rate_limited = lambda: False
    p2.is_rate_limited = lambda: False
    monkeypatch.setattr(mod.random, "random", lambda: 0.0)
    picked = await manager._select_from_region(mod.Region.US_EAST)
    assert picked is p1
    assert manager.successful_requests == 1
    assert len(p1.request_times) == 1

    p1.is_rate_limited = lambda: True
    p2.is_rate_limited = lambda: True
    none_again = await manager._select_from_region(mod.Region.US_EAST, require_healthy=True)
    assert none_again is None

    picked_any = await manager._select_from_region(mod.Region.US_EAST, require_healthy=False)
    assert picked_any is p1 or picked_any is p2


@pytest.mark.asyncio
async def test_load_balancer_strategy_selection_and_get_proxy(monkeypatch):
    manager = mod.GeoProxyShardManager(default_region=mod.Region.US_EAST)
    for region in mod.Region:
        pool = manager.pools[region]
        pool.total_count = 1
        pool.healthy_count = 1
        pool.success_rate = 1.0

    lb = mod.GeoCrossRegionLoadBalancer(
        manager,
        strategy=mod.GeoCrossRegionLoadBalancer.Strategy.LOCALITY_FIRST,
        local_region=mod.Region.US_EAST,
    )
    assert await lb.select_region() == mod.Region.US_EAST

    manager.pools[mod.Region.US_EAST].healthy_count = 0
    monkeypatch.setattr(
        manager,
        "get_nearest_regions",
        lambda _from_region: [mod.Region.EU_WEST, mod.Region.US_WEST],
    )
    assert await lb.select_region() == mod.Region.EU_WEST

    lb.strategy = mod.GeoCrossRegionLoadBalancer.Strategy.ROUND_ROBIN
    available = [mod.Region.US_WEST, mod.Region.EU_WEST]
    assert lb._select_round_robin(available) == mod.Region.EU_WEST
    assert lb._select_round_robin(available) == mod.Region.US_WEST

    lb.strategy = mod.GeoCrossRegionLoadBalancer.Strategy.LATENCY_BASED
    manager.pools[mod.Region.US_WEST].avg_latency_ms = 80
    manager.pools[mod.Region.EU_WEST].avg_latency_ms = 30
    assert await lb.select_region() == mod.Region.EU_WEST

    lb.strategy = mod.GeoCrossRegionLoadBalancer.Strategy.COST_OPTIMIZED
    manager.pools[mod.Region.US_WEST].success_rate = 0.4
    manager.pools[mod.Region.EU_WEST].success_rate = 1.0
    assert await lb.select_region() == mod.Region.EU_WEST

    manager.pools[mod.Region.EU_WEST].success_rate = 0.4
    fallback = lb._select_cost_optimized([mod.Region.US_WEST, mod.Region.EU_WEST])
    assert fallback == mod.Region.US_WEST

    chosen = _make_proxy("chosen")

    async def _fake_select_proxy(**kwargs):
        assert kwargs["preferred_region"] == mod.Region.US_WEST
        return chosen

    async def _fake_select_region(_target_domain=None):
        return mod.Region.US_WEST

    monkeypatch.setattr(manager, "select_proxy", _fake_select_proxy)
    monkeypatch.setattr(lb, "select_region", _fake_select_region)
    assert await lb.get_proxy("example.com") is chosen


def test_create_geo_proxy_manager_factory_paths():
    manager = mod.create_geo_proxy_manager(
        config={
            "regions": {
                "us-east-1": [{"id": "p1", "host": "1.1.1.1", "port": 8080}],
            },
            "domain_affinity": {
                "ok.com": "eu-west-1",
                "bad.com": "invalid-region",
            },
        },
        default_region="invalid-default",
    )
    assert manager.default_region == mod.Region.US_EAST
    assert manager.pools[mod.Region.US_EAST].total_count == 1
    assert manager.get_domain_region("ok.com") == mod.Region.EU_WEST
    assert manager.get_domain_region("bad.com") is None
