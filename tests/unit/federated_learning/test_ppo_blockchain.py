"""
Tests for PPO Agent and Model Blockchain.
"""

import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.federated_learning.blockchain import (Block, BlockType,
                                               ConsensusProof, ModelBlockchain,
                                               ModelMetadata, WeightStorage,
                                               create_genesis_blockchain)
from src.federated_learning.ppo_agent import (MLP, Layer, MeshRoutingEnv,
                                              MeshState, PPOAgent, PPOConfig,
                                              RoutingAction, TrajectoryBuffer,
                                              train_episode, train_ppo)

# ==================== PPO Agent Tests ====================


class TestMeshState:
    """Tests for MeshState."""

    def test_creation(self):
        state = MeshState(
            node_id="node-1",
            neighbors=["n1", "n2"],
            rssi=[-50, -60],
            latency=[10, 20],
            packet_loss=[0.01, 0.02],
            queue_depth=0.3,
            hop_counts=[1, 2],
            bandwidth=[100, 50],
            trust_scores=[0.9, 0.8],
        )
        assert state.num_neighbors == 2

    def test_to_vector(self):
        state = MeshState(
            node_id="node-1",
            neighbors=["n1"],
            rssi=[-50],
            latency=[100],
            packet_loss=[0.1],
            queue_depth=0.5,
            hop_counts=[2],
            bandwidth=[50],
            trust_scores=[0.9],
        )
        vec = state.to_vector()

        # 6 features per neighbor + 1 global
        assert len(vec) == 7
        assert all(0 <= v <= 1 for v in vec)  # Normalized


class TestMeshRoutingEnv:
    """Tests for MeshRoutingEnv."""

    def test_creation(self):
        env = MeshRoutingEnv(max_neighbors=8)
        assert env.observation_space_dim == 8 * 6 + 1
        assert env.action_space_dim == 8

    def test_reset(self):
        env = MeshRoutingEnv()
        state = env.reset()

        assert isinstance(state, MeshState)
        assert state.num_neighbors >= 2

    def test_step_valid_action(self):
        env = MeshRoutingEnv()
        state = env.reset()

        result = env.step(0)  # First neighbor

        assert result.reward != 0
        assert isinstance(result.done, bool)

    def test_step_invalid_action(self):
        env = MeshRoutingEnv(max_neighbors=8)
        env.reset()

        result = env.step(100)  # Invalid action

        assert result.reward == -10.0
        assert result.done

    def test_episode_completion(self):
        env = MeshRoutingEnv(max_hops=5)
        env.reset()

        done = False
        steps = 0
        while not done and steps < 10:
            result = env.step(0)
            done = result.done
            steps += 1

        assert done or steps >= 5

    def test_metrics(self):
        env = MeshRoutingEnv()
        env.reset()
        env.step(0)

        metrics = env.get_metrics()

        assert "packets_delivered" in metrics
        assert "delivery_rate" in metrics


class TestTrajectoryBuffer:
    """Tests for TrajectoryBuffer."""

    def test_creation(self):
        buffer = TrajectoryBuffer()
        assert len(buffer) == 0

    def test_add_transition(self):
        buffer = TrajectoryBuffer()
        buffer.add(
            state=[0.5, 0.5], action=1, reward=1.0, log_prob=-0.5, value=0.8, done=False
        )
        assert len(buffer) == 1

    def test_compute_advantages(self):
        buffer = TrajectoryBuffer(gamma=0.99, gae_lambda=0.95)

        # Add trajectory
        for i in range(5):
            buffer.add([0.5], i % 2, 1.0, -0.5, 0.5, i == 4)

        buffer.compute_advantages(last_value=0.0)

        assert len(buffer.advantages) == 5
        assert len(buffer.returns) == 5

    def test_get_batches(self):
        buffer = TrajectoryBuffer()

        for i in range(10):
            buffer.add([0.5], 0, 1.0, -0.5, 0.5, False)

        buffer.compute_advantages()

        batches = list(buffer.get_batches(batch_size=4))

        assert len(batches) >= 2  # 10 items / 4 batch_size

    def test_clear(self):
        buffer = TrajectoryBuffer()
        buffer.add([0.5], 0, 1.0, -0.5, 0.5, False)
        buffer.clear()

        assert len(buffer) == 0


