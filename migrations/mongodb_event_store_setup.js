/**
 * Event Store MongoDB Setup Script.
 * 
 * Creates collections, indexes, and validation rules for event sourcing.
 * Run with: mongosh maas_event_store < mongodb_event_store_setup.js
 */

// ============================================================================
// DATABASE
// ============================================================================

db = db.getSiblingDB('maas_event_store');

// ============================================================================
// COLLECTIONS
// ============================================================================

// Events collection
db.createCollection('events', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['event_id', 'aggregate_id', 'event_type', 'sequence_number', 'timestamp'],
            properties: {
                event_id: {
                    bsonType: 'string',
                    description: 'Unique event identifier (UUID)'
                },
                aggregate_id: {
                    bsonType: 'string',
                    description: 'ID of the aggregate this event belongs to'
                },
                aggregate_type: {
                    bsonType: 'string',
                    description: 'Type of the aggregate'
                },
                event_type: {
                    bsonType: 'string',
                    description: 'Type of event'
                },
                sequence_number: {
                    bsonType: 'int',
                    minimum: 1,
                    description: 'Sequential version number within the stream'
                },
                data: {
                    bsonType: 'object',
                    description: 'Event payload'
                },
                metadata: {
                    bsonType: 'object',
                    properties: {
                        correlation_id: { bsonType: 'string' },
                        causation_id: { bsonType: 'string' },
                        user_id: { bsonType: 'string' },
                        source: { bsonType: 'string' },
                        timestamp: { bsonType: 'date' },
                        version: {
                            bsonType: 'object',
                            properties: {
                                major: { bsonType: 'int' },
                                minor: { bsonType: 'int' }
                            }
                        },
                        custom: { bsonType: 'object' }
                    }
                },
                timestamp: {
                    bsonType: 'date',
                    description: 'When the event occurred'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'When the event was stored'
                }
            }
        }
    }
});

// Streams collection
db.createCollection('streams', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['aggregate_id', 'version'],
            properties: {
                aggregate_id: {
                    bsonType: 'string',
                    description: 'Unique identifier for the aggregate'
                },
                aggregate_type: {
                    bsonType: 'string',
                    description: 'Type of the aggregate'
                },
                version: {
                    bsonType: 'int',
                    minimum: 0,
                    description: 'Current version of the stream'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'When the stream was created'
                },
                updated_at: {
                    bsonType: 'date',
                    description: 'When the stream was last updated'
                }
            }
        }
    }
});

// Snapshots collection
db.createCollection('snapshots', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['snapshot_id', 'aggregate_id', 'sequence_number', 'state'],
            properties: {
                snapshot_id: {
                    bsonType: 'string',
                    description: 'Unique snapshot identifier'
                },
                aggregate_id: {
                    bsonType: 'string',
                    description: 'ID of the aggregate'
                },
                aggregate_type: {
                    bsonType: 'string',
                    description: 'Type of the aggregate'
                },
                sequence_number: {
                    bsonType: 'int',
                    minimum: 1,
                    description: 'Version of the aggregate at snapshot time'
                },
                state: {
                    bsonType: 'object',
                    description: 'Serialized aggregate state'
                },
                timestamp: {
                    bsonType: 'date',
                    description: 'When the snapshot was taken'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'When the snapshot was stored'
                }
            }
        }
    }
});

// Projections collection
db.createCollection('projections', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['projection_name'],
            properties: {
                projection_name: {
                    bsonType: 'string',
                    description: 'Name of the projection'
                },
                last_processed_position: {
                    bsonType: 'int',
                    description: 'Last processed event position'
                },
                last_processed_timestamp: {
                    bsonType: 'date',
                    description: 'When last event was processed'
                },
                updated_at: {
                    bsonType: 'date',
                    description: 'When the projection was updated'
                }
            }
        }
    }
});

// Subscriptions collection
db.createCollection('subscriptions', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['subscription_id', 'subscription_name', 'subscriber_id'],
            properties: {
                subscription_id: {
                    bsonType: 'string',
                    description: 'Unique subscription identifier'
                },
                subscription_name: {
                    bsonType: 'string',
                    description: 'Name of the subscription'
                },
                subscriber_id: {
                    bsonType: 'string',
                    description: 'ID of the subscriber'
                },
                event_types: {
                    bsonType: 'array',
                    items: { bsonType: 'string' },
                    description: 'Event types to subscribe to'
                },
                filter_expression: {
                    bsonType: 'string',
                    description: 'Optional filter expression'
                },
                last_processed_position: {
                    bsonType: 'int',
                    description: 'Last processed event position'
                },
                last_processed_timestamp: {
                    bsonType: 'date',
                    description: 'When last event was processed'
                },
                status: {
                    enum: ['active', 'paused', 'error'],
                    description: 'Subscription status'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'When the subscription was created'
                },
                updated_at: {
                    bsonType: 'date',
                    description: 'When the subscription was updated'
                }
            }
        }
    }
});

