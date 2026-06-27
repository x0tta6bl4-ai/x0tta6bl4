"""Normalize policy decisions across the repo's policy engines."""

from __future__ import annotations

from typing import Any, List


_ALLOW_VALUES = {"allow", "allowed", "permit", "permitted", "audit"}
_DENY_VALUES = {"deny", "denied", "block", "blocked", "reject", "rejected", "challenge"}


def _decision_value(value: Any) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        value = enum_value
    return str(value).strip().lower()


def _effect_allows(value: Any) -> bool | None:
    normalized = _decision_value(value)
    if normalized in _ALLOW_VALUES:
        return True
    if normalized in _DENY_VALUES:
        return False
    return None


def policy_allowed(decision: Any) -> bool:
    """Return a fail-closed boolean for known policy decision shapes."""
    if decision is None:
        return False

    if isinstance(decision, dict):
        if "allowed" in decision:
            return bool(decision["allowed"])
        for key in ("effect", "action", "decision"):
            if key in decision:
                allowed = _effect_allows(decision[key])
                if allowed is not None:
                    return allowed
        return bool(decision)

    if hasattr(decision, "allowed"):
        return bool(decision.allowed)

    for attr in ("effect", "action", "decision"):
        if hasattr(decision, attr):
            allowed = _effect_allows(getattr(decision, attr))
            if allowed is not None:
                return allowed

    return bool(decision)


def policy_reason(decision: Any) -> str:
    if decision is None:
        return ""
    if isinstance(decision, dict):
        for key in ("reason", "detail", "message", "error"):
            if decision.get(key):
                return str(decision[key])
        return ""
    return str(getattr(decision, "reason", "") or "")


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def policy_rules(decision: Any) -> List[str]:
    if decision is None:
        return []
    if isinstance(decision, dict):
        for key in ("matched_rules", "rules"):
            if key in decision:
                return _as_list(decision[key])
        return _as_list(decision.get("rule_id"))
    rules = getattr(decision, "matched_rules", None)
    if rules:
        return _as_list(rules)
    return _as_list(getattr(decision, "rule_id", None))
