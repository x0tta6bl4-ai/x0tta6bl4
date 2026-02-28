"""
Anti-Delos Charter Policy Validator and Metric Enforcer.


Implements DAO-governed privacy policy enforcement:
- Load and validate YAML charter policies
- Allow/block metrics based on whitelist/blacklist
- Track violation events with severity escalation
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

_VIOLATION_THRESHOLD_HIGH = 3
_VIOLATION_THRESHOLD_CRITICAL = 5


class CharterPolicyValidator:
    def __init__(self, policy_data: Dict[str, Any]):
        self.policy_data = policy_data

    @staticmethod
    def load_policy(policy_path: str) -> Dict[str, Any]:
        """Load a charter policy from a YAML file."""
        path = Path(policy_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")
        with open(path) as f:
            return yaml.safe_load(f)

    @staticmethod
    def validate_policy(policy: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate policy structure. Returns (is_valid, errors)."""
        errors = []
        required_keys = ["charter", "whitelisted_metrics", "forbidden_metrics"]
        for key in required_keys:
            if key not in policy:
                errors.append(f"Missing required key: {key}")
        return len(errors) == 0, errors

    @staticmethod
    def get_whitelisted_metrics(policy: Dict[str, Any]) -> List[str]:
        """Return the list of whitelisted metric names (flattened from categories)."""
        wl = policy.get("whitelisted_metrics", [])
        if isinstance(wl, dict):
            result: List[str] = []
            for metrics in wl.values():
                result.extend(metrics)
            return result
        return list(wl)

    @staticmethod
    def get_forbidden_metrics(policy: Dict[str, Any]) -> List[str]:
        """Return the list of forbidden metric names."""
        return list(policy.get("forbidden_metrics", []))

    @staticmethod
    def is_metric_allowed(
        policy: Dict[str, Any], metric_name: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if a metric is allowed by policy.

        Returns (is_allowed, reason):
          - (True, None) if whitelisted
          - (False, "FORBIDDEN_METRIC") if explicitly forbidden
          - (False, "NOT_WHITELISTED") if not in whitelist
        """
        forbidden = set(policy.get("forbidden_metrics", []))
        whitelisted = set(CharterPolicyValidator.get_whitelisted_metrics(policy))
        if metric_name in forbidden:
            return False, "FORBIDDEN_METRIC"
        if metric_name in whitelisted:
            return True, None
        return False, "NOT_WHITELISTED"

    @staticmethod
    def policy_to_json(policy: Dict[str, Any]) -> str:
        """Serialize policy to a JSON string."""
        return json.dumps(policy, indent=2)

    @staticmethod
    def validate_metric_schema(metrics: List[str]) -> List[str]:
        """Validate a list of metric names. Returns list of error strings."""
        errors = []
        for metric in metrics:
            if not isinstance(metric, str):
                errors.append(f"Metric name must be a string, got: {type(metric)}")
            elif not metric.strip():
                errors.append("Metric name cannot be empty")
        return errors

    @staticmethod
    def validate_access_control(ac: Dict[str, Any]) -> List[str]:
        """Validate access control structure. Returns list of error strings."""
        errors = []
        if not ac:
            errors.append("Access control section is empty")
            return errors
        for role_entry in ac.get("read_access", []):
            if "role" not in role_entry:
                errors.append("Access control entry missing 'role' field")
        return errors

    @staticmethod
    def validate_violation_policy(vp: Dict[str, Any]) -> List[str]:
        """Validate violation policy structure. Returns list of error strings."""
        errors = []
        if not vp:
            errors.append("Violation policy section is empty")
            return errors
        levels = vp.get("levels", [])
        if not levels:
            errors.append("Violation policy has no levels defined")
        for level in levels:
            if "name" not in level:
                errors.append("Violation level missing 'name' field")
            if "threshold" not in level:
                errors.append("Violation level missing 'threshold' field")
            if "action" not in level:
                errors.append("Violation level missing 'action' field")
        return errors

    @staticmethod
    def generate_validation_report(policy: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive validation report for the policy."""
        is_valid, errors = CharterPolicyValidator.validate_policy(policy)
        charter = policy.get("charter", {})
        metadata = charter.get("metadata", {})

        whitelisted = CharterPolicyValidator.get_whitelisted_metrics(policy)
        forbidden = CharterPolicyValidator.get_forbidden_metrics(policy)

        ac = policy.get("access_control", {})
        vp = policy.get("violation_policy", {})

        violation_levels = [
            {
                "name": level.get("name"),
                "threshold": level.get("threshold"),
                "action": level.get("action"),
            }
            for level in vp.get("levels", [])
        ]

        recommendations = []
        if not policy.get("whistleblower_policy"):
            recommendations.append("Add whistleblower policy")
        if not policy.get("emergency_override"):
            recommendations.append("Add emergency override policy")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "policy_name": charter.get("name", "unknown"),
            "environment": metadata.get("environment", "unknown"),
            "overall_status": "PASS" if is_valid else "FAIL",
            "total_errors": len(errors),
            "errors": errors,
            "metrics": {
                "whitelisted": len(whitelisted),
                "forbidden": len(forbidden),
            },
            "access_control": {
                "roles_count": len(ac.get("read_access", [])),
                "roles": [r.get("role") for r in ac.get("read_access", [])],
            },
            "violation_levels": violation_levels,
            "has_whistleblower_policy": "whistleblower_policy" in policy,
            "has_emergency_override": "emergency_override" in policy,
            "recommendations": recommendations,
        }

    @staticmethod
    def compare_policies(
        policy1: Dict[str, Any], policy2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two policies and return a comparison report."""
        wl1 = set(CharterPolicyValidator.get_whitelisted_metrics(policy1))
        wl2 = set(CharterPolicyValidator.get_whitelisted_metrics(policy2))

        fb1 = set(CharterPolicyValidator.get_forbidden_metrics(policy1))
        fb2 = set(CharterPolicyValidator.get_forbidden_metrics(policy2))

        charter1 = policy1.get("charter", {})
        charter2 = policy2.get("charter", {})

        added = sorted(wl2 - wl1)
        removed = sorted(wl1 - wl2)
        unchanged = sorted(wl1 & wl2)

        fb_added = sorted(fb2 - fb1)
        fb_removed = sorted(fb1 - fb2)
        fb_unchanged = sorted(fb1 & fb2)

        return {
            "policy1_name": charter1.get("name", "unknown"),
            "policy2_name": charter2.get("name", "unknown"),
            "metrics": {
                "added": added,
                "removed": removed,
                "unchanged": unchanged,
            },
            "forbidden_metrics": {
                "added": fb_added,
                "removed": fb_removed,
                "unchanged": fb_unchanged,
            },
            "versions": {
                "policy1": charter1.get("version"),
                "policy2": charter2.get("version"),
            },
            "environments": {
                "policy1": charter1.get("metadata", {}).get("environment"),
                "policy2": charter2.get("metadata", {}).get("environment"),
            },
            "is_identical_metrics": len(added) == 0 and len(removed) == 0,
            "is_identical_forbidden": len(fb_added) == 0 and len(fb_removed) == 0,
        }


class MetricEnforcer:
    """Enforce charter metric policy: block forbidden metrics, track violations."""

    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self._forbidden: set = set(policy.get("forbidden_metrics", []))
        self._violation_log: List[Dict[str, Any]] = []
        # metric_name -> {"count": int, "event": dict or None}
        self._violation_events: Dict[str, Dict[str, Any]] = {}

    def validate_metric(self, metric: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single metric. Logs every call; tracks repeated violations."""
        name = metric.get("metric_name", "unknown")
        timestamp = metric.get("timestamp")
        source = metric.get("source")

        errors: List[str] = []

        # Check required fields
        for field in ["value", "timestamp", "source"]:
            if field not in metric:
                errors.append(f"Missing required field: {field}")

        # Validate timestamp format if present
        if timestamp is not None:
            try:
                datetime.fromisoformat(str(timestamp))
            except (ValueError, TypeError):
                errors.append(f"Invalid timestamp format: {timestamp}")

        is_valid = len(errors) == 0
        is_forbidden = name in self._forbidden
        allowed = not is_forbidden
        action = "BLOCK" if is_forbidden else "ALLOW"

        # Log every attempt
        self._violation_log.append(
            {
                "metric_name": name,
                "timestamp": timestamp,
                "source": source,
                "action": action,
            }
        )

        # Update violation event tracking for forbidden metrics
        if is_forbidden:
            entry = self._violation_events.setdefault(
                name, {"count": 0, "event": None}
            )
            entry["count"] += 1
            count = entry["count"]

            if count >= _VIOLATION_THRESHOLD_CRITICAL:
                entry["event"] = {
                    "metric_name": name,
                    "attempt_count": count,
                    "severity": "CRITICAL",
                    "recommended_action": "IMMEDIATE_SHUTDOWN",
                }
            elif count >= _VIOLATION_THRESHOLD_HIGH:
                entry["event"] = {
                    "metric_name": name,
                    "attempt_count": count,
                    "severity": "HIGH",
                    "recommended_action": "ESCALATE_TO_DAO",
                }

        result: Dict[str, Any] = {
            "is_valid": is_valid,
            "allowed": allowed,
            "enforcement_action": action,
            "errors": errors,
        }
        if is_forbidden:
            result["reason"] = "FORBIDDEN_METRIC"
        return result

    def validate_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of metrics."""
        results = [self.validate_metric(m) for m in metrics]
        passed = sum(1 for r in results if r["allowed"])
        blocked = sum(1 for r in results if not r["allowed"])
        return {
            "total_metrics": len(metrics),
            "passed": passed,
            "blocked": blocked,
            "all_valid": blocked == 0,
        }

    def reset_logs(self) -> None:
        """Reset violation log and event tracking."""
        self._violation_log = []
        self._violation_events = {}

    def get_violation_log(self) -> List[Dict[str, Any]]:
        """Return all logged metric validation attempts."""
        return self._violation_log

    def get_violation_events(self) -> List[Dict[str, Any]]:
        """Return violation events (only for metrics with 3+ attempts)."""
        return [
            entry["event"]
            for entry in self._violation_events.values()
            if entry["event"] is not None
        ]
