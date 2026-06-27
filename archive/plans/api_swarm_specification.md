# API Specification для управления роем агентов

## Обзор

Расширение API x0tta6bl4 для управления роями агентов на базе Kimi K2.5.

## Базовый URL

```
/api/v3/swarm
```

## Endpoints

### 1. Создание роя

**POST** `/api/v3/swarm/create`

Создает новый рой агентов для выполнения задачи.

#### Request

```json
{
  "name": "mesh-optimization-swarm",
  "task_type": "mesh_optimization",
  "num_agents": 50,
  "capabilities": ["routing", "monitoring", "analysis"],
  "constraints": {
    "max_parallel_steps": 1500,
    "target_latency_ms": 100,
    "resource_limits": {
      "cpu_cores": 8,
      "memory_gb": 16
    }
  },
  "integration_targets": ["mesh_router", "mape_k", "federated_learning"],
  "auto_terminate": true,
  "ttl_seconds": 3600
}
```

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "status": "initializing",
  "created_at": "2026-01-31T00:30:00Z",
  "estimated_ready_at": "2026-01-31T00:30:05Z",
  "agents": [
    {
      "agent_id": "agent_001",
      "role": "coordinator",
      "status": "starting"
    },
    {
      "agent_id": "agent_002",
      "role": "worker",
      "status": "starting"
    }
  ],
  "endpoints": {
    "status": "/api/v3/swarm/swarm_abc123xyz/status",
    "tasks": "/api/v3/swarm/swarm_abc123xyz/tasks",
    "agents": "/api/v3/swarm/swarm_abc123xyz/agents"
  }
}
```

#### Status Codes

- `201 Created` - Рой успешно создан
- `400 Bad Request` - Некорректные параметры
- `429 Too Many Requests` - Превышен лимит роев
- `503 Service Unavailable` - Недостаточно ресурсов

---

### 2. Получение статуса роя

**GET** `/api/v3/swarm/{swarm_id}/status`

Возвращает текущий статус роя и его агентов.

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "name": "mesh-optimization-swarm",
  "status": "active",
  "created_at": "2026-01-31T00:30:00Z",
  "started_at": "2026-01-31T00:30:05Z",
  "metrics": {
    "total_agents": 50,
    "active_agents": 48,
    "failed_agents": 0,
    "completed_tasks": 1250,
    "queued_tasks": 250,
    "parallelism_factor": 48,
    "throughput_tps": 450.5,
    "avg_latency_ms": 95.2
  },
  "performance": {
    "speedup_vs_sequential": 4.5,
    "resource_utilization": {
      "cpu_percent": 78.5,
      "memory_percent": 65.2
    }
  },
  "integrations": {
    "mesh_router": "connected",
    "mape_k": "connected",
    "federated_learning": "standby"
  }
}
```

#### Status Codes

- `200 OK` - Успешно
- `404 Not Found` - Рой не найден

---

### 3. Отправка задачи в рой

**POST** `/api/v3/swarm/{swarm_id}/tasks`

Отправляет задачу на выполнение роем агентов.

#### Request

```json
{
  "task_type": "route_optimization",
  "priority": "high",
  "payload": {
    "source_node": "node_001",
    "target_node": "node_100",
    "constraints": {
      "max_latency_ms": 50,
      "min_bandwidth_mbps": 100
    }
  },
  "parallelization": {
    "strategy": "split_by_segments",
    "num_subtasks": 10
  },
  "timeout_seconds": 30,
  "callback_url": "https://api.example.com/webhooks/task-complete"
}
```

#### Response

```json
{
  "task_id": "task_xyz789",
  "swarm_id": "swarm_abc123xyz",
  "status": "queued",
  "created_at": "2026-01-31T00:35:00Z",
  "estimated_start": "2026-01-31T00:35:01Z",
  "subtasks": [
    {
      "subtask_id": "subtask_001",
      "agent_id": "agent_003",
      "status": "pending"
    },
    {
      "subtask_id": "subtask_002",
      "agent_id": "agent_007",
      "status": "pending"
    }
  ],
  "progress": {
    "total": 10,
    "completed": 0,
    "failed": 0,
    "percent": 0
  }
}
```

#### Status Codes

- `202 Accepted` - Задача принята в обработку
- `404 Not Found` - Рой не найден
- `503 Service Unavailable` - Рой перегружен

---

### 4. Получение статуса задачи

**GET** `/api/v3/swarm/{swarm_id}/tasks/{task_id}`

Возвращает статус и результат выполнения задачи.

#### Response

