"""
Make-Make-Make-Never-Break Network Resilience Module.

Implements Rajant-inspired aggressive path establishment and maintenance
for zero-downtime mesh networking. Core principle: establish multiple
redundant paths proactively and never let connectivity break.

Key Features:
- Multi-path redundancy (4+ simultaneous paths like Rajant)
- Sub-second rerouting (<100ms target vs Rajant's <1ms)
- Proactive path establishment before failures
- Frequency/channel diversity for wireless mesh
- Trust-score aware routing decisions

Reference: Rajant Kinetic Mesh "Make-Make-Make-Never-Break" principle
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import random
import hashlib

logger = logging.getLogger(__name__)


class PathState(str, Enum):
    """State of a network path."""
    ACTIVE = "active"           # Currently carrying traffic
    STANDBY = "standby"         # Available, ready to use
    DEGRADED = "degraded"       # Partially functional
    FAILED = "failed"           # Not functional
    ESTABLISHING = "establishing"  # Being set up


class PathType(str, Enum):
    """Type of network path."""
    PRIMARY = "primary"         # Best current path
    BACKUP = "backup"           # Secondary path
    EMERGENCY = "emergency"     # Last resort path
    SCOUT = "scout"             # Exploratory path


@dataclass
class PathMetrics:
    """Metrics for a network path."""
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    bandwidth_mbps: float = 0.0
    rtt_ms: float = 0.0
    
    # Trust/reliability
    trust_score: float = 1.0
    uptime_ratio: float = 1.0
    failure_count: int = 0
    
    # Timestamps
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_probe: Optional[datetime] = None
    
    def quality_score(self) -> float:
        """Calculate overall path quality score (0-1)."""
        # Weighted combination of metrics
        latency_score = max(0, 1 - (self.latency_ms / 500))  # 500ms = 0 score
        jitter_score = max(0, 1 - (self.jitter_ms / 100))    # 100ms jitter = 0
        loss_score = 1 - self.packet_loss
        trust_component = self.trust_score * self.uptime_ratio
        
        return (
            0.3 * latency_score +
            0.2 * jitter_score +
            0.2 * loss_score +
            0.3 * trust_component
        )


@dataclass
class NetworkPath:
    """A network path between two nodes."""
    path_id: str
    source_node: str
    target_node: str
    path_type: PathType
    state: PathState = PathState.ESTABLISHING
    
    # Route information
    hops: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)  # Frequency channels
    
    # Metrics
    metrics: PathMetrics = field(default_factory=PathMetrics)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_usable(self) -> bool:
        """Check if path can carry traffic."""
        return self.state in (PathState.ACTIVE, PathState.STANDBY, PathState.DEGRADED)
    
    def age_seconds(self) -> float:
        """Get path age in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()


@dataclass
class ResilienceConfig:
    """Configuration for resilience module."""
    # Path management
    min_active_paths: int = 4           # Minimum simultaneous paths (Rajant: 4+)
    max_paths: int = 16                  # Maximum paths to maintain
    path_timeout_seconds: float = 30.0   # Path timeout before removal
    
    # Probing
    probe_interval_seconds: float = 1.0  # How often to probe paths
    probe_timeout_ms: float = 500.0      # Probe timeout
    
    # Rerouting
    reroute_threshold: float = 0.5       # Quality threshold to trigger reroute
    reroute_delay_ms: float = 50.0       # Target reroute delay
    
    # Trust scoring
    trust_decay_rate: float = 0.1        # How fast trust decays
    trust_recovery_rate: float = 0.05    # How fast trust recovers
    min_trust_score: float = 0.1         # Minimum trust to use path
    
    # Aggressive establishment
    scout_paths: int = 2                 # Exploratory paths to maintain
    preemptive_paths: int = 2            # Pre-emptive backup paths


