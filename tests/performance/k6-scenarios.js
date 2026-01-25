import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  scenarios: {
    // Scenario 1: Constant load (Normal traffic)
    normal_load: {
      executor: 'constant-vus',
      vus: 50,
      duration: '1m',
    },
    // Scenario 2: Stress test (Peak traffic)
    stress_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 100 },
        { duration: '1m', target: 200 },
        { duration: '30s', target: 0 },
      ],
      startTime: '1m', // Start after normal load
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200'], // 95% of requests must complete below 200ms
    http_req_failed: ['rate<0.01'],   // Error rate must be below 1%
  }
};

const BASE_URL = 'http://localhost:8000';

export default function() {
  // Test Health Endpoint
  let res = http.get(`${BASE_URL}/health`);
  check(res, {
    'health status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });

  // Test Mesh Status Endpoint
  res = http.get(`${BASE_URL}/mesh/status`);
  check(res, {
    'mesh status is 200': (r) => r.status === 200,
  });
  
  // Test Metrics Endpoint (Observability overhead)
  res = http.get(`${BASE_URL}/metrics`);
  check(res, {
    'metrics status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
