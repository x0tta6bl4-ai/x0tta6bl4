"""
Batman-adv Mesh Topology Discovery & Management
Core module for x0tta6bl4 decentralized mesh networking
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import heapq

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
    GOOD = 4       # 80-95% delivery
    FAIR = 3       # 60-80% delivery
    POOR = 2       # 40-60% delivery
    BAD = 1        # <40% delivery


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
    
    def __init__(self, mesh_id: str, local_node_id: str):
        self.mesh_id = mesh_id
        self.local_node_id = local_node_id
        self.nodes: Dict[str, MeshNode] = {}
        self.links: Dict[Tuple[str, str], MeshLink] = {}
        self.routing_table: Dict[str, str] = {}  # destination -> next_hop
        
    def add_node(self, node: MeshNode) -> bool:
        """Register a new node in the mesh"""
        if node.node_id in self.nodes:
            logger.warning(f"Node {node.node_id} already exists")
            return False
        
        self.nodes[node.node_id] = node
        logger.info(f"Added node {node.node_id} ({node.ip_address})")
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
            logger.info(f"Added link {link.source} → {link.destination} (quality: {link.quality.name})")
        
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
        distances = {node_id: float('inf') for node_id in self.nodes}
        distances[source] = 0
        previous = {node_id: None for node_id in self.nodes}
        unvisited = set(self.nodes.keys())
        
        while unvisited:
            # Find unvisited node with minimum distance
            current = min(unvisited, key=lambda n: distances[n])
            
            if distances[current] == float('inf'):
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
    
    def update_routing_table(self) -> int:
        """Rebuild routing table from local node"""
        updated = 0
        for dest_id in self.nodes:
            if dest_id != self.local_node_id:
                path = self.compute_shortest_path(self.local_node_id, dest_id)
                if path and len(path) > 1:
                    next_hop = path[1]
                    if self.routing_table.get(dest_id) != next_hop:
                        self.routing_table[dest_id] = next_hop
                        updated += 1
        
        return updated
    
    def prune_dead_nodes(self, timeout: int = 300) -> int:
        """Remove nodes that haven't been seen (timeout in seconds)"""
        dead_nodes = []
        for node_id, node in self.nodes.items():
            if not node.is_alive(timeout):
                dead_nodes.append(node_id)
        
        for node_id in dead_nodes:
            del self.nodes[node_id]
            # Also remove associated links
            self.links = {k: v for k, v in self.links.items() 
                         if k[0] != node_id and k[1] != node_id}
            logger.info(f"Pruned dead node: {node_id}")
        
        return len(dead_nodes)
    
    def get_topology_stats(self) -> Dict:
        """Get current topology statistics"""
        good_links = sum(1 for link in self.links.values() 
                        if link.quality.value >= LinkQuality.GOOD.value)
        avg_latency = sum(link.latency_ms for link in self.links.values()) / (len(self.links) or 1)
        
        return {
            "total_nodes": len(self.nodes),
            "online_nodes": sum(1 for n in self.nodes.values() if n.state == NodeState.ONLINE),
            "total_links": len(self.links),
            "good_links": good_links,
            "avg_latency_ms": avg_latency,
            "mesh_diameter": self._compute_diameter(),
        }
    
    def _compute_diameter(self) -> int:
        """Compute mesh diameter (longest shortest path)"""
        max_distance = 0
        for source in self.nodes:
            for dest in self.nodes:
                if source != dest:
                    path = self.compute_shortest_path(source, dest)
                    if path:
                        max_distance = max(max_distance, len(path) - 1)
        return max_distance
