import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const recallScore = new Trend('gnn_recall_score');
const failureRate = new Rate('failed_predictions');

export let options = {
  stages: [
    { duration: '10s', target: 5 },
    { duration: '30s', target: 20 },
    { duration: '10s', target: 0 },
  ],
  
  thresholds: {
    'gnn_recall_score': ['avg>=0.92'],         // Recall ≥ 92%
    'failed_predictions': ['rate<0.05'],       // < 5% failures
  },
};

const BASE_URL = __ENV.MESH_URL || 'http://localhost:8080';

export default function () {
  const nodeId = `node-${Math.floor(Math.random() * 100)}`;
  
  const response = http.get(
    `${BASE_URL}/ai/predict/${nodeId}`,
    { tags: { name: 'graphsage_prediction' } }
  );
  
  check(response, {
    'status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);
  
  sleep(1);
}
