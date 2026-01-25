# 📡 API Endpoints Reference для x0tta6bl4 v3.0.0

**Base URL:** `http://localhost:8080` (development)  
**Production:** `https://api.x0tta6bl4.net`  
**Version:** 3.0.0

---

## 🔍 Health & Status

### `GET /health`
Проверка здоровья приложения.

**Response:**
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "timestamp": "2025-11-30T12:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Приложение работает
- `503 Service Unavailable` - Приложение недоступно

---

## 🌐 Mesh Network

### `POST /mesh/beacon`
Отправить beacon для обнаружения peers.

**Request:**
```json
{
  "node_id": "node-01",
  "timestamp": "2025-11-30T12:00:00Z"
}
```

**Response:**
```json
{
  "status": "broadcasted",
  "peers_discovered": 5
}
```

### `GET /mesh/status`
Получить статус mesh сети.

**Response:**
```json
{
  "status": "online",
  "total_nodes": 50,
  "online_nodes": 48,
  "offline_nodes": 2,
  "total_links": 120,
  "active_links": 115
}
```

### `GET /mesh/peers`
Получить список mesh peers.

**Response:**
```json
{
  "peers": [
    {
      "node_id": "node-01",
      "address": "2001:db8::1",
      "state": "online",
      "rssi": -45.0,
      "latency_ms": 12.5
    }
  ],
  "total": 50
}
```

### `GET /mesh/routes`
Получить маршруты mesh сети.

**Query Parameters:**
- `source` (optional): Source node ID
- `target` (optional): Target node ID

**Response:**
```json
{
  "routes": [
    {
      "source": "node-01",
      "target": "node-05",
      "path": ["node-01", "node-02", "node-05"],
      "latency_ms": 25.3,
      "hops": 2
    }
  ]
}
```

---

## 🔒 Security

### `POST /security/handshake`
Выполнить PQC handshake между узлами.

**Request:**
```json
{
  "peer_id": "node-02",
  "public_key": "base64_encoded_pqc_public_key",
  "algorithm": "ML-KEM-768"
}
```

**Response:**
```json
{
  "status": "success",
  "session_key": "encrypted_session_key",
  "algorithm": "ML-KEM-768",
  "handshake_time_ms": 45.2
}
```

**Status Codes:**
- `200 OK` - Handshake успешен
- `400 Bad Request` - Неверный формат запроса
- `500 Internal Server Error` - Ошибка PQC

---

## 🤖 AI/ML

### `GET /ai/predict/{target_node_id}`
Предсказать состояние целевого узла с помощью GraphSAGE.

**Path Parameters:**
- `target_node_id`: ID целевого узла

**Query Parameters:**
- `include_causal` (optional, default: false): Включить causal analysis
- `include_shap` (optional, default: false): Включить SHAP values

**Response:**
```json
{
  "node_id": "node-01",
  "prediction": {
    "is_anomaly": false,
    "anomaly_score": 0.35,
    "confidence": 0.65,
    "inference_time_ms": 42.3
  },
  "causal_analysis": {
    "root_causes": [],
    "confidence": 0.0
  },
  "shap_values": {
    "rssi": 0.12,
    "snr": 0.08,
    "loss_rate": 0.15
  }
}
```

---

## 📊 Metrics

### `GET /metrics`
Prometheus metrics endpoint.

**Response:** Prometheus format
```
# HELP x0tta6bl4_requests_total Total number of requests
# TYPE x0tta6bl4_requests_total counter
x0tta6bl4_requests_total 1250

# HELP x0tta6bl4_latency_seconds Request latency
# TYPE x0tta6bl4_latency_seconds histogram
x0tta6bl4_latency_seconds_bucket{le="0.1"} 1200
...
```

---

## 🔔 Alerts

### `POST /alerts/send`
Отправить alert (internal use).

**Request:**
```json
{
  "name": "HIGH_ERROR_RATE",
  "severity": "critical",
  "message": "Error rate exceeded 1%",
  "labels": {
    "component": "mesh_router",
    "node_id": "node-01"
  }
}
```

**Response:**
```json
{
  "status": "sent",
  "channels": ["alertmanager", "telegram"],
  "timestamp": "2025-11-30T12:00:00Z"
}
```

---

## 🗳️ DAO Governance

### `POST /dao/vote`
Проголосовать в DAO.

**Request:**
```json
{
  "proposal_id": "prop-001",
  "vote": "yes",
  "weight": 10,
  "node_id": "node-01"
}
```

**Response:**
```json
{
  "status": "recorded",
  "proposal_id": "prop-001",
  "vote": "yes",
  "weight": 10,
  "total_votes": 150,
  "quorum_reached": true
}
```

---

## 📚 Documentation

### `GET /docs`
Swagger UI документация (FastAPI auto-generated).

**URL:** `http://localhost:8080/docs`

### `GET /redoc`
ReDoc документация.

**URL:** `http://localhost:8080/redoc`

---

## 🔐 Authentication

Все endpoints требуют SPIFFE mTLS authentication (если включено).

**Headers:**
```
X-SPIFFE-ID: spiffe://example.org/workload/node-01
```

---

## ⚠️ Rate Limiting

- **Default:** 100 requests/minute per IP
- **Mesh endpoints:** 1000 requests/minute
- **ML endpoints:** 50 requests/minute

---

## 📝 Error Responses

### Standard Error Format
```json
{
  "error": "Error type",
  "message": "Human-readable error message",
  "details": {
    "field": "additional context"
  },
  "timestamp": "2025-11-30T12:00:00Z"
}
```

### Status Codes
- `200 OK` - Success
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Access denied
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

---

## 🧪 Testing

### Health Check
```bash
curl http://localhost:8080/health
```

### Get Mesh Peers
```bash
curl http://localhost:8080/mesh/peers
```

### Detect Anomaly
```bash
curl -X POST http://localhost:8080/ml/anomaly/detect \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-01",
    "features": {
      "rssi": -50.0,
      "snr": 25.0,
      "loss_rate": 0.02,
      "link_age": 3600,
      "latency": 15.0,
      "throughput": 100.0,
      "cpu": 45.0,
      "memory": 60.0
    },
    "neighbors": []
  }'
```

---

**Версия:** 3.0.0  
**Дата:** 30 ноября 2025  
**Статус:** Production Ready

