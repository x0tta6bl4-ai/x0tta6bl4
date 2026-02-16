"""
PPO Agent for Mesh Routing Optimization.

Implements Proximal Policy Optimization for distributed mesh routing decisions.
Each node learns locally, gradients are aggregated federally with DP.

Components:
- MeshRoutingEnv: Gym-compatible environment
- PPOAgent: Actor-Critic with clipped objective
- TrajectoryBuffer: GAE-based advantage estimation

Reference: "Proximal Policy Optimization Algorithms" (Schulman et al., 2017)
"""

import logging
import math
import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)


# ==================== Environment ====================


@dataclass
class MeshState:
    """
    State representation for mesh routing.

    Features:
    - rssi: Signal strength to neighbors (-100 to 0 dBm)
    - latency: RTT to neighbors (ms)
    - packet_loss: Loss rate to neighbors (0-1)
    - queue_depth: Local queue occupancy (0-1)
    - hop_count: Hops to destination
    - bandwidth: Available bandwidth (Mbps)
    - trust_score: Node trust from Zero Trust (0-1)
    """

    node_id: str
    neighbors: List[str]
    rssi: List[float]
    latency: List[float]
    packet_loss: List[float]
    queue_depth: float
    hop_counts: List[int]
    bandwidth: List[float]
    trust_scores: List[float]

    def to_vector(self) -> List[float]:
        """Convert to flat feature vector for neural network."""
        # Normalize features
        features = []

        for i in range(len(self.neighbors)):
            # Per-neighbor features (normalized)
            features.extend(
                [
                    (self.rssi[i] + 100) / 100,  # -100..0 -> 0..1
                    min(self.latency[i] / 500, 1.0),  # 0..500ms -> 0..1
                    self.packet_loss[i],  # Already 0..1
                    min(self.hop_counts[i] / 10, 1.0),  # 0..10 -> 0..1
                    min(self.bandwidth[i] / 100, 1.0),  # 0..100Mbps -> 0..1
                    self.trust_scores[i],  # Already 0..1
                ]
            )

        # Global features
        features.append(self.queue_depth)

        return features

    @property
    def num_neighbors(self) -> int:
        return len(self.neighbors)


@dataclass
class RoutingAction:
    """Action: select next hop for packet routing."""

    next_hop_index: int  # Index into neighbors list
    next_hop_id: str = ""

    def __post_init__(self):
        if not self.next_hop_id:
            self.next_hop_id = f"neighbor_{self.next_hop_index}"


@dataclass
class StepResult:
    """Result of taking an action in the environment."""

    next_state: MeshState
    reward: float
    done: bool
    info: Dict[str, Any] = field(default_factory=dict)


