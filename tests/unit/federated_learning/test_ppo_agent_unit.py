"""
Unit tests for src/federated_learning/ppo_agent.py

Covers:
- MeshState (to_vector, num_neighbors)
- RoutingAction (__post_init__)
- StepResult
- MeshRoutingEnv (reset, step, get_metrics, properties, edge cases)
- Transition (NamedTuple)
- TrajectoryBuffer (add, compute_advantages, get_batches, clear, __len__)
- Layer (forward with activations, get_params, set_params)
- MLP (forward, get_params, set_params, num_params)
- PPOConfig (defaults)
- PPOAgent (get_action, store_transition, update, get/set weights, checkpoints)
- train_episode / train_ppo
"""

import json
import math
import os
import random
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.federated_learning.ppo_agent import (MLP, Layer, MeshRoutingEnv,
                                              MeshState, PPOAgent, PPOConfig,
                                              RoutingAction, StepResult,
                                              TrajectoryBuffer, Transition,
                                              train_episode, train_ppo)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(num_neighbors=3, node_id="node_0"):
    """Create a deterministic MeshState for testing."""
    return MeshState(
        node_id=node_id,
        neighbors=[f"neighbor_{i}" for i in range(num_neighbors)],
        rssi=[-50.0 + i * 5 for i in range(num_neighbors)],
        latency=[10.0 + i * 20 for i in range(num_neighbors)],
        packet_loss=[0.01 * (i + 1) for i in range(num_neighbors)],
        queue_depth=0.3,
        hop_counts=[1 + i for i in range(num_neighbors)],
        bandwidth=[50.0 + i * 10 for i in range(num_neighbors)],
        trust_scores=[0.9 - i * 0.1 for i in range(num_neighbors)],
    )


# ===================================================================
# MeshState
# ===================================================================


class TestMeshState:
    def test_to_vector_length(self):
        state = _make_state(num_neighbors=3)
        vec = state.to_vector()
        # 6 per-neighbor features + 1 global
        assert len(vec) == 3 * 6 + 1

    def test_to_vector_normalization(self):
        state = MeshState(
            node_id="n",
            neighbors=["a"],
            rssi=[-100.0],
            latency=[0.0],
            packet_loss=[0.0],
            queue_depth=0.5,
            hop_counts=[0],
            bandwidth=[0.0],
            trust_scores=[1.0],
        )
        vec = state.to_vector()
        # rssi: (-100+100)/100 = 0.0
        assert vec[0] == pytest.approx(0.0)
        # latency: 0/500 = 0.0
        assert vec[1] == pytest.approx(0.0)
        # packet_loss: 0.0
        assert vec[2] == pytest.approx(0.0)
        # hop_count: 0/10 = 0.0
        assert vec[3] == pytest.approx(0.0)
        # bandwidth: 0/100 = 0.0
        assert vec[4] == pytest.approx(0.0)
        # trust: 1.0
        assert vec[5] == pytest.approx(1.0)
        # queue_depth
        assert vec[6] == pytest.approx(0.5)

    def test_to_vector_clipping(self):
        """Latency, hop_count, bandwidth are clamped to 1.0."""
        state = MeshState(
            node_id="n",
            neighbors=["a"],
            rssi=[0.0],
            latency=[9999.0],
            packet_loss=[0.0],
            queue_depth=0.0,
            hop_counts=[100],
            bandwidth=[9999.0],
            trust_scores=[0.5],
        )
        vec = state.to_vector()
        assert vec[1] == pytest.approx(1.0)  # latency clamped
        assert vec[3] == pytest.approx(1.0)  # hop_count clamped
        assert vec[4] == pytest.approx(1.0)  # bandwidth clamped

    def test_num_neighbors(self):
        state = _make_state(num_neighbors=5)
        assert state.num_neighbors == 5


# ===================================================================
# RoutingAction
# ===================================================================