// ============================================================================
// INDEXES
// ============================================================================

// Events indexes
db.events.createIndex(
    { aggregate_id: 1, sequence_number: 1 },
    { unique: true, name: 'idx_aggregate_sequence' }
);

db.events.createIndex(
    { aggregate_id: 1 },
    { name: 'idx_aggregate_id' }
);

db.events.createIndex(
    { event_type: 1 },
    { name: 'idx_event_type' }
);

db.events.createIndex(
    { timestamp: 1 },
    { name: 'idx_timestamp' }
);

db.events.createIndex(
    { aggregate_type: 1 },
    { name: 'idx_aggregate_type' }
);

db.events.createIndex(
    { 'metadata.correlation_id': 1 },
    { name: 'idx_correlation_id' }
);

db.events.createIndex(
    { event_type: 1, timestamp: 1 },
    { name: 'idx_type_timestamp' }
);

db.events.createIndex(
    { aggregate_id: 1, timestamp: 1 },
    { name: 'idx_aggregate_timestamp' }
);

// Streams indexes
db.streams.createIndex(
    { aggregate_id: 1 },
    { unique: true, name: 'idx_stream_aggregate_id' }
);

db.streams.createIndex(
    { aggregate_type: 1 },
    { name: 'idx_stream_aggregate_type' }
);

db.streams.createIndex(
    { updated_at: 1 },
    { name: 'idx_stream_updated_at' }
);

// Snapshots indexes
db.snapshots.createIndex(
    { aggregate_id: 1, sequence_number: -1 },
    { name: 'idx_snapshot_aggregate_version' }
);

db.snapshots.createIndex(
    { aggregate_id: 1 },
    { name: 'idx_snapshot_aggregate_id' }
);

// Projections indexes
db.projections.createIndex(
    { projection_name: 1 },
    { unique: true, name: 'idx_projection_name' }
);

// Subscriptions indexes
db.subscriptions.createIndex(
    { subscription_name: 1 },
    { unique: true, name: 'idx_subscription_name' }
);

db.subscriptions.createIndex(
    { subscriber_id: 1 },
    { name: 'idx_subscriber' }
);

db.subscriptions.createIndex(
    { status: 1 },
    { name: 'idx_subscription_status' }
);

// ============================================================================
// TTL INDEXES (optional - for automatic cleanup)
// ============================================================================

// Uncomment to enable automatic cleanup of old events (e.g., after 365 days)
// db.events.createIndex(
//     { created_at: 1 },
//     { expireAfterSeconds: 31536000, name: 'idx_events_ttl' }
// );

// ============================================================================
// VIEWS
// ============================================================================

// Event statistics view
db.createView('event_statistics', 'events', [
    {
        $group: {
            _id: null,
            total_events: { $sum: 1 },
            total_streams: { $addToSet: '$aggregate_id' },
            event_types: { $addToSet: '$event_type' },
            first_event: { $min: '$timestamp' },
            last_event: { $max: '$timestamp' }
        }
    },
    {
        $project: {
            _id: 0,
            total_events: 1,
            total_streams: { $size: '$total_streams' },
            event_type_count: { $size: '$event_types' },
            first_event: 1,
            last_event: 1
        }
    }
]);

// Stream statistics view
db.createView('stream_statistics', 'streams', [
    {
        $lookup: {
            from: 'events',
            localField: 'aggregate_id',
            foreignField: 'aggregate_id',
            as: 'events'
        }
    },
    {
        $project: {
            aggregate_id: 1,
            aggregate_type: 1,
            version: 1,
            event_count: { $size: '$events' },
            first_event: { $min: '$events.timestamp' },
            last_event: { $max: '$events.timestamp' }
        }
    }
]);

// Event type statistics view
db.createView('event_type_statistics', 'events', [
    {
        $group: {
            _id: '$event_type',
            count: { $sum: 1 },
            first_occurrence: { $min: '$timestamp' },
            last_occurrence: { $max: '$timestamp' }
        }
    },
    {
        $project: {
            _id: 0,
            event_type: '$_id',
            count: 1,
            first_occurrence: 1,
            last_occurrence: 1
        }
    },
    {
        $sort: { count: -1 }
    }
]);

// ============================================================================
// FUNCTIONS (stored as views/aggregations)
// ============================================================================

// Function to get events for replay (as aggregation pipeline)
db.createView('events_for_replay', 'events', [
    { $sort: { timestamp: 1, sequence_number: 1 } }
]);

print('MongoDB Event Store setup completed successfully!');
print('Collections created: events, streams, snapshots, projections, subscriptions');
print('Views created: event_statistics, stream_statistics, event_type_statistics');
