"""
Edge Computing API Endpoints
============================

FastAPI endpoints for Edge Computing module.
Implements OpenAPI specification from docs/api/edge_openapi.yaml

Features:
- Edge Node management (register, deregister, drain, resources)
- Task distribution (submit, status, cancel, batch)
- Edge Cache operations (get, set, delete, invalidate)
- Health monitoring

Integrates resilience patterns:
- Rate limiting for API protection
- Bulkhead for resource isolation
- Fallback for graceful degradation

Integrates Prometheus metrics for observability.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import edge computing components
from src.edge.edge_node import EdgeNode, EdgeNodeConfig, EdgeNodeManager, EdgeNodeStatus
from src.edge.task_distributor import TaskDistributor, DistributionStrategy as TaskDistributionStrategy
from src.edge.edge_cache import EdgeCache, CacheConfig, CachePolicy

# Import resilience patterns
from src.resilience import (
    TokenBucket,
    SemaphoreBulkhead,
    BulkheadFullException,
    FallbackExecutor,
    DefaultValueFallback,
    CircuitBreaker,
    CircuitBreakerConfig,
    RateLimitExceeded,
)

# Import metrics
try:
    from src.monitoring.edge_event_sourcing_metrics import (
        edge_metrics,
        resilience_metrics,
    )
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    edge_metrics = None
    resilience_metrics = None

logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models (matching OpenAPI spec)
# =============================================================================

class EdgeNodeRegister(BaseModel):
    """Request to register a new edge node."""
    endpoint: str = Field(..., description="Node endpoint URL")
    name: Optional[str] = Field(None, description="Node name")
    capabilities: List[str] = Field(default_factory=list, description="Node capabilities")
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent tasks")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ResourceMetrics(BaseModel):
    """Resource metrics for an edge node."""
    cpu_percent: float = Field(..., ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)
    network_mbps: Optional[float] = Field(None, ge=0)
    gpu_percent: Optional[float] = Field(None, ge=0, le=100)
    load_average: Optional[List[float]] = Field(None, min_items=3, max_items=3)
    available_memory_mb: Optional[int] = Field(None, ge=0)
    total_memory_mb: Optional[int] = Field(None, ge=0)


class EdgeNodeResponse(BaseModel):
    """Response for edge node operations."""
    node_id: str
    name: Optional[str]
    endpoint: str
    status: str
    capabilities: List[str]
    current_tasks: int
    max_concurrent_tasks: int
    registered_at: datetime
    last_heartbeat: Optional[datetime]
    resources: Optional[ResourceMetrics]


class TaskSubmit(BaseModel):
    """Request to submit a task."""
    type: str = Field(..., description="Task type identifier")
    payload: Dict[str, Any] = Field(..., description="Task payload")
    priority: str = Field(default="normal", description="Task priority")
    required_capabilities: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300)
    retry_count: int = Field(default=3)
    metadata: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Response for task submission."""
    task_id: str
    node_id: Optional[str]
    status: str
    submitted_at: datetime
    estimated_start: Optional[datetime]


class BatchTasksRequest(BaseModel):
    """Request to submit multiple tasks."""
    tasks: List[TaskSubmit]


class TaskStatus(BaseModel):
    """Task status response."""
    task_id: str
    node_id: Optional[str]
    status: str
    progress: Optional[float] = Field(None, ge=0, le=100)
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]


class TaskResult(BaseModel):
    """Task result response."""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time_ms: Optional[int]
    node_id: Optional[str]


class CacheValueRequest(BaseModel):
    """Request to set cache value."""
    value: Any
    ttl_seconds: int = Field(default=300)
    tags: List[str] = Field(default_factory=list)


class CacheInvalidateRequest(BaseModel):
    """Request to invalidate cache."""
    pattern: Optional[str] = None
    tags: Optional[List[str]] = None


class DistributionStrategyUpdate(BaseModel):
    """Request to update distribution strategy."""
    strategy: str
    config: Optional[Dict[str, Any]] = None


class EdgeHealth(BaseModel):
    """Edge computing health status."""
    healthy: bool
    timestamp: datetime
    nodes: Dict[str, Any]
    tasks: Dict[str, Any]
    cache: Dict[str, Any]


# =============================================================================
# Router Setup with Resilience
# =============================================================================

router = APIRouter(prefix="/edge", tags=["Edge Computing"])

