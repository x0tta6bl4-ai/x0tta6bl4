import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const voteLatency = new Trend('vote_latency_ms');
const failureRate = new Rate('failed_votes');

export let options = {
  stages: [
    { duration: '10s', target: 10 },
    { duration: '30s', target: 50 },
    { duration: '10s', target: 0 },
  ],
  
  thresholds: {
    'vote_latency_ms': ['p(95)<2000'],         // < 2s
    'failed_votes': ['rate<0.02'],             // < 2% failures
  },
};

const BASE_URL = __ENV.MESH_URL || 'http://localhost:8080';

export default function () {
  const payload = JSON.stringify({
    proposal_id: 1,
    voter_id: `voter-${__VU}`,
    tokens: Math.floor(Math.random() * 10000) + 100,
    vote: true,
  });
  
  const startTime = Date.now();
  
  const response = http.post(
    `${BASE_URL}/dao/vote`,
    payload,
    { 
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'dao_vote' }
    }
  );
  
  voteLatency.add(Date.now() - startTime);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);
  
  sleep(2);
}
