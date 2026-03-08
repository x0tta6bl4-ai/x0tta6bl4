# API Latency Baseline — x0tta6bl4

**Captured:** 2026-03-04 (in-process TestClient, no network I/O)
**Branch:** develop
**Python:** 3.12

These numbers are the **in-process baseline** (FastAPI routing + business logic only,
no real DB or Redis). Production numbers will be higher due to network and DB overhead.

## Critical Endpoint Baselines

| Endpoint | Median µs | Mean µs | OPS (in-proc) | SLO target p95 |
|---|---:|---:|---:|---|
| GET /health (liveness) | 1,045 | 1,424 | 702/s | < 5 ms |
| GET /mesh/peers | 1,211 | 1,266 | 790/s | < 20 ms |
| GET /mesh/route/{id} | 1,089 | 1,300 | 769/s | < 20 ms |
| GET /mesh/status | 1,284 | 1,490 | 671/s | < 20 ms |
| GET /metrics (Prometheus) | 1,403 | 1,770 | 565/s | < 30 ms |
| POST /mesh/beacon | 1,140 | 1,141 | 876/s | < 50 ms |

## Throughput Baselines (sequential)

| Scenario | Median batch µs | Effective req/s |
|---|---:|---:|
| 100× GET /health | 150,845 | ~663 |
| 50× POST /mesh/beacon | 64,473 | ~775 |

## SLO Targets (production, real DB + Redis)

| Tier | p50 | p95 | p99 |
|---|---|---|---|
| Health probes | < 2 ms | < 5 ms | < 10 ms |
| Read endpoints | < 10 ms | < 50 ms | < 100 ms |
| Write endpoints | < 20 ms | < 100 ms | < 200 ms |
| Metrics scrape | < 10 ms | < 30 ms | < 60 ms |

## How to re-run

```bash
pytest tests/benchmarks/test_api_latency_baseline.py \
  -v --benchmark-only --benchmark-min-rounds=5 \
  --benchmark-json=reports/benchmark_baseline.json
```

To compare against a saved baseline:

```bash
pytest tests/benchmarks/ --benchmark-compare=reports/benchmark_baseline.json
```

## Interpretation notes

- In-process numbers are **floor** values: add ~5–20 ms for DB calls, ~1–5 ms for Redis.
- High StdDev on health tests is due to cold-start jitter in first rounds. Median is
  the reliable signal.
- 100× sequential health test is single-threaded; production Gunicorn/uvicorn workers
  handle concurrent requests and should achieve higher aggregate throughput.
