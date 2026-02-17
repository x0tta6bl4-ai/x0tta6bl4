"""
Route Table for Mesh Routing.

Manages routing entries with support for:
- Multi-path routing (k-disjoint paths)
- Route caching and expiration
- Route lookup and selection
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RouteEntry:
    """A single route entry in the routing table."""
    
    destination: str
    next_hop: str
    hop_count: int
    seq_num: int
    path: List[str] = field(default_factory=list[str])
    timestamp: float = field(default_factory=time.time)
    valid: bool = True
    metric: float = 1.0  # Route quality metric (lower is better)
    
    @property
    def age(self) -> float:
        """Time since route was created/updated."""
        return time.time() - self.timestamp
    
    def __hash__(self):
        return hash((self.destination, self.next_hop, tuple(self.path)))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteEntry):
            return False
        return (self.destination == other.destination and 
                self.next_hop == other.next_hop and
                self.path == other.path)


class RouteTable:
    """
    Routing table with multi-path support.
    
    Responsibilities:
    - Store and manage route entries
    - Support multiple routes per destination
    - Route selection based on metrics
    - Route expiration and cleanup
    """
    
    ROUTE_TIMEOUT = 60.0  # Seconds before route expires
    
    def __init__(self):
        # destination -> List[RouteEntry] (multiple paths supported)
        self._routes: Dict[str, List[RouteEntry]] = {}
        
    def add_route(self, entry: RouteEntry) -> bool:
        """
        Add or update a route entry.
        
        Returns True if route was added/updated.
        """
        dest = entry.destination
        
        if dest not in self._routes:
            self._routes[dest] = [entry]
            logger.debug(f"Added new route to {dest} via {entry.next_hop}")
            return True
        
        existing = self._routes[dest]
        
        # Check if this is an update to existing route (same next_hop)
        for i, route in enumerate(existing):
            if route.next_hop == entry.next_hop:
                # Update if newer sequence number or better metric
                if entry.seq_num > route.seq_num:
                    existing[i] = entry
                    logger.debug(f"Updated route to {dest} via {entry.next_hop}")
                    return True
                elif entry.seq_num == route.seq_num and entry.hop_count < route.hop_count:
                    existing[i] = entry
                    logger.debug(f"Updated route to {dest} (better hop count)")
                    return True
                return False
        
        # New route to existing destination
        existing.append(entry)
        logger.debug(f"Added alternate route to {dest} via {entry.next_hop}")
        return True
    
    def remove_route(self, destination: str, next_hop: Optional[str] = None) -> int:
        """
        Remove routes to destination.
        
        If next_hop is specified, only remove routes through that hop.
        Returns number of routes removed.
        """
        if destination not in self._routes:
            return 0
        
        if next_hop is None:
            count = len(self._routes[destination])
            del self._routes[destination]
            return count
        
        original = len(self._routes[destination])
        self._routes[destination] = [
            r for r in self._routes[destination] if r.next_hop != next_hop
        ]
        
        if not self._routes[destination]:
            del self._routes[destination]
        
        return original - len(self._routes.get(destination, []))
    
    def invalidate_route(self, destination: str, next_hop: Optional[str] = None):
        """Mark routes as invalid without removing them."""
        if destination not in self._routes:
            return
        
        for route in self._routes[destination]:
            if next_hop is None or route.next_hop == next_hop:
                route.valid = False
    
    def invalidate_route_by_hop(self, next_hop: str):
        """Invalidate all routes through a specific next hop."""
        for dest in self._routes:
            for route in self._routes[dest]:
                if route.next_hop == next_hop:
                    route.valid = False
    
    def get_routes(self, destination: str, valid_only: bool = True) -> List[RouteEntry]:
        """
        Get all routes to a destination.
        
        Routes are sorted by quality (hop_count, then metric).
        """
        if destination not in self._routes:
            return []
        
        routes = self._routes[destination]
        
        if valid_only:
            routes = [r for r in routes if r.valid and r.age < self.ROUTE_TIMEOUT]
        
        # Sort by hop_count (primary) and metric (secondary)
        return sorted(routes, key=lambda r: (r.hop_count, r.metric))
    
    def get_best_route(self, destination: str) -> Optional[RouteEntry]:
        """Get the best route to a destination."""
        routes = self.get_routes(destination)
        return routes[0] if routes else None
    
    def get_all_routes(self) -> Dict[str, List[RouteEntry]]:
        """Get all routes in the table."""
        return {
            dest: self.get_routes(dest)
            for dest in self._routes
            if self.get_routes(dest)
        }
    
    def get_next_hops(self, destination: str) -> List[str]:
        """Get all unique next hops for a destination."""
        routes = self.get_routes(destination)
        return list(dict.fromkeys(r.next_hop for r in routes))
    
    def has_route(self, destination: str) -> bool:
        """Check if a valid route exists."""
        return bool(self.get_routes(destination))
    
    def cleanup_expired(self) -> int:
        """Remove expired routes."""
        expired_count = 0
        
        for dest in list(self._routes.keys()):
            before = len(self._routes[dest])
            self._routes[dest] = [
                r for r in self._routes[dest]
                if r.valid and r.age < self.ROUTE_TIMEOUT
            ]
            
            if not self._routes[dest]:
                del self._routes[dest]
            
            expired_count += before - len(self._routes.get(dest, []))
        
        if expired_count:
            logger.debug(f"Cleaned up {expired_count} expired routes")
        
        return expired_count
    
    def get_stats(self) -> Dict[str, float | int]:
        """Get routing table statistics."""
        total_routes = sum(len(routes) for routes in self._routes.values())
        destinations = len(self._routes)
        
        avg_hop = 0.0
        if total_routes > 0:
            total_hops = sum(r.hop_count for routes in self._routes.values() for r in routes)
            avg_hop = total_hops / total_routes
        
        return {
            "destinations": destinations,
            "total_routes": total_routes,
            "average_hop_count": avg_hop,
        }
    
    def find_disjoint_paths(self, destination: str, k: int = 3) -> List[RouteEntry]:
        """
        Find k node-disjoint paths to destination.
        
        Node-disjoint means paths don't share intermediate nodes.
        """
        routes = self.get_routes(destination)
        if not routes:
            return []
        
        disjoint: List[RouteEntry] = []
        used_nodes: set[str] = set()
        
        for route in routes:
            # Check if path shares nodes with already selected paths
            path_nodes = set(route.path) - {destination}
            
            if not path_nodes.intersection(used_nodes):
                disjoint.append(route)
                used_nodes.update(path_nodes)
                
                if len(disjoint) >= k:
                    break
        
        return disjoint
