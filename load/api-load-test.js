/**
 * k6 load test — x0tta Mesh API
 *
 * Scenarios:
 *   - topology_read  : 70% of traffic — GET /mesh/topology (cache-heavy)
 *   - health_checks  : 20% of traffic — GET /mesh/nodes/:id/health
 *   - heal_trigger   : 10% of traffic — POST /mesh/heal (rate-limited path)
 *
 * Targets (p99):
 *   - API latency    < 100 ms
 *   - Error rate     < 0.5%
 *   - Throughput     1000 req/s sustained
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ── Custom metrics ────────────────────────────────────────────────────────────

const errorRate = new Rate('mesh_error_rate');
const topologyLatency = new Trend('mesh_topology_latency_ms', true);
const healthLatency = new Trend('mesh_health_latency_ms', true);
const healLatency = new Trend('mesh_heal_latency_ms', true);
const healAccepted = new Counter('mesh_heal_accepted_total');

// ── Config ────────────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || 'http://mesh-api.x0tta-production.svc';
const JWT = __ENV.MESH_JWT || 'load-test-token';

// Pre-seeded node IDs for health checks
const NODE_IDS = Array.from({ length: 10 }, (_, i) => `node-load-${i.toString().padStart(3, '0')}`);

// ── k6 options ────────────────────────────────────────────────────────────────

export const options = {
  scenarios: {
    topology_read: {
      executor: 'constant-arrival-rate',
      rate: 700,          // 700 req/s = 70% of 1000 target
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 50,
      maxVUs: 200,
      exec: 'topologyRead',
    },
    health_checks: {
      executor: 'constant-arrival-rate',
      rate: 200,
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 20,
      maxVUs: 80,
      exec: 'healthCheck',
    },
    heal_trigger: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 10,
      maxVUs: 40,
      exec: 'healTrigger',
    },
  },

  thresholds: {
    // p99 latency targets
    mesh_topology_latency_ms: ['p(99)<100'],
    mesh_health_latency_ms:   ['p(99)<100'],
    mesh_heal_latency_ms:     ['p(99)<200'],   // heal is heavier — allow 200ms
    // Error rate
    mesh_error_rate:          ['rate<0.005'],  // < 0.5%
    // HTTP built-ins
    http_req_duration:        ['p(99)<200'],
    http_req_failed:          ['rate<0.01'],
  },
};

// ── Auth header ───────────────────────────────────────────────────────────────

const AUTH_HEADERS = {
  'Authorization': `Bearer ${JWT}`,
  'Content-Type': 'application/json',
};

// ── Scenarios ─────────────────────────────────────────────────────────────────

export function topologyRead() {
  group('GET /mesh/topology', () => {
    const res = http.get(`${BASE_URL}/mesh/topology`, { headers: AUTH_HEADERS });

    const ok = check(res, {
      'status 200': (r) => r.status === 200,
      'has nodes array': (r) => {
        try { return Array.isArray(JSON.parse(r.body).nodes); } catch { return false; }
      },
      'has cachedAt': (r) => {
        try { return !!JSON.parse(r.body).cachedAt; } catch { return false; }
      },
    });

    topologyLatency.add(res.timings.duration);
    errorRate.add(!ok);
  });
}

export function healthCheck() {
  const nodeId = NODE_IDS[Math.floor(Math.random() * NODE_IDS.length)];

  group(`GET /mesh/nodes/${nodeId}/health`, () => {
    const res = http.get(`${BASE_URL}/mesh/nodes/${nodeId}/health`, { headers: AUTH_HEADERS });

    const ok = check(res, {
      'status 200 or 404': (r) => r.status === 200 || r.status === 404,
      'has status field': (r) => {
        if (r.status !== 200) return true;
        try { return !!JSON.parse(r.body).status; } catch { return false; }
      },
    });

    healthLatency.add(res.timings.duration);
    errorRate.add(res.status >= 500);
  });
}

export function healTrigger() {
  const nodeId = NODE_IDS[Math.floor(Math.random() * NODE_IDS.length)];
  const payload = JSON.stringify({
    nodeId,
    reason: 'k6-load-test',
    strategy: 'auto',
  });

  group('POST /mesh/heal', () => {
    const res = http.post(`${BASE_URL}/mesh/heal`, payload, { headers: AUTH_HEADERS });

    const ok = check(res, {
      // 202 = accepted, 429 = rate-limited (both valid for this test)
      'status 202 or 429': (r) => r.status === 202 || r.status === 429,
    });

    healLatency.add(res.timings.duration);
    errorRate.add(res.status >= 500);

    if (res.status === 202) healAccepted.add(1);
  });

  // Simulate a brief think-time to avoid overwhelming rate limiter
  sleep(0.1);
}

// ── Lifecycle hooks ───────────────────────────────────────────────────────────

export function setup() {
  // Warm-up: fetch topology once to prime the cache
  const res = http.get(`${BASE_URL}/mesh/topology`, { headers: AUTH_HEADERS });
  if (res.status !== 200) {
    console.warn(`Warm-up request returned ${res.status} — proceeding anyway`);
  }
  return { warmupOk: res.status === 200 };
}

export function teardown(data) {
  console.log(`Load test complete. Warm-up OK: ${data.warmupOk}`);
}
