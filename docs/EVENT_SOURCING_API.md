# Event Sourcing API Documentation

## Overview

The Event Sourcing API provides a complete CQRS (Command Query Responsibility Segregation) and Event Sourcing implementation. It enables building event-driven systems with full audit trails, temporal queries, and eventual consistency.

**Base URL:** `/events`

**Version:** 3.3.0

**OpenAPI Specification:** [`docs/api/event_sourcing_openapi.yaml`](api/event_sourcing_openapi.yaml)

---

## Features

- **Event Store**: Append-only log with optimistic concurrency control
- **Command Bus**: Command handling with validation and event production
- **Query Bus**: Query execution with caching support
- **Projections**: Read models built from event streams
- **Aggregates**: Domain-driven design aggregate roots
- **WebSocket Subscriptions**: Real-time event streaming
- **Resilience Integration**: Rate limiting, bulkhead isolation, circuit breakers

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Command Bus   │    Query Bus    │      Event Store            │
│   (Write)       │    (Read)       │      (Event Log)            │
├─────────────────┴─────────────────┴─────────────────────────────┤
│                     Projections                                  │
│              (Read Models from Events)                           │
├─────────────────────────────────────────────────────────────────┤
│                     Aggregates                                   │
│              (Domain Logic & State)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication

All endpoints require authentication via Bearer token:

```http
Authorization: Bearer <token>
```

---

## Endpoints

### Event Store

#### List Streams

```http
GET /events/streams
```

List all event streams.

**Query Parameters:**

| Parameter | Type   | Description                    |
|-----------|--------|--------------------------------|
| prefix    | string | Filter by stream ID prefix     |
| limit     | int    | Maximum results (default: 100) |

**Response:**

```json
{
  "streams": [
    {
      "stream_id": "user-123",
      "version": 5,
      "event_count": 5,
      "created_at": "2026-02-20T10:00:00Z",
      "updated_at": "2026-02-20T13:30:00Z"
    }
  ]
}
```

---

#### Get Stream Events

```http
GET /events/streams/{stream_id}
```

Get events from a specific stream.

**Query Parameters:**

| Parameter    | Type | Description                          |
|--------------|------|--------------------------------------|
| from_version | int  | Start from version (default: 0)      |
| to_version   | int  | End at version (optional)            |
| limit        | int  | Maximum events (default: 100)        |

**Response:**

```json
{
  "stream_id": "user-123",
  "version": 5,
  "events": [
    {
      "event_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "UserCreated",
      "stream_id": "user-123",
      "version": 1,
      "timestamp": "2026-02-20T10:00:00Z",
      "payload": {
        "email": "user@example.com",
        "name": "John Doe"
      },
      "metadata": {
        "correlation_id": "abc-123",
        "causation_id": "def-456"
      }
    }
  ]
}
```

---

#### Append Events

```http
POST /events/streams/{stream_id}/append
```

Append events to a stream with optimistic concurrency control.

**Request Body:**

```json
{
  "events": [
    {
      "event_type": "UserEmailChanged",
      "payload": {
        "old_email": "user@example.com",
        "new_email": "newemail@example.com"
      },
      "metadata": {
        "reason": "user_request"
      }
    }
  ],
  "expected_version": 5
}
```

**Response:**

```json
{
  "stream_id": "user-123",
  "new_version": 6,
  "appended_count": 1
}
```

**Concurrency Control:**

- If `expected_version` is provided, the append will fail if the stream version doesn't match
- Returns `409 Conflict` on version mismatch:

```json
{
  "detail": {
    "error": "Version conflict",
    "expected_version": 5,
    "actual_version": 7
  }
}
```

---

#### Get Snapshot

```http
GET /events/streams/{stream_id}/snapshot
```

Get the latest snapshot for a stream.

**Response:**

```json
{
  "stream_id": "user-123",
  "version": 100,
  "state": {
    "email": "user@example.com",
    "name": "John Doe",
    "status": "active"
  },
  "timestamp": "2026-02-20T13:00:00Z"
}
```

---

#### Create Snapshot

```http
POST /events/streams/{stream_id}/snapshot
```

Create a snapshot at the current or specified version.

**Query Parameters:**

| Parameter | Type | Description                    |
|-----------|------|--------------------------------|
| version   | int  | Version to snapshot (optional) |

