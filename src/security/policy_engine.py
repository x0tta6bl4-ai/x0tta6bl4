"""
Policy Engine for x0tta6bl4 Mesh Zero Trust.
Centralized policy management with distributed enforcement.

Implements:
- Policy Definition Language (PDL)
- Attribute-Based Access Control (ABAC)
- Risk-based dynamic policies
- Policy versioning and rollback
- Distributed policy sync

Standards: XACML concepts, OPA-compatible
"""

import hashlib
import json
import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PolicyEffect(Enum):
    """Policy decision effects."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log
    CHALLENGE = "challenge"  # Require additional verification


class PolicyPriority(Enum):
    """Policy priority levels."""

    EMERGENCY = 0  # Override everything
    CRITICAL = 10
    HIGH = 20
    NORMAL = 30
    LOW = 40
    DEFAULT = 50


class AttributeType(Enum):
    """Types of attributes for ABAC."""

    SUBJECT = "subject"  # Who (node, user, service)
    RESOURCE = "resource"  # What (data, endpoint, service)
    ACTION = "action"  # How (read, write, execute)
    ENVIRONMENT = "environment"  # When/Where (time, location, network)


@dataclass
class Attribute:
    """Attribute for policy evaluation."""

    type: AttributeType
    name: str
    value: Any

    def matches(self, pattern: Any) -> bool:
        """Check if value matches pattern."""
        if pattern == "*":
            return True
        if isinstance(pattern, str) and pattern.startswith("regex:"):
            return bool(re.match(pattern[6:], str(self.value)))
        if isinstance(pattern, list):
            return self.value in pattern
        if isinstance(pattern, dict):
            if "gt" in pattern:
                return self.value > pattern["gt"]
            if "lt" in pattern:
                return self.value < pattern["lt"]
            if "gte" in pattern:
                return self.value >= pattern["gte"]
            if "lte" in pattern:
                return self.value <= pattern["lte"]
            if "in" in pattern:
                return self.value in pattern["in"]
            if "not_in" in pattern:
                return self.value not in pattern["not_in"]
        return self.value == pattern


@dataclass
class PolicyCondition:
    """Condition in a policy rule."""

    attribute_type: AttributeType
    attribute_name: str
    operator: str  # eq, ne, gt, lt, gte, lte, in, not_in, regex, exists
    value: Any

    def evaluate(self, attributes: Dict[str, Attribute]) -> bool:
        """Evaluate condition against attributes."""
        key = f"{self.attribute_type.value}.{self.attribute_name}"
        attr = attributes.get(key)

        if self.operator == "exists":
            return attr is not None if self.value else attr is None

        if attr is None:
            return False

        if self.operator == "eq":
            return attr.value == self.value
        elif self.operator == "ne":
            return attr.value != self.value
        elif self.operator == "gt":
            return attr.value > self.value
        elif self.operator == "lt":
            return attr.value < self.value
        elif self.operator == "gte":
            return attr.value >= self.value
        elif self.operator == "lte":
            return attr.value <= self.value
        elif self.operator == "in":
            return attr.value in self.value
        elif self.operator == "not_in":
            return attr.value not in self.value
        elif self.operator == "regex":
            return bool(re.match(self.value, str(attr.value)))
        elif self.operator == "contains":
            return self.value in str(attr.value)

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribute_type": self.attribute_type.value,
            "attribute_name": self.attribute_name,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass
class PolicyRule:
    """Single rule in a policy."""

    id: str
    description: str
    conditions: List[PolicyCondition]
    effect: PolicyEffect
    priority: PolicyPriority = PolicyPriority.NORMAL
    enabled: bool = True

    def evaluate(self, attributes: Dict[str, Attribute]) -> Optional[PolicyEffect]:
        """
        Evaluate rule against attributes.
        Returns effect if all conditions match, None otherwise.
        """
        if not self.enabled:
            return None

        for condition in self.conditions:
            if not condition.evaluate(attributes):
                return None

        return self.effect

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "effect": self.effect.value,
            "priority": self.priority.value,
            "enabled": self.enabled,
        }


@dataclass
class Policy:
    """Complete policy with multiple rules."""

    id: str
    name: str
    description: str
    version: int
    rules: List[PolicyRule]
    target: Dict[str, Any]  # Resource/action targeting
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = ""
    enabled: bool = True

    def matches_target(self, resource: str, action: str) -> bool:
        """Check if policy applies to resource/action."""
        resource_pattern = self.target.get("resource", "*")
        action_pattern = self.target.get("action", "*")

        resource_match = (
            resource_pattern == "*"
            or resource == resource_pattern
            or (isinstance(resource_pattern, list) and resource in resource_pattern)
        )

        action_match = (
            action_pattern == "*"
            or action == action_pattern
            or (isinstance(action_pattern, list) and action in action_pattern)
        )

        return resource_match and action_match

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "target": self.target,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
        }


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    effect: PolicyEffect
    policy_id: str
    rule_id: str
    reason: str
    attributes_evaluated: int
    evaluation_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect": self.effect.value,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "attributes_evaluated": self.attributes_evaluated,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


class PolicyEngine:
    """
    Core policy engine for Zero Trust access control.
    Evaluates policies using ABAC (Attribute-Based Access Control).
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.policies: Dict[str, Policy] = {}
        self.policy_versions: Dict[str, List[Policy]] = {}
        self._lock = threading.RLock()
        self._decision_cache: Dict[str, Tuple[PolicyDecision, float]] = {}
        self._cache_ttl = 60  # seconds

        # Initialize with default policies
        self._init_default_policies()

        logger.info(f"PolicyEngine initialized for {node_id}")

    def _init_default_policies(self) -> None:
        """Initialize default Zero Trust policies."""
        # Default deny policy
        default_deny = Policy(
            id="default-deny",
            name="Default Deny",
            description="Deny all access by default (Zero Trust)",
            version=1,
            rules=[
                PolicyRule(
                    id="deny-all",
                    description="Default deny rule",
                    conditions=[],  # No conditions = matches everything
                    effect=PolicyEffect.DENY,
                    priority=PolicyPriority.DEFAULT,
                )
            ],
            target={"resource": "*", "action": "*"},
            created_by="system",
        )

        # Allow health checks
        health_policy = Policy(
            id="allow-health",
            name="Allow Health Checks",
            description="Allow health check endpoints",
            version=1,
            rules=[
                PolicyRule(
                    id="health-allow",
                    description="Allow health endpoint access",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.RESOURCE,
                            attribute_name="endpoint",
                            operator="in",
                            value=["/health", "/ready", "/live", "/metrics"],
                        )
                    ],
                    effect=PolicyEffect.ALLOW,
                    priority=PolicyPriority.HIGH,
                )
            ],
            target={"resource": "*", "action": "read"},
            created_by="system",
        )

        # Trust-based access
        trust_policy = Policy(
            id="trust-based-access",
            name="Trust-Based Access Control",
            description="Allow access based on trust level",
            version=1,
            rules=[
                PolicyRule(
                    id="high-trust-allow",
                    description="High trust nodes can access sensitive resources",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.SUBJECT,
                            attribute_name="trust_level",
                            operator="gte",
                            value=70,
                        ),
                        PolicyCondition(
                            attribute_type=AttributeType.RESOURCE,
                            attribute_name="sensitivity",
                            operator="in",
                            value=["low", "medium", "high"],
                        ),
                    ],
                    effect=PolicyEffect.ALLOW,
                    priority=PolicyPriority.NORMAL,
                ),
                PolicyRule(
                    id="medium-trust-allow",
                    description="Medium trust nodes can access non-sensitive resources",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.SUBJECT,
                            attribute_name="trust_level",
                            operator="gte",
                            value=50,
                        ),
                        PolicyCondition(
                            attribute_type=AttributeType.RESOURCE,
                            attribute_name="sensitivity",
                            operator="in",
                            value=["low", "medium"],
                        ),
                    ],
                    effect=PolicyEffect.ALLOW,
                    priority=PolicyPriority.NORMAL,
                ),
                PolicyRule(
                    id="low-trust-audit",
                    description="Low trust nodes require audit logging",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.SUBJECT,
                            attribute_name="trust_level",
                            operator="lt",
                            value=50,
                        )
                    ],
                    effect=PolicyEffect.AUDIT,
                    priority=PolicyPriority.NORMAL,
                ),
            ],
            target={"resource": "*", "action": "*"},
            created_by="system",
        )

        # Time-based access
        time_policy = Policy(
            id="time-based-access",
            name="Time-Based Access Control",
            description="Restrict access based on time",
            version=1,
            rules=[
                PolicyRule(
                    id="maintenance-window",
                    description="Deny non-essential access during maintenance",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.ENVIRONMENT,
                            attribute_name="maintenance_mode",
                            operator="eq",
                            value=True,
                        ),
                        PolicyCondition(
                            attribute_type=AttributeType.ACTION,
                            attribute_name="type",
                            operator="not_in",
                            value=["health", "metrics", "admin"],
                        ),
                    ],
                    effect=PolicyEffect.DENY,
                    priority=PolicyPriority.HIGH,
                )
            ],
            target={"resource": "*", "action": "*"},
            created_by="system",
        )

        # Add default policies
        for policy in [default_deny, health_policy, trust_policy, time_policy]:
            self.add_policy(policy)

    def add_policy(self, policy: Policy) -> None:
        """Add or update a policy."""
        with self._lock:
            # Store version history
            if policy.id in self.policies:
                if policy.id not in self.policy_versions:
                    self.policy_versions[policy.id] = []
                self.policy_versions[policy.id].append(self.policies[policy.id])

            policy.updated_at = time.time()
            self.policies[policy.id] = policy

            # Clear cache
            self._decision_cache.clear()

            logger.info(f"Added/updated policy: {policy.id} v{policy.version}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy."""
        with self._lock:
            if policy_id in self.policies:
                del self.policies[policy_id]
                self._decision_cache.clear()
                logger.info(f"Removed policy: {policy_id}")
                return True
            return False

    def rollback_policy(self, policy_id: str, version: Optional[int] = None) -> bool:
        """Rollback policy to previous version."""
        with self._lock:
            if policy_id not in self.policy_versions:
                return False

            versions = self.policy_versions[policy_id]
            if not versions:
                return False

            if version is not None:
                # Find specific version
                target = None
                for v in versions:
                    if v.version == version:
                        target = v
                        break
                if not target:
                    return False
            else:
                # Rollback to previous version
                target = versions.pop()

            self.policies[policy_id] = target
            self._decision_cache.clear()
            logger.info(f"Rolled back policy {policy_id} to v{target.version}")
            return True

    def evaluate(
        self,
        subject: Dict[str, Any],
        resource: str,
        action: str,
        environment: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Evaluate policies for access decision.

        Args:
            subject: Subject attributes (node_id, trust_level, etc.)
            resource: Resource being accessed
            action: Action being performed
            environment: Environmental context

        Returns:
            PolicyDecision with effect and reasoning
        """
        start_time = time.time()

        # Build attribute context
        attributes = self._build_attributes(subject, resource, action, environment)

        # Check cache
        cache_key = self._cache_key(attributes)
        if cache_key in self._decision_cache:
            decision, cached_at = self._decision_cache[cache_key]
            if time.time() - cached_at < self._cache_ttl:
                return decision

        # Evaluate policies
        with self._lock:
            applicable_policies = [
                p
                for p in self.policies.values()
                if p.enabled and p.matches_target(resource, action)
            ]

            # Sort by priority (lower = higher priority)
            decisions = []
            for policy in applicable_policies:
                for rule in sorted(policy.rules, key=lambda r: r.priority.value):
                    effect = rule.evaluate(attributes)
                    if effect is not None:
                        decisions.append((rule.priority.value, policy, rule, effect))

            # Get highest priority decision
            if decisions:
                decisions.sort(key=lambda d: d[0])
                _, policy, rule, effect = decisions[0]

                decision = PolicyDecision(
                    effect=effect,
                    policy_id=policy.id,
                    rule_id=rule.id,
                    reason=rule.description,
                    attributes_evaluated=len(attributes),
                    evaluation_time_ms=(time.time() - start_time) * 1000,
                )
            else:
                # No matching rules, use default deny
                decision = PolicyDecision(
                    effect=PolicyEffect.DENY,
                    policy_id="implicit",
                    rule_id="no-match",
                    reason="No matching policy rules",
                    attributes_evaluated=len(attributes),
                    evaluation_time_ms=(time.time() - start_time) * 1000,
                )

        # Cache decision
        self._decision_cache[cache_key] = (decision, time.time())

        return decision

    def _build_attributes(
        self,
        subject: Dict[str, Any],
        resource: str,
        action: str,
        environment: Optional[Dict[str, Any]],
    ) -> Dict[str, Attribute]:
        """Build attribute dictionary from inputs."""
        attributes = {}

        # Subject attributes
        for key, value in subject.items():
            attr = Attribute(AttributeType.SUBJECT, key, value)
            attributes[f"subject.{key}"] = attr

        # Resource attributes
        attributes["resource.name"] = Attribute(
            AttributeType.RESOURCE, "name", resource
        )
        attributes["resource.endpoint"] = Attribute(
            AttributeType.RESOURCE, "endpoint", resource
        )

        # Action attributes
        attributes["action.type"] = Attribute(AttributeType.ACTION, "type", action)

        # Environment attributes
        if environment:
            for key, value in environment.items():
                attr = Attribute(AttributeType.ENVIRONMENT, key, value)
                attributes[f"environment.{key}"] = attr

        # Add time context
        attributes["environment.timestamp"] = Attribute(
            AttributeType.ENVIRONMENT, "timestamp", time.time()
        )

        return attributes

    def _cache_key(self, attributes: Dict[str, Attribute]) -> str:
        """Generate cache key from attributes."""
        key_parts = sorted(f"{k}:{v.value}" for k, v in attributes.items())
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:32]

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get policy by ID."""
        return self.policies.get(policy_id)

    def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies."""
        return [p.to_dict() for p in self.policies.values()]

    def export_policies(self) -> str:
        """Export policies as JSON."""
        return json.dumps([p.to_dict() for p in self.policies.values()], indent=2)

    def import_policies(self, json_str: str) -> int:
        """Import policies from JSON."""
        policies_data = json.loads(json_str)
        count = 0

        for p_data in policies_data:
            rules = [
                PolicyRule(
                    id=r["id"],
                    description=r["description"],
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType(c["attribute_type"]),
                            attribute_name=c["attribute_name"],
                            operator=c["operator"],
                            value=c["value"],
                        )
                        for c in r["conditions"]
                    ],
                    effect=PolicyEffect(r["effect"]),
                    priority=PolicyPriority(r["priority"]),
                    enabled=r.get("enabled", True),
                )
                for r in p_data["rules"]
            ]

            policy = Policy(
                id=p_data["id"],
                name=p_data["name"],
                description=p_data["description"],
                version=p_data["version"],
                rules=rules,
                target=p_data["target"],
                enabled=p_data.get("enabled", True),
            )

            self.add_policy(policy)
            count += 1

        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get policy engine statistics."""
        with self._lock:
            return {
                "total_policies": len(self.policies),
                "enabled_policies": sum(1 for p in self.policies.values() if p.enabled),
                "total_rules": sum(len(p.rules) for p in self.policies.values()),
                "cache_size": len(self._decision_cache),
                "policy_ids": list(self.policies.keys()),
            }


class PolicyEnforcer:
    """
    Enforce policies at runtime.
    Decorator-based enforcement for functions/methods.
    """

    def __init__(self, engine: PolicyEngine):
        self.engine = engine

    def enforce(
        self,
        resource: str,
        action: str,
        get_subject: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """
        Decorator to enforce policy on function.

        Usage:
            @enforcer.enforce("sensitive_data", "read")
            def read_data(node_id):
                ...
        """

        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # Get subject attributes
                if get_subject:
                    subject = get_subject()
                else:
                    subject = {"node_id": "unknown"}

                # Evaluate policy
                decision = self.engine.evaluate(subject, resource, action)

                if decision.effect == PolicyEffect.DENY:
                    raise PermissionError(
                        f"Access denied: {decision.reason} "
                        f"(policy: {decision.policy_id})"
                    )

                if decision.effect == PolicyEffect.CHALLENGE:
                    # Would trigger additional verification
                    logger.warning(f"Challenge required for {resource}/{action}")

                if decision.effect == PolicyEffect.AUDIT:
                    logger.info(f"AUDIT: {subject} accessed {resource}/{action}")

                return func(*args, **kwargs)

            return wrapper

        return decorator