# Global instances (initialized on startup)
_node_manager: Optional[EdgeNodeManager] = None
_task_distributor: Optional[TaskDistributor] = None
_edge_cache: Optional[EdgeCache] = None

# Resilience patterns
_api_rate_limiter = TokenBucket(capacity=100, refill_rate=20.0, name="edge_api")
_node_bulkhead = SemaphoreBulkhead(max_concurrent=10, name="node_operations")
_task_bulkhead = SemaphoreBulkhead(max_concurrent=20, name="task_operations")
_cache_bulkhead = SemaphoreBulkhead(max_concurrent=50, name="cache_operations")

# Circuit breaker for external node communication
_node_circuit_breaker = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout_seconds=30,
        success_threshold=2
    ),
    name="node_communication"
)

# Fallback for degraded mode
_degraded_node_fallback = DefaultValueFallback({"status": "degraded", "message": "Node temporarily unavailable"})


async def _resolve_awaitable(value: Any) -> Any:
    """Resolve coroutine results returned by async-compatible backends."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def get_node_manager() -> EdgeNodeManager:
    """Get or create node manager instance."""
    global _node_manager
    if _node_manager is None:
        _node_manager = EdgeNodeManager()
    return _node_manager


def get_task_distributor() -> TaskDistributor:
    """Get or create task distributor instance."""
    global _task_distributor
    if _task_distributor is None:
        node_manager = get_node_manager()
        _task_distributor = TaskDistributor(
            node_manager=node_manager,
            strategy=TaskDistributionStrategy.ADAPTIVE
        )
    return _task_distributor


def get_edge_cache() -> EdgeCache:
    """Get or create edge cache instance."""
    global _edge_cache
    if _edge_cache is None:
        _edge_cache = EdgeCache(
            CacheConfig(
                max_entries=10000,
                policy=CachePolicy.ADAPTIVE,
            )
        )
    return _edge_cache


# =============================================================================
# Rate Limiting Dependency
# =============================================================================

async def check_rate_limit():
    """Check rate limit for API requests."""
    result = _api_rate_limiter.acquire()
    
    # Record metrics
    if METRICS_ENABLED and resilience_metrics:
        resilience_metrics.record_rate_limit("edge", result.allowed)
    
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
# Edge Node Endpoints
# =============================================================================

@router.get("/nodes", response_model=Dict[str, Any])
async def list_edge_nodes(
    status_filter: Optional[str] = Query(None, alias="status"),
    capability: Optional[str] = Query(None),
    _: None = Depends(check_rate_limit)
):
    """
    List all registered edge nodes.
    
    Supports filtering by status and capability.
    """
    manager = get_node_manager()
    
    try:
        nodes = _node_bulkhead.execute(
            lambda: manager.list_nodes(
                status_filter=status_filter,
                capability_filter=capability
            )
        )
        
        return {
            "nodes": [
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "endpoint": node.endpoint,
                    "status": node.status.value if hasattr(node.status, 'value') else node.status,
                    "capabilities": node.capabilities,
                    "current_tasks": node.current_tasks,
                    "max_concurrent_tasks": node.max_concurrent_tasks,
                    "registered_at": node.registered_at.isoformat() if node.registered_at else None,
                    "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None
                }
                for node in nodes
            ],
            "total": len(nodes)
        }
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node operations temporarily unavailable"
        )


@router.post("/nodes", response_model=EdgeNodeResponse, status_code=status.HTTP_201_CREATED)
async def register_edge_node(
    request: EdgeNodeRegister,
    _: None = Depends(check_rate_limit)
):
    """
    Register a new edge node.
    
    The node will be available for task distribution after registration.
    """
    manager = get_node_manager()
    start_time = time.perf_counter()
    
    try:
        node = _node_bulkhead.execute(
            lambda: manager.register_node(
                endpoint=request.endpoint,
                name=request.name,
                capabilities=request.capabilities,
                max_concurrent_tasks=request.max_concurrent_tasks,
                metadata=request.metadata
            )
        )
        
        # Record metrics
        duration = time.perf_counter() - start_time
        if METRICS_ENABLED and edge_metrics:
            edge_metrics.record_node_registration(success=True, duration=duration)
        
        return EdgeNodeResponse(
            node_id=node.node_id,
            name=node.name,
            endpoint=node.endpoint,
            status=node.status.value if hasattr(node.status, 'value') else node.status,
            capabilities=node.capabilities,
            current_tasks=node.current_tasks,
            max_concurrent_tasks=node.max_concurrent_tasks,
            registered_at=node.registered_at,
            last_heartbeat=node.last_heartbeat,
            resources=None
        )
    except BulkheadFullException:
        if METRICS_ENABLED and edge_metrics:
            edge_metrics.record_node_registration(success=False, duration=time.perf_counter() - start_time)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node registration temporarily unavailable"
        )
    except Exception as e:
        logger.error(f"Failed to register node: {e}")
        if METRICS_ENABLED and edge_metrics:
            edge_metrics.record_node_registration(success=False, duration=time.perf_counter() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/nodes/{node_id}", response_model=EdgeNodeResponse)
async def get_edge_node(
    node_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get details of a specific edge node."""
    manager = get_node_manager()
    
    node = manager.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )
    
    return EdgeNodeResponse(
        node_id=node.node_id,
        name=node.name,
        endpoint=node.endpoint,
        status=node.status.value if hasattr(node.status, 'value') else node.status,
        capabilities=node.capabilities,
        current_tasks=node.current_tasks,
        max_concurrent_tasks=node.max_concurrent_tasks,
        registered_at=node.registered_at,
        last_heartbeat=node.last_heartbeat,
        resources=None
    )


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_edge_node(
    node_id: str,
    _: None = Depends(check_rate_limit)
):
    """Deregister an edge node."""
    manager = get_node_manager()
    
    try:
        success = _node_bulkhead.execute(
            lambda: manager.deregister_node(node_id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node {node_id} not found"
            )
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node operations temporarily unavailable"
        )


