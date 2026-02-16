"""
Tests for Differential Privacy and PBFT Consensus.
"""

import math
import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.federated_learning.consensus import (ConsensusMessage,
                                              ConsensusNetwork, ConsensusPhase,
                                              ConsensusProposal, MessageType,
                                              PBFTConfig, PBFTConsensus)
from src.federated_learning.privacy import (DifferentialPrivacy, DPConfig,
                                            GaussianNoiseGenerator,
                                            GradientClipper, PrivacyBudget,
                                            SecureAggregation,
                                            compute_dp_sgd_privacy)

# ==================== Privacy Tests ====================


class TestPrivacyBudget:
    """Tests for PrivacyBudget tracking."""

    def test_creation(self):
        budget = PrivacyBudget()
        assert budget.epsilon == 0.0
        assert budget.rounds_participated == 0

    def test_add_round(self):
        budget = PrivacyBudget()
        budget.add_round(epsilon_spent=0.1, noise_scale=1.0)

        assert budget.epsilon == 0.1
        assert budget.rounds_participated == 1

    def test_remaining(self):
        budget = PrivacyBudget(epsilon=0.5)
        remaining = budget.remaining(max_epsilon=1.0)

        assert remaining == 0.5

    def test_exhausted(self):
        budget = PrivacyBudget(epsilon=1.0)

        assert budget.is_exhausted(max_epsilon=1.0)
        assert not budget.is_exhausted(max_epsilon=2.0)


class TestGradientClipper:
    """Tests for gradient clipping."""

    def test_no_clipping_needed(self):
        clipper = GradientClipper(max_norm=10.0)
        gradients = [1.0, 2.0, 2.0]  # Norm = 3

        clipped, norm = clipper.clip(gradients)

        assert clipped == gradients
        assert norm == 3.0

    def test_clipping_applied(self):
        clipper = GradientClipper(max_norm=1.0)
        gradients = [3.0, 4.0]  # Norm = 5

        clipped, norm = clipper.clip(gradients)

        assert norm == 5.0
        # Clipped norm should be 1.0
        clipped_norm = math.sqrt(sum(g * g for g in clipped))
        assert abs(clipped_norm - 1.0) < 0.001

    def test_clip_rate(self):
        clipper = GradientClipper(max_norm=1.0)

        # One clipped, one not
        clipper.clip([0.5])  # Norm < 1
        clipper.clip([3.0, 4.0])  # Norm > 1

        assert clipper.clip_rate == 0.5

    def test_batch_clip(self):
        clipper = GradientClipper(max_norm=1.0)
        batch = [[0.5], [3.0, 4.0], [0.3, 0.4]]

        clipped, norms = clipper.clip_batch(batch)

        assert len(clipped) == 3
        assert len(norms) == 3


class TestGaussianNoiseGenerator:
    """Tests for noise generation."""

    def test_generate_noise(self):
        gen = GaussianNoiseGenerator(seed=42)
        noise = gen.generate(size=100, scale=1.0)

        assert len(noise) == 100
        # Check distribution is roughly normal
        mean = sum(noise) / len(noise)
        assert abs(mean) < 0.5  # Should be close to 0

    def test_reproducibility(self):
        gen1 = GaussianNoiseGenerator(seed=42)
        gen2 = GaussianNoiseGenerator(seed=42)

        noise1 = gen1.generate(10, 1.0)
        noise2 = gen2.generate(10, 1.0)

        assert noise1 == noise2

    def test_calibrate_noise(self):
        gen = GaussianNoiseGenerator()

        sigma = gen.calibrate_noise(sensitivity=1.0, epsilon=1.0, delta=1e-5)

        assert sigma > 0
        # Higher epsilon = less noise needed
        sigma_higher_eps = gen.calibrate_noise(1.0, 2.0, 1e-5)
        assert sigma_higher_eps < sigma


class TestDifferentialPrivacy:
    """Tests for main DP engine."""

    def test_creation(self):
        config = DPConfig(target_epsilon=1.0)
        dp = DifferentialPrivacy(config)

        assert dp.can_continue_training()

    def test_privatize_gradients(self):
        config = DPConfig(target_epsilon=1.0, max_rounds=10)
        dp = DifferentialPrivacy(config)

        gradients = [1.0, 2.0, 3.0]
        privatized, metadata = dp.privatize_gradients(gradients, num_samples=100)

        assert len(privatized) == 3
        assert metadata["epsilon_spent"] > 0
        assert metadata["total_epsilon"] > 0

    def test_budget_tracking(self):
        config = DPConfig(target_epsilon=1.0, max_rounds=10)
        dp = DifferentialPrivacy(config)

        # Use some budget
        for _ in range(5):
            dp.privatize_gradients([1.0], num_samples=10)

        eps, delta = dp.get_privacy_spent()
        assert eps > 0
        assert eps < config.target_epsilon

    def test_budget_exhaustion(self):
        config = DPConfig(target_epsilon=0.1, max_rounds=2)
        dp = DifferentialPrivacy(config)

        # Exhaust budget
        for _ in range(3):
            dp.privatize_gradients([1.0], num_samples=10)

        assert not dp.can_continue_training()

    def test_gradient_clipping_in_privatize(self):
        config = DPConfig(max_grad_norm=1.0)
        dp = DifferentialPrivacy(config)

        large_gradients = [3.0, 4.0]  # Norm = 5
        _, metadata = dp.privatize_gradients(large_gradients)

        assert metadata["clipped"]
        assert metadata["original_norm"] == 5.0

    def test_get_stats(self):
        dp = DifferentialPrivacy()
        stats = dp.get_stats()

        assert "config" in stats
        assert "budget" in stats
        assert "can_continue" in stats