```json
{
  "task_id": "task_xyz789",
  "swarm_id": "swarm_abc123xyz",
  "status": "completed",
  "created_at": "2026-01-31T00:35:00Z",
  "started_at": "2026-01-31T00:35:01Z",
  "completed_at": "2026-01-31T00:35:08Z",
  "duration_ms": 7000,
  "result": {
    "optimal_route": ["node_001", "node_015", "node_042", "node_100"],
    "estimated_latency_ms": 45,
    "bandwidth_mbps": 150
  },
  "subtasks": [
    {
      "subtask_id": "subtask_001",
      "agent_id": "agent_003",
      "status": "completed",
      "duration_ms": 6500,
      "result": {...}
    }
  ],
  "metrics": {
    "parallelism_used": 10,
    "speedup_vs_sequential": 4.2
  }
}
```

---

### 5. Список агентов в рое

**GET** `/api/v3/swarm/{swarm_id}/agents`

Возвращает список всех агентов в рое.

#### Query Parameters

- `status` - Фильтр по статусу (active, failed, idle)
- `role` - Фильтр по роли
- `limit` - Лимит результатов (default: 100)
- `offset` - Смещение для пагинации

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "total_agents": 50,
  "returned": 50,
  "agents": [
    {
      "agent_id": "agent_001",
      "role": "coordinator",
      "status": "active",
      "capabilities": ["task_distribution", "result_aggregation"],
      "metrics": {
        "tasks_completed": 150,
        "avg_task_duration_ms": 120,
        "success_rate": 0.98
      },
      "connected_at": "2026-01-31T00:30:05Z"
    },
    {
      "agent_id": "agent_002",
      "role": "worker",
      "status": "active",
      "capabilities": ["routing", "monitoring"],
      "metrics": {
        "tasks_completed": 45,
        "avg_task_duration_ms": 95,
        "success_rate": 1.0
      },
      "connected_at": "2026-01-31T00:30:06Z"
    }
  ]
}
```

---

### 6. Получение информации об агенте

**GET** `/api/v3/swarm/{swarm_id}/agents/{agent_id}`

Возвращает детальную информацию о конкретном агенте.

#### Response

```json
{
  "agent_id": "agent_001",
  "swarm_id": "swarm_abc123xyz",
  "role": "coordinator",
  "status": "active",
  "capabilities": ["task_distribution", "result_aggregation"],
  "policy": {
    "type": "ppo",
    "version": "v2.1",
    "last_updated": "2026-01-31T00:30:05Z"
  },
  "current_task": {
    "task_id": "task_abc456",
    "type": "route_optimization",
    "started_at": "2026-01-31T00:35:10Z",
    "progress_percent": 65
  },
  "metrics": {
    "tasks_completed": 150,
    "tasks_failed": 3,
    "avg_task_duration_ms": 120,
    "success_rate": 0.98,
    "total_execution_time_ms": 18000
  },
  "resource_usage": {
    "cpu_percent": 45.2,
    "memory_mb": 256,
    "network_io_mbps": 12.5
  }
}
```

---

### 7. Управление агентом

**POST** `/api/v3/swarm/{swarm_id}/agents/{agent_id}/control`

Управление состоянием агента (pause, resume, restart, terminate).

#### Request

```json
{
  "action": "pause",
  "reason": "maintenance",
  "duration_seconds": 300
}
```

#### Actions

- `pause` - Приостановить выполнение задач
- `resume` - Возобновить выполнение
- `restart` - Перезапустить агента
- `terminate` - Завершить агента

#### Response

```json
{
  "agent_id": "agent_001",
  "action": "pause",
  "status": "paused",
  "previous_status": "active",
  "paused_at": "2026-01-31T00:40:00Z",
  "resume_at": "2026-01-31T00:45:00Z"
}
```

---

### 8. Масштабирование роя

**POST** `/api/v3/swarm/{swarm_id}/scale`

Масштабирование роя (увеличение/уменьшение числа агентов).

#### Request

```json
{
  "action": "scale_up",
  "num_agents": 20,
  "capabilities": ["routing", "monitoring"],
  "reason": "increased_load"
}
```

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "action": "scale_up",
  "previous_count": 50,
  "new_count": 70,
  "scaling_status": "in_progress",
  "estimated_completion": "2026-01-31T00:42:00Z",
  "new_agents": [
    "agent_051",
    "agent_052",
    "..."
  ]
}
```

---

### 9. Визуальный анализ (Coding with Vision)

**POST** `/api/v3/swarm/{swarm_id}/vision/analyze`

Анализ изображения/скриншота роем агентов.

#### Request

```multipart/form-data```

- `image` - Файл изображения (PNG, JPG)
- `analysis_type` - Тип анализа (mesh_topology, routing_visualization, anomaly_detection)
- `context` - Дополнительный контекст (JSON)

#### Response

