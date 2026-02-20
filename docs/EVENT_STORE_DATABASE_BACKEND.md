# Event Store Database Backend Documentation

## Overview

The Event Store Database Backend provides persistent storage for event sourcing with support for multiple database engines. Currently supported backends:

- **PostgreSQL**: ACID-compliant relational storage with advanced indexing
- **MongoDB**: Document-based storage for flexible schemas

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Event Store API                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              DatabaseBackend (Abstract)                  │   │
│  │  - append_event() / append_events()                      │   │
│  │  - get_events() / get_all_events()                       │   │
│  │  - save_snapshot() / get_snapshot()                      │   │
│  │  - list_streams() / delete_stream()                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ▲                                      │
│                          │ implements                           │
│            ┌─────────────┴─────────────┐                       │
│            │                           │                        │
│  ┌─────────┴─────────┐     ┌──────────┴──────────┐            │
│  │ PostgresEventStore │     │  MongoDBEventStore  │            │
│  │                    │     │                     │            │
│  │ - asyncpg pool     │     │ - motor pool        │            │
│  │ - ACID trans.      │     │ - Change streams    │            │
│  │ - JSONB queries    │     │ - Flexible schema   │            │
│  └────────────────────┘     └─────────────────────┘            │
│            │                           │                        │
│            ▼                           ▼                        │
│  ┌────────────────────┐     ┌─────────────────────┐            │
│  │    PostgreSQL      │     │      MongoDB        │            │
│  │  (event_store      │     │  (maas_event_store) │            │
│  │     schema)        │     │                     │            │
│  └────────────────────┘     └─────────────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## PostgreSQL Backend

### Configuration

```python
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig

config = PostgresConfig(
    host="localhost",
    port=5432,
    database="maas_event_store",
    user="postgres",
    password="secret",
    schema="event_store",
    min_pool_size=5,
    max_pool_size=20,
    connection_timeout=30.0,
    command_timeout=60.0,
)

store = PostgresEventStore(config=config)
await store.connect()
```

### Schema

The PostgreSQL backend uses a dedicated schema with the following tables:

#### `event_store.streams`
| Column | Type | Description |
|--------|------|-------------|
| aggregate_id | VARCHAR(255) | Primary key, stream identifier |
| aggregate_type | VARCHAR(255) | Type of aggregate |
| version | BIGINT | Current stream version |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

#### `event_store.events`
| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR(36) | Primary key, UUID |
| aggregate_id | VARCHAR(255) | Foreign key to streams |
| aggregate_type | VARCHAR(255) | Type of aggregate |
| event_type | VARCHAR(255) | Event type name |
| sequence_number | BIGINT | Version within stream |
| data | JSONB | Event payload |
| metadata | JSONB | Event metadata |
| timestamp | TIMESTAMPTZ | When event occurred |
| created_at | TIMESTAMPTZ | When stored |

#### `event_store.snapshots`
| Column | Type | Description |
|--------|------|-------------|
| snapshot_id | VARCHAR(36) | Primary key |
| aggregate_id | VARCHAR(255) | Aggregate identifier |
| sequence_number | BIGINT | Version at snapshot |
| state | JSONB | Aggregate state |
| timestamp | TIMESTAMPTZ | Snapshot timestamp |

### Indexes

```sql
-- Primary lookup indexes
CREATE INDEX idx_events_aggregate_id ON event_store.events (aggregate_id);
CREATE INDEX idx_events_event_type ON event_store.events (event_type);
CREATE INDEX idx_events_timestamp ON event_store.events (timestamp);

-- JSONB indexes for flexible queries
CREATE INDEX idx_events_data ON event_store.events USING GIN (data);
CREATE INDEX idx_events_metadata ON event_store.events USING GIN (metadata);

-- Composite indexes
CREATE INDEX idx_events_type_timestamp ON event_store.events (event_type, timestamp);
```

### Usage Examples

```python
# Append events
event = Event(
    event_type="OrderCreated",
    aggregate_id="order-123",
    aggregate_type="Order",
    data={"customer_id": "cust-456", "total": 99.99},
    metadata=EventMetadata(correlation_id="corr-001")
)

version = await store.append_event("order-123", event)

# Append with optimistic concurrency
try:
    version = await store.append_event(
        "order-123",
        event,
        expected_version=5  # Will fail if version != 5
    )
except VersionConflictError as e:
    print(f"Conflict: expected {e.expected_version}, got {e.actual_version}")

# Get events
events = await store.get_events(
    "order-123",
    from_sequence=0,
    limit=100
)

# Query by event type
order_events = await store.get_events_by_type(
    "OrderCreated",
    from_timestamp=datetime(2026, 1, 1),
    limit=1000
)

# Snapshot operations
snapshot = Snapshot(
    aggregate_id="order-123",
    aggregate_type="Order",
    sequence_number=100,
    state={"status": "completed", "total": 99.99}
)
await store.save_snapshot(snapshot)

# Retrieve latest snapshot
snapshot = await store.get_snapshot("order-123")
```