@router.post("/nodes/{node_id}/drain")
async def drain_edge_node(
    node_id: str,
    _: None = Depends(check_rate_limit)
):
    """
    Put node in draining mode.
    
    No new tasks will be assigned. Existing tasks will complete.
    """
    manager = get_node_manager()
    
    try:
        pending_tasks = _node_bulkhead.execute(
            lambda: manager.drain_node(node_id)
        )
        
        return {
            "status": "draining",
            "pending_tasks": pending_tasks
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/nodes/{node_id}/resources", response_model=ResourceMetrics)
async def get_node_resources(
    node_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get resource metrics for a node."""
    manager = get_node_manager()
    
    # Use circuit breaker for external node communication
    try:
        resources = _node_circuit_breaker.call(
            lambda: manager.get_node_resources(node_id)
        )
        
        if not resources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node {node_id} not found or resources unavailable"
            )
        
        return ResourceMetrics(**resources)
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            # Fallback to degraded response
            return ResourceMetrics(
                cpu_percent=0,
                memory_percent=0,
                disk_percent=0
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


# =============================================================================
# Task Distribution Endpoints
# =============================================================================

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_task(
    request: TaskSubmit,
    background_tasks: BackgroundTasks,
    _: None = Depends(check_rate_limit)
):
    """
    Submit a task for distribution.
    
    The task will be routed to an appropriate edge node based on
    the current distribution strategy.
    """
    distributor = get_task_distributor()
    manager = get_node_manager()
    
    task_id = str(uuid.uuid4())
    submitted_at = datetime.utcnow()
    start_time = time.perf_counter()
    
    try:
        result = _task_bulkhead.execute(
            lambda: distributor.distribute_task(
                task_id=task_id,
                task_type=request.type,
                payload=request.payload,
                priority=request.priority,
                required_capabilities=request.required_capabilities,
                timeout_seconds=request.timeout_seconds,
                retry_count=request.retry_count,
                metadata=request.metadata
            )
        )
        result = await _resolve_awaitable(result)
        if isinstance(result, tuple):
            result = {"node_id": result[1] if len(result) > 1 else None}
        if not isinstance(result, dict):
            result = {}
        
        # Record metrics
        duration = time.perf_counter() - start_time
        if METRICS_ENABLED and edge_metrics:
            edge_metrics.record_task_submitted(
                task_type=request.type,
                priority=request.priority,
                duration=duration
            )
        
        return TaskResponse(
            task_id=task_id,
            node_id=result.get("node_id"),
            status="queued",
            submitted_at=submitted_at,
            estimated_start=result.get("estimated_start")
        )
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task submission temporarily unavailable"
        )
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get the status of a submitted task."""
    distributor = get_task_distributor()
    
    task_status = distributor.get_task_status(task_id)
    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return TaskStatus(
        task_id=task_id,
        node_id=task_status.get("node_id"),
        status=task_status.get("status", "unknown"),
        progress=task_status.get("progress"),
        started_at=task_status.get("started_at"),
        completed_at=task_status.get("completed_at"),
        error=task_status.get("error")
    )


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    _: None = Depends(check_rate_limit)
):
    """Cancel a submitted task."""
    distributor = get_task_distributor()
    
    success = distributor.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found or already completed"
        )
    
    return {"status": "cancelled"}