class TestSecureAggregation:
    """Tests for secure aggregation."""

    def test_mask_generation(self):
        sa = SecureAggregation(num_parties=3)

        mask, seeds = sa.generate_masks(party_id=0, vector_size=5)

        assert len(mask) == 5
        assert len(seeds) == 2  # Seeds for other 2 parties

    def test_masks_cancel_out(self):
        sa = SecureAggregation(num_parties=3)

        # Generate masks for all parties
        updates = [[1.0, 2.0, 3.0] for _ in range(3)]
        masked = []

        for party_id in range(3):
            masked.append(sa.mask_update(updates[party_id], party_id))

        # Aggregate
        aggregated = sa.aggregate_masked(masked)

        # Sum of original updates
        expected = [3.0, 6.0, 9.0]

        # Masks should cancel (approximately due to floating point)
        for a, e in zip(aggregated, expected):
            assert abs(a - e) < 0.001


class TestDPSGDPrivacy:
    """Tests for DP-SGD privacy computation."""

    def test_compute_privacy(self):
        epsilon = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=1.1, epochs=10, delta=1e-5
        )

        assert epsilon > 0

    def test_more_noise_less_epsilon(self):
        eps_low_noise = compute_dp_sgd_privacy(0.01, 1.0, 10)
        eps_high_noise = compute_dp_sgd_privacy(0.01, 2.0, 10)

        assert eps_high_noise < eps_low_noise


# ==================== Consensus Tests ====================


class TestConsensusProposal:
    """Tests for ConsensusProposal."""

    def test_creation(self):
        proposal = ConsensusProposal(
            proposal_id="p1", proposer="node-1", content={"model": "v1"}
        )

        assert proposal.proposal_id == "p1"
        assert proposal.digest != ""

    def test_digest_deterministic(self):
        p1 = ConsensusProposal("p1", "node-1", {"data": "test"})
        p2 = ConsensusProposal("p2", "node-2", {"data": "test"})

        assert p1.digest == p2.digest  # Same content = same digest


class TestConsensusMessage:
    """Tests for ConsensusMessage."""

    def test_creation(self):
        msg = ConsensusMessage(
            msg_type=MessageType.PREPARE,
            view=0,
            sequence=1,
            digest="abc123",
            sender="node-1",
        )

        assert msg.view == 0
        assert msg.sequence == 1

    def test_to_dict_from_dict(self):
        msg = ConsensusMessage(
            msg_type=MessageType.COMMIT,
            view=1,
            sequence=5,
            digest="xyz",
            sender="node-2",
            payload={"data": "test"},
        )

        d = msg.to_dict()
        restored = ConsensusMessage.from_dict(d)

        assert restored.view == 1
        assert restored.sequence == 5
        assert restored.payload == {"data": "test"}


class TestPBFTConsensus:
    """Tests for PBFT consensus node."""

    def test_creation(self):
        nodes = ["node-1", "node-2", "node-3", "node-4"]
        pbft = PBFTConsensus("node-1", nodes, is_primary=True)

        assert pbft.n == 4
        assert pbft.f == 1
        assert pbft.quorum == 3
        assert pbft.is_primary

    def test_non_primary_cannot_propose(self):
        nodes = ["node-1", "node-2", "node-3", "node-4"]
        pbft = PBFTConsensus("node-2", nodes, is_primary=False)

        result = pbft.propose({"model": "v1"})

        assert result is None

    def test_primary_can_propose(self):
        nodes = ["node-1", "node-2", "node-3", "node-4"]
        pbft = PBFTConsensus("node-1", nodes, is_primary=True)

        proposal = pbft.propose({"model": "v1"})

        assert proposal is not None
        assert proposal.proposer == "node-1"

    def test_get_metrics(self):
        nodes = ["node-1", "node-2", "node-3", "node-4"]
        pbft = PBFTConsensus("node-1", nodes)

        metrics = pbft.get_metrics()

        assert "view" in metrics
        assert "sequence" in metrics
        assert "n" in metrics
        assert "f" in metrics


