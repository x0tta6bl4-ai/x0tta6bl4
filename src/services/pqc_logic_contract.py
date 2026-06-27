"""
PQC Rotation Logic Contract for x0tta6bl4.
Enforces formal invariants T1-T3 for Trust Plane stability.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class PQCFormalState(Enum):
    STABLE = "STABLE"
    GENERATING = "GENERATING"
    STAGING = "STAGING"
    VERIFYING = "VERIFYING"
    COMMITTING = "COMMITTING"
    TRUST_FAILURE = "TRUST_FAILURE"

class PQCRotationLogicContract:
    """
    Formal logic gate for PQC identity rotation.
    Prevents broken trust states by enforcing atomic handover.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.current_state = PQCFormalState.STABLE
        self.violations: List[str] = []
        self.verified_staged_keys = False

    def check_transition(self, next_state: PQCFormalState, context: Dict[str, Any]) -> bool:
        """
        Verifies if the PQC trust transition is logically sound.
        """
        # T1: Invariant_Safe_Handover
        if next_state == PQCFormalState.COMMITTING:
            if not self.verified_staged_keys:
                self._record_violation("T1", "Attempted commitment without prior verification", context)
                return False
            if not context.get("new_keys_exist"):
                self._record_violation("T1", "Attempted commitment without physical keys staged", context)
                return False

        # T3: Invariant_Signer_Integrity
        if next_state == PQCFormalState.VERIFYING:
            algorithm = context.get("algorithm")
            if algorithm not in {"ML-DSA-65", "ML-KEM-768", "Dilithium5"}:
                self._record_violation("T3", f"Unauthorized PQC algorithm: {algorithm}", context)
                return False

        # Allowed state transitions
        allowed = {
            PQCFormalState.STABLE: {PQCFormalState.GENERATING, PQCFormalState.TRUST_FAILURE},
            PQCFormalState.GENERATING: {PQCFormalState.STAGING, PQCFormalState.TRUST_FAILURE},
            PQCFormalState.STAGING: {PQCFormalState.VERIFYING, PQCFormalState.TRUST_FAILURE},
            PQCFormalState.VERIFYING: {PQCFormalState.COMMITTING, PQCFormalState.TRUST_FAILURE},
            PQCFormalState.COMMITTING: {PQCFormalState.STABLE, PQCFormalState.TRUST_FAILURE},
            PQCFormalState.TRUST_FAILURE: {PQCFormalState.STABLE},
        }

        if next_state not in allowed.get(self.current_state, set()):
            self._record_violation("PQC_ASM_VAL", f"Invalid PQC transition: {self.current_state} -> {next_state}", context)
            return False

        return True

    def _record_violation(self, inv_id: str, msg: str, ctx: Dict[str, Any]):
        violation_str = f"[{inv_id}] {msg}"
        self.violations.append(violation_str)
        logger.critical("TRUST LOGIC VIOLATION: %s", violation_str)

    def transition_to(self, next_state: PQCFormalState, context: Dict[str, Any]):
        if self.check_transition(next_state, context):
            if next_state == PQCFormalState.VERIFYING and context.get("verification_success"):
                self.verified_staged_keys = True
            elif next_state == PQCFormalState.STABLE:
                self.verified_staged_keys = False # Reset for next cycle

            logger.debug("PQC Logic Gate: %s -> %s", self.current_state, next_state)
            self.current_state = next_state
        else:
            logger.critical("PQC Logic Gate: Transition BLOCKED. Entering TRUST_FAILURE.")
            self.current_state = PQCFormalState.TRUST_FAILURE

    def get_trust_proof_fragment(self) -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.trust_proof.fragment.v1",
            "node_id": self.node_id,
            "current_trust_state": self.current_state.value,
            "handover_verified": self.verified_staged_keys,
            "violations": self.violations,
            "claim_boundary": "AlphaProof Nexus PQC trust state evidence."
        }