class TestRoutingAction:
    def test_default_next_hop_id(self):
        action = RoutingAction(next_hop_index=2)
        assert action.next_hop_id == "neighbor_2"

    def test_explicit_next_hop_id(self):
        action = RoutingAction(next_hop_index=0, next_hop_id="custom")
        assert action.next_hop_id == "custom"


# ===================================================================
# StepResult
# ===================================================================


class TestStepResult:
    def test_defaults(self):
        state = _make_state()
        result = StepResult(next_state=state, reward=1.0, done=False)
        assert result.info == {}

    def test_with_info(self):
        state = _make_state()
        result = StepResult(next_state=state, reward=-5.0, done=True, info={"err": "x"})
        assert result.info["err"] == "x"


# ===================================================================
# Transition (NamedTuple)
# ===================================================================


class TestTransition:
    def test_fields(self):
        t = Transition(
            state=[1.0],
            action=0,
            reward=1.0,
            next_state=[2.0],
            done=False,
            log_prob=-0.5,
            value=0.8,
        )
        assert t.action == 0
        assert t.done is False


# ===================================================================
# MeshRoutingEnv
# ===================================================================


class TestMeshRoutingEnv:
    def test_observation_and_action_dims(self):
        env = MeshRoutingEnv(max_neighbors=4)
        assert env.observation_space_dim == 4 * 6 + 1
        assert env.action_space_dim == 4

    def test_reset_generates_state(self):
        env = MeshRoutingEnv()
        state = env.reset()
        assert isinstance(state, MeshState)
        assert env.hops_taken == 0
        assert env.episode_reward == 0.0

    def test_reset_with_source_and_destination(self):
        env = MeshRoutingEnv()
        state = env.reset(source="src_node", destination="dst_node")
        assert env.current_node == "src_node"
        assert env.destination == "dst_node"

    def test_step_before_reset_raises(self):
        env = MeshRoutingEnv()
        with pytest.raises(RuntimeError, match="not reset"):
            env.step(0)

    def test_step_invalid_action(self):
        env = MeshRoutingEnv()
        env.reset()
        # Force a state with known neighbors
        env.current_state = _make_state(num_neighbors=2)
        result = env.step(5)  # index 5 out of range
        assert result.done is True
        assert result.reward == -10.0
        assert result.info["error"] == "invalid_action"

    def test_step_packet_lost(self):
        env = MeshRoutingEnv()
        env.reset()
        # State with 100% packet loss on neighbor 0
        state = _make_state(num_neighbors=3)
        state.packet_loss = [1.0, 1.0, 1.0]  # guaranteed loss
        env.current_state = state
        result = env.step(0)
        assert result.done is True
        assert result.reward == -5.0
        assert result.info["outcome"] == "packet_lost"
        assert env.packets_dropped == 1

    def test_step_reached_destination(self):
        env = MeshRoutingEnv()
        env.reset()
        state = _make_state(num_neighbors=3)
        state.packet_loss = [0.0, 0.0, 0.0]
        env.current_state = state
        env.destination = "neighbor_1"  # route to neighbor_1

        result = env.step(1)
        assert result.done is True
        assert result.info["outcome"] == "delivered"
        assert result.reward > 0
        assert env.packets_delivered == 1

    def test_step_max_hops_triggers_delivery(self):
        env = MeshRoutingEnv(max_hops=1)
        env.reset()
        state = _make_state(num_neighbors=3)
        state.packet_loss = [0.0, 0.0, 0.0]
        env.current_state = state
        env.destination = "far_away"

        result = env.step(0)
        # hops_taken becomes 1 == max_hops => delivered
        assert result.done is True
        assert result.info["outcome"] == "delivered"

    def test_step_continue_routing(self):
        env = MeshRoutingEnv(max_hops=100)
        env.reset()
        state = _make_state(num_neighbors=3)
        state.packet_loss = [0.0, 0.0, 0.0]
        env.current_state = state
        env.destination = "far_away"

        result = env.step(0)
        assert result.done is False
        assert "current_hop" in result.info

    def test_get_metrics(self):
        env = MeshRoutingEnv()
        env.packets_delivered = 8
        env.packets_dropped = 2
        env.hops_taken = 16
        m = env.get_metrics()
        assert m["packets_delivered"] == 8
        assert m["packets_dropped"] == 2
        assert m["delivery_rate"] == pytest.approx(0.8)
        assert m["avg_hops"] == pytest.approx(2.0)

    def test_get_metrics_no_packets(self):
        env = MeshRoutingEnv()
        m = env.get_metrics()
        assert m["delivery_rate"] == 0.0
        assert m["avg_hops"] == 0.0

    def test_reset_with_digital_twin(self):
        twin = MagicMock()
        twin.nodes = {"src": MagicMock(cpu_usage=50, trust_score=0.9)}
        twin.links = {}
        env = MeshRoutingEnv(digital_twin=twin)
        # _get_state_from_twin with no links => falls back to synthetic
        state = env.reset(source="src")
        assert isinstance(state, MeshState)

    def test_get_state_from_twin_with_links(self):
        twin = MagicMock()
        node_src = MagicMock(cpu_usage=40, trust_score=0.8)
        node_tgt = MagicMock(trust_score=0.7)
        twin.nodes = {"src": node_src, "tgt": node_tgt}
        link = MagicMock(
            source="src",
            target="tgt",
            rssi=-60.0,
            latency_ms=25.0,
            packet_loss=0.05,
            bandwidth_mbps=80.0,
        )
        twin.links = {"link1": link}
        env = MeshRoutingEnv(digital_twin=twin)
        state = env._get_state_from_twin("src")
        assert state.node_id == "src"
        assert state.neighbors == ["tgt"]
        assert state.rssi == [-60.0]

    def test_get_state_from_twin_no_twin(self):
        env = MeshRoutingEnv()
        state = env._get_state_from_twin("x")
        assert isinstance(state, MeshState)

    def test_get_state_from_twin_unknown_node(self):
        twin = MagicMock()
        twin.nodes = {}
        env = MeshRoutingEnv(digital_twin=twin)
        state = env._get_state_from_twin("unknown")
        assert isinstance(state, MeshState)


