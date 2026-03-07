# Swarm Orchestration API

## Обзор
API для управления роем интеллектуальных агентов Kimi K2.5 в проекте x0tta6bl4.

## Endpoints

### `GET /api/v1/swarm/status`
Получение текущего статуса роя (количество активных агентов, загрузка PARL-контроллера).

**Response:**
```json
{
  "active_workers": 100,
  "queued_tasks": 0,
  "throughput_tps": 450.5
}
```

### `POST /api/v1/swarm/task`
Отправка новой задачи в рой на асинхронное выполнение.

**Request Body:**
```json
{
  "task_type": "route_optimization",
  "payload": {"mesh_id": "m123"},
  "priority": 1
}
```

**Response:**
```json
{
  "status": "accepted",
  "task_id": "api_task_route_optimization"
}
```
