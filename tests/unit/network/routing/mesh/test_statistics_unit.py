"""Unit tests for src.network.routing.mesh.statistics."""

from __future__ import annotations

import pytest

models_mod = pytest.importorskip("src.network.routing.mesh.models")
statistics_mod = pytest.importorskip("src.network.routing.mesh.statistics")
RouteEntry = models_mod.RouteEntry
RouterStatistics = statistics_mod.RouterStatistics


@pytest.mark.asyncio
async def test_increment_get_stats_and_unknown_counter():
    stats = RouterStatistics()

    await stats.increment("packets_sent", 3)
    await stats.increment("packets_received")
    await stats.increment("unknown_counter", 99)

    current = await stats.get_stats()
    assert current["packets_sent"] == 3
    assert current["packets_received"] == 1
    assert current["packets_dropped"] == 0


@pytest.mark.asyncio
async def test_get_mape_k_metrics_zero_denominators():
    stats = RouterStatistics()
    metrics = await stats.get_mape_k_metrics(lambda: {})

    assert metrics["packet_drop_rate"] == 0.0
    assert metrics["route_discovery_success_rate"] == 0.0
    assert metrics["total_routes_known"] == 0.0
    assert metrics["avg_route_hop_count"] == 0.0
    assert metrics["routing_overhead_ratio"] == 0.0


@pytest.mark.asyncio
async def test_get_mape_k_metrics_with_routes_and_counters():
    stats = RouterStatistics()

    await stats.increment("packets_sent", 10)
    await stats.increment("packets_received", 5)
    await stats.increment("packets_forwarded", 5)
    await stats.increment("packets_dropped", 2)
    await stats.increment("rreq_sent", 4)
    await stats.increment("rreq_received", 2)
    await stats.increment("rrep_sent", 1)
    await stats.increment("rrep_received", 1)
    await stats.increment("routes_discovered", 3)

    def _routes():
        return {
            "dest-a": [
                RouteEntry("dest-a", "n1", 2, 1),
                RouteEntry("dest-a", "n2", 4, 1),
            ],
            "dest-b": [RouteEntry("dest-b", "n3", 1, 1)],
        }

    metrics = await stats.get_mape_k_metrics(_routes)
    assert metrics["packet_drop_rate"] == pytest.approx(2 / 28)
    assert metrics["route_discovery_success_rate"] == pytest.approx(3 / 4)
    assert metrics["total_routes_known"] == 2.0
    assert metrics["avg_route_hop_count"] == pytest.approx((2 + 4 + 1) / 3)
    assert metrics["routing_overhead_ratio"] == pytest.approx(8 / 15)


@pytest.mark.asyncio
async def test_reset_clears_all_counters():
    stats = RouterStatistics()
    await stats.increment("packets_sent", 2)
    await stats.increment("routes_discovered", 1)

    await stats.reset()
    current = await stats.get_stats()
    assert all(value == 0 for value in current.values())