## MongoDB Backend

### Configuration

```python
from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig

config = MongoDBConfig(
    host="localhost",
    port=27017,
    database="maas_event_store",
    user="mongo_user",
    password="secret",
    replica_set="rs0",  # Optional, for replica sets
    max_pool_size=100,
    min_pool_size=10,
)

store = MongoDBEventStore(config=config)
await store.connect()
```

### Collections

#### `events`
```javascript
{
    "_id": ObjectId("..."),
    "event_id": "uuid-string",
    "aggregate_id": "order-123",
    "aggregate_type": "Order",
    "event_type": "OrderCreated",
    "sequence_number": 1,
    "data": { "customer_id": "cust-456", "total": 99.99 },
    "metadata": {
        "correlation_id": "corr-001",
        "causation_id": "cause-001",
        "user_id": "user-001",
        "timestamp": ISODate("2026-02-20T10:00:00Z")
    },
    "timestamp": ISODate("2026-02-20T10:00:00Z"),
    "created_at": ISODate("2026-02-20T10:00:01Z")
}
```

#### `streams`
```javascript
{
    "_id": ObjectId("..."),
    "aggregate_id": "order-123",
    "aggregate_type": "Order",
    "version": 10,
    "created_at": ISODate("2026-02-20T10:00:00Z"),
    "updated_at": ISODate("2026-02-20T10:30:00Z")
}
```

#### `snapshots`
```javascript
{
    "_id": ObjectId("..."),
    "snapshot_id": "uuid-string",
    "aggregate_id": "order-123",
    "aggregate_type": "Order",
    "sequence_number": 10,
    "state": { "status": "completed", "total": 99.99 },
    "timestamp": ISODate("2026-02-20T10:30:00Z")
}
```

### Indexes

```javascript
// Unique constraint on aggregate + sequence
db.events.createIndex(
    { aggregate_id: 1, sequence_number: 1 },
    { unique: true }
)

// Event type queries
db.events.createIndex({ event_type: 1 })

// Time-based queries
db.events.createIndex({ timestamp: 1 })

// Correlation ID queries
db.events.createIndex({ "metadata.correlation_id": 1 })
```

### Change Streams

MongoDB backend supports real-time event subscriptions via change streams:

```python
# Watch for new events
async for event in store.watch_events(
    aggregate_id="order-123",
    event_types=["OrderCreated", "OrderUpdated"]
):
    print(f"New event: {event.event_type}")
    # Process event in real-time
```

## Connection Pooling

Both backends implement connection pooling for optimal performance:

### PostgreSQL (asyncpg)

```python
config = PostgresConfig(
    min_pool_size=5,    # Minimum connections maintained
    max_pool_size=20,   # Maximum connections allowed
    connection_timeout=30.0,
    command_timeout=60.0,
)
```

### MongoDB (motor)

```python
config = MongoDBConfig(
    min_pool_size=10,
    max_pool_size=100,
    connection_timeout=30.0,
    socket_timeout=30.0,
)
```

## Optimistic Concurrency Control

Both backends support optimistic concurrency control for safe concurrent writes:

```python
# Get current version
version = await store.get_stream_version("order-123")

# Append with expected version
try:
    new_version = await store.append_event(
        "order-123",
        event,
        expected_version=version
    )
except VersionConflictError as e:
    # Handle conflict - another process modified the stream
    print(f"Conflict detected: {e}")
```

## Migration Scripts

### PostgreSQL Migration

Run the migration script to set up the schema:

```bash
# Using psql
psql -U postgres -d maas_event_store -f alembic/versions/v001_event_store_postgres.py

# Or using the Python migration
python -m src.event_sourcing.migrations.postgres
```

### MongoDB Setup

Run the setup script to create collections and indexes:

```bash
# Using mongosh
mongosh maas_event_store < migrations/mongodb_event_store_setup.js

# Or using the Python setup
python -m src.event_sourcing.migrations.mongodb
```

## Performance Considerations

### PostgreSQL

