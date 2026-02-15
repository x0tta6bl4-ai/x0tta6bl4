"""
Batman-adv Mesh Topology Discovery & Management
Core module for x0tta6bl4 decentralized mesh networking
"""

import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from ...core.thread_safe_stats import MeshTopologyStats

logger = logging.getLogger(__name__)


class NodeState(Enum):
    """Node status in mesh network"""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    INITIALIZING = "initializing"


class LinkQuality(Enum):
    """Link quality metrics"""

    EXCELLENT = 5  # >95% delivery
    GOOD = 4  # 80-95% delivery
    FAIR = 3  # 60-80% delivery
    POOR = 2  # 40-60% delivery
    BAD = 1  # <40% delivery


@dataclass
class MeshNode:
    """Represents a node in the mesh network"""

    node_id: str
    mac_address: str
    ip_address: str
    state: NodeState = NodeState.INITIALIZING
    last_seen: datetime = field(default_factory=datetime.now)
    hop_count: int = 0
    spiffe_id: Optional[str] = None  # Zero Trust identity
    metrics: Dict = field(default_factory=dict)

    def is_alive(self, timeout: int = 300) -> bool:
        """Check if node is still alive (timeout in seconds)"""
        elapsed = (datetime.now() - self.last_seen).total_seconds()
        return elapsed < timeout


@dataclass
class MeshLink:
    """Represents a link between two nodes"""

    source: str  # node_id
    destination: str  # node_id
    quality: LinkQuality
    throughput_mbps: float  # Estimated throughput
    latency_ms: float  # Latency in milliseconds
    last_updated: datetime = field(default_factory=datetime.now)
    packet_loss_percent: float = 0.0

    def quality_score(self) -> float:
        """Calculate link quality score (0-100)"""
        base_score = self.quality.value * 20
        latency_penalty = min(10, self.latency_ms / 10)
        loss_penalty = self.packet_loss_percent
        return max(0, base_score - latency_penalty - loss_penalty)


