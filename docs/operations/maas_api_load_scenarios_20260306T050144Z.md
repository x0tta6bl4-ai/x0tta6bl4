# MaaS API Load Scenarios

- **Started (UTC):** 2026-03-06T05:01:44Z
- **Collected (UTC):** 2026-03-06T05:05:29Z
- **Base URL:** http://127.0.0.1:38080
- **Duration:** 180s
- **Concurrency:** 12
- **Mesh ID:** mesh-load-profile
- **Node ID:** node-001
- **Overall:** FAIL

## Totals

- Requests total: `490`
- Requests ok: `163`
- Requests error: `327`
- Error rate: `66.735%` (threshold <= `2.000%`)
- Throughput: `2.72 req/s`

## Scenario Metrics

### `marketplace_search`

- Requests total: `164`
- Requests ok: `108`
- Requests error: `56`
- Error rate: `34.146%`
- Latency mean: `3940.85 ms`
- Latency p95: `5019.43 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.91 req/s`

### `telemetry_heartbeat`

- Requests total: `161`
- Requests ok: `0`
- Requests error: `161`
- Error rate: `100.000%`
- Latency mean: `4789.68 ms`
- Latency p95: `5026.92 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.89 req/s`

### `node_heartbeat`

- Requests total: `165`
- Requests ok: `55`
- Requests error: `110`
- Error rate: `66.667%`
- Latency mean: `4602.98 ms`
- Latency p95: `5013.35 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.92 req/s`

## Gate Checks

- overall_error_rate_ok: `FAIL`
- marketplace_search_p95_ok: `FAIL`
- marketplace_search_has_success: `PASS`
- telemetry_heartbeat_p95_ok: `FAIL`
- telemetry_heartbeat_has_success: `FAIL`
- node_heartbeat_p95_ok: `FAIL`
- node_heartbeat_has_success: `PASS`
