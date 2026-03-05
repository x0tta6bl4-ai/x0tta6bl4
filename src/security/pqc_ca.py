"""
PQC Certificate Authority for x0tta6bl4 Mesh.
=============================================

Implements a second identity layer using ML-DSA-65 (Post-Quantum) 
to sign and rotate node identities, augmenting standard SPIFFE SVIDs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.security.pqc_identity import PQCNodeIdentity

logger = logging.getLogger(__name__)

@dataclass
class PQCSVID:
    """PQC-signed Workload Identity (SVID extension)."""
    spiffe_id: str
    public_key_hex: str
    algorithm: str # ML-DSA-65
    issued_at: str
    expires_at: str
    signature: str
    issuer_did: str

class PQCCertificateAuthority:
    """
    Central CA for issuing Post-Quantum signed identities.
    """
    def __init__(self, ca_node_id: str = "maas-root-ca"):
        self.identity = PQCNodeIdentity(ca_node_id)
        self.issued_count = 0
        logger.info(f"PQCCertificateAuthority initialized with DID: {self.identity.did}")

    def issue_pqc_svid(self, spiffe_id: str, node_public_key_hex: str, ttl_days: int = 30) -> PQCSVID:
        """
        Signs a node's public key binding it to a SPIFFE ID.
        """
        now = datetime.utcnow()
        expires = now + timedelta(days=ttl_days)
        
        claims = {
            "sub": spiffe_id,
            "pub": node_public_key_hex,
            "iat": now.isoformat(),
            "exp": expires.isoformat(),
            "iss": self.identity.did
        }
        
        # Sign claims
        signed_data = self.identity.sign_manifest(claims)
        signature = signed_data["proof"]["signatureValue"]
        
        self.issued_count += 1
        
        return PQCSVID(
            spiffe_id=spiffe_id,
            public_key_hex=node_public_key_hex,
            algorithm=self.identity.security.pq_backend.sig_algorithm,
            issued_at=claims["iat"],
            expires_at=claims["exp"],
            signature=signature,
            issuer_did=self.identity.did
        )

    def verify_pqc_svid(self, svid: PQCSVID, issuer_public_key_hex: str) -> bool:
        """
        Verifies a PQC-SVID signature.
        """
        claims = {
            "sub": svid.spiffe_id,
            "pub": svid.public_key_hex,
            "iat": svid.issued_at,
            "exp": svid.expires_at,
            "iss": svid.issuer_did
        }
        
        signed_manifest = {
            "manifest": claims,
            "proof": {
                "signatureValue": svid.signature
            }
        }
        
        return self.identity.verify_remote_node(signed_manifest, issuer_public_key_hex)

class PQCIdentityManager:
    """
    Manages local node's PQC identity and interaction with CA.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.identity = PQCNodeIdentity(node_id)
        self.current_svid: Optional[PQCSVID] = None
        logger.info(f"PQCIdentityManager initialized for {node_id}")

    def get_public_key_hex(self) -> str:
        return self.identity.security.get_public_keys()["sig_public_key"]

    def rotate_identity(self, ca: PQCCertificateAuthority) -> PQCSVID:
        """
        Perform key rotation and get new SVID from CA.
        """
        self.identity.rotate_keys()
        new_pubkey = self.get_public_key_hex()
        
        # In real world, this would be an API call to MaaS CA
        self.current_svid = ca.issue_pqc_svid(
            spiffe_id=f"spiffe://x0tta6bl4.mesh/node/{self.node_id}",
            node_public_key_hex=new_pubkey
        )
        
        logger.info(f"✅ PQC Identity rotated for {self.node_id}. New signature: {self.current_svid.signature[:16]}...")
        return self.current_svid