# ===================================================================
# TrajectoryBuffer
# ===================================================================


class TestTrajectoryBuffer:
    def test_add_and_len(self):
        buf = TrajectoryBuffer()
        assert len(buf) == 0
        buf.add([1.0, 2.0], 0, 1.0, -0.5, 0.8, False)
        assert len(buf) == 1

    def test_clear(self):
        buf = TrajectoryBuffer()
        buf.add([1.0], 0, 1.0, -0.1, 0.5, False)
        buf.add([2.0], 1, 2.0, -0.2, 0.6, True)
        buf.clear()
        assert len(buf) == 0
        assert buf.advantages == []
        assert buf.returns == []

    def test_compute_advantages_single_done(self):
        buf = TrajectoryBuffer(gamma=0.99, gae_lambda=0.95)
        buf.add([1.0], 0, 5.0, -0.1, 1.0, True)
        buf.compute_advantages()
        # single element: advantage = reward - value = 5.0 - 1.0 = 4.0
        # normalized with only 1 element => stays the same (no std normalization)
        assert len(buf.advantages) == 1
        assert len(buf.returns) == 1
        assert buf.returns[0] == pytest.approx(4.0 + 1.0)

    def test_compute_advantages_multi_step(self):
        buf = TrajectoryBuffer(gamma=0.99, gae_lambda=0.95)
        buf.add([1.0], 0, 1.0, -0.1, 0.5, False)
        buf.add([2.0], 1, 2.0, -0.2, 0.6, True)
        buf.compute_advantages()
        assert len(buf.advantages) == 2
        assert len(buf.returns) == 2

    def test_compute_advantages_normalizes(self):
        buf = TrajectoryBuffer(gamma=0.99, gae_lambda=0.95)
        for i in range(10):
            buf.add([float(i)], 0, float(i), -0.1, 0.5, i == 9)
        buf.compute_advantages()
        # Check normalized mean ~ 0
        mean_adv = sum(buf.advantages) / len(buf.advantages)
        assert abs(mean_adv) < 1e-6

    def test_compute_advantages_with_last_value(self):
        buf = TrajectoryBuffer(gamma=0.99, gae_lambda=0.95)
        buf.add([1.0], 0, 1.0, -0.1, 0.5, False)
        buf.compute_advantages(last_value=2.0)
        # delta = 1.0 + 0.99*2.0 - 0.5 = 2.48
        assert len(buf.advantages) == 1

    def test_get_batches(self):
        buf = TrajectoryBuffer()
        for i in range(5):
            buf.add([float(i)], i % 3, float(i), -0.1, 0.5, i == 4)
        buf.compute_advantages()
        batches = list(buf.get_batches(batch_size=2))
        # 5 items, batch_size=2 => 3 batches (2, 2, 1)
        assert len(batches) == 3
        total_items = sum(len(b["states"]) for b in batches)
        assert total_items == 5

    def test_get_batches_contains_correct_keys(self):
        buf = TrajectoryBuffer()
        buf.add([1.0], 0, 1.0, -0.5, 0.8, True)
        buf.compute_advantages()
        for batch in buf.get_batches(batch_size=64):
            assert "states" in batch
            assert "actions" in batch
            assert "log_probs" in batch
            assert "advantages" in batch
            assert "returns" in batch


