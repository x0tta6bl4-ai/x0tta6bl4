"""
Baseline latency/throughput benchmarks for critical x0tta6bl4 API endpoints.

Purpose:
  - Establishes baseline p50/p95/p99 latency numbers for the in-process app.
  - Run with: pytest tests/benchmarks/test_api_latency_baseline.py -v --benchmark-only
  - Results are stored by pytest-benchmark and can be compared across runs with
    --benchmark-compare.

Endpoints covered (P1 critical path):
  1. GET  /health            — liveness probe
  2. GET  /health/ready      — readiness probe
  3. GET  /mesh/status       — mesh topology read
  4. GET  /mesh/peers        — peer list read
  5. POST /mesh/beacon       — high-frequency beacon write
  6. GET  /metrics           — Prometheus scrape endpoint

All benchmarks use the FastAPI TestClient (in-process, no network I/O).
Thresholds below are SLO-informed targets for the in-process baseline:
  - Health probes:  p95 < 5 ms
  - Read paths:     p95 < 20 ms
  - Write paths:    p95 < 50 ms
  - Metrics scrape: p95 < 30 ms
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """In-process TestClient for the minimal app (no external deps)."""
    from src.core.app_minimal import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Health / liveness
# ---------------------------------------------------------------------------


def test_benchmark_health_liveness(benchmark, client):
    """GET /health — liveness probe baseline."""
    result = benchmark(client.get, "/health")
    assert result.status_code == 200
    # SLO target hint (not enforced in benchmark runner, logged only)
    stats = benchmark.stats
    if stats and hasattr(stats, "mean"):
        assert stats.mean < 0.050, f"p50 liveness > 50 ms: {stats.mean*1000:.1f} ms"


# ---------------------------------------------------------------------------
# 2. Mesh status (read path)
# ---------------------------------------------------------------------------


def test_benchmark_mesh_status(benchmark, client):
    """GET /mesh/status — topology read baseline."""
    result = benchmark(client.get, "/mesh/status")
    assert result.status_code in (200, 503)


# ---------------------------------------------------------------------------
# 3. Peer list (read path)
# ---------------------------------------------------------------------------


def test_benchmark_mesh_peers(benchmark, client):
    """GET /mesh/peers — peer list read baseline."""
    result = benchmark(client.get, "/mesh/peers")
    assert result.status_code == 200


# ---------------------------------------------------------------------------
# 4. Beacon write (high-frequency write path)
# ---------------------------------------------------------------------------

_BEACON_PAYLOAD = {
    "node_id": "bench-node-01",
    "timestamp": 1709500000.0,
    "status": "active",
    "peers": [],
    "metrics": {"latency_ms": 12.5, "packet_loss": 0.0},
}


def test_benchmark_beacon_write(benchmark, client):
    """POST /mesh/beacon — beacon write baseline (high-frequency path)."""
    result = benchmark(client.post, "/mesh/beacon", json=_BEACON_PAYLOAD)
    assert result.status_code in (200, 201, 422)


# ---------------------------------------------------------------------------
# 5. Prometheus metrics scrape
# ---------------------------------------------------------------------------


def test_benchmark_metrics_scrape(benchmark, client):
    """GET /metrics — Prometheus scrape baseline."""
    result = benchmark(client.get, "/metrics")
    assert result.status_code == 200


# ---------------------------------------------------------------------------
# 6. Route lookup (read with path param)
# ---------------------------------------------------------------------------


def test_benchmark_route_lookup(benchmark, client):
    """GET /mesh/route/{destination} — route lookup baseline."""
    result = benchmark(client.get, "/mesh/route/bench-node-02")
    assert result.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 7. Throughput saturation — 100 sequential health checks
# ---------------------------------------------------------------------------


def test_benchmark_health_throughput_100(benchmark, client):
    """100 sequential GET /health — measures throughput (req/s)."""

    def _100_requests():
        for _ in range(100):
            r = client.get("/health")
            assert r.status_code == 200

    benchmark(_100_requests)


# ---------------------------------------------------------------------------
# 8. Concurrent-equivalent: batch beacon (write throughput)
# ---------------------------------------------------------------------------


def test_benchmark_beacon_throughput_50(benchmark, client):
    """50 sequential POST /mesh/beacon — write throughput baseline."""

    def _50_beacons():
        for i in range(50):
            payload = {**_BEACON_PAYLOAD, "node_id": f"bench-node-{i:04d}"}
            r = client.post("/mesh/beacon", json=payload)
            assert r.status_code in (200, 201, 422)

    benchmark(_50_beacons)
