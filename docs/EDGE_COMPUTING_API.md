# Edge Computing API Documentation

## Overview

The Edge Computing API provides distributed computing capabilities across edge nodes. It enables task distribution, edge caching, and node management for low-latency processing at the network edge.

**Base URL:** `/edge`

**Version:** 3.3.0

**OpenAPI Specification:** [`docs/api/edge_openapi.yaml`](api/edge_openapi.yaml)

---

## Features

- **Edge Node Management**: Register, deregister, and monitor edge nodes
- **Task Distribution**: Submit, track, and cancel tasks across edge nodes
- **Edge Caching**: Distributed cache with TTL and tag-based invalidation
- **Health Monitoring**: Real-time health status of edge infrastructure
- **Resilience Integration**: Built-in rate limiting, bulkhead isolation, and circuit breakers

---

## Authentication

All endpoints require authentication via Bearer token:

```http
Authorization: Bearer <token>
```

---

## Endpoints

### Edge Nodes

#### List Edge Nodes

```http
GET /edge/nodes
```

List all registered edge nodes with optional filtering.

**Query Parameters:**

| Parameter | Type   | Description                    |
|-----------|--------|--------------------------------|
| status    | string | Filter by node status          |
| capability| string | Filter by required capability  |

**Response:**

```json
{
  "nodes": [
    {
      "node_id": "edge-node-001",
      "name": "us-west-edge-1",
      "endpoint": "https://edge1.example.com:8443",
      "status": "active",
      "capabilities": ["gpu", "inference", "storage"],
      "current_tasks": 5,
      "max_concurrent_tasks": 20,
      "registered_at": "2026-02-20T10:00:00Z",
      "last_heartbeat": "2026-02-20T13:25:00Z"
    }
  ],
  "total": 1
}
```

---

#### Register Edge Node

```http
POST /edge/nodes
```

Register a new edge node for task distribution.

**Request Body:**

```json
{
  "endpoint": "https://edge1.example.com:8443",
  "name": "us-west-edge-1",
  "capabilities": ["gpu", "inference", "storage"],
  "max_concurrent_tasks": 20,
  "metadata": {
    "region": "us-west-2",
    "zone": "a"
  }
}
```

**Response:** `201 Created`

```json
{
  "node_id": "edge-node-001",
  "name": "us-west-edge-1",
  "endpoint": "https://edge1.example.com:8443",
  "status": "active",
  "capabilities": ["gpu", "inference", "storage"],
  "current_tasks": 0,
  "max_concurrent_tasks": 20,
  "registered_at": "2026-02-20T13:30:00Z",
  "last_heartbeat": null,
  "resources": null
}
```

---

#### Get Edge Node

```http
GET /edge/nodes/{node_id}
```

Get details of a specific edge node.

---

#### Deregister Edge Node

```http
DELETE /edge/nodes/{node_id}
```

Deregister an edge node. Returns `204 No Content` on success.

---

#### Drain Edge Node

```http
POST /edge/nodes/{node_id}/drain
```

Put a node in draining mode. No new tasks will be assigned.

**Response:**

```json
{
  "status": "draining",
  "pending_tasks": 3
}
```

---

#### Get Node Resources

```http
GET /edge/nodes/{node_id}/resources
```

Get current resource metrics for a node.

**Response:**

```json
{
  "cpu_percent": 45.5,
  "memory_percent": 62.3,
  "disk_percent": 35.0,
  "network_mbps": 150.2,
  "gpu_percent": 80.0,
  "load_average": [1.5, 1.2, 1.0],
  "available_memory_mb": 4096,
  "total_memory_mb": 8192
}
```

---

### Task Distribution

#### Submit Task

```http
POST /edge/tasks
```

Submit a task for distribution to an appropriate edge node.

**Request Body:**

```json
{
  "type": "inference",
  "payload": {
    "model": "llama-3-70b",
    "prompt": "Hello, world!",
    "max_tokens": 100
  },
  "priority": "normal",
  "required_capabilities": ["gpu", "inference"],
  "timeout_seconds": 300,
  "retry_count": 3,
  "metadata": {
    "user_id": "user-123"
  }
}
```

**Response:** `202 Accepted`

