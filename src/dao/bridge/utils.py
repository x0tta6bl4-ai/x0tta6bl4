"""
Utility functions for Token Bridge data safety and formatting.
"""
from __future__ import annotations
import hashlib
from typing import Any, Dict, List, Optional


def _safe_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _safe_numeric_mapping_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    numeric_values = [
        float(v)
        for v in data.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    return {
        "count": len(data),
        "min": min(numeric_values) if numeric_values else None,
        "max": max(numeric_values) if numeric_values else None,
        "sum": sum(numeric_values) if numeric_values else None,
        "keys_redacted": True,
    }


def _safe_value(key: str, value: Any, depth: int = 0) -> Any:
    key_lower = str(key).lower()
    blocked_fragments = ("secret", "password", "token", "key", "private")
    identifier_fragments = (
        "address", "did", "escrow", "listing", "mesh", "node", "renter", "spiffe", "wallet",
    )
    if any(fragment in key_lower for fragment in blocked_fragments):
        return "<redacted>"
    if any(fragment in key_lower for fragment in identifier_fragments):
        return _safe_identifier(value)
    if key_lower in {"rewards", "uptimes"} and isinstance(value, dict):
        return _safe_numeric_mapping_summary(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict) and depth < 3:
        return {
            str(child_key): _safe_value(str(child_key), child_value, depth + 1)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list) and depth < 3:
        return [_safe_value(key, item, depth + 1) for item in value]
    return str(value)


def _safe_context(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        str(key): _safe_value(str(key), value)
        for key, value in context.items()
    }


def _chain_write_result_summary(
    *,
    success: Optional[bool],
    transaction_hash: Optional[str],
    simulated: Optional[bool],
) -> Dict[str, Any]:
    return {
        "success": bool(success),
        "transaction_hash_present": bool(transaction_hash),
        "transaction_hash_sha256": _safe_identifier(transaction_hash),
        "simulated": bool(simulated),
        "raw_hash_redacted": True,
    }

