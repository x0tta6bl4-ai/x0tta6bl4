"""
Topology Manager for Mesh Routing.

Manages mesh network topology including:
- Node registration and discovery
- Link quality tracking
- Neighbor relationships
"""

import logging
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    return "100+"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"topology-manager:{_safe_hash(local_node_id)}",
            role="monitoring",
            capabilities=("ops", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "topology_manager_init",
                "goal": "Initialize mesh topology management safely",
                "signals": {
                    "local_node_hash": _safe_hash(local_node_id),
                    "node_count_bucket": "0",
                    "link_source_count_bucket": "0",
                },
                "safety_boundary": "Keep node ids and link endpoints out of thinking context.",
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_node_ids": True,
                    "redact_link_endpoints": True,
                    "preserve_topology_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and quality bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }
        
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
            
        self._record_thinking(
            "topology_node_added",
            "Add or update topology node safely",
            {
                "node_hash": _safe_hash(node_id),
                "is_neighbor": is_neighbor,
                "hop_count_bucket": _safe_count_bucket(hop_count),
                "has_link_quality": link_quality is not None,
                "node_count_bucket": _safe_count_bucket(len(self._nodes)),
            },
        )
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
                
            self._record_thinking(
                "topology_node_removed",
                "Remove topology node safely",
                {
                    "node_hash": _safe_hash(node_id),
                    "removed": True,
                    "node_count_bucket": _safe_count_bucket(len(self._nodes)),
                },
            )
            logger.debug(f"Removed node {node_id}")
            return True
        self._record_thinking(
            "topology_node_removed",
            "Report missing topology node removal",
            {"node_hash": _safe_hash(node_id), "removed": False},
        )
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
        self._record_thinking(
            "topology_link_quality_updated",
            "Update topology link quality safely",
            {
                "from_hash": _safe_hash(from_node),
                "to_hash": _safe_hash(to_node),
                "latency_band": _safe_number_band(quality.latency_ms),
                "throughput_band": _safe_number_band(quality.throughput_mbps),
                "loss_band": _safe_number_band(quality.loss_rate),
                "quality_band": _safe_number_band(quality.quality_score),
            },
        )
    
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
        self._record_thinking(
            "topology_stale_nodes_cleaned",
            "Clean up stale topology nodes",
            {
                "stale_count_bucket": _safe_count_bucket(len(stale)),
                "remaining_node_count_bucket": _safe_count_bucket(len(self._nodes)),
            },
        )
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
        
        stats = {
            "local_node_id": self.local_node_id,
            "total_nodes": len(self._nodes),
            "active_nodes": len(active),
            "neighbor_count": len(neighbors),
            "average_link_quality": avg_quality,
        }
        self._record_thinking(
            "topology_stats",
            "Summarize topology state safely",
            {
                "local_node_hash": _safe_hash(self.local_node_id),
                "total_nodes_bucket": _safe_count_bucket(len(self._nodes)),
                "active_nodes_bucket": _safe_count_bucket(len(active)),
                "neighbor_count_bucket": _safe_count_bucket(len(neighbors)),
                "average_link_quality_band": _safe_number_band(avg_quality),
            },
        )
        return stats
    
    def build_adjacency(self) -> Dict[str, List[str]]:
        """Build adjacency list for pathfinding."""
        adjacency: Dict[str, List[str]] = {self.local_node_id: self.get_neighbors()}
        
        for node_id, links in self._links.items():
            if node_id not in adjacency:
                adjacency[node_id] = []
            adjacency[node_id].extend(links.keys())
            
        self._record_thinking(
            "topology_adjacency_built",
            "Build topology adjacency safely",
            {
                "node_count_bucket": _safe_count_bucket(len(adjacency)),
                "edge_count_bucket": _safe_count_bucket(
                    sum(len(values) for values in adjacency.values())
                ),
            },
        )
        return adjacency