class MeshTopology:
    """
    Batman-adv Mesh Topology Management

    Maintains:
    - Node registry with status tracking
    - Link quality metrics
    - Routing information
    - Topology changes
    """

    def __init__(self, mesh_id: str, local_node_id: str, k_disjoint: int = 3):
        self.mesh_id = mesh_id
        self.local_node_id = local_node_id
        self.k_disjoint = k_disjoint
        self.nodes: Dict[str, MeshNode] = {}
        self.links: Dict[Tuple[str, str], MeshLink] = {}
        self.routing_table: Dict[str, str] = {}  # destination -> next_hop
        # Cache for k-disjoint paths: destination -> List[paths]
        self.path_cache: Dict[str, List[List[str]]] = {}
        self.cache_timestamp: Dict[str, datetime] = {}
        self.cache_ttl: int = 300  # 5 minutes cache TTL

        # Thread-safe statistics
        self._stats = MeshTopologyStats(local_node_id)

    def add_node(self, node: MeshNode) -> bool:
        """Register a new node in the mesh"""
        if node.node_id in self.nodes:
            logger.warning(f"Node {node.node_id} already exists")
            return False

        self.nodes[node.node_id] = node
        logger.info(f"Added node {node.node_id} ({node.ip_address})")

        # Export topology change metric
        try:
            from src.monitoring.metrics import record_topology_change

            record_topology_change(self.local_node_id, "node_added")
        except ImportError:
            pass

        return True

    def add_link(self, link: MeshLink) -> bool:
        """Register a link between two nodes"""
        key = (link.source, link.destination)

        if key in self.links:
            # Update existing link
            self.links[key] = link
            logger.debug(f"Updated link {link.source} → {link.destination}")
        else:
            self.links[key] = link
            logger.info(
                f"Added link {link.source} → {link.destination} (quality: {link.quality.name})"
            )

        return True

    def get_neighbors(self, node_id: str) -> List[str]:
        """Get direct neighbors of a node"""
        neighbors = []
        for (src, dst), link in self.links.items():
            if src == node_id and link.quality.value >= LinkQuality.FAIR.value:
                neighbors.append(dst)
        return neighbors

    def compute_shortest_path(self, source: str, destination: str) -> List[str]:
        """
        Compute shortest path using Dijkstra's algorithm
        Considers link quality as edge weight
        """
        if source not in self.nodes or destination not in self.nodes:
            return []

        # Initialize distances
        distances = {node_id: float("inf") for node_id in self.nodes}
        distances[source] = 0
        previous = {node_id: None for node_id in self.nodes}
        unvisited = set(self.nodes.keys())

        while unvisited:
            # Find unvisited node with minimum distance
            current = min(unvisited, key=lambda n: distances[n])

            if distances[current] == float("inf"):
                break  # Unreachable nodes

            if current == destination:
                # Reconstruct path
                path = []
                node = destination
                while node is not None:
                    path.append(node)
                    node = previous[node]
                return list(reversed(path))

            # Check neighbors
            for neighbor in self.get_neighbors(current):
                if neighbor in unvisited:
                    link = self.links.get((current, neighbor))
                    if link:
                        # Edge weight is inverse of link quality (lower is better)
                        weight = 100 / (link.quality_score() + 1)
                        new_distance = distances[current] + weight

                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            previous[neighbor] = current

            unvisited.remove(current)

        return []  # No path found

    def compute_k_disjoint_paths(
        self, source: str, destination: str, k: int = 3
    ) -> List[List[str]]:
        """
        Compute k disjoint shortest paths using modified Dijkstra algorithm.

        Algorithm:
        1. Find shortest path using Dijkstra
        2. Remove used edges from graph
        3. Repeat k-1 times
        4. Rank paths by link quality score
        5. Cache pre-computed paths for fast failover

        Args:
            source: Source node ID
            destination: Destination node ID
            k: Number of disjoint paths to find (default: 3)

        Returns:
            List of k disjoint paths, each path is a list of node IDs
        """
        if source not in self.nodes or destination not in self.nodes:
            return []

        if source == destination:
            return [[source]]

        paths = []
        used_edges: Set[Tuple[str, str]] = set()

        for i in range(k):
            # Find shortest path avoiding used edges
            path = self._find_shortest_path_avoiding_edges(
                source, destination, used_edges
            )

            if not path:
                break  # No more paths available

            paths.append(path)

            # Mark edges as used (both directions for undirected graph)
            for j in range(len(path) - 1):
                used_edges.add((path[j], path[j + 1]))
                used_edges.add((path[j + 1], path[j]))  # Bidirectional

            logger.debug(f"Found disjoint path {i+1}/{k}: {path}")

        # Rank paths by quality score (best first)
        ranked_paths = self._rank_paths_by_quality(paths)

        logger.info(
            f"Computed {len(ranked_paths)} disjoint paths from {source} to {destination}"
        )
        return ranked_paths

    def _find_shortest_path_avoiding_edges(
        self, source: str, destination: str, used_edges: Set[Tuple[str, str]]
    ) -> List[str]:
        """
        Find shortest path avoiding specified edges.

        Args:
            source: Source node ID
            destination: Destination node ID
            used_edges: Set of edges to avoid (as (node1, node2) tuples)

        Returns:
            List of node IDs representing the path, or empty list if no path found
        """
        # Initialize distances
        distances = {node_id: float("inf") for node_id in self.nodes}
        distances[source] = 0
        previous = {node_id: None for node_id in self.nodes}
        unvisited = set(self.nodes.keys())

        while unvisited:
            # Find unvisited node with minimum distance
            current = min(unvisited, key=lambda n: distances[n])

            if distances[current] == float("inf"):
                break  # Unreachable nodes

            if current == destination:
                # Reconstruct path
                path = []
                node = destination
                while node is not None:
                    path.append(node)
                    node = previous[node]
                return list(reversed(path))

            # Check neighbors (avoiding used edges)
            for neighbor in self.get_neighbors(current):
                if neighbor in unvisited:
                    # Skip if edge is in used_edges
                    if (current, neighbor) in used_edges or (
                        neighbor,
                        current,
                    ) in used_edges:
                        continue

                    link = self.links.get((current, neighbor))
                    if link:
                        # Edge weight is inverse of link quality (lower is better)
                        weight = 100 / (link.quality_score() + 1)
                        new_distance = distances[current] + weight

                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            previous[neighbor] = current

            unvisited.remove(current)

        return []  # No path found

    def _rank_paths_by_quality(self, paths: List[List[str]]) -> List[List[str]]:
        """
        Rank paths by overall quality score.

        Quality score = average link quality score along the path.
        Higher score = better path.

        Args:
            paths: List of paths to rank

        Returns:
            List of paths sorted by quality (best first)
        """
        path_scores = []

        for path in paths:
            if len(path) < 2:
                path_scores.append((path, 0.0))
                continue

            # Calculate average link quality score
            total_score = 0.0
            link_count = 0

            for i in range(len(path) - 1):
                link = self.links.get((path[i], path[i + 1]))
                if link:
                    total_score += link.quality_score()
                    link_count += 1

            avg_score = total_score / link_count if link_count > 0 else 0.0
            path_scores.append((path, avg_score))

        # Sort by score (descending) and return paths only
        path_scores.sort(key=lambda x: x[1], reverse=True)
        return [path for path, _ in path_scores]

    def update_routing_table(self, use_k_disjoint: bool = True) -> int:
        """
        Rebuild routing table from local node.

        Args:
            use_k_disjoint: If True, use k-disjoint paths for failover routing

        Returns:
            Number of routing table entries updated
        """
        updated = 0

        for dest_id in self.nodes:
            if dest_id == self.local_node_id:
                continue

            if use_k_disjoint:
                # Use k-disjoint paths: primary path goes to routing table
                paths = self.get_cached_k_disjoint_paths(self.local_node_id, dest_id)
                if paths and len(paths) > 0:
                    primary_path = paths[0]  # Best quality path
                    if len(primary_path) > 1:
                        next_hop = primary_path[1]
                        if self.routing_table.get(dest_id) != next_hop:
                            self.routing_table[dest_id] = next_hop
                            updated += 1
            else:
                # Fallback to single shortest path
                path = self.compute_shortest_path(self.local_node_id, dest_id)
                if path and len(path) > 1:
                    next_hop = path[1]
                    if self.routing_table.get(dest_id) != next_hop:
                        self.routing_table[dest_id] = next_hop
                        updated += 1

        return updated

    def get_cached_k_disjoint_paths(
        self, source: str, destination: str
    ) -> List[List[str]]:
        """
        Get k-disjoint paths with caching for fast failover.

        Cache is invalidated after TTL or when topology changes.

        Args:
            source: Source node ID
            destination: Destination node ID

        Returns:
            List of k disjoint paths (best quality first)
        """
        cache_key = f"{source}->{destination}"

        # Check cache validity
        if cache_key in self.path_cache and cache_key in self.cache_timestamp:
            age = (datetime.now() - self.cache_timestamp[cache_key]).total_seconds()
            if age < self.cache_ttl:
                # Record cache hit
                self._stats.record_cache_hit()
                return self.path_cache[cache_key]

        # Cache miss - compute paths
        # Note: MeshTopologyStats doesn't have record_cache_miss, only record_cache_hit
        # We can track cache misses via path_computation instead
        self._stats.record_path_computation()
        paths = self.compute_k_disjoint_paths(source, destination, self.k_disjoint)

        # Update cache
        self.path_cache[cache_key] = paths
        self.cache_timestamp[cache_key] = datetime.now()

        # Update cache size in stats
        self._stats.update_cache_size(len(self.path_cache))

        return paths

    def get_failover_path(
        self, destination: str, failed_path: List[str]
    ) -> Optional[List[str]]:
        """
        Get alternative path when primary path fails.

        Args:
            destination: Destination node ID
            failed_path: The path that failed

        Returns:
            Alternative path or None if no alternative available
        """
        paths = self.get_cached_k_disjoint_paths(self.local_node_id, destination)

        # Find first path that doesn't overlap with failed path
        for path in paths:
            # Check if paths share any edges
            failed_edges = set()
            for i in range(len(failed_path) - 1):
                failed_edges.add((failed_path[i], failed_path[i + 1]))
                failed_edges.add((failed_path[i + 1], failed_path[i]))

            path_edges = set()
            for i in range(len(path) - 1):
                path_edges.add((path[i], path[i + 1]))
                path_edges.add((path[i + 1], path[i]))

            # If no common edges, this is a valid failover path
            if not failed_edges.intersection(path_edges):
                logger.info(f"Found failover path for {destination}: {path}")
                # Record failover event
                self._stats.record_failover()
                return path

        logger.warning(f"No failover path available for {destination}")
        return None

    def invalidate_cache(self, destination: Optional[str] = None):
        """
        Invalidate path cache.

        Args:
            destination: If specified, invalidate only paths to this destination.
                        If None, invalidate all caches.
        """
        if destination:
            # Invalidate all paths to/from this destination
            keys_to_remove = [
                key for key in self.path_cache.keys() if destination in key
            ]
            for key in keys_to_remove:
                del self.path_cache[key]
                del self.cache_timestamp[key]
            logger.debug(f"Invalidated cache for destination {destination}")
        else:
            # Invalidate all caches
            self.path_cache.clear()
            self.cache_timestamp.clear()
            logger.debug("Invalidated all path caches")

    def prune_dead_nodes(self, timeout: int = 300) -> int:
        """Remove nodes that haven't been seen (timeout in seconds)"""
        dead_nodes = []
        for node_id, node in self.nodes.items():
            if not node.is_alive(timeout):
                dead_nodes.append(node_id)

        for node_id in dead_nodes:
            del self.nodes[node_id]
            # Also remove associated links
            self.links = {
                k: v
                for k, v in self.links.items()
                if k[0] != node_id and k[1] != node_id
            }
            logger.info(f"Pruned dead node: {node_id}")

            # Export topology change metric
            try:
                from src.monitoring.metrics import record_topology_change

                record_topology_change(self.local_node_id, "node_removed")
            except ImportError:
                pass

        return len(dead_nodes)

    def _compute_diameter(self) -> int:
        """Compute mesh diameter (longest shortest path)"""
        if len(self.nodes) < 2:
            return 0

        max_distance = 0
        for source in self.nodes:
            for dest in self.nodes:
                if source != dest:
                    path = self.compute_shortest_path(source, dest)
                    if path and len(path) > 1:
                        # Distance is number of edges, not nodes
                        distance = len(path) - 1
                        max_distance = max(max_distance, distance)

        return max_distance

    def get_topology_stats(self) -> Dict:
        """Get current topology statistics"""
        # Update thread-safe stats
        self._stats.update_topology_counts(len(self.nodes), len(self.links))

        # Get base stats from thread-safe collector
        stats = self._stats.get_stats()

        # Extract values from nested structure
        total_nodes = stats.get("gauges", {}).get("total_nodes", len(self.nodes))
        total_links = stats.get("gauges", {}).get("total_links", len(self.links))

        # Add computed topology metrics
        good_links = sum(
            1
            for link in self.links.values()
            if link.quality.value >= LinkQuality.GOOD.value
        )
        avg_latency = sum(link.latency_ms for link in self.links.values()) / (
            len(self.links) or 1
        )

        # Compute diameter
        try:
            mesh_diameter = self._compute_diameter()
        except Exception:
            mesh_diameter = 0

        # Flatten stats for easier access
        flat_stats = {
            "mesh_id": self.mesh_id,
            "local_node_id": self.local_node_id,
            "total_nodes": int(total_nodes),
            "total_links": int(total_links),
            "good_links": good_links,
            "avg_latency_ms": avg_latency,
            "k_disjoint": self.k_disjoint,
            "cache_ttl": self.cache_ttl,
            "mesh_diameter": mesh_diameter,
        }

        # Merge with nested stats for backward compatibility
        flat_stats.update(stats)

        return flat_stats

    def _compute_diameter(self) -> int:
        """Compute mesh diameter (longest shortest path)"""
        if len(self.nodes) < 2:
            return 0

        max_distance = 0
        for source in self.nodes:
            for dest in self.nodes:
                if source != dest:
                    path = self.compute_shortest_path(source, dest)
                    if path and len(path) > 1:
                        # Distance is number of edges, not nodes
                        distance = len(path) - 1
                        max_distance = max(max_distance, distance)

        return max_distance
