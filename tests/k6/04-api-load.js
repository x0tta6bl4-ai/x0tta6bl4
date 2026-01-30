import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const failureRate = new Rate('failed_requests');
const healthLatency = new Trend('health_latency_ms');
const vpnStatusLatency = new Trend('vpn_status_latency_ms');
const vpnConfigLatency = new Trend('vpn_config_latency_ms');

export let options = {
  scenarios: {
    // Health check - high frequency, should always be fast
    health_check: {
      executor: 'constant-arrival-rate',
      rate: 1000, // 1000 RPS target
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 50,
      maxVUs: 100,
      exec: 'healthCheck',
    },
    // VPN status - moderate load
    vpn_status: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 20 },
        { duration: '30s', target: 100 },
        { duration: '10s', target: 0 },
      ],
      exec: 'vpnStatus',
    },
    // VPN config generation - lower load, heavier operation
    vpn_config: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
      exec: 'vpnConfig',
    },
  },

  thresholds: {
    // Health endpoint: P95 < 50ms, P99 < 100ms
    'health_latency_ms': ['p(95)<50', 'p(99)<100'],
    // VPN status: P95 < 200ms (cached)
    'vpn_status_latency_ms': ['p(95)<200'],
    // VPN config: P95 < 500ms (compute-heavy)
    'vpn_config_latency_ms': ['p(95)<500'],
    // Overall failure rate < 1%
    'failed_requests': ['rate<0.01'],
    // HTTP duration
    'http_req_duration': ['p(95)<300'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8080';

export function healthCheck() {
  const startTime = Date.now();

  const response = http.get(`${BASE_URL}/health`, {
    tags: { name: 'health_check' }
  });

  const latency = Date.now() - startTime;
  healthLatency.add(latency);

  const success = check(response, {
    'health status 200': (r) => r.status === 200,
    'health response ok': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.status === 'ok';
      } catch (e) {
        return false;
      }
    },
  });

  if (!success) {
    failureRate.add(1);
  }
}

export function vpnStatus() {
  const startTime = Date.now();

  const response = http.get(`${BASE_URL}/vpn/status`, {
    tags: { name: 'vpn_status' }
  });

  const latency = Date.now() - startTime;
  vpnStatusLatency.add(latency);

  const success = check(response, {
    'vpn status 200': (r) => r.status === 200,
    'vpn has server': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.server !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success) {
    failureRate.add(1);
  }

  sleep(0.5);
}

export function vpnConfig() {
  const startTime = Date.now();
  const userId = Math.floor(Math.random() * 1000000);

  const response = http.get(`${BASE_URL}/vpn/config?user_id=${userId}`, {
    tags: { name: 'vpn_config' }
  });

  const latency = Date.now() - startTime;
  vpnConfigLatency.add(latency);

  const success = check(response, {
    'vpn config 200': (r) => r.status === 200,
    'vpn config has vless_link': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.vless_link && body.vless_link.startsWith('vless://');
      } catch (e) {
        return false;
      }
    },
  });

  if (!success) {
    failureRate.add(1);
  }

  sleep(1);
}

// Default function for single scenario runs
export default function () {
  group('Health Check', () => {
    healthCheck();
  });

  group('VPN Status', () => {
    vpnStatus();
  });

  group('VPN Config', () => {
    vpnConfig();
  });

  sleep(1);
}
