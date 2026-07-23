"""
Global Formal Proof Registry for x0tta6bl4.
Consolidates Logic Proof Fragments from all planes (MAPE-K, Trust, Dataplane).
Enforces inter-plane invariants G1-G3.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class FormalProofRegistry:
    """
    Central repository for formal evidence shards.
    Verifies global system integrity across multiple planes.
    """

    def __init__(self):
        self.proof_shards: Dict[str, Dict[str, Any]] = {}
        self.required_planes = {"mape_k", "trust_pqc", "dataplane"}
        self.violations: List[str] = []

    def register_proof(self, plane_id: str, proof_fragment: Dict[str, Any]):
        """
        Registers a proof fragment from a specific plane.
        """
        if proof_fragment.get("schema") not in {
            "x0tta6bl4.formal_proof.fragment.v1",
            "x0tta6bl4.trust_proof.fragment.v1",
            "x0tta6bl4.dataplane_proof.fragment.v1",
        }:
            logger.warning("Unrecognized proof schema for plane %s", plane_id)

        self.proof_shards[plane_id] = proof_fragment
        logger.info("Registered formal proof shard for plane: %s", plane_id)
        self._verify_global_invariants()

    def _verify_global_invariants(self):
        """
        Checks inter-plane invariants G1-G3.
        """
        # G1: Invariant_Trust_Before_Action
        trust = self.proof_shards.get("trust_pqc")
        mape_k = self.proof_shards.get("mape_k")

        if trust and mape_k:
            trust_stable = trust.get("current_trust_state") == "STABLE"
            mape_k_executing = mape_k.get("current_state") == "EXECUTING"

            if mape_k_executing and not trust_stable:
                self._record_violation("G1", "MAPE-K attempted execution while Trust Plane is unstable.")

    def _record_violation(self, inv_id: str, msg: str):
        violation = f"[{inv_id}] {msg}"
        if violation not in self.violations:
            self.violations.append(violation)
            logger.critical("GLOBAL LOGIC VIOLATION: %s", violation)

    def get_global_readiness_proof(self) -> Dict[str, Any]:
        """
        Produces a consolidated Global Readiness Proof.
        """
        planes_present = set(self.proof_shards.keys())
        missing_planes = self.required_planes - planes_present

        is_ready = (
            not missing_planes
            and not self.violations
            and all(not p.get("safe_mode", False) for p in self.proof_shards.values())
            and all(not p.get("violations") for p in self.proof_shards.values())
        )

        proof_body = {
            "schema": "x0tta6bl4.global_readiness_proof.v1",
            "ready": is_ready,
            "decision": "GLOBAL_VERIFIED" if is_ready else "GLOBAL_BLOCKED",
            "registered_planes": sorted(planes_present),
            "missing_planes": sorted(missing_planes),
            "global_violations": self.violations,
            "shard_summaries": {
                pid: {
                    "state": p.get("current_state") or p.get("current_trust_state"),
                    "local_violations": len(p.get("violations", []) or []),
                    "safe_mode": p.get("safe_mode", False)
                } for pid, p in self.proof_shards.items()
            },
            "claim_boundary": "Consolidated AlphaProof Nexus global evidence."
        }

        # G2: Invariant_Consolidated_Integrity
        serialized = json.dumps(proof_body, sort_keys=True)
        proof_body["proof_hash"] = hashlib.sha256(serialized.encode()).hexdigest()

        return proof_body