class TestNeuralNetwork:
    """Tests for MLP implementation."""

    def test_layer_creation(self):
        layer = Layer(10, 5, activation="relu")
        assert len(layer.weights) == 10
        assert len(layer.weights[0]) == 5

    def test_layer_forward(self):
        layer = Layer(3, 2, activation="relu")
        output = layer.forward([1.0, 0.5, 0.0])

        assert len(output) == 2

    def test_mlp_forward(self):
        mlp = MLP([10, 8, 4], ["relu", "softmax"])
        output = mlp.forward([0.5] * 10)

        assert len(output) == 4
        assert abs(sum(output) - 1.0) < 0.01  # Softmax sums to 1

    def test_mlp_params(self):
        mlp = MLP([10, 8, 4], ["relu", "softmax"])
        params = mlp.get_params()

        # 10*8 + 8 (layer 1) + 8*4 + 4 (layer 2) = 80+8+32+4 = 124
        assert len(params) == 124

    def test_mlp_set_params(self):
        mlp = MLP([4, 3, 2], ["relu", "softmax"])
        num_params = mlp.num_params()

        new_params = [0.1] * num_params
        mlp.set_params(new_params)

        retrieved = mlp.get_params()
        assert all(abs(p - 0.1) < 0.01 for p in retrieved)


class TestPPOAgent:
    """Tests for PPOAgent."""

    def test_creation(self):
        agent = PPOAgent(state_dim=10, action_dim=4)

        assert agent.state_dim == 10
        assert agent.action_dim == 4

    def test_get_action(self):
        agent = PPOAgent(state_dim=10, action_dim=4)
        state = [0.5] * 10

        action, log_prob, value = agent.get_action(state)

        assert 0 <= action < 4
        assert log_prob <= 0  # Log prob is negative

    def test_get_action_deterministic(self):
        agent = PPOAgent(state_dim=10, action_dim=4)
        state = [0.5] * 10

        action1, _, _ = agent.get_action(state, deterministic=True)
        action2, _, _ = agent.get_action(state, deterministic=True)

        assert action1 == action2  # Should be same

    def test_store_transition(self):
        agent = PPOAgent(state_dim=10, action_dim=4)

        agent.store_transition([0.5] * 10, 1, 1.0, -0.5, 0.8, False)

        assert len(agent.buffer) == 1

    def test_update(self):
        agent = PPOAgent(state_dim=10, action_dim=4)

        # Add some transitions
        for _ in range(20):
            agent.store_transition([0.5] * 10, 1, 1.0, -0.5, 0.8, False)

        metrics = agent.update()

        assert "policy_loss" in metrics
        assert "value_loss" in metrics

    def test_get_set_weights(self):
        agent = PPOAgent(state_dim=10, action_dim=4)

        weights = agent.get_weights()
        assert len(weights) > 0

        # Modify and set back
        new_weights = [w * 2 for w in weights]
        agent.set_weights(new_weights)

        retrieved = agent.get_weights()
        assert all(abs(r - n) < 0.01 for r, n in zip(retrieved, new_weights))


class TestTraining:
    """Tests for training functions."""

    def test_train_episode(self):
        agent = PPOAgent(state_dim=49, action_dim=8)  # 8*6+1
        env = MeshRoutingEnv(max_neighbors=8)

        metrics = train_episode(agent, env, max_steps=10)

        assert "total_reward" in metrics
        assert "steps" in metrics

    def test_train_ppo_short(self):
        agent = PPOAgent(state_dim=49, action_dim=8)
        env = MeshRoutingEnv(max_neighbors=8)

        history = train_ppo(agent, env, num_episodes=5, update_interval=5)

        assert len(history) == 5


