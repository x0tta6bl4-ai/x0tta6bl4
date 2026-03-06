# API Long-Run Memory Profile

- **Started (UTC):** 2026-03-06T04:58:25Z
- **Collected (UTC):** 2026-03-06T05:01:32Z
- **Mode:** light
- **Duration:** 180s
- **Concurrency:** 8
- **Base URL:** http://127.0.0.1:8000
- **Overall:** FAIL

## Workload

- Endpoints: `/health/ready, /health, /metrics, /api/v1/maas/plans`
- Requests total: `2241`
- Throughput: `12.45 req/s`
- Error rate: `0.000%` (threshold <= `1.000%`)
- Latency mean: `643.46 ms`
- Latency p95: `1477.76 ms` (threshold <= `1000.00 ms`)

## Memory

- RSS start: `156.06 MiB`
- RSS end: `162.37 MiB`
- RSS peak: `162.37 MiB`
- RSS growth: `6.30 MiB` (threshold <= `200.00 MiB`)
- Samples: `180`

## Gate Checks

- memory_growth_ok: `PASS`
- error_rate_ok: `PASS`
- latency_p95_ok: `FAIL`
