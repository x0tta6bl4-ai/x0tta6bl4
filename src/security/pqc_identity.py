"""
Post-Quantum Decentralized Identity (PQC-DID) for x0tta6bl4 Mesh.
Upgrades W3C DID Core 1.0 to Quantum-Resistant standards using ML-DSA (Dilithium) and ML-KEM (Kyber).
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Import the existing PQC backend from libx0t
try:
    from libx0t.security.post_quantum import PQMeshSecurityLibOQS, LIBOQS_AVAILABLE
except ImportError:
    # Fallback if not installed in site-packages yet
    from src.libx0t.security.post_quantum import PQMeshSecurityLibOQS, LIBOQS_AVAILABLE

logger = logging.getLogger(__name__)

@dataclass
class PQCVerificationMethod:
    """Verification method in PQC DID Document using ML-DSA."""
    id: str
    type: str # e.g., "ML-DSA-65"
    controller: str
    public_key_hex: str
    key_id: str
    created: float = field(default_factory=time.time)
    revoked: bool = False

@dataclass
class PQCDIDDocument:
    """W3C DID Document extended for Post-Quantum algorithms."""
    id: str
    verification_method: List[PQCVerificationMethod] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    assertion_method: List[str] = field(default_factory=list)
    key_agreement: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://x0tta6bl4.mesh/pqc/v1"
            ],
            "id": self.id,
            "verificationMethod": [
                {
                    "id": vm.id,
                    "type": vm.type,
                    "controller": vm.controller,
                    "publicKeyHex": vm.public_key_hex,
                    "keyId": vm.key_id
                }
                for vm in self.verification_method if not vm.revoked
            ],
            "authentication": self.authentication,
            "assertionMethod": self.assertion_method,
            "keyAgreement": self.key_agreement,
            "created": datetime.fromtimestamp(self.created).isoformat(),
            "updated": datetime.fromtimestamp(self.updated).isoformat(),
        }

class PQCNodeIdentity:
    """
    Manage Post-Quantum Identity for a mesh node.
    Combines DID standards with NIST PQC algorithms.
    """
    def __init__(self, node_id: str, kem_alg: str = "ML-KEM-768", sig_alg: str = "ML-DSA-65"):
        if not LIBOQS_AVAILABLE:
            logger.critical("liboqs is NOT available. Falling back to insecure mode (ONLY FOR DEV)!")
        
        self.node_id = node_id
        self.security = PQMeshSecurityLibOQS(node_id, kem_algorithm=kem_alg, sig_algorithm=sig_alg)
        
        # PQC DID: did:mesh:pqc:<node_id>:<key_id_short>
        pkeys = self.security.get_public_keys()
        self.did = f"did:mesh:pqc:{node_id}:{pkeys['key_id'][:8]}"
        
        self.document = self._create_pqc_document()
        logger.info(f"Generated PQC-DID for node {node_id}: {self.did}")

    def _create_pqc_document(self) -> PQCDIDDocument:
        pkeys = self.security.get_public_keys()
        sig_key_id = f"{self.did}#sig-1"
        kem_key_id = f"{self.did}#kem-1"

        sig_vm = PQCVerificationMethod(
            id=sig_key_id,
            type=pkeys['sig_algorithm'],
            controller=self.did,
            public_key_hex=pkeys['sig_public_key'],
            key_id=pkeys['key_id']
        )

        kem_vm = PQCVerificationMethod(
            id=kem_key_id,
            type=pkeys['kem_algorithm'],
            controller=self.did,
            public_key_hex=pkeys['kem_public_key'],
            key_id=pkeys['key_id']
        )

        return PQCDIDDocument(
            id=self.did,
            verification_method=[sig_vm, kem_vm],
            authentication=[sig_key_id],
            assertion_method=[sig_key_id],
            key_agreement=[kem_key_id]
        )

    def sign_manifest(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signs a node manifest (state, capabilities, resources) using PQC.
        """
        payload = json.dumps(manifest_data, sort_keys=True).encode()
        signature = self.security.sign(payload)
        
        return {
            "manifest": manifest_data,
            "proof": {
                "type": self.security.sig_keypair.algorithm.value,
                "created": datetime.now().isoformat(),
                "verificationMethod": self.document.authentication[0],
                "signatureValue": signature.hex()
            }
        }

    def verify_remote_node(self, signed_manifest: Dict[str, Any], remote_pubkey_hex: str) -> bool:
        """
        Verifies a manifest from another node.
        """
        try:
            payload = json.dumps(signed_manifest["manifest"], sort_keys=True).encode()
            signature = bytes.fromhex(signed_manifest["proof"]["signatureValue"])
            pubkey = bytes.fromhex(remote_pubkey_hex)
            
            return self.security.verify(payload, signature, pubkey)
        except Exception as e:
            logger.error(f"PQC Verification failed: {e}")
            return False

    def rotate_keys(self):
        """
        MAPE-K triggered key rotation.
        """
        logger.info(f"Rotating PQC keys for node {self.node_id}")
        self.security = PQMeshSecurityLibOQS(
            self.node_id, 
            self.security.pq_backend.kem_algorithm, 
            self.security.pq_backend.sig_algorithm
        )
        self.document = self._create_pqc_document()
        self.document.updated = time.time()
        return self.did
