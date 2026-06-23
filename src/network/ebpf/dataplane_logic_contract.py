"""
Dataplane Logic Contract for x0tta6bl4.
Enforces formal invariants D1-D3 for eBPF/XDP stability.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class DataplaneFormalState(Enum):
    DETACHED = "DETACHED"
    COMPILING = "COMPILING"
    STAGED = "STAGED"
    ATTACHING = "ATTACHING"
    ATTACHED = "ATTACHED"
    LOAD_FAILURE = "LOAD_FAILURE"

class DataplaneLogicContract:
    """
    Formal logic gate for eBPF Dataplane operations.
    Prevents inconsistent datapath states.
    """

    def __init__(self, interface: str):
        self.interface = interface
        self.current_state = DataplaneFormalState.DETACHED
        self.violations: List[str] = []

    def check_transition(self, next_state: DataplaneFormalState, context: Dict[str, Any]) -> bool:
        """
        Verifies if the dataplane transition is logically sound.
        """
        # D1: Invariant_Atomic_Swap
        if next_state == DataplaneFormalState.ATTACHING:
            if not context.get("bcc_ready"):
                self._record_violation("D1", "Attempted attach without successful BCC compilation", context)
                return False

        # D2: Invariant_Map_Consistency
        if next_state == DataplaneFormalState.ATTACHED:
            if context.get("map_sync_failed"):
                self._record_violation("D2", "Dataplane attached but map sync is inconsistent", context)
                return False

        allowed = {
            DataplaneFormalState.DETACHED: {DataplaneFormalState.COMPILING, DataplaneFormalState.LOAD_FAILURE},
            DataplaneFormalState.COMPILING: {DataplaneFormalState.STAGED, DataplaneFormalState.LOAD_FAILURE},
            DataplaneFormalState.STAGED: {DataplaneFormalState.ATTACHING, DataplaneFormalState.LOAD_FAILURE},
            DataplaneFormalState.ATTACHING: {DataplaneFormalState.ATTACHED, DataplaneFormalState.LOAD_FAILURE},
            DataplaneFormalState.ATTACHED: {DataplaneFormalState.DETACHED},
            DataplaneFormalState.LOAD_FAILURE: {DataplaneFormalState.DETACHED},
        }

        if next_state not in allowed.get(self.current_state, set()):
            self._record_violation("DP_ASM_VAL", f"Invalid Dataplane transition: {self.current_state} -> {next_state}", context)
            return False

        return True

    def _record_violation(self, inv_id: str, msg: str, ctx: Dict[str, Any]):
        violation = f"[{inv_id}] {msg}"
        self.violations.append(violation)
        logger.critical("DATAPLANE LOGIC VIOLATION: %s", violation)

    def transition_to(self, next_state: DataplaneFormalState, context: Dict[str, Any]):
        if self.check_transition(next_state, context):
            logger.debug("Dataplane Logic Gate: %s -> %s", self.current_state, next_state)
            self.current_state = next_state
        else:
            logger.critical("Dataplane Logic Gate: Transition BLOCKED. Entering LOAD_FAILURE.")
            self.current_state = DataplaneFormalState.LOAD_FAILURE

    def get_dataplane_proof_fragment(self) -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.dataplane_proof.fragment.v1",
            "interface": self.interface,
            "current_state": self.current_state.value,
            "violations": self.violations,
            "claim_boundary": "AlphaProof Nexus eBPF dataplane state evidence."
        }
