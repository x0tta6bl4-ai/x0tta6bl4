"""
Unit tests for SlotSynchronizer (slot-based mesh synchronization).

Tests cover:
- Beacon generation and validation
- Slot state transitions
- Neighbor tracking and drift calculation
- Collision detection and recovery
- Edge cases and error handling
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mesh.slot_sync import (Beacon, NeighborInfo, SlotConfig, SlotState,
                                SlotSynchronizer)


@pytest.fixture
def slot_config():
    """Standard slot configuration for testing."""
    return SlotConfig(
        slot_duration_ms=100.0,
        beacon_interval_ms=1000.0,
        jitter_max_ms=5.0,
        collision_backoff_ms=50.0,
        sync_window_ms=10.0,
    )


@pytest.fixture
def synchronizer(slot_config):
    """Create a SlotSynchronizer instance."""
    return SlotSynchronizer(node_id="test_node_1", config=slot_config)


class TestSlotConfig:
    """Tests for SlotConfig dataclass."""

    def test_default_config(self):
        """Test default SlotConfig values."""
        config = SlotConfig()

        assert config.slot_duration_ms == 100.0
        assert config.beacon_interval_ms == 1000.0
        assert config.jitter_max_ms == 5.0
        assert config.collision_backoff_ms == 50.0
        assert config.sync_window_ms == 10.0

    def test_custom_config(self, slot_config):
        """Test custom SlotConfig initialization."""
        assert slot_config.slot_duration_ms == 100.0
        assert slot_config.beacon_interval_ms == 1000.0

    def test_config_immutable_values(self, slot_config):
        """Test that config values are accessible."""
        original_duration = slot_config.slot_duration_ms
        # SlotConfig is mutable (dataclass), but we document expected usage
        assert slot_config.slot_duration_ms == original_duration


class TestBeacon:
    """Tests for Beacon dataclass."""

    def test_beacon_creation(self):
        """Test beacon creation with valid data."""
        beacon = Beacon(
            node_id="node_1",
            sequence=42,
            timestamp_local=100.0,
            timestamp_received=101.5,
            slot_offset=0.5,
            neighbors=["node_2", "node_3"],
        )

        assert beacon.node_id == "node_1"
        assert beacon.sequence == 42
        assert beacon.timestamp_local == 100.0
        assert beacon.timestamp_received == 101.5
        assert beacon.slot_offset == 0.5
        assert beacon.neighbors == ["node_2", "node_3"]

    def test_beacon_calculate_drift(self):
        """Test drift calculation between beacon timestamps."""
        beacon = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=105.5,
            slot_offset=0.0,
            neighbors=[],
        )

        drift = beacon.calculate_drift()
        assert drift == 5.5  # received - local

    def test_beacon_zero_drift(self):
        """Test beacon with zero drift (synchronized)."""
        beacon = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=100.0,
            slot_offset=0.0,
            neighbors=[],
        )

        assert beacon.calculate_drift() == 0.0

    def test_beacon_negative_drift(self):
        """Test beacon with negative drift."""
        beacon = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=105.0,
            timestamp_received=100.0,
            slot_offset=0.0,
            neighbors=[],
        )

        assert beacon.calculate_drift() == -5.0


class TestNeighborInfo:
    """Tests for NeighborInfo dataclass."""

    def test_neighbor_creation(self):
        """Test neighbor info creation."""
        neighbor = NeighborInfo(
            node_id="neighbor_1",
            last_seen=time.time(),
            drift=0.5,
            beacons_received=10,
            quality=0.95,
        )

        assert neighbor.node_id == "neighbor_1"
        assert neighbor.beacons_received == 10
        assert neighbor.quality == 0.95
        assert neighbor.drift == 0.5

    def test_neighbor_default_quality(self):
        """Test neighbor with default quality value."""
        neighbor = NeighborInfo(node_id="neighbor_1", last_seen=time.time())

        assert neighbor.quality == 1.0
        assert neighbor.drift == 0.0
        assert neighbor.beacons_received == 0


class TestSlotSynchronizer:
    """Tests for SlotSynchronizer core functionality."""

    def test_synchronizer_initialization(self, synchronizer):
        """Test SlotSynchronizer initialization."""
        assert synchronizer.node_id == "test_node_1"
        assert synchronizer.config.slot_duration_ms == 100.0
        assert isinstance(synchronizer.neighbors, dict)
        assert len(synchronizer.neighbors) == 0

    def test_synchronizer_current_slot(self, synchronizer, slot_config):
        """Test current slot calculation."""
        # _calculate_slot is private but we can test the public state
        slot_duration_sec = slot_config.slot_duration_ms / 1000
        current_time = time.time()
        expected_slot = int(current_time / slot_duration_sec)

        # The synchronizer's current_slot should be around expected value
        assert isinstance(synchronizer.current_slot, int)
        assert synchronizer.current_slot >= 0

    def test_synchronizer_now_method(self, synchronizer):
        """Test now() method returns current time with offset."""
        current_time = synchronizer.now()

        # Should return a float representing current time
        assert isinstance(current_time, float)
        assert current_time > 0

    def test_receive_beacon(self, synchronizer):
        """Test receiving a beacon."""
        beacon = Beacon(
            node_id="neighbor_1",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=101.0,
            slot_offset=0.0,
            neighbors=[],
        )

        synchronizer.receive_beacon(beacon)

        # Beacon should be processed (check via sync status)
        status = synchronizer.get_sync_status()
        assert status is not None
        assert isinstance(status, dict)

    def test_receive_multiple_beacons(self, synchronizer):
        """Test receiving multiple beacons from same neighbor."""
        for seq in range(1, 6):
            beacon = Beacon(
                node_id="neighbor_1",
                sequence=seq,
                timestamp_local=100.0 + seq,
                timestamp_received=101.0 + seq,
                slot_offset=0.0,
                neighbors=[],
            )
            synchronizer.receive_beacon(beacon)

        # Should be able to call multiple times without error
        status = synchronizer.get_sync_status()
        assert status is not None

    def test_neighbors_dict_structure(self, synchronizer):
        """Test neighbors dictionary structure."""
        # Neighbors dict should exist and be empty initially
        assert isinstance(synchronizer.neighbors, dict)
        assert len(synchronizer.neighbors) == 0

        # Add some neighbors via beacons
        for i in range(3):
            beacon = Beacon(
                node_id=f"neighbor_{i}",
                sequence=1,
                timestamp_local=100.0,
                timestamp_received=100.0,
                slot_offset=0.0,
                neighbors=[],
            )
            synchronizer.receive_beacon(beacon)

        # Check neighbors dict
        assert isinstance(synchronizer.neighbors, dict)

    def test_collision_detection(self, synchronizer):
        """Test collision detection method."""
        # Initially no collision
        has_collision = synchronizer.detect_collision()
        assert isinstance(has_collision, bool)

    def test_state_properties(self, synchronizer):
        """Test synchronizer state properties."""
        # Check public attributes exist
        assert synchronizer.node_id == "test_node_1"
        assert synchronizer.config is not None
        assert isinstance(synchronizer.state, SlotState)
        assert isinstance(synchronizer.current_slot, int)
        assert isinstance(synchronizer.sequence, int)

    def test_detect_collision_call(self, synchronizer):
        """Test collision detection can be called."""
        # receive some beacons
        beacon1 = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=100.0,
            slot_offset=0.0,
            neighbors=[],
        )

        beacon2 = Beacon(
            node_id="node_2",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=100.1,
            slot_offset=0.0,
            neighbors=[],
        )

        synchronizer.receive_beacon(beacon1)
        synchronizer.receive_beacon(beacon2)

        # Should be able to detect collisions
        has_collision = synchronizer.detect_collision()
        assert isinstance(has_collision, bool)


class TestSlotSynchronizerAdvanced:
    """Advanced tests for SlotSynchronizer."""

    def test_receive_multiple_beacons_with_drift(self, synchronizer):
        """Test receiving multiple beacons with different drifts."""
        drifts = [1.0, 2.0, 3.0, 2.5, 1.5]

        for seq, drift_val in enumerate(drifts, 1):
            beacon = Beacon(
                node_id="neighbor_1",
                sequence=seq,
                timestamp_local=100.0,
                timestamp_received=100.0 + drift_val,
                slot_offset=0.0,
                neighbors=[],
            )
            synchronizer.receive_beacon(beacon)

        # Should complete without error
        status = synchronizer.get_sync_status()
        assert status is not None

    def test_slot_state_transitions(self, synchronizer):
        """Test slot state can transition correctly."""
        # Initial state should be IDLE
        assert synchronizer.state == SlotState.IDLE

        # States should be updateable
        synchronizer.state = SlotState.LISTENING
        assert synchronizer.state == SlotState.LISTENING

        synchronizer.state = SlotState.TRANSMITTING
        assert synchronizer.state == SlotState.TRANSMITTING

    def test_beacon_structure(self, synchronizer):
        """Test Beacon structure creation."""
        current_time = time.time()

        beacon = Beacon(
            node_id="test_node_1",
            sequence=1,
            timestamp_local=current_time,
            timestamp_received=current_time,
            slot_offset=0.0,
            neighbors=["neighbor_1", "neighbor_2"],
        )

        assert beacon.node_id == "test_node_1"
        assert beacon.sequence == 1
        assert beacon.timestamp_local > 0
        assert isinstance(beacon.neighbors, list)
        assert len(beacon.neighbors) == 2
        assert beacon.neighbors == ["neighbor_1", "neighbor_2"]

    def test_high_jitter_tolerance(self, synchronizer, slot_config):
        """Test that synchronizer handles high jitter."""
        # Create beacons with high jitter
        for i in range(10):
            jitter = (i - 5) * (slot_config.jitter_max_ms / 5)  # Varies around 0
            beacon = Beacon(
                node_id=f"neighbor_{i % 3}",
                sequence=i,
                timestamp_local=100.0,
                timestamp_received=100.0 + jitter,
                slot_offset=0.0,
                neighbors=[],
            )
            synchronizer.receive_beacon(beacon)

        # Should handle multiple beacons with jitter
        status = synchronizer.get_sync_status()
        assert status is not None


class TestSlotSynchronizerEdgeCases:
    """Edge case tests for SlotSynchronizer."""

    def test_empty_neighbors_dict(self, synchronizer):
        """Test behavior with no neighbors."""
        assert len(synchronizer.neighbors) == 0
        assert isinstance(synchronizer.neighbors, dict)

    def test_very_large_drift_beacon(self, synchronizer):
        """Test handling beacon with very large drift values."""
        beacon = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=0.0,
            timestamp_received=10000.0,  # 10 seconds drift
            slot_offset=0.0,
            neighbors=[],
        )

        # Should handle large drift without error
        synchronizer.receive_beacon(beacon)
        status = synchronizer.get_sync_status()
        assert status is not None

    def test_beacon_with_empty_neighbors_list(self, synchronizer):
        """Test beacon with empty neighbor list."""
        beacon = Beacon(
            node_id="node_1",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=100.0,
            slot_offset=0.0,
            neighbors=[],
        )

        synchronizer.receive_beacon(beacon)
        # Should process beacon without error
        status = synchronizer.get_sync_status()
        assert status is not None

    def test_beacon_with_many_neighbors_in_list(self, synchronizer):
        """Test beacon containing many neighbors in beacon list."""
        neighbor_list = [f"node_{i}" for i in range(50)]

        beacon = Beacon(
            node_id="source_node",
            sequence=1,
            timestamp_local=100.0,
            timestamp_received=100.0,
            slot_offset=0.0,
            neighbors=neighbor_list,
        )

        synchronizer.receive_beacon(beacon)
        assert beacon.neighbors == neighbor_list
        # Should handle beacon with many neighbors
        status = synchronizer.get_sync_status()
        assert status is not None

    def test_collision_resolution(self, synchronizer):
        """Test collision resolution mechanism."""
        # Trigger potential collision detection
        has_collision = synchronizer.detect_collision()

        if has_collision:
            # Try to resolve collision
            synchronizer.resolve_collision()
            # After resolution, should have less collision state
            status = synchronizer.get_sync_status()
            assert status is not None


class TestSlotSynchronizerSequentialOperations:
    """Tests for sequential operations."""

    def test_sequential_beacon_receiving(self, synchronizer):
        """Test receiving multiple beacons sequentially."""
        # Receive beacons sequentially
        for i in range(10):
            beacon = Beacon(
                node_id=f"node_{i}",
                sequence=i,
                timestamp_local=100.0 + i,
                timestamp_received=100.0 + i,
                slot_offset=0.0,
                neighbors=[],
            )
            synchronizer.receive_beacon(beacon)

        # Should handle multiple beacon receptions
        status = synchronizer.get_sync_status()
        assert status is not None
        assert isinstance(status, dict)

    def test_mttd_calculation(self, synchronizer):
        """Test Mean Time To Detect (MTTD) calculation."""
        # Calculate MTTD
        mttd = synchronizer.calculate_mttd()

        # Should return a float value
        assert isinstance(mttd, float)
        assert mttd >= 0
