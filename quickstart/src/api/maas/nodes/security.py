"""
MaaS Node Security and RBAC - granular admission control.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import MeshInstance, User, get_db
from src.core.security.rbac import MeshPermission, DEFAULT_ROLE_PERMISSIONS as ROLE_PERMISSIONS
from src.api.maas.auth import require_role

logger = logging.getLogger(__name__)


class MeshOperator:
    """Represents a mesh operator with granular permissions.
    
    This class extends the basic User model with mesh-specific permissions,
    allowing fine-grained access control beyond simple role-based checks.
    """
    
    def __init__(
        self,
        user: User,
        mesh_id: str,
        db: Session,
        custom_permissions: Optional[Set[MeshPermission]] = None,
    ) -> None:
        self.user_id = user.id
        self.mesh_id = mesh_id
        self.role = user.role
        self._db = db
        
        # Check if user is mesh owner
        mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
        self.is_owner = mesh is not None and mesh.owner_id == user.id
        
        # Determine permissions
        if custom_permissions is not None:
            self.permissions = custom_permissions
        else:
            self.permissions = self._resolve_permissions(user, mesh_id, db)
    
    def _resolve_permissions(
        self, user: User, mesh_id: str, db: Session
    ) -> Set[MeshPermission]:
        """Resolve effective permissions for user on mesh."""
        # Admin gets all permissions
        if user.role == "admin":
            return ROLE_PERMISSIONS["admin"].copy()
        
        # Start with role default permissions
        if user.role == "user" and not self.is_owner:
            base_permissions = set()
        else:
            base_permissions = ROLE_PERMISSIONS.get(user.role, set()).copy()
        
        # Mesh owner gets additional permissions
        if self.is_owner:
            base_permissions.update([
                MeshPermission.MESH_READ,
                MeshPermission.MESH_VIEW,
                MeshPermission.MESH_WRITE,
                MeshPermission.NODE_READ,
                MeshPermission.NODE_VIEW,
                MeshPermission.NODE_WRITE,
                MeshPermission.NODE_APPROVE,
                MeshPermission.NODE_REVOKE,
                MeshPermission.NODE_DELETE,
                MeshPermission.NODE_HEAL,
                MeshPermission.ACL_READ,
                MeshPermission.ACL_VIEW,
                MeshPermission.ACL_WRITE,
                MeshPermission.ACL_UPDATE,
                MeshPermission.TELEMETRY_READ,
                MeshPermission.TELEMETRY_VIEW,
                MeshPermission.TELEMETRY_EXPORT,
            ])
        
        # Check for explicit permission grants
        try:
            from src.database import MeshOperatorPermission
            explicit_perms = db.query(MeshOperatorPermission).filter(
                MeshOperatorPermission.user_id == user.id,
                MeshOperatorPermission.mesh_id == mesh_id,
            ).all()
            
            for perm in explicit_perms:
                try:
                    base_permissions.add(MeshPermission(perm.permission))
                except ValueError:
                    logger.warning(f"Unknown permission: {perm.permission}")
        except ImportError:
            logger.debug(
                f"MeshOperatorPermission table not found for user {user.id} on mesh {mesh_id}"
            )
        
        return _expand_permission_aliases(base_permissions)
    
    def has_permission(self, permission: MeshPermission) -> bool:
        """Check if operator has a specific permission."""
        return permission in self.permissions
    
    def require_permission(self, permission: MeshPermission) -> None:
        """Require a specific permission, raising HTTPException if not granted."""
        if not self.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
    
    def has_any_permission(self, permissions: Set[MeshPermission]) -> bool:
        """Check if operator has any of the specified permissions."""
        return bool(self.permissions & permissions)
    
    def has_all_permissions(self, permissions: Set[MeshPermission]) -> bool:
        """Check if operator has all of the specified permissions."""
        return permissions.issubset(self.permissions)


def _expand_permission_aliases(permissions: Set[MeshPermission]) -> Set[MeshPermission]:
    expanded = set(permissions)
    alias_groups = (
        {MeshPermission.MESH_READ, MeshPermission.MESH_VIEW},
        {MeshPermission.NODE_READ, MeshPermission.NODE_VIEW},
        {MeshPermission.ACL_READ, MeshPermission.ACL_VIEW},
        {MeshPermission.ACL_WRITE, MeshPermission.ACL_UPDATE},
        {MeshPermission.TELEMETRY_READ, MeshPermission.TELEMETRY_VIEW},
    )
    for group in alias_groups:
        if expanded.intersection(group):
            expanded.update(group)
    return expanded


def get_mesh_operator(
    mesh_id: str,
    current_user: User = Depends(require_role("operator")),
    db: Session = Depends(get_db),
) -> MeshOperator:
    """Dependency to get MeshOperator for current user and mesh."""
    return MeshOperator(current_user, mesh_id, db)


def check_permission(
    current_user: User,
    mesh_id: str,
    permission: MeshPermission,
    db: Session,
) -> bool:
    """Check if user has a specific permission on mesh."""
    operator = MeshOperator(current_user, mesh_id, db)
    return operator.has_permission(permission)


def ensure_mesh_visibility(
    mesh_id: str,
    current_user: User,
    db: Session,
    permission: MeshPermission = MeshPermission.MESH_READ,
) -> None:
    """Enforce mesh access with permission check."""
    operator = MeshOperator(current_user, mesh_id, db)
    
    # Check if mesh exists and user has access
    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    # Admin always has access
    if current_user.role == "admin":
        return
    
    # Check ownership or explicit permission
    if not operator.is_owner and not operator.has_permission(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {permission.value} required",
        )


def ensure_mesh_visibility_with_permission(
    mesh_id: str,
    current_user: User,
    db: Session,
    required_permission: MeshPermission,
) -> MeshOperator:
    """Enforce mesh visibility and return MeshOperator for further checks."""
    operator = MeshOperator(current_user, mesh_id, db)
    
    # Check mesh existence
    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    # Check basic read visibility for anti-enumeration
    if current_user.role != "admin" and not operator.is_owner and not operator.has_permission(MeshPermission.MESH_READ):
        raise HTTPException(status_code=404, detail="Mesh not found")
        
    # Require permission
    operator.require_permission(required_permission)
    
    return operator

