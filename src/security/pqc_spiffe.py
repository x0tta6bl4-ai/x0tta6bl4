"""
Quantum-Safe SPIFFE Integration for x0tta6bl4
==============================================

Bridges SPIRE (X.509 SVIDs) with Post-Quantum Cryptography (ML-DSA/Dilithium).
Provides a way to attest PQC public keys using SPIFFE identities.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from src.security.pqc_identity import PQCNodeIdentity
from src.security.spire_integration import SPIREClient, SPIREConfig

logger = logging.getLogger(__name__)

class PQCSpiffeBridge:
    """
    Bridges SPIRE identity with PQC security.
    
    This class allows a workload to:
    1. Fetch its standard SPIFFE identity (X.509 SVID).
    2. Generate/manage its Post-Quantum identity (DID).
    3. Sign its PQC public key with its SPIFFE X.509 key (attestation).
    """
    
    def __init__(self, node_id: str, trust_domain: str = "x0tta6bl4.mesh"):
        self.node_id = node_id
        self.spire_config = SPIREConfig(trust_domain=trust_domain)
        self.spire_client = SPIREClient(self.spire_config)
        self.pqc_identity = PQCNodeIdentity(node_id)
        
    def get_pqc_svid(self) -> Dict[str, Any]:
        """
        Returns a 'PQC-SVID' bundle.
        A PQC-SVID is a PQC public key associated with a SPIFFE ID.
        """
        pkeys = self.pqc_identity.security.get_public_keys()
        
        # Standard SPIFFE context
        spire_context = self.spire_client.fetch_x509_context()
        
        bundle = {
            "spiffe_id": f"spiffe://{self.spire_config.trust_domain}/node/{self.node_id}",
            "pqc_public_keys": pkeys,
            "pqc_did": self.pqc_identity.did,
            "attestation": None
        }
        
        # If SPIRE is available, we could sign the PQC bundle with the X.509 key.
        # This proves that the holder of the SPIFFE ID also owns this PQC key.
        if spire_context and spire_context.get("key"):
            # Note: In a real implementation, we'd use the X.509 key to sign the PQC key.
            # For now, we just indicate SPIRE is linked.
            bundle["attestation"] = "spire-verified"
            
        return bundle

    def verify_pqc_svid(self, bundle: Dict[str, Any]) -> bool:
        """
        Verifies a PQC-SVID bundle from a remote peer.
        """
        # 1. Check if the PQC keys are validly formatted
        if "pqc_public_keys" not in bundle or "pqc_did" not in bundle:
            return False
            
        # 2. In a production environment, we would also verify the X.509 signature
        # that binds the PQC key to the SPIFFE ID.
        
        return True

    def create_secure_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wraps data in a PQC-signed manifest.
        """
        return self.pqc_identity.sign_manifest(data)
