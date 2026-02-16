"""
Integration Tests: Federated Learning + Digital Twin.

Tests end-to-end training pipeline with realistic network simulation.
"""

import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.federated_learning.blockchain import ModelBlockchain
from src.federated_learning.coordinator import (CoordinatorConfig,
                                                FederatedCoordinator)
from src.federated_learning.integrations.twin_integration import (
    FederatedTrainingOrchestrator, TrainingConfig, TwinBackedRoutingEnv,
    TwinMetricsCollector)
from src.federated_learning.ppo_agent import PPOAgent, train_episode
from src.simulation.digital_twin import (LinkState, MeshDigitalTwin, NodeState,
                                         TwinLink, TwinNode)

# ==================== Fixtures ====================


@pytest.fixture
def small_twin():
    """Create small Digital Twin for testing."""
    twin = MeshDigitalTwin("test-mesh")

    # Add 4 nodes
    for i in range(4):
        node = TwinNode(
            node_id=f"node-{i}",
            cpu_usage=20.0 + i * 10,
            memory_usage=30.0 + i * 5,
            trust_score=0.9 - i * 0.1,
        )
        twin.add_node(node)

    # Add links (mesh topology)
    links = [
        ("node-0", "node-1", 10, -50),
        ("node-0", "node-2", 15, -55),
        ("node-1", "node-2", 8, -45),
        ("node-1", "node-3", 12, -52),
        ("node-2", "node-3", 20, -60),
    ]

    for src, tgt, latency, rssi in links:
        link = TwinLink(
            source=src,
            target=tgt,
            latency_ms=latency,
            rssi=rssi,
            bandwidth_mbps=50.0,
            packet_loss=0.01,
        )
        twin.add_link(link)

    return twin


@pytest.fixture
def medium_twin():
    """Create medium Digital Twin (6 nodes) for realistic tests."""
    twin = MeshDigitalTwin("medium-mesh")

    # Add 6 nodes
    for i in range(6):
        node = TwinNode(
            node_id=f"node-{i}",
            cpu_usage=20.0 + i * 5,
            memory_usage=30.0 + i * 3,
            trust_score=0.95 - i * 0.05,
        )
        twin.add_node(node)

    # Create mesh links
    import random

    random.seed(42)

    for i in range(6):
        for j in range(i + 1, 6):
            if random.random() < 0.6:  # 60% connectivity
                link = TwinLink(
                    source=f"node-{i}",
                    target=f"node-{j}",
                    latency_ms=random.uniform(5, 30),
                    rssi=random.uniform(-70, -40),
                    bandwidth_mbps=random.uniform(20, 100),
                    packet_loss=random.uniform(0.001, 0.05),
                )
                twin.add_link(link)

    return twin


# ==================== TwinBackedRoutingEnv Tests ====================


class TestTwinBackedRoutingEnv:
    """Tests for TwinBackedRoutingEnv."""

    def test_creation(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)

        assert env.twin == small_twin
        assert env.max_neighbors == 8

    def test_reset_with_twin_nodes(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin, source_node="node-0")
        state = env.reset()

        assert state.node_id == "node-0"
        assert state.num_neighbors > 0

    def test_step_uses_twin_topology(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin, source_node="node-0")
        state = env.reset()

        # Step should use actual neighbors
        result = env.step(0)

        assert result.next_state is not None

    def test_routing_history_tracking(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)
        env.reset(source="node-0", destination="node-3")

        # Take a few steps
        for _ in range(3):
            result = env.step(0)
            if result.done:
                break

        assert len(env.routing_history) == 1
        assert env.routing_history[0]["source"] == "node-0"

    def test_inject_failure(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)

        success = env.inject_failure("node-1")

        assert success
        assert small_twin.nodes["node-1"].state == NodeState.FAILED

    def test_recover_node(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)
        env.inject_failure("node-1")

        success = env.recover_node("node-1")

        assert success
        assert small_twin.nodes["node-1"].state == NodeState.HEALTHY

    def test_routing_stats(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)

        # Run a few episodes
        for _ in range(3):
            env.reset()
            done = False
            while not done:
                result = env.step(0)
                done = result.done

        stats = env.get_routing_stats()

        assert "total_episodes" in stats
        assert stats["total_episodes"] == 3