- **Best for**: Strong consistency requirements, complex queries, ACID transactions
- **Optimizations**:
  - Use JSONB indexes for flexible queries
  - Partition large event tables by time
  - Use connection pooling appropriately
  - Consider table partitioning for high-volume streams

### MongoDB

- **Best for**: Flexible schemas, horizontal scaling, real-time subscriptions
- **Optimizations**:
  - Use appropriate index coverage
  - Configure write concern for durability
  - Use change streams for real-time updates
  - Consider sharding for large datasets

## Health Checks

```python
# Check backend health
health = await store.health_check()

# PostgreSQL response
{
    "healthy": True,
    "backend": "postgresql",
    "database": "maas_event_store",
    "host": "localhost",
    "pool_size": 10,
    "pool_idle": 5,
    "pool_max": 20
}

# MongoDB response
{
    "healthy": True,
    "backend": "mongodb",
    "database": "maas_event_store",
    "host": "localhost",
    "version": "6.0.4",
    "connections": 15,
    "pool_size": 100
}
```

## Statistics

```python
stats = await store.get_statistics()

# Response structure
{
    "total_events": 150000,
    "total_streams": 5000,
    "total_snapshots": 200,
    "event_types": {
        "OrderCreated": 50000,
        "OrderUpdated": 75000,
        "OrderCompleted": 25000
    },
    "aggregate_types": {
        "Order": 3000,
        "Customer": 1500,
        "Product": 500
    },
    "database_size": "1.5 GB"  # PostgreSQL
    # or
    "database_size_mb": 1500,  # MongoDB
    "storage_size_mb": 1200,
    "index_size_mb": 300
}
```

## Error Handling

```python
from src.event_sourcing.backends.base import (
    VersionConflictError,
    DatabaseConnectionError,
    DatabaseQueryError,
)

try:
    await store.append_event(aggregate_id, event, expected_version=5)
except VersionConflictError as e:
    # Handle optimistic concurrency conflict
    logger.warning(f"Version conflict: {e}")
except DatabaseConnectionError as e:
    # Handle connection issues
    logger.error(f"Database connection failed: {e}")
    await store.connect()  # Reconnect
except DatabaseQueryError as e:
    # Handle query errors
    logger.error(f"Query failed: {e}")
```

## Environment Variables

### PostgreSQL

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=maas_event_store
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
```

### MongoDB

```bash
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB=maas_event_store
MONGODB_USER=mongo_user
MONGODB_PASSWORD=secret
```

## Testing

Run the backend tests:

```bash
# All backend tests
pytest tests/test_event_store_backends.py -v

# PostgreSQL only
pytest tests/test_event_store_backends.py -v -k "postgres"

# MongoDB only
pytest tests/test_event_store_backends.py -v -k "mongodb"

# With coverage
pytest tests/test_event_store_backends.py --cov=src/event_sourcing/backends
```

## Best Practices

1. **Connection Management**: Use context managers for automatic cleanup
   ```python
   async with PostgresEventStore(config) as store:
       await store.append_event(aggregate_id, event)
   ```

2. **Batch Operations**: Use batch append for multiple events
   ```python
   await store.append_events(aggregate_id, events)  # Atomic
   ```

3. **Snapshots**: Create snapshots periodically to reduce replay time
   ```python
   if events_since_snapshot >= SNAPSHOT_INTERVAL:
       await store.save_snapshot(snapshot)
   ```

4. **Index Strategy**: Create indexes based on query patterns
   ```python
   # For correlation ID queries
   await store.create_index("metadata.correlation_id")
   ```

5. **Monitoring**: Track pool usage and query performance
   ```python
   health = await store.health_check()
   if health["pool_idle"] < 2:
       logger.warning("Connection pool running low")
   ```

---

## Backend Migration

The migration tool allows transferring events between different database backends.

### Basic Migration

```python
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig
from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig
from src.event_sourcing.backends.migration import BackendMigrator, MigrationConfig

# Configure backends
pg_config = PostgresConfig(
    host="localhost",
    database="maas_event_store",
    user="postgres",
    password="secret",
)

mongo_config = MongoDBConfig(
    host="localhost",
    database="maas_event_store",
)

# Create backends
source = PostgresEventStore(config=pg_config)
target = MongoDBEventStore(config=mongo_config)

# Configure migration
migration_config = MigrationConfig(
    batch_size=1000,           # Events per batch
    validate_after_migration=True,  # Verify data after migration
    create_backup=True,        # Create backup before migration
    stop_on_error=False,       # Continue on errors
    max_errors=10,             # Max errors before stopping
)

# Run migration
migrator = BackendMigrator(source, target, migration_config)

