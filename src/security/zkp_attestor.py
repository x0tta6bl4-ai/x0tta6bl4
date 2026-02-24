"""
Zero-Knowledge Attestation Provider for x0tta6bl4
==================================================

Provides non-interactive ZKP (NIZKP) for node attestation at scale (10k nodes).
Uses Fiat-Shamir heuristic to convert Schnorr interactive proof to non-interactive.

Attestations supported:
1. Identity: Proof of private key possession without revealing it.
2. Firmware Integrity: Proof that firmware hash matches a commitment.
"""

import hashlib
import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from src.security.zkp_auth import G, P, Q, SchnorrZKP, PedersenCommitment

logger = logging.getLogger("zkp-attestor")

class NIZKPAttestor:
    """
    Non-Interactive ZKP Attestor.
    Generates proofs that can be verified in a single step.
    """
    def __init__(self, node_id: str, secret_key: int):
        self.node_id = node_id
        self.secret_key = secret_key
        self.public_key = pow(G, secret_key, P)

    def generate_identity_proof(self, message: str = "") -> Dict[str, Any]:
        """
        Generates a NIZKP of identity using Fiat-Shamir.
        Proof = (commitment, response) where challenge = H(G, public_key, commitment, message)
        """
        # 1. Create random nonce r and commitment R = G^r
        r = secrets.randbelow(Q - 1) + 1
        commitment = pow(G, r, P)
        
        # 2. Compute challenge c = H(G, public_key, commitment, message)
        challenge_input = f"{G}{self.public_key}{commitment}{message}{self.node_id}".encode()
        challenge = int(hashlib.sha256(challenge_input).hexdigest(), 16) % Q
        
        # 3. Compute response s = r + c*x
        response = (r + challenge * self.secret_key) % Q
        
        return {
            "node_id": self.node_id,
            "public_key": self.public_key,
            "commitment": commitment,
            "response": response,
            "timestamp": time.time()
        }

    @staticmethod
    def verify_identity_proof(
        proof: Dict[str, Any], 
        message: str = "", 
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verifies a NIZKP identity proof.
        Checks: G^s == commitment * public_key^c
        
        Args:
            proof: The proof dictionary containing node_id, public_key, commitment, response, timestamp
            message: The message that was signed
            max_age_seconds: Maximum age of proof in seconds (default 5 minutes)
        
        Returns:
            True if proof is valid and not expired, False otherwise
        """
        try:
            node_id = proof["node_id"]
            pk = proof["public_key"]
            comm = proof["commitment"]
            resp = proof["response"]
            
            # Validate timestamp to prevent replay attacks
            timestamp = proof.get("timestamp", 0)
            current_time = time.time()
            proof_age = current_time - timestamp
            
            if proof_age > max_age_seconds:
                logger.warning(
                    f"ZKP proof expired for node {node_id}: age={proof_age:.1f}s, max={max_age_seconds}s"
                )
                return False
            
            if proof_age < -30:  # Allow 30s clock skew for future timestamps
                logger.warning(
                    f"ZKP proof from future for node {node_id}: age={proof_age:.1f}s"
                )
                return False
            
            # Recompute challenge
            challenge_input = f"{G}{pk}{comm}{message}{node_id}".encode()
            challenge = int(hashlib.sha256(challenge_input).hexdigest(), 16) % Q
            
            # G^s mod P
            left = pow(G, resp, P)
            
            # commitment * public_key^c mod P
            pk_c = pow(pk, challenge, P)
            right = (comm * pk_c) % P
            
            return left == right
        except Exception as e:
            logger.error(f"ZKP Verification error: {e}")
            return False

class FirmwareAttestor:
    """
    Uses Pedersen Commitments to prove firmware version matches expected
    without revealing the exact hash to all peers (only to auditors).
    """
    def __init__(self, firmware_hash: str):
        self.firmware_int = int(hashlib.sha256(firmware_hash.encode()).hexdigest(), 16) % Q
        self.commitment, self.blinding_factor = PedersenCommitment.commit(self.firmware_int)

    def get_attestation_bundle(self) -> Dict[str, Any]:
        return {
            "commitment": self.commitment,
            # Blinding factor is NOT shared except during audit
        }

    def prove_firmware_match(self, expected_hash: str) -> bool:
        """Simple verification if blinding factor is known."""
        expected_int = int(hashlib.sha256(expected_hash.encode()).hexdigest(), 16) % Q
        return PedersenCommitment.verify(self.commitment, expected_int, self.blinding_factor)

class BatchZKPVerifier:
    """
    Optimized verifier for 10k nodes.
    Supports batching proofs to reduce verification time.
    
    Uses batch verification optimization for Schnorr proofs:
    Instead of verifying n individual proofs, we verify:
    prod(G^s_i) == prod(R_i * pk_i^c_i)
    
    This reduces from n exponentiations to a single multi-exponentiation.
    """
    
    @staticmethod
    def verify_batch(proofs: List[Dict[str, Any]], message: str = "") -> Dict[str, bool]:
        """
        Verify a batch of proofs individually.
        
        For small batches or when individual results are needed.
        """
        results = {}
        for proof in proofs:
            results[proof["node_id"]] = NIZKPAttestor.verify_identity_proof(proof, message)
        return results
    
    @staticmethod
    def verify_batch_optimized(proofs: List[Dict[str, Any]], message: str = "") -> Tuple[bool, Optional[str]]:
        """
        Optimized batch verification using Schnorr batch property.
        
        For large batches (1000+ nodes), this is significantly faster
        than individual verification.
        
        The batch equation is:
        G^sum(s_i) = prod(R_i) * prod(pk_i^c_i) mod P
        
        Args:
            proofs: List of NIZKP proofs
            message: Shared message for all proofs
            
        Returns:
            Tuple of (all_valid: bool, failed_node_id: Optional[str])
            If all_valid is False, failed_node_id contains the first failing node.
        """
        if not proofs:
            return True, None
        
        # For small batches, individual verification is fine
        if len(proofs) < 100:
            results = BatchZKPVerifier.verify_batch(proofs, message)
            failed = [nid for nid, valid in results.items() if not valid]
            if failed:
                return False, failed[0]
            return True, None
        
        # Optimized batch verification for large batches
        # We use random linear combination for security
        
        sum_s = 0
        prod_R = 1
        prod_pk_c = 1
        
        # Use deterministic random weights for the batch
        # This prevents a malicious prover from crafting proofs that cancel out
        weights = [secrets.randbelow(Q - 1) + 1 for _ in proofs]
        
        for i, proof in enumerate(proofs):
            try:
                node_id = proof["node_id"]
                pk = proof["public_key"]
                comm = proof["commitment"]
                resp = proof["response"]
                
                # Recompute challenge
                challenge_input = f"{G}{pk}{comm}{message}{node_id}".encode()
                challenge = int(hashlib.sha256(challenge_input).hexdigest(), 16) % Q
                
                w = weights[i]
                
                # Accumulate weighted values
                sum_s = (sum_s + w * resp) % Q
                prod_R = (prod_R * pow(comm, w, P)) % P
                prod_pk_c = (prod_pk_c * pow(pk, challenge * w, P)) % P
                
            except (KeyError, TypeError) as e:
                logger.error(f"Invalid proof format for node {proof.get('node_id', 'unknown')}: {e}")
                return False, proof.get("node_id", "unknown")
        
        # Verify: G^sum_s == prod_R * prod_pk_c mod P
        left = pow(G, sum_s, P)
        right = (prod_R * prod_pk_c) % P
        
        if left == right:
            return True, None
        
        # Batch failed - fall back to individual verification to find culprit
        logger.warning("Batch verification failed, falling back to individual verification")
        results = BatchZKPVerifier.verify_batch(proofs, message)
        failed = [nid for nid, valid in results.items() if not valid]
        if failed:
            return False, failed[0]
        
        # This shouldn't happen - batch failed but individual all passed
        logger.error("Batch verification inconsistency detected")
        return False, "batch_inconsistency"