**Response:** `201 Created`

---

#### Get All Events

```http
GET /events/events
```

Get events from all streams (global event log).

**Query Parameters:**

| Parameter      | Type     | Description                    |
|----------------|----------|--------------------------------|
| event_type     | string   | Filter by event type           |
| from_timestamp | datetime | Start timestamp (ISO 8601)     |
| to_timestamp   | datetime | End timestamp (ISO 8601)       |
| limit          | int      | Maximum events (default: 100)  |

---

### WebSocket Subscriptions

#### Subscribe to Events

```websocket
WS /events/events/subscribe
```

Subscribe to real-time event notifications.

**Subscribe Message:**

```json
{
  "type": "subscribe",
  "stream_id": "user-123",
  "event_types": ["UserCreated", "UserUpdated", "UserDeleted"]
}
```

**Event Message:**

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "UserUpdated",
  "stream_id": "user-123",
  "version": 6,
  "timestamp": "2026-02-20T13:30:00Z",
  "payload": {
    "field": "email",
    "old_value": "old@example.com",
    "new_value": "new@example.com"
  }
}
```

---

### Command Bus

#### Execute Command

```http
POST /events/commands
```

Execute a command through the command bus.

**Request Body:**

```json
{
  "command_id": "optional-uuid",
  "command_type": "CreateUser",
  "payload": {
    "email": "newuser@example.com",
    "name": "Jane Doe"
  },
  "metadata": {
    "user_id": "admin-123",
    "correlation_id": "req-abc-123"
  }
}
```

**Response:**

```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "result": {
    "user_id": "user-456",
    "created_at": "2026-02-20T13:30:00Z"
  },
  "error": null,
  "events_produced": 1,
  "execution_time_ms": 15
}
```

---

#### Execute Batch Commands

```http
POST /events/commands/batch
```

Execute multiple commands in sequence.

**Request Body:**

```json
{
  "commands": [
    {
      "command_type": "CreateUser",
      "payload": {"email": "user1@example.com"}
    },
    {
      "command_type": "CreateUser",
      "payload": {"email": "user2@example.com"}
    }
  ],
  "atomic": false
}
```

**Response:**

```json
{
  "results": [
    {
      "command_id": "...",
      "success": true,
      "result": {"user_id": "user-1"},
      "error": null,
      "events_produced": 1,
      "execution_time_ms": 10
    }
  ],
  "success_count": 2,
  "failure_count": 0
}
```

---

#### List Command Handlers

```http
GET /events/commands/handlers
```

List all registered command handlers.

**Response:**

```json
{
  "handlers": [
    {
      "command_type": "CreateUser",
      "handler_name": "create_user_handler",
      "registered_at": null
    }
  ]
}
```

---

### Query Bus

#### Execute Query

```http
POST /events/queries
```

Execute a query through the query bus.

**Request Body:**

```json
{
  "query_id": "optional-uuid",
  "query_type": "GetUserByEmail",
  "parameters": {
    "email": "user@example.com"
  },
  "options": {
    "use_cache": true,
    "cache_ttl": 300
  }
}
```

**Response:**

```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "user_id": "user-123",
    "email": "user@example.com",
    "name": "John Doe",
    "status": "active"
  },
  "from_cache": false,
  "execution_time_ms": 5
}
```

---

#### Get Query Cache Stats

```http
GET /events/queries/cache
```

Get query cache statistics.

**Response:**

```json
{
  "size": 500,
  "max_size": 1000,
  "hit_rate": 0.85,
  "miss_rate": 0.15,
  "evictions": 50
}
```

---

#### Invalidate Query Cache

```http
POST /events/queries/cache/invalidate
```

Invalidate query cache entries.

**Request Body:**

```json
{
  "query_type": "GetUserByEmail",
  "all": false
}
```

**Response:**

```json
{
  "invalidated_count": 25
}
```

---

### Projections

#### List Projections

```http
GET /events/projections
```

List all registered projections.

**Response:**

```json
{
  "projections": [
    {
      "name": "UserSummary",
      "status": "running",
      "position": 1500,
      "events_processed": 1500,
      "last_event_timestamp": "2026-02-20T13:30:00Z"
    }
  ]
}
```

**Projection Statuses:**

| Status    | Description                           |
|-----------|---------------------------------------|
| running   | Projection is actively processing     |
| paused    | Projection is paused                  |
| stopped   | Projection is stopped                 |
| error     | Projection encountered an error       |
| resetting | Projection is being rebuilt           |

---

#### Get Projection Status

```http
GET /events/projections/{projection_name}
```

Get detailed status of a projection.

**Response:**

```json
{
  "name": "UserSummary",
  "status": "running",
  "position": 1500,
  "events_processed": 1500,
  "last_event_timestamp": "2026-02-20T13:30:00Z",
  "lag": 5,
  "error": null,
  "started_at": "2026-02-20T10:00:00Z"
}
```

---

#### Reset Projection

```http
POST /events/projections/{projection_name}/reset
```

Reset and rebuild a projection from the beginning.

**Response:**

```json
{
  "status": "resetting",
  "started_at": "2026-02-20T13:35:00Z"
}
```

---

#### Pause Projection

```http
POST /events/projections/{projection_name}/pause
```

Pause a running projection.

**Response:**

```json
{
  "status": "paused"
}
```

---

#### Resume Projection

```http
POST /events/projections/{projection_name}/resume
```

Resume a paused projection.

**Response:**

```json
{
  "status": "running"
}
```

---

### Aggregates

#### Get Aggregate State

```http
GET /events/aggregates/{aggregate_type}/{aggregate_id}
```

Get the current state of an aggregate.

**Response:**

```json
{
  "aggregate_type": "User",
  "aggregate_id": "user-123",
  "version": 5,
  "state": {
    "email": "user@example.com",
    "name": "John Doe",
    "status": "active",
    "created_at": "2026-02-20T10:00:00Z"
  },
  "created_at": "2026-02-20T10:00:00Z",
  "updated_at": "2026-02-20T13:30:00Z"
}
```

---

#### Get Aggregate History

```http
GET /events/aggregates/{aggregate_type}/{aggregate_id}/history
```

Get the full event history of an aggregate.

**Response:**

```json
{
  "aggregate_type": "User",
  "aggregate_id": "user-123",
  "events": [
    {
      "event_id": "...",
      "event_type": "UserCreated",
      "version": 1,
      "timestamp": "2026-02-20T10:00:00Z",
      "payload": {...}
    },
    {
      "event_id": "...",
      "event_type": "UserEmailChanged",
      "version": 2,
      "timestamp": "2026-02-20T11:00:00Z",
      "payload": {...}
    }
  ]
}
```

---

## Resilience Patterns

The Event Sourcing API integrates the following resilience patterns:

### Rate Limiting

- **Token Bucket** algorithm with 200 requests capacity
- **Refill rate**: 50 requests/second
- **Response**: `429 Too Many Requests` when exceeded

### Bulkhead Isolation

| Bulkhead            | Max Concurrent |
|---------------------|----------------|
| event_operations    | 20             |
| command_operations  | 30             |
| query_operations    | 50             |

When bulkhead is full: `503 Service Unavailable`

### Circuit Breaker (Projections)

- **Failure threshold**: 5 failures
- **Recovery timeout**: 60 seconds
- **Success threshold**: 3 successes

When circuit is open: `503 Service Unavailable`

### Query Fallback

- **Cache Fallback** with 300-second TTL
- Returns cached results when query execution fails

---

## Event Types

### Standard Event Metadata

Every event includes standard metadata:

```json
{
  "event_id": "uuid",
  "event_type": "EventType",
  "stream_id": "stream-identifier",
  "version": 1,
  "timestamp": "2026-02-20T13:30:00Z",
  "payload": {},
  "metadata": {
    "correlation_id": "uuid",
    "causation_id": "uuid",
    "user_id": "user-123",
    "source": "api"
  }
}
```

### Common Event Types

| Event Type         | Description                    |
|--------------------|--------------------------------|
| EntityCreated      | New entity created             |
| EntityUpdated      | Entity properties changed      |
| EntityDeleted      | Entity removed                 |
| StateChanged       | State transition occurred      |
| CommandExecuted    | Command completed              |

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid event type: UnknownEvent"
}
```

