import pytest
from src.security.peaq_bridge import PeaqPqcBridge

def test_peaq_bridge_initialization():
    node_id = "node-bridge-1"
    bridge = PeaqPqcBridge(node_id)
    
    assert bridge.node_id == node_id
    assert bridge.peaq_identity.node_id == node_id
    assert bridge.active_key_id is not None
    assert len(bridge.archived_keys) == 0

def test_peaq_bridge_create_did_document():
    node_id = "node-bridge-2"
    bridge = PeaqPqcBridge(node_id)
    
    doc = bridge.create_did_document()
    assert doc["id"] == bridge.peaq_identity.get_peaq_did()
    assert "spiffe_id" in doc
    assert doc["pqc_key_id"] == bridge.active_key_id
    assert len(doc["verificationMethod"]) == 2
    assert "proof" in doc
    assert doc["proof"]["type"] == "EthereumEIP191Signature"

def test_peaq_bridge_rotate_pqc_key():
    node_id = "node-bridge-3"
    bridge = PeaqPqcBridge(node_id)
    
    old_key_id = bridge.active_key_id
    old_pub_key = bridge.public_key
    
    rotation = bridge.rotate_pqc_key()
    
    assert rotation["operation"] == "key_rotation"
    assert rotation["old_key_id"] == old_key_id
    assert rotation["old_public_key"] == bridge._to_hex(old_pub_key)
    assert rotation["new_key_id"] == bridge.active_key_id
    assert rotation["new_public_key"] == bridge._to_hex(bridge.public_key)
    assert "archival_signature" in rotation
    assert "proof" in rotation
    
    assert old_key_id in bridge.archived_keys
    assert bridge.archived_keys[old_key_id] == old_pub_key
