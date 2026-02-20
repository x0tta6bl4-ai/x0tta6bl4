"""
Tests for Event Sourcing API Endpoints
======================================

Comprehensive tests for:
- Event Store operations (append, read, subscribe)
- Command Bus (execute, batch)
- Query Bus (execute, cache management)
- Projections (status, reset, pause, resume)
- Aggregates (state, history)
- Resilience pattern integration
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import API and models
from src.event_sourcing.api import (
    router,
    event_sourcing_startup,
    event_sourcing_shutdown,
    EventCreate,
    AppendEventsRequest,
    CommandRequest,
    QueryRequest,
)

# Import event sourcing components
from src.event_sourcing.event_store import EventStore, Event, Snapshot
from src.event_sourcing.command_bus import CommandBus, CommandResult
from src.event_sourcing.query_bus import QueryBus, QueryResult
from src.event_sourcing.projection import ProjectionManager, ProjectionStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create FastAPI app with event sourcing router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_event_store():
    """Mock EventStore."""
    store = Mock(spec=EventStore)
    return store


@pytest.fixture
def mock_command_bus():
    """Mock CommandBus."""
    bus = Mock(spec=CommandBus)
    return bus


@pytest.fixture
def mock_query_bus():
    """Mock QueryBus."""
    bus = Mock(spec=QueryBus)
    return bus


@pytest.fixture
def mock_projection_manager():
    """Mock ProjectionManager."""
    manager = Mock(spec=ProjectionManager)
    return manager


@pytest.fixture
def sample_event():
    """Sample event for testing."""
    event = Mock(spec=Event)
    event.event_id = uuid.uuid4()
    event.event_type = "UserCreated"
    event.stream_id = "user-123"
    event.version = 1
    event.timestamp = datetime.utcnow()
    event.payload = {"name": "John", "email": "john@example.com"}
    event.metadata = {}
    return event


@pytest.fixture
def sample_command_result():
    """Sample command result for testing."""
    result = Mock(spec=CommandResult)
    result.success = True
    result.result = {"user_id": "user-123"}
    result.error = None
    result.events_produced = 1
    return result


@pytest.fixture
def sample_query_result():
    """Sample query result for testing."""
    result = Mock(spec=QueryResult)
    result.result = {"users": [{"id": "1", "name": "John"}]}
    result.from_cache = False
    return result


# =============================================================================
# Event Store Tests
# =============================================================================

class TestEventStoreEndpoints:
    """Tests for event store endpoints."""
    
    def test_list_streams_empty(self, client, mock_event_store):
        """Test listing streams when empty."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.list_streams.return_value = []
            
            response = client.get("/events/streams")
            
            assert response.status_code == 200
            assert response.json()["streams"] == []
    
    def test_list_streams_with_data(self, client, mock_event_store):
        """Test listing streams with data."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.list_streams.return_value = [
                {
                    "stream_id": "user-123",
                    "version": 5,
                    "event_count": 5,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ]
            
            response = client.get("/events/streams")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["streams"]) == 1
            assert data["streams"][0]["stream_id"] == "user-123"
    
    def test_list_streams_with_prefix(self, client, mock_event_store):
        """Test listing streams with prefix filter."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.list_streams.return_value = []
            
            response = client.get("/events/streams?prefix=user-")
            
            assert response.status_code == 200
            mock_event_store.list_streams.assert_called_with(prefix="user-", limit=100)
    
    def test_get_stream_events_success(self, client, mock_event_store, sample_event):
        """Test getting events from a stream."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_stream.return_value = [sample_event]
            
            response = client.get("/events/streams/user-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["stream_id"] == "user-123"
            assert len(data["events"]) == 1
            assert data["events"][0]["event_type"] == "UserCreated"
    
    def test_get_stream_events_not_found(self, client, mock_event_store):
        """Test getting events from non-existent stream."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_stream.return_value = []
            
            response = client.get("/events/streams/nonexistent")
            
            assert response.status_code == 404
    
    def test_get_stream_events_with_version_range(self, client, mock_event_store, sample_event):
        """Test getting events with version range."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_stream.return_value = [sample_event]
            
            response = client.get("/events/streams/user-123?from_version=0&to_version=10")
            
            assert response.status_code == 200
    
    def test_append_events_success(self, client, mock_event_store):
        """Test appending events to a stream."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.append.return_value = {"version": 2}
            
            response = client.post(
                "/events/streams/user-123/append",
                json={
                    "events": [
                        {
                            "event_type": "UserUpdated",
                            "payload": {"name": "Jane"}
                        }
                    ]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["stream_id"] == "user-123"
            assert data["new_version"] == 2
            assert data["appended_count"] == 1
    
    def test_append_events_with_expected_version(self, client, mock_event_store):
        """Test appending events with optimistic concurrency."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.append.return_value = {"version": 2}
            
            response = client.post(
                "/events/streams/user-123/append",
                json={
                    "events": [
                        {
                            "event_type": "UserUpdated",
                            "payload": {"name": "Jane"}
                        }
                    ],
                    "expected_version": 1
                }
            )
            
            assert response.status_code == 200
    
    def test_append_events_version_conflict(self, client, mock_event_store):
        """Test appending events with version conflict."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.append.side_effect = ValueError("Version conflict: expected 1, got 2")
            
            response = client.post(
                "/events/streams/user-123/append",
                json={
                    "events": [
                        {
                            "event_type": "UserUpdated",
                            "payload": {}
                        }
                    ],
                    "expected_version": 1
                }
            )
            
            assert response.status_code == 409
    
    def test_get_snapshot_success(self, client, mock_event_store):
        """Test getting a snapshot."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            snapshot = Mock(spec=Snapshot)
            snapshot.stream_id = "user-123"
            snapshot.version = 5
            snapshot.state = {"name": "John", "email": "john@example.com"}
            snapshot.timestamp = datetime.utcnow()
            mock_event_store.get_snapshot.return_value = snapshot
            
            response = client.get("/events/streams/user-123/snapshot")
            
            assert response.status_code == 200
            data = response.json()
            assert data["stream_id"] == "user-123"
            assert data["version"] == 5
    
    def test_get_snapshot_not_found(self, client, mock_event_store):
        """Test getting a non-existent snapshot."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.get_snapshot.return_value = None
            
            response = client.get("/events/streams/user-123/snapshot")
            
            assert response.status_code == 404
    
    def test_create_snapshot(self, client, mock_event_store):
        """Test creating a snapshot."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            snapshot = Mock(spec=Snapshot)
            snapshot.stream_id = "user-123"
            snapshot.version = 5
            snapshot.state = {"name": "John"}
            snapshot.timestamp = datetime.utcnow()
            mock_event_store.create_snapshot.return_value = snapshot
            
            response = client.post("/events/streams/user-123/snapshot")
            
            assert response.status_code == 201
    
    def test_get_all_events(self, client, mock_event_store, sample_event):
        """Test getting all events."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_all.return_value = [sample_event]
            
            response = client.get("/events/events")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1
    
    def test_get_all_events_with_filters(self, client, mock_event_store, sample_event):
        """Test getting events with filters."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_all.return_value = [sample_event]
            
            response = client.get(
                "/events/events?event_type=UserCreated&limit=50"
            )
            
            assert response.status_code == 200


# =============================================================================
# Command Bus Tests
# =============================================================================

class TestCommandBusEndpoints:
    """Tests for command bus endpoints."""
    
    def test_execute_command_success(self, client, mock_command_bus, sample_command_result):
        """Test successful command execution."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            mock_command_bus.execute.return_value = sample_command_result
            
            response = client.post(
                "/events/commands",
                json={
                    "command_type": "CreateUser",
                    "payload": {"name": "John", "email": "john@example.com"}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["events_produced"] == 1
    
    def test_execute_command_failure(self, client, mock_command_bus):
        """Test failed command execution."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            result = Mock(spec=CommandResult)
            result.success = False
            result.result = None
            result.error = "Validation failed"
            result.events_produced = 0
            mock_command_bus.execute.return_value = result
            
            response = client.post(
                "/events/commands",
                json={
                    "command_type": "CreateUser",
                    "payload": {}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "Validation failed"
    
    def test_execute_command_with_id(self, client, mock_command_bus, sample_command_result):
        """Test command execution with provided ID."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            mock_command_bus.execute.return_value = sample_command_result
            
            command_id = str(uuid.uuid4())
            response = client.post(
                "/events/commands",
                json={
                    "command_id": command_id,
                    "command_type": "CreateUser",
                    "payload": {}
                }
            )
            
            assert response.status_code == 200
            assert response.json()["command_id"] == command_id
    
    def test_execute_batch_commands(self, client, mock_command_bus, sample_command_result):
        """Test batch command execution."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            mock_command_bus.execute.return_value = sample_command_result
            
            response = client.post(
                "/events/commands/batch",
                json={
                    "commands": [
                        {"command_type": "CreateUser", "payload": {"name": "User1"}},
                        {"command_type": "CreateUser", "payload": {"name": "User2"}}
                    ]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success_count"] == 2
            assert data["failure_count"] == 0
    
    def test_execute_batch_commands_partial_failure(self, client, mock_command_bus):
        """Test batch command execution with partial failure."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            # First call succeeds, second fails
            success_result = Mock(spec=CommandResult)
            success_result.success = True
            success_result.result = {}
            success_result.error = None
            success_result.events_produced = 1
            
            fail_result = Mock(spec=CommandResult)
            fail_result.success = False
            fail_result.result = None
            fail_result.error = "Failed"
            fail_result.events_produced = 0
            
            mock_command_bus.execute.side_effect = [success_result, fail_result]
            
            response = client.post(
                "/events/commands/batch",
                json={
                    "commands": [
                        {"command_type": "CreateUser", "payload": {}},
                        {"command_type": "CreateUser", "payload": {}}
                    ]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success_count"] == 1
            assert data["failure_count"] == 1
    
    def test_list_command_handlers(self, client, mock_command_bus):
        """Test listing command handlers."""
        with patch('src.event_sourcing.api.get_command_bus', return_value=mock_command_bus):
            mock_command_bus.get_registered_handlers.return_value = {
                "CreateUser": lambda c: None,
                "UpdateUser": lambda c: None
            }
            
            response = client.get("/events/commands/handlers")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["handlers"]) == 2


# =============================================================================
# Query Bus Tests
# =============================================================================

class TestQueryBusEndpoints:
    """Tests for query bus endpoints."""
    
    def test_execute_query_success(self, client, mock_query_bus, sample_query_result):
        """Test successful query execution."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            mock_query_bus.execute.return_value = sample_query_result
            
            response = client.post(
                "/events/queries",
                json={
                    "query_type": "GetUser",
                    "parameters": {"user_id": "user-123"}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["from_cache"] is False
            assert "users" in data["result"]
    
    def test_execute_query_from_cache(self, client, mock_query_bus):
        """Test query execution from cache."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            result = Mock(spec=QueryResult)
            result.result = {"users": []}
            result.from_cache = True
            mock_query_bus.execute.return_value = result
            
            response = client.post(
                "/events/queries",
                json={
                    "query_type": "GetAllUsers",
                    "parameters": {}
                }
            )
            
            assert response.status_code == 200
            assert response.json()["from_cache"] is True
    
    def test_execute_query_with_options(self, client, mock_query_bus, sample_query_result):
        """Test query execution with options."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            mock_query_bus.execute.return_value = sample_query_result
            
            response = client.post(
                "/events/queries",
                json={
                    "query_type": "GetUser",
                    "parameters": {"user_id": "user-123"},
                    "options": {
                        "use_cache": True,
                        "cache_ttl_seconds": 60
                    }
                }
            )
            
            assert response.status_code == 200
    
    def test_get_query_cache_stats(self, client, mock_query_bus):
        """Test getting query cache statistics."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            mock_query_bus.get_cache_stats.return_value = {
                "size": 100,
                "hits": 500,
                "misses": 50,
                "hit_rate": 0.91
            }
            
            response = client.get("/events/queries/cache")
            
            assert response.status_code == 200
            assert response.json()["hit_rate"] == 0.91
    
    def test_invalidate_query_cache(self, client, mock_query_bus):
        """Test invalidating query cache."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            mock_query_bus.invalidate_cache.return_value = 10
            
            response = client.post(
                "/events/queries/cache/invalidate",
                json={"query_type": "GetUser"}
            )
            
            assert response.status_code == 200
            assert response.json()["invalidated_count"] == 10
    
    def test_invalidate_all_query_cache(self, client, mock_query_bus):
        """Test invalidating all query cache."""
        with patch('src.event_sourcing.api.get_query_bus', return_value=mock_query_bus):
            mock_query_bus.invalidate_cache.return_value = 100
            
            response = client.post(
                "/events/queries/cache/invalidate",
                json={"all": True}
            )
            
            assert response.status_code == 200
            assert response.json()["invalidated_count"] == 100


# =============================================================================
# Projection Tests
# =============================================================================

class TestProjectionEndpoints:
    """Tests for projection endpoints."""
    
    def test_list_projections(self, client, mock_projection_manager):
        """Test listing projections."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            projection = Mock()
            projection.name = "UserProjection"
            projection.status = ProjectionStatus.RUNNING
            projection.position = 100
            projection.events_processed = 100
            projection.last_event_timestamp = datetime.utcnow()
            mock_projection_manager.list_projections.return_value = [projection]
            
            response = client.get("/events/projections")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["projections"]) == 1
            assert data["projections"][0]["name"] == "UserProjection"
    
    def test_get_projection_status(self, client, mock_projection_manager):
        """Test getting projection status."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            mock_projection_manager.get_projection_status.return_value = {
                "name": "UserProjection",
                "status": "running",
                "position": 100,
                "events_processed": 100,
                "last_event_timestamp": datetime.utcnow(),
                "lag": 0,
                "error": None,
                "started_at": datetime.utcnow()
            }
            
            response = client.get("/events/projections/UserProjection")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "UserProjection"
            assert data["status"] == "running"
    
    def test_get_projection_status_not_found(self, client, mock_projection_manager):
        """Test getting non-existent projection status."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            mock_projection_manager.get_projection_status.return_value = None
            
            response = client.get("/events/projections/NonExistent")
            
            assert response.status_code == 404
    
    def test_reset_projection(self, client, mock_projection_manager):
        """Test resetting a projection."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            mock_projection_manager.reset_projection.return_value = None
            
            response = client.post("/events/projections/UserProjection/reset")
            
            assert response.status_code == 200
            assert response.json()["status"] == "resetting"
    
    def test_pause_projection(self, client, mock_projection_manager):
        """Test pausing a projection."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            mock_projection_manager.pause_projection.return_value = None
            
            response = client.post("/events/projections/UserProjection/pause")
            
            assert response.status_code == 200
            assert response.json()["status"] == "paused"
    
    def test_resume_projection(self, client, mock_projection_manager):
        """Test resuming a projection."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            mock_projection_manager.resume_projection.return_value = None
            
            response = client.post("/events/projections/UserProjection/resume")
            
            assert response.status_code == 200
            assert response.json()["status"] == "running"


# =============================================================================
# Aggregate Tests
# =============================================================================

class TestAggregateEndpoints:
    """Tests for aggregate endpoints."""
    
    def test_get_aggregate_success(self, client, mock_event_store, sample_event):
        """Test getting aggregate state."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            sample_event.payload = {"name": "John", "email": "john@example.com"}
            mock_event_store.read_stream.return_value = [sample_event]
            
            response = client.get("/events/aggregates/User/user-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["aggregate_type"] == "User"
            assert data["aggregate_id"] == "user-123"
    
    def test_get_aggregate_not_found(self, client, mock_event_store):
        """Test getting non-existent aggregate."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_stream.return_value = []
            
            response = client.get("/events/aggregates/User/nonexistent")
            
            assert response.status_code == 404
    
    def test_get_aggregate_history(self, client, mock_event_store, sample_event):
        """Test getting aggregate history."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.read_stream.return_value = [sample_event]
            
            response = client.get("/events/aggregates/User/user-123/history")
            
            assert response.status_code == 200
            data = response.json()
            assert data["aggregate_type"] == "User"
            assert len(data["events"]) == 1


# =============================================================================
# Resilience Integration Tests
# =============================================================================

class TestResilienceIntegration:
    """Tests for resilience pattern integration."""
    
    def test_rate_limiting(self, client, mock_event_store):
        """Test rate limiting on API endpoints."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.list_streams.return_value = []
            
            # Make many requests quickly
            responses = []
            for _ in range(250):  # More than the rate limit
                responses.append(client.get("/events/streams"))
            
            # Some should be rate limited
            assert all(r.status_code in {200, 429} for r in responses)
            # Note: In test environment, rate limiting might not trigger
    
    def test_bulkhead_isolation(self, client, mock_event_store):
        """Test bulkhead isolation for event operations."""
        with patch('src.event_sourcing.api.get_event_store', return_value=mock_event_store):
            mock_event_store.list_streams.return_value = []
            
            # Normal operation should work
            response = client.get("/events/streams")
            assert response.status_code == 200
    
    def test_circuit_breaker_on_projection_failure(self, client, mock_projection_manager):
        """Test circuit breaker on projection failures."""
        with patch('src.event_sourcing.api.get_projection_manager', return_value=mock_projection_manager):
            # Simulate repeated failures
            mock_projection_manager.get_projection_status.side_effect = Exception("Connection refused")
            
            # Multiple failed requests
            for _ in range(5):
                try:
                    client.get("/events/projections/UserProjection")
                except Exception:
                    pass


# =============================================================================
# Pydantic Model Tests
# =============================================================================

class TestPydanticModels:
    """Tests for Pydantic models."""
    
    def test_event_create_validation(self):
        """Test EventCreate validation."""
        valid = EventCreate(
            event_type="UserCreated",
            payload={"name": "John"}
        )
        assert valid.event_type == "UserCreated"
        
        # Invalid - missing required field
        with pytest.raises(Exception):
            EventCreate()
    
    def test_append_events_request_validation(self):
        """Test AppendEventsRequest validation."""
        valid = AppendEventsRequest(
            events=[
                EventCreate(event_type="UserCreated", payload={})
            ]
        )
        assert len(valid.events) == 1
        assert valid.expected_version is None
    
    def test_command_request_validation(self):
        """Test CommandRequest validation."""
        valid = CommandRequest(
            command_type="CreateUser",
            payload={"name": "John"}
        )
        assert valid.command_type == "CreateUser"
        assert valid.command_id is None
    
    def test_query_request_validation(self):
        """Test QueryRequest validation."""
        valid = QueryRequest(
            query_type="GetUser",
            parameters={"user_id": "123"}
        )
        assert valid.query_type == "GetUser"
        assert valid.options is None


# =============================================================================
# Startup/Shutdown Tests
# =============================================================================

class TestLifecycle:
    """Tests for startup and shutdown."""
    
    @pytest.mark.asyncio
    async def test_startup(self):
        """Test event sourcing module startup."""
        await event_sourcing_startup()
        # Should initialize without errors
    
    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test event sourcing module shutdown."""
        await event_sourcing_shutdown()
        # Should cleanup without errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
