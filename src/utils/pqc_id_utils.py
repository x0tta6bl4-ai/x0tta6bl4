"""
Utility functions for PQC Identity and DID integration in x0tta6bl4.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def verify_pqc_manifest(signed_manifest: Dict[str, Any], identity_manager: Any) -> bool:
    """
    Verifies a PQC-signed manifest using the provided identity manager.
    
    Args:
        signed_manifest: Dict containing 'manifest' and 'proof' (signature)
        identity_manager: Instance of PQCNodeIdentity
        
    Returns:
        bool: True if verification succeeds
    """
    try:
        # Extract public key from proof or look up via DID
        proof = signed_manifest.get("proof", {})
        pubkey_hex = proof.get("publicKeyHex") # In some cases we might include it for convenience
        
        # If not in proof, we'd normally resolve the DID
        # For now, we assume the pubkey is provided or known
        if not pubkey_hex:
            logger.warning("Manifest proof missing publicKeyHex, cannot verify without DID resolution.")
            return False
            
        return identity_manager.verify_remote_node(signed_manifest, pubkey_hex)
    except Exception as e:
        logger.error(f"Error in manifest verification utility: {e}")
        return False

def extract_node_id_from_did(did: str) -> Optional[str]:
    """Extract node_id from did:mesh:pqc:<node_id>[:<key_id>]."""
    if not isinstance(did, str):
        return None

    parts = did.split(":")
    if len(parts) < 4:
        return None
    if parts[0] != "did" or parts[1] != "mesh" or parts[2] != "pqc":
        return None

    node_id = parts[3].strip()
    return node_id or None
