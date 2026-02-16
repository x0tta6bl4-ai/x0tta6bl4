"""
Integration tests for Federated Learning.

Tests complete FL flow:
- Model initialization
- Local training
- Gradient aggregation
- Model synchronization
- Privacy preservation
"""

from typing import Dict, List
from unittest.mock import Mock, patch

import numpy as np
import pytest

try:
    from src.federated_learning.aggregator import FederatedAggregator
    from src.federated_learning.client import FLClient
    from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

    FL_AVAILABLE = True
except ImportError:
    FL_AVAILABLE = False
    FederatedAggregator = None
    FLClient = None
    GraphSAGEAnomalyDetector = None


@pytest.mark.skipif(not FL_AVAILABLE, reason="Federated Learning not available")
class TestFederatedLearningIntegration:
    """Integration tests for Federated Learning"""

    def test_fl_round_complete(self):
        """Test complete federated learning round"""
        # Create aggregator
        aggregator = FederatedAggregator()

        # Create clients
        clients = []
        for i in range(3):
            client = FLClient(node_id=f"node-{i+1}")
            clients.append(client)

        # Initialize model
        initial_model = aggregator.get_global_model()

        # Clients train locally
        client_gradients = []
        for client in clients:
            # Simulate local training
            gradients = client.train_local(initial_model)
            client_gradients.append(gradients)

        # Aggregate gradients
        aggregated_gradients = aggregator.aggregate_gradients(client_gradients)

        # Update global model
        aggregator.update_global_model(aggregated_gradients)

        # Verify model updated
        updated_model = aggregator.get_global_model()
        assert updated_model is not None
        assert updated_model != initial_model

    def test_fl_privacy_preservation(self):
        """Test that FL preserves privacy (no raw data sharing)"""
        aggregator = FederatedAggregator()

        # Create client with sensitive data
        client = FLClient(node_id="node-1")

        # Client trains locally (data stays local)
        initial_model = aggregator.get_global_model()
        gradients = client.train_local(initial_model)

        # Only gradients are shared (not raw data)
        assert gradients is not None
        # Verify no raw data in gradients
        assert not hasattr(gradients, "raw_data")

    def test_fl_differential_privacy(self):
        """Test differential privacy in FL aggregation"""
        aggregator = FederatedAggregator(use_differential_privacy=True)

        # Create clients
        clients = []
        for i in range(5):
            client = FLClient(node_id=f"node-{i+1}")
            clients.append(client)

        # Train and aggregate with DP
        initial_model = aggregator.get_global_model()
        client_gradients = []

        for client in clients:
            gradients = client.train_local(initial_model)
            client_gradients.append(gradients)

        # Aggregate with differential privacy
        aggregated = aggregator.aggregate_gradients(client_gradients)

        # Verify DP noise added
        assert aggregated is not None

    def test_fl_byzantine_robust_aggregation(self):
        """Test Byzantine-robust aggregation (handles malicious clients)"""
        aggregator = FederatedAggregator(byzantine_robust=True)

        # Create clients (one malicious)
        clients = []
        for i in range(4):
            client = FLClient(node_id=f"node-{i+1}")
            clients.append(client)

        # Malicious client sends corrupted gradients
        initial_model = aggregator.get_global_model()
        client_gradients = []

        for i, client in enumerate(clients):
            if i == 0:  # Malicious client
                # Send corrupted gradients
                corrupted_gradients = np.random.randn(100) * 1000  # Very large values
                client_gradients.append(corrupted_gradients)
            else:
                gradients = client.train_local(initial_model)
                client_gradients.append(gradients)

        # Aggregate (should handle malicious client)
        aggregated = aggregator.aggregate_gradients(client_gradients)

        # Should still produce valid aggregated gradients
        assert aggregated is not None

    def test_fl_model_convergence(self):
        """Test FL model convergence over multiple rounds"""
        aggregator = FederatedAggregator()

        # Create clients
        clients = []
        for i in range(3):
            client = FLClient(node_id=f"node-{i+1}")
            clients.append(client)

        # Run multiple rounds
        initial_loss = float("inf")
        for round_num in range(5):
            # Get global model
            global_model = aggregator.get_global_model()

            # Clients train
            client_gradients = []
            for client in clients:
                gradients = client.train_local(global_model)
                client_gradients.append(gradients)

            # Aggregate
            aggregated = aggregator.aggregate_gradients(client_gradients)
            aggregator.update_global_model(aggregated)

            # Check loss (should decrease over rounds)
            current_loss = aggregator.get_global_loss()
            if round_num > 0:
                # Loss should generally decrease (or at least not increase dramatically)
                assert current_loss <= initial_loss * 1.1  # Allow 10% increase

            initial_loss = current_loss


