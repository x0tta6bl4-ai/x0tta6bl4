"""
Federated Learning Coordinator.

Orchestrates FL training rounds, manages node participation,
and handles model distribution.

Features:
- Async round management
- Node health monitoring
- Adaptive participation selection
- Prometheus metrics integration
"""
import time
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import random

from .protocol import (
    ModelUpdate,
    GlobalModel,
    ModelWeights,
    FLMessage,
    FLMessageType,
    AggregationResult
)
from .aggregators import Aggregator, get_aggregator

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Status of a federated learning node."""
    UNKNOWN = "unknown"
    ONLINE = "online"
    TRAINING = "training"
    IDLE = "idle"
    STALE = "stale"  # Missed heartbeats
    BANNED = "banned"  # Byzantine detected


class RoundStatus(Enum):
    """Status of a training round."""
    PENDING = "pending"
    STARTED = "started"
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NodeInfo:
    """Information about a participating node."""
    node_id: str
    status: NodeStatus = NodeStatus.UNKNOWN
    
    # Performance metrics
    avg_training_time: float = 0.0
    avg_loss: float = 0.0
    total_samples_contributed: int = 0
    rounds_participated: int = 0
    
    # Trust metrics
    trust_score: float = 1.0
    byzantine_violations: int = 0
    
    # Heartbeat tracking
    last_heartbeat: float = 0.0
    consecutive_missed: int = 0
    
    # Metadata
    capabilities: Dict[str, Any] = field(default_factory=dict)
    
    def is_eligible(self, min_trust: float = 0.5) -> bool:
        """Check if node is eligible for participation."""
        return (
            self.status in (NodeStatus.ONLINE, NodeStatus.IDLE) and
            self.trust_score >= min_trust and
            self.byzantine_violations < 3
        )


@dataclass
class TrainingRound:
    """Represents a single training round."""
    round_number: int
    status: RoundStatus = RoundStatus.PENDING
    
    # Participation
    selected_nodes: Set[str] = field(default_factory=set)
    participating_nodes: Set[str] = field(default_factory=set)
    
    # Updates
    received_updates: Dict[str, ModelUpdate] = field(default_factory=dict)
    
    # Timing
    started_at: float = 0.0
    collection_deadline: float = 0.0
    completed_at: float = 0.0
    
    # Configuration
    min_participants: int = 3
    target_participants: int = 10
    collection_timeout: float = 60.0  # seconds
    
    # Results
    aggregation_result: Optional[AggregationResult] = None
    
    def is_collection_complete(self) -> bool:
        """Check if we have enough updates."""
        return len(self.received_updates) >= self.min_participants
    
    def is_deadline_passed(self) -> bool:
        """Check if collection deadline has passed."""
        return time.time() > self.collection_deadline
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_number": self.round_number,
            "status": self.status.value,
            "selected_nodes": list(self.selected_nodes),
            "participating_nodes": list(self.participating_nodes),
            "updates_received": len(self.received_updates),
            "started_at": self.started_at,
            "collection_deadline": self.collection_deadline,
            "completed_at": self.completed_at
        }


@dataclass
class CoordinatorConfig:
    """Configuration for the FL coordinator."""
    # Round settings
    round_duration: float = 60.0  # seconds
    min_participants: int = 3
    target_participants: int = 10
    max_participants: int = 50
    
    # Aggregation
    aggregation_method: str = "krum"
    byzantine_tolerance: int = 1
    
    # Node management
    heartbeat_interval: float = 10.0
    heartbeat_timeout: float = 30.0
    min_trust_score: float = 0.5
    
    # Model
    initial_weights: Optional[ModelWeights] = None
    
    # Async settings
    collection_timeout: float = 60.0
    aggregation_timeout: float = 30.0


class FederatedCoordinator:
    """
    Coordinates federated learning across mesh nodes.
    
    Responsibilities:
    - Manage training rounds
    - Select participants
    - Collect and aggregate updates
    - Distribute global model
    - Monitor node health
    """
    
    def __init__(
        self,
        coordinator_id: str,
        config: Optional[CoordinatorConfig] = None
    ):
        self.coordinator_id = coordinator_id
        self.config = config or CoordinatorConfig()
        
        # State
        self.nodes: Dict[str, NodeInfo] = {}
        self.current_round: Optional[TrainingRound] = None
        self.round_history: List[TrainingRound] = []
        self.global_model: Optional[GlobalModel] = None
        
        # Aggregator - only pass f for Krum
        if self.config.aggregation_method == "krum":
            self.aggregator: Aggregator = get_aggregator(
                self.config.aggregation_method,
                f=self.config.byzantine_tolerance
            )
        else:
            self.aggregator: Aggregator = get_aggregator(
                self.config.aggregation_method
            )
        
        # Callbacks
        self._on_round_complete: List[Callable] = []
        self._on_model_update: List[Callable] = []
        
        # Threading
        self._lock = threading.RLock()
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        
        # Metrics
        self._metrics = {
            "rounds_completed": 0,
            "total_updates_received": 0,
            "byzantine_detections": 0,
            "avg_round_time": 0.0
        }
        
        logger.info(f"FederatedCoordinator '{coordinator_id}' initialized")
    
    # ==================== Node Management ====================
    
    def register_node(
        self,
        node_id: str,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new node for FL participation."""
        with self._lock:
            if node_id in self.nodes:
                logger.warning(f"Node {node_id} already registered")
                return False
            
            self.nodes[node_id] = NodeInfo(
                node_id=node_id,
                status=NodeStatus.ONLINE,
                last_heartbeat=time.time(),
                capabilities=capabilities or {}
            )
            
            logger.info(f"Node {node_id} registered")
            return True
    
    def unregister_node(self, node_id: str) -> bool:
        """Remove a node from FL participation."""
        with self._lock:
            if node_id not in self.nodes:
                return False
            
            del self.nodes[node_id]
            logger.info(f"Node {node_id} unregistered")
            return True
    
    def update_heartbeat(self, node_id: str, status: Dict[str, Any] = None) -> None:
        """Update node heartbeat."""
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.last_heartbeat = time.time()
                node.consecutive_missed = 0
                
                if node.status == NodeStatus.STALE:
                    node.status = NodeStatus.ONLINE
                
                if status:
                    if "training_loss" in status:
                        node.avg_loss = status["training_loss"]
    
    def ban_node(self, node_id: str, reason: str = "Byzantine behavior") -> None:
        """Ban a node from participation."""
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].status = NodeStatus.BANNED
                self.nodes[node_id].byzantine_violations += 1
                logger.warning(f"Node {node_id} banned: {reason}")
    
    def _check_heartbeats(self) -> None:
        """Check for stale nodes."""
        current_time = time.time()
        timeout = self.config.heartbeat_timeout
        
        with self._lock:
            for node_id, node in self.nodes.items():
                if node.status == NodeStatus.BANNED:
                    continue
                
                time_since_heartbeat = current_time - node.last_heartbeat
                
                if time_since_heartbeat > timeout:
                    node.consecutive_missed += 1
                    
                    if node.consecutive_missed >= 3:
                        node.status = NodeStatus.STALE
                        logger.warning(f"Node {node_id} marked stale")
    
    def _heartbeat_loop(self) -> None:
        """Background heartbeat checking loop."""
        while self._running:
            self._check_heartbeats()
            time.sleep(self.config.heartbeat_interval)
    
    def get_eligible_nodes(self) -> List[str]:
        """Get list of nodes eligible for participation."""
        with self._lock:
            return [
                node_id for node_id, node in self.nodes.items()
                if node.is_eligible(self.config.min_trust_score)
            ]
    
    # ==================== Round Management ====================
    
    def start_round(self, round_number: Optional[int] = None) -> Optional[TrainingRound]:
        """
        Start a new training round.
        
        Args:
            round_number: Optional explicit round number
            
        Returns:
            TrainingRound if started, None if failed
        """
        with self._lock:
            if self.current_round and self.current_round.status not in (
                RoundStatus.COMPLETED, RoundStatus.FAILED
            ):
                logger.warning("Cannot start new round - current round in progress")
                return None
            
            # Determine round number
            if round_number is None:
                if self.round_history:
                    round_number = self.round_history[-1].round_number + 1
                else:
                    round_number = 1
            
            # Select participants
            eligible = self.get_eligible_nodes()
            
            if len(eligible) < self.config.min_participants:
                logger.error(
                    f"Not enough eligible nodes: {len(eligible)} < "
                    f"{self.config.min_participants}"
                )
                return None
            
            # Random selection with weighting by trust score
            weights = [
                self.nodes[n].trust_score for n in eligible
            ]
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            num_to_select = min(
                self.config.target_participants,
                len(eligible)
            )
            
            # Weighted random selection
            selected = set()
            available = list(zip(eligible, weights))
            
            while len(selected) < num_to_select and available:
                # Simple weighted selection
                r = random.random()
                cumulative = 0
                for node_id, weight in available:
                    cumulative += weight
                    if r <= cumulative:
                        selected.add(node_id)
                        available = [(n, w) for n, w in available if n != node_id]
                        # Renormalize weights
                        if available:
                            total = sum(w for _, w in available)
                            available = [(n, w/total) for n, w in available]
                        break
            
            # Create round
            round_obj = TrainingRound(
                round_number=round_number,
                status=RoundStatus.STARTED,
                selected_nodes=selected,
                started_at=time.time(),
                collection_deadline=time.time() + self.config.collection_timeout,
                min_participants=self.config.min_participants,
                target_participants=num_to_select,
                collection_timeout=self.config.collection_timeout
            )
            
            self.current_round = round_obj
            
            # Update node status
            for node_id in selected:
                self.nodes[node_id].status = NodeStatus.TRAINING
            
            logger.info(
                f"Round {round_number} started with {len(selected)} selected nodes"
            )
            
            return round_obj
    
    def submit_update(self, update: ModelUpdate) -> bool:
        """
        Submit a local model update.
        
        Args:
            update: Model update from a node
            
        Returns:
            True if accepted, False otherwise
        """
        with self._lock:
            if not self.current_round:
                logger.warning("No active round")
                return False
            
            if self.current_round.status != RoundStatus.STARTED:
                logger.warning(f"Round not accepting updates: {self.current_round.status}")
                return False
            
            node_id = update.node_id
            
            # Verify node is selected
            if node_id not in self.current_round.selected_nodes:
                logger.warning(f"Node {node_id} not selected for this round")
                return False
            
            # Check for duplicate
            if node_id in self.current_round.received_updates:
                logger.warning(f"Duplicate update from {node_id}")
                return False
            
            # Accept update
            self.current_round.received_updates[node_id] = update
            self.current_round.participating_nodes.add(node_id)
            self._metrics["total_updates_received"] += 1
            
            # Update node stats
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.rounds_participated += 1
                node.total_samples_contributed += update.num_samples
                # Rolling average for training time
                node.avg_training_time = (
                    node.avg_training_time * 0.9 + update.training_time_seconds * 0.1
                )
            
            logger.info(
                f"Update from {node_id} accepted "
                f"({len(self.current_round.received_updates)}/"
                f"{self.current_round.target_participants})"
            )
            
            # Check if we should aggregate
            if self.current_round.is_collection_complete():
                self._trigger_aggregation()
            
            return True
    
    def _trigger_aggregation(self) -> None:
        """Trigger aggregation of collected updates."""
        if not self.current_round:
            return
        
        self.current_round.status = RoundStatus.AGGREGATING
        
        try:
            updates = list(self.current_round.received_updates.values())
            
            result = self.aggregator.aggregate(
                updates=updates,
                previous_model=self.global_model
            )
            
            self.current_round.aggregation_result = result
            
            if result.success:
                self.global_model = result.global_model
                self.current_round.status = RoundStatus.COMPLETED
                self.current_round.completed_at = time.time()
                
                # Handle Byzantine detections
                for node_id in result.suspected_byzantine:
                    if node_id in self.nodes:
                        self.nodes[node_id].trust_score *= 0.8
                        self.nodes[node_id].byzantine_violations += 1
                        self._metrics["byzantine_detections"] += 1
                        
                        if self.nodes[node_id].byzantine_violations >= 3:
                            self.ban_node(node_id, "Multiple Byzantine violations")
                
                # Update metrics
                self._metrics["rounds_completed"] += 1
                round_time = self.current_round.completed_at - self.current_round.started_at
                self._metrics["avg_round_time"] = (
                    self._metrics["avg_round_time"] * 0.9 + round_time * 0.1
                )
                
                # Trigger callbacks
                for callback in self._on_round_complete:
                    try:
                        callback(self.current_round)
                    except Exception as e:
                        logger.error(f"Round complete callback error: {e}")
                
                for callback in self._on_model_update:
                    try:
                        callback(self.global_model)
                    except Exception as e:
                        logger.error(f"Model update callback error: {e}")
                
                logger.info(
                    f"Round {self.current_round.round_number} completed. "
                    f"Model version: {self.global_model.version}"
                )
            else:
                self.current_round.status = RoundStatus.FAILED
                logger.error(f"Aggregation failed: {result.error_message}")
            
            # Archive round
            self.round_history.append(self.current_round)
            
            # Reset node status
            for node_id in self.current_round.selected_nodes:
                if node_id in self.nodes and self.nodes[node_id].status == NodeStatus.TRAINING:
                    self.nodes[node_id].status = NodeStatus.IDLE
            
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            self.current_round.status = RoundStatus.FAILED
    
    def check_round_timeout(self) -> bool:
        """
        Check if current round has timed out.
        
        Returns:
            True if round was processed due to timeout
        """
        with self._lock:
            if not self.current_round:
                return False
            
            if self.current_round.status != RoundStatus.STARTED:
                return False
            
            if self.current_round.is_deadline_passed():
                if self.current_round.is_collection_complete():
                    logger.info("Round deadline passed, triggering aggregation")
                    self._trigger_aggregation()
                else:
                    logger.warning(
                        f"Round {self.current_round.round_number} timed out with "
                        f"insufficient participants: "
                        f"{len(self.current_round.received_updates)}/"
                        f"{self.current_round.min_participants}"
                    )
                    self.current_round.status = RoundStatus.FAILED
                    self.round_history.append(self.current_round)
                
                return True
            
            return False
    
    # ==================== Model Management ====================
    
    def initialize_model(self, weights: ModelWeights) -> GlobalModel:
        """Initialize the global model."""
        with self._lock:
            self.global_model = GlobalModel(
                version=0,
                round_number=0,
                weights=weights,
                aggregation_method="initial"
            )
            
            logger.info("Global model initialized")
            return self.global_model
    
    def get_global_model(self) -> Optional[GlobalModel]:
        """Get current global model."""
        with self._lock:
            return self.global_model
    
    # ==================== Callbacks ====================
    
    def on_round_complete(self, callback: Callable[[TrainingRound], None]) -> None:
        """Register callback for round completion."""
        self._on_round_complete.append(callback)
    
    def on_model_update(self, callback: Callable[[GlobalModel], None]) -> None:
        """Register callback for model updates."""
        self._on_model_update.append(callback)
    
    # ==================== Lifecycle ====================
    
    def start(self) -> None:
        """Start the coordinator."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True
            )
            self._heartbeat_thread.start()
            
            logger.info("Coordinator started")
    
    def stop(self) -> None:
        """Stop the coordinator."""
        with self._lock:
            self._running = False
            
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=5.0)
            
            logger.info("Coordinator stopped")
    
    # ==================== Metrics ====================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get coordinator metrics."""
        with self._lock:
            return {
                **self._metrics,
                "registered_nodes": len(self.nodes),
                "eligible_nodes": len(self.get_eligible_nodes()),
                "banned_nodes": sum(
                    1 for n in self.nodes.values() if n.status == NodeStatus.BANNED
                ),
                "current_round": self.current_round.to_dict() if self.current_round else None,
                "global_model_version": self.global_model.version if self.global_model else 0
            }
    
    def get_node_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all nodes."""
        with self._lock:
            return {
                node_id: {
                    "status": node.status.value,
                    "trust_score": node.trust_score,
                    "rounds_participated": node.rounds_participated,
                    "total_samples": node.total_samples_contributed,
                    "avg_training_time": node.avg_training_time,
                    "byzantine_violations": node.byzantine_violations
                }
                for node_id, node in self.nodes.items()
            }