### 404 Not Found

```json
{
  "detail": "Stream user-123 not found"
}
```

### 409 Conflict

```json
{
  "detail": {
    "error": "Version conflict",
    "expected_version": 5,
    "actual_version": 7
  }
}
```

### 429 Too Many Requests

```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "retry_after": 1.5
  }
}
```

### 503 Service Unavailable

```json
{
  "detail": "Event operations temporarily unavailable"
}
```

---

## SDK Examples

### Python

```python
import httpx
import asyncio

client = httpx.AsyncClient(base_url="https://api.example.com", headers={
    "Authorization": "Bearer <token>"
})

# Append events
response = await client.post("/events/streams/user-123/append", json={
    "events": [
        {
            "event_type": "UserCreated",
            "payload": {"email": "user@example.com", "name": "John"}
        }
    ]
})

# Execute command
response = await client.post("/events/commands", json={
    "command_type": "CreateUser",
    "payload": {"email": "new@example.com", "name": "Jane"}
})
command_result = response.json()

# Execute query
response = await client.post("/events/queries", json={
    "query_type": "GetUserByEmail",
    "parameters": {"email": "user@example.com"}
})
user = response.json()

# WebSocket subscription
import websockets

async def subscribe():
    async with websockets.connect(
        "wss://api.example.com/events/events/subscribe",
        extra_headers={"Authorization": "Bearer <token>"}
    ) as ws:
        await ws.send_json({
            "type": "subscribe",
            "event_types": ["UserCreated", "UserUpdated"]
        })
        
        async for message in ws:
            event = json.loads(message)
            print(f"Received: {event['event_type']}")

asyncio.run(subscribe())
```