# ===================================================================
# Layer
# ===================================================================


class TestLayer:
    def test_init_dimensions(self):
        layer = Layer(4, 3, activation="relu")
        assert len(layer.weights) == 4
        assert len(layer.weights[0]) == 3
        assert len(layer.biases) == 3

    def test_forward_relu(self):
        layer = Layer(2, 2, activation="relu")
        # Set weights to identity-ish for predictability
        layer.weights = [[1.0, 0.0], [0.0, 1.0]]
        layer.biases = [0.0, -10.0]
        out = layer.forward([3.0, 5.0])
        assert out[0] == pytest.approx(3.0)
        assert out[1] == pytest.approx(0.0)  # relu clips negative

    def test_forward_tanh(self):
        layer = Layer(1, 1, activation="tanh")
        layer.weights = [[1.0]]
        layer.biases = [0.0]
        out = layer.forward([0.0])
        assert out[0] == pytest.approx(0.0)

    def test_forward_softmax(self):
        layer = Layer(2, 3, activation="softmax")
        layer.weights = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        layer.biases = [0.0, 0.0, 0.0]
        out = layer.forward([1.0, 1.0])
        assert sum(out) == pytest.approx(1.0)
        assert all(p >= 0 for p in out)

    def test_forward_linear(self):
        layer = Layer(2, 1, activation="linear")
        layer.weights = [[2.0], [3.0]]
        layer.biases = [1.0]
        out = layer.forward([1.0, 1.0])
        assert out[0] == pytest.approx(6.0)

    def test_get_set_params_roundtrip(self):
        layer = Layer(3, 2, activation="relu")
        params = layer.get_params()
        assert len(params) == 3 * 2 + 2  # weights + biases

        # Modify and set back
        new_params = [float(i) for i in range(len(params))]
        layer.set_params(new_params)
        assert layer.get_params() == new_params


# ===================================================================
# MLP
# ===================================================================