@router.get("/tasks/{task_id}/result", response_model=TaskResult)
async def get_task_result(
    task_id: str,
    _: None = Depends(check_rate_limit)
):
    """Get the result of a completed task."""
    distributor = get_task_distributor()
    
    result = distributor.get_task_result(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not ready or task failed"
        )
    
    return TaskResult(
        task_id=task_id,
        status=result.get("status", "unknown"),
        result=result.get("result"),
        error=result.get("error"),
        execution_time_ms=result.get("execution_time_ms"),
        node_id=result.get("node_id")
    )


@router.post("/tasks/batch", status_code=status.HTTP_202_ACCEPTED)
async def submit_batch_tasks(
    request: BatchTasksRequest,
    strategy: Optional[str] = None,
    _: None = Depends(check_rate_limit)
):
    """Submit multiple tasks for distribution."""
    distributor = get_task_distributor()
    
    batch_id = str(uuid.uuid4())
    task_ids = []
    
    for task in request.tasks:
        task_id = str(uuid.uuid4())
        try:
            result = _task_bulkhead.execute(
                lambda task=task, task_id=task_id: distributor.distribute_task(
                    task_id=task_id,
                    task_type=task.type,
                    payload=task.payload,
                    priority=task.priority,
                    required_capabilities=task.required_capabilities
                )
            )
            await _resolve_awaitable(result)
            task_ids.append(task_id)
        except Exception as e:
            logger.warning(f"Failed to submit task in batch: {e}")
    
    return {
        "batch_id": batch_id,
        "task_ids": task_ids
    }


@router.get("/distribution/strategy")
async def get_distribution_strategy():
    """Get current distribution strategy."""
    distributor = get_task_distributor()
    
    return {
        "strategy": distributor.get_strategy().value if hasattr(distributor.get_strategy(), 'value') else str(distributor.get_strategy()),
        "config": distributor.get_strategy_config()
    }


@router.put("/distribution/strategy")
async def set_distribution_strategy(request: DistributionStrategyUpdate):
    """Set distribution strategy."""
    distributor = get_task_distributor()
    
    try:
        strategy = TaskDistributionStrategy(request.strategy)
        distributor.set_strategy(strategy, request.config)
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy: {request.strategy}"
        )


# =============================================================================
# Cache Endpoints
# =============================================================================

@router.get("/cache")
async def get_cache_stats():
    """Get cache statistics."""
    cache = get_edge_cache()
    
    try:
        stats = _cache_bulkhead.execute(lambda: cache.get_stats())
        return stats
    except BulkheadFullException:
        return {"error": "Cache temporarily unavailable"}


@router.get("/cache/{key}")
async def get_cache_value(
    key: str,
    _: None = Depends(check_rate_limit)
):
    """Get a cached value."""
    cache = get_edge_cache()
    start_time = time.perf_counter()
    
    try:
        entry = _cache_bulkhead.execute(lambda: cache.get(key))
        
        # Record metrics
        duration = time.perf_counter() - start_time
        if METRICS_ENABLED and edge_metrics:
            edge_metrics.record_cache_get(hit=entry is not None, duration=duration)
        
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key '{key}' not found"
            )
        
        return {
            "key": key,
            "value": entry.get("value"),
            "ttl_seconds": entry.get("ttl_seconds"),
            "created_at": entry.get("created_at")
        }
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache temporarily unavailable"
        )


@router.put("/cache/{key}")
async def set_cache_value(
    key: str,
    request: CacheValueRequest,
    _: None = Depends(check_rate_limit)
):
    """Store a value in cache."""
    cache = get_edge_cache()
    
    try:
        _cache_bulkhead.execute(
            lambda: cache.set(
                key,
                request.value,
                ttl_seconds=request.ttl_seconds,
                tags=request.tags
            )
        )
        return {"status": "cached"}
    except BulkheadFullException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache temporarily unavailable"
        )


@router.delete("/cache/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cache_value(
    key: str,
    _: None = Depends(check_rate_limit)
):
    """Delete a cached value."""
    cache = get_edge_cache()
    
    _cache_bulkhead.execute(lambda: cache.delete(key))


