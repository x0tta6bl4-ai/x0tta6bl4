"""
Topology Manager for Mesh Routing.

Manages mesh network topology including:
- Node registration and discovery
- Link quality tracking
- Neighbor relationships
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LinkQuality:
    """Link quality metrics between two nodes."""
    
    latency_ms: float = 0.0
    throughput_mbps: float = 0.0
    loss_rate: float = 0.0
    rssi: float = -60.0  # Signal strength in dBm
    snr: float = 25.0  # Signal-to-noise ratio
    last_updated: float = field(default_factory=time.time)
    
    @property
    def quality_score(self) -> float:
        """Calculate composite quality score (0-1)."""
        # Latency factor (target: <100ms)
        latency_factor = max(0.0, 1.0 - (self.latency_ms / 200.0))
        
        # Throughput factor (target: >10 Mbps)
        throughput_factor = min(1.0, self.throughput_mbps / 50.0)
        
        # Loss factor (target: <5%)
        loss_factor = max(0.0, 1.0 - (self.loss_rate / 10.0))
        
        # Signal factor (target: >-70 dBm)
        signal_factor = max(0.0, min(1.0, (self.rssi + 90) / 40))
        
        return (latency_factor * 0.3 + throughput_factor * 0.2 + 
                loss_factor * 0.3 + signal_factor * 0.2)


@dataclass
class NodeInfo:
    """Information about a mesh node."""
    
    node_id: str
    is_neighbor: bool = False
    hop_count: int = 1
    link_quality: Optional[LinkQuality] = None
    last_seen: float = field(default_factory=time.time)
    is_active: bool = True
    
    @property
    def age(self) -> float:
        """Time since last contact."""
        return time.time() - self.last_seen


class TopologyManager:
    """
    Manages mesh network topology.
    
    Responsibilities:
    - Track nodes and their status
    - Manage neighbor relationships
    - Track link quality metrics
    - Provide topology statistics
    """
    
    NODE_TIMEOUT = 120.0  # Seconds before node is considered inactive
    
    def __init__(self, local_node_id: str):
        self.local_node_id = local_node_id
        self._nodes: Dict[str, NodeInfo] = {}
        self._links: Dict[str, Dict[str, LinkQuality]] = {}  # node_id -> neighbor_id -> quality
        
    def add_node(self, node_id: str, is_neighbor: bool = False, 
                 hop_count: int = 1, link_quality: Optional[LinkQuality] = None) -> NodeInfo:
        """Add or update a node in the topology."""
        if node_id == self.local_node_id:
            raise ValueError("Cannot add local node to topology")
            
        node = NodeInfo(
            node_id=node_id,
            is_neighbor=is_neighbor,
            hop_count=hop_count,
            link_quality=link_quality,
            last_seen=time.time(),
            is_active=True
        )
        
        self._nodes[node_id] = node
        
        if is_neighbor and link_quality:
            if self.local_node_id not in self._links:
                self._links[self.local_node_id] = {}
            self._links[self.local_node_id][node_id] = link_quality
            
        logger.debug(f"Added node {node_id} (neighbor={is_neighbor}, hop={hop_count})")
        return node
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the topology."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            
            # Clean up links
            if node_id in self._links:
                del self._links[node_id]
            for links in self._links.values():
                links.pop(node_id, None)
                
            logger.debug(f"Removed node {node_id}")
            return True
        return False
    
    def update_link_quality(self, from_node: str, to_node: str, quality: LinkQuality):
        """Update link quality between two nodes."""
        if from_node not in self._links:
            self._links[from_node] = {}
        self._links[from_node][to_node] = quality
        
        # Update node info if it's a neighbor
        if to_node in self._nodes:
            self._nodes[to_node].link_quality = quality
            self._nodes[to_node].last_seen = time.time()
    
    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get node information."""
        return self._nodes.get(node_id)
    
    def get_neighbors(self) -> List[str]:
        """Get list of direct neighbor node IDs."""
        return [nid for nid, node in self._nodes.items() if node.is_neighbor and node.is_active]
    
    def get_active_nodes(self) -> List[str]:
        """Get list of all active node IDs."""
        return [nid for nid, node in self._nodes.items() if node.is_active]
    
    def get_link_quality(self, from_node: str, to_node: str) -> Optional[LinkQuality]:
        """Get link quality between two nodes."""
        return self._links.get(from_node, {}).get(to_node)
    
    def cleanup_stale_nodes(self) -> int:
        """Remove nodes that haven't been seen recently."""
        stale: List[str] = []
        for node_id, node in self._nodes.items():
            if node.age > self.NODE_TIMEOUT:
                node.is_active = False
                stale.append(node_id)
                
        for node_id in stale:
            self.remove_node(node_id)
            
        if stale:
            logger.info(f"Cleaned up {len(stale)} stale nodes")
        return len(stale)
    
    def get_topology_stats(self) -> Dict[str, str | int | float]:
        """Get topology statistics."""
        neighbors = self.get_neighbors()
        active = self.get_active_nodes()
        
        avg_quality = 0.0
        if neighbors:
            qualities: List[float] = []
            for nid in neighbors:
                node = self._nodes.get(nid)
                if node and node.link_quality:
                    qualities.append(node.link_quality.quality_score)
            if qualities:
                avg_quality = sum(qualities) / len(qualities)
        
        return {
            "local_node_id": self.local_node_id,
            "total_nodes": len(self._nodes),
            "active_nodes": len(active),
            "neighbor_count": len(neighbors),
            "average_link_quality": avg_quality,
        }
    
    def build_adjacency(self) -> Dict[str, List[str]]:
        """Build adjacency list for pathfinding."""
        adjacency: Dict[str, List[str]] = {self.local_node_id: self.get_neighbors()}
        
        for node_id, links in self._links.items():
            if node_id not in adjacency:
                adjacency[node_id] = []
            adjacency[node_id].extend(links.keys())
            
        return adjacency