try:
    await source.connect()
    await target.connect()
    
    progress = await migrator.migrate()
    
    print(f"Migrated {progress.migrated_events} events")
    print(f"Migrated {progress.migrated_streams} streams")
    print(f"Status: {progress.status.value}")
    
finally:
    await source.disconnect()
    await target.disconnect()
```

### Migration with Progress Tracking

```python
def on_progress(progress):
    print(f"Events: {progress.migrated_events}/{progress.total_events} ({progress.events_percentage:.1f}%)")
    print(f"Streams: {progress.migrated_streams}/{progress.total_streams}")

config = MigrationConfig(
    batch_size=500,
    progress_callback=on_progress,
)

migrator = BackendMigrator(source, target, config)
progress = await migrator.migrate()
```

### Dry Run Migration

Test migration without writing data:

```python
config = MigrationConfig(dry_run=True)
migrator = BackendMigrator(source, target, config)
progress = await migrator.migrate()

# No data written, but progress tracked
print(f"Would migrate {progress.migrated_events} events")
```

### Migration Rollback

Rollback a completed migration:

```python
migrator = BackendMigrator(source, target, config)
progress = await migrator.migrate()

# If something went wrong, rollback
if len(progress.errors) > 0:
    await migrator.rollback()
```

### Convenience Functions

```python
from src.event_sourcing.backends.migration import (
    migrate_postgresql_to_mongodb,
    migrate_mongodb_to_postgresql,
)

# PostgreSQL → MongoDB
progress = await migrate_postgresql_to_mongodb(pg_config, mongo_config)

# MongoDB → PostgreSQL
progress = await migrate_mongodb_to_postgresql(mongo_config, pg_config)
```

---

## Dual Backend Operation

Run two backends simultaneously for gradual migration or A/B testing.

### Basic Dual Backend

```python
from src.event_sourcing.backends.migration import DualBackendEventStore

# Create dual backend store
store = DualBackendEventStore(
    primary_backend=postgres_store,
    secondary_backend=mongodb_store,
    write_to_both=True,      # Write to both backends
    read_from_secondary=False,  # Read from primary
)

await store.connect()

# Writes go to both backends
await store.append_events(aggregate_id, events)

# Reads come from primary
events = await store.get_events(aggregate_id)
```

### Read Fallback Mode

Use secondary as read fallback:

```python
store = DualBackendEventStore(
    primary_backend=postgres_store,
    secondary_backend=mongodb_store,
    write_to_both=False,
    read_from_secondary=True,  # Try secondary first
)

# If secondary fails, automatically falls back to primary
events = await store.get_events(aggregate_id)
```

### Health Check Both Backends

```python
health = await store.health_check()

# Returns health for both backends
{
    "healthy": True,
    "primary": {
        "healthy": True,
        "backend": "postgresql",
        ...
    },
    "secondary": {
        "healthy": True,
        "backend": "mongodb",
        ...
    }
}
```

---

## Complete Usage Examples

### Example 1: Order Processing System

```python
import asyncio
from datetime import datetime
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig
from src.event_sourcing.event_store import Event, EventMetadata, Snapshot

async def order_processing_example():
    # Configure PostgreSQL backend
    config = PostgresConfig(
        host="localhost",
        database="order_db",
        user="postgres",
        password="secret",
        schema="orders",
    )
    
    store = PostgresEventStore(config=config)
    
    async with store:
        # Create order events
        order_id = "order-2026-001"
        
        events = [
            Event(
                event_type="OrderCreated",
                aggregate_id=order_id,
                aggregate_type="Order",
                data={
                    "customer_id": "cust-12345",
                    "items": [
                        {"product_id": "prod-001", "quantity": 2, "price": 29.99},
                        {"product_id": "prod-002", "quantity": 1, "price": 49.99},
                    ],
                    "total": 109.97,
                },
                metadata=EventMetadata(
                    correlation_id="corr-order-001",
                    user_id="user-system",
                ),
            ),
            Event(
                event_type="OrderPaid",
                aggregate_id=order_id,
                aggregate_type="Order",
                data={
                    "payment_method": "credit_card",
                    "transaction_id": "txn-abc123",
                },
                metadata=EventMetadata(
                    correlation_id="corr-order-001",
                    causation_id="order-2026-001-0",
                ),
            ),
            Event(
                event_type="OrderShipped",
                aggregate_id=order_id,
                aggregate_type="Order",
                data={
                    "carrier": "FedEx",
                    "tracking_number": "FX123456789",
                },
                metadata=EventMetadata(
                    correlation_id="corr-order-001",
                ),
            ),
        ]
        
        # Append all events
        version = await store.append_events(order_id, events)
        print(f"Order {order_id} at version {version}")
        
        # Create snapshot
        snapshot = Snapshot(
            aggregate_id=order_id,
            aggregate_type="Order",
            sequence_number=version,
            state={
                "status": "shipped",
                "total": 109.97,
                "items_count": 3,
            },
        )
        await store.save_snapshot(snapshot)
        
        # Query events by type
        shipped_events = await store.get_events_by_type("OrderShipped")
        print(f"Found {len(shipped_events)} shipped orders")
        
        # Get statistics
        stats = await store.get_statistics()
        print(f"Total events: {stats['total_events']}")

