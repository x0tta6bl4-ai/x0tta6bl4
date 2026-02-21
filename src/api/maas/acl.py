"""
MaaS ACL - Access Control List evaluation.

Provides ACL policy management and evaluation for fine-grained access control.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------

class Effect(str, Enum):
    """ACL policy effect."""
    ALLOW = "allow"
    DENY = "deny"


class ActionType(str, Enum):
    """Common action types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    DEPLOY = "deploy"
    SCALE = "scale"
    TERMINATE = "terminate"
    APPROVE = "approve"
    REVOKE = "revoke"


@dataclass
class ACLEntry:
    """A single ACL entry."""

    id: str
    principal: str  # User ID or "*" for anyone
    action: str  # Action or "*" for all actions
    resource: str  # Resource pattern or "*" for all resources
    effect: Effect = Effect.ALLOW
    conditions: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "principal": self.principal,
            "action": self.action,
            "resource": self.resource,
            "effect": self.effect.value,
            "conditions": self.conditions,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ACLEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            principal=data["principal"],
            action=data["action"],
            resource=data["resource"],
            effect=Effect(data.get("effect", "allow")),
            conditions=data.get("conditions", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.utcnow(),
            created_by=data.get("created_by"),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
        )


# ---------------------------------------------------------------------------
# ACL Evaluator
# ---------------------------------------------------------------------------

