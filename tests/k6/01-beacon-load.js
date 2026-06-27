import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const failureRate = new Rate('failed_requests');
const beaconLatency = new Trend('beacon_latency_ms');

export let options = {
  stages: [
    { duration: '10s', target: 10 },   // Warm-up
    { duration: '20s', target: 50 },   // Ramp
    { duration: '30s', target: 10 },   // Cool down
  ],
  
  thresholds: {
    'http_req_duration': ['p(95)<500'],        // P95 < 500ms
    'failed_requests': ['rate<0.01'],          // < 1% failures
    'beacon_latency_ms': ['p(95)<100'],        // Beacon P95 < 100ms
  },
};

const BASE_URL = __ENV.MESH_URL || 'http://localhost:8080';

export default function () {
  const nodeId = `node-${__VU}-${__ITER}`;
  const startTime = Date.now();
  
  // Send beacon heartbeat
  const beaconPayload = JSON.stringify({
    node_id: nodeId,
    timestamp: startTime,
    neighbors: ['node-1', 'node-2'],
  });
  
  const response = http.post(
    `${BASE_URL}/mesh/beacon`,
    beaconPayload,
    { 
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'beacon_heartbeat' }
    }
  );
  
  // Measure beacon latency
  const latency = Date.now() - startTime;
  beaconLatency.add(latency);
  
  // Validate response
  check(response, {
    'status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);
  
  sleep(1);
}
