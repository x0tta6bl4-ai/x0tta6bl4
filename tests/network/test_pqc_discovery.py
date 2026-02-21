
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

try:
    from network.discovery.protocol import MulticastDiscovery, DiscoveryMessage, MessageType
    from security.pqc_identity import PQCNodeIdentity
    from libx0t.security.post_quantum import LIBOQS_AVAILABLE
except ImportError:
    # Fallback for CI
    from src.network.discovery.protocol import MulticastDiscovery, DiscoveryMessage, MessageType
    from src.security.pqc_identity import PQCNodeIdentity
    from src.libx0t.security.post_quantum import LIBOQS_AVAILABLE

class TestPQCDiscovery(unittest.TestCase):

    def setUp(self):
        if not LIBOQS_AVAILABLE:
            self.skipTest("liboqs-python not available")
        
        self.node_id_sender = "node-sender"
        self.node_id_receiver = "node-receiver"
        
        # Create Identities
        self.identity_sender = PQCNodeIdentity(self.node_id_sender)
        self.identity_receiver = PQCNodeIdentity(self.node_id_receiver)
        
        # Create Discovery Instances
        self.discovery_sender = MulticastDiscovery(
            self.node_id_sender, 
            service_port=8000, 
            identity_manager=self.identity_sender
        )
        self.discovery_receiver = MulticastDiscovery(
            self.node_id_receiver, 
            service_port=8001, 
            identity_manager=self.identity_receiver
        )

    def test_announce_signature_creation(self):
        """Test that ANNOUNCE messages are correctly signed."""
        # Manually create verify the private method logic
        # Mock socket to avoid network IO
        self.discovery_sender._socket = MagicMock()
        
        # We want to check _sign_message logic directly
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.node_id_sender,
            payload={"test": "data"}
        )
        
        assert msg.signature is None
        
        self.discovery_sender._sign_message(msg)
        
        assert msg.signature is not None
        assert len(msg.signature) > 64 # PQC signatures are long
        assert msg.pqc_pubkey == self.identity_sender.security.get_public_keys()['sig_public_key']

    def test_signature_verification_success(self):
        """Test that a validly signed message is accepted."""
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.node_id_sender,
            payload={"test": "verification"}
        )
        self.discovery_sender._sign_message(msg)
        
        # Receiver should accept it
        is_valid = self.discovery_receiver._verify_message(msg)
        self.assertTrue(is_valid)

    def test_signature_verification_tamper(self):
        """Test that tampering with payload invalidates signature."""
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.node_id_sender,
            payload={"test": "original"}
        )
        self.discovery_sender._sign_message(msg)
        
        # Tamper with payload
        msg.payload = {"test": "tampered"}
        
        # Receiver should reject it
        is_valid = self.discovery_receiver._verify_message(msg)
        self.assertFalse(is_valid)

    def test_signature_verification_wrong_key(self):
        """Test that using wrong public key fails verification."""
        msg = DiscoveryMessage(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.node_id_sender,
            payload={"test": "key_mismatch"}
        )
        self.discovery_sender._sign_message(msg)
        
        # Replace pubkey with receiver's pubkey (different keypair)
        msg.pqc_pubkey = self.identity_receiver.security.get_public_keys()['sig_public_key']
        
        is_valid = self.discovery_receiver._verify_message(msg)
        self.assertFalse(is_valid)

if __name__ == '__main__':
    unittest.main()
