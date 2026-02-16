"""
Tests for Model Synchronization.

Tests version control, conflict resolution, and rollback.
"""

from typing import Dict
from unittest.mock import Mock

import pytest

try:
    from src.federated_learning.model_sync import (ModelSynchronizer,
                                                   ModelSyncState,
                                                   ModelVersion)
    from src.federated_learning.protocol import GlobalModel, ModelWeights

    MODEL_SYNC_AVAILABLE = True
except ImportError:
    MODEL_SYNC_AVAILABLE = False
    ModelSynchronizer = None
    ModelVersion = None


@pytest.mark.skipif(
    not MODEL_SYNC_AVAILABLE, reason="Model synchronization not available"
)
class TestModelSynchronizer:
    """Tests for ModelSynchronizer"""

    def test_receive_global_model(self):
        """Test receiving global model"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Create global model
        weights = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        global_model = GlobalModel(
            version=1, round_number=1, weights=weights, num_contributors=3
        )

        # Receive model
        success = synchronizer.receive_global_model(global_model, "coordinator")

        assert success == True
        assert synchronizer.get_current_model() == global_model
        assert synchronizer.get_model_version() == 1

    def test_receive_older_model(self):
        """Test receiving older model version"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Receive first model
        weights1 = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        model1 = GlobalModel(version=2, round_number=1, weights=weights1)
        synchronizer.receive_global_model(model1, "coordinator")

        # Try to receive older model
        weights2 = ModelWeights(layer_weights={"layer1": [3.0, 4.0]})
        model2 = GlobalModel(version=1, round_number=1, weights=weights2)
        success = synchronizer.receive_global_model(model2, "coordinator")

        # Should reject older model
        assert success == False
        assert synchronizer.get_model_version() == 2

    def test_model_history(self):
        """Test model history tracking"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Receive multiple models
        for version in range(1, 6):
            weights = ModelWeights(layer_weights={"layer1": [float(version), 2.0]})
            model = GlobalModel(version=version, round_number=1, weights=weights)
            synchronizer.receive_global_model(model, "coordinator")

        # History should contain previous models
        assert len(synchronizer.model_history) == 4  # Versions 1-4 (current is 5)
        assert synchronizer.get_model_version() == 5

    def test_conflict_detection(self):
        """Test conflict detection"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Create two models with different versions
        weights1 = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        local_model = GlobalModel(version=1, round_number=1, weights=weights1)

        weights2 = ModelWeights(layer_weights={"layer1": [3.0, 4.0]})
        global_model = GlobalModel(version=2, round_number=1, weights=weights2)

        # Check for conflicts
        conflicts = synchronizer.check_for_conflicts(local_model, global_model)

        # Should detect version mismatch
        assert len(conflicts) > 0
        assert any(c["type"] == "version_mismatch" for c in conflicts)

    def test_conflict_resolution(self):
        """Test conflict resolution"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Create conflicts
        conflicts = [
            {"type": "version_mismatch", "severity": "high"},
            {"type": "weight_hash_mismatch", "severity": "critical"},
        ]

        # Resolve with prefer_global strategy
        success = synchronizer.resolve_conflicts(conflicts, strategy="prefer_global")

        assert success == True
        assert len(synchronizer.sync_state.conflicts) == 2

    def test_rollback(self):
        """Test model rollback"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Receive multiple models
        for version in range(1, 4):
            weights = ModelWeights(layer_weights={"layer1": [float(version), 2.0]})
            model = GlobalModel(version=version, round_number=1, weights=weights)
            synchronizer.receive_global_model(model, "coordinator")

        # Rollback to version 2
        success = synchronizer.rollback(target_version=2)

        assert success == True
        assert synchronizer.get_model_version() == 2

    def test_rollback_invalid_version(self):
        """Test rollback to invalid version"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Receive model
        weights = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        model = GlobalModel(version=3, round_number=1, weights=weights)
        synchronizer.receive_global_model(model, "coordinator")

        # Try to rollback to non-existent version
        success = synchronizer.rollback(target_version=1)

        assert success == False
        assert synchronizer.get_model_version() == 3

    def test_sync_status(self):
        """Test getting sync status"""
        synchronizer = ModelSynchronizer(node_id="node-1")

        # Receive model
        weights = ModelWeights(layer_weights={"layer1": [1.0, 2.0]})
        model = GlobalModel(version=1, round_number=1, weights=weights)
        synchronizer.receive_global_model(model, "coordinator")

        # Get status
        status = synchronizer.get_sync_status()

        assert status["node_id"] == "node-1"
        assert status["current_version"] == 1
        assert status["sync_status"] == ModelVersion.ACTIVE.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