# ==================== Blockchain Tests ====================


class TestWeightStorage:
    """Tests for WeightStorage."""

    def test_store_retrieve(self):
        storage = WeightStorage()
        weights = [1.0, 2.0, 3.0]

        content_hash = storage.store(weights)
        retrieved = storage.retrieve(content_hash)

        assert retrieved == weights

    def test_verify(self):
        storage = WeightStorage()
        weights = [1.0, 2.0, 3.0]
        content_hash = storage.store(weights)

        assert storage.verify(content_hash, weights)
        assert not storage.verify(content_hash, [1.0, 2.0, 4.0])

    def test_contains(self):
        storage = WeightStorage()
        weights = [1.0, 2.0]
        content_hash = storage.store(weights)

        assert storage.contains(content_hash)
        assert not storage.contains("invalid_hash")


class TestBlock:
    """Tests for Block."""

    def test_creation(self):
        block = Block(
            index=1,
            block_type=BlockType.MODEL_UPDATE,
            timestamp=1000.0,
            weights_hash="abc123",
            previous_hash="000000",
        )

        assert block.index == 1
        assert block.block_hash != ""

    def test_verify_hash(self):
        block = Block(
            index=1,
            block_type=BlockType.MODEL_UPDATE,
            timestamp=1000.0,
            weights_hash="abc123",
            previous_hash="000000",
        )

        assert block.verify_hash()

        # Tamper with block
        block.weights_hash = "tampered"
        assert not block.verify_hash()

    def test_to_dict_from_dict(self):
        metadata = ModelMetadata(
            version=1,
            round_number=5,
            contributors=["node-1", "node-2"],
            aggregation_method="krum",
            total_samples=1000,
        )

        block = Block(
            index=1,
            block_type=BlockType.MODEL_UPDATE,
            timestamp=1000.0,
            weights_hash="abc123",
            metadata=metadata,
            previous_hash="000000",
        )

        d = block.to_dict()
        restored = Block.from_dict(d)

        assert restored.index == 1
        assert restored.metadata.version == 1