### JavaScript

```javascript
const client = new ApiClient('https://api.example.com', {
  headers: { 'Authorization': 'Bearer <token>' }
});

// Append events
await client.post('/events/streams/user-123/append', {
  events: [
    {
      event_type: 'UserCreated',
      payload: { email: 'user@example.com', name: 'John' }
    }
  ]
});

// Execute command
const result = await client.post('/events/commands', {
  command_type: 'CreateUser',
  payload: { email: 'new@example.com', name: 'Jane' }
});

// Execute query
const user = await client.post('/events/queries', {
  query_type: 'GetUserByEmail',
  parameters: { email: 'user@example.com' }
});

// WebSocket subscription
const ws = new WebSocket('wss://api.example.com/events/events/subscribe');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    event_types: ['UserCreated', 'UserUpdated']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data.event_type);
};
```

---

## Best Practices

### Event Design

1. **Events should be immutable** - Never modify an event after it's been stored
2. **Use past tense naming** - `UserCreated`, `EmailChanged`, not `CreateUser`
3. **Include all relevant data** - Events should be self-contained
4. **Version your events** - Use schema versioning for backward compatibility

### Stream Design

1. **One stream per aggregate** - Keep related events together
2. **Use meaningful stream IDs** - `user-{id}`, `order-{id}`
3. **Consider stream size** - Use snapshots for large streams

### Projection Design

1. **Idempotent handlers** - Handle duplicate events gracefully
2. **Track position** - Enable resume from last processed event
3. **Handle out-of-order events** - Use event timestamps, not arrival order

### Command Design

1. **Validate before producing events** - Fail fast on invalid commands
2. **One command, one handler** - Single responsibility
3. **Return meaningful results** - Include aggregate ID, version

---

## Configuration

Environment variables for Event Sourcing:

| Variable                      | Default | Description                        |
|-------------------------------|---------|------------------------------------|
| EVENT_STORE_BATCH_SIZE        | 100     | Max events per append              |
| EVENT_STORE_RETENTION_DAYS    | 365     | Event retention period             |
| SNAPSHOT_THRESHOLD            | 100     | Events before snapshot             |
| PROJECTION_BATCH_SIZE         | 50      | Events per projection batch        |
| QUERY_CACHE_SIZE              | 1000    | Max cached query results           |
| QUERY_CACHE_TTL               | 300     | Cache TTL in seconds               |
| COMMAND_TIMEOUT               | 30      | Command execution timeout (sec)    |

---

## Changelog

### v3.3.0 (2026-02-20)

- Initial Event Sourcing API release
- Event Store with optimistic concurrency
- Command Bus with batch execution
- Query Bus with caching
- Projection management
- Aggregate state and history
- WebSocket subscriptions
- Resilience patterns integration
