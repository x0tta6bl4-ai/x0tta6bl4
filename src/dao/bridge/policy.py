"""
Policy evaluation for Token Bridge.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Tuple

from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)

logger = logging.getLogger(__name__)


def _policy_allowed(decision: Any) -> bool:
    return normalize_policy_allowed(decision)


def _policy_reason(decision: Any) -> str:
    return normalize_policy_reason(decision)


def _policy_rules(decision: Any) -> list[str]:
    return normalize_policy_rules(decision)


def evaluate_bridge_policy(
    policy_engine: Any,
    spiffe_id: str,
    operation: str,
    workload_type: str = "token-bridge",
) -> Tuple[bool, Any, str]:
    if policy_engine is None:
        return True, None, ""
        
    if not spiffe_id:
        return False, None, "TokenBridge SPIFFE identity is required for policy evaluation"
        
    try:
        decision = policy_engine.evaluate(
            spiffe_id,
            resource=f"dao:token_bridge:{operation}",
            workload_type=workload_type,
        )
    except Exception as exc:
        return False, None, f"TokenBridge policy evaluation failed: {exc}"
        
    if not _policy_allowed(decision):
        return False, decision, _policy_reason(decision) or "TokenBridge policy denied operation"
        
    return True, decision, _policy_reason(decision)