class TestMLP:
    def test_forward_shape(self):
        mlp = MLP(layer_sizes=[4, 8, 2], activations=["relu", "softmax"])
        out = mlp.forward([1.0, 2.0, 3.0, 4.0])
        assert len(out) == 2
        assert sum(out) == pytest.approx(1.0)

    def test_num_params(self):
        mlp = MLP(layer_sizes=[3, 4, 2], activations=["relu", "linear"])
        # layer 0: 3*4 + 4 = 16;  layer 1: 4*2 + 2 = 10
        assert mlp.num_params() == 26

    def test_get_set_params_roundtrip(self):
        mlp = MLP(layer_sizes=[2, 3, 1], activations=["relu", "linear"])
        total = mlp.num_params()
        new_params = [0.1 * i for i in range(total)]
        mlp.set_params(new_params)
        got = mlp.get_params()
        for a, b in zip(got, new_params):
            assert a == pytest.approx(b)


# ===================================================================
# PPOConfig
# ===================================================================


class TestPPOConfig:
    def test_defaults(self):
        cfg = PPOConfig()
        assert cfg.hidden_sizes == [64, 64]
        assert cfg.clip_epsilon == pytest.approx(0.2)
        assert cfg.learning_rate == pytest.approx(3e-4)
        assert cfg.epochs_per_update == 10
        assert cfg.batch_size == 64


# ===================================================================
# PPOAgent
# ===================================================================


class TestPPOAgent:
    def _make_agent(self, state_dim=7, action_dim=3):
        cfg = PPOConfig(hidden_sizes=[8], epochs_per_update=2, batch_size=4)
        return PPOAgent(state_dim=state_dim, action_dim=action_dim, config=cfg)

    def test_init(self):
        agent = self._make_agent(state_dim=7, action_dim=3)
        assert agent.state_dim == 7
        assert agent.action_dim == 3
        assert agent.train_steps == 0
        assert agent.episodes_completed == 0

    def test_get_action_deterministic(self):
        random.seed(42)
        agent = self._make_agent()
        state = [0.5] * 7
        action, log_prob, value = agent.get_action(state, deterministic=True)
        assert 0 <= action < 3
        assert isinstance(log_prob, float)
        assert isinstance(value, float)

    def test_get_action_stochastic(self):
        random.seed(42)
        agent = self._make_agent()
        state = [0.5] * 7
        action, log_prob, value = agent.get_action(state, deterministic=False)
        assert 0 <= action < 3

    def test_get_action_log_prob_is_negative(self):
        """log(p) for p in (0,1) should be negative."""
        agent = self._make_agent()
        state = [0.5] * 7
        _, log_prob, _ = agent.get_action(state, deterministic=True)
        assert log_prob <= 0.0

    def test_store_transition(self):
        agent = self._make_agent()
        agent.store_transition(
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7], 1, 2.0, -0.3, 0.5, False
        )
        assert len(agent.buffer) == 1

    def test_update_empty_buffer(self):
        agent = self._make_agent()
        metrics = agent.update()
        assert metrics == {"loss": 0.0}

    def test_update_with_data(self):
        random.seed(123)
        agent = self._make_agent()
        for i in range(10):
            state = [random.random() for _ in range(7)]
            action, lp, val = agent.get_action(state)
            agent.store_transition(state, action, random.random(), lp, val, i == 9)
        metrics = agent.update()
        assert "policy_loss" in metrics
        assert "value_loss" in metrics
        assert "entropy" in metrics
        assert "train_steps" in metrics
        assert agent.train_steps == 1
        # buffer should be cleared after update
        assert len(agent.buffer) == 0

    def test_get_set_weights_roundtrip(self):
        agent = self._make_agent()
        weights = agent.get_weights()
        assert isinstance(weights, list)
        total_params = agent.actor.num_params() + agent.critic.num_params()
        assert len(weights) == total_params

        new_weights = [0.01 * i for i in range(len(weights))]
        agent.set_weights(new_weights)
        got = agent.get_weights()
        for a, b in zip(got, new_weights):
            assert a == pytest.approx(b)

    def test_save_load_checkpoint(self, tmp_path):
        agent = self._make_agent()
        agent.train_steps = 42
        path = str(tmp_path / "checkpoint.json")
        agent.save_checkpoint(path)

        agent2 = self._make_agent()
        agent2.load_checkpoint(path)
        assert agent2.train_steps == 42
        # Weights should match
        w1 = agent.get_weights()
        w2 = agent2.get_weights()
        for a, b in zip(w1, w2):
            assert a == pytest.approx(b)

    def test_checkpoint_file_contents(self, tmp_path):
        agent = self._make_agent()
        path = str(tmp_path / "cp.json")
        agent.save_checkpoint(path)
        with open(path) as f:
            data = json.load(f)
        assert "actor" in data
        assert "critic" in data
        assert "train_steps" in data
        assert "config" in data
        assert data["config"]["state_dim"] == 7

    def test_default_config_used_when_none(self):
        agent = PPOAgent(state_dim=10, action_dim=4)
        assert agent.config.hidden_sizes == [64, 64]