```json
{
  "analysis_id": "analysis_001",
  "swarm_id": "swarm_abc123xyz",
  "status": "completed",
  "image_processed": true,
  "results": {
    "detected_issues": [
      {
        "type": "bottleneck",
        "location": "node_015",
        "confidence": 0.95,
        "severity": "high"
      }
    ],
    "recommendations": [
      {
        "action": "reroute_traffic",
        "target": "node_015",
        "alternative_route": ["node_016", "node_017"]
      }
    ],
    "visualization": {
      "annotated_image_url": "/api/v3/swarm/swarm_abc123xyz/vision/analysis_001/image",
      "heatmap_url": "/api/v3/swarm/swarm_abc123xyz/vision/analysis_001/heatmap"
    }
  },
  "agents_used": 5,
  "processing_time_ms": 2500
}
```

---

### 10. Завершение роя

**DELETE** `/api/v3/swarm/{swarm_id}`

Завершение работы роя и освобождение ресурсов.

#### Request

```json
{
  "graceful": true,
  "timeout_seconds": 60,
  "force": false
}
```

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "status": "terminating",
  "termination_started_at": "2026-01-31T01:00:00Z",
  "estimated_completion": "2026-01-31T01:01:00Z",
  "active_tasks": 25,
  "termination_strategy": "graceful"
}
```

---

### 11. Список всех роев

**GET** `/api/v3/swarm`

Возвращает список всех активных роев.

#### Query Parameters

- `status` - Фильтр по статусу
- `task_type` - Фильтр по типу задачи
- `limit` - Лимит результатов
- `offset` - Смещение

#### Response

```json
{
  "total": 5,
  "swarms": [
    {
      "swarm_id": "swarm_abc123xyz",
      "name": "mesh-optimization-swarm",
      "status": "active",
      "task_type": "mesh_optimization",
      "num_agents": 50,
      "created_at": "2026-01-31T00:30:00Z"
    }
  ]
}
```

---

### 12. Получение метрик роя

**GET** `/api/v3/swarm/{swarm_id}/metrics`

Возвращает детальные метрики производительности роя.

#### Query Parameters

- `from` - Начало периода (ISO 8601)
- `to` - Конец периода (ISO 8601)
- `granularity` - Гранулярность (1m, 5m, 1h)

#### Response

```json
{
  "swarm_id": "swarm_abc123xyz",
  "period": {
    "from": "2026-01-31T00:00:00Z",
    "to": "2026-01-31T01:00:00Z"
  },
  "metrics": {
    "throughput": {
      "avg_tps": 450.5,
      "max_tps": 520.0,
      "min_tps": 380.0
    },
    "latency": {
      "avg_ms": 95.2,
      "p50_ms": 90.0,
      "p95_ms": 150.0,
      "p99_ms": 200.0
    },
    "parallelism": {
      "avg_active_agents": 48.5,
      "max_parallel_steps": 1500,
      "utilization_percent": 85.0
    },
    "speedup": {
      "vs_sequential": 4.5,
      "vs_baseline": 3.8
    }
  },
  "timeseries": [
    {
      "timestamp": "2026-01-31T00:05:00Z",
      "throughput_tps": 445.0,
      "latency_ms": 98.0,
      "active_agents": 48
    }
  ]
}
```

---

## Webhooks

### События

Рой может отправлять webhook-уведомления при следующих событиях:

- `swarm.created` - Рой создан
- `swarm.ready` - Рой готов к работе
- `swarm.terminated` - Рой завершен
- `task.completed` - Задача выполнена
- `task.failed` - Задача завершена с ошибкой
- `agent.failed` - Агент вышел из строя
- `scaling.completed` - Масштабирование завершено

### Формат webhook

```json
{
  "event": "task.completed",
  "timestamp": "2026-01-31T00:35:08Z",
  "swarm_id": "swarm_abc123xyz",
  "data": {
    "task_id": "task_xyz789",
    "status": "completed",
    "duration_ms": 7000
  }
}
```

## Аутентификация

Все endpoints требуют аутентификации через:

```
Authorization: Bearer <token>
X-Admin-Token: <admin_token>  # для административных операций
```

## Rate Limiting

- Создание роев: 10/minute
- Отправка задач: 1000/minute
- Получение статуса: 100/minute
- Масштабирование: 5/minute

## Ошибки

### Формат ошибки

```json
{
  "error": {
    "code": "SWARM_LIMIT_EXCEEDED",
    "message": "Maximum number of swarms (10) exceeded",
    "details": {
      "current": 10,
      "maximum": 10
    }
  }
}
```

### Коды ошибок

- `SWARM_NOT_FOUND` - Рой не найден
- `AGENT_NOT_FOUND` - Агент не найден
- `TASK_NOT_FOUND` - Задача не найдена
- `SWARM_LIMIT_EXCEEDED` - Превышен лимит роев
- `INSUFFICIENT_RESOURCES` - Недостаточно ресурсов
- `INVALID_CONFIGURATION` - Некорректная конфигурация
- `SCALING_IN_PROGRESS` - Масштабирование уже выполняется
- `VISION_ANALYSIS_FAILED` - Ошибка визуального анализа
