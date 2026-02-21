
import pytest
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

try:
    from security.pqc_identity import PQCNodeIdentity
    from libx0t.security.post_quantum import LIBOQS_AVAILABLE
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for CI environments where package layout might be different
    from src.security.pqc_identity import PQCNodeIdentity
    from src.libx0t.security.post_quantum import LIBOQS_AVAILABLE

@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not available")
def test_pqc_identity_generation():
    """Test that a PQC-DID and document are correctly generated."""
    node_id = "test-node-001"
    identity = PQCNodeIdentity(node_id)
    
    assert identity.node_id == node_id
    assert identity.did.startswith("did:mesh:pqc:test-node-001:")
    
    doc = identity.document.to_dict()
    assert doc["id"] == identity.did
    assert len(doc["verificationMethod"]) >= 2 # Sig + KEM
    assert "ML-DSA-65" in str(doc["verificationMethod"])
    assert "ML-KEM-768" in str(doc["verificationMethod"])

@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not available")
def test_pqc_manifest_signing_and_verification():
    """Test signing and verifying a node manifest with PQC."""
    identity = PQCNodeIdentity("node-alpha")
    
    manifest = {
        "status": "online",
        "cpu_load": 0.45,
        "mesh_neighbors": ["node-beta", "node-gamma"],
        "version": "1.2.3-beta"
    }
    
    signed_manifest = identity.sign_manifest(manifest)
    
    assert "proof" in signed_manifest
    assert signed_manifest["proof"]["type"] == "ML-DSA-65"
    
    # Verify using the same identity (self-verification)
    pubkey_hex = identity.security.get_public_keys()["sig_public_key"]
    is_valid = identity.verify_remote_node(signed_manifest, pubkey_hex)
    
    assert is_valid is True

@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs-python not available")
def test_pqc_key_rotation():
    """Test that identity rotation generates a new DID or updates the document."""
    identity = PQCNodeIdentity("node-rotator")
    old_did = identity.did
    old_sig_pubkey = identity.security.get_public_keys()["sig_public_key"]
    
    identity.rotate_keys()
    
    new_sig_pubkey = identity.security.get_public_keys()["sig_public_key"]
    
    assert old_sig_pubkey != new_sig_pubkey
    assert identity.document.updated > identity.document.created