# ===================================================================
# train_episode
# ===================================================================


class TestTrainEpisode:
    def test_returns_metrics(self):
        random.seed(0)
        cfg = PPOConfig(hidden_sizes=[8])
        env = MeshRoutingEnv(max_neighbors=4, max_hops=5)
        agent = PPOAgent(
            state_dim=env.observation_space_dim,
            action_dim=env.action_space_dim,
            config=cfg,
        )
        metrics = train_episode(agent, env, max_steps=20)
        assert "total_reward" in metrics
        assert "steps" in metrics
        assert "episodes" in metrics
        assert agent.episodes_completed == 1

    def test_increments_episodes(self):
        random.seed(1)
        cfg = PPOConfig(hidden_sizes=[8])
        env = MeshRoutingEnv(max_neighbors=4, max_hops=3)
        agent = PPOAgent(
            state_dim=env.observation_space_dim,
            action_dim=env.action_space_dim,
            config=cfg,
        )
        train_episode(agent, env, max_steps=10)
        train_episode(agent, env, max_steps=10)
        assert agent.episodes_completed == 2

    def test_state_padding(self):
        """State vectors shorter than state_dim get padded with zeros."""
        random.seed(2)
        cfg = PPOConfig(hidden_sizes=[8])
        env = MeshRoutingEnv(max_neighbors=8, max_hops=3)
        agent = PPOAgent(
            state_dim=env.observation_space_dim,
            action_dim=env.action_space_dim,
            config=cfg,
        )
        # This should not raise even if the generated state has fewer neighbors
        metrics = train_episode(agent, env, max_steps=10)
        assert metrics["steps"] >= 1


# ===================================================================
# train_ppo
# ===================================================================


