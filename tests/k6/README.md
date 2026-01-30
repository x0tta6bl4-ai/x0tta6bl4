# k6 Load Testing Suite

Performance and load tests for x0tta6bl4 API using [k6](https://k6.io/).

## Test Files

| File | Purpose | Duration | VUs |
|------|---------|----------|-----|
| `01-beacon-load.js` | Mesh beacon heartbeat testing | ~1 min | 10-50 |
| `02-graphsage-load.js` | GraphSAGE ML inference testing | ~1 min | 10-30 |
| `03-dao-voting-load.js` | DAO governance voting testing | ~1 min | 10-50 |
| `04-api-load.js` | API endpoint load testing | ~1 min | 10-100 |
| `05-stress-test.js` | Stress test (find breaking point) | ~15 min | 10-1000 |
| `06-smoke-test.js` | Smoke test (CI/CD sanity check) | ~30 sec | 1 |

## Running Tests

### Prerequisites

```bash
# Install k6 on macOS
brew install k6

# Install k6 on Ubuntu/Debian
sudo apt-get install k6

# Or via Docker
docker pull grafana/k6
```

### Quick Start

```bash
# Run smoke test (fast sanity check)
k6 run tests/k6/06-smoke-test.js

# Run API load test
k6 run tests/k6/04-api-load.js

# Run with custom API URL
k6 run -e API_URL=http://staging.x0tta6bl4.com tests/k6/04-api-load.js
```

### Run with Docker

```bash
docker run --rm -i grafana/k6 run - < tests/k6/06-smoke-test.js
```

### Stress Testing

```bash
# Full stress test (15 minutes)
k6 run tests/k6/05-stress-test.js

# Stress test with custom environment
k6 run \
  -e API_URL=http://staging:8080 \
  -e ADMIN_TOKEN=secret \
  --out json=results.json \
  tests/k6/05-stress-test.js
```

## Performance Targets

### Health Endpoint (`/health`)
- P95 < 50ms
- P99 < 100ms
- RPS: 1000+

### VPN Status (`/vpn/status`)
- P95 < 200ms (cached)
- P99 < 500ms
- RPS: 100+

### VPN Config (`/vpn/config`)
- P95 < 500ms
- P99 < 1000ms
- RPS: 30+

### Overall
- Failure rate < 1%
- Availability > 99%

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run smoke tests
  run: |
    docker run --rm \
      -e API_URL=http://localhost:8080 \
      grafana/k6 run - < tests/k6/06-smoke-test.js
```

### Output Formats

```bash
# JSON output
k6 run --out json=results.json tests/k6/04-api-load.js

# InfluxDB output
k6 run --out influxdb=http://localhost:8086/k6 tests/k6/04-api-load.js

# Prometheus output
k6 run --out experimental-prometheus-rw tests/k6/04-api-load.js
```

## Metrics Collected

### HTTP Metrics
- `http_req_duration` - Request duration
- `http_req_blocked` - Time blocked before request
- `http_req_connecting` - TCP connection time
- `http_req_tls_handshaking` - TLS handshake time
- `http_reqs` - Total requests

### Custom Metrics
- `health_latency_ms` - Health endpoint latency
- `vpn_status_latency_ms` - VPN status latency
- `vpn_config_latency_ms` - VPN config generation latency
- `failed_requests` - Failure rate
- `rate_limit_429` - Rate limit hits

## Troubleshooting

### Rate Limiting
If you see many 429 errors, the rate limiting is working. Adjust test parameters:
```javascript
export let options = {
  vus: 10, // Reduce VUs
  duration: '30s',
};
```

### Connection Errors
Ensure the API is running and accessible:
```bash
curl http://localhost:8080/health
```

### High Latency
Check if cache is working:
```bash
# First request (cache miss)
time curl http://localhost:8080/vpn/status

# Second request (cache hit - should be faster)
time curl http://localhost:8080/vpn/status
```