class ACLEvaluator:
    """
    Evaluates ACL policies for access control decisions.

    Features:
    - Policy-based access control
    - Wildcard matching for resources and actions
    - Condition evaluation (time-based, attribute-based)
    - Policy expiration
    - Audit logging integration
    """

    def __init__(self):
        self._policies: Dict[str, List[ACLEntry]] = {}

    def add_policy(
        self,
        mesh_id: str,
        entry: ACLEntry,
    ) -> None:
        """Add an ACL entry to a mesh."""
        if mesh_id not in self._policies:
            self._policies[mesh_id] = []
        self._policies[mesh_id].append(entry)

        logger.info(
            f"Added ACL entry {entry.id} to mesh {mesh_id}: "
            f"{entry.principal} -> {entry.action} on {entry.resource}"
        )

    def remove_policy(
        self,
        mesh_id: str,
        entry_id: str,
    ) -> bool:
        """Remove an ACL entry from a mesh."""
        if mesh_id not in self._policies:
            return False

        for i, entry in enumerate(self._policies[mesh_id]):
            if entry.id == entry_id:
                self._policies[mesh_id].pop(i)
                logger.info(f"Removed ACL entry {entry_id} from mesh {mesh_id}")
                return True

        return False

    def get_policies(self, mesh_id: str) -> List[ACLEntry]:
        """Get all ACL entries for a mesh."""
        return self._policies.get(mesh_id, [])

    def evaluate(
        self,
        mesh_id: str,
        principal: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Evaluate access control for a request.

        Uses deny-by-default with explicit allow override.
        Policies are evaluated in order; first matching policy wins.

        Args:
            mesh_id: Mesh ID
            principal: User ID making the request
            action: Action being performed
            resource: Resource being accessed
            context: Additional context for condition evaluation

        Returns:
            True if access is allowed, False otherwise
        """
        policies = self.get_policies(mesh_id)

        # Default deny
        allowed = False

        for entry in policies:
            # Check expiration
            if entry.expires_at and datetime.utcnow() > entry.expires_at:
                continue

            # Check principal match
            if not self._match_principal(entry.principal, principal):
                continue

            # Check action match
            if not self._match_action(entry.action, action):
                continue

            # Check resource match
            if not self._match_resource(entry.resource, resource):
                continue

            # Check conditions
            if entry.conditions and not self._evaluate_conditions(
                entry.conditions, context or {}
            ):
                continue

            # Policy matches - apply effect
            if entry.effect == Effect.DENY:
                logger.warning(
                    f"ACL DENY: {principal} -> {action} on {resource} "
                    f"(policy: {entry.id})"
                )
                return False

            allowed = True
            logger.debug(
                f"ACL ALLOW: {principal} -> {action} on {resource} "
                f"(policy: {entry.id})"
            )

        return allowed

    def _match_principal(self, pattern: str, principal: str) -> bool:
        """Match principal pattern against actual principal."""
        if pattern == "*":
            return True
        if pattern == principal:
            return True
        # Support for group patterns like "group:admins"
        if pattern.startswith("group:"):
            # Would need group membership lookup
            return False
        return False

    def _match_action(self, pattern: str, action: str) -> bool:
        """Match action pattern against actual action."""
        if pattern == "*":
            return True
        if pattern == action:
            return True
        # Support for action hierarchies (admin includes all)
        if pattern == "admin":
            return True
        if pattern == "write" and action in ("read", "write"):
            return True
        return False

    def _match_resource(self, pattern: str, resource: str) -> bool:
        """
        Match resource pattern against actual resource.

        Supports:
        - Exact match: "mesh/abc123"
        - Single wildcard: "mesh/*" matches "mesh/abc123"
        - Multi wildcard: "nodes/**" matches "nodes/xyz/actions/read"
        """
        if pattern == "*":
            return True
        if pattern == resource:
            return True

        pattern_parts = pattern.split("/")
        resource_parts = resource.split("/")

        for i, p_part in enumerate(pattern_parts):
            if i >= len(resource_parts):
                return False

            if p_part == "**":
                return True

            if p_part != "*" and p_part != resource_parts[i]:
                return False

        return len(pattern_parts) == len(resource_parts)

    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """
        Evaluate ACL conditions against context.

        Supported conditions:
        - time_range: {start: "09:00", end: "17:00"}
        - ip_range: {cidr: "10.0.0.0/8"}
        - attributes: {key: value, ...}
        """
        for cond_type, cond_value in conditions.items():
            if cond_type == "time_range":
                if not self._check_time_range(cond_value):
                    return False
            elif cond_type == "ip_range":
                if not self._check_ip_range(cond_value, context.get("ip")):
                    return False
            elif cond_type == "attributes":
                if not self._check_attributes(cond_value, context.get("attributes", {})):
                    return False

        return True

    def _check_time_range(self, time_range: Dict[str, str]) -> bool:
        """Check if current time is within range."""
        from datetime import time as dt_time

        now = datetime.utcnow().time()
        start = dt_time.fromisoformat(time_range["start"])
        end = dt_time.fromisoformat(time_range["end"])

        if start <= end:
            return start <= now <= end
        else:
            # Range spans midnight
            return now >= start or now <= end

    def _check_ip_range(self, ip_range: Dict[str, str], ip: Optional[str]) -> bool:
        """Check if IP is within allowed range."""
        import ipaddress

        if not ip:
            return False

        try:
            network = ipaddress.ip_network(ip_range["cidr"], strict=False)
            return ipaddress.ip_address(ip) in network
        except ValueError:
            return False

    def _check_attributes(
        self,
        required: Dict[str, Any],
        actual: Dict[str, Any],
    ) -> bool:
        """Check if actual attributes match required."""
        for key, value in required.items():
            if key not in actual:
                return False
            if actual[key] != value:
                return False
        return True


# ---------------------------------------------------------------------------
# ACL Manager
# ---------------------------------------------------------------------------

class ACLManager:
    """
    High-level ACL management interface.

    Provides convenience methods for common ACL operations.
    """

    def __init__(self, evaluator: Optional[ACLEvaluator] = None):
        self._evaluator = evaluator or ACLEvaluator()

    def grant_access(
        self,
        mesh_id: str,
        user_id: str,
        action: str,
        resource: str,
        granted_by: str,
        expires_at: Optional[datetime] = None,
    ) -> ACLEntry:
        """
        Grant access to a user.

        Args:
            mesh_id: Mesh ID
            user_id: User to grant access to
            action: Action to allow
            resource: Resource pattern
            granted_by: User granting access
            expires_at: Optional expiration time

        Returns:
            Created ACL entry
        """
        import secrets

        entry = ACLEntry(
            id=f"acl-{secrets.token_hex(8)}",
            principal=user_id,
            action=action,
            resource=resource,
            effect=Effect.ALLOW,
            created_by=granted_by,
            expires_at=expires_at,
        )

        self._evaluator.add_policy(mesh_id, entry)

        # Sync to registry
        from .registry import add_mesh_policy
        add_mesh_policy(mesh_id, entry.to_dict())

        return entry

    def revoke_access(
        self,
        mesh_id: str,
        entry_id: str,
    ) -> bool:
        """
        Revoke an ACL entry.

        Args:
            mesh_id: Mesh ID
            entry_id: ACL entry ID to revoke

        Returns:
            True if entry was revoked
        """
        return self._evaluator.remove_policy(mesh_id, entry_id)

    def check_access(
        self,
        mesh_id: str,
        user_id: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if a user has access to perform an action.

        Args:
            mesh_id: Mesh ID
            user_id: User ID
            action: Action to check
            resource: Resource to check
            context: Additional context

        Returns:
            True if access is allowed
        """
        return self._evaluator.evaluate(
            mesh_id, user_id, action, resource, context
        )

    def list_user_permissions(
        self,
        mesh_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List all permissions for a user on a mesh.

        Args:
            mesh_id: Mesh ID
            user_id: User ID

        Returns:
            List of permission dictionaries
        """
        policies = self._evaluator.get_policies(mesh_id)

        permissions = []
        for entry in policies:
            if entry.principal == user_id or entry.principal == "*":
                permissions.append(entry.to_dict())

        return permissions


# ---------------------------------------------------------------------------
# Predefined Policies
# ---------------------------------------------------------------------------

def create_default_policies(
    mesh_id: str,
    owner_id: str,
) -> List[ACLEntry]:
    """
    Create default ACL policies for a new mesh.

    Args:
        mesh_id: Mesh ID
        owner_id: Owner user ID

    Returns:
        List of default ACL entries
    """
    import secrets

    now = datetime.utcnow()

    return [
        # Owner has full access
        ACLEntry(
            id=f"acl-{secrets.token_hex(8)}",
            principal=owner_id,
            action="*",
            resource="*",
            effect=Effect.ALLOW,
            created_by="system",
            created_at=now,
        ),
    ]


def create_readonly_policy(
    mesh_id: str,
    user_id: str,
    granted_by: str,
) -> ACLEntry:
    """
    Create a read-only policy for a user.

    Args:
        mesh_id: Mesh ID
        user_id: User to grant read access
        granted_by: User granting access

    Returns:
        Read-only ACL entry
    """
    import secrets

    return ACLEntry(
        id=f"acl-{secrets.token_hex(8)}",
        principal=user_id,
        action="read",
        resource="*",
        effect=Effect.ALLOW,
        created_by=granted_by,
    )


__all__ = [
    # Enums
    "Effect",
    "ActionType",
    # Classes
    "ACLEntry",
    "ACLEvaluator",
    "ACLManager",
    # Functions
    "create_default_policies",
    "create_readonly_policy",
]
