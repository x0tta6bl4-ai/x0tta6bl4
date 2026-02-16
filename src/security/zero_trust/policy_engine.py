"""
Advanced Policy Engine for Zero Trust

Provides fine-grained policy enforcement using rule-based engine.
Now includes OPA/Rego integration, dynamic policy updates, and versioning.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# OPA integration (optional)
try:
    import requests

    OPA_AVAILABLE = True
except ImportError:
    OPA_AVAILABLE = False
    logger.warning("requests library not available, OPA integration disabled")


class PolicyAction(Enum):
    """Policy actions"""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log


class PolicyCondition(Enum):
    """Policy conditions"""

    TIME_BASED = "time_based"  # Time of day restrictions
    RESOURCE_BASED = "resource_based"  # Resource access restrictions
    RATE_LIMIT = "rate_limit"  # Rate limiting
    GEOGRAPHIC = "geographic"  # Geographic restrictions
    WORKLOAD_TYPE = "workload_type"  # Workload type restrictions


@dataclass
class PolicyRule:
    """A single policy rule"""

    rule_id: str
    name: str
    action: PolicyAction
    conditions: List[PolicyCondition] = field(default_factory=list)
    spiffe_id_pattern: Optional[str] = (
        None  # Pattern matching (e.g., "spiffe://domain/workload/*")
    )
    allowed_resources: Optional[List[str]] = None
    time_window: Optional[Dict[str, str]] = None  # {"start": "09:00", "end": "17:00"}
    rate_limit: Optional[Dict[str, int]] = None  # {"requests_per_minute": 100}
    priority: int = 100  # Higher priority = evaluated first
    enabled: bool = True
    version: int = 1  # Policy version
    opa_policy: Optional[str] = None  # Rego policy string (for OPA integration)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PolicyDecision:
    """Result of policy evaluation"""

    allowed: bool
    action: PolicyAction
    matched_rules: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    audit_log: bool = False


class PolicyEngine:
    """
    Advanced Policy Engine for Zero Trust.

    Provides:
    - Rule-based policy evaluation
    - Time-based access control
    - Resource-based permissions
    - Rate limiting
    - Audit logging
    - OPA (Open Policy Agent) integration for Rego policies
    - Dynamic policy updates
    - Policy versioning
    - Advanced rule conditions
    """

    def __init__(
        self,
        default_action: PolicyAction = PolicyAction.DENY,
        opa_endpoint: Optional[str] = None,
        enable_opa: bool = True,
    ):
        """
        Initialize Policy Engine.

        Args:
            default_action: Default action if no rules match (default: DENY for security)
            opa_endpoint: OPA server endpoint (e.g., "http://localhost:8181")
            enable_opa: Enable OPA integration if available
        """
        self.default_action = default_action
        self.rules: List[PolicyRule] = []
        self.rate_limit_tracker: Dict[str, List[datetime]] = (
            {}
        )  # spiffe_id -> [timestamps]
        self.audit_log: List[Dict[str, Any]] = []

        # OPA integration
        self.opa_endpoint = opa_endpoint or "http://localhost:8181"
        self.enable_opa = enable_opa and OPA_AVAILABLE

        # Policy versioning
        self.policy_versions: Dict[str, List[PolicyRule]] = {}  # rule_id -> [versions]
        self.current_versions: Dict[str, int] = {}  # rule_id -> current version

        # Dynamic update tracking
        self.update_callbacks: List[Callable[[PolicyRule], None]] = []

        # Load default policies
        self._load_default_policies()

        logger.info(
            f"Policy Engine initialized with {len(self.rules)} rules (default: {default_action.value}, OPA: {self.enable_opa})"
        )

    def _load_default_policies(self):
        """Load default security policies."""
        # Default: Allow all within trust domain (can be restricted)
        default_allow = PolicyRule(
            rule_id="default_allow",
            name="Default Allow Within Trust Domain",
            action=PolicyAction.ALLOW,
            priority=1,
            enabled=True,
        )
        self.add_rule(default_allow)

    def add_rule(self, rule: PolicyRule):
        """
        Add a policy rule.

        Args:
            rule: Policy rule to add
        """
        self.rules.append(rule)
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added policy rule: {rule.name} (priority: {rule.priority})")

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a policy rule.

        Args:
            rule_id: ID of rule to remove

        Returns:
            True if rule was removed
        """
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        removed = len(self.rules) < initial_count
        if removed:
            logger.info(f"Removed policy rule: {rule_id}")
        return removed

    def evaluate(
        self,
        peer_spiffe_id: str,
        resource: Optional[str] = None,
        workload_type: Optional[str] = None,
    ) -> PolicyDecision:
        """
        Evaluate policy for a peer access request.

        Args:
            peer_spiffe_id: SPIFFE ID of the peer
            resource: Resource being accessed (optional)
            workload_type: Type of workload (optional)

        Returns:
            PolicyDecision with allow/deny result
        """
        matched_rules = []

        # Evaluate rules in priority order
        for rule in self.rules:
            if not rule.enabled:
                continue

            # Check if rule matches
            if self._rule_matches(rule, peer_spiffe_id, resource, workload_type):
                matched_rules.append(rule.rule_id)

                # If rule has OPA policy, evaluate via OPA first
                if rule.opa_policy and self.enable_opa:
                    opa_decision = self._evaluate_opa_policy(
                        rule, peer_spiffe_id, resource, workload_type
                    )
                    if opa_decision is not None:
                        # OPA decision takes precedence
                        decision = PolicyDecision(
                            allowed=opa_decision,
                            action=rule.action if opa_decision else PolicyAction.DENY,
                            matched_rules=[rule.rule_id],
                            reason=f"OPA policy decision for rule: {rule.name}",
                            audit_log=True,
                        )
                        self._log_audit(peer_spiffe_id, resource, decision)
                        return decision

                # Check conditions
                if self._check_conditions(rule, peer_spiffe_id):
                    # Rule matched and conditions passed
                    decision = PolicyDecision(
                        allowed=(rule.action == PolicyAction.ALLOW),
                        action=rule.action,
                        matched_rules=[rule.rule_id],
                        reason=f"Matched rule: {rule.name}",
                        audit_log=(rule.action == PolicyAction.AUDIT),
                    )

                    # Log audit if needed
                    if decision.audit_log:
                        self._log_audit(peer_spiffe_id, resource, decision)

                    return decision

        # No rules matched - use default action
        decision = PolicyDecision(
            allowed=(self.default_action == PolicyAction.ALLOW),
            action=self.default_action,
            reason=f"No rules matched, using default: {self.default_action.value}",
            audit_log=True,
        )

        self._log_audit(peer_spiffe_id, resource, decision)
        return decision

    def _rule_matches(
        self,
        rule: PolicyRule,
        peer_spiffe_id: str,
        resource: Optional[str],
        workload_type: Optional[str],
    ) -> bool:
        """Check if a rule matches the request."""
        # Check SPIFFE ID pattern
        if rule.spiffe_id_pattern:
            if not self._match_pattern(peer_spiffe_id, rule.spiffe_id_pattern):
                return False

        # Check resource access
        if rule.allowed_resources and resource:
            if resource not in rule.allowed_resources:
                return False

        # Check workload type
        if rule.conditions and PolicyCondition.WORKLOAD_TYPE in rule.conditions:
            spiffe_workload_type = (
                peer_spiffe_id.split("/")[-1] if "/" in peer_spiffe_id else None
            )
            if (
                workload_type
                and spiffe_workload_type
                and workload_type != spiffe_workload_type
            ):
                return False

        return True

    def _match_pattern(self, spiffe_id: str, pattern: str) -> bool:
        """
        Match SPIFFE ID against pattern.

        Supports:
        - Exact match: "spiffe://domain/workload/api"
        - Wildcard: "spiffe://domain/workload/*"
        - Prefix: "spiffe://domain/workload/api*"
        """
        if pattern == spiffe_id:
            return True

        if "*" in pattern:
            # Simple wildcard matching
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                return spiffe_id.startswith(prefix) and spiffe_id.endswith(suffix)
            elif len(pattern_parts) == 1:
                # Only prefix or suffix
                if pattern.startswith("*"):
                    return spiffe_id.endswith(pattern[1:])
                elif pattern.endswith("*"):
                    return spiffe_id.startswith(pattern[:-1])

        return False

    def _check_conditions(self, rule: PolicyRule, peer_spiffe_id: str) -> bool:
        """Check if rule conditions are met."""
        # Time-based condition
        if PolicyCondition.TIME_BASED in rule.conditions and rule.time_window:
            if not self._check_time_window(rule.time_window):
                return False

        # Rate limiting condition
        if PolicyCondition.RATE_LIMIT in rule.conditions and rule.rate_limit:
            if not self._check_rate_limit(peer_spiffe_id, rule.rate_limit):
                return False

        return True

    def _check_time_window(self, time_window: Dict[str, str]) -> bool:
        """Check if current time is within allowed window."""
        now = datetime.now()
        current_time = now.time()

        start_str = time_window.get("start", "00:00")
        end_str = time_window.get("end", "23:59")

        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                # Window spans midnight
                return current_time >= start_time or current_time <= end_time
        except ValueError:
            logger.warning(f"Invalid time window format: {time_window}")
            return True  # Default allow if format invalid

    def _check_rate_limit(
        self, peer_spiffe_id: str, rate_limit: Dict[str, int]
    ) -> bool:
        """Check if peer is within rate limit."""
        requests_per_minute = rate_limit.get("requests_per_minute", 1000)

        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        # Get recent requests
        if peer_spiffe_id not in self.rate_limit_tracker:
            self.rate_limit_tracker[peer_spiffe_id] = []

        recent_requests = [
            ts for ts in self.rate_limit_tracker[peer_spiffe_id] if ts > one_minute_ago
        ]

        # Update tracker
        self.rate_limit_tracker[peer_spiffe_id] = recent_requests

        # Check limit
        if len(recent_requests) >= requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for {peer_spiffe_id}: "
                f"{len(recent_requests)}/{requests_per_minute} requests/min"
            )
            return False

        # Add current request
        self.rate_limit_tracker[peer_spiffe_id].append(now)
        return True

    def _log_audit(
        self, peer_spiffe_id: str, resource: Optional[str], decision: PolicyDecision
    ):
        """Log audit event."""
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "peer_spiffe_id": peer_spiffe_id,
            "resource": resource,
            "action": decision.action.value,
            "allowed": decision.allowed,
            "matched_rules": decision.matched_rules,
            "reason": decision.reason,
        }
        self.audit_log.append(audit_entry)

        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.audit_log[-limit:]

    def _evaluate_opa_policy(
        self,
        rule: PolicyRule,
        peer_spiffe_id: str,
        resource: Optional[str],
        workload_type: Optional[str],
    ) -> Optional[bool]:
        """
        Evaluate policy using OPA (Open Policy Agent).

        Args:
            rule: Policy rule with OPA policy
            peer_spiffe_id: SPIFFE ID of the peer
            resource: Resource being accessed
            workload_type: Type of workload

        Returns:
            True if allowed, False if denied, None if OPA unavailable
        """
        if not self.enable_opa or not rule.opa_policy:
            return None

        try:
            # Prepare input for OPA
            input_data = {
                "input": {
                    "peer_spiffe_id": peer_spiffe_id,
                    "resource": resource,
                    "workload_type": workload_type,
                    "rule_id": rule.rule_id,
                    "timestamp": datetime.now().isoformat(),
                }
            }

            # Query OPA
            response = requests.post(
                f"{self.opa_endpoint}/v1/data/x0tta6bl4/policy",
                json=input_data,
                timeout=2,
            )

            if response.status_code == 200:
                result = response.json()
                # OPA returns {"result": true/false}
                return result.get("result", False)
            else:
                logger.warning(f"OPA query failed: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"OPA evaluation failed: {e}")
            return None

    def update_rule(self, rule_id: str, updated_rule: PolicyRule) -> bool:
        """
        Dynamically update a policy rule without restart.

        Args:
            rule_id: ID of rule to update
            updated_rule: Updated rule (must have same rule_id)

        Returns:
            True if rule was updated
        """
        if updated_rule.rule_id != rule_id:
            logger.error(f"Rule ID mismatch: {rule_id} != {updated_rule.rule_id}")
            return False

        # Find existing rule
        existing_rule = next((r for r in self.rules if r.rule_id == rule_id), None)
        if not existing_rule:
            logger.warning(f"Rule {rule_id} not found for update")
            return False

        # Increment version
        current_version = self.current_versions.get(rule_id, existing_rule.version)
        updated_rule.version = current_version + 1
        updated_rule.updated_at = datetime.now()

        # Save old version
        if rule_id not in self.policy_versions:
            self.policy_versions[rule_id] = []
        self.policy_versions[rule_id].append(existing_rule)

        # Update rule in list
        rule_index = next(
            (i for i, r in enumerate(self.rules) if r.rule_id == rule_id), None
        )
        if rule_index is not None:
            self.rules[rule_index] = updated_rule
            self.current_versions[rule_id] = updated_rule.version

            # Sort by priority
            self.rules.sort(key=lambda r: r.priority, reverse=True)

            # Notify callbacks
            for callback in self.update_callbacks:
                try:
                    callback(updated_rule)
                except Exception as e:
                    logger.warning(f"Policy update callback failed: {e}")

            logger.info(
                f"✅ Policy rule {rule_id} updated to version {updated_rule.version}"
            )
            return True

        return False

    def get_rule_version_history(self, rule_id: str) -> List[PolicyRule]:
        """
        Get version history for a policy rule.

        Args:
            rule_id: ID of rule

        Returns:
            List of rule versions (oldest first)
        """
        return self.policy_versions.get(rule_id, [])

    def rollback_rule(self, rule_id: str, target_version: Optional[int] = None) -> bool:
        """
        Rollback a policy rule to a previous version.

        Args:
            rule_id: ID of rule to rollback
            target_version: Target version (None = previous version)

        Returns:
            True if rollback successful
        """
        if rule_id not in self.policy_versions or not self.policy_versions[rule_id]:
            logger.warning(f"No version history for rule {rule_id}")
            return False

        versions = self.policy_versions[rule_id]
        current_version = self.current_versions.get(rule_id, 1)

        if target_version is None:
            # Rollback to previous version
            if versions:
                target_rule = versions[-1]  # Last (most recent) version
            else:
                logger.warning(f"No previous version for rule {rule_id}")
                return False
        else:
            # Rollback to specific version
            target_rule = next(
                (r for r in versions if r.version == target_version), None
            )
            if not target_rule:
                logger.warning(f"Version {target_version} not found for rule {rule_id}")
                return False

        # Create new version from target
        rolled_back_rule = PolicyRule(
            rule_id=target_rule.rule_id,
            name=target_rule.name,
            action=target_rule.action,
            conditions=target_rule.conditions.copy(),
            spiffe_id_pattern=target_rule.spiffe_id_pattern,
            allowed_resources=(
                target_rule.allowed_resources.copy()
                if target_rule.allowed_resources
                else None
            ),
            time_window=(
                target_rule.time_window.copy() if target_rule.time_window else None
            ),
            rate_limit=(
                target_rule.rate_limit.copy() if target_rule.rate_limit else None
            ),
            priority=target_rule.priority,
            enabled=target_rule.enabled,
            version=current_version + 1,
            opa_policy=target_rule.opa_policy,
            created_at=target_rule.created_at,
            updated_at=datetime.now(),
        )

        return self.update_rule(rule_id, rolled_back_rule)

    def register_update_callback(self, callback: Callable[[PolicyRule], None]):
        """
        Register a callback for policy updates.

        Args:
            callback: Function to call when a policy is updated
        """
        self.update_callbacks.append(callback)
        logger.info(f"Registered policy update callback: {callback.__name__}")

    def _check_advanced_conditions(
        self, rule: PolicyRule, peer_spiffe_id: str, resource: Optional[str]
    ) -> bool:
        """
        Check advanced rule conditions.

        Args:
            rule: Policy rule
            peer_spiffe_id: SPIFFE ID of the peer
            resource: Resource being accessed

        Returns:
            True if all advanced conditions pass
        """
        # Geographic condition (if implemented)
        if PolicyCondition.GEOGRAPHIC in rule.conditions:
            # Future: Add geographic IP-based checks
            pass

        # Workload type condition
        if PolicyCondition.WORKLOAD_TYPE in rule.conditions:
            # Future: Add workload type matching
            pass

        # Additional advanced conditions can be added here
        return True

    def _check_conditions(self, rule: PolicyRule, peer_spiffe_id: str) -> bool:
        """Check if rule conditions are met."""
        # Time-based condition
        if PolicyCondition.TIME_BASED in rule.conditions and rule.time_window:
            if not self._check_time_window(rule.time_window):
                return False

        # Rate limiting condition
        if PolicyCondition.RATE_LIMIT in rule.conditions and rule.rate_limit:
            if not self._check_rate_limit(peer_spiffe_id, rule.rate_limit):
                return False

        # Advanced conditions
        if not self._check_advanced_conditions(rule, peer_spiffe_id, None):
            return False

        return True

    def get_policy_status(self) -> Dict[str, Any]:
        """
        Get policy engine status.

        Returns:
            Dictionary with policy engine status
        """
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules if r.enabled),
            "default_action": self.default_action.value,
            "audit_log_entries": len(self.audit_log),
            "rate_limit_tracked_peers": len(self.rate_limit_tracker),
            "opa_enabled": self.enable_opa,
            "opa_endpoint": self.opa_endpoint if self.enable_opa else None,
            "versioned_rules": len(self.policy_versions),
            "update_callbacks": len(self.update_callbacks),
        }


# Global instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get global PolicyEngine instance."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


def configure_policy_engine(default_action: PolicyAction = PolicyAction.DENY):
    """
    Configure global PolicyEngine.

    Args:
        default_action: Default action for unmatched requests
    """
    global _policy_engine
    _policy_engine = PolicyEngine(default_action=default_action)
    logger.info(f"Policy Engine configured with default action: {default_action.value}")
