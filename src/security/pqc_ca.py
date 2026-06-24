"""
PQC Certificate Authority for x0tta6bl4 Mesh.
=============================================

Implements a second identity layer using ML-DSA-65 (Post-Quantum) 
to sign and rotate node identities, augmenting standard SPIFFE SVIDs.
"""

import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Dict


logger = logging.getLogger(__name__)

PQCNodeIdentity: Any = None


def _get_pqc_node_identity() -> Any:
    global PQCNodeIdentity
    if PQCNodeIdentity is None:
        from src.security.pqc_identity import PQCNodeIdentity as imported_identity

        PQCNodeIdentity = imported_identity
    return PQCNodeIdentity

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
        self.identity = _get_pqc_node_identity()(ca_node_id)
        self.issued_count = 0
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"pqc-certificate-authority:{_safe_hash(ca_node_id)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "pqc_certificate_authority_init",
                "goal": "Initialize PQC identity issuer safely",
                "signals": {
                    "ca_node_hash": _safe_hash(ca_node_id),
                    "issuer_did_hash": _safe_hash(self.identity.did),
                    "issued_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep raw CA node ids, SPIFFE IDs, DID values, public keys, "
                    "signatures, and manifest claims out of thinking context."
                ),
            }
        )
        logger.info(f"PQCCertificateAuthority initialized with DID: {self.identity.did}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_ca_node_ids": True,
                    "redact_spiffe_ids": True,
                    "redact_dids": True,
                    "redact_public_keys": True,
                    "redact_signatures": True,
                    "redact_manifest_claims": True,
                    "preserve_identity_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, algorithm labels, and TTL bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
        
        svid = PQCSVID(
            spiffe_id=spiffe_id,
            public_key_hex=node_public_key_hex,
            algorithm=self.identity.security.pq_backend.sig_algorithm,
            issued_at=claims["iat"],
            expires_at=claims["exp"],
            signature=signature,
            issuer_did=self.identity.did
        )
        self._record_thinking(
            "pqc_svid_issued",
            "Issue PQC SVID safely",
            {
                "spiffe_hash": _safe_hash(spiffe_id),
                "public_key_hash": _safe_hash(node_public_key_hex),
                "public_key_length_band": _safe_number_band(
                    len(node_public_key_hex)
                ),
                "ttl_days_band": _safe_number_band(ttl_days),
                "signature_hash": _safe_hash(signature),
                "issuer_did_hash": _safe_hash(self.identity.did),
                "algorithm": svid.algorithm,
                "issued_count_bucket": _safe_count_bucket(self.issued_count),
            },
        )
        return svid

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
        
        verified = self.identity.verify_remote_node(signed_manifest, issuer_public_key_hex)
        self._record_thinking(
            "pqc_svid_verified",
            "Verify PQC SVID safely",
            {
                "spiffe_hash": _safe_hash(svid.spiffe_id),
                "public_key_hash": _safe_hash(svid.public_key_hex),
                "issuer_public_key_hash": _safe_hash(issuer_public_key_hex),
                "signature_hash": _safe_hash(svid.signature),
                "issuer_did_hash": _safe_hash(svid.issuer_did),
                "verified": verified,
            },
        )
        return verified

class PQCIdentityManager:
    """
    Manages local node's PQC identity and interaction with CA.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.identity = _get_pqc_node_identity()(node_id)
        self.current_svid: Optional[PQCSVID] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"pqc-identity-manager:{_safe_hash(node_id)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "pqc_identity_manager_init",
                "goal": "Initialize local PQC identity safely",
                "signals": {
                    "node_hash": _safe_hash(node_id),
                    "did_hash": _safe_hash(self.identity.did),
                    "has_current_svid": False,
                },
                "safety_boundary": (
                    "Keep raw node ids, SPIFFE IDs, DID values, public keys, "
                    "private keys, and signatures out of thinking context."
                ),
            }
        )
        logger.info(f"PQCIdentityManager initialized for {node_id}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_node_ids": True,
                    "redact_spiffe_ids": True,
                    "redact_dids": True,
                    "redact_public_keys": True,
                    "redact_private_keys": True,
                    "redact_signatures": True,
                    "preserve_identity_rotation_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, algorithm labels, and TTL bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def get_public_key_hex(self) -> str:
        public_key = self.identity.security.get_public_keys()["sig_public_key"]
        self._record_thinking(
            "pqc_public_key_reported",
            "Report local PQC public key safely",
            {
                "node_hash": _safe_hash(self.node_id),
                "public_key_hash": _safe_hash(public_key),
                "public_key_length_band": _safe_number_band(len(public_key)),
            },
        )
        return public_key

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
        self._record_thinking(
            "pqc_identity_rotated",
            "Rotate local PQC identity safely",
            {
                "node_hash": _safe_hash(self.node_id),
                "spiffe_hash": _safe_hash(self.current_svid.spiffe_id),
                "public_key_hash": _safe_hash(new_pubkey),
                "signature_hash": _safe_hash(self.current_svid.signature),
                "issuer_did_hash": _safe_hash(self.current_svid.issuer_did),
                "has_current_svid": self.current_svid is not None,
            },
        )
        return self.current_svid
