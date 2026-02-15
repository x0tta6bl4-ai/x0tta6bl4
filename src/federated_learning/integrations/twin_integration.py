"""
Digital Twin Integration for Federated Learning.

Connects PPO Agent with MeshDigitalTwin for realistic
network simulation and training.

Features:
- TwinBackedRoutingEnv: Real network topology from Digital Twin
- FederatedTrainingOrchestrator: Coordinates multi-node FL training
- TwinMetricsCollector: Gathers metrics for monitoring
"""

import logging
# Import Digital Twin
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..aggregators import get_aggregator
from ..blockchain import ConsensusProof, ModelBlockchain, ModelMetadata
from ..coordinator import CoordinatorConfig, FederatedCoordinator, NodeStatus
# Import FL components
from ..ppo_agent import (MeshRoutingEnv, MeshState, PPOAgent, PPOConfig,
                         TrajectoryBuffer, train_episode)
from ..privacy import DifferentialPrivacy, DPConfig
from ..protocol import GlobalModel, ModelUpdate, ModelWeights

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")
from src.simulation.digital_twin import (ChaosScenarioRunner, LinkState,
                                         MeshDigitalTwin, NodeState, TwinLink,
                                         TwinNode)

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for federated training."""

    # Environment
    max_neighbors: int = 8
    max_hops: int = 10

    # PPO
    state_dim: int = 49  # 8 neighbors * 6 features + 1 global
    action_dim: int = 8
    hidden_sizes: List[int] = field(default_factory=lambda: [64, 64])

    # Training
    episodes_per_round: int = 10
    update_interval: int = 5
    local_epochs: int = 3

    # FL
    aggregation_method: str = "fedavg"
    min_participants: int = 3

    # Privacy
    enable_dp: bool = True
    target_epsilon: float = 1.0

    # Blockchain
    enable_blockchain: bool = True


class TwinBackedRoutingEnv(MeshRoutingEnv):
    """
    Routing environment backed by Digital Twin.

    Uses real network topology and simulated failures
    from MeshDigitalTwin for realistic training.
    """

    def __init__(
        self,
        twin: MeshDigitalTwin,
        source_node: Optional[str] = None,
        destination_node: Optional[str] = None,
        max_neighbors: int = 8,
        max_hops: int = 10,
    ):
        super().__init__(
            max_neighbors=max_neighbors, max_hops=max_hops, digital_twin=twin
        )

        self.twin = twin
        self.source_node = source_node
        self.destination_node = destination_node

        # Track routing decisions for analysis
        self.routing_history: List[Dict[str, Any]] = []

        logger.info(f"TwinBackedRoutingEnv initialized with {len(twin.nodes)} nodes")

    def reset(self, source: str = "", destination: str = "") -> MeshState:
        """
        Reset environment using Digital Twin topology.

        Args:
            source: Source node ID (random if empty)
            destination: Destination node ID (random if empty)
        """
        # Use provided nodes or defaults
        source = source or self.source_node
        destination = destination or self.destination_node

        # If still empty, select random nodes from twin
        active_nodes = [
            nid
            for nid, node in self.twin.nodes.items()
            if node.state == NodeState.HEALTHY
        ]

        if not active_nodes:
            logger.warning("No healthy nodes in twin, using synthetic state")
            return super().reset()

        if not source or source not in active_nodes:
            source = active_nodes[0] if active_nodes else ""

        if not destination or destination == source:
            # Pick a different node as destination
            other_nodes = [n for n in active_nodes if n != source]
            destination = other_nodes[-1] if other_nodes else f"dest_{source}"

        self.current_node = source
        self.destination = destination
        self.hops_taken = 0
        self.episode_reward = 0.0
        self.episode_steps = 0

        # Get state from twin
        self.current_state = self._get_state_from_twin(source)

        # Record start of route
        self.routing_history.append(
            {
                "episode": len(self.routing_history),
                "source": source,
                "destination": destination,
                "start_time": time.time(),
                "path": [source],
            }
        )

        return self.current_state

    def step(self, action: int):
        """Take step using Digital Twin state."""
        result = super().step(action)

        # Update routing history
        if self.routing_history:
            current_route = self.routing_history[-1]
            current_route["path"].append(self.current_node)

            if result.done:
                current_route["end_time"] = time.time()
                current_route["success"] = "delivered" in result.info.get("outcome", "")
                current_route["total_hops"] = len(current_route["path"]) - 1
                current_route["total_reward"] = self.episode_reward

        return result

    def inject_failure(self, node_id: str) -> bool:
        """
        Inject node failure via Digital Twin.

        Tests agent's ability to route around failures.
        """
        if node_id not in self.twin.nodes:
            return False

        self.twin.nodes[node_id].state = NodeState.FAILED
        logger.info(f"Injected failure at node {node_id}")
        return True

    def recover_node(self, node_id: str) -> bool:
        """Recover a failed node."""
        if node_id not in self.twin.nodes:
            return False

        self.twin.nodes[node_id].state = NodeState.HEALTHY
        logger.info(f"Recovered node {node_id}")
        return True

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        if not self.routing_history:
            return {}

        successful = [r for r in self.routing_history if r.get("success")]

        return {
            "total_episodes": len(self.routing_history),
            "successful_routes": len(successful),
            "success_rate": len(successful) / len(self.routing_history),
            "avg_hops": sum(r.get("total_hops", 0) for r in successful)
            / max(1, len(successful)),
            "avg_reward": sum(r.get("total_reward", 0) for r in self.routing_history)
            / len(self.routing_history),
        }


class TwinMetricsCollector:
    """
    Collects and aggregates metrics from training.

    Provides data for monitoring and visualization.
    """

    def __init__(self):
        self.training_metrics: List[Dict[str, Any]] = []
        self.aggregation_metrics: List[Dict[str, Any]] = []
        self.routing_metrics: List[Dict[str, Any]] = []
        self.privacy_metrics: List[Dict[str, Any]] = []

    def record_training(
        self,
        node_id: str,
        round_number: int,
        episode_reward: float,
        policy_loss: float,
        value_loss: float,
        entropy: float,
    ) -> None:
        """Record training metrics."""
        self.training_metrics.append(
            {
                "timestamp": time.time(),
                "node_id": node_id,
                "round": round_number,
                "episode_reward": episode_reward,
                "policy_loss": policy_loss,
                "value_loss": value_loss,
                "entropy": entropy,
            }
        )

    def record_aggregation(
        self,
        round_number: int,
        num_participants: int,
        aggregation_method: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record aggregation metrics."""
        self.aggregation_metrics.append(
            {
                "timestamp": time.time(),
                "round": round_number,
                "participants": num_participants,
                "method": aggregation_method,
                "success": success,
                "duration_ms": duration_ms,
            }
        )

    def record_routing(
        self, episode: int, success: bool, hops: int, reward: float
    ) -> None:
        """Record routing metrics."""
        self.routing_metrics.append(
            {
                "timestamp": time.time(),
                "episode": episode,
                "success": success,
                "hops": hops,
                "reward": reward,
            }
        )

    def record_privacy(
        self,
        round_number: int,
        epsilon_spent: float,
        noise_scale: float,
        clipped_count: int,
    ) -> None:
        """Record privacy metrics."""
        self.privacy_metrics.append(
            {
                "timestamp": time.time(),
                "round": round_number,
                "epsilon_spent": epsilon_spent,
                "noise_scale": noise_scale,
                "clipped_count": clipped_count,
            }
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        return {
            "training": {
                "total_records": len(self.training_metrics),
                "avg_reward": self._avg(self.training_metrics, "episode_reward"),
                "avg_policy_loss": self._avg(self.training_metrics, "policy_loss"),
            },
            "aggregation": {
                "total_rounds": len(self.aggregation_metrics),
                "success_rate": self._rate(self.aggregation_metrics, "success"),
                "avg_duration_ms": self._avg(self.aggregation_metrics, "duration_ms"),
            },
            "routing": {
                "total_episodes": len(self.routing_metrics),
                "success_rate": self._rate(self.routing_metrics, "success"),
                "avg_hops": self._avg(self.routing_metrics, "hops"),
            },
            "privacy": {
                "total_epsilon": sum(
                    m.get("epsilon_spent", 0) for m in self.privacy_metrics
                ),
                "avg_noise_scale": self._avg(self.privacy_metrics, "noise_scale"),
            },
        }

    def _avg(self, metrics: List[Dict], key: str) -> float:
        if not metrics:
            return 0.0
        values = [m.get(key, 0) for m in metrics]
        return sum(values) / len(values)

    def _rate(self, metrics: List[Dict], key: str) -> float:
        if not metrics:
            return 0.0
        return sum(1 for m in metrics if m.get(key)) / len(metrics)


class FederatedTrainingOrchestrator:
    """
    Orchestrates federated training across mesh nodes.

    Combines:
    - Digital Twin for simulation
    - PPO Agents on each node
    - FL Coordinator for aggregation
    - DP for privacy
    - Blockchain for audit
    """

    def __init__(self, twin: MeshDigitalTwin, config: Optional[TrainingConfig] = None):
        self.twin = twin
        self.config = config or TrainingConfig()

        # Initialize components
        self._init_coordinator()
        self._init_agents()
        self._init_privacy()
        self._init_blockchain()

        # Metrics
        self.metrics = TwinMetricsCollector()

        # State
        self.current_round = 0
        self.global_weights: Optional[List[float]] = None

        logger.info(
            f"FederatedTrainingOrchestrator initialized with "
            f"{len(self.agents)} agents"
        )

    def _init_coordinator(self) -> None:
        """Initialize FL coordinator."""
        coord_config = CoordinatorConfig(
            min_participants=self.config.min_participants,
            aggregation_method=self.config.aggregation_method,
        )
        self.coordinator = FederatedCoordinator("orchestrator", coord_config)

        # Register all twin nodes
        for node_id in self.twin.nodes:
            self.coordinator.register_node(node_id)

    def _init_agents(self) -> None:
        """Initialize PPO agents for each node."""
        self.agents: Dict[str, PPOAgent] = {}
        self.envs: Dict[str, TwinBackedRoutingEnv] = {}

        ppo_config = PPOConfig(hidden_sizes=self.config.hidden_sizes)

        for node_id in self.twin.nodes:
            # Create agent
            agent = PPOAgent(
                state_dim=self.config.state_dim,
                action_dim=self.config.action_dim,
                config=ppo_config,
            )
            self.agents[node_id] = agent

            # Create environment centered on this node
            env = TwinBackedRoutingEnv(
                twin=self.twin,
                source_node=node_id,
                max_neighbors=self.config.max_neighbors,
                max_hops=self.config.max_hops,
            )
            self.envs[node_id] = env

    def _init_privacy(self) -> None:
        """Initialize differential privacy if enabled."""
        if self.config.enable_dp:
            dp_config = DPConfig(target_epsilon=self.config.target_epsilon)
            self.dp = DifferentialPrivacy(dp_config)
        else:
            self.dp = None

    def _init_blockchain(self) -> None:
        """Initialize blockchain if enabled."""
        if self.config.enable_blockchain:
            self.blockchain = ModelBlockchain("fl-training")
        else:
            self.blockchain = None

    def train_round(self) -> Dict[str, Any]:
        """
        Execute one round of federated training.

        Returns:
            Round metrics
        """
        self.current_round += 1
        round_start = time.time()

        logger.info(f"Starting training round {self.current_round}")

        # Phase 1: Local training
        local_updates = self._local_training_phase()

        # Phase 2: Privacy protection
        if self.dp:
            local_updates = self._apply_privacy(local_updates)

        # Phase 3: Aggregation
        global_weights = self._aggregation_phase(local_updates)

        # Phase 4: Distribution
        self._distribution_phase(global_weights)

        # Phase 5: Blockchain audit
        if self.blockchain:
            self._record_to_blockchain(global_weights, local_updates)

        round_duration = (time.time() - round_start) * 1000

        # Record metrics
        self.metrics.record_aggregation(
            self.current_round,
            len(local_updates),
            self.config.aggregation_method,
            global_weights is not None,
            round_duration,
        )

        return {
            "round": self.current_round,
            "participants": len(local_updates),
            "duration_ms": round_duration,
            "success": global_weights is not None,
        }

    def _local_training_phase(self) -> Dict[str, Dict[str, Any]]:
        """
        Execute local training on each node.

        Returns:
            Dict mapping node_id to update info
        """
        updates = {}

        for node_id, agent in self.agents.items():
            env = self.envs[node_id]

            # Skip failed nodes
            if self.twin.nodes[node_id].state == NodeState.FAILED:
                continue

            total_reward = 0.0

            # Train for configured episodes
            for _ in range(self.config.episodes_per_round):
                episode_metrics = train_episode(
                    agent, env, max_steps=self.config.max_hops * 2
                )
                total_reward += episode_metrics["total_reward"]

            # Get update
            update_metrics = agent.update()

            updates[node_id] = {
                "weights": agent.get_weights(),
                "samples": self.config.episodes_per_round,
                "avg_reward": total_reward / self.config.episodes_per_round,
                "policy_loss": update_metrics.get("policy_loss", 0),
                "value_loss": update_metrics.get("value_loss", 0),
                "entropy": update_metrics.get("entropy", 0),
            }

            # Record training metrics
            self.metrics.record_training(
                node_id,
                self.current_round,
                updates[node_id]["avg_reward"],
                updates[node_id]["policy_loss"],
                updates[node_id]["value_loss"],
                updates[node_id]["entropy"],
            )

        logger.info(f"Local training complete: {len(updates)} participants")
        return updates

    def _apply_privacy(
        self, updates: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Apply differential privacy to updates."""
        for node_id, update in updates.items():
            private_weights, metadata = self.dp.privatize_gradients(
                update["weights"], num_samples=update["samples"]
            )
            update["weights"] = private_weights
            update["dp_metadata"] = metadata

            self.metrics.record_privacy(
                self.current_round,
                metadata["epsilon_spent"],
                metadata["noise_scale"],
                1 if metadata["clipped"] else 0,
            )

        return updates

    def _aggregation_phase(
        self, updates: Dict[str, Dict[str, Any]]
    ) -> Optional[List[float]]:
        """Aggregate updates using configured method."""
        if not updates:
            return None

        # Prepare ModelUpdate objects
        model_updates = []
        for node_id, update in updates.items():
            model_updates.append(
                ModelUpdate(
                    node_id=node_id,
                    round_number=self.current_round,
                    weights=ModelWeights(layer_weights={"flat": update["weights"]}),
                    num_samples=update["samples"],
                )
            )

        # Get aggregator
        aggregator = get_aggregator(self.config.aggregation_method)

        # Aggregate
        result = aggregator.aggregate(model_updates)

        if result.success and result.global_model:
            self.global_weights = result.global_model.weights.layer_weights["flat"]
            logger.info(f"Aggregation successful: {len(self.global_weights)} weights")
            return self.global_weights
        else:
            logger.warning(
                f"Aggregation failed: {getattr(result, 'message', 'unknown')}"
            )
            return None

    def _distribution_phase(self, weights: Optional[List[float]]) -> None:
        """Distribute global weights to all agents."""
        if weights is None:
            return

        for agent in self.agents.values():
            agent.set_weights(weights)

        logger.info(f"Distributed weights to {len(self.agents)} agents")

    def _record_to_blockchain(
        self, weights: Optional[List[float]], updates: Dict[str, Dict[str, Any]]
    ) -> None:
        """Record round to blockchain."""
        if weights is None:
            return

        metadata = ModelMetadata(
            version=self.current_round,
            round_number=self.current_round,
            contributors=list(updates.keys()),
            aggregation_method=self.config.aggregation_method,
            total_samples=sum(u["samples"] for u in updates.values()),
            epsilon_spent=self.dp.budget.epsilon if self.dp else 0.0,
        )

        self.blockchain.add_model_update(weights, metadata)

    def train(
        self, num_rounds: int = 10, callback: Optional[Callable[[Dict], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run full federated training.

        Args:
            num_rounds: Number of training rounds
            callback: Optional callback for each round

        Returns:
            Training history
        """
        history = []

        for _ in range(num_rounds):
            round_metrics = self.train_round()
            history.append(round_metrics)

            if callback:
                callback(round_metrics)

        return history

    def get_global_model(self) -> Optional[List[float]]:
        """Get current global model weights."""
        return self.global_weights

    def get_training_summary(self) -> Dict[str, Any]:
        """Get summary of training."""
        return {
            "total_rounds": self.current_round,
            "num_agents": len(self.agents),
            "aggregation_method": self.config.aggregation_method,
            "dp_enabled": self.dp is not None,
            "blockchain_enabled": self.blockchain is not None,
            "metrics": self.metrics.get_summary(),
            "blockchain_stats": (
                self.blockchain.get_stats() if self.blockchain else None
            ),
            "privacy_budget": self.dp.get_stats() if self.dp else None,
        }

    def inject_chaos(
        self, scenario: str = "node_failure", target: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inject chaos for resilience testing.

        Args:
            scenario: Type of chaos (node_failure, network_partition)
            target: Specific target node (random if None)
        """
        if scenario == "node_failure":
            if target is None:
                healthy = [
                    nid
                    for nid, n in self.twin.nodes.items()
                    if n.state == NodeState.HEALTHY
                ]
                if healthy:
                    import random

                    target = random.choice(healthy)

            if target and target in self.twin.nodes:
                # Directly set node to FAILED state (don't use simulate_node_failure
                # which auto-recovers)
                self.twin.nodes[target].state = NodeState.FAILED
                return {"scenario": scenario, "target": target, "success": True}

        return {"scenario": scenario, "success": False}

    def evaluate_routing(self, num_episodes: int = 20) -> Dict[str, Any]:
        """
        Evaluate current model's routing performance.

        Args:
            num_episodes: Number of evaluation episodes

        Returns:
            Evaluation metrics
        """
        total_reward = 0.0
        successes = 0
        total_hops = 0

        # Use first agent for evaluation
        agent = list(self.agents.values())[0]
        env = list(self.envs.values())[0]

        for _ in range(num_episodes):
            state = env.reset()
            state_vec = state.to_vector()

            # Pad state
            while len(state_vec) < self.config.state_dim:
                state_vec.append(0.0)
            state_vec = state_vec[: self.config.state_dim]

            done = False
            episode_reward = 0.0
            steps = 0

            while not done and steps < self.config.max_hops * 2:
                action, _, _ = agent.get_action(state_vec, deterministic=True)
                action = min(action, state.num_neighbors - 1)

                result = env.step(action)
                episode_reward += result.reward
                steps += 1
                done = result.done

                if not done:
                    state = result.next_state
                    state_vec = state.to_vector()
                    while len(state_vec) < self.config.state_dim:
                        state_vec.append(0.0)
                    state_vec = state_vec[: self.config.state_dim]

            total_reward += episode_reward
            if "delivered" in env.routing_history[-1].get("outcome", ""):
                successes += 1
                total_hops += steps

            self.metrics.record_routing(
                len(env.routing_history),
                "delivered" in str(env.routing_history[-1]),
                steps,
                episode_reward,
            )

        return {
            "episodes": num_episodes,
            "success_rate": successes / num_episodes,
            "avg_reward": total_reward / num_episodes,
            "avg_hops": total_hops / max(1, successes),
        }
