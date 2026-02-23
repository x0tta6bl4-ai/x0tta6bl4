// MaaS API Load Testing with k6
// ==============================
// Comprehensive load tests for MaaS staging environment
//
// Usage:
//   k6 run tests/load/maas_load_test.js
//   k6 run --vus 100 --duration 5m tests/load/maas_load_test.js
//   k6 run --stage.1m:10,5m:50,1m:10 tests/load/maas_load_test.js

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = __ENV.BASE_URL || 'https://api.staging.maas-x0tta6bl4.local';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Custom metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');
const meshCreationTime = new Trend('mesh_creation_time');
const nodeProvisioningTime = new Trend('node_provisioning_time');
const successfulRequests = new Counter('successful_requests');
const failedRequests = new Counter('failed_requests');

// Test data
const testData = new SharedArray('test data', function() {
    return [
        { name: 'load-test-mesh-1', nodes: 3, region: 'us-east-1' },
        { name: 'load-test-mesh-2', nodes: 5, region: 'eu-west-1' },
        { name: 'load-test-mesh-3', nodes: 2, region: 'ap-southeast-1' },
    ];
});

// ============================================================================
// Test Options
// ============================================================================

export const options = {
    // Scenarios
    scenarios: {
        // Smoke test - basic functionality
        smoke_test: {
            executor: 'per-vu-iterations',
            vus: 1,
            iterations: 5,
            maxDuration: '1m',
            tags: { test_type: 'smoke' },
        },
        
        // Load test - normal load
        load_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 10 },
                { duration: '5m', target: 50 },
                { duration: '2m', target: 10 },
                { duration: '1m', target: 0 },
            ],
            gracefulRampDown: '30s',
            tags: { test_type: 'load' },
        },
        
        // Stress test - high load
        stress_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 50 },
                { duration: '5m', target: 200 },
                { duration: '2m', target: 50 },
                { duration: '1m', target: 0 },
            ],
            gracefulRampDown: '30s',
            tags: { test_type: 'stress' },
            exec: 'stressTest',  // Use different function
        },
        
        // Spike test - sudden load increase
        spike_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 100 },
                { duration: '1m', target: 100 },
                { duration: '10s', target: 0 },
            ],
            tags: { test_type: 'spike' },
            exec: 'spikeTest',
        },
        
        // Soak test - extended duration
        soak_test: {
            executor: 'constant-vus',
            vus: 20,
            duration: '30m',
            tags: { test_type: 'soak' },
            exec: 'soakTest',
        },
    },
    
    // Thresholds
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<1000'],
        http_req_failed: ['rate<0.05'],
        errors: ['rate<0.1'],
        request_duration: ['p(95)<500'],
        mesh_creation_time: ['p(95)<2000'],
        node_provisioning_time: ['p(95)<5000'],
    },
    
    // Summary output
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ============================================================================
// Setup and Teardown
// ============================================================================

export function setup() {
    console.log('🚀 Starting MaaS load test...');
    console.log(`📍 Base URL: ${BASE_URL}`);
    
    // Verify API is accessible
    const healthCheck = http.get(`${BASE_URL}/health/live`, {
        headers: { 'Content-Type': 'application/json' },
    });
    
    check(healthCheck, {
        'API is healthy': (r) => r.status === 200,
    });
    
    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log(`✅ Load test completed in ${duration.toFixed(2)} seconds`);
    
    // Cleanup any created resources
    console.log('🧹 Cleaning up test resources...');
}

// ============================================================================
// Helper Functions
// ============================================================================

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`,
        'X-Request-ID': `k6-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    };
}

function makeRequest(method, endpoint, payload = null, tags = {}) {
    const url = `${BASE_URL}${endpoint}`;
    const params = {
        headers: getHeaders(),
        tags: tags,
        timeout: '30s',
    };
    
    let response;
    const startTime = Date.now();
    
    if (method === 'GET') {
        response = http.get(url, params);
    } else if (method === 'POST') {
        response = http.post(url, JSON.stringify(payload), params);
    } else if (method === 'PUT') {
        response = http.put(url, JSON.stringify(payload), params);
    } else if (method === 'DELETE') {
        response = http.del(url, null, params);
    }
    
    const duration = Date.now() - startTime;
    requestDuration.add(duration);
    
    // Track errors
    if (response.status >= 400) {
        errorRate.add(1);
        failedRequests.add(1);
    } else {
        errorRate.add(0);
        successfulRequests.add(1);
    }
    
    return response;
}

// ============================================================================
// Test Functions
// ============================================================================

