# API Reference

**Версия:** 3.3.0  
**Дата:** 2026-03-03  
**Базовый URL:** `http://localhost:8000`

---

## 📋 Обзор

REST API для x0tta6bl4 mesh network platform.

### Новые возможности v3.3.0

- **MAPE-K Self-Healing:** Автоматическое восстановление сети
- **Vision API:** Анализ топологии из изображений
- **AI Agents:** Оркестрация агентов мониторинга и healing
- **Circuit Breaker:** Защита от каскадных сбоев

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

## 🤖 MAPE-K Self-Healing

### `POST /mape/heal`

Ручной запуск healing действия.

**Request:**
```json
{
  "issue": "High latency detected",
  "context": {
    "target": "mesh-routing",
    "severity": "warning"
  }
}
```

**Response:**
```json
{
  "success": true,
  "actions_executed": 2,
  "mttr_seconds": 1.2
}
```

### `GET /mape/status`

Получение статуса MAPE-K orchestrator.

**Response:**
```json
{
  "is_healthy": true,
  "circuit_breaker_state": "closed",
  "total_healing_actions": 15,
  "successful_healings": 14,
  "success_rate": 0.93,
  "avg_mttr_seconds": 2.5
}
```

### `GET /mape/metrics`

Метрики self-healing.

**Response:**
```json
{
  "healing_actions": {
    "re_route": 10,
    "scale_up": 3,
    "clear_cache": 2
  },
  "mttr_by_severity": {
    "critical": 1.2,
    "warning": 3.5
  }
}
```

---

## 👁 Vision API

### `POST /vision/analyze`

Анализ топологии сети из изображения.

**Request:**
```json
{
  "image_url": "http://example.com/topology.png"
}
```

или

```json
{
  "image_data": "<base64 encoded image>"
}
```

**Response:**
```json
{
  "status": "success",
  "nodes_detected": 15,
  "links_detected": 32,
  "metrics": {
    "avg_centrality": 0.45,
    "resilience_score": 0.82,
    "bottlenecks": [
      {
        "node_id": "node_015",
        "centrality": 0.95,
        "health_score": 0.3
      }
    ],
    "isolated_nodes": ["node_offline_1"]
  },
  "recommendations": [
    {"action": "add_redundant_link", "target": "node_015"}
  ]
}
```

---

## 🤖 AI Agents

### `GET /agents/status`

Получение статуса всех AI Agents.

**Response:**
```json
{
  "is_running": true,
  "agents": {
    "health_monitor": true,
    "log_analyzer": true,
    "auto_healer": true,
    "spec_to_code": true,
    "documentation": true
  },
  "health_monitor_status": {
    "services_monitored": 5,
    "alerts_generated": 3
  },
  "auto_healer_status": {
    "healing_incidents": 10,
    "successful_healings": 9
  }
}
```

### `POST /agents/analyze-logs`

Анализ логов через Log Analyzer Agent.

**Request:**
```json
{
  "logs": [
    "ERROR: Connection timeout to node-1",
    "WARN: High memory usage on node-2"
  ]
}
```

**Response:**
```json
{
  "issues_detected": 2,
  "root_cause": "Network connectivity issues in zone east",
  "recommended_actions": [
    "restart_network_service",
    "check_firewall_rules"
  ]
}
```

---

## 📡 Endpoints

### Health Check

#### `GET /health`

Проверка статуса системы и компонентов.

**Response:**
```json
{
  "status": "ok",
  "version": "3.3.0",
  "components": {
    "graphsage": true,
    "causal_analysis": true,
    "fl_coordinator": true,
    "spiffe": true,
    "mape_orchestrator": true,
    "vision_api": true
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

# HELP mape_healing_actions_total Total healing actions
# TYPE mape_healing_actions_total counter
mape_healing_actions_total 15

# HELP mape_mttr_seconds Mean Time To Recovery
# TYPE mape_mttr_seconds gauge
mape_mttr_seconds 2.5
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

### Circuit Breaker

MAPE-K включает Circuit Breaker для предотвращения каскадных сбоев:

- **failure_threshold:** 5 последовательных ошибок
- **recovery_timeout:** 60 секунд
- **half_open_max_calls:** 3 пробных вызова

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
- `429 Too Many Requests` - Превышен rate limit
- `500 Internal Server Error` - Внутренняя ошибка сервера
- `503 Service Unavailable` - Сервис недоступен

---

## 📝 Examples

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Send beacon
curl -X POST http://localhost:8000/mesh/beacon \
  -H "Content-Type: application/json" \
  -d '{"node_id":"node-01","timestamp":1703779200000,"neighbors":[]}'

# Trigger healing
curl -X POST http://localhost:8000/mape/heal \
  -H "Content-Type: application/json" \
  -d '{"issue":"High latency","context":{"target":"mesh"}}'

# Analyze topology
curl -X POST http://localhost:8000/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{"image_url":"http://example.com/topology.png"}'

# Get agents status
curl http://localhost:8000/agents/status
```

### Python

```python
import httpx

async with httpx.AsyncClient() as client:
    # Health check
    response = await client.get("http://localhost:8000/health")
    print(response.json())
    
    # Send beacon
    response = await client.post(
        "http://localhost:8000/mesh/beacon",
        json={
            "node_id": "node-01",
            "timestamp": 1703779200000,
            "neighbors": []
        }
    )
    print(response.json())
    
    # Trigger healing
    response = await client.post(
        "http://localhost:8000/mape/heal",
        json={
            "issue": "High latency",
            "context": {"target": "mesh"}
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
curl http://localhost:8000/health | jq .component_stats
```

### Metrics Endpoint

Prometheus metrics через `/metrics` endpoint:

```bash
# Scrape metrics
curl http://localhost:8000/metrics
```

### Self-Healing Monitoring

```bash
# Check MAPE-K status
curl http://localhost:8000/mape/status

# Get healing metrics
curl http://localhost:8000/mape/metrics
```

---

**Mesh обновлён. API reference готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**
