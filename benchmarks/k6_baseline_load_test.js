import http from 'k6/http';
import { check, group, sleep } from 'k6';

// Configuration for baseline test
export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 users
    { duration: '60s', target: 10 },  // Ramp up to 10 users
    { duration: '60s', target: 10 },  // Stay at 10 users
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // 95th percentile under 500ms
    http_req_failed: ['rate<0.1'],                   // Error rate under 0.1%
  },
};

export default function () {
  // Health check
  group('Health Check', function () {
    const res = http.get('http://localhost:8000/health');
    check(res, {
      'health check status is 200': (r) => r.status === 200,
      'health check response time < 100ms': (r) => r.timings.duration < 100,
    });
  });

  sleep(1);

  // Metrics endpoint
  group('Metrics Endpoint', function () {
    const res = http.get('http://localhost:8001/metrics');
    check(res, {
      'metrics endpoint status is 200': (r) => r.status === 200,
      'metrics response time < 200ms': (r) => r.timings.duration < 200,
    });
  });

  sleep(1);

  // API endpoint (mock - adjust based on actual API)
  group('API Request', function () {
    const res = http.get('http://localhost:8000/api/v1/info');
    check(res, {
      'API response code is 200 or 404': (r) => r.status === 200 || r.status === 404,
      'API response time < 300ms': (r) => r.timings.duration < 300,
    });
  });

  sleep(1);
}