export default function () {
    // Random test data
    const data = testData[Math.floor(Math.random() * testData.length)];
    
    group('Health Check', () => {
        const response = makeRequest('GET', '/health/live', null, { endpoint: 'health' });
        
        check(response, {
            'Health check status is 200': (r) => r.status === 200,
            'Health check response time < 100ms': (r) => r.timings.duration < 100,
        });
    });
    
    sleep(1);
    
    group('API Info', () => {
        const response = makeRequest('GET', '/v1/info', null, { endpoint: 'info' });
        
        check(response, {
            'Info status is 200': (r) => r.status === 200,
            'Info has version': (r) => r.json('version') !== undefined,
        });
    });
    
    sleep(1);
    
    group('Mesh Operations', () => {
        // List meshes
        const listResponse = makeRequest('GET', '/v1/mesh', null, { endpoint: 'mesh_list' });
        
        check(listResponse, {
            'List meshes status is 200': (r) => r.status === 200,
            'List meshes has items': (r) => Array.isArray(r.json('meshes')),
        });
        
        sleep(0.5);
        
        // Create mesh (only for some iterations to avoid too many resources)
        if (Math.random() < 0.1) {
            const createPayload = {
                name: `${data.name}-${Date.now()}`,
                nodes: data.nodes,
                region: data.region,
                pqc_profile: 'ML-KEM-768',
            };
            
            const startTime = Date.now();
            const createResponse = makeRequest('POST', '/v1/mesh', createPayload, { endpoint: 'mesh_create' });
            meshCreationTime.add(Date.now() - startTime);
            
            check(createResponse, {
                'Create mesh status is 201': (r) => r.status === 201,
                'Create mesh has ID': (r) => r.json('mesh_id') !== undefined,
            });
            
            if (createResponse.status === 201) {
                const meshId = createResponse.json('mesh_id');
                
                sleep(2);
                
                // Get mesh details
                const getResponse = makeRequest('GET', `/v1/mesh/${meshId}`, null, { endpoint: 'mesh_get' });
                
                check(getResponse, {
                    'Get mesh status is 200': (r) => r.status === 200,
                    'Get mesh has correct ID': (r) => r.json('mesh_id') === meshId,
                });
                
                sleep(1);
                
                // Delete mesh
                const deleteResponse = makeRequest('DELETE', `/v1/mesh/${meshId}`, null, { endpoint: 'mesh_delete' });
                
                check(deleteResponse, {
                    'Delete mesh status is 204': (r) => r.status === 204,
                });
            }
        }
    });
    
    sleep(1);
    
    group('Node Operations', () => {
        // List nodes
        const listResponse = makeRequest('GET', '/v1/nodes', null, { endpoint: 'node_list' });
        
        check(listResponse, {
            'List nodes status is 200': (r) => r.status === 200,
            'List nodes has items': (r) => Array.isArray(r.json('nodes')),
        });
    });
    
    sleep(1);
    
    group('Billing Operations', () => {
        // Get subscription info
        const subResponse = makeRequest('GET', '/v1/billing/subscription', null, { endpoint: 'billing_subscription' });
        
        check(subResponse, {
            'Subscription status is 200 or 404': (r) => r.status === 200 || r.status === 404,
        });
        
        sleep(0.5);
        
        // Get usage
        const usageResponse = makeRequest('GET', '/v1/billing/usage', null, { endpoint: 'billing_usage' });
        
        check(usageResponse, {
            'Usage status is 200': (r) => r.status === 200,
        });
    });
    
    sleep(2);
}

// Stress test function - more aggressive operations
export function stressTest() {
    const data = testData[Math.floor(Math.random() * testData.length)];
    
    // Rapid-fire requests
    for (let i = 0; i < 5; i++) {
        const response = makeRequest('GET', '/health/live', null, { endpoint: 'health_stress' });
        
        check(response, {
            'Stress health check passed': (r) => r.status === 200,
        });
        
        sleep(0.1);
    }
    
    // Create multiple meshes rapidly
    if (Math.random() < 0.3) {
        const createPayload = {
            name: `stress-mesh-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
            nodes: Math.floor(Math.random() * 5) + 1,
            region: data.region,
        };
        
        const response = makeRequest('POST', '/v1/mesh', createPayload, { endpoint: 'mesh_create_stress' });
        
        check(response, {
            'Stress mesh creation passed': (r) => r.status === 201 || r.status === 429,  // 429 = rate limited
        });
    }
    
    sleep(0.5);
}

// Spike test function - handle sudden load
export function spikeTest() {
    const response = makeRequest('GET', '/v1/mesh', null, { endpoint: 'mesh_spike' });
    
    check(response, {
        'Spike test response received': (r) => r.status !== 0,
        'Spike test response time acceptable': (r) => r.timings.duration < 5000,
    });
    
    sleep(0.1);
}

// Soak test function - extended duration stability
export function soakTest() {
    // Basic operations over extended period
    group('Soak Test - Health', () => {
        const response = makeRequest('GET', '/health/ready', null, { endpoint: 'health_soak' });
        
        check(response, {
            'Soak health check passed': (r) => r.status === 200,
        });
    });
    
    sleep(5);
    
    group('Soak Test - Mesh List', () => {
        const response = makeRequest('GET', '/v1/mesh', null, { endpoint: 'mesh_soak' });
        
        check(response, {
            'Soak mesh list passed': (r) => r.status === 200,
        });
    });
    
    sleep(5);
}

// ============================================================================
// Summary Report
// ============================================================================

export function handleSummary(data) {
    const stats = {
        totalRequests: successfulRequests.valueOf() + failedRequests.valueOf(),
        successfulRequests: successfulRequests.valueOf(),
        failedRequests: failedRequests.valueOf(),
        errorRate: (failedRequests.valueOf() / (successfulRequests.valueOf() + failedRequests.valueOf()) * 100).toFixed(2),
    };
    
    return {
        stdout: textSummary(data, { indent: ' ', enableColors: true }),
        'load-test-summary.json': JSON.stringify({
            stats: stats,
            metrics: data.metrics,
            timestamp: new Date().toISOString(),
        }, null, 2),
    };
}