class MakeNeverBreakEngine:
    """
    Implements the Make-Make-Make-Never-Break principle.
    
    Core algorithm:
    1. AGGRESSIVELY establish multiple paths (make-make-make)
    2. NEVER let all paths fail simultaneously
    3. Proactively maintain standby paths
    4. Instant failover when degradation detected
    """
    
    def __init__(self, config: Optional[ResilienceConfig] = None):
        self.config = config or ResilienceConfig()
        
        # Path storage
        self._paths: Dict[str, NetworkPath] = {}
        self._paths_by_target: Dict[str, Set[str]] = {}  # target -> path_ids
        self._paths_by_source: Dict[str, Set[str]] = {}  # source -> path_ids
        
        # Current best paths
        self._primary_paths: Dict[str, str] = {}  # target -> best_path_id
        
        # Callbacks
        self._on_path_change: Optional[Callable[[NetworkPath], None]] = None
        self._on_reroute: Optional[Callable[[str, str, str], None]] = None
        
        # Background tasks
        self._probe_task: Optional[asyncio.Task] = None
        self._maintenance_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self._stats = {
            "paths_created": 0,
            "paths_failed": 0,
            "reroutes": 0,
            "probes_sent": 0,
            "avg_reroute_time_ms": 0.0,
        }
    
    def set_callbacks(
        self,
        on_path_change: Optional[Callable[[NetworkPath], None]] = None,
        on_reroute: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        """Set callbacks for path events."""
        self._on_path_change = on_path_change
        self._on_reroute = on_reroute
    
    async def start(self) -> None:
        """Start the resilience engine."""
        if self._running:
            return
        
        self._running = True
        self._probe_task = asyncio.create_task(self._probe_loop())
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        logger.info("Make-Never-Break engine started")
    
    async def stop(self) -> None:
        """Stop the resilience engine."""
        self._running = False
        
        if self._probe_task:
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Make-Never-Break engine stopped")
    
    # -------------------------------------------------------------------------
    # Path Management (Make-Make-Make)
    # -------------------------------------------------------------------------
    
    def create_path(
        self,
        source: str,
        target: str,
        hops: List[str],
        channels: Optional[List[str]] = None,
        path_type: PathType = PathType.PRIMARY,
    ) -> NetworkPath:
        """
        Create a new network path.
        
        This is the "make" in make-make-make - aggressively establish paths.
        """
        path_id = self._generate_path_id(source, target, hops)
        
        path = NetworkPath(
            path_id=path_id,
            source_node=source,
            target_node=target,
            path_type=path_type,
            hops=hops,
            channels=channels or [],
            state=PathState.ESTABLISHING,
        )
        
        self._paths[path_id] = path
        
        # Index by target and source
        if target not in self._paths_by_target:
            self._paths_by_target[target] = set()
        self._paths_by_target[target].add(path_id)
        
        if source not in self._paths_by_source:
            self._paths_by_source[source] = set()
        self._paths_by_source[source].add(path_id)
        
        self._stats["paths_created"] += 1
        
        logger.debug(f"Created path {path_id}: {source} -> {target} via {hops}")
        
        if self._on_path_change:
            self._on_path_change(path)
        
        return path
    
    def establish_redundant_paths(
        self,
        source: str,
        target: str,
        available_hops: List[List[str]],
        available_channels: Optional[List[str]] = None,
    ) -> List[NetworkPath]:
        """
        Aggressively establish multiple redundant paths.
        
        This implements the core "make-make-make" principle:
        - Establish min_active_paths immediately
        - Use diverse hops and channels
        - Don't wait for failures
        """
        paths = []
        channels = available_channels or ["default"]
        
        # Sort hop routes by diversity (prefer different intermediate nodes)
        diverse_routes = self._select_diverse_routes(
            available_hops,
            self.config.min_active_paths
        )
        
        for i, hops in enumerate(diverse_routes[:self.config.max_paths]):
            # Assign channel with diversity
            channel = channels[i % len(channels)]
            
            # Determine path type
            if i == 0:
                path_type = PathType.PRIMARY
            elif i < self.config.min_active_paths:
                path_type = PathType.BACKUP
            else:
                path_type = PathType.SCOUT
            
            path = self.create_path(
                source=source,
                target=target,
                hops=hops,
                channels=[channel],
                path_type=path_type,
            )
            paths.append(path)
        
        logger.info(
            f"Established {len(paths)} redundant paths: {source} -> {target}"
        )
        
        return paths
    
    def _select_diverse_routes(
        self,
        routes: List[List[str]],
        count: int,
    ) -> List[List[str]]:
        """Select routes with maximum node diversity."""
        if not routes:
            return []
        
        selected = [routes[0]]  # Start with first route
        used_nodes = set(routes[0])
        
        remaining = routes[1:]
        random.shuffle(remaining)  # Add randomness
        
        for route in remaining:
            if len(selected) >= count:
                break
            
            # Calculate overlap with already selected routes
            route_nodes = set(route)
            overlap = len(route_nodes & used_nodes)
            
            # Prefer routes with less overlap
            if overlap < len(route_nodes) * 0.5:  # Less than 50% overlap
                selected.append(route)
                used_nodes.update(route_nodes)
        
        # Fill remaining with any routes
        for route in remaining:
            if len(selected) >= count:
                break
            if route not in selected:
                selected.append(route)
        
        return selected
    
    # -------------------------------------------------------------------------
    # Path Maintenance (Never Break)
    # -------------------------------------------------------------------------
    
    def update_path_metrics(
        self,
        path_id: str,
        latency_ms: float,
        jitter_ms: float = 0.0,
        packet_loss: float = 0.0,
        bandwidth_mbps: float = 0.0,
    ) -> None:
        """Update metrics for a path."""
        path = self._paths.get(path_id)
        if not path:
            return
        
        path.metrics.latency_ms = latency_ms
        path.metrics.jitter_ms = jitter_ms
        path.metrics.packet_loss = packet_loss
        path.metrics.bandwidth_mbps = bandwidth_mbps
        path.metrics.last_probe = datetime.utcnow()
        path.updated_at = datetime.utcnow()
        
        # Update state based on metrics
        if path.metrics.quality_score() > 0.7:
            path.state = PathState.ACTIVE
        elif path.metrics.quality_score() > 0.3:
            path.state = PathState.DEGRADED
        else:
            path.state = PathState.FAILED
            self._handle_path_failure(path)
    
    def update_trust_score(
        self,
        path_id: str,
        trust_delta: float,
    ) -> None:
        """Update trust score for a path (Cisco-like trust evaluation)."""
        path = self._paths.get(path_id)
        if not path:
            return
        
        # Apply trust update with bounds
        path.metrics.trust_score = max(
            self.config.min_trust_score,
            min(1.0, path.metrics.trust_score + trust_delta)
        )
        path.updated_at = datetime.utcnow()
    
    def _handle_path_failure(self, path: NetworkPath) -> None:
        """Handle a path failure - this is where 'never break' kicks in."""
        path.state = PathState.FAILED
        path.metrics.failure_count += 1
        path.metrics.last_failure = datetime.utcnow()
        
        # Decay trust score
        path.metrics.trust_score *= (1 - self.config.trust_decay_rate)
        
        self._stats["paths_failed"] += 1
        
        logger.warning(f"Path {path.path_id} failed, initiating reroute")
        
        # Trigger immediate reroute if this was a primary path
        if path.path_type == PathType.PRIMARY:
            self._reroute_primary(path.target_node)
    
    def _reroute_primary(self, target: str) -> Optional[str]:
        """
        Reroute to a new primary path.
        
        This is the core of 'never break' - instant failover.
        """
        start_time = time.time()
        
        # Find best available path to target
        available_paths = [
            p for p in self._paths.values()
            if p.target_node == target and p.is_usable()
        ]
        
        if not available_paths:
            logger.error(f"No available paths to {target} - connectivity broken!")
            return None
        
        # Sort by quality score
        available_paths.sort(key=lambda p: p.metrics.quality_score(), reverse=True)
        
        new_primary = available_paths[0]
        old_path_id = self._primary_paths.get(target)
        
        # Update path types
        if old_path_id:
            old_path = self._paths.get(old_path_id)
            if old_path:
                old_path.path_type = PathType.BACKUP
        
        new_primary.path_type = PathType.PRIMARY
        new_primary.state = PathState.ACTIVE
        self._primary_paths[target] = new_primary.path_id
        
        # Calculate reroute time
        reroute_time_ms = (time.time() - start_time) * 1000
        self._stats["reroutes"] += 1
        self._stats["avg_reroute_time_ms"] = (
            (self._stats["avg_reroute_time_ms"] * (self._stats["reroutes"] - 1) + reroute_time_ms)
            / self._stats["reroutes"]
        )
        
        logger.info(
            f"Rerouted to {new_primary.path_id} in {reroute_time_ms:.2f}ms "
            f"(avg: {self._stats['avg_reroute_time_ms']:.2f}ms)"
        )
        
        if self._on_reroute:
            self._on_reroute(target, old_path_id or "none", new_primary.path_id)
        
        return new_primary.path_id
    
    # -------------------------------------------------------------------------
    # Background Tasks
    # -------------------------------------------------------------------------
    
    async def _probe_loop(self) -> None:
        """Periodically probe all paths to maintain fresh metrics."""
        while self._running:
            try:
                for path in list(self._paths.values()):
                    if path.state != PathState.FAILED:
                        # Simulate probe (in real implementation, send actual probe)
                        await self._probe_path(path)
                
                await asyncio.sleep(self.config.probe_interval_seconds)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Probe loop error: {e}")
                await asyncio.sleep(1)
    
    async def _probe_path(self, path: NetworkPath) -> None:
        """Probe a single path for metrics."""
        self._stats["probes_sent"] += 1
        
        # In real implementation, this would send actual network probes
        # For now, we simulate based on existing metrics with some noise
        
        # Simulate latency measurement
        base_latency = path.metrics.latency_ms or 50.0
        measured_latency = base_latency + random.gauss(0, 5)
        
        self.update_path_metrics(
            path.path_id,
            latency_ms=max(0, measured_latency),
            jitter_ms=path.metrics.jitter_ms,
            packet_loss=path.metrics.packet_loss,
        )
    
    async def _maintenance_loop(self) -> None:
        """Maintain path health and create new paths as needed."""
        while self._running:
            try:
                # Remove stale paths
                await self._cleanup_stale_paths()
                
                # Ensure minimum path count
                await self._ensure_path_redundancy()
                
                # Recover trust scores for healthy paths
                self._recover_trust_scores()
                
                await asyncio.sleep(5)  # Maintenance interval
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_stale_paths(self) -> None:
        """Remove paths that have been failed for too long."""
        now = datetime.utcnow()
        to_remove = []
        
        for path_id, path in self._paths.items():
            if path.state == PathState.FAILED:
                age = (now - path.updated_at).total_seconds()
                if age > self.config.path_timeout_seconds:
                    to_remove.append(path_id)
        
        for path_id in to_remove:
            self._remove_path(path_id)
        
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} stale paths")
    
    async def _ensure_path_redundancy(self) -> None:
        """Ensure minimum path redundancy for all targets."""
        for target, path_ids in self._paths_by_target.items():
            active_count = sum(
                1 for pid in path_ids
                if self._paths.get(pid, NetworkPath("", "", "", PathType.PRIMARY)).is_usable()
            )
            
            if active_count < self.config.min_active_paths:
                logger.warning(
                    f"Target {target} has only {active_count} active paths, "
                    f"need {self.config.min_active_paths}"
                )
                # In real implementation, trigger path discovery
    
    def _recover_trust_scores(self) -> None:
        """Gradually recover trust scores for healthy paths."""
        for path in self._paths.values():
            if path.state == PathState.ACTIVE:
                path.metrics.trust_score = min(
                    1.0,
                    path.metrics.trust_score + self.config.trust_recovery_rate
                )
    
    def _remove_path(self, path_id: str) -> None:
        """Remove a path from tracking."""
        path = self._paths.pop(path_id, None)
        if not path:
            return
        
        # Remove from indexes
        if path.target_node in self._paths_by_target:
            self._paths_by_target[path.target_node].discard(path_id)
        if path.source_node in self._paths_by_source:
            self._paths_by_source[path.source_node].discard(path_id)
        
        # Clear primary if needed
        if self._primary_paths.get(path.target_node) == path_id:
            del self._primary_paths[path.target_node]
    
    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------
    
    def get_best_path(self, target: str) -> Optional[NetworkPath]:
        """Get the best available path to a target."""
        path_id = self._primary_paths.get(target)
        if path_id:
            return self._paths.get(path_id)
        
        # Find best available
        paths = self.get_paths_to_target(target)
        if not paths:
            return None
        
        paths.sort(key=lambda p: p.metrics.quality_score(), reverse=True)
        return paths[0]
    
    def get_paths_to_target(self, target: str) -> List[NetworkPath]:
        """Get all paths to a target."""
        path_ids = self._paths_by_target.get(target, set())
        return [self._paths[pid] for pid in path_ids if pid in self._paths]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get resilience statistics."""
        return {
            **self._stats,
            "total_paths": len(self._paths),
            "active_paths": sum(1 for p in self._paths.values() if p.state == PathState.ACTIVE),
            "failed_paths": sum(1 for p in self._paths.values() if p.state == PathState.FAILED),
            "targets": len(self._paths_by_target),
        }
    
    def _generate_path_id(self, source: str, target: str, hops: List[str]) -> str:
        """Generate a unique path ID."""
        content = f"{source}:{':'.join(hops)}:{target}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


# Export
__all__ = [
    "PathState",
    "PathType",
    "PathMetrics",
    "NetworkPath",
    "ResilienceConfig",
    "MakeNeverBreakEngine",
]