```json
{
  "task_id": "task-uuid-here",
  "node_id": "edge-node-001",
  "status": "queued",
  "submitted_at": "2026-02-20T13:30:00Z",
  "estimated_start": "2026-02-20T13:30:05Z"
}
```

---

#### Get Task Status

```http
GET /edge/tasks/{task_id}
```

Get the current status of a submitted task.

**Response:**

```json
{
  "task_id": "task-uuid-here",
  "node_id": "edge-node-001",
  "status": "running",
  "progress": 45.5,
  "started_at": "2026-02-20T13:30:05Z",
  "completed_at": null,
  "error": null
}
```

**Task Statuses:**

| Status    | Description                           |
|-----------|---------------------------------------|
| queued    | Task is waiting for available node    |
| running   | Task is currently executing           |
| completed | Task finished successfully            |
| failed    | Task execution failed                 |
| cancelled | Task was cancelled by user            |

---

#### Cancel Task

```http
DELETE /edge/tasks/{task_id}
```

Cancel a submitted task.

**Response:**

```json
{
  "status": "cancelled"
}
```

---

#### Get Task Result

```http
GET /edge/tasks/{task_id}/result
```

Get the result of a completed task.

**Response:**

```json
{
  "task_id": "task-uuid-here",
  "status": "completed",
  "result": {
    "output": "Generated text here...",
    "tokens_used": 85
  },
  "error": null,
  "execution_time_ms": 1250,
  "node_id": "edge-node-001"
}
```

---

#### Submit Batch Tasks

```http
POST /edge/tasks/batch
```

Submit multiple tasks in a single request.

**Request Body:**

```json
{
  "tasks": [
    {"type": "inference", "payload": {...}},
    {"type": "inference", "payload": {...}}
  ],
  "strategy": "round_robin"
}
```

**Response:** `202 Accepted`

```json
{
  "batch_id": "batch-uuid-here",
  "task_ids": ["task-1", "task-2"]
}
```

---

### Distribution Strategy

#### Get Distribution Strategy

```http
GET /edge/distribution/strategy
```

Get the current task distribution strategy.

**Response:**

```json
{
  "strategy": "adaptive",
  "config": {
    "load_balance_threshold": 0.8,
    "capability_matching": true
  }
}
```

**Available Strategies:**

| Strategy     | Description                                    |
|--------------|------------------------------------------------|
| round_robin  | Distribute tasks in round-robin fashion        |
| least_loaded | Route to node with lowest load                 |
| capability   | Match task requirements to node capabilities   |
| latency      | Route to node with lowest latency              |
| adaptive     | Dynamically select best strategy               |

---

#### Set Distribution Strategy

```http
PUT /edge/distribution/strategy
```

Update the distribution strategy.

**Request Body:**

```json
{
  "strategy": "least_loaded",
  "config": {
    "load_balance_threshold": 0.7
  }
}
```

---

### Edge Cache

#### Get Cache Statistics

```http
GET /edge/cache
```

Get cache statistics and metrics.

**Response:**

```json
{
  "size": 5000,
  "max_size": 10000,
  "hit_rate": 0.85,
  "miss_rate": 0.15,
  "evictions": 120,
  "memory_used_mb": 256
}
```

---

#### Get Cached Value

```http
GET /edge/cache/{key}
```

Retrieve a cached value.

**Response:**

```json
{
  "key": "user:123:profile",
  "value": {"name": "John", "email": "john@example.com"},
  "ttl_seconds": 300,
  "created_at": "2026-02-20T13:25:00Z"
}
```

---

#### Set Cached Value

```http
PUT /edge/cache/{key}
```

Store a value in the edge cache.

**Request Body:**

```json
{
  "value": {"name": "John", "email": "john@example.com"},
  "ttl_seconds": 300,
  "tags": ["user", "profile"]
}
```

---

#### Delete Cached Value

```http
DELETE /edge/cache/{key}
```

Delete a cached value. Returns `204 No Content`.

---

#### Invalidate Cache

```http
POST /edge/cache/invalidate
```

Invalidate cache entries by pattern or tags.

**Request Body:**

```json
{
  "pattern": "user:*:profile",
  "tags": ["profile"]
}
```

**Response:**

```json
{
  "invalidated_count": 50
}
```

---

### Health Monitoring

