"""
Edge Node - Core edge computing node implementation.

Provides local processing, caching, and task execution capabilities
for distributed edge computing infrastructure.
"""

import asyncio
import logging
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EdgeNodeState(Enum):
    """States of an edge node."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class EdgeNodeStatus(Enum):
    """API-facing status enum — maps from EdgeNodeState."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAINING = "draining"


class TaskPriority(Enum):
    """Priority levels for edge tasks."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class EdgeNodeConfig:
    """Configuration for an edge node."""
    node_id: str = ""
    name: str = ""
    region: str = "default"
    zone: str = "default"
    
    # Resource limits
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 85.0
    max_concurrent_tasks: int = 10
    max_queue_size: int = 100
    
    # Network settings
    listen_port: int = 8080
    advertise_host: str = ""
    heartbeat_interval_seconds: float = 10.0
    node_timeout_seconds: float = 60.0
    
    # Capabilities
    capabilities: Set[str] = field(default_factory=lambda: {"compute", "storage", "cache"})
    tags: Dict[str, str] = field(default_factory=dict)
    
    # Processing settings
    task_timeout_seconds: float = 300.0
    result_cache_ttl_seconds: float = 3600.0
    enable_auto_scaling: bool = True
    
    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"edge-{uuid.uuid4().hex[:8]}"
        if not self.name:
            self.name = self.node_id


@dataclass
class EdgeTask:
    """A task to be executed on an edge node."""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0
    required_capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None
    
    @property
    def is_failed(self) -> bool:
        return self.error is not None and self.completed_at is not None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class NodeResources:
    """Resource metrics for an edge node."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    active_tasks: int = 0
    queued_tasks: int = 0
    available_slots: int = 0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "network_in_mbps": self.network_in_mbps,
            "network_out_mbps": self.network_out_mbps,
            "active_tasks": self.active_tasks,
            "queued_tasks": self.queued_tasks,
            "available_slots": self.available_slots,
        }


