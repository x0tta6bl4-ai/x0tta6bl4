"""
Integration tests for Byzantine Protection.

Тестирует:
- Signed Gossip для control-plane сообщений
- Quorum Validation для критических событий
- Reputation scoring и quarantine
- Защиту от replay attacks
"""

import sys
import time
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from network.byzantine.mesh_byzantine_protection import \
        MeshByzantineProtection
    from network.byzantine.quorum_validation import (CriticalEventType,
                                                     QuorumValidator)
    from network.byzantine.signed_gossip import MessageType, SignedGossip

    LIBOQS_AVAILABLE = True
except ImportError as e:
    LIBOQS_AVAILABLE = False
    pytest.skip(f"liboqs not available: {e}", allow_module_level=True)


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestSignedGossip:
    """Tests for Signed Gossip."""

    def test_sign_and_verify_message(self):
        """Test signing and verifying messages."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")

        # Sign message
        message = gossip1.sign_message(
            MessageType.BEACON, {"neighbors": ["node-2", "node-3"]}
        )

        # Verify message
        is_valid, error = gossip2.verify_message(message)
        assert is_valid, f"Message verification failed: {error}"

    def test_replay_attack_prevention(self):
        """Test that replay attacks are prevented."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")

        # Sign message
        message = gossip1.sign_message(MessageType.BEACON, {"neighbors": ["node-2"]})

        # First verification should succeed
        is_valid, _ = gossip2.verify_message(message)
        assert is_valid

        # Second verification (replay) should fail
        is_valid, error = gossip2.verify_message(message)
        assert not is_valid
        assert "replay" in error.lower() or "nonce" in error.lower()

    def test_rate_limiting(self):
        """Test rate limiting."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")

        # Send many messages quickly
        for i in range(15):  # More than rate limit (10/sec)
            message = gossip1.sign_message(
                MessageType.BEACON, {"neighbors": ["node-2"], "seq": i}
            )

            is_valid, error = gossip2.verify_message(message)

            if i >= 10:
                # Should be rate limited
                assert not is_valid or "rate limit" in error.lower()

    def test_quarantine(self):
        """Test node quarantine after violations."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")

        # Send many invalid messages to trigger quarantine
        for i in range(20):
            message = gossip1.sign_message(
                MessageType.BEACON, {"neighbors": ["node-2"], "seq": i}
            )

            # Corrupt signature
            message.signature = b"invalid_signature"

            gossip2.verify_message(message)

        # Node should be quarantined
        assert gossip2.is_quarantined("node-1")

    def test_reputation_recovery(self):
        """Test reputation recovery after good behavior."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")

        # Send invalid message (penalize)
        message = gossip1.sign_message(MessageType.BEACON, {"neighbors": ["node-2"]})
        message.signature = b"invalid"
        gossip2.verify_message(message)

        initial_reputation = gossip2.get_reputation("node-1")
        assert initial_reputation < 1.0

        # Send many valid messages (recover)
        for i in range(10):
            message = gossip1.sign_message(
                MessageType.BEACON, {"neighbors": ["node-2"], "seq": i}
            )
            gossip2.verify_message(message)

        final_reputation = gossip2.get_reputation("node-1")
        assert final_reputation > initial_reputation


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestQuorumValidation:
    """Tests for Quorum Validation."""

    def test_quorum_calculation(self):
        """Test quorum size calculation."""
        # n=10, threshold=0.67, quorum=7
        validator = QuorumValidator("node-1", total_nodes=10, quorum_threshold=0.67)
        assert validator.quorum_size == 7

        # n=4, threshold=0.67, quorum=3
        validator = QuorumValidator("node-1", total_nodes=4, quorum_threshold=0.67)
        assert validator.quorum_size == 3

    def test_critical_event_validation(self):
        """Test critical event validation with quorum."""
        validator = QuorumValidator("node-1", total_nodes=10, quorum_threshold=0.67)

        # Report critical event
        event = validator.report_critical_event(
            CriticalEventType.NODE_FAILURE,
            target="node-5",
            evidence={"latency": float("inf"), "packet_loss": 1.0},
        )

        assert not validator.is_validated(event)

        # Add signatures until quorum (7 signatures needed, quorum_size=int(10*0.67)+1=7)
        for i in range(2, 9):  # node-2 to node-8 inclusive (7 signatures)
            signature = f"signature_from_node_{i}".encode()
            is_validated = validator.validate_event(event, f"node-{i}", signature)

            if i == 8:
                assert is_validated
                assert validator.is_validated(event)
            else:
                assert not is_validated

    def test_source_reputation(self):
        """Test source reputation tracking."""
        validator = QuorumValidator("node-1", total_nodes=10)

        # Report valid event
        event1 = validator.report_critical_event(
            CriticalEventType.NODE_FAILURE,
            target="node-5",
            evidence={"latency": float("inf")},
        )

        # Validate event (quorum reached: 7 signatures needed)
        for i in range(2, 9):
            validator.validate_event(event1, f"node-{i}", b"sig")

        # Source reputation should increase above initial 1.0
        reputation = validator.get_source_reputation("node-1")
        assert reputation > 1.0

        # Penalize source for false report
        validator.penalize_source("node-1", "false_report")
        reputation_after = validator.get_source_reputation("node-1")
        assert reputation_after < reputation


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestMeshByzantineProtection:
    """Tests for integrated Mesh Byzantine Protection."""

    def test_beacon_signing_and_verification(self):
        """Test beacon signing and verification."""
        protection1 = MeshByzantineProtection("node-1", total_nodes=10)
        protection2 = MeshByzantineProtection("node-2", total_nodes=10)

        # Sign beacon
        beacon = protection1.sign_beacon(["node-2", "node-3"])

        # Verify beacon
        is_valid, error = protection2.verify_beacon(beacon)
        assert is_valid, f"Beacon verification failed: {error}"

    def test_node_failure_quorum(self):
        """Test node failure reporting with quorum validation."""
        # Create 10 nodes
        protections = {
            f"node-{i}": MeshByzantineProtection(f"node-{i}", total_nodes=10)
            for i in range(1, 11)
        }

        # Node-1 reports node-5 failure
        event = protections["node-1"].report_node_failure(
            "node-5", evidence={"latency": float("inf"), "packet_loss": 1.0}
        )

        # Other nodes validate (need 7 signatures)
        validated_count = 0
        for i in range(2, 9):  # node-2 to node-8
            node_id = f"node-{i}"
            signature = (
                protections[node_id]
                .signed_gossip.sign_message(
                    MessageType.NODE_FAILURE, {"target": "node-5"}
                )
                .signature
            )

            is_validated = protections[node_id].validate_node_failure(event, signature)

            if is_validated:
                validated_count += 1

        assert validated_count >= 1  # At least one validation should reach quorum
        assert "node-5" in protections["node-1"].get_validated_failures()

    def test_quarantine_protection(self):
        """Test that quarantined nodes are rejected."""
        protection1 = MeshByzantineProtection("node-1", total_nodes=10)
        protection2 = MeshByzantineProtection("node-2", total_nodes=10)

        # Send many invalid beacons to trigger quarantine
        for i in range(20):
            beacon = protection1.sign_beacon(["node-2"])
            beacon.signature = b"invalid"
            protection2.verify_beacon(beacon)

        # Node-1 should be quarantined
        assert protection2.is_node_quarantined("node-1")
        assert not protection2.should_accept_message("node-1")

    def test_reputation_tracking(self):
        """Test reputation tracking."""
        protection1 = MeshByzantineProtection("node-1", total_nodes=10)
        protection2 = MeshByzantineProtection("node-2", total_nodes=10)

        # Send invalid message
        beacon = protection1.sign_beacon(["node-2"])
        beacon.signature = b"invalid"
        protection2.verify_beacon(beacon)

        reputation_bad = protection2.get_node_reputation("node-1")
        assert reputation_bad < 1.0

        # Send valid messages
        for i in range(10):
            beacon = protection1.sign_beacon(["node-2"], timestamp=time.time() + i)
            protection2.verify_beacon(beacon)

        reputation_good = protection2.get_node_reputation("node-1")
        assert reputation_good > reputation_bad