#### Get Edge Health

```http
GET /edge/health
```

Get overall edge computing health status.

**Response:**

```json
{
  "healthy": true,
  "timestamp": "2026-02-20T13:30:00Z",
  "nodes": {
    "total": 5,
    "active": 4,
    "inactive": 1,
    "draining": 0
  },
  "tasks": {
    "queued": 10,
    "running": 25,
    "completed_today": 1500
  },
  "cache": {
    "hit_rate": 0.85,
    "size": 5000
  }
}
```

---

#### Get Nodes Health

```http
GET /edge/health/nodes
```

Get health status of all nodes.

**Response:**

```json
{
  "healthy": 4,
  "unhealthy": 1,
  "draining": 0,
  "nodes": [
    {
      "node_id": "edge-node-001",
      "healthy": true,
      "last_heartbeat": "2026-02-20T13:29:55Z"
    }
  ]
}
```

---

## Resilience Patterns

The Edge Computing API integrates the following resilience patterns:

### Rate Limiting

- **Token Bucket** algorithm with 100 requests capacity
- **Refill rate**: 20 requests/second
- **Response**: `429 Too Many Requests` when exceeded

### Bulkhead Isolation

| Bulkhead          | Max Concurrent |
|-------------------|----------------|
| node_operations   | 10             |
| task_operations   | 20             |
| cache_operations  | 50             |

When bulkhead is full: `503 Service Unavailable`

### Circuit Breaker

- **Failure threshold**: 3 failures
- **Recovery timeout**: 30 seconds
- **Success threshold**: 2 successes

When circuit is open, degraded responses are returned for node resources.

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid request: missing required field 'type'"
}
```

### 404 Not Found

```json
{
  "detail": "Node edge-node-001 not found"
}
```

### 429 Too Many Requests

```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "retry_after": 2.5
  }
}
```

### 503 Service Unavailable

```json
{
  "detail": "Node operations temporarily unavailable"
}
```

---

## SDK Examples

### Python

```python
import httpx

client = httpx.Client(base_url="https://api.example.com", headers={
    "Authorization": "Bearer <token>"
})

# Register edge node
response = client.post("/edge/nodes", json={
    "endpoint": "https://edge1.example.com:8443",
    "name": "us-west-edge-1",
    "capabilities": ["gpu", "inference"]
})
node = response.json()

# Submit task
response = client.post("/edge/tasks", json={
    "type": "inference",
    "payload": {"model": "llama-3", "prompt": "Hello"},
    "required_capabilities": ["gpu"]
})
task = response.json()

# Get result
result = client.get(f"/edge/tasks/{task['task_id']}/result")
```

### JavaScript

```javascript
const client = new ApiClient('https://api.example.com', {
  headers: { 'Authorization': 'Bearer <token>' }
});

// Register edge node
const node = await client.post('/edge/nodes', {
  endpoint: 'https://edge1.example.com:8443',
  name: 'us-west-edge-1',
  capabilities: ['gpu', 'inference']
});

// Submit task
const task = await client.post('/edge/tasks', {
  type: 'inference',
  payload: { model: 'llama-3', prompt: 'Hello' },
  required_capabilities: ['gpu']
});

// Get result
const result = await client.get(`/edge/tasks/${task.task_id}/result`);
```

---

## Configuration

Environment variables for Edge Computing:

| Variable                    | Default | Description                    |
|-----------------------------|---------|--------------------------------|
| EDGE_MAX_NODES              | 100     | Maximum edge nodes             |
| EDGE_TASK_TIMEOUT           | 300     | Default task timeout (seconds) |
| EDGE_CACHE_MAX_SIZE         | 10000   | Maximum cache entries          |
| EDGE_HEARTBEAT_INTERVAL     | 30      | Heartbeat interval (seconds)   |
| EDGE_RATE_LIMIT_CAPACITY    | 100     | Rate limit bucket capacity     |
| EDGE_RATE_LIMIT_REFILL      | 20      | Rate limit refill rate         |

---

## Changelog

### v3.3.0 (2026-02-20)

- Initial Edge Computing API release
- Node management endpoints
- Task distribution with multiple strategies
- Edge caching with TTL and tags
- Health monitoring
- Resilience patterns integration