class TestTrainPPO:
    def test_returns_history(self):
        random.seed(42)
        cfg = PPOConfig(hidden_sizes=[8], epochs_per_update=1, batch_size=4)
        env = MeshRoutingEnv(max_neighbors=4, max_hops=3)
        agent = PPOAgent(
            state_dim=env.observation_space_dim,
            action_dim=env.action_space_dim,
            config=cfg,
        )
        history = train_ppo(agent, env, num_episodes=6, update_interval=3)
        assert len(history) == 6

    def test_updates_happen_at_intervals(self):
        random.seed(99)
        cfg = PPOConfig(hidden_sizes=[8], epochs_per_update=1, batch_size=4)
        env = MeshRoutingEnv(max_neighbors=4, max_hops=3)
        agent = PPOAgent(
            state_dim=env.observation_space_dim,
            action_dim=env.action_space_dim,
            config=cfg,
        )
        history = train_ppo(agent, env, num_episodes=4, update_interval=2)
        # Entries at update_interval multiples should contain update metrics
        assert "policy_loss" in history[1]  # episode index 1 => ep 2 (2%2==0)
        assert "policy_loss" in history[3]  # episode index 3 => ep 4


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_layer_zero_input(self):
        layer = Layer(3, 2, activation="relu")
        out = layer.forward([0.0, 0.0, 0.0])
        # With zero input, output = biases passed through relu
        assert len(out) == 2

    def test_softmax_numerical_stability(self):
        """Softmax should handle large inputs without overflow."""
        layer = Layer(1, 3, activation="softmax")
        layer.weights = [[100.0, 200.0, 300.0]]
        layer.biases = [0.0, 0.0, 0.0]
        out = layer.forward([1.0])
        assert sum(out) == pytest.approx(1.0)
        assert all(math.isfinite(v) for v in out)

    def test_trajectory_buffer_all_done(self):
        buf = TrajectoryBuffer()
        for i in range(3):
            buf.add([float(i)], 0, 1.0, -0.1, 0.5, True)
        buf.compute_advantages()
        assert len(buf.advantages) == 3

    def test_trajectory_buffer_no_done(self):
        buf = TrajectoryBuffer()
        for i in range(3):
            buf.add([float(i)], 0, 1.0, -0.1, 0.5, False)
        buf.compute_advantages(last_value=1.0)
        assert len(buf.advantages) == 3

    def test_env_step_updates_episode_reward(self):
        env = MeshRoutingEnv(max_hops=100)
        env.reset()
        state = _make_state(num_neighbors=3)
        state.packet_loss = [0.0, 0.0, 0.0]
        env.current_state = state
        env.destination = "far_away"
        result = env.step(0)
        assert env.episode_reward != 0.0

    def test_mlp_single_layer(self):
        mlp = MLP(layer_sizes=[2, 3], activations=["relu"])
        out = mlp.forward([1.0, 2.0])
        assert len(out) == 3

    def test_ppo_multiple_updates(self):
        random.seed(7)
        agent = PPOAgent(
            state_dim=7,
            action_dim=3,
            config=PPOConfig(hidden_sizes=[8], epochs_per_update=1, batch_size=2),
        )
        for _ in range(2):
            for i in range(5):
                state = [random.random() for _ in range(7)]
                a, lp, v = agent.get_action(state)
                agent.store_transition(state, a, random.random(), lp, v, i == 4)
            agent.update()
        assert agent.train_steps == 2

    def test_env_digital_twin_step_continue(self):
        """When step continues, digital_twin is used for next state."""
        twin = MagicMock()
        node_a = MagicMock(cpu_usage=20, trust_score=0.9)
        node_b = MagicMock(cpu_usage=30, trust_score=0.8)
        twin.nodes = {"node_a": node_a, "neighbor_0": node_b}
        link_ab = MagicMock(
            source="neighbor_0",
            target="node_a",
            rssi=-50.0,
            latency_ms=10.0,
            packet_loss=0.0,
            bandwidth_mbps=50.0,
        )
        twin.links = {"l1": link_ab}
        env = MeshRoutingEnv(max_hops=100, digital_twin=twin)
        env.reset()
        state = _make_state(num_neighbors=3)
        state.packet_loss = [0.0, 0.0, 0.0]
        env.current_state = state
        env.destination = "far_away"
        result = env.step(0)
        assert result.done is False

    def test_compute_advantages_zero_std(self):
        """When all advantages are identical, normalization divides by near-zero std."""
        buf = TrajectoryBuffer(gamma=1.0, gae_lambda=1.0)
        # All identical rewards, values, and done flags
        for _ in range(5):
            buf.add([1.0], 0, 1.0, -0.1, 1.0, True)
        buf.compute_advantages()
        # delta = 1.0 - 1.0 = 0 for all, so std=0, no normalization applied
        for a in buf.advantages:
            assert a == pytest.approx(0.0)

    def test_routing_action_zero_index(self):
        a = RoutingAction(next_hop_index=0)
        assert a.next_hop_id == "neighbor_0"

    def test_layer_caches_input_output(self):
        layer = Layer(2, 2, activation="relu")
        layer.weights = [[1.0, 0.0], [0.0, 1.0]]
        layer.biases = [0.0, 0.0]
        inp = [3.0, 4.0]
        layer.forward(inp)
        assert layer._input == inp
        assert layer._output is not None