class EdgeNode:
    """
    Edge computing node with local processing capabilities.
    
    Features:
    - Task queue management with priorities
    - Resource monitoring and limits
    - Capability-based task routing
    - Result caching
    - Health monitoring
    """
    
    def __init__(self, config: Optional[EdgeNodeConfig] = None):
        self.config = config or EdgeNodeConfig()
        self.state = EdgeNodeState.INITIALIZING
        self._task_queue: List[EdgeTask] = []
        self._active_tasks: Dict[str, EdgeTask] = {}
        self._completed_tasks: Dict[str, EdgeTask] = {}
        self._result_cache: Dict[str, tuple] = {}  # (result, timestamp)
        self._task_handlers: Dict[str, Callable] = {}
        self._resources = NodeResources()
        self._last_heartbeat: Optional[datetime] = None
        self._started_at: Optional[datetime] = None
        self._running = False
        self._stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "total_processing_time": 0.0,
        }
        
    @property
    def status(self) -> "EdgeNodeStatus":
        """API-facing status derived from internal state."""
        if self.state in (EdgeNodeState.READY, EdgeNodeState.BUSY, EdgeNodeState.DEGRADED):
            return EdgeNodeStatus.ACTIVE
        if self.state == EdgeNodeState.MAINTENANCE:
            return EdgeNodeStatus.DRAINING
        return EdgeNodeStatus.INACTIVE

    @property
    def node_id(self) -> str:
        """Shortcut to config.node_id for API compatibility."""
        return self.config.node_id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def endpoint(self) -> str:
        host = self.config.advertise_host or "localhost"
        return f"http://{host}:{self.config.listen_port}"

    @property
    def capabilities(self) -> List[str]:
        return sorted(self.config.capabilities)

    @property
    def current_tasks(self) -> int:
        return len(self._active_tasks)

    @property
    def max_concurrent_tasks(self) -> int:
        return self.config.max_concurrent_tasks

    @property
    def registered_at(self) -> Optional[datetime]:
        return self._started_at

    @property
    def last_heartbeat(self) -> Optional[datetime]:
        """Expose internal heartbeat timestamp."""
        return self._last_heartbeat

    async def start(self) -> None:
        """Start the edge node."""
        logger.info(f"Starting edge node {self.config.node_id}")
        
        self._started_at = datetime.utcnow()
        self.state = EdgeNodeState.READY
        self._running = True
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._task_processor_loop())
        asyncio.create_task(self._resource_monitor_loop())
        
        logger.info(f"Edge node {self.config.node_id} started in region {self.config.region}")
    
    async def stop(self) -> None:
        """Stop the edge node gracefully."""
        logger.info(f"Stopping edge node {self.config.node_id}")
        
        self._running = False
        self.state = EdgeNodeState.OFFLINE
        
        # Wait for active tasks to complete
        while self._active_tasks:
            await asyncio.sleep(0.1)
        
        logger.info(f"Edge node {self.config.node_id} stopped")
    
    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a handler for a task type."""
        self._task_handlers[task_type] = handler
        self.config.capabilities.add(task_type)
        logger.debug(f"Registered handler for task type: {task_type}")
    
    def unregister_handler(self, task_type: str) -> None:
        """Unregister a task handler."""
        if task_type in self._task_handlers:
            del self._task_handlers[task_type]
            self.config.capabilities.discard(task_type)
    
    async def submit_task(self, task: EdgeTask) -> str:
        """
        Submit a task to the node.
        
        Returns task_id if accepted, raises exception if rejected.
        """
        # Check capabilities
        if task.required_capabilities:
            missing = task.required_capabilities - self.config.capabilities
            if missing:
                raise ValueError(f"Missing capabilities: {missing}")
        
        # Check queue capacity
        if len(self._task_queue) >= self.config.max_queue_size:
            raise RuntimeError("Task queue is full")
        
        # Check node state
        if self.state == EdgeNodeState.OFFLINE:
            raise RuntimeError("Node is offline")
        
        if self.state == EdgeNodeState.MAINTENANCE:
            raise RuntimeError("Node is in maintenance mode")
        
        # Add to queue
        self._task_queue.append(task)
        self._sort_queue()
        
        logger.debug(f"Task {task.task_id} queued, queue size: {len(self._task_queue)}")
        
        return task.task_id
    
    def _sort_queue(self) -> None:
        """Sort task queue by priority."""
        self._task_queue.sort(key=lambda t: t.priority.value)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or active task."""
        # Check queue
        for i, task in enumerate(self._task_queue):
            if task.task_id == task_id:
                self._task_queue.pop(i)
                logger.debug(f"Task {task_id} cancelled from queue")
                return True
        
        # Check active tasks
        if task_id in self._active_tasks:
            # Mark for cancellation (handler should check)
            self._active_tasks[task_id].error = "Cancelled"
            logger.debug(f"Task {task_id} marked for cancellation")
            return True
        
        return False
    
    def get_task_status(self, task_id: str) -> Optional[EdgeTask]:
        """Get current status of a task."""
        # Check active
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]
        
        # Check completed
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        
        # Check queue
        for task in self._task_queue:
            if task.task_id == task_id:
                return task
        
        return None
    
    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if still valid."""
        if cache_key in self._result_cache:
            result, timestamp = self._result_cache[cache_key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.config.result_cache_ttl_seconds:
                return result
            else:
                del self._result_cache[cache_key]
        return None
    
    def cache_result(self, cache_key: str, result: Any) -> None:
        """Cache a result."""
        self._result_cache[cache_key] = (result, datetime.utcnow())
        
        # Simple cache eviction
        if len(self._result_cache) > 1000:
            # Remove oldest entries
            sorted_items = sorted(
                self._result_cache.items(),
                key=lambda x: x[1][1]
            )
            for key, _ in sorted_items[:100]:
                del self._result_cache[key]
    
    def get_resources(self) -> NodeResources:
        """Get current resource metrics."""
        return self._resources
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        return {
            "node_id": self.config.node_id,
            "state": self.state.value,
            "region": self.config.region,
            "zone": self.config.zone,
            "uptime_seconds": (
                (datetime.utcnow() - self._started_at).total_seconds()
                if self._started_at else 0
            ),
            "queue_size": len(self._task_queue),
            "active_tasks": len(self._active_tasks),
            "completed_tasks": len(self._completed_tasks),
            "cache_size": len(self._result_cache),
            "capabilities": list(self.config.capabilities),
            **self._stats,
            **self._resources.to_dict(),
        }
    
    def can_accept_task(self) -> bool:
        """Check if node can accept more tasks."""
        if self.state not in (EdgeNodeState.READY, EdgeNodeState.BUSY):
            return False
        
        if len(self._active_tasks) >= self.config.max_concurrent_tasks:
            return False
        
        if self._resources.cpu_percent > self.config.max_cpu_percent:
            return False
        
        if self._resources.memory_percent > self.config.max_memory_percent:
            return False
        
        return True
    
    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat for health monitoring."""
        while self._running:
            try:
                self._last_heartbeat = datetime.utcnow()
                
                # Update state based on resources
                if not self.can_accept_task():
                    if self.state == EdgeNodeState.READY:
                        self.state = EdgeNodeState.BUSY
                else:
                    if self.state == EdgeNodeState.BUSY:
                        self.state = EdgeNodeState.READY
                
                await asyncio.sleep(self.config.heartbeat_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _task_processor_loop(self) -> None:
        """Process tasks from the queue."""
        while self._running:
            try:
                # Check if we can process more tasks
                if not self.can_accept_task():
                    await asyncio.sleep(0.1)
                    continue
                
                # Get next task
                if not self._task_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                task = self._task_queue.pop(0)
                
                # Process task
                asyncio.create_task(self._process_task(task))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_task(self, task: EdgeTask) -> None:
        """Process a single task."""
        task.started_at = datetime.utcnow()
        self._active_tasks[task.task_id] = task
        
        try:
            # Get handler
            handler = self._task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    handler(task.payload),
                    timeout=task.timeout_seconds
                )
                task.result = result
                task.completed_at = datetime.utcnow()
                
                self._stats["tasks_processed"] += 1
                self._stats["total_processing_time"] += task.duration_seconds or 0
                
                logger.debug(f"Task {task.task_id} completed in {task.duration_seconds:.2f}s")
                
            except asyncio.TimeoutError:
                raise RuntimeError(f"Task timed out after {task.timeout_seconds}s")
            
        except Exception as e:
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            task.retry_count += 1
            
            self._stats["tasks_failed"] += 1
            
            # Retry if possible
            if task.retry_count < task.max_retries:
                task.error = None
                task.completed_at = None
                task.started_at = None
                self._task_queue.append(task)
                self._sort_queue()
                logger.info(f"Task {task.task_id} queued for retry {task.retry_count}/{task.max_retries}")
            else:
                logger.error(f"Task {task.task_id} failed: {e}")
        
        finally:
            # Move to completed
            if task.completed_at:
                del self._active_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task
                
                # Cleanup old completed tasks
                if len(self._completed_tasks) > 1000:
                    # Remove oldest
                    sorted_tasks = sorted(
                        self._completed_tasks.items(),
                        key=lambda x: x[1].completed_at or datetime.min
                    )
                    for tid, _ in sorted_tasks[:100]:
                        del self._completed_tasks[tid]
    
    async def _resource_monitor_loop(self) -> None:
        """Monitor system resources."""
        while self._running:
            try:
                self._update_resources()
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitor error: {e}")
    
    def _update_resources(self) -> None:
        """Update resource metrics."""
        try:
            import psutil
            
            self._resources.cpu_percent = psutil.cpu_percent(interval=0.1)
            self._resources.memory_percent = psutil.virtual_memory().percent
            self._resources.disk_percent = psutil.disk_usage('/').percent
            
            # Network (simplified)
            net = psutil.net_io_counters()
            self._resources.network_in_mbps = net.bytes_recv / 1024 / 1024
            self._resources.network_out_mbps = net.bytes_sent / 1024 / 1024
            
        except ImportError:
            # psutil not available, use defaults
            pass
        
        self._resources.active_tasks = len(self._active_tasks)
        self._resources.queued_tasks = len(self._task_queue)
        self._resources.available_slots = max(
            0, 
            self.config.max_concurrent_tasks - len(self._active_tasks)
        )


