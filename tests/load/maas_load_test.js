// MaaS API Load Testing with k6
// ==============================
// Updated for v1.1 Router Structure (2026-03-06)

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Custom metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');
const meshCreationTime = new Trend('mesh_creation_time');
const successfulRequests = new Counter('successful_requests');
const failedRequests = new Counter('failed_requests');

// Test data
const testData = new SharedArray('test data', function() {
    return [
        { name: 'load-test-mesh-1', nodes: 3, region: 'us-east-1' },
        { name: 'load-test-mesh-2', nodes: 5, region: 'eu-west-1' },
    ];
});

export const options = {
    vus: 5,
    duration: '20s',
    thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.1'],
    },
};

export function setup() {
    const healthCheck = http.get(`${BASE_URL}/health/live`);
    check(healthCheck, { 'API is healthy': (r) => r.status === 200 });
    return { startTime: Date.now() };
}

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`,
    };
}

export default function () {
    const data = testData[Math.floor(Math.random() * testData.length)];
    
    group('Discovery', () => {
        const info = http.get(`${BASE_URL}/`, { headers: getHeaders() });
        check(info, { 'Info returns 200': (r) => r.status === 200 });

        const search = http.get(`${BASE_URL}/api/v1/maas/marketplace/search`, { headers: getHeaders() });
        check(search, { 'Marketplace search returns 200': (r) => r.status === 200 });
    });

    group('Billing', () => {
        const status = http.get(`${BASE_URL}/api/v1/maas/billing/status`, { headers: getHeaders() });
        check(status, { 'Billing status ok': (r) => r.status === 200 || r.status === 401 || r.status === 404 });
    });

    sleep(1);
}

export function handleSummary(data) {
    return {
        stdout: textSummary(data, { indent: ' ', enableColors: true }),
    };
}
