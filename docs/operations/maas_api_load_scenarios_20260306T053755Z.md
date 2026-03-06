# MaaS API Load Scenarios

- **Started (UTC):** 2026-03-06T05:37:55Z
- **Collected (UTC):** 2026-03-06T05:42:14Z
- **Base URL:** http://127.0.0.1:38080
- **Duration:** 180s
- **Concurrency:** 12
- **Request timeout:** 5.00s
- **Scenarios:** `marketplace_search, telemetry_heartbeat, node_heartbeat`
- **Mesh ID:** mesh-load-profile
- **Node ID:** node-001
- **Overall:** FAIL

## Totals

- Requests total: `432`
- Requests ok: `5`
- Requests error: `427`
- Error rate: `98.843%` (threshold <= `2.000%`)
- Throughput: `2.40 req/s`

## Scenario Metrics

### `marketplace_search`

- Requests total: `144`
- Requests ok: `4`
- Requests error: `140`
- Error rate: `97.222%`
- Latency mean: `5004.98 ms`
- Latency p95: `5025.30 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.80 req/s`
- Errors by reason: `{'timeout': 140}`

### `telemetry_heartbeat`

- Requests total: `144`
- Requests ok: `0`
- Requests error: `144`
- Error rate: `100.000%`
- Latency mean: `5027.26 ms`
- Latency p95: `5026.28 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.80 req/s`
- Errors by reason: `{'timeout': 144}`

### `node_heartbeat`

- Requests total: `144`
- Requests ok: `1`
- Requests error: `143`
- Error rate: `99.306%`
- Latency mean: `5020.75 ms`
- Latency p95: `5028.89 ms` (threshold <= `1200.00 ms`)
- Throughput: `0.80 req/s`
- Errors by reason: `{'timeout': 143}`

## Gate Checks

- overall_error_rate_ok: `FAIL`
- marketplace_search_p95_ok: `FAIL`
- marketplace_search_has_success: `PASS`
- telemetry_heartbeat_p95_ok: `FAIL`
- telemetry_heartbeat_has_success: `FAIL`
- node_heartbeat_p95_ok: `FAIL`
- node_heartbeat_has_success: `PASS`