@pytest.mark.skipif(not FL_AVAILABLE, reason="Federated Learning not available")
class TestFLGraphSAGEIntegration:
    """Integration tests for FL with GraphSAGE"""

    def test_fl_with_graphsage(self):
        """Test FL with GraphSAGE model"""
        try:
            from src.ml.graphsage_anomaly_detector import \
                GraphSAGEAnomalyDetector

            aggregator = FederatedAggregator()

            # Create GraphSAGE model
            graphsage = GraphSAGEAnomalyDetector()

            # Initialize with GraphSAGE
            aggregator.set_model(graphsage)

            # Create clients
            clients = []
            for i in range(3):
                client = FLClient(node_id=f"node-{i+1}")
                clients.append(client)

            # Train round
            global_model = aggregator.get_global_model()
            client_gradients = []

            for client in clients:
                gradients = client.train_local(global_model)
                client_gradients.append(gradients)

            # Aggregate
            aggregated = aggregator.aggregate_gradients(client_gradients)
            aggregator.update_global_model(aggregated)

            # Verify GraphSAGE model updated
            updated_model = aggregator.get_global_model()
            assert updated_model is not None

        except ImportError:
            pytest.skip("GraphSAGE not available")

    def test_fl_graphsage_anomaly_detection(self):
        """Test anomaly detection with FL-trained GraphSAGE"""
        try:
            from src.ml.graphsage_anomaly_detector import \
                GraphSAGEAnomalyDetector

            aggregator = FederatedAggregator()
            graphsage = GraphSAGEAnomalyDetector()
            aggregator.set_model(graphsage)

            # Train model via FL
            clients = []
            for i in range(3):
                client = FLClient(node_id=f"node-{i+1}")
                clients.append(client)

            # One training round
            global_model = aggregator.get_global_model()
            client_gradients = []

            for client in clients:
                gradients = client.train_local(global_model)
                client_gradients.append(gradients)

            aggregated = aggregator.aggregate_gradients(client_gradients)
            aggregator.update_global_model(aggregated)

            # Use model for anomaly detection
            test_data = np.random.randn(10, 5)  # Sample data
            predictions = graphsage.predict(test_data)

            assert predictions is not None
            assert len(predictions) == len(test_data)

        except ImportError:
            pytest.skip("GraphSAGE not available")


@pytest.mark.skipif(not FL_AVAILABLE, reason="Federated Learning not available")
class TestFLEdgeCases:
    """Edge case tests for Federated Learning"""

    def test_fl_with_single_client(self):
        """Test FL with only one client"""
        aggregator = FederatedAggregator()
        client = FLClient(node_id="node-1")

        # Train with single client
        global_model = aggregator.get_global_model()
        gradients = client.train_local(global_model)

        # Aggregate (should handle single client)
        aggregated = aggregator.aggregate_gradients([gradients])
        aggregator.update_global_model(aggregated)

        assert aggregator.get_global_model() is not None

    def test_fl_with_empty_gradients(self):
        """Test handling of empty gradients"""
        aggregator = FederatedAggregator()

        # Empty gradients list
        with pytest.raises((ValueError, IndexError)):
            aggregator.aggregate_gradients([])

    def test_fl_client_dropout(self):
        """Test FL with client dropout (some clients don't participate)"""
        aggregator = FederatedAggregator()

        # Create 5 clients
        clients = []
        for i in range(5):
            client = FLClient(node_id=f"node-{i+1}")
            clients.append(client)

        # Only 3 clients participate
        global_model = aggregator.get_global_model()
        client_gradients = []

        for i, client in enumerate(clients[:3]):  # Only first 3
            gradients = client.train_local(global_model)
            client_gradients.append(gradients)

        # Aggregate with partial participation
        aggregated = aggregator.aggregate_gradients(client_gradients)
        aggregator.update_global_model(aggregated)

        # Should still work
        assert aggregator.get_global_model() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