class TestModelBlockchain:
    """Tests for ModelBlockchain."""

    def test_creation(self):
        bc = ModelBlockchain("test-chain")

        assert bc.chain_id == "test-chain"
        assert len(bc.chain) == 1  # Genesis
        assert bc.chain[0].block_type == BlockType.GENESIS

    def test_add_model_update(self):
        bc = ModelBlockchain()

        metadata = ModelMetadata(
            version=1,
            round_number=1,
            contributors=["node-1"],
            aggregation_method="fedavg",
            total_samples=500,
        )

        block = bc.add_model_update([1.0, 2.0, 3.0], metadata)

        assert block.index == 1
        assert block.block_type == BlockType.MODEL_UPDATE

    def test_chain_integrity(self):
        bc = ModelBlockchain()

        for i in range(3):
            metadata = ModelMetadata(
                version=i + 1,
                round_number=i + 1,
                contributors=["node-1"],
                aggregation_method="fedavg",
                total_samples=100,
            )
            bc.add_model_update([float(i)] * 10, metadata)

        is_valid, errors = bc.verify_chain()

        assert is_valid
        assert len(errors) == 0

    def test_get_model_weights(self):
        bc = ModelBlockchain()

        weights = [1.0, 2.0, 3.0]
        metadata = ModelMetadata(1, 1, ["n1"], "fedavg", 100)
        bc.add_model_update(weights, metadata)

        retrieved = bc.get_model_weights(version=1)

        assert retrieved == weights

    def test_get_latest_weights(self):
        bc = ModelBlockchain()

        for i in range(3):
            metadata = ModelMetadata(i + 1, i + 1, ["n1"], "fedavg", 100)
            bc.add_model_update([float(i + 1)] * 5, metadata)

        latest = bc.get_latest_weights()

        assert latest == [3.0] * 5

    def test_rollback(self):
        bc = ModelBlockchain()

        # Add 3 versions
        for i in range(3):
            metadata = ModelMetadata(i + 1, i + 1, ["n1"], "fedavg", 100)
            bc.add_model_update([float(i + 1)] * 5, metadata)

        # Rollback to version 1
        rollback_block = bc.add_rollback(target_version=1, reason="Test rollback")

        assert rollback_block is not None
        assert rollback_block.block_type == BlockType.ROLLBACK

        # Latest should now point to v1 weights
        latest = bc.get_latest_weights()
        assert latest == [1.0] * 5

    def test_checkpoint(self):
        bc = ModelBlockchain()

        metadata = ModelMetadata(1, 1, ["n1"], "fedavg", 100)
        bc.add_model_update([1.0] * 5, metadata)

        checkpoint = bc.add_checkpoint(
            [1.0] * 5, version=1, description="Test checkpoint"
        )

        assert checkpoint.block_type == BlockType.CHECKPOINT

    def test_model_history(self):
        bc = ModelBlockchain()

        for i in range(3):
            metadata = ModelMetadata(i + 1, i + 1, ["n1"], "fedavg", 100)
            bc.add_model_update([float(i)] * 5, metadata)

        history = bc.get_model_history()

        assert len(history) == 3
        assert history[0]["version"] == 1
        assert history[2]["version"] == 3

    def test_provenance(self):
        bc = ModelBlockchain()

        for i in range(3):
            metadata = ModelMetadata(i + 1, i + 1, ["n1"], "fedavg", 100)
            bc.add_model_update([float(i)] * 5, metadata)

        provenance = bc.get_provenance(version=2)

        # Genesis + v1 + v2
        assert len(provenance) == 3

    def test_stats(self):
        bc = ModelBlockchain()

        metadata = ModelMetadata(1, 1, ["n1"], "fedavg", 100)
        bc.add_model_update([1.0] * 5, metadata)
        bc.add_checkpoint([1.0] * 5, 1)

        stats = bc.get_stats()

        assert stats["chain_length"] == 3
        assert stats["model_updates"] == 1
        assert stats["checkpoints"] == 1


class TestCreateGenesisBlockchain:
    """Tests for genesis blockchain creation."""

    def test_create_genesis(self):
        bc = create_genesis_blockchain([0.0] * 10, "test")

        assert len(bc.chain) == 2  # Genesis + initial model
        assert bc.get_model_weights(0) == [0.0] * 10


class TestIntegration:
    """Integration tests for PPO + Blockchain."""

    def test_ppo_weights_to_blockchain(self):
        """Test storing PPO weights in blockchain."""
        agent = PPOAgent(state_dim=10, action_dim=4)
        bc = ModelBlockchain()

        # Get agent weights
        weights = agent.get_weights()

        # Store in blockchain
        metadata = ModelMetadata(
            version=1,
            round_number=1,
            contributors=["local"],
            aggregation_method="local_training",
            total_samples=0,
        )

        block = bc.add_model_update(weights, metadata)

        # Retrieve and verify
        retrieved = bc.get_model_weights(1)
        assert len(retrieved) == len(weights)

    def test_blockchain_rollback_to_agent(self):
        """Test loading blockchain weights to agent."""
        agent = PPOAgent(state_dim=10, action_dim=4)
        bc = ModelBlockchain()

        # Store initial weights
        initial_weights = agent.get_weights()
        metadata = ModelMetadata(1, 1, ["local"], "initial", 0)
        bc.add_model_update(initial_weights, metadata)

        # Modify agent
        modified = [w * 2 for w in initial_weights]
        agent.set_weights(modified)

        # Store modified
        metadata2 = ModelMetadata(2, 2, ["local"], "modified", 100)
        bc.add_model_update(modified, metadata2)

        # Rollback blockchain
        bc.add_rollback(1, "restore initial")

        # Load from blockchain
        restored = bc.get_latest_weights()
        agent.set_weights(restored)

        # Verify
        current = agent.get_weights()
        assert all(abs(c - i) < 0.01 for c, i in zip(current, initial_weights))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