class TestConsensusNetwork:
    """Tests for simulated consensus network."""

    def test_creation(self):
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])

        assert len(network.nodes) == 4
        assert network.nodes["n1"].is_primary

    def test_proposal_starts(self):
        """Test that proposals are initiated correctly."""
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])

        proposal = network.propose({"model": "v1", "version": 1})

        assert proposal is not None
        assert proposal.content["version"] == 1

        # Primary should have proposal in progress
        primary = network.nodes["n1"]
        assert primary.sequence == 1

    def test_multiple_proposals_started(self):
        """Test multiple proposals can be initiated."""
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])

        p1 = network.propose({"update": 1})
        p2 = network.propose({"update": 2})
        p3 = network.propose({"update": 3})

        assert p1 is not None
        assert p2 is not None
        assert p3 is not None

        # Check sequence numbers
        primary = network.nodes["n1"]
        assert primary.sequence == 3

    def test_metrics(self):
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])
        network.propose({"test": True})

        metrics = network.get_all_metrics()

        assert "n1" in metrics
        assert metrics["n1"]["proposals_started"] == 1


class TestByzantineTolerance:
    """Tests for Byzantine fault tolerance."""

    def test_quorum_calculation(self):
        # n=4, f=1, quorum=3
        pbft4 = PBFTConsensus("n1", ["n1", "n2", "n3", "n4"])
        assert pbft4.f == 1
        assert pbft4.quorum == 3

        # n=7, f=2, quorum=5
        pbft7 = PBFTConsensus("n1", [f"n{i}" for i in range(7)])
        assert pbft7.f == 2
        assert pbft7.quorum == 5

        # n=10, f=3, quorum=7
        pbft10 = PBFTConsensus("n1", [f"n{i}" for i in range(10)])
        assert pbft10.f == 3
        assert pbft10.quorum == 7

    def test_consensus_with_minimum_nodes(self):
        # Minimum for f=1 is n=4
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])

        proposal = network.propose({"critical": True})

        # Verify proposal was created
        assert proposal is not None
        assert proposal.content["critical"] == True

        # Verify quorum requirements
        assert network.nodes["n1"].quorum == 3


class TestViewChange:
    """Tests for view change mechanism."""

    def test_start_view_change(self):
        nodes = ["n1", "n2", "n3", "n4"]
        pbft = PBFTConsensus("n1", nodes)

        initial_view = pbft.view

        # Start view change - the node broadcasts VIEW_CHANGE
        # Other nodes would increment their view_changes counter
        pbft.start_view_change()

        # Verify view change was initiated (message sent)
        metrics = pbft.get_metrics()
        assert metrics["messages_sent"] > 0

    def test_complete_view_change(self):
        nodes = ["n1", "n2", "n3", "n4"]
        pbft = PBFTConsensus("n1", nodes, is_primary=True)

        assert pbft.is_primary

        pbft.complete_view_change(new_view=1)

        assert pbft.view == 1
        # n2 should be new primary (view 1 % 4 = 1)
        assert not pbft.is_primary


# ==================== Integration Tests ====================


class TestDPWithFL:
    """Integration tests for DP with FL."""

    def test_dp_gradient_aggregation(self):
        """Test DP works with FL aggregation flow."""
        from src.federated_learning.aggregators import FedAvgAggregator
        from src.federated_learning.protocol import ModelUpdate, ModelWeights

        dp = DifferentialPrivacy(DPConfig(target_epsilon=1.0))

        # Create updates with DP
        updates = []
        for i in range(5):
            raw_weights = [1.0, 2.0, 3.0]
            private_weights, _ = dp.privatize_gradients(raw_weights, num_samples=100)

            update = ModelUpdate(
                node_id=f"node-{i}",
                round_number=1,
                weights=ModelWeights(layer_weights={"flat": private_weights}),
                num_samples=100,
            )
            updates.append(update)

        # Aggregate
        aggregator = FedAvgAggregator()
        result = aggregator.aggregate(updates)

        assert result.success


class TestConsensusWithFL:
    """Integration tests for consensus with FL."""

    def test_consensus_for_model_update(self):
        """Test PBFT consensus for FL model update agreement."""
        network = ConsensusNetwork(["n1", "n2", "n3", "n4"])

        # Propose model update
        model_update = {
            "round": 5,
            "version": 1,
            "weights_hash": "abc123def456",
            "contributors": ["node-1", "node-2", "node-3"],
        }

        proposal = network.propose(model_update)

        # Verify proposal was created and distributed
        assert proposal is not None
        assert proposal.content["round"] == 5
        assert proposal.content["weights_hash"] == "abc123def456"

        # Verify primary processed it
        primary_metrics = network.nodes["n1"].get_metrics()
        assert primary_metrics["proposals_started"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