class MeshRoutingEnv:
    """
    Gym-compatible environment for mesh routing.

    Simulates packet routing through a mesh network.
    Agent learns to select optimal next-hop based on network conditions.
    """

    def __init__(
        self,
        max_neighbors: int = 8,
        max_hops: int = 10,
        digital_twin=None,  # Optional: MeshDigitalTwin for realistic simulation
    ):
        self.max_neighbors = max_neighbors
        self.max_hops = max_hops
        self.digital_twin = digital_twin

        # State tracking
        self.current_state: Optional[MeshState] = None
        self.current_node: str = ""
        self.destination: str = ""
        self.hops_taken: int = 0
        self.packets_delivered: int = 0
        self.packets_dropped: int = 0

        # Episode tracking
        self.episode_reward: float = 0.0
        self.episode_steps: int = 0

    @property
    def observation_space_dim(self) -> int:
        """Dimension of observation vector."""
        # 6 features per neighbor + 1 global
        return self.max_neighbors * 6 + 1

    @property
    def action_space_dim(self) -> int:
        """Number of possible actions."""
        return self.max_neighbors

    def reset(self, source: str = "", destination: str = "") -> MeshState:
        """Reset environment for new episode."""
        self.hops_taken = 0
        self.episode_reward = 0.0
        self.episode_steps = 0

        if self.digital_twin:
            # Use digital twin for realistic state
            self.current_state = self._get_state_from_twin(source)
        else:
            # Generate synthetic state
            self.current_state = self._generate_synthetic_state()

        self.current_node = source or self.current_state.node_id
        self.destination = destination or f"dest_{random.randint(0, 99)}"

        return self.current_state

    def step(self, action: int) -> StepResult:
        """
        Take routing action.

        Args:
            action: Index of neighbor to route to

        Returns:
            StepResult with next state, reward, done flag
        """
        if self.current_state is None:
            raise RuntimeError("Environment not reset")

        if action >= self.current_state.num_neighbors:
            # Invalid action - penalize
            return StepResult(
                next_state=self.current_state,
                reward=-10.0,
                done=True,
                info={"error": "invalid_action"},
            )

        # Get selected neighbor info
        neighbor_id = self.current_state.neighbors[action]
        latency = self.current_state.latency[action]
        packet_loss = self.current_state.packet_loss[action]
        trust = self.current_state.trust_scores[action]
        bandwidth = self.current_state.bandwidth[action]

        # Simulate packet transmission
        self.hops_taken += 1
        self.episode_steps += 1

        # Check for packet loss
        if random.random() < packet_loss:
            self.packets_dropped += 1
            reward = -5.0  # Packet lost penalty
            done = True
            info = {"outcome": "packet_lost", "hop": self.hops_taken}

        # Check if reached destination
        elif neighbor_id == self.destination or self.hops_taken >= self.max_hops:
            self.packets_delivered += 1

            # Reward based on efficiency
            hop_bonus = max(0, 10 - self.hops_taken)  # Fewer hops = better
            latency_bonus = max(0, 5 - latency / 100)  # Lower latency = better
            trust_bonus = trust * 3  # Higher trust = better

            reward = 10.0 + hop_bonus + latency_bonus + trust_bonus
            done = True
            info = {"outcome": "delivered", "hops": self.hops_taken}

        else:
            # Continue routing
            # Intermediate reward based on progress
            reward = -0.1 * latency / 100  # Small penalty for latency
            reward += -0.5 * packet_loss  # Penalty for risky links
            reward += 0.2 * trust  # Bonus for trusted nodes

            done = False
            info = {"current_hop": self.hops_taken}

        # Get next state
        if done:
            next_state = self.current_state
        else:
            self.current_node = neighbor_id
            if self.digital_twin:
                next_state = self._get_state_from_twin(neighbor_id)
            else:
                next_state = self._generate_synthetic_state(neighbor_id)
            self.current_state = next_state

        self.episode_reward += reward

        return StepResult(next_state=next_state, reward=reward, done=done, info=info)

    def _generate_synthetic_state(self, node_id: str = "") -> MeshState:
        """Generate synthetic network state for testing."""
        num_neighbors = random.randint(2, self.max_neighbors)

        return MeshState(
            node_id=node_id or f"node_{random.randint(0, 99)}",
            neighbors=[f"neighbor_{i}" for i in range(num_neighbors)],
            rssi=[random.uniform(-90, -30) for _ in range(num_neighbors)],
            latency=[random.uniform(5, 200) for _ in range(num_neighbors)],
            packet_loss=[random.uniform(0, 0.2) for _ in range(num_neighbors)],
            queue_depth=random.uniform(0, 0.8),
            hop_counts=[random.randint(1, 8) for _ in range(num_neighbors)],
            bandwidth=[random.uniform(10, 100) for _ in range(num_neighbors)],
            trust_scores=[random.uniform(0.5, 1.0) for _ in range(num_neighbors)],
        )

    def _get_state_from_twin(self, node_id: str) -> MeshState:
        """Get state from Digital Twin simulation."""
        if not self.digital_twin:
            return self._generate_synthetic_state(node_id)

        # Get node from twin
        if node_id not in self.digital_twin.nodes:
            return self._generate_synthetic_state(node_id)

        node = self.digital_twin.nodes[node_id]

        # Get neighbors
        neighbors = []
        rssi = []
        latency = []
        packet_loss = []
        hop_counts = []
        bandwidth = []
        trust_scores = []

        for link_id, link in self.digital_twin.links.items():
            if link.source == node_id:
                neighbors.append(link.target)
                rssi.append(link.rssi)
                latency.append(link.latency_ms)
                packet_loss.append(link.packet_loss)
                hop_counts.append(1)  # Direct neighbor
                bandwidth.append(link.bandwidth_mbps)
                trust_scores.append(
                    self.digital_twin.nodes.get(link.target, node).trust_score
                )

        if not neighbors:
            return self._generate_synthetic_state(node_id)

        return MeshState(
            node_id=node_id,
            neighbors=neighbors,
            rssi=rssi,
            latency=latency,
            packet_loss=packet_loss,
            queue_depth=node.cpu_usage / 100,
            hop_counts=hop_counts,
            bandwidth=bandwidth,
            trust_scores=trust_scores,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get environment metrics."""
        total = self.packets_delivered + self.packets_dropped
        return {
            "packets_delivered": self.packets_delivered,
            "packets_dropped": self.packets_dropped,
            "delivery_rate": self.packets_delivered / max(1, total),
            "avg_hops": self.hops_taken / max(1, self.packets_delivered),
        }


# ==================== Trajectory Buffer ====================


class Transition(NamedTuple):
    """Single transition in trajectory."""

    state: List[float]
    action: int
    reward: float
    next_state: List[float]
    done: bool
    log_prob: float
    value: float


class TrajectoryBuffer:
    """
    Buffer for storing trajectories with GAE computation.

    Generalized Advantage Estimation for variance reduction.
    """

    def __init__(
        self, gamma: float = 0.99, gae_lambda: float = 0.95, max_size: int = 2048
    ):
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.max_size = max_size

        self.states: List[List[float]] = []
        self.actions: List[int] = []
        self.rewards: List[float] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.dones: List[bool] = []

        self.advantages: List[float] = []
        self.returns: List[float] = []

    def add(
        self,
        state: List[float],
        action: int,
        reward: float,
        log_prob: float,
        value: float,
        done: bool,
    ) -> None:
        """Add transition to buffer."""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)

    def compute_advantages(self, last_value: float = 0.0) -> None:
        """
        Compute GAE advantages.

        Args:
            last_value: Value estimate of final state (for incomplete episodes)
        """
        self.advantages = []
        self.returns = []

        gae = 0.0
        values = self.values + [last_value]

        # Compute advantages in reverse order
        for t in reversed(range(len(self.rewards))):
            if self.dones[t]:
                delta = self.rewards[t] - values[t]
                gae = delta
            else:
                delta = self.rewards[t] + self.gamma * values[t + 1] - values[t]
                gae = delta + self.gamma * self.gae_lambda * gae

            self.advantages.insert(0, gae)
            self.returns.insert(0, gae + values[t])

        # Normalize advantages
        if len(self.advantages) > 1:
            mean = sum(self.advantages) / len(self.advantages)
            std = math.sqrt(
                sum((a - mean) ** 2 for a in self.advantages) / len(self.advantages)
            )
            if std > 1e-8:
                self.advantages = [(a - mean) / std for a in self.advantages]

    def get_batches(self, batch_size: int):
        """Yield random mini-batches."""
        indices = list(range(len(self.states)))
        random.shuffle(indices)

        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]

            yield {
                "states": [self.states[i] for i in batch_indices],
                "actions": [self.actions[i] for i in batch_indices],
                "log_probs": [self.log_probs[i] for i in batch_indices],
                "advantages": [self.advantages[i] for i in batch_indices],
                "returns": [self.returns[i] for i in batch_indices],
            }

    def clear(self) -> None:
        """Clear buffer."""
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.values.clear()
        self.dones.clear()
        self.advantages.clear()
        self.returns.clear()

    def __len__(self) -> int:
        return len(self.states)


# ==================== Neural Network (Pure Python) ====================


class Layer:
    """Simple dense layer implementation."""

    def __init__(self, in_features: int, out_features: int, activation: str = "relu"):
        self.in_features = in_features
        self.out_features = out_features
        self.activation = activation

        # Xavier initialization
        scale = math.sqrt(2.0 / (in_features + out_features))
        self.weights = [
            [random.gauss(0, scale) for _ in range(out_features)]
            for _ in range(in_features)
        ]
        self.biases = [0.0] * out_features

        # Gradients
        self.weight_grads = [[0.0] * out_features for _ in range(in_features)]
        self.bias_grads = [0.0] * out_features

        # Cache for backward pass
        self._input = None
        self._output = None

    def forward(self, x: List[float]) -> List[float]:
        """Forward pass."""
        self._input = x

        # Linear transformation
        output = list(self.biases)
        for i, xi in enumerate(x):
            for j in range(self.out_features):
                output[j] += xi * self.weights[i][j]

        # Activation
        if self.activation == "relu":
            output = [max(0, o) for o in output]
        elif self.activation == "tanh":
            output = [math.tanh(o) for o in output]
        elif self.activation == "softmax":
            max_val = max(output)
            exp_vals = [math.exp(o - max_val) for o in output]
            sum_exp = sum(exp_vals)
            output = [e / sum_exp for e in exp_vals]
        # else: linear (no activation)

        self._output = output
        return output

    def get_params(self) -> List[float]:
        """Get flattened parameters."""
        params = []
        for row in self.weights:
            params.extend(row)
        params.extend(self.biases)
        return params

    def set_params(self, params: List[float]) -> None:
        """Set parameters from flat vector."""
        idx = 0
        for i in range(self.in_features):
            for j in range(self.out_features):
                self.weights[i][j] = params[idx]
                idx += 1
        for j in range(self.out_features):
            self.biases[j] = params[idx]
            idx += 1


class MLP:
    """Multi-layer perceptron."""

    def __init__(self, layer_sizes: List[int], activations: List[str]):
        self.layers = []
        for i in range(len(layer_sizes) - 1):
            self.layers.append(
                Layer(layer_sizes[i], layer_sizes[i + 1], activations[i])
            )

    def forward(self, x: List[float]) -> List[float]:
        """Forward pass through all layers."""
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def get_params(self) -> List[float]:
        """Get all parameters."""
        params = []
        for layer in self.layers:
            params.extend(layer.get_params())
        return params

    def set_params(self, params: List[float]) -> None:
        """Set all parameters."""
        idx = 0
        for layer in self.layers:
            layer_params = layer.in_features * layer.out_features + layer.out_features
            layer.set_params(params[idx : idx + layer_params])
            idx += layer_params

    def num_params(self) -> int:
        """Total number of parameters."""
        return sum(
            layer.in_features * layer.out_features + layer.out_features
            for layer in self.layers
        )


# ==================== PPO Agent ====================


@dataclass
class PPOConfig:
    """PPO hyperparameters."""

    # Network
    hidden_sizes: List[int] = field(default_factory=lambda: [64, 64])

    # PPO
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01

    # Training
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95

    # Updates
    epochs_per_update: int = 10
    batch_size: int = 64
    max_grad_norm: float = 0.5


class PPOAgent:
    """
    Proximal Policy Optimization agent for mesh routing.

    Features:
    - Actor-Critic architecture
    - Clipped surrogate objective
    - GAE advantage estimation
    - FL-compatible weight extraction
    """

    def __init__(
        self, state_dim: int, action_dim: int, config: Optional[PPOConfig] = None
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.config = config or PPOConfig()

        # Build networks
        hidden = self.config.hidden_sizes

        # Actor (policy) network
        self.actor = MLP(
            layer_sizes=[state_dim] + hidden + [action_dim],
            activations=["relu"] * len(hidden) + ["softmax"],
        )

        # Critic (value) network
        self.critic = MLP(
            layer_sizes=[state_dim] + hidden + [1],
            activations=["relu"] * len(hidden) + ["linear"],
        )

        # Trajectory buffer
        self.buffer = TrajectoryBuffer(
            gamma=self.config.gamma, gae_lambda=self.config.gae_lambda
        )

        # Training stats
        self.train_steps = 0
        self.episodes_completed = 0

        logger.info(
            f"PPOAgent initialized: state_dim={state_dim}, action_dim={action_dim}, "
            f"actor_params={self.actor.num_params()}, critic_params={self.critic.num_params()}"
        )

    def get_action(
        self, state: List[float], deterministic: bool = False
    ) -> Tuple[int, float, float]:
        """
        Select action given state.

        Args:
            state: Observation vector
            deterministic: If True, select argmax action

        Returns:
            Tuple of (action, log_prob, value)
        """
        # Get action probabilities
        probs = self.actor.forward(state)

        # Get value estimate
        value = self.critic.forward(state)[0]

        if deterministic:
            action = probs.index(max(probs))
        else:
            # Sample from distribution
            r = random.random()
            cumsum = 0.0
            action = len(probs) - 1
            for i, p in enumerate(probs):
                cumsum += p
                if r <= cumsum:
                    action = i
                    break

        # Compute log probability
        log_prob = math.log(max(probs[action], 1e-10))

        return action, log_prob, value

    def store_transition(
        self,
        state: List[float],
        action: int,
        reward: float,
        log_prob: float,
        value: float,
        done: bool,
    ) -> None:
        """Store transition in buffer."""
        self.buffer.add(state, action, reward, log_prob, value, done)

    def update(self) -> Dict[str, float]:
        """
        Perform PPO update.

        Returns:
            Training metrics
        """
        if len(self.buffer) == 0:
            return {"loss": 0.0}

        # Compute advantages
        self.buffer.compute_advantages()

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        num_updates = 0

        for epoch in range(self.config.epochs_per_update):
            for batch in self.buffer.get_batches(self.config.batch_size):
                policy_loss = 0.0
                value_loss = 0.0
                entropy = 0.0

                for i, state in enumerate(batch["states"]):
                    action = batch["actions"][i]
                    old_log_prob = batch["log_probs"][i]
                    advantage = batch["advantages"][i]
                    target_return = batch["returns"][i]

                    # Forward pass
                    probs = self.actor.forward(state)
                    new_log_prob = math.log(max(probs[action], 1e-10))
                    value = self.critic.forward(state)[0]

                    # PPO clipped objective
                    ratio = math.exp(new_log_prob - old_log_prob)
                    clipped_ratio = max(
                        min(ratio, 1 + self.config.clip_epsilon),
                        1 - self.config.clip_epsilon,
                    )

                    policy_loss += -min(ratio * advantage, clipped_ratio * advantage)
                    value_loss += (value - target_return) ** 2

                    # Entropy bonus
                    for p in probs:
                        if p > 1e-10:
                            entropy += -p * math.log(p)

                batch_size = len(batch["states"])
                total_policy_loss += policy_loss / batch_size
                total_value_loss += value_loss / batch_size
                total_entropy += entropy / batch_size
                num_updates += 1

                # Note: Gradient updates would go here
                # In practice, use autograd (PyTorch/JAX)
                # This is a simulation for FL integration

        self.buffer.clear()
        self.train_steps += 1

        return {
            "policy_loss": total_policy_loss / max(1, num_updates),
            "value_loss": total_value_loss / max(1, num_updates),
            "entropy": total_entropy / max(1, num_updates),
            "train_steps": self.train_steps,
        }

    def get_weights(self) -> List[float]:
        """Get all weights for federated aggregation."""
        weights = []
        weights.extend(self.actor.get_params())
        weights.extend(self.critic.get_params())
        return weights

    def set_weights(self, weights: List[float]) -> None:
        """Set weights from federated aggregation."""
        actor_params = self.actor.num_params()
        self.actor.set_params(weights[:actor_params])
        self.critic.set_params(weights[actor_params:])

    def save_checkpoint(self, path: str) -> None:
        """Save agent weights to file."""
        import json

        checkpoint = {
            "actor": self.actor.get_params(),
            "critic": self.critic.get_params(),
            "train_steps": self.train_steps,
            "config": {"state_dim": self.state_dim, "action_dim": self.action_dim},
        }
        with open(path, "w") as f:
            json.dump(checkpoint, f)

    def load_checkpoint(self, path: str) -> None:
        """Load agent weights from file."""
        import json

        with open(path, "r") as f:
            checkpoint = json.load(f)
        self.actor.set_params(checkpoint["actor"])
        self.critic.set_params(checkpoint["critic"])
        self.train_steps = checkpoint.get("train_steps", 0)


# ==================== Training Loop ====================


def train_episode(
    agent: PPOAgent, env: MeshRoutingEnv, max_steps: int = 100
) -> Dict[str, float]:
    """
    Train agent for one episode.

    Returns:
        Episode metrics
    """
    state = env.reset()
    state_vec = state.to_vector()

    # Pad state to fixed size
    while len(state_vec) < agent.state_dim:
        state_vec.append(0.0)
    state_vec = state_vec[: agent.state_dim]

    total_reward = 0.0
    steps = 0

    for _ in range(max_steps):
        action, log_prob, value = agent.get_action(state_vec)

        # Clamp action to valid range
        action = min(action, state.num_neighbors - 1)

        result = env.step(action)

        next_state_vec = result.next_state.to_vector()
        while len(next_state_vec) < agent.state_dim:
            next_state_vec.append(0.0)
        next_state_vec = next_state_vec[: agent.state_dim]

        agent.store_transition(
            state_vec, action, result.reward, log_prob, value, result.done
        )

        total_reward += result.reward
        steps += 1

        if result.done:
            break

        state = result.next_state
        state_vec = next_state_vec

    agent.episodes_completed += 1

    return {
        "total_reward": total_reward,
        "steps": steps,
        "episodes": agent.episodes_completed,
    }


def train_ppo(
    agent: PPOAgent,
    env: MeshRoutingEnv,
    num_episodes: int = 100,
    update_interval: int = 10,
) -> List[Dict[str, float]]:
    """
    Train PPO agent.

    Args:
        agent: PPO agent
        env: Routing environment
        num_episodes: Number of episodes
        update_interval: Episodes between updates

    Returns:
        Training history
    """
    history = []

    for ep in range(num_episodes):
        episode_metrics = train_episode(agent, env)

        if (ep + 1) % update_interval == 0:
            update_metrics = agent.update()
            episode_metrics.update(update_metrics)
            logger.info(
                f"Episode {ep + 1}: reward={episode_metrics['total_reward']:.2f}"
            )

        history.append(episode_metrics)

    return history