class EdgeNodeManager:
    """
    Manager for multiple edge nodes.
    
    Features:
    - Node discovery and registration
    - Health monitoring
    - Load balancing
    - Failover handling
    """
    
    def __init__(self):
        self._nodes: Dict[str, EdgeNode] = {}
        self._node_health: Dict[str, datetime] = {}
        self._running = False
    
    def register_node(
        self,
        node: Optional[EdgeNode] = None,
        *,
        endpoint: Optional[str] = None,
        name: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        max_concurrent_tasks: int = 10,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EdgeNode:
        """Register an edge node (object or API-style kwargs)."""
        if node is None:
            if not endpoint or "://" not in endpoint:
                raise ValueError("Invalid endpoint")
            host_port = endpoint.split("://", 1)[1]
            host = host_port.split(":", 1)[0]
            port = int(host_port.split(":", 1)[1]) if ":" in host_port else 80
            node = EdgeNode(
                EdgeNodeConfig(
                    name=name or "",
                    advertise_host=host,
                    listen_port=port,
                    max_concurrent_tasks=max_concurrent_tasks,
                    capabilities=set(capabilities or []),
                )
            )
            if metadata and isinstance(metadata, dict):
                node.config.tags.update({str(k): str(v) for k, v in metadata.items()})

        self._nodes[node.config.node_id] = node
        self._node_health[node.config.node_id] = datetime.utcnow()
        logger.info(f"Registered edge node: {node.config.node_id}")
        return node
    
    def unregister_node(self, node_id: str) -> None:
        """Unregister an edge node."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            del self._node_health[node_id]
            logger.info(f"Unregistered edge node: {node_id}")

    def deregister_node(self, node_id: str) -> bool:
        """API compatibility alias for unregister."""
        if node_id not in self._nodes:
            return False
        self.unregister_node(node_id)
        return True
    
    def get_node(self, node_id: str) -> Optional[EdgeNode]:
        """Get a specific node."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[EdgeNode]:
        """Get all registered nodes."""
        return list(self._nodes.values())

    def list_nodes(
        self,
        status_filter: Optional[str] = None,
        capability_filter: Optional[str] = None,
    ) -> List[EdgeNode]:
        """List nodes with optional status/capability filters."""
        nodes = self.get_all_nodes()
        if status_filter:
            sf = status_filter.lower()
            nodes = [
                node
                for node in nodes
                if getattr(node.status, "value", str(node.status)).lower() == sf
            ]
        if capability_filter:
            nodes = [node for node in nodes if capability_filter in node.config.capabilities]
        return nodes
    
    def get_nodes_by_capability(self, capability: str) -> List[EdgeNode]:
        """Get nodes with a specific capability."""
        return [
            node for node in self._nodes.values()
            if capability in node.config.capabilities
        ]
    
    def get_nodes_by_region(self, region: str) -> List[EdgeNode]:
        """Get nodes in a specific region."""
        return [
            node for node in self._nodes.values()
            if node.config.region == region
        ]
    
    def get_healthy_nodes(self) -> List[EdgeNode]:
        """Get all healthy nodes."""
        return [
            node for node in self._nodes.values()
            if node.state in (EdgeNodeState.READY, EdgeNodeState.BUSY)
        ]
    
    def get_best_node(
        self,
        required_capabilities: Optional[Set[str]] = None,
        preferred_region: Optional[str] = None,
    ) -> Optional[EdgeNode]:
        """Get the best node for a task."""
        candidates = self.get_healthy_nodes()
        
        # Filter by capabilities
        if required_capabilities:
            candidates = [
                node for node in candidates
                if required_capabilities.issubset(node.config.capabilities)
            ]
        
        # Filter by region
        if preferred_region:
            region_candidates = [
                node for node in candidates
                if node.config.region == preferred_region
            ]
            if region_candidates:
                candidates = region_candidates
        
        if not candidates:
            return None
        
        # Sort by load (prefer nodes with more available slots)
        candidates.sort(
            key=lambda n: n._resources.available_slots,
            reverse=True
        )
        
        return candidates[0]
    
    async def start_all(self) -> None:
        """Start all registered nodes."""
        for node in self._nodes.values():
            await node.start()
        self._running = True
    
    async def stop_all(self) -> None:
        """Stop all registered nodes."""
        for node in self._nodes.values():
            await node.stop()
        self._running = False
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster-wide statistics."""
        total_nodes = len(self._nodes)
        healthy_nodes = len(self.get_healthy_nodes())
        
        total_active_tasks = sum(
            len(node._active_tasks) for node in self._nodes.values()
        )
        total_queued_tasks = sum(
            len(node._task_queue) for node in self._nodes.values()
        )
        
        regions = set(node.config.region for node in self._nodes.values())
        capabilities = set()
        for node in self._nodes.values():
            capabilities.update(node.config.capabilities)
        
        return {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy_nodes,
            "unhealthy_nodes": total_nodes - healthy_nodes,
            "total_active_tasks": total_active_tasks,
            "total_queued_tasks": total_queued_tasks,
            "regions": list(regions),
            "capabilities": list(capabilities),
        }

    def drain_node(self, node_id: str) -> int:
        """Switch node to maintenance mode and return pending task count."""
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        node.state = EdgeNodeState.MAINTENANCE
        return len(node._task_queue) + len(node._active_tasks)

    def get_node_resources(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Return node resource dictionary for API compatibility."""
        node = self._nodes.get(node_id)
        if not node:
            return None
        resources = node.get_resources().to_dict()
        resources["network_mbps"] = resources.get("network_in_mbps", 0.0)
        return resources
