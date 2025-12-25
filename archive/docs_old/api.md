# API Reference

## Endpoints

### Health

```http
GET /health
```

Response:
```json
{"status": "ok", "version": "3.0.0"}
```

### Mesh Beacon

```http
POST /mesh/beacon
Content-Type: application/json

{
  "node_id": "node-01",
  "timestamp": 1234567890,
  "slot": 42
}
```

### AI Prediction

```http
POST /ai/predict
Content-Type: application/json

{
  "features": [0.1, 0.2, 0.3, ...],
  "node_id": "node-01"
}
```

Response:
```json
{
  "anomaly": false,
  "confidence": 0.96,
  "latency_ms": 3.84
}
```

### DAO Vote

```http
POST /dao/vote
Content-Type: application/json

{
  "proposal_id": "prop-123",
  "voter_id": "node-01",
  "tokens": 100,
  "support": true
}
```

Response:
```json
{
  "vote_power": 10.0,
  "success": true
}
```

### Metrics

```http
GET /metrics
```

Prometheus format metrics.
