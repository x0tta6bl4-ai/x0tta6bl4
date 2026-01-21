# API Reference

**Версия:** 3.0.0  
**Дата:** 2025-12-28  
**Базовый URL:** `http://localhost:8080`

---

## 📋 Обзор

REST API для x0tta6bl4 mesh network platform.

---

## 🔐 Аутентификация

### SPIFFE/mTLS (Production)

В production используется SPIFFE/SPIRE для Zero Trust аутентификации:

- **mTLS:** Обязательно для всех запросов
- **SPIFFE ID:** Проверяется автоматически
- **Socket:** `/run/spire/sockets/agent.sock`

### Development/Staging

В development/staging режиме mTLS опционален.

---

## 📡 Endpoints

### Health Check

#### `GET /health`

Проверка статуса системы и компонентов.

**Response:**
```json
{
  "status": "ok",
  "version": "3.0.0",
  "components": {
    "graphsage": true,
    "causal_analysis": true,
    "fl_coordinator": true,
    "spiffe": true,
    ...
  },
  "component_stats": {
    "active": 15,
    "total": 20,
    "percentage": 75.0
  }
}
```

**Status Codes:**
- `200 OK` - Система работает
- `503 Service Unavailable` - Критические компоненты недоступны

---

### Mesh Network

#### `POST /mesh/beacon`

Отправка beacon в mesh network.

**Request:**
```json
{
  "node_id": "node-01",
  "timestamp": 1703779200000,
  "neighbors": ["node-02", "node-03"]
}
```

**Response:**
```json
{
  "accepted": true,
  "slot": 12345,
  "mttd_ms": 12.5,
  "offset_ms": 0.5
}
```

#### `GET /mesh/status`

Получение статуса mesh network.

**Response:**
```json
{
  "build_name": "yggdrasil",
  "build_version": "0.5.0",
  "uptime": 3600,
  "peers": 5,
  "routes": 10
}
```

#### `GET /mesh/peers`

Получение списка peers.

**Response:**
```json
[
  {
    "address": "200:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx",
    "port": 12345,
    "uptime": 3600
  }
]
```

#### `GET /mesh/routes`

Получение маршрутов mesh network.

**Response:**
```json
[
  {
    "destination": "200:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx",
    "via": "200:yyyy:yyyy:yyyy:yyyy:yyyy:yyyy:yyyy",
    "hops": 2
  }
]
```

---

### AI/ML

#### `GET /ai/predict/{target_node_id}`

Предсказание аномалии для узла.

**Parameters:**
- `target_node_id` (path) - ID целевого узла

**Response:**
```json
{
  "prediction": {
    "is_anomaly": false,
    "score": 0.15,
    "confidence": 0.85
  },
  "model_metrics": {
    "recall": 0.92,
    "accuracy": 0.88
  },
  "model_config": {
    "quantization": "FP32"
  }
}
```

---

### DAO Governance

#### `POST /dao/vote`

Голосование с поддержкой quadratic voting.

**Request:**
```json
{
  "proposal_id": "1",
  "voter_id": "voter-01",
  "tokens": 100,
  "vote": true
}
```

**Response:**
```json
{
  "recorded": true,
  "voting_power": 10.0,
  "tokens": 100,
  "quadratic": true,
  "proposal_id": "1"
}
```

**Quadratic Voting:**
- `voting_power = sqrt(tokens)`
- Снижает влияние крупных держателей токенов

---

### Security

#### `POST /security/handshake`

Post-Quantum handshake.

**Request:**
```json
{
  "node_id": "node-01",
  "algorithm": "hybrid"
}
```

**Headers:**
- `X-Forwarded-Tls-Client-Cert` - mTLS client certificate (production)

**Response:**
```json
{
  "status": "handshake_initiated",
  "algorithm": "NTRU+ECDSA",
  "security_level": "NIST_L3"
}
```

**Status Codes:**
- `200 OK` - Handshake успешен
- `403 Forbidden` - Невалидный сертификат
- `500 Internal Server Error` - mTLS controller не инициализирован

---

### Metrics

#### `GET /metrics`

Prometheus metrics endpoint.

**Response:**
```
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 52428800

# HELP mesh_mttd_seconds_bucket Mean Time To Detect buckets
# TYPE mesh_mttd_seconds_bucket histogram
mesh_mttd_seconds_bucket{le="0.001"} 10
mesh_mttd_seconds_bucket{le="0.005"} 50
mesh_mttd_seconds_bucket{le="+Inf"} 60

# HELP gnn_recall_score Current model recall
# TYPE gnn_recall_score gauge
gnn_recall_score 0.92
```

---

## 🔒 Security

### Post-Quantum Cryptography

- **KEM:** ML-KEM-768 (NIST Level 3)
- **Signatures:** ML-DSA-65 (NIST Level 3)
- **Backend:** LibOQS (обязательно в production)

### Zero Trust

- **SPIFFE/SPIRE:** Обязательно в production
- **mTLS:** Все соединения защищены
- **Workload Identity:** Автоматическая аутентификация

---

## ⚠️ Error Handling

### Standard Error Response

```json
{
  "detail": "Error message"
}
```

### Status Codes

- `200 OK` - Успешный запрос
- `400 Bad Request` - Невалидный запрос
- `401 Unauthorized` - Требуется аутентификация
- `403 Forbidden` - Доступ запрещён
- `404 Not Found` - Ресурс не найден
- `422 Unprocessable Entity` - Валидация не пройдена
- `500 Internal Server Error` - Внутренняя ошибка сервера
- `503 Service Unavailable` - Сервис недоступен

---

## 📝 Examples

### cURL

```bash
# Health check
curl http://localhost:8080/health

# Send beacon
curl -X POST http://localhost:8080/mesh/beacon \
  -H "Content-Type: application/json" \
  -d '{"node_id":"node-01","timestamp":1703779200000,"neighbors":[]}'

# Predict anomaly
curl http://localhost:8080/ai/predict/node-01

# Cast vote
curl -X POST http://localhost:8080/dao/vote \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"1","voter_id":"voter-01","tokens":100,"vote":true}'
```

### Python

```python
import httpx

async with httpx.AsyncClient() as client:
    # Health check
    response = await client.get("http://localhost:8080/health")
    print(response.json())
    
    # Send beacon
    response = await client.post(
        "http://localhost:8080/mesh/beacon",
        json={
            "node_id": "node-01",
            "timestamp": 1703779200000,
            "neighbors": []
        }
    )
    print(response.json())
```

---

## 🔄 Rate Limiting

- **Default:** 100 requests/second per IP
- **Burst:** 200 requests/second
- **Headers:**
  - `X-RateLimit-Limit` - Лимит запросов
  - `X-RateLimit-Remaining` - Оставшиеся запросы
  - `X-RateLimit-Reset` - Время сброса лимита

---

## 📊 Monitoring

### Health Endpoint

Мониторинг через `/health` endpoint:

```bash
# Check health
curl http://localhost:8080/health | jq .component_stats
```

### Metrics Endpoint

Prometheus metrics через `/metrics` endpoint:

```bash
# Scrape metrics
curl http://localhost:8080/metrics
```

---

**Mesh обновлён. API reference готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

