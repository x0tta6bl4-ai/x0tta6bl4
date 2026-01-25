"""
Chaos Engineering: Byzantine Attack Simulations.

Тестирует защиту от различных Byzantine attacks:
- Replay attacks
- Signature forgery
- False failure reports
- Quorum manipulation
"""
import pytest
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from network.byzantine.signed_gossip import SignedGossip, MessageType
    from network.byzantine.quorum_validation import QuorumValidator, CriticalEventType
    from network.byzantine.mesh_byzantine_protection import MeshByzantineProtection
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    pytest.skip("liboqs-python not installed", allow_module_level=True)


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestReplayAttacks:
    """Test protection against replay attacks."""
    
    def test_beacon_replay_attack(self):
        """Test that replaying old beacons is detected."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")
        
        # Sign beacon
        beacon1 = gossip1.sign_message(
            MessageType.BEACON,
            {"neighbors": ["node-2"]}
        )
        
        # First verification succeeds
        is_valid, _ = gossip2.verify_message(beacon1)
        assert is_valid
        
        # Replay attack: same message again
        is_valid, error = gossip2.verify_message(beacon1)
        assert not is_valid
        assert "replay" in error.lower() or "nonce" in error.lower()
    
    def test_epoch_replay_attack(self):
        """Test that replaying messages from old epoch is detected."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")
        
        # Sign message in epoch 0
        msg1 = gossip1.sign_message(
            MessageType.BEACON,
            {"neighbors": ["node-2"]}
        )
        gossip2.verify_message(msg1)
        
        # Rotate keys (new epoch)
        gossip1.rotate_keys()
        
        # Try to replay old message (should fail due to epoch check)
        # Note: This test may need adjustment based on epoch validation logic
        msg1.epoch = 0  # Old epoch
        is_valid, error = gossip2.verify_message(msg1)
        # Should fail due to stale epoch or replay detection
        assert not is_valid or "epoch" in error.lower()


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestSignatureForgery:
    """Test protection against signature forgery."""
    
    def test_forged_signature_rejected(self):
        """Test that forged signatures are rejected."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")
        
        # Sign message
        message = gossip1.sign_message(
            MessageType.BEACON,
            {"neighbors": ["node-2"]}
        )
        
        # Forge signature
        message.signature = b"forged_signature_12345"
        
        # Verification should fail
        is_valid, error = gossip2.verify_message(message)
        assert not is_valid
        assert "invalid" in error.lower() or "signature" in error.lower()
    
    def test_public_key_manipulation(self):
        """Test that changing public key is detected."""
        gossip1 = SignedGossip("node-1")
        gossip2 = SignedGossip("node-2")
        
        # Sign message
        message = gossip1.sign_message(
            MessageType.BEACON,
            {"neighbors": ["node-2"]}
        )
        
        # First verification (stores public key)
        is_valid, _ = gossip2.verify_message(message)
        assert is_valid
        
        # Try to change public key (should be detected if we track keys)
        # This depends on implementation - may need to check in actual usage
        message.public_key = b"forged_public_key"
        
        # Verification should fail
        is_valid, error = gossip2.verify_message(message)
        # May fail due to invalid signature or key mismatch
        assert not is_valid


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestFalseFailureReports:
    """Test protection against false failure reports."""
    
    def test_single_false_report_rejected(self):
        """Test that single false failure report is rejected (needs quorum)."""
        # Create 10 nodes
        protections = {
            f"node-{i}": MeshByzantineProtection(f"node-{i}", total_nodes=10)
            for i in range(1, 11)
        }
        
        # Malicious node-1 reports false failure
        event = protections["node-1"].report_node_failure(
            "node-5",  # Actually healthy node
            evidence={"latency": 1000.0}  # False evidence
        )
        
        # Only malicious node validates (no quorum)
        signature = protections["node-1"].signed_gossip.sign_message(
            MessageType.NODE_FAILURE,
            {"target": "node-5"}
        ).signature
        
        is_validated = protections["node-1"].validate_node_failure(event, signature)
        
        # Should not be validated (only 1 signature, need 7)
        assert not is_validated
        assert "node-5" not in protections["node-1"].get_validated_failures()
    
    def test_quorum_prevents_false_reports(self):
        """Test that quorum requirement prevents false reports."""
        # Create 10 nodes
        protections = {
            f"node-{i}": MeshByzantineProtection(f"node-{i}", total_nodes=10)
            for i in range(1, 11)
        }
        
        # Malicious nodes (1-3) try to report false failure
        event = protections["node-1"].report_node_failure(
            "node-5",
            evidence={"latency": 1000.0}  # False
        )
        
        # Only malicious nodes validate (3 signatures, need 7)
        for i in range(1, 4):
            node_id = f"node-{i}"
            signature = protections[node_id].signed_gossip.sign_message(
                MessageType.NODE_FAILURE,
                {"target": "node-5"}
            ).signature
            
            protections[node_id].validate_node_failure(event, signature)
        
        # Should not be validated (only 3 signatures, need 7)
        assert "node-5" not in protections["node-1"].get_validated_failures()


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not installed")
class TestQuorumManipulation:
    """Test protection against quorum manipulation."""
    
    def test_byzantine_nodes_cannot_reach_quorum(self):
        """Test that Byzantine nodes cannot reach quorum if < 1/3."""
        # Create 10 nodes (max 3 Byzantine = f < n/3)
        protections = {
            f"node-{i}": MeshByzantineProtection(f"node-{i}", total_nodes=10)
            for i in range(1, 11)
        }
        
        # Byzantine nodes (1-3) try to manipulate quorum
        event = protections["node-1"].report_node_failure(
            "node-5",
            evidence={"latency": 1000.0}  # False
        )
        
        # Only Byzantine nodes validate (3 signatures, need 7)
        for i in range(1, 4):
            node_id = f"node-{i}"
            signature = protections[node_id].signed_gossip.sign_message(
                MessageType.NODE_FAILURE,
                {"target": "node-5"}
            ).signature
            
            protections[node_id].validate_node_failure(event, signature)
        
        # Quorum not reached (3 < 7)
        assert "node-5" not in protections["node-1"].get_validated_failures()
    
    def test_honest_nodes_can_reach_quorum(self):
        """Test that honest nodes can reach quorum."""
        # Create 10 nodes
        protections = {
            f"node-{i}": MeshByzantineProtection(f"node-{i}", total_nodes=10)
            for i in range(1, 11)
        }
        
        # Honest node reports real failure
        event = protections["node-1"].report_node_failure(
            "node-5",
            evidence={"latency": float('inf'), "packet_loss": 1.0}  # Real failure
        )
        
        # Honest nodes validate (7 signatures, need 7)
        for i in range(1, 8):  # node-1 to node-7
            node_id = f"node-{i}"
            signature = protections[node_id].signed_gossip.sign_message(
                MessageType.NODE_FAILURE,
                {"target": "node-5"}
            ).signature
            
            is_validated = protections[node_id].validate_node_failure(event, signature)
            
            if i == 7:
                assert is_validated
                assert "node-5" in protections[node_id].get_validated_failures()

