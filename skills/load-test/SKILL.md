---
name: load-test
description: "Runs k6 performance and load tests against MaaS API and mesh endpoints for x0tta6bl4. Measures P95 latency, throughput, error rates under sustained load. Use when user asks to: run load test, performance test, stress test, k6, benchmark API, measure latency, MaaS performance, нагрузочное тестирование, тест производительности, запусти k6, проверь производительность API."
---

# Load Test

k6-based load testing for x0tta6bl4 MaaS API.

## Prerequisites

```bash
# Install k6 (if not present)
snap install k6  # Ubuntu
# or
brew install k6  # macOS

# Verify
k6 version
```

## Step 1: Start the API

```bash
# Local dev
uvicorn src.core.app:app --host 0.0.0.0 --port 8080

# Or Docker
docker-compose up -d api
```

Wait for health check:
```bash
curl -s http://localhost:8080/health | python3 -m json.tool
```

## Step 2: Run Load Tests

```bash
# Run all load tests
bash tests/load/run_load_tests.sh

# Run specific scenario (k6 directly)
k6 run tests/load/maas_load_test.js \
  -e BASE_URL=http://localhost:8080 \
  -e API_TOKEN=test-token-here \
  --vus 10 \
  --duration 30s
```

Available scenarios in `tests/load/maas_load_test.js`:
- `smoke` — 1 VU, 1 min (sanity check)
- `load` — ramp up to 50 VU, 5 min
- `stress` — ramp up to 200 VU, 10 min
- `soak` — 50 VU, 30 min (detect memory leaks)

## Step 3: Read Results

```
scenarios: (100.00%) 1 scenario, 50 max VUs, ...

     data_received..................: 2.3 MB  77 kB/s
     http_req_duration..............: avg=45ms  min=12ms  med=38ms  max=890ms  p(90)=95ms  p(95)=142ms
     http_req_failed................: 0.00%   ✓ 0  ✗ 5000
     http_reqs......................: 5000    166/s
     vus............................: 50      min=1  max=50
```

**Pass criteria:**
- `http_req_failed` < 1%
- `p(95)` latency < 200ms for read endpoints
- `p(95)` latency < 500ms for write endpoints

## Step 4: Identify Regressions

Compare with baseline:
```bash
# Save baseline
k6 run tests/load/maas_load_test.js --out json=/tmp/baseline.json

# After changes
k6 run tests/load/maas_load_test.js --out json=/tmp/current.json

# Compare (Python helper)
python3 -c "
import json
b = json.load(open('/tmp/baseline.json'))
c = json.load(open('/tmp/current.json'))
# Look for p95 degradation > 20%
"
```

## Step 5: Profile Slow Endpoints

If specific endpoints are slow:
```bash
# Target single endpoint
k6 run -e ENDPOINT=/api/v1/maas/nodes --vus 20 --duration 60s tests/load/maas_load_test.js
```

Check API logs for slow queries:
```bash
docker-compose logs api | grep -E "slow|timeout|>500ms"
```

## Troubleshooting

**High error rate (> 5%):**
- Check API logs: `docker-compose logs api --tail=100`
- Verify auth token is valid
- Reduce VU count: `--vus 5`

**k6 not found:**
```bash
export PATH=$PATH:$(go env GOPATH)/bin
# or use npx k6
npx @k6/k6 run tests/load/maas_load_test.js
```

**Connection refused:**
- API not started — run `curl http://localhost:8080/health`
- Wrong port — check `BASE_URL` env var

## Reference

- `tests/load/maas_load_test.js` — main load test script
- `tests/load/run_load_tests.sh` — orchestration script
