import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

/**
 * Stress Test for x0tta6bl4 API
 *
 * Purpose: Find the breaking point of the system
 *
 * Stages:
 * 1. Warm up (2 min): 10 users
 * 2. Ramp up (5 min): 10 → 500 users
 * 3. Stress (3 min): Hold at 500 users
 * 4. Spike (1 min): Jump to 1000 users
 * 5. Recovery (2 min): Back to 100 users
 * 6. Cool down (2 min): 100 → 0 users
 */

// Custom metrics
const failureRate = new Rate('failed_requests');
const successRate = new Rate('successful_requests');
const requestLatency = new Trend('request_latency_ms');
const errorCounter = new Counter('error_count');
const rateLimitHits = new Counter('rate_limit_429');

export let options = {
  stages: [
    // Warm up
    { duration: '2m', target: 10 },
    // Ramp up to stress level
    { duration: '5m', target: 500 },
    // Stress plateau
    { duration: '3m', target: 500 },
    // Spike test
    { duration: '1m', target: 1000 },
    // Recovery
    { duration: '2m', target: 100 },
    // Cool down
    { duration: '2m', target: 0 },
  ],

  thresholds: {
    // During stress, allow some degradation
    'http_req_duration': ['p(95)<1000', 'p(99)<2000'],
    // Allow up to 5% failure under stress
    'failed_requests': ['rate<0.05'],
    // Track successful requests
    'successful_requests': ['rate>0.90'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8080';

// Weighted endpoint selection
const ENDPOINTS = [
  { path: '/health', weight: 40 },
  { path: '/vpn/status', weight: 30 },
  { path: '/status', weight: 20 },
  { path: '/vpn/config?user_id=', weight: 10 },
];

function selectEndpoint() {
  const totalWeight = ENDPOINTS.reduce((sum, e) => sum + e.weight, 0);
  let random = Math.random() * totalWeight;

  for (const endpoint of ENDPOINTS) {
    random -= endpoint.weight;
    if (random <= 0) {
      return endpoint.path;
    }
  }
  return '/health';
}

export default function () {
  const startTime = Date.now();
  let endpoint = selectEndpoint();

  // Add user_id for config endpoint
  if (endpoint.includes('user_id=')) {
    endpoint += Math.floor(Math.random() * 1000000);
  }

  const response = http.get(`${BASE_URL}${endpoint}`, {
    tags: { name: endpoint.split('?')[0] },
    timeout: '10s',
  });

  const latency = Date.now() - startTime;
  requestLatency.add(latency);

  // Track response status
  if (response.status === 200) {
    successRate.add(1);

    const success = check(response, {
      'response is valid JSON': (r) => {
        try {
          JSON.parse(r.body);
          return true;
        } catch (e) {
          return false;
        }
      },
    });

    if (!success) {
      failureRate.add(1);
    }
  } else if (response.status === 429) {
    // Rate limited - expected under stress
    rateLimitHits.add(1);
    failureRate.add(1);
  } else {
    failureRate.add(1);
    errorCounter.add(1);

    console.error(`Error ${response.status} on ${endpoint}: ${response.body}`);
  }

  // Variable think time based on VU count
  const thinkTime = Math.max(0.1, 1 - (__VU / 500));
  sleep(thinkTime);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: '  ', enableColors: true }),
    'stress_test_results.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const metrics = data.metrics;

  let output = '\n========== STRESS TEST SUMMARY ==========\n\n';

  output += `Total Requests: ${metrics.http_reqs?.values?.count || 0}\n`;
  output += `Success Rate: ${((metrics.successful_requests?.values?.rate || 0) * 100).toFixed(2)}%\n`;
  output += `Failure Rate: ${((metrics.failed_requests?.values?.rate || 0) * 100).toFixed(2)}%\n`;
  output += `Rate Limit Hits: ${metrics.rate_limit_429?.values?.count || 0}\n`;
  output += `Errors: ${metrics.error_count?.values?.count || 0}\n\n`;

  output += 'Latency Percentiles:\n';
  output += `  P50: ${(metrics.http_req_duration?.values?.med || 0).toFixed(2)}ms\n`;
  output += `  P90: ${(metrics.http_req_duration?.values?.['p(90)'] || 0).toFixed(2)}ms\n`;
  output += `  P95: ${(metrics.http_req_duration?.values?.['p(95)'] || 0).toFixed(2)}ms\n`;
  output += `  P99: ${(metrics.http_req_duration?.values?.['p(99)'] || 0).toFixed(2)}ms\n\n`;

  output += '==========================================\n';

  return output;
}
