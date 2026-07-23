"""
Routing Table management for Mesh Router.

Handles route storage, retrieval, validation, and multi-path support.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .models import RouteEntry

logger = logging.getLogger(__name__)


class RoutingTable:
    """
    Manages the routing table for mesh routing.
    
    Supports multiple paths to each destination (k-disjoint routes)
    with automatic expiration and validation.
    
    Example:
        >>> table = RoutingTable(route_timeout=60.0)
        >>> table.add_neighbor("node_a")
        >>> routes = table.get_routes("node_b")
    """

    def __init__(self, node_id: str, route_timeout: float = 60.0):
        """
        Initialize routing table.
        
        Args:
            node_id: ID of the local node
            route_timeout: Time in seconds before routes expire
        """
        self._node_id = node_id
        self._route_timeout = route_timeout
        self._routes: Dict[str, List[RouteEntry]] = {}

    def add_neighbor(self, neighbor_id: str) -> None:
        """
        Add a direct neighbor (1 hop).
        
        Args:
            neighbor_id: ID of the neighbor node
        """
        new_entry = RouteEntry(
            destination=neighbor_id,
            next_hop=neighbor_id,
            hop_count=1,
            seq_num=0,
            path=[self._node_id, neighbor_id],
        )

        if neighbor_id not in self._routes:
            self._routes[neighbor_id] = []

        # Check if a direct route already exists and update it
        for i, entry in enumerate(self._routes[neighbor_id]):
            if entry.next_hop == neighbor_id and entry.hop_count == 1:
                self._routes[neighbor_id][i] = new_entry
                logger.debug(f"Updated neighbor route: {neighbor_id}")
                return

        self._routes[neighbor_id].append(new_entry)
        logger.debug(f"Added neighbor route: {neighbor_id}")

    def remove_neighbor(self, neighbor_id: str) -> List[str]:
        """
        Remove a neighbor and all routes using it.
        
        Args:
            neighbor_id: ID of the neighbor to remove
            
        Returns:
            List of destinations that lost all routes
        """
        affected_destinations = []

        # Remove direct routes to the neighbor
        if neighbor_id in self._routes:
            del self._routes[neighbor_id]
            logger.debug(f"Removed direct routes to neighbor: {neighbor_id}")

        # Invalidate routes that use this neighbor as next_hop
        for dest in list(self._routes.keys()):
            if dest == neighbor_id:
                continue

            initial_count = len(self._routes[dest])
            self._routes[dest] = [
                route for route in self._routes[dest]
                if route.next_hop != neighbor_id
            ]

            if len(self._routes[dest]) < initial_count:
                logger.debug(
                    f"Invalidated routes to {dest} through {neighbor_id}"
                )

            if not self._routes[dest]:
                del self._routes[dest]
                affected_destinations.append(dest)
                logger.debug(f"No routes left for {dest}")

        return affected_destinations

    def get_route(self, destination: str) -> List[RouteEntry]:
        """
        Get all active routes to destination, sorted by quality.
        
        Args:
            destination: Target node ID
            
        Returns:
            List of valid routes sorted by hop count (best first)
        """
        routes_for_dest = self._routes.get(destination, [])

        valid_routes = [
            route for route in routes_for_dest
            if route.valid and route.is_fresh(self._route_timeout)
        ]

        # Sort by hop count (primary), then by seq_num (secondary)
        valid_routes.sort(key=lambda route: (route.hop_count, -route.seq_num))
        return valid_routes

    def get_routes(self) -> Dict[str, List[RouteEntry]]:
        """
        Get all active routes.
        
        Returns:
            Dictionary of destination -> list of valid routes
        """
        active_routes: Dict[str, List[RouteEntry]] = {}
        for dest, routes_list in self._routes.items():
            valid_routes = [
                route for route in routes_list
                if route.valid and route.is_fresh(self._route_timeout)
            ]
            if valid_routes:
                active_routes[dest] = valid_routes
        return active_routes

    def update_route(
        self,
        destination: str,
        next_hop: str,
        hop_count: int,
        seq_num: int,
        path: Optional[List[str]] = None,
    ) -> None:
        """
        Update or add a route.
        
        Args:
            destination: Target node ID
            next_hop: Next hop node ID
            hop_count: Number of hops to destination
            seq_num: Sequence number for freshness
            path: Full path to destination (optional)
        """
        if path is None:
            if next_hop == destination:
                path = [self._node_id, destination]
            else:
                path = [self._node_id, next_hop, destination]

        new_entry = RouteEntry(
            destination=destination,
            next_hop=next_hop,
            hop_count=hop_count,
            seq_num=seq_num,
            path=path,
        )

        if destination not in self._routes:
            self._routes[destination] = [new_entry]
            logger.debug(f"New route added for {destination}")
            return

        existing_routes = self._routes[destination]
        updated = False

        for i, entry in enumerate(existing_routes):
            if entry.next_hop == new_entry.next_hop:
                # Apply AODV-like update rules
                if new_entry.seq_num > entry.seq_num:
                    existing_routes[i] = new_entry
                    updated = True
                    logger.debug(f"Route updated (better seq_num) for {destination}")
                    break
                elif (
                    new_entry.seq_num == entry.seq_num
                    and new_entry.hop_count < entry.hop_count
                ):
                    existing_routes[i] = new_entry
                    updated = True
                    logger.debug(f"Route updated (better hop_count) for {destination}")
                    break

        if not updated:
            existing_routes.append(new_entry)
            logger.debug(f"New distinct route added for {destination}")

    def invalidate_route(self, destination: str, next_hop: str) -> bool:
        """
        Invalidate routes using a specific next hop.
        
        Args:
            destination: Target node ID
            next_hop: Failed next hop
            
        Returns:
            True if any routes were invalidated
        """
        if destination not in self._routes:
            return False

        initial_count = len(self._routes[destination])
        self._routes[destination] = [
            route for route in self._routes[destination]
            if route.next_hop != next_hop
        ]

        if not self._routes[destination]:
            del self._routes[destination]
            logger.debug(f"No routes left for {destination}")

        return len(self._routes.get(destination, [])) < initial_count

    def get_direct_neighbors(self) -> List[str]:
        """
        Get list of direct neighbors (1 hop).
        
        Returns:
            List of neighbor node IDs
        """
        neighbors = []
        for dest, routes in self._routes.items():
            if any(
                route.hop_count == 1
                and route.valid
                and route.is_fresh(self._route_timeout)
                for route in routes
            ):
                neighbors.append(dest)
        return neighbors

    def get_all_destinations(self) -> List[str]:
        """Get all known destinations."""
        return list(self._routes.keys())


__all__ = ["RoutingTable"]