class TestTwinWithPPOAgent:
    """Tests for PPO Agent with Twin environment."""

    def test_train_episode_with_twin(self, small_twin):
        env = TwinBackedRoutingEnv(small_twin)
        agent = PPOAgent(state_dim=49, action_dim=8)

        metrics = train_episode(agent, env, max_steps=20)

        assert "total_reward" in metrics
        assert "steps" in metrics

    def test_agent_learns_from_twin(self, medium_twin):
        env = TwinBackedRoutingEnv(medium_twin)
        agent = PPOAgent(state_dim=49, action_dim=8)

        # Train for a few episodes
        rewards = []
        for _ in range(10):
            metrics = train_episode(agent, env, max_steps=15)
            rewards.append(metrics["total_reward"])

            if len(agent.buffer) >= 20:
                agent.update()

        # Agent should have accumulated experience
        assert agent.episodes_completed == 10


# ==================== TwinMetricsCollector Tests ====================


class TestTwinMetricsCollector:
    """Tests for metrics collection."""

    def test_record_training(self):
        collector = TwinMetricsCollector()

        collector.record_training("node-1", 1, 10.5, 0.5, 0.3, 0.1)

        assert len(collector.training_metrics) == 1

    def test_record_aggregation(self):
        collector = TwinMetricsCollector()

        collector.record_aggregation(1, 5, "fedavg", True, 150.0)

        assert len(collector.aggregation_metrics) == 1

    def test_summary(self):
        collector = TwinMetricsCollector()

        collector.record_training("n1", 1, 10.0, 0.5, 0.3, 0.1)
        collector.record_training("n2", 1, 12.0, 0.4, 0.2, 0.15)
        collector.record_aggregation(1, 2, "fedavg", True, 100.0)

        summary = collector.get_summary()

        assert summary["training"]["total_records"] == 2
        assert summary["training"]["avg_reward"] == 11.0
        assert summary["aggregation"]["success_rate"] == 1.0


# ==================== FederatedTrainingOrchestrator Tests ====================


class TestFederatedTrainingOrchestrator:
    """Tests for full orchestrated training."""

    def test_creation(self, small_twin):
        config = TrainingConfig(min_participants=2, episodes_per_round=2)
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        assert len(orchestrator.agents) == 4
        assert len(orchestrator.envs) == 4

    def test_single_training_round(self, small_twin):
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=2,
            enable_dp=False,
            enable_blockchain=False,
        )
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        result = orchestrator.train_round()

        assert result["round"] == 1
        assert result["participants"] >= 2
        assert result["success"]

    def test_training_with_dp(self, small_twin):
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=2,
            enable_dp=True,
            target_epsilon=1.0,
            enable_blockchain=False,
        )
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        result = orchestrator.train_round()

        assert result["success"]
        assert orchestrator.dp.budget.epsilon > 0

    def test_training_with_blockchain(self, small_twin):
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=2,
            enable_dp=False,
            enable_blockchain=True,
        )
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        orchestrator.train_round()

        stats = orchestrator.blockchain.get_stats()
        assert stats["model_updates"] == 1

    def test_multi_round_training(self, medium_twin):
        config = TrainingConfig(
            min_participants=3,
            episodes_per_round=2,
            enable_dp=True,
            enable_blockchain=True,
        )
        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        history = orchestrator.train(num_rounds=3)

        assert len(history) == 3
        assert orchestrator.current_round == 3

    def test_training_summary(self, small_twin):
        config = TrainingConfig(min_participants=2, episodes_per_round=2)
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)
        orchestrator.train_round()

        summary = orchestrator.get_training_summary()

        assert summary["total_rounds"] == 1
        assert summary["num_agents"] == 4
        assert "metrics" in summary

    def test_chaos_injection(self, medium_twin):
        config = TrainingConfig(min_participants=2)
        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        result = orchestrator.inject_chaos("node_failure", "node-1")

        assert result["success"]
        assert medium_twin.nodes["node-1"].state == NodeState.FAILED

    def test_training_with_failed_node(self, medium_twin):
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=2,
            enable_dp=False,
            enable_blockchain=False,
        )
        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        # Inject failure
        orchestrator.inject_chaos("node_failure", "node-0")

        # Training should still work with remaining nodes
        result = orchestrator.train_round()

        assert result["success"]
        # Should have fewer participants (node-0 excluded)
        assert result["participants"] < 6

    def test_routing_evaluation(self, small_twin):
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=3,
            enable_dp=False,
            enable_blockchain=False,
        )
        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        # Train a bit
        orchestrator.train(num_rounds=2)

        # Evaluate
        eval_result = orchestrator.evaluate_routing(num_episodes=5)

        assert "success_rate" in eval_result
        assert "avg_reward" in eval_result
        assert eval_result["episodes"] == 5


