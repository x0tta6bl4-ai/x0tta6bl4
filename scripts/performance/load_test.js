import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const STAGE_DURATION = __ENV.STAGE_DURATION || '5m';
const VU_RAMP_UP = parseInt(__ENV.VU_RAMP_UP || '50');
const VU_SUSTAINED = parseInt(__ENV.VU_SUSTAINED || '100');
const VU_SPIKE = parseInt(__ENV.VU_SPIKE || '200');

const errorRate = new Rate('errors');
const apiDuration = new Trend('api_duration');
const requestCount = new Counter('requests');
const activeConnections = new Gauge('active_connections');

export const options = {
  stages: [
    { duration: '1m', target: 10, name: 'warm-up' },
    { duration: STAGE_DURATION, target: VU_RAMP_UP, name: 'ramp-up' },
    { duration: STAGE_DURATION, target: VU_SUSTAINED, name: 'sustained-load' },
    { duration: '2m', target: VU_SPIKE, name: 'spike-test' },
    { duration: '2m', target: 0, name: 'ramp-down' },
  ],
  
  thresholds: {
    errors: ['rate<0.05'],
    api_duration: ['p(95)<500', 'p(99)<1000'],
    'api_duration{endpoint:health}': ['p(95)<100'],
  },
  
  ext: {
    loadimpact: {
      projectID: 3474747,
      name: 'x0tta6bl4-baseline',
    },
  },
};

export function setup() {
  console.log(`Starting load test against: ${BASE_URL}`);
  
  const res = http.get(`${BASE_URL}/health/ready`);
  check(res, {
    'app is ready': (r) => r.status === 200,
  });
}

export default function (data) {
  activeConnections.add(__VU);
  
  group('Health Checks', () => {
    let res = http.get(`${BASE_URL}/health/ready`);
    
    const success = check(res, {
      'health check status 200': (r) => r.status === 200,
      'health check response time < 100ms': (r) => r.timings.duration < 100,
    });
    
    if (!success) {
      errorRate.add(1);
    }
    
    apiDuration.add(res.timings.duration, { endpoint: 'health' });
    requestCount.add(1);
    
    sleep(1);
  });
  
  group('API Endpoints', () => {
    const endpoints = [
      '/api/v1/mesh/nodes',
      '/api/v1/metrics',
      '/api/v1/security/policies',
    ];
    
    for (const endpoint of endpoints) {
      const res = http.get(`${BASE_URL}${endpoint}`);
      
      const success = check(res, {
        [`${endpoint} status 200/401/403`]: (r) => [200, 401, 403].includes(r.status),
        [`${endpoint} response time < 1000ms`]: (r) => r.timings.duration < 1000,
      });
      
      if (!success) {
        errorRate.add(1);
      }
      
      apiDuration.add(res.timings.duration, { endpoint: endpoint });
      requestCount.add(1);
      
      sleep(0.5);
    }
  });
  
  sleep(Math.random() * 2);
}

export function teardown(data) {
  console.log('Load test completed');
  const res = http.get(`${BASE_URL}/metrics`);
  if (res.status === 200) {
    console.log('Final metrics collected');
  }
}