asyncio.run(order_processing_example())
```

### Example 2: Event Replay for Projection

```python
async def event_replay_example():
    config = PostgresConfig(database="projection_db")
    store = PostgresEventStore(config=config)
    
    async with store:
        # Get all events for replay
        all_events = await store.get_all_events(
            from_position=0,
            max_count=10000,
            event_types=["OrderCreated", "OrderPaid", "OrderShipped"],
        )
        
        # Replay events to rebuild projection
        projection_state = {}
        
        for event in all_events:
            if event.event_type == "OrderCreated":
                projection_state[event.aggregate_id] = {
                    "status": "created",
                    "total": event.data.get("total", 0),
                }
            elif event.event_type == "OrderPaid":
                if event.aggregate_id in projection_state:
                    projection_state[event.aggregate_id]["status"] = "paid"
            elif event.event_type == "OrderShipped":
                if event.aggregate_id in projection_state:
                    projection_state[event.aggregate_id]["status"] = "shipped"
        
        print(f"Rebuilt projection with {len(projection_state)} orders")
```

### Example 3: MongoDB Change Stream Integration

```python
async def change_stream_example():
    from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig
    
    config = MongoDBConfig(
        host="localhost",
        database="realtime_db",
        replica_set="rs0",  # Required for change streams
    )
    
    store = MongoDBEventStore(config=config)
    
    async with store:
        # Watch for new order events in real-time
        print("Watching for new orders...")
        
        async for event in store.watch_events(
            event_types=["OrderCreated", "OrderUpdated"]
        ):
            print(f"New event: {event.event_type}")
            print(f"Order ID: {event.aggregate_id}")
            print(f"Data: {event.data}")
            
            # Process in real-time (e.g., send notifications)
            await process_order_event(event)

async def process_order_event(event):
    # Your processing logic here
    pass
```

### Example 4: Gradual Migration Strategy

```python
async def gradual_migration_example():
    """
    Gradual migration strategy:
    1. Setup dual backend with write to both
    2. Verify data consistency
    3. Switch reads to new backend
    4. Remove old backend
    """
    from src.event_sourcing.backends.migration import (
        DualBackendEventStore,
        BackendMigrator,
        MigrationConfig,
    )
    
    # Phase 1: Setup dual backend
    pg_store = PostgresEventStore(config=pg_config)
    mongo_store = MongoDBEventStore(config=mongo_config)
    
    dual_store = DualBackendEventStore(
        primary_backend=pg_store,
        secondary_backend=mongo_store,
        write_to_both=True,  # Phase 1: Write to both
        read_from_secondary=False,  # Phase 1: Read from PostgreSQL
    )
    
    await dual_store.connect()
    
    # Phase 2: Migrate existing data
    migrator = BackendMigrator(pg_store, mongo_store)
    progress = await migrator.migrate()
    
    if progress.status.value == "completed":
        print("Migration completed successfully")
        
        # Phase 3: Switch reads to MongoDB
        dual_store.read_from_secondary = True
        
        # Phase 4: After verification, stop writing to PostgreSQL
        # dual_store.write_to_both = False
        
        # Phase 5: Remove PostgreSQL backend entirely
        # store = mongo_store
```

---

## Integration Tests

Run integration tests between backends:

```bash
# All integration tests
pytest tests/test_backend_integration.py -v

# Only mocked tests (no database required)
pytest tests/test_backend_integration.py -v -k "Mocked"

# Full integration tests (requires both databases)
pytest tests/test_backend_integration.py -v -k "Integration" --integration

# Performance tests
pytest tests/test_backend_integration.py -v -k "Performance" --slow
```

### Environment Setup for Integration Tests

```bash
# PostgreSQL
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=maas_event_store_test
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=secret

# MongoDB
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_DB=maas_event_store_test
```
