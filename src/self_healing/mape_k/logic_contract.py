"""
Logic Contract for x0tta6bl4 Self-Healing.
Implements formal invariant checks for the MAPE-K loop.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class FormalState(Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COOLDOWN = "COOLDOWN"
    SAFE_MODE = "SAFE_MODE"

@dataclass(frozen=True)
class LogicViolation:
    invariant_id: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

class SelfHealingLogicContract:
    """
    Formal logic gate for MAPE-K transitions.
    Mirroring AlphaProof Nexus Lean-style verification.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.current_state = FormalState.IDLE
        self.violations: List[LogicViolation] = []

    def check_transition(self, next_state: FormalState, context: Dict[str, Any]) -> bool:
        """
        Verifies if the transition to next_state is logically sound.
        """
        # I1: Invariant_No_Concurrent_Recovery
        if next_state == FormalState.EXECUTING:
            if context.get("pending_verification"):
                self._record_violation(
                    "I1", "Concurrent recovery detected", context
                )
                return False

        # I2: Invariant_CoolDown_Enforced
        if next_state == FormalState.EXECUTING:
            cooldown_active = context.get("cooldown_active", False)
            if cooldown_active:
                self._record_violation(
                    "I2", "Action executed during active cooldown", context
                )
                return False

        # State machine transition rules
        allowed_transitions = {
            FormalState.IDLE: {FormalState.ANALYZING, FormalState.VERIFYING, FormalState.SAFE_MODE},
            FormalState.ANALYZING: {FormalState.PLANNING, FormalState.SAFE_MODE},
            FormalState.PLANNING: {FormalState.IDLE, FormalState.EXECUTING, FormalState.SAFE_MODE},
            FormalState.EXECUTING: {FormalState.IDLE, FormalState.VERIFYING, FormalState.SAFE_MODE},
            FormalState.VERIFYING: {FormalState.IDLE, FormalState.COOLDOWN, FormalState.SAFE_MODE},
            FormalState.COOLDOWN: {FormalState.IDLE, FormalState.SAFE_MODE},
            FormalState.SAFE_MODE: {FormalState.IDLE},  # Only manual override
        }

        if next_state not in allowed_transitions.get(self.current_state, set()):
            self._record_violation(
                "ASM_VALIDATION",
                f"Invalid state transition: {self.current_state} -> {next_state}",
                context
            )
            return False

        return True

    def _record_violation(self, inv_id: str, msg: str, ctx: Dict[str, Any]):
        violation = LogicViolation(inv_id, msg, ctx)
        self.violations.append(violation)
        logger.critical("LOGIC VIOLATION [%s]: %s", inv_id, msg)
        # In a real Nexus pipeline, this would trigger a Lean proof failure

    def transition_to(self, next_state: FormalState, context: Dict[str, Any]):
        if self.check_transition(next_state, context):
            logger.debug("Logic Gate: Transitioning %s -> %s", self.current_state, next_state)
            # Use object.__setattr__ because we might want to make it even more strict
            self.__dict__['current_state'] = next_state
        else:
            logger.critical("Logic Gate: Transition BLOCKED. Entering SAFE_MODE.")
            self.__dict__['current_state'] = FormalState.SAFE_MODE

    def is_in_safe_mode(self) -> bool:
        return self.current_state == FormalState.SAFE_MODE

    def get_proof_fragment(self) -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.formal_proof.fragment.v1",
            "node_id": self.node_id,
            "current_state": self.current_state.value,
            "violations_total": len(self.violations),
            "safe_mode": self.is_in_safe_mode(),
            "claim_boundary": "AlphaProof Nexus formal state evidence."
        }
