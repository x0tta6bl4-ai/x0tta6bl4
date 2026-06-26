"""
Utility functions for MAPE-K Self-Healing.
"""
from __future__ import annotations
import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

def _safe_numeric_summary(values: Dict[str, Any]) -> Dict[str, float]:
    return {
        str(key): round(float(value), 4)
        for key, value in values.items()
        if isinstance(value, (int, float))
    }

def _safe_metric_keys(values: Dict[str, Any]) -> List[str]:
    return sorted(str(key) for key in values.keys())

def _safe_issue_summary(issue: str) -> Dict[str, Any]:
    known = {
        "Healthy",
        "High CPU",
        "High Memory",
        "High Packet Loss",
        "Network Loss",
        "Custom Anomaly",
        "GraphSAGE Anomaly",
        "Predicted Peak",
    }
    issue_text = str(issue or "")
    return {
        "category": issue_text if issue_text in known else "[redacted]",
        "sha256": _sha256_text(issue_text),
        "redacted": issue_text not in known,
    }

def _safe_action_summary(action: str) -> Dict[str, Any]:
    action_text = str(action or "")
    known = {
        "No action needed",
        "Restart service",
        "Restart service/process",
        "Free memory / restart service",
        "Switch route",
        "Scale up",
        "Custom Action",
    }
    return {
        "category": action_text if action_text in known else "[redacted]",
        "length": len(action_text),
        "sha256": _sha256_text(action_text),
        "redacted": action_text not in known,
    }

def _safe_monitor_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        issue = str(result.get("issue", ""))
        return {
            "anomaly_detected": bool(result.get("anomaly_detected", False)),
            "scaling_recommended": bool(result.get("scaling_recommended", False)),
            "issue": _safe_issue_summary(issue),
            "keys": sorted(str(key) for key in result.keys()),
            "values_redacted": True,
        }
    return {
        "anomaly_detected": bool(result),
        "values_redacted": True,
    }

def _safe_downstream_evidence(
    event_ids: Optional[List[str]] = None,
    *,
    source_agent: str = "recovery-action-executor",
    limit: int = 10,
) -> Dict[str, Any]:
    safe_event_ids = [str(event_id) for event_id in (event_ids or []) if event_id]
    return {
        "source_agents": [source_agent] if safe_event_ids else [],
        "event_ids": safe_event_ids[-limit:],
        "events_total": len(safe_event_ids),
        "event_ids_limit": limit,
        "event_ids_truncated": len(safe_event_ids) > limit,
        "payloads_redacted": True,
    }

