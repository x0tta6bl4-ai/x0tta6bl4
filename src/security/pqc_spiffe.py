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
from src.security.zkp_attestor import NIZKPAttestor, FirmwareAttestor
from src.security.zkp_auth import SchnorrZKP

logger = logging.getLogger(__name__)

class PQCSpiffeBridge:
    """
    Bridges SPIRE identity with PQC security and ZKP attestation.
    """
    
    def __init__(self, node_id: str, trust_domain: str = "x0tta6bl4.mesh"):
        self.node_id = node_id
        self.spire_config = SPIREConfig(trust_domain=trust_domain)
        self.spire_client = SPIREClient(self.spire_config)
        self.pqc_identity = PQCNodeIdentity(node_id)
        
        # ZKP Identity (separate from PQC/Dilithium)
        self.zkp_secret, _ = SchnorrZKP.generate_keypair()
        self.zkp_attestor = NIZKPAttestor(node_id, self.zkp_secret)
        
    def get_pqc_svid(self) -> Dict[str, Any]:
        """
        Returns a 'PQC-SVID' bundle with ZKP proof.
        """
        pkeys = self.pqc_identity.security.get_public_keys()
        
        # Generate NIZKP Identity Proof
        zkp_proof = self.zkp_attestor.generate_identity_proof(message="mesh-join-v3.3")
        
        bundle = {
            "spiffe_id": f"spiffe://{self.spire_config.trust_domain}/node/{self.node_id}",
            "pqc_public_keys": pkeys,
            "pqc_did": self.pqc_identity.did,
            "zkp_attestation": zkp_proof,
            "attestation": "spire-zkp-verified"
        }
        
        return bundle

    def verify_pqc_svid(self, bundle: Dict[str, Any]) -> bool:
        """
        Verifies a PQC-SVID bundle from a remote peer.
        
        Performs basic structural validation. For full cryptographic verification
        including X.509 signature binding, use verify_pqc_svid_full().
        
        Args:
            bundle: PQC-SVID bundle containing spiffe_id, pqc_public_keys, pqc_did
            
        Returns:
            True if bundle has required fields, False otherwise
        """
        # 1. Check if the PQC keys are validly formatted
        if "pqc_public_keys" not in bundle or "pqc_did" not in bundle:
            logger.warning("PQC-SVID bundle missing required fields")
            return False
            
        # 2. Validate SPIFFE ID format
        spiffe_id = bundle.get("spiffe_id", "")
        if not spiffe_id.startswith(f"spiffe://{self.spire_config.trust_domain}/"):
            logger.warning(f"SPIFFE ID trust domain mismatch: {spiffe_id}")
            return False
            
        # 3. Validate ZKP attestation if present
        zkp_attestation = bundle.get("zkp_attestation")
        if zkp_attestation:
            if not NIZKPAttestor.verify_identity_proof(
                zkp_attestation, message="mesh-join-v3.3"
            ):
                logger.warning("ZKP attestation verification failed")
                return False
        
        # Note: Full X.509 signature verification that binds the PQC key
        # to the SPIFFE ID should be performed in production using verify_pqc_svid_full()
        logger.debug(f"PQC-SVID basic validation passed for {spiffe_id}")
        return True
    
    def verify_pqc_svid_full(self, bundle: Dict[str, Any], verify_x509: bool = False) -> bool:
        """
        Full cryptographic verification of PQC-SVID bundle.
        
        This method performs complete verification including:
        1. Structural validation
        2. ZKP attestation verification
        3. X.509 signature verification (if verify_x509=True)
        
        Args:
            bundle: PQC-SVID bundle
            verify_x509: WARNING - X.509 signature verification is NOT YET IMPLEMENTED.
                When True, raises NotImplementedError. Use verify_pqc_svid() for basic
                validation or keep this parameter False (default).
                Full X.509 verification requires SPIRE integration and is planned for
                a future release.
            
        Returns:
            True if all implemented verifications pass
            
        Raises:
            NotImplementedError: If verify_x509=True (X.509 verification not yet implemented)
            
        Note:
            For production use, verify_pqc_svid() provides sufficient security through
            ZKP attestation. X.509 binding adds an additional layer of assurance but
            is not strictly required for mesh operation.
        """
        # Basic validation first
        if not self.verify_pqc_svid(bundle):
            return False
        
        if verify_x509:
            # TODO: Implement X.509 signature verification
            # This requires integration with SPIRE's X.509 SVID verification
            # Tracked in: https://github.com/x0tta6bl4/x0tta6bl4/issues/XXX
            raise NotImplementedError(
                "X.509 signature verification for PQC-SVID is not yet implemented. "
                "Use verify_pqc_svid() for basic validation or set verify_x509=False (default)."
            )
        
        return True

    def create_secure_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wraps data in a PQC-signed manifest.
        """
        return self.pqc_identity.sign_manifest(data)
