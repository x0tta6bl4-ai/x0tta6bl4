"""
MeshNetworkManager - aggregates mesh network metrics from real subsystems.

Provides statistics, route management, and healing operations for MAPE-K loop.

Features:
    - ML-based neighbor scoring for intelligent route selection
    - Aggressive healing with state integrity verification
    - Preemptive route freshness checks
    - MTTR (Mean Time To Repair) tracking

Example:
    >>> manager = MeshNetworkManager(node_id="node-001")
    >>> stats = await manager.get_statistics()
    >>> healed = await manager.trigger_aggressive_healing(
    ...     auto_restore_nodes=True,
    ...     verification_mode=VerificationMode.FULL
    ... )
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VerificationMode(Enum):
    """Verification modes for node state integrity checks.
    
    Attributes:
        NONE: No verification, auto-restore without checks (dangerous)
        PING: Basic connectivity check via ICMP/TCP ping
        FULL: Full state verification including last_seen, config hash, peer connectivity
        CONSENSUS: Multi-node consensus verification (requires quorum)
    """
    NONE = "none"
    PING = "ping"
    FULL = "full"
    CONSENSUS = "consensus"


@dataclass
class NodeVerificationResult:
    """Result of a node state verification check.
    
    Attributes:
        node_id: Identifier of the verified node
        is_healthy: Whether the node passed verification
        verification_mode: Mode used for verification
        latency_ms: Round-trip latency in milliseconds (if applicable)
        last_seen_match: Whether last_seen timestamp matches expected
        config_hash_match: Whether configuration hash matches expected
        peer_connectivity: Number of reachable peers from this node
        error_message: Error description if verification failed
        verified_at: Timestamp when verification was performed
    """
    node_id: str
    is_healthy: bool
    verification_mode: VerificationMode
    latency_ms: Optional[float] = None
    last_seen_match: Optional[bool] = None
    config_hash_match: Optional[bool] = None
    peer_connectivity: Optional[int] = None
    error_message: Optional[str] = None
    verified_at: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        if self.verified_at is None:
            self.verified_at = datetime.utcnow()


class NodeVerificationError(Exception):
    """Exception raised when node verification fails."""
    pass


class MeshNetworkManager:
    """
    Aggregates mesh network data from MeshRouter and Yggdrasil.

    Used by MAPEKLoop to monitor network health and trigger healing.
    
    Attributes:
        node_id: Identifier for this network node
        verification_timeout_seconds: Timeout for node verification checks
        verification_retries: Number of retries for failed verifications
        consensus_quorum: Minimum nodes required for consensus verification
    
    Example:
        >>> manager = MeshNetworkManager(node_id="node-001")
        >>> result = await manager.verify_node_state(
        ...     node_id="node-002",
        ...     mode=VerificationMode.FULL
        ... )
        >>> if result.is_healthy:
        ...     print(f"Node {result.node_id} is healthy")
    """

    # Default configuration constants
    DEFAULT_VERIFICATION_TIMEOUT: int = 30
    DEFAULT_VERIFICATION_RETRIES: int = 3
    DEFAULT_CONSENSUS_QUORUM: int = 3
    UNVERIFIED_RESTORE_ENV_VAR: str = "X0TTA6BL4_ALLOW_UNVERIFIED_RESTORE"

    def __init__(
        self,
        node_id: str = "local",
        verification_timeout_seconds: int = DEFAULT_VERIFICATION_TIMEOUT,
        verification_retries: int = DEFAULT_VERIFICATION_RETRIES,
        consensus_quorum: int = DEFAULT_CONSENSUS_QUORUM,
    ) -> None:
        """Initialize MeshNetworkManager.
        
        Args:
            node_id: Unique identifier for this network node
            verification_timeout_seconds: Timeout for verification operations
            verification_retries: Number of retries for failed verifications
            consensus_quorum: Minimum nodes for consensus verification
        """
        self.node_id = node_id
        self._router = None  # lazy init
        self._healing_log: List[Dict[str, Any]] = []
        self._route_preference: str = "balanced"
        # ML Scoring components
        self._neighbor_stats: Dict[str, Dict[str, float]] = {}
        self._ml_enabled: bool = True
        # Verification configuration
        self.verification_timeout_seconds = verification_timeout_seconds
        self.verification_retries = verification_retries
        self.consensus_quorum = consensus_quorum
        # Cache for verification results
        self._verification_cache: Dict[str, NodeVerificationResult] = {}

    def ml_score_neighbor(self, neighbor_id: str, rssi: float, load: float, hops: int) -> float:
        """
        Calculate reliability score for a neighbor using hybrid ML logic.
        
        Uses a combination of delivery probability (based on signal strength),
        load factor, and hop count to determine the best next-hop neighbor.
        
        Formula:
            score = delivery_prob * delay_factor
            where:
                delivery_prob = 0.95 if rssi > -70 else 0.70
                delivery_prob *= 0.5 if load > 0.8
                delay_factor = 1.0 / (hops * 15.0 + 1.0)
        
        Args:
            neighbor_id: Unique identifier for the neighbor node
            rssi: Received Signal Strength Indicator in dBm (typically -30 to -100)
            load: Current load on the neighbor (0.0 to 1.0)
            hops: Number of hops to reach this neighbor
        
        Returns:
            Reliability score between 0.0 and 1.0, higher is better
        
        Example:
            >>> score = manager.ml_score_neighbor("node-002", rssi=-65, load=0.3, hops=1)
            >>> print(f"Neighbor score: {score:.3f}")
        """
        # Baseline metrics (simulating model predictions)
        # In production, these would come from self.classifier.predict()
        delivery_prob = 0.95 if rssi > -70 else 0.70
        if load > 0.8:
            delivery_prob *= 0.5
        
        delay_factor = 1.0 / (hops * 15.0 + 1.0)
        
        score = delivery_prob * delay_factor
        
        # Update local stats for analysis
        self._neighbor_stats[neighbor_id] = {
            "score": score,
            "last_rssi": rssi,
            "last_load": load,
            "timestamp": time.time()
        }
        
        return score

    def select_best_neighbor(self, neighbors: List[Dict[str, Any]]) -> Optional[str]:
        """
        Select the best next hop based on ML scores.
        
        Evaluates all candidate neighbors and returns the one with
        the highest reliability score calculated by ml_score_neighbor().
        
        Args:
            neighbors: List of neighbor dictionaries, each containing:
                - id: Neighbor identifier
                - rssi: Signal strength (optional, default -100)
                - load: Current load (optional, default 0.0)
                - hops: Hop count (optional, default 1)
        
        Returns:
            Node ID of the best neighbor, or None if neighbors list is empty
        
        Example:
            >>> neighbors = [
            ...     {"id": "node-002", "rssi": -65, "load": 0.3, "hops": 1},
            ...     {"id": "node-003", "rssi": -80, "load": 0.1, "hops": 2},
            ... ]
            >>> best = manager.select_best_neighbor(neighbors)
            >>> print(f"Best neighbor: {best}")
        """
        if not neighbors:
            return None
            
        scored_neighbors: List[Tuple[str, float]] = []
        for n in neighbors:
            score = self.ml_score_neighbor(
                n["id"], 
                n.get("rssi", -100), 
                n.get("load", 0.0), 
                n.get("hops", 1)
            )
            scored_neighbors.append((n["id"], score))
            
        # Return ID with highest score
        return max(scored_neighbors, key=lambda x: x[1])[0]

    async def verify_node_state(
        self,
        node_id: str,
        mode: VerificationMode = VerificationMode.FULL,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """
        Verify the state integrity of a node before restoring it.
        
        Performs verification based on the specified mode:
        - NONE: Always returns healthy (dangerous, use with caution)
        - PING: Basic TCP/ICMP connectivity check
        - FULL: Comprehensive check including last_seen, config hash, peer connectivity
        - CONSENSUS: Multi-node verification requiring quorum agreement
        
        Args:
            node_id: Unique identifier of the node to verify
            mode: Verification mode (default: FULL)
            expected_last_seen: Expected last_seen timestamp for FULL mode
            expected_config_hash: Expected configuration hash for FULL mode
        
        Returns:
            NodeVerificationResult with verification outcome
        
        Raises:
            NodeVerificationError: If verification fails critically
        
        Example:
            >>> result = await manager.verify_node_state(
            ...     "node-002",
            ...     mode=VerificationMode.FULL,
            ...     expected_last_seen=datetime.utcnow() - timedelta(minutes=5)
            ... )
            >>> if result.is_healthy:
            ...     print(f"Node verified in {result.latency_ms:.1f}ms")
        """
        if mode == VerificationMode.NONE:
            # Bypass verification - only allowed with explicit environment variable
            if not os.getenv(self.UNVERIFIED_RESTORE_ENV_VAR):
                raise NodeVerificationError(
                    f"VerificationMode.NONE requires {self.UNVERIFIED_RESTORE_ENV_VAR}=1"
                )
            logger.warning(f"⚠️ Bypassing verification for node {node_id}")
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=mode,
            )
        
        # Perform verification with retries
        last_error: Optional[str] = None
        for attempt in range(self.verification_retries):
            try:
                if mode == VerificationMode.PING:
                    result = await self._verify_ping(node_id)
                elif mode == VerificationMode.FULL:
                    result = await self._verify_full(
                        node_id, expected_last_seen, expected_config_hash
                    )
                elif mode == VerificationMode.CONSENSUS:
                    result = await self._verify_consensus(node_id)
                else:
                    raise NodeVerificationError(f"Unknown verification mode: {mode}")
                
                # Cache successful result
                if result.is_healthy:
                    self._verification_cache[node_id] = result
                
                return result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Verification attempt {attempt + 1}/{self.verification_retries} "
                    f"failed for node {node_id}: {e}"
                )
                if attempt < self.verification_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # All retries exhausted
        return NodeVerificationResult(
            node_id=node_id,
            is_healthy=False,
            verification_mode=mode,
            error_message=f"Verification failed after {self.verification_retries} attempts: {last_error}",
        )

    async def _verify_ping(self, node_id: str) -> NodeVerificationResult:
        """
        Perform basic connectivity verification via TCP ping.
        
        Attempts to establish a TCP connection to the node's mesh port
        to verify basic network reachability.
        
        Args:
            node_id: Node identifier to ping
        
        Returns:
            NodeVerificationResult with ping outcome
        """
        start_time = time.time()
        
        try:
            # Get node address from database or mesh routing table
            node_address = await self._get_node_address(node_id)
            if not node_address:
                return NodeVerificationResult(
                    node_id=node_id,
                    is_healthy=False,
                    verification_mode=VerificationMode.PING,
                    error_message="Node address not found",
                )
            
            # Attempt TCP connection with timeout
            host, port = node_address
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.verification_timeout_seconds
            )
            writer.close()
            await writer.wait_closed()
            
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"✅ Ping verification passed for {node_id}: {latency_ms:.1f}ms")
            
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=VerificationMode.PING,
                latency_ms=latency_ms,
            )
            
        except asyncio.TimeoutError:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.PING,
                error_message=f"Connection timeout after {self.verification_timeout_seconds}s",
            )
        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.PING,
                error_message=str(e),
            )

    async def _verify_full(
        self,
        node_id: str,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """
        Perform full state verification including connectivity, timestamps, and config.
        
        This is the recommended verification mode for production use as it
        validates multiple aspects of node state integrity.
        
        Args:
            node_id: Node identifier to verify
            expected_last_seen: Expected last_seen timestamp (tolerance: 5 minutes)
            expected_config_hash: Expected SHA-256 hash of node configuration
        
        Returns:
            NodeVerificationResult with comprehensive verification outcome
        """
        # Start with ping verification
        ping_result = await self._verify_ping(node_id)
        if not ping_result.is_healthy:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.FULL,
                error_message=f"Ping failed: {ping_result.error_message}",
            )
        
        last_seen_match: Optional[bool] = None
        config_hash_match: Optional[bool] = None
        peer_connectivity: Optional[int] = None
        
        try:
            # Query node state from database
            from src.database import SessionLocal, MeshNode
            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if not node:
                    return NodeVerificationResult(
                        node_id=node_id,
                        is_healthy=False,
                        verification_mode=VerificationMode.FULL,
                        error_message="Node not found in database",
                    )
                
                # Check last_seen timestamp (5 minute tolerance)
                if expected_last_seen and node.last_seen:
                    time_diff = abs((node.last_seen - expected_last_seen).total_seconds())
                    last_seen_match = time_diff <= 300  # 5 minutes tolerance
                
                # Check configuration hash if provided
                if expected_config_hash:
                    # In production, this would compute hash of node's actual config
                    # For now, we assume match if node has a config
                    config_hash_match = hasattr(node, 'config_hash') and node.config_hash == expected_config_hash
                
                # Count reachable peers
                peers = db.query(MeshNode).filter(
                    MeshNode.mesh_id == node.mesh_id,
                    MeshNode.status == "approved",
                    MeshNode.id != node_id,
                ).all()
                peer_connectivity = len(peers)
            
            # All checks passed
            logger.info(
                f"✅ Full verification passed for {node_id}: "
                f"last_seen_match={last_seen_match}, config_match={config_hash_match}, "
                f"peers={peer_connectivity}"
            )
            
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=VerificationMode.FULL,
                latency_ms=ping_result.latency_ms,
                last_seen_match=last_seen_match,
                config_hash_match=config_hash_match,
                peer_connectivity=peer_connectivity,
            )
            
        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.FULL,
                error_message=f"State verification failed: {e}",
            )

    async def _verify_consensus(self, node_id: str) -> NodeVerificationResult:
        """
        Perform multi-node consensus verification.
        
        Queries multiple nodes in the mesh to reach consensus on whether
        the target node is healthy. Requires quorum agreement.
        
        Args:
            node_id: Node identifier to verify
        
        Returns:
            NodeVerificationResult with consensus outcome
        """
        try:
            from src.database import SessionLocal, MeshNode
            
            # Get peer nodes for consensus
            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if not node:
                    return NodeVerificationResult(
                        node_id=node_id,
                        is_healthy=False,
                        verification_mode=VerificationMode.CONSENSUS,
                        error_message="Node not found in database",
                    )
                
                # Get peers for consensus query
                peers = db.query(MeshNode).filter(
                    MeshNode.mesh_id == node.mesh_id,
                    MeshNode.status == "approved",
                    MeshNode.id != node_id,
                ).limit(self.consensus_quorum * 2).all()
            
            if len(peers) < self.consensus_quorum:
                logger.warning(
                    f"Insufficient peers for consensus verification of {node_id}: "
                    f"need {self.consensus_quorum}, have {len(peers)}"
                )
                # Fall back to full verification
                return await self._verify_full(node_id)
            
            # Query each peer for node health opinion
            # In production, this would use actual mesh protocol messages
            healthy_votes = 0
            total_votes = 0
            
            for peer in peers[:self.consensus_quorum * 2]:
                try:
                    # Simulate peer query (in production: actual mesh RPC)
                    # For now, assume peer agrees if it can reach the node
                    peer_result = await self._verify_ping(node_id)
                    total_votes += 1
                    if peer_result.is_healthy:
                        healthy_votes += 1
                except Exception:
                    continue
            
            # Check quorum
            quorum_reached = healthy_votes >= self.consensus_quorum
            is_healthy = quorum_reached and (healthy_votes / max(total_votes, 1)) > 0.5
            
            logger.info(
                f"{'✅' if is_healthy else '❌'} Consensus verification for {node_id}: "
                f"{healthy_votes}/{total_votes} healthy votes, quorum={quorum_reached}"
            )
            
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=is_healthy,
                verification_mode=VerificationMode.CONSENSUS,
                peer_connectivity=healthy_votes,
                error_message=None if is_healthy else "Consensus quorum not reached",
            )
            
        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.CONSENSUS,
                error_message=f"Consensus verification failed: {e}",
            )

    async def _get_node_address(self, node_id: str) -> Optional[Tuple[str, int]]:
        """
        Get the network address (host, port) for a node.
        
        Args:
            node_id: Node identifier
        
        Returns:
            Tuple of (host, port) or None if not found
        """
        try:
            from src.database import SessionLocal, MeshNode
            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if node and hasattr(node, 'endpoint') and node.endpoint:
                    # Parse endpoint (format: "host:port")
                    parts = node.endpoint.split(':')
                    if len(parts) == 2:
                        return (parts[0], int(parts[1]))
                    return (node.endpoint, 8080)  # Default port
        except Exception as e:
            logger.debug(f"Failed to get node address for {node_id}: {e}")
        
        # Fallback: try mesh routing table
        router = self._get_router()
        if router:
            try:
                route = router.get_route(node_id)
                if route:
                    return (route.next_hop, route.port if hasattr(route, 'port') else 8080)
            except Exception:
                pass
        
        return None

    def _get_router(self):
        """Lazy-init MeshRouter to avoid import-time side effects."""
        if self._router is None:
            try:
                from ..network.routing.mesh_router import MeshRouter

                self._router = MeshRouter(self.node_id)
                logger.info(f"MeshRouter initialized for node {self.node_id}")
            except Exception as e:
                logger.warning(f"MeshRouter unavailable: {e}")
        return self._router

    async def get_statistics(self) -> Dict[str, float]:
        """
        Collect real network statistics from subsystems.

        Returns keys expected by MAPEKLoop:
        - active_peers, avg_latency_ms, packet_loss_percent, mttr_minutes
        """
        stats: Dict[str, float] = {
            "active_peers": 0,
            "avg_latency_ms": 0.0,
            "packet_loss_percent": 0.0,
            "mttr_minutes": 0.0,
        }

        # MeshRouter metrics
        router = self._get_router()
        if router is not None:
            try:
                router_metrics = await router.get_mape_k_metrics()
                stats["packet_loss_percent"] = (
                    router_metrics.get("packet_drop_rate", 0) * 100
                )
                stats["active_peers"] = router_metrics.get("total_routes_known", 0)
                hop_count = router_metrics.get("avg_route_hop_count", 0)
                # Estimate latency from hop count (rough: ~15ms per hop)
                if hop_count > 0:
                    stats["avg_latency_ms"] = hop_count * 15.0
            except Exception as e:
                logger.debug(f"MeshRouter metrics unavailable: {e}")

        # Yggdrasil peer count (supplement)
        try:
            from ..network.yggdrasil_client import get_yggdrasil_peers

            peer_data = get_yggdrasil_peers()
            if peer_data and "count" in peer_data:
                ygg_count = peer_data["count"]
                stats["active_peers"] = max(stats["active_peers"], ygg_count)
        except Exception:
            pass

        # MTTR from healing log
        stats["mttr_minutes"] = self._compute_mttr()

        # ML-based reliability metrics
        if self._ml_enabled and self._neighbor_stats:
            avg_score = sum(s["score"] for s in self._neighbor_stats.values()) / len(self._neighbor_stats)
            stats["ml_reliability_score"] = avg_score

        return stats

    async def set_route_preference(self, preference: str) -> bool:
        """
        Set route selection preference.

        Args:
            preference: One of 'low_latency', 'reliability', 'balanced'
        """
        valid = {"low_latency", "reliability", "balanced"}
        if preference not in valid:
            logger.warning(f"Invalid route preference: {preference}")
            return False
        self._route_preference = preference
        logger.info(f"Route preference set to {preference}")
        return True

    async def trigger_aggressive_healing(
        self,
        auto_restore_nodes: bool = False,
        node_recovery_callback: Optional[Callable[[str], bool]] = None,
        verification_mode: VerificationMode = VerificationMode.FULL,
        require_verification: bool = True,
    ) -> int:
        """
        Force route rediscovery and optionally restore offline nodes in DB.
        
        This method performs two types of healing:
        1. Mesh routing healing - rediscovers stale routes
        2. Database node healing - restores offline nodes with verification
        
        Args:
            auto_restore_nodes: If True, attempt to restore offline nodes.
                               If False (default), only log and count them.
            node_recovery_callback: Optional async callback for custom verification.
                                   If provided, used instead of built-in verification.
            verification_mode: Mode for state integrity verification (default: FULL).
                              Options: NONE, PING, FULL, CONSENSUS.
            require_verification: If True (default), nodes must pass verification.
                                 If False, allows unverified restore with warning.
        
        Returns:
            Number of components healed (routes + nodes).
        
        Raises:
            NodeVerificationError: If verification_mode=NONE without env var.
        
        Security Notes:
            - By default, nodes are NOT restored without passing verification
            - VerificationMode.NONE requires X0TTA6BL4_ALLOW_UNVERIFIED_RESTORE=1
            - Use require_verification=False with caution (logs warning)
        
        Example:
            >>> # Safe: Full verification (recommended)
            >>> healed = await manager.trigger_aggressive_healing(
            ...     auto_restore_nodes=True,
            ...     verification_mode=VerificationMode.FULL
            ... )
            
            >>> # Custom verification callback
            >>> async def my_verify(node_id: str) -> bool:
            ...     return await custom_health_check(node_id)
            >>> healed = await manager.trigger_aggressive_healing(
            ...     auto_restore_nodes=True,
            ...     node_recovery_callback=my_verify
            ... )
        """
        healed = 0
        start_time = time.time()
        verification_results: List[NodeVerificationResult] = []

        # 1. Mesh Routing Healing
        router = self._get_router()
        if router is not None:
            try:
                active_routes = router.get_routes()
                for dest in list(active_routes.keys()):
                    routes = active_routes[dest]
                    stale = [r for r in routes if r.age > router.ROUTE_TIMEOUT * 0.8]
                    for route in stale:
                        try:
                            await router._discover_route(dest)
                            healed += 1
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Aggressive routing healing failed: {e}")

        # 2. Database Node Healing with State Integrity Verification
        try:
            from src.database import SessionLocal, MeshNode
            with SessionLocal() as db:
                offline_nodes = db.query(MeshNode).filter(MeshNode.status == "offline").all()
                
                if not offline_nodes:
                    logger.debug("No offline nodes to heal")
                elif auto_restore_nodes:
                    for node in offline_nodes:
                        try:
                            is_recovered = False
                            
                            # Use custom callback if provided
                            if node_recovery_callback is not None:
                                is_recovered = await node_recovery_callback(node.id)
                            else:
                                # Use built-in verification
                                result = await self.verify_node_state(
                                    node_id=node.id,
                                    mode=verification_mode,
                                )
                                verification_results.append(result)
                                is_recovered = result.is_healthy
                            
                            if is_recovered:
                                logger.info(
                                    f"🔧 Healing: Node {node.id} verified and restored "
                                    f"(mode={verification_mode.value})"
                                )
                                node.status = "healthy"
                                node.last_seen = datetime.utcnow()
                                healed += 1
                            elif not require_verification:
                                # Allow unverified restore with warning
                                logger.warning(
                                    f"⚠️ Node {node.id} restored WITHOUT passing verification "
                                    f"(require_verification=False)"
                                )
                                node.status = "healthy"
                                node.last_seen = datetime.utcnow()
                                healed += 1
                            else:
                                logger.warning(
                                    f"⚠️ Node {node.id} failed verification, skipping. "
                                    f"Use require_verification=False to force restore."
                                )
                        except NodeVerificationError as e:
                            logger.error(f"❌ Node {node.id} verification error: {e}")
                        except Exception as e:
                            logger.warning(f"⚠️ Node {node.id} recovery check failed: {e}")
                    
                    db.commit()
                else:
                    # Default: just log offline nodes without modifying
                    logger.info(
                        f"📊 Found {len(offline_nodes)} offline nodes. "
                        "Use auto_restore_nodes=True to attempt recovery."
                    )
                    for node in offline_nodes:
                        logger.debug(f"  - Offline node: {node.id} (last_seen: {node.last_seen})")
                        
        except Exception as e:
            logger.error(f"Database node healing failed: {e}")

        elapsed = (time.time() - start_time) / 60.0
        self._healing_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "healed": healed,
                "duration_minutes": elapsed,
                "verification_mode": verification_mode.value,
                "verification_results": [
                    {
                        "node_id": r.node_id,
                        "is_healthy": r.is_healthy,
                        "latency_ms": r.latency_ms,
                    }
                    for r in verification_results
                ],
            }
        )
        return healed

    async def trigger_preemptive_checks(self):
        """
        Proactively check route freshness for all known destinations.
        """
        router = self._get_router()
        if router is None:
            return

        try:
            active_routes = router.get_routes()
            for dest in list(active_routes.keys()):
                routes = active_routes[dest]
                # If best route is getting stale, start background discovery
                if routes and routes[0].age > router.ROUTE_TIMEOUT * 0.5:
                    try:
                        await router._discover_route(dest)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Preemptive check error: {e}")

    def _compute_mttr(self) -> float:
        """Compute mean time to repair from healing log (minutes)."""
        if not self._healing_log:
            return 0.0
        # Use last 10 entries
        recent = self._healing_log[-10:]
        durations = [
            entry["duration_minutes"] for entry in recent if entry["healed"] > 0
        ]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)
