import pytest

from src.network.resilience.make_never_break import (
    MakeNeverBreakEngine,
    PathMetrics,
    PathState,
)


@pytest.mark.asyncio
async def test_probe_path_uses_sync_backend_metrics():
    engine = MakeNeverBreakEngine(
        probe_backend=lambda _path: {
            "latency_ms": 12.5,
            "jitter_ms": 1.5,
            "packet_loss": 0.02,
            "bandwidth_mbps": 80.0,
        }
    )
    path = engine.create_path("node-a", "node-b", ["node-a", "node-b"])

    await engine._probe_path(path)

    assert engine.get_stats()["probes_sent"] == 1
    assert path.metrics.latency_ms == 12.5
    assert path.metrics.jitter_ms == 1.5
    assert path.metrics.packet_loss == 0.02
    assert path.metrics.bandwidth_mbps == 80.0
    assert path.metrics.last_probe is not None


@pytest.mark.asyncio
async def test_probe_path_uses_async_backend_path_metrics():
    async def probe_backend(_path):
        return PathMetrics(
            latency_ms=20.0,
            jitter_ms=3.0,
            packet_loss=0.01,
            bandwidth_mbps=50.0,
        )

    engine = MakeNeverBreakEngine(probe_backend=probe_backend)
    path = engine.create_path("node-a", "node-b", ["node-a", "node-b"])

    await engine._probe_path(path)

    assert path.metrics.latency_ms == 20.0
    assert path.metrics.jitter_ms == 3.0
    assert path.metrics.packet_loss == 0.01
    assert path.metrics.bandwidth_mbps == 50.0


@pytest.mark.asyncio
async def test_probe_path_without_backend_keeps_existing_metrics():
    engine = MakeNeverBreakEngine()
    path = engine.create_path("node-a", "node-b", ["node-a", "node-b"])
    path.metrics.latency_ms = 77.0
    path.metrics.jitter_ms = 4.0
    path.metrics.packet_loss = 0.03

    await engine._probe_path(path)

    assert path.metrics.latency_ms == 77.0
    assert path.metrics.jitter_ms == 4.0
    assert path.metrics.packet_loss == 0.03
    assert path.metrics.last_probe is not None


@pytest.mark.asyncio
async def test_probe_backend_failure_degrades_active_path():
    def probe_backend(_path):
        raise RuntimeError("probe failed")

    engine = MakeNeverBreakEngine(probe_backend=probe_backend)
    path = engine.create_path("node-a", "node-b", ["node-a", "node-b"])
    path.state = PathState.ACTIVE

    await engine._probe_path(path)

    assert path.state == PathState.DEGRADED
    assert path.metrics.failure_count == 1
    assert path.metrics.last_failure is not None


def test_normalize_probe_result_clamps_metric_ranges():
    engine = MakeNeverBreakEngine()
    path = engine.create_path("node-a", "node-b", ["node-a", "node-b"])

    metrics = engine._normalize_probe_result(
        path,
        {
            "latency_ms": -1,
            "jitter_ms": -2,
            "packet_loss": 2,
            "bandwidth_mbps": -3,
        },
    )

    assert metrics == {
        "latency_ms": 0.0,
        "jitter_ms": 0.0,
        "packet_loss": 1.0,
        "bandwidth_mbps": 0.0,
    }
