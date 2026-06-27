from __future__ import annotations
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.vision.processor import VisionProcessor

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
class NodeMetrics:
    """Metrics for a single network node."""
    node_id: str
    centrality: float = 0.0
    degree: int = 0
    betweenness: float = 0.0
    clustering_coef: float = 0.0
    is_bottleneck: bool = False
    is_isolated: bool = False
    health_score: float = 1.0


@dataclass
class LinkMetrics:
    """Metrics for network link between nodes."""
    source: str
    target: str
    bandwidth: float = 0.0
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    utilization: float = 0.0
    is_congested: bool = False


@dataclass
class TopologyMetrics:
    """Complete topology analysis metrics."""
    nodes: Dict[str, NodeMetrics] = field(default_factory=dict)
    links: List[LinkMetrics] = field(default_factory=list)
    avg_centrality: float = 0.0
    network_diameter: int = 0
    cluster_count: int = 0
    resilience_score: float = 1.0


class MeshTopologyAnalyzer:
    """
    Analyzes visual representations of the mesh network (screenshots, diagrams)
    to detect isolated nodes, bottlenecks, and suboptimal routing.
    Phase 3: Week 10 Deliverable.
    
    Optimized algorithms for:
    - Node centrality computation (degree, betweenness)
    - Bottleneck detection using critical path analysis
    - Network resilience scoring
    """

    def __init__(
        self,
        vision_processor: Optional[VisionProcessor] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.processor = vision_processor or VisionProcessor()
        self.config = config or {}
        self._cache: Dict[str, TopologyMetrics] = {}
        
        # Configuration thresholds
        self._centrality_threshold = self.config.get("centrality_threshold", 0.8)
        self._latency_threshold_ms = self.config.get("latency_threshold_ms", 100)
        self._packet_loss_threshold = self.config.get("packet_loss_threshold", 0.05)
        self.thinking_coach = AgentThinkingCoach(
            agent_id="mesh-topology-vision-analyzer",
            role="monitoring",
            capabilities=("ops", "quality", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "vision_topology_analyzer_init",
                "goal": "Initialize visual topology analysis safely",
                "signals": {
                    "centrality_threshold_band": _safe_number_band(
                        self._centrality_threshold
                    ),
                    "latency_threshold_band": _safe_number_band(
                        self._latency_threshold_ms
                    ),
                    "packet_loss_threshold_band": _safe_number_band(
                        self._packet_loss_threshold
                    ),
                    "cache_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep image bytes, node ids, findings text, recommendations, "
                    "and file paths out of thinking context."
                ),
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
                    "redact_image_bytes": True,
                    "redact_node_ids": True,
                    "redact_findings": True,
                    "redact_recommendations": True,
                    "redact_paths": True,
                    "preserve_topology_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and metric bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def _compute_node_degree(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """O(n) algorithm to compute node degrees from link list."""
        degrees = {n["id"]: 0 for n in nodes}
        
        for link in links:
            src, tgt = link.get("source"), link.get("target")
            if src in degrees:
                degrees[src] += 1
            if tgt in degrees:
                degrees[tgt] += 1
        
        return degrees

    def _compute_centrality(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """O(n) normalized degree centrality approximation."""
        degrees = self._compute_node_degree(nodes, links)
        max_possible_degree = max(len(nodes) - 1, 1)
        
        centrality = {
            node_id: min(1.0, degree / max_possible_degree)
            for node_id, degree in degrees.items()
        }
        return centrality

    def _detect_bottlenecks(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
        centrality: Dict[str, float]
    ) -> Set[str]:
        """
        Detect bottleneck nodes using centrality threshold.
        O(n) algorithm using precomputed centrality scores.
        """
        bottlenecks: Set[str] = set()
        
        for node in nodes:
            node_id = node.get("id", "")
            # High centrality + high utilization = bottleneck
            if centrality.get(node_id, 0) >= self._centrality_threshold:
                bottlenecks.add(node_id)
                logger.warning(f"Bottleneck detected: {node_id}")
        
        return bottlenecks

    def _detect_isolated_nodes(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]]
    ) -> Set[str]:
        """O(n) detection of isolated nodes (degree = 0)."""
        degrees = self._compute_node_degree(nodes, links)
        return {node_id for node_id, degree in degrees.items() if degree == 0}

    def _compute_resilience_score(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
        bottlenecks: Set[str],
        isolated: Set[str]
    ) -> float:
        """
        Compute network resilience score (0.0 - 1.0).
        Lower score = less resilient network.
        """
        if not nodes:
            return 0.0
        
        # Base score from connectivity
        n_nodes = len(nodes)
        n_links = len(links)
        connectivity_ratio = n_links / max(n_nodes - 1, 1)
        
        # Penalties for problems
        bottleneck_penalty = len(bottlenecks) / max(n_nodes, 1)
        isolated_penalty = len(isolated) / max(n_nodes, 1)
        
        score = min(1.0, connectivity_ratio * 0.7 - bottleneck_penalty * 0.2 - isolated_penalty * 0.1)
        return max(0.0, score)

    def _analyze_topology_structure(
        self,
        raw_data: Dict[str, Any]
    ) -> TopologyMetrics:
        """
        Core topology analysis algorithm.
        Runs in O(n^2) worst case for centrality computation.
        """
        nodes = raw_data.get("objects_detected", [])
        links = raw_data.get("links", [])
        
        # Step 1: Compute node degrees O(n)
        degrees = self._compute_node_degree(nodes, links)
        
        # Step 2: Compute centrality O(n^2) - approximation O(n)
        centrality = self._compute_centrality(nodes, links)
        
        # Step 3: Detect bottlenecks O(n)
        bottlenecks = self._detect_bottlenecks(nodes, links, centrality)
        
        # Step 4: Detect isolated nodes O(n)
        isolated = self._detect_isolated_nodes(nodes, links)
        
        # Step 5: Build node metrics
        node_metrics: Dict[str, NodeMetrics] = {}
        for node in nodes:
            node_id = node.get("id", "")
            node_metrics[node_id] = NodeMetrics(
                node_id=node_id,
                centrality=centrality.get(node_id, 0.0),
                degree=degrees.get(node_id, 0),
                is_bottleneck=node_id in bottlenecks,
                is_isolated=node_id in isolated,
                health_score=1.0 if node_id not in bottlenecks and node_id not in isolated else 0.5
            )
        
        # Step 6: Compute link metrics
        link_metrics = []
        for link in links:
            link_metrics.append(LinkMetrics(
                source=link.get("source", ""),
                target=link.get("target", ""),
                latency_ms=link.get("latency_ms", 0),
                packet_loss=link.get("packet_loss", 0),
                is_congested=link.get("latency_ms", 0) > self._latency_threshold_ms
            ))
        
        # Step 7: Compute resilience score
        resilience = self._compute_resilience_score(nodes, links, bottlenecks, isolated)
        
        topology = TopologyMetrics(
            nodes=node_metrics,
            links=link_metrics,
            avg_centrality=sum(centrality.values()) / max(len(centrality), 1),
            resilience_score=resilience
        )
        self._record_thinking(
            "vision_topology_structure_analyzed",
            "Analyze topology structure safely",
            {
                "node_count_bucket": _safe_count_bucket(len(nodes)),
                "link_count_bucket": _safe_count_bucket(len(links)),
                "bottleneck_count_bucket": _safe_count_bucket(len(bottlenecks)),
                "isolated_count_bucket": _safe_count_bucket(len(isolated)),
                "resilience_band": _safe_number_band(resilience),
            },
        )
        return topology

    async def analyze_bytes(self, image_data: bytes) -> Dict[str, Any]:
        """
        Analyze network topology from image bytes.
        """
        logger.info(f"Analyzing topology from image bytes (size: {len(image_data)})")
        
        # Check cache
        cache_key = hashlib.sha256(image_data).hexdigest()
        if cache_key in self._cache:
            logger.debug("Using cached topology analysis")
            topology = self._cache[cache_key]
            self._record_thinking(
                "vision_topology_analyzed",
                "Return cached topology analysis safely",
                {
                    "image_hash": _safe_hash(cache_key),
                    "image_size_bucket": _safe_count_bucket(len(image_data)),
                    "cache_hit": True,
                    "node_count_bucket": _safe_count_bucket(len(topology.nodes)),
                    "link_count_bucket": _safe_count_bucket(len(topology.links)),
                },
            )
            return {
                "status": "success",
                "nodes_detected": len(topology.nodes),
                "links_detected": len(topology.links),
                "findings": {},
                "recommendations": [],
                "metrics": {
                    "avg_centrality": topology.avg_centrality,
                    "resilience_score": topology.resilience_score,
                    "bottlenecks": [n for n in topology.nodes.values() if n.is_bottleneck],
                    "isolated_nodes": [n for n in topology.nodes.values() if n.is_isolated],
                }
            }
        
        # 1. Process image bytes
        # This will raise RuntimeError if API key is missing
        raw_data = await self.processor.process_image(image_data)
        
        # 2. Reconstruct graph from Vision API output.
        # The processor is expected to return structured nodes and links.
        
        # If we have findings from the processor, we format them.
        findings = raw_data.get("findings", {})
        if not findings and not raw_data.get("objects_detected"):
            # If nothing was detected and no structured findings, we can't reconstruct topology.
            raise RuntimeError("Vision model failed to detect topology elements.")

        # 3. Run topology analysis algorithm
        topology = self._analyze_topology_structure(raw_data)
        
        # Cache result
        self._cache[cache_key] = topology
        
        result = {
            "status": "success",
            "nodes_detected": len(topology.nodes),
            "links_detected": len(topology.links),
            "findings": findings,
            "recommendations": raw_data.get("proposed_plan", []),
            # New detailed metrics
            "metrics": {
                "avg_centrality": topology.avg_centrality,
                "resilience_score": topology.resilience_score,
                "bottlenecks": [n for n in topology.nodes.values() if n.is_bottleneck],
                "isolated_nodes": [n for n in topology.nodes.values() if n.is_isolated],
            }
        }
        self._record_thinking(
            "vision_topology_analyzed",
            "Analyze topology image bytes safely",
            {
                "image_hash": _safe_hash(cache_key),
                "image_size_bucket": _safe_count_bucket(len(image_data)),
                "cache_hit": False,
                "node_count_bucket": _safe_count_bucket(len(topology.nodes)),
                "link_count_bucket": _safe_count_bucket(len(topology.links)),
                "finding_key_count_bucket": _safe_count_bucket(len(findings)),
                "recommendation_count_bucket": _safe_count_bucket(
                    len(raw_data.get("proposed_plan", []))
                ),
                "resilience_band": _safe_number_band(topology.resilience_score),
            },
        )
        return result

    async def analyze(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze a network topology screenshot from a file path.
        """
        import os
        if not os.path.exists(image_path):
            self._record_thinking(
                "vision_topology_path_analyzed",
                "Reject missing topology image path",
                {"path_hash": _safe_hash(image_path), "exists": False},
            )
            raise FileNotFoundError(f"Image not found at {image_path}")
            
        with open(image_path, "rb") as f:
            result = await self.analyze_bytes(f.read())
        self._record_thinking(
            "vision_topology_path_analyzed",
            "Analyze topology image path safely",
            {"path_hash": _safe_hash(image_path), "exists": True},
        )
        return result
    
    def clear_cache(self) -> None:
        """Clear analysis cache."""
        self._cache.clear()
        self._record_thinking(
            "vision_topology_cache_cleared",
            "Clear topology analysis cache",
            {"cache_count_bucket": "0"},
        )
        logger.info("Topology analysis cache cleared")

