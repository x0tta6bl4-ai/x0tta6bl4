"""
Route Recovery for Mesh Routing.

Handles route failure detection and recovery:
- Link failure detection
- Local route repair
- Alternative path selection
- Route error propagation
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .route_table import RouteEntry, RouteTable
from .topology import TopologyManager

logger = logging.getLogger(__name__)


@dataclass
class RecoveryAttempt:
    """Tracks a route recovery attempt."""
    
    destination: str
    start_time: float
    attempt_count: int = 0
    max_attempts: int = 3
    last_attempt: float = 0.0
    success: bool = False
    
    @property
    def elapsed(self) -> float:
        """Time since recovery started."""
        return time.time() - self.start_time


class RouteRecovery:
    """
    Handles route failure detection and recovery.
    
    Responsibilities:
    - Detect link failures
    - Attempt local route repair
    - Select alternative paths
    - Propagate route errors
    """
    
    RECOVERY_TIMEOUT = 5.0  # Seconds to wait for recovery
    MAX_REPAIR_ATTEMPTS = 3
    HELLO_INTERVAL = 1.0  # Seconds between hello packets
    MISSED_HELLOS_THRESHOLD = 3  # Number of missed hellos before link failure
    
    def __init__(
        self,
        topology: TopologyManager,
        route_table: RouteTable,
        local_node_id: str
    ):
        self.topology = topology
        self.route_table = route_table
        self.local_node_id = local_node_id
        
        # Track recovery attempts
        self._recovery_attempts: Dict[str, RecoveryAttempt] = {}
        
        # Track neighbor hello status
        self._neighbor_hellos: Dict[str, Tuple[int, float]] = {}  # node_id -> (missed_count, last_hello)
        
        # Callbacks
        self._on_route_discovery: Optional[Callable] = None
        self._on_route_error: Optional[Callable] = None
        self._on_recovery_success: Optional[Callable] = None
        self._on_recovery_failure: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_route_discovery: Optional[Callable] = None,
        on_route_error: Optional[Callable] = None,
        on_recovery_success: Optional[Callable] = None,
        on_recovery_failure: Optional[Callable] = None
    ):
        """Set callback functions for recovery events."""
        if on_route_discovery:
            self._on_route_discovery = on_route_discovery
        if on_route_error:
            self._on_route_error = on_route_error
        if on_recovery_success:
            self._on_recovery_success = on_recovery_success
        if on_recovery_failure:
            self._on_recovery_failure = on_recovery_failure
    
    def handle_hello(self, neighbor_id: str):
        """Process a hello packet from a neighbor."""
        # Reset missed count
        self._neighbor_hellos[neighbor_id] = (0, time.time())
        
        # Update topology
        node = self.topology.get_node(neighbor_id)
        if node:
            node.last_seen = time.time()
            node.is_active = True
    
    def check_neighbor_status(self) -> List[str]:
        """
        Check for failed neighbors based on missed hellos.
        
        Returns list of failed neighbor IDs.
        """
        now = time.time()
        failed: List[str] = []
        
        for neighbor_id, (missed, last_hello) in list(self._neighbor_hellos.items()):
            # Check if we should increment missed count
            if now - last_hello > self.HELLO_INTERVAL:
                missed += 1
                self._neighbor_hellos[neighbor_id] = (missed, last_hello)
            
            # Check if neighbor is failed
            if missed >= self.MISSED_HELLOS_THRESHOLD:
                failed.append(neighbor_id)
                del self._neighbor_hellos[neighbor_id]
        
        return failed
    
    def handle_link_failure(self, failed_node: str) -> List[str]:
        """
        Handle a detected link failure.
        
        Returns list of affected destinations.
        """
        logger.warning(f"Link failure detected: {failed_node}")
        
        # Mark node as inactive in topology
        node = self.topology.get_node(failed_node)
        if node:
            node.is_active = False
        
        # Find all routes using this node as next hop
        affected_destinations: List[str] = []
        
        for dest, routes in self.route_table.get_all_routes().items():
            for route in routes:
                if route.next_hop == failed_node:
                    affected_destinations.append(dest)
                    break
        
        # Invalidate routes through failed node
        self.route_table.invalidate_route_by_hop(failed_node)
        
        # Start recovery for affected destinations
        for dest in affected_destinations:
            self._start_recovery(dest)
        
        # Propagate route error
        if self._on_route_error:
            self._on_route_error(failed_node)
        
        return affected_destinations
    
    def _start_recovery(self, destination: str):
        """Start recovery process for a destination."""
        if destination in self._recovery_attempts:
            return
        
        self._recovery_attempts[destination] = RecoveryAttempt(
            destination=destination,
            start_time=time.time(),
            attempt_count=0
        )
        
        logger.info(f"Started recovery for {destination}")
        
        # Try alternative path first
        if self._try_alternative_path(destination):
            return
        
        # Initiate route discovery
        self._initiate_discovery(destination)
    
    def _try_alternative_path(self, destination: str) -> bool:
        """Try to use an alternative path to destination."""
        # Get disjoint paths
        disjoint_paths = self.route_table.find_disjoint_paths(destination, k=3)
        
        # Filter out invalid paths
        valid_paths = [p for p in disjoint_paths if p.valid]
        
        if valid_paths:
            # Use best alternative path
            best = valid_paths[0]
            logger.info(f"Using alternative path to {destination} via {best.next_hop}")
            
            # Mark recovery as successful
            if destination in self._recovery_attempts:
                self._recovery_attempts[destination].success = True
                del self._recovery_attempts[destination]
            
            if self._on_recovery_success:
                self._on_recovery_success(destination, best)
            
            return True
        
        return False
    
    def _initiate_discovery(self, destination: str):
        """Initiate route discovery for destination."""
        attempt = self._recovery_attempts.get(destination)
        if not attempt:
            return
        
        if attempt.attempt_count >= self.MAX_REPAIR_ATTEMPTS:
            logger.warning(f"Recovery failed for {destination} after {attempt.attempt_count} attempts")
            
            if self._on_recovery_failure:
                self._on_recovery_failure(destination)
            
            del self._recovery_attempts[destination]
            return
        
        attempt.attempt_count += 1
        attempt.last_attempt = time.time()
        
        logger.debug(f"Initiating route discovery for {destination} (attempt {attempt.attempt_count})")
        
        if self._on_route_discovery:
            self._on_route_discovery(destination)
    
    def handle_route_discovered(self, destination: str, route: RouteEntry):
        """Handle successful route discovery."""
        if destination not in self._recovery_attempts:
            return
        
        # Add route to table
        self.route_table.add_route(route)
        
        # Mark recovery as successful
        self._recovery_attempts[destination].success = True
        del self._recovery_attempts[destination]
        
        logger.info(f"Recovery successful for {destination} via {route.next_hop}")
        
        if self._on_recovery_success:
            self._on_recovery_success(destination, route)
    
    def check_recovery_timeouts(self) -> List[str]:
        """
        Check for timed-out recovery attempts.
        
        Returns list of destinations that failed recovery.
        """
        failed: List[str] = []
        now = time.time()
        
        for dest, attempt in list(self._recovery_attempts.items()):
            if attempt.elapsed > self.RECOVERY_TIMEOUT:
                if attempt.attempt_count < self.MAX_REPAIR_ATTEMPTS:
                    # Retry discovery
                    self._initiate_discovery(dest)
                else:
                    # Give up
                    failed.append(dest)
                    del self._recovery_attempts[dest]
                    
                    logger.warning(f"Recovery timed out for {dest}")
                    
                    if self._on_recovery_failure:
                        self._on_recovery_failure(dest)
        
        return failed
    
    def get_active_recoveries(self) -> Dict[str, RecoveryAttempt]:
        """Get currently active recovery attempts."""
        return self._recovery_attempts.copy()
    
    def get_stats(self) -> Dict:
        """Get recovery statistics."""
        return {
            "active_recoveries": len(self._recovery_attempts),
            "tracked_neighbors": len(self._neighbor_hellos),
        }
    
    def cleanup(self):
        """Cleanup stale state."""
        # Remove old recovery attempts
        self._recovery_attempts = {
            dest: attempt for dest, attempt in self._recovery_attempts.items()
            if attempt.elapsed < self.RECOVERY_TIMEOUT * 2
        }
        
        # Remove stale neighbor tracking
        now = time.time()
        self._neighbor_hellos = {
            nid: (missed, last) for nid, (missed, last) in self._neighbor_hellos.items()
            if now - last < self.HELLO_INTERVAL * 10
        }