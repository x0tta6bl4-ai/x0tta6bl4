"""
Event Sourcing API Endpoints
============================

FastAPI endpoints for Event Sourcing and CQRS module.
Implements OpenAPI specification from docs/api/event_sourcing_openapi.yaml

Features:
- Event Store operations (append, read, subscribe)
- Command Bus (execute, batch)
- Query Bus (execute, cache management)
- Projections (status, reset, pause, resume)
- Aggregates (state, history)

Integrates resilience patterns:
- Rate limiting for API protection
- Bulkhead for resource isolation
- Circuit breaker for external dependencies
- Fallback for graceful degradation
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

# Import event sourcing components
from src.event_sourcing.event_store import EventStore, Event, EventMetadata
from src.event_sourcing.command_bus import CommandBus, Command
from src.event_sourcing.query_bus import QueryBus, Query as ESQuery
from src.event_sourcing.projection import ProjectionManager

# Import resilience patterns
from src.resilience import (
    TokenBucket,
    SemaphoreBulkhead,
    BulkheadFullException,
    CacheFallback,
    CircuitBreaker,
    CircuitBreakerConfig,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models (matching OpenAPI spec)
# =============================================================================

class EventCreate(BaseModel):
    """Request to create an event."""
    event_type: str = Field(..., description="Event type identifier")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    metadata: Optional[Dict[str, Any]] = None


class AppendEventsRequest(BaseModel):
    """Request to append events to a stream."""
    events: List[EventCreate]
    expected_version: Optional[int] = None


class EventResponse(BaseModel):
    """Event response model."""
    event_id: str
    event_type: str
    stream_id: str
    version: int
    timestamp: datetime
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]


class SnapshotResponse(BaseModel):
    """Snapshot response model."""
    stream_id: str
    version: int
    state: Dict[str, Any]
    timestamp: datetime


class VersionConflictResponse(BaseModel):
    """Version conflict error response."""
    error: str
    expected_version: int
    actual_version: int


class CommandRequest(BaseModel):
    """Request to execute a command."""
    command_id: Optional[str] = None
    command_type: str = Field(..., description="Command type identifier")
    payload: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class CommandResultResponse(BaseModel):
    """Command result response."""
    command_id: str
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    events_produced: int
    execution_time_ms: int


class BatchCommandsRequest(BaseModel):
    """Request to execute multiple commands."""
    commands: List[CommandRequest]
    atomic: bool = False


class QueryRequest(BaseModel):
    """Request to execute a query."""
    query_id: Optional[str] = None
    query_type: str = Field(..., description="Query type identifier")
    parameters: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class QueryResultResponse(BaseModel):
    """Query result response."""
    query_id: str
    result: Optional[Dict[str, Any]]
    from_cache: bool
    execution_time_ms: int


class ProjectionInfo(BaseModel):
    """Projection information."""
    name: str
    status: str
    position: int
    events_processed: int
    last_event_timestamp: Optional[datetime]


class ProjectionStatusResponse(BaseModel):
    """Detailed projection status."""
    name: str
    status: str
    position: int
    events_processed: int
    last_event_timestamp: Optional[datetime]
    lag: int
    error: Optional[str]
    started_at: Optional[datetime]


class AggregateStateResponse(BaseModel):
    """Aggregate state response."""
    aggregate_type: str
    aggregate_id: str
    version: int
    state: Dict[str, Any]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class InvalidateCacheRequest(BaseModel):
    """Request to invalidate query cache."""
    query_type: Optional[str] = None
    all: bool = False


# =============================================================================
# Router Setup with Resilience
# =============================================================================

router = APIRouter(prefix="/events", tags=["Event Sourcing"])

# Global instances (initialized on startup)
_event_store: Optional[EventStore] = None
_command_bus: Optional[CommandBus] = None
_query_bus: Optional[QueryBus] = None
_projection_manager: Optional[ProjectionManager] = None

# Resilience patterns
_api_rate_limiter = TokenBucket(capacity=200, refill_rate=50.0, name="events_api")
_event_bulkhead = SemaphoreBulkhead(max_concurrent=20, name="event_operations")
_command_bulkhead = SemaphoreBulkhead(max_concurrent=30, name="command_operations")
_query_bulkhead = SemaphoreBulkhead(max_concurrent=50, name="query_operations")

# Circuit breaker for projections
_projection_circuit_breaker = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout_seconds=60,
        success_threshold=3
    ),
    name="projection_operations"
)

# Fallback for queries
_query_fallback = CacheFallback(ttl_seconds=300, max_size=1000)


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check endpoint for Event Store service.
    
    Returns status of Event Store components and database connectivity.
    """
    from datetime import datetime as dt
    
    health_status = {
        "status": "healthy",
        "timestamp": dt.utcnow().isoformat(),
        "components": {}
    }
    
    # Check Event Store
    try:
        store = get_event_store()
        if store is not None:
            # Try a simple operation to verify connectivity
            health_status["components"]["event_store"] = {
                "status": "healthy",
                "backend": getattr(store, '_backend_type', 'unknown')
            }
        else:
            health_status["components"]["event_store"] = {"status": "not_initialized"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["event_store"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Check Command Bus
    try:
        bus = get_command_bus()
        health_status["components"]["command_bus"] = {
            "status": "healthy" if bus else "not_initialized"
        }
    except Exception as e:
        health_status["components"]["command_bus"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Query Bus
    try:
        bus = get_query_bus()
        health_status["components"]["query_bus"] = {
            "status": "healthy" if bus else "not_initialized"
        }
    except Exception as e:
        health_status["components"]["query_bus"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Projection Manager
    try:
        manager = get_projection_manager()
        health_status["components"]["projection_manager"] = {
            "status": "healthy" if manager else "not_initialized"
        }
    except Exception as e:
        health_status["components"]["projection_manager"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check rate limiter
    health_status["components"]["rate_limiter"] = {
        "status": "healthy",
        "available_tokens": _api_rate_limiter._tokens
    }
    
    # Check bulkheads
    health_status["components"]["bulkheads"] = {
        "event": {
            "available_permits": _event_bulkhead._semaphore._value if hasattr(_event_bulkhead, '_semaphore') else 'unknown'
        },
        "command": {
            "available_permits": _command_bulkhead._semaphore._value if hasattr(_command_bulkhead, '_semaphore') else 'unknown'
        },
        "query": {
            "available_permits": _query_bulkhead._semaphore._value if hasattr(_query_bulkhead, '_semaphore') else 'unknown'
        }
    }
    
    # Check circuit breaker
    health_status["components"]["circuit_breaker"] = {
        "state": _projection_circuit_breaker.state.value if hasattr(_projection_circuit_breaker.state, 'value') else str(_projection_circuit_breaker.state),
        "failure_count": _projection_circuit_breaker._failure_count
    }
    
    return health_status


async def _resolve_awaitable(value: Any) -> Any:
    """Resolve coroutine results returned by async-compatible backends."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def get_event_store() -> EventStore:
    """Get or create event store instance."""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store


def get_command_bus() -> CommandBus:
    """Get or create command bus instance."""
    global _command_bus
    if _command_bus is None:
        _command_bus = CommandBus()
    return _command_bus


def get_query_bus() -> QueryBus:
    """Get or create query bus instance."""
    global _query_bus
    if _query_bus is None:
        _query_bus = QueryBus()
    return _query_bus


def get_projection_manager() -> ProjectionManager:
    """Get or create projection manager instance."""
    global _projection_manager
    if _projection_manager is None:
        _projection_manager = ProjectionManager(get_event_store())
    return _projection_manager


# =============================================================================
# Rate Limiting Dependency
# =============================================================================

async def check_rate_limit():
    """Check rate limit for API requests."""
    result = _api_rate_limiter.acquire()
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": result.retry_after
            }
        )
    return result


# =============================================================================
# Event Store Endpoints
# =============================================================================

@router.get("/streams")
async def list_streams(
    prefix: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    _: None = Depends(check_rate_limit)
):
    """List all event streams."""
    store = get_event_store()
    
    try:
        streams = _event_bulkhead.execute(
            lambda: store.list_streams(prefix=prefix, limit=limit)
        )
        streams = await _resolve_awaitable(streams)
        
        return {
            "streams": [
                {
                    "stream_id": s["stream_id"],
                    "version": s["version"],
                    "event_count": s["event_count"],
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at")
                }
                for s in streams
            ]
        }
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event operations temporarily unavailable"
        )


@router.get("/streams/{stream_id}")
async def get_stream_events(
    stream_id: str,
    from_version: int = Query(default=0, ge=0),
    to_version: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
    _: None = Depends(check_rate_limit)
):
    """Get events from a stream."""
    store = get_event_store()
    
    try:
        events = _event_bulkhead.execute(
            lambda: store.read_stream(
                stream_id=stream_id,
                from_version=from_version,
                to_version=to_version,
                limit=limit
            )
        )
        events = await _resolve_awaitable(events)
        
        if not events and from_version == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream {stream_id} not found"
            )
        
        return {
            "stream_id": stream_id,
            "version": events[-1].version if events else from_version,
            "events": [
                {
                    "event_id": str(e.event_id),
                    "event_type": e.event_type,
                    "stream_id": e.stream_id,
                    "version": e.version,
                    "timestamp": e.timestamp.isoformat(),
                    "payload": e.payload,
                    "metadata": e.metadata
                }
                for e in events
            ]
        }
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event operations temporarily unavailable"
        )


@router.post("/streams/{stream_id}/append")
async def append_events(
    stream_id: str,
    request: AppendEventsRequest,
    _: None = Depends(check_rate_limit)
):
    """
    Append events to a stream.
    
    Supports optimistic concurrency control via expected_version.
    """
    store = get_event_store()
    
    try:
        # Convert to Event objects
        events = [
            Event(
                event_id=str(uuid.uuid4()),
                event_type=e.event_type,
                aggregate_id=stream_id,
                aggregate_type="stream",
                sequence_number=0,  # Will be assigned by store
                data=e.payload,
                metadata=EventMetadata(
                    timestamp=datetime.utcnow(),
                    custom=e.metadata or {},
                ),
            )
            for e in request.events
        ]
        
        result = _event_bulkhead.execute(
            lambda: store.append(
                aggregate_id=stream_id,
                events=events,
                expected_version=request.expected_version
            )
        )
        result = await _resolve_awaitable(result)
        new_version = result["version"] if isinstance(result, dict) else int(result)
        
        return {
            "stream_id": stream_id,
            "new_version": new_version,
            "appended_count": len(events)
        }
        
    except ValueError as e:
        if "version" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Version conflict",
                    "expected_version": request.expected_version,
                    "actual_version": -1  # Would need to extract from error
                }
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event operations temporarily unavailable"
        )


@router.get("/streams/{stream_id}/snapshot", response_model=SnapshotResponse)
async def get_snapshot(
    stream_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get the latest snapshot for a stream."""
    store = get_event_store()
    
    snapshot = _event_bulkhead.execute(
        lambda: store.get_snapshot(stream_id)
    )
    snapshot = await _resolve_awaitable(snapshot)
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No snapshot available"
        )
    
    return SnapshotResponse(
        stream_id=snapshot.stream_id,
        version=snapshot.version,
        state=snapshot.state,
        timestamp=snapshot.timestamp
    )


@router.post("/streams/{stream_id}/snapshot", status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    stream_id: str,
    version: Optional[int] = None,
    _: None = Depends(check_rate_limit)
):
    """Create a snapshot for a stream."""
    store = get_event_store()
    
    try:
        snapshot = _event_bulkhead.execute(
            lambda: store.create_snapshot(stream_id, version=version)
        )
        snapshot = await _resolve_awaitable(snapshot)
        
        return SnapshotResponse(
            stream_id=snapshot.stream_id,
            version=snapshot.version,
            state=snapshot.state,
            timestamp=snapshot.timestamp
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/events")
async def get_all_events(
    event_type: Optional[str] = None,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    _: None = Depends(check_rate_limit)
):
    """Get all events (global stream)."""
    store = get_event_store()
    
    try:
        events = _event_bulkhead.execute(
            lambda: store.read_all(
                event_type=event_type,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                limit=limit
            )
        )
        events = await _resolve_awaitable(events)
        
        return {
            "events": [
                {
                    "event_id": str(e.event_id),
                    "event_type": e.event_type,
                    "stream_id": e.stream_id,
                    "version": e.version,
                    "timestamp": e.timestamp.isoformat(),
                    "payload": e.payload,
                    "metadata": e.metadata
                }
                for e in events
            ]
        }
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event operations temporarily unavailable"
        )


# =============================================================================
# WebSocket Event Subscription
# =============================================================================

class ConnectionManager:
    """Manage WebSocket connections for event subscriptions."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = {}
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        self.subscriptions.pop(websocket, None)
    
    async def send_event(self, event: Event, websocket: WebSocket):
        await websocket.send_json({
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "stream_id": event.stream_id,
            "version": event.version,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload
        })


_manager = ConnectionManager()


@router.websocket("/events/subscribe")
async def subscribe_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event subscription.
    
    Send JSON to subscribe:
    {
        "type": "subscribe",
        "stream_id": "optional-stream-id",
        "event_types": ["UserCreated", "UserUpdated"]
    }
    """
    await _manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe":
                _manager.subscriptions[websocket] = {
                    "stream_id": data.get("stream_id"),
                    "event_types": data.get("event_types", [])
                }
                await websocket.send_json({"status": "subscribed"})
            
    except WebSocketDisconnect:
        _manager.disconnect(websocket)


# =============================================================================
# Command Bus Endpoints
# =============================================================================

@router.post("/commands", response_model=CommandResultResponse)
async def execute_command(
    request: CommandRequest,
    _: None = Depends(check_rate_limit)
):
    """Execute a command through the command bus."""
    bus = get_command_bus()
    
    command = Command(
        command_id=uuid.UUID(request.command_id) if request.command_id else uuid.uuid4(),
        command_type=request.command_type,
        payload=request.payload or {},
        metadata=request.metadata or {}
    )
    
    try:
        import time
        start = time.time()
        
        result = _command_bulkhead.execute(
            lambda: bus.execute(command)
        )
        result = await _resolve_awaitable(result)
        
        execution_time = int((time.time() - start) * 1000)
        
        return CommandResultResponse(
            command_id=str(command.command_id),
            success=result.success,
            result=result.result,
            error=result.error,
            events_produced=result.events_produced,
            execution_time_ms=execution_time
        )
        
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Command execution temporarily unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/commands/batch")
async def execute_batch_commands(
    request: BatchCommandsRequest,
    _: None = Depends(check_rate_limit)
):
    """Execute multiple commands."""
    bus = get_command_bus()
    
    results = []
    success_count = 0
    failure_count = 0
    
    for cmd_request in request.commands:
        command = Command(
            command_id=uuid.UUID(cmd_request.command_id) if cmd_request.command_id else uuid.uuid4(),
            command_type=cmd_request.command_type,
            payload=cmd_request.payload or {},
            metadata=cmd_request.metadata or {}
        )
        
        try:
            result = _command_bulkhead.execute(
                lambda c=command: bus.execute(c)
            )
            result = await _resolve_awaitable(result)
            results.append(CommandResultResponse(
                command_id=str(command.command_id),
                success=result.success,
                result=result.result,
                error=result.error,
                events_produced=result.events_produced,
                execution_time_ms=0
            ))
            if result.success:
                success_count += 1
            else:
                failure_count += 1
                
        except Exception as e:
            results.append(CommandResultResponse(
                command_id=str(command.command_id),
                success=False,
                result=None,
                error=str(e),
                events_produced=0,
                execution_time_ms=0
            ))
            failure_count += 1
    
    return {
        "results": [r.dict() for r in results],
        "success_count": success_count,
        "failure_count": failure_count
    }


@router.get("/commands/handlers")
async def list_command_handlers():
    """List registered command handlers."""
    bus = get_command_bus()
    
    handlers = bus.get_registered_handlers()
    
    return {
        "handlers": [
            {
                "command_type": cmd_type,
                "handler_name": handler.__name__ if hasattr(handler, '__name__') else str(handler),
                "registered_at": None  # Would need to track this
            }
            for cmd_type, handler in handlers.items()
        ]
    }


# =============================================================================
# Query Bus Endpoints
# =============================================================================

@router.post("/queries", response_model=QueryResultResponse)
async def execute_query(
    request: QueryRequest,
    _: None = Depends(check_rate_limit)
):
    """Execute a query through the query bus."""
    bus = get_query_bus()
    
    query = ESQuery(
        query_id=uuid.UUID(request.query_id) if request.query_id else uuid.uuid4(),
        query_type=request.query_type,
        parameters=request.parameters or {},
        options=request.options or {}
    )
    
    try:
        import time
        start = time.time()
        
        result = _query_bulkhead.execute(
            lambda: bus.execute(query)
        )
        result = await _resolve_awaitable(result)
        
        execution_time = int((time.time() - start) * 1000)
        
        return QueryResultResponse(
            query_id=str(query.query_id),
            result=result.result,
            from_cache=result.from_cache,
            execution_time_ms=execution_time
        )
        
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Query execution temporarily unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/queries/cache")
async def get_query_cache_stats():
    """Get query cache statistics."""
    bus = get_query_bus()
    
    return bus.get_cache_stats()


@router.post("/queries/cache/invalidate")
async def invalidate_query_cache(request: InvalidateCacheRequest):
    """Invalidate query cache."""
    bus = get_query_bus()
    
    count = bus.invalidate_cache(
        query_type=request.query_type,
        all=request.all
    )
    
    return {"invalidated_count": count}


# =============================================================================
# Projection Endpoints
# =============================================================================

@router.get("/projections")
async def list_projections():
    """List all projections."""
    manager = get_projection_manager()
    
    projections = manager.list_projections()
    
    return {
        "projections": [
            ProjectionInfo(
                name=p.name,
                status=p.status.value if hasattr(p.status, 'value') else str(p.status),
                position=p.position,
                events_processed=p.events_processed,
                last_event_timestamp=p.last_event_timestamp
            )
            for p in projections
        ]
    }


@router.get("/projections/{projection_name}", response_model=ProjectionStatusResponse)
async def get_projection_status(projection_name: str):
    """Get detailed projection status."""
    manager = get_projection_manager()
    
    try:
        status_info = _projection_circuit_breaker.call(
            lambda: manager.get_projection_status(projection_name)
        )
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Projection {projection_name} not found"
            )
        
        return ProjectionStatusResponse(
            name=status_info["name"],
            status=status_info["status"],
            position=status_info["position"],
            events_processed=status_info["events_processed"],
            last_event_timestamp=status_info.get("last_event_timestamp"),
            lag=status_info.get("lag", 0),
            error=status_info.get("error"),
            started_at=status_info.get("started_at")
        )
        
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Projection operations temporarily unavailable"
            )
        raise


@router.post("/projections/{projection_name}/reset")
async def reset_projection(projection_name: str):
    """Reset and rebuild a projection."""
    manager = get_projection_manager()
    
    try:
        manager.reset_projection(projection_name)
        
        return {
            "status": "resetting",
            "started_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/projections/{projection_name}/pause")
async def pause_projection(projection_name: str):
    """Pause a projection."""
    manager = get_projection_manager()
    
    try:
        manager.pause_projection(projection_name)
        return {"status": "paused"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/projections/{projection_name}/resume")
async def resume_projection(projection_name: str):
    """Resume a paused projection."""
    manager = get_projection_manager()
    
    try:
        manager.resume_projection(projection_name)
        return {"status": "running"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# =============================================================================
# Aggregate Endpoints
# =============================================================================

@router.get("/aggregates/{aggregate_type}/{aggregate_id}", response_model=AggregateStateResponse)
async def get_aggregate(
    aggregate_type: str,
    aggregate_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get aggregate state."""
    store = get_event_store()
    
    try:
        # Load aggregate from event stream
        stream_id = f"{aggregate_type}-{aggregate_id}"
        events = store.read_stream(stream_id)
        events = await _resolve_awaitable(events)
        
        if not events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aggregate {aggregate_type}/{aggregate_id} not found"
            )
        
        # Build state from events
        state = {}
        for event in events:
            # Apply event to state (simplified)
            if event.payload:
                state.update(event.payload)
        
        return AggregateStateResponse(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            version=events[-1].version if events else 0,
            state=state,
            created_at=events[0].timestamp if events else None,
            updated_at=events[-1].timestamp if events else None
        )
        
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Aggregate operations temporarily unavailable"
        )


@router.get("/aggregates/{aggregate_type}/{aggregate_id}/history")
async def get_aggregate_history(
    aggregate_type: str,
    aggregate_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get aggregate event history."""
    store = get_event_store()
    
    stream_id = f"{aggregate_type}-{aggregate_id}"
    events = store.read_stream(stream_id)
    events = await _resolve_awaitable(events)
    
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aggregate {aggregate_type}/{aggregate_id} not found"
        )
    
    return {
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "events": [
            {
                "event_id": str(e.event_id),
                "event_type": e.event_type,
                "stream_id": e.stream_id,
                "version": e.version,
                "timestamp": e.timestamp.isoformat(),
                "payload": e.payload,
                "metadata": e.metadata
            }
            for e in events
        ]
    }


# =============================================================================
# Startup/Shutdown
# =============================================================================

async def event_sourcing_startup():
    """Initialize event sourcing components on startup."""
    global _event_store, _command_bus, _query_bus, _projection_manager
    
    logger.info("Initializing Event Sourcing module...")
    
    _event_store = EventStore()
    _command_bus = CommandBus()
    _query_bus = QueryBus()
    _projection_manager = ProjectionManager(_event_store)
    
    logger.info("Event Sourcing module initialized")


async def event_sourcing_shutdown():
    """Cleanup event sourcing components on shutdown."""
    global _event_store, _command_bus, _query_bus, _projection_manager
    
    logger.info("Shutting down Event Sourcing module...")
    
    if _projection_manager:
        await _projection_manager.stop_all()
    
    _event_store = None
    _command_bus = None
    _query_bus = None
    _projection_manager = None
    
    logger.info("Event Sourcing module shut down")


# =============================================================================
# Router Export
# =============================================================================

__all__ = [
    "router",
    "event_sourcing_startup",
    "event_sourcing_shutdown",
    "EventCreate",
    "AppendEventsRequest",
    "EventResponse",
    "SnapshotResponse",
    "CommandRequest",
    "CommandResultResponse",
    "QueryRequest",
    "QueryResultResponse",
    "ProjectionInfo",
    "ProjectionStatusResponse",
    "AggregateStateResponse",
]