# ==================== End-to-End Integration Tests ====================


class TestEndToEndIntegration:
    """Full end-to-end integration tests."""

    def test_complete_fl_pipeline(self, medium_twin):
        """Test complete FL pipeline with all components."""
        config = TrainingConfig(
            min_participants=3,
            episodes_per_round=3,
            enable_dp=True,
            target_epsilon=2.0,
            enable_blockchain=True,
            aggregation_method="fedavg",
        )

        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        # Run training
        history = orchestrator.train(num_rounds=5)

        # Verify training completed
        assert len(history) == 5
        assert all(r["success"] for r in history)

        # Verify blockchain
        bc_stats = orchestrator.blockchain.get_stats()
        assert bc_stats["model_updates"] == 5

        # Verify chain integrity
        is_valid, errors = orchestrator.blockchain.verify_chain()
        assert is_valid

        # Verify privacy
        dp_stats = orchestrator.dp.get_stats()
        assert dp_stats["budget"]["epsilon"] > 0

    def test_resilience_to_failures(self, medium_twin):
        """Test training resilience to node failures."""
        config = TrainingConfig(
            min_participants=2,
            episodes_per_round=2,
            enable_dp=False,
            enable_blockchain=True,
        )

        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        # Train round 1
        r1 = orchestrator.train_round()
        assert r1["success"]

        # Inject failure
        orchestrator.inject_chaos("node_failure", "node-2")

        # Train round 2 - should still work
        r2 = orchestrator.train_round()
        assert r2["success"]
        assert r2["participants"] < r1["participants"]

        # Recover and train round 3
        medium_twin.nodes["node-2"].state = NodeState.HEALTHY
        r3 = orchestrator.train_round()
        assert r3["success"]

    def test_model_rollback(self, small_twin):
        """Test blockchain rollback functionality."""
        config = TrainingConfig(
            min_participants=2, episodes_per_round=2, enable_blockchain=True
        )

        orchestrator = FederatedTrainingOrchestrator(small_twin, config)

        # Train 3 rounds
        orchestrator.train(num_rounds=3)

        # Get weights from round 1
        v1_weights = orchestrator.blockchain.get_model_weights(version=1)

        # Rollback to round 1
        orchestrator.blockchain.add_rollback(1, "Test rollback")

        # Verify rollback
        latest = orchestrator.blockchain.get_latest_weights()
        assert latest == v1_weights


# ==================== Performance Tests ====================


class TestPerformance:
    """Performance-related tests."""

    def test_training_performance(self, medium_twin):
        """Verify training completes in reasonable time."""
        import time

        config = TrainingConfig(
            min_participants=3,
            episodes_per_round=5,
            enable_dp=True,
            enable_blockchain=True,
        )

        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        start = time.time()
        orchestrator.train(num_rounds=3)
        duration = time.time() - start

        # Should complete 3 rounds in under 30 seconds
        assert duration < 30.0

    def test_memory_efficiency(self, medium_twin):
        """Test that training doesn't leak memory."""
        import gc

        config = TrainingConfig(min_participants=3, episodes_per_round=3)

        orchestrator = FederatedTrainingOrchestrator(medium_twin, config)

        # Run multiple rounds
        for _ in range(5):
            orchestrator.train_round()

        # Force garbage collection
        gc.collect()

        # Check buffer sizes are reasonable
        for agent in orchestrator.agents.values():
            assert len(agent.buffer) == 0  # Should be cleared after update


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