@router.post("/cache/invalidate")
async def invalidate_cache(
    request: CacheInvalidateRequest,
    _: None = Depends(check_rate_limit)
):
    """Invalidate cache entries by pattern or tags."""
    cache = get_edge_cache()
    
    count = _cache_bulkhead.execute(
        lambda: cache.invalidate(
            pattern=request.pattern,
            tags=request.tags
        )
    )
    
    return {"invalidated_count": count}


# =============================================================================
# Health Endpoints
# =============================================================================

@router.get("/health", response_model=EdgeHealth)
async def get_edge_health():
    """Get overall edge computing health."""
    start_time = time.perf_counter()
    
    manager = get_node_manager()
    distributor = get_task_distributor()
    cache = get_edge_cache()
    
    nodes = manager.list_nodes()
    active_nodes = [n for n in nodes if n.status == EdgeNodeStatus.ACTIVE]
    healthy = len(active_nodes) > 0
    
    # Update metrics
    if METRICS_ENABLED and edge_metrics:
        edge_metrics.set_health_status(healthy)
        edge_metrics.update_nodes_count(
            active=len(active_nodes),
            inactive=len([n for n in nodes if n.status == EdgeNodeStatus.INACTIVE]),
            draining=len([n for n in nodes if n.status == EdgeNodeStatus.DRAINING])
        )
        edge_metrics.record_health_check(time.perf_counter() - start_time)
        
        # Update cache stats
        cache_stats = cache.get_stats()
        edge_metrics.update_cache_stats(
            size=cache_stats.get("size", 0),
            memory_bytes=cache_stats.get("memory_bytes", 0),
            hit_ratio=cache_stats.get("hit_rate", 0.0)
        )
    
    return EdgeHealth(
        healthy=healthy,
        timestamp=datetime.utcnow(),
        nodes={
            "total": len(nodes),
            "active": len(active_nodes),
            "inactive": len(nodes) - len(active_nodes),
            "draining": len([n for n in nodes if n.status == EdgeNodeStatus.DRAINING])
        },
        tasks=distributor.get_stats(),
        cache=cache.get_stats()
    )


@router.get("/health/nodes")
async def get_nodes_health():
    """Get health status of all nodes."""
    manager = get_node_manager()
    
    nodes = manager.list_nodes()
    
    return {
        "healthy": len([n for n in nodes if n.status == EdgeNodeStatus.ACTIVE]),
        "unhealthy": len([n for n in nodes if n.status == EdgeNodeStatus.INACTIVE]),
        "draining": len([n for n in nodes if n.status == EdgeNodeStatus.DRAINING]),
        "nodes": [
            {
                "node_id": n.node_id,
                "healthy": n.status == EdgeNodeStatus.ACTIVE,
                "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None
            }
            for n in nodes
        ]
    }


# =============================================================================
# Startup/Shutdown
# =============================================================================

async def edge_startup():
    """Initialize edge computing components on startup."""
    global _node_manager, _task_distributor, _edge_cache
    
    logger.info("Initializing Edge Computing module...")
    
    _node_manager = EdgeNodeManager()
    _task_distributor = TaskDistributor(
        node_manager=_node_manager,
        strategy=TaskDistributionStrategy.ADAPTIVE,
    )
    _edge_cache = EdgeCache(
        CacheConfig(
            max_entries=10000,
            policy=CachePolicy.ADAPTIVE,
        )
    )
    
    logger.info("Edge Computing module initialized")


async def edge_shutdown():
    """Cleanup edge computing components on shutdown."""
    global _node_manager, _task_distributor, _edge_cache
    
    logger.info("Shutting down Edge Computing module...")
    
    if _task_distributor:
        await _task_distributor.shutdown()
    
    _node_manager = None
    _task_distributor = None
    _edge_cache = None
    
    logger.info("Edge Computing module shut down")


# =============================================================================
# Router Export
# =============================================================================

__all__ = [
    "router",
    "edge_startup",
    "edge_shutdown",
    "EdgeNodeRegister",
    "EdgeNodeResponse",
    "ResourceMetrics",
    "TaskSubmit",
    "TaskResponse",
    "TaskStatus",
    "TaskResult",
    "CacheValueRequest",
    "CacheInvalidateRequest",
    "DistributionStrategyUpdate",
    "EdgeHealth",
]
