"""
Role-Based Access Control (RBAC)

Provides role definitions, permission management, and policy enforcement.
"""

import logging
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions"""
    # Mesh permissions
    MESH_READ = "mesh:read"
    MESH_WRITE = "mesh:write"
    MESH_ADMIN = "mesh:admin"
    
    # Node permissions
    NODE_READ = "node:read"
    NODE_WRITE = "node:write"
    NODE_DELETE = "node:delete"
    
    # Service permissions
    SERVICE_READ = "service:read"
    SERVICE_WRITE = "service:write"
    SERVICE_DELETE = "service:delete"
    
    # Security permissions
    SECURITY_READ = "security:read"
    SECURITY_WRITE = "security:write"
    SECURITY_ADMIN = "security:admin"
    
    # Monitoring permissions
    MONITORING_READ = "monitoring:read"
    MONITORING_WRITE = "monitoring:write"
    
    # Admin permissions
    ADMIN = "admin:*"


@dataclass
class Role:
    """Represents a role with permissions"""
    role_id: str
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Policy:
    """Access control policy"""
    policy_id: str
    name: str
    role_id: str
    resource_pattern: str  # e.g., "mesh:*", "node:node-*"
    conditions: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class RBACManager:
    """
    Manages roles, permissions, and access control policies.
    
    Provides:
    - Role management
    - Permission assignment
    - Policy enforcement
    - Access control checks
    """
    
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.user_roles: Dict[str, List[str]] = {}  # user_id -> [role_id]
        self.policies: Dict[str, Policy] = {}
        
        # Initialize default roles
        self._initialize_default_roles()
        
        logger.info("RBACManager initialized")
    
    def _initialize_default_roles(self):
        """Initialize default system roles"""
        # Admin role
        admin_role = Role(
            role_id="admin",
            name="Administrator",
            permissions={Permission.ADMIN},
            description="Full system access"
        )
        self.roles["admin"] = admin_role
        
        # Operator role
        operator_role = Role(
            role_id="operator",
            name="Operator",
            permissions={
                Permission.MESH_READ,
                Permission.MESH_WRITE,
                Permission.NODE_READ,
                Permission.NODE_WRITE,
                Permission.SERVICE_READ,
                Permission.SERVICE_WRITE,
                Permission.MONITORING_READ,
                Permission.MONITORING_WRITE
            },
            description="Operational access"
        )
        self.roles["operator"] = operator_role
        
        # Viewer role
        viewer_role = Role(
            role_id="viewer",
            name="Viewer",
            permissions={
                Permission.MESH_READ,
                Permission.NODE_READ,
                Permission.SERVICE_READ,
                Permission.MONITORING_READ
            },
            description="Read-only access"
        )
        self.roles["viewer"] = viewer_role
        
        logger.info("Default roles initialized: admin, operator, viewer")
    
    def create_role(
        self,
        name: str,
        permissions: Set[Permission],
        description: str = ""
    ) -> Role:
        """
        Create a new role.
        
        Args:
            name: Role name
            permissions: Set of permissions
            description: Role description
        
        Returns:
            Created Role object
        """
        role_id = f"role-{name.lower().replace(' ', '-')}"
        role = Role(
            role_id=role_id,
            name=name,
            permissions=permissions,
            description=description
        )
        
        self.roles[role_id] = role
        logger.info(f"Created role {role_id} ({name})")
        return role
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID"""
        return self.roles.get(role_id)
    
    def assign_role(self, user_id: str, role_id: str) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: User identifier
            role_id: Role identifier
        
        Returns:
            True if assigned successfully
        """
        if role_id not in self.roles:
            logger.warning(f"Role {role_id} not found")
            return False
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        
        if role_id not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role_id)
            logger.info(f"Assigned role {role_id} to user {user_id}")
        
        return True
    
    def revoke_role(self, user_id: str, role_id: str) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User identifier
            role_id: Role identifier
        
        Returns:
            True if revoked successfully
        """
        if user_id not in self.user_roles:
            return False
        
        if role_id in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_id)
            logger.info(f"Revoked role {role_id} from user {user_id}")
            return True
        
        return False
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        Get all roles for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of Role objects
        """
        role_ids = self.user_roles.get(user_id, [])
        return [self.roles[rid] for rid in role_ids if rid in self.roles]
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get all permissions for a user (from all roles).
        
        Args:
            user_id: User identifier
        
        Returns:
            Set of permissions
        """
        roles = self.get_user_roles(user_id)
        permissions = set()
        
        for role in roles:
            permissions.update(role.permissions)
        
        return permissions
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            user_id: User identifier
            permission: Permission to check
        
        Returns:
            True if user has permission
        """
        user_permissions = self.get_user_permissions(user_id)
        
        # Check direct permission
        if permission in user_permissions:
            return True
        
        # Check admin permission
        if Permission.ADMIN in user_permissions:
            return True
        
        return False
    
    def create_policy(
        self,
        name: str,
        role_id: str,
        resource_pattern: str,
        conditions: Optional[Dict[str, Any]] = None
    ) -> Policy:
        """
        Create an access control policy.
        
        Args:
            name: Policy name
            role_id: Role ID
            resource_pattern: Resource pattern (e.g., "mesh:*")
            conditions: Optional conditions
        
        Returns:
            Created Policy object
        """
        policy_id = f"policy-{name.lower().replace(' ', '-')}"
        policy = Policy(
            policy_id=policy_id,
            name=name,
            role_id=role_id,
            resource_pattern=resource_pattern,
            conditions=conditions or {}
        )
        
        self.policies[policy_id] = policy
        logger.info(f"Created policy {policy_id} ({name})")
        return policy
    
    def check_resource_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str = "read"
    ) -> bool:
        """
        Check if user has access to a resource.
        
        Args:
            user_id: User identifier
            resource_type: Type of resource
            resource_id: Resource identifier
            action: Action (read, write, delete)
        
        Returns:
            True if user has access
        """
        # Get user permissions
        user_permissions = self.get_user_permissions(user_id)
        
        # Check admin permission
        if Permission.ADMIN in user_permissions:
            return True
        
        # Map action to permission
        permission_map = {
            "read": Permission(f"{resource_type}:read"),
            "write": Permission(f"{resource_type}:write"),
            "delete": Permission(f"{resource_type}:delete")
        }
        
        required_permission = permission_map.get(action)
        if required_permission and required_permission in user_permissions:
            return True
        
        # Check policies
        for policy in self.policies.values():
            if self._match_policy(policy, resource_type, resource_id):
                user_roles = [r.role_id for r in self.get_user_roles(user_id)]
                if policy.role_id in user_roles:
                    return True
        
        return False
    
    def _match_policy(self, policy: Policy, resource_type: str, resource_id: str) -> bool:
        """Check if policy matches resource"""
        pattern = policy.resource_pattern
        
        # Simple pattern matching (can be extended)
        if pattern == f"{resource_type}:*":
            return True
        elif pattern == f"{resource_type}:{resource_id}":
            return True
        elif pattern.endswith("*") and resource_id.startswith(pattern[:-1]):
            return True
        
        return False

