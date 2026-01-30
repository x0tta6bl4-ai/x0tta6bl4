import http from 'k6/http';
import { check, fail } from 'k6';

/**
 * Smoke Test for x0tta6bl4 API
 *
 * Purpose: Quick sanity check that all endpoints are working
 *
 * Duration: ~30 seconds
 * Use Case: Run in CI/CD before deployment
 */

export let options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ['rate==1.0'], // All checks must pass
    http_req_duration: ['p(95)<500'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8080';
const ADMIN_TOKEN = __ENV.ADMIN_TOKEN || 'test_admin_token';

export default function () {
  console.log(`Testing API at ${BASE_URL}`);

  // Test 1: Health endpoint
  console.log('\n[1/6] Testing /health...');
  let response = http.get(`${BASE_URL}/health`);
  let passed = check(response, {
    '/health returns 200': (r) => r.status === 200,
    '/health returns ok status': (r) => {
      const body = JSON.parse(r.body);
      return body.status === 'ok';
    },
  });
  if (!passed) fail('/health check failed');
  console.log('✓ /health OK');

  // Test 2: Status endpoint
  console.log('\n[2/6] Testing /status...');
  response = http.get(`${BASE_URL}/status`);
  passed = check(response, {
    '/status returns 200': (r) => r.status === 200,
    '/status is valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (e) {
        return false;
      }
    },
  });
  if (!passed) fail('/status check failed');
  console.log('✓ /status OK');

  // Test 3: Root endpoint
  console.log('\n[3/6] Testing /...');
  response = http.get(`${BASE_URL}/`);
  passed = check(response, {
    '/ returns 200': (r) => r.status === 200,
    '/ has name': (r) => {
      const body = JSON.parse(r.body);
      return body.name === 'x0tta6bl4';
    },
  });
  if (!passed) fail('/ check failed');
  console.log('✓ / OK');

  // Test 4: VPN status
  console.log('\n[4/6] Testing /vpn/status...');
  response = http.get(`${BASE_URL}/vpn/status`);
  passed = check(response, {
    '/vpn/status returns 200': (r) => r.status === 200,
    '/vpn/status has server': (r) => {
      const body = JSON.parse(r.body);
      return body.server !== undefined;
    },
    '/vpn/status has protocol': (r) => {
      const body = JSON.parse(r.body);
      return body.protocol === 'VLESS+Reality';
    },
  });
  if (!passed) fail('/vpn/status check failed');
  console.log('✓ /vpn/status OK');

  // Test 5: VPN config generation
  console.log('\n[5/6] Testing /vpn/config...');
  response = http.get(`${BASE_URL}/vpn/config?user_id=12345`);
  passed = check(response, {
    '/vpn/config returns 200': (r) => r.status === 200,
    '/vpn/config has vless_link': (r) => {
      const body = JSON.parse(r.body);
      return body.vless_link && body.vless_link.startsWith('vless://');
    },
    '/vpn/config has config_text': (r) => {
      const body = JSON.parse(r.body);
      return body.config_text && body.config_text.length > 0;
    },
  });
  if (!passed) fail('/vpn/config check failed');
  console.log('✓ /vpn/config OK');

  // Test 6: Billing config
  console.log('\n[6/6] Testing /api/v1/billing/config...');
  response = http.get(`${BASE_URL}/api/v1/billing/config`);
  passed = check(response, {
    '/api/v1/billing/config returns 200': (r) => r.status === 200,
    '/api/v1/billing/config has configured field': (r) => {
      const body = JSON.parse(r.body);
      return body.configured !== undefined;
    },
  });
  if (!passed) fail('/api/v1/billing/config check failed');
  console.log('✓ /api/v1/billing/config OK');

  console.log('\n========================================');
  console.log('✓ ALL SMOKE TESTS PASSED');
  console.log('========================================\n');
}

export function handleSummary(data) {
  const passed = data.metrics.checks?.values?.passes || 0;
  const failed = data.metrics.checks?.values?.fails || 0;

  return {
    stdout: `
Smoke Test Results:
  Passed: ${passed}
  Failed: ${failed}
  Status: ${failed === 0 ? '✓ PASS' : '✗ FAIL'}
`,
  };
}
