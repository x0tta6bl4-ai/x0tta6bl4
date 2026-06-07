"""Compatibility alias for the DB-backed MaaS auth API."""

import sys as _sys
from typing import Any, Iterable

from fastapi import Depends, HTTPException

from src.api import maas_auth_legacy_full as _legacy
from src.api.maas.auth import (
    require_mesh_access as _modular_require_mesh_access,
)
from src.core.rbac import DEFAULT_ROLE_PERMISSIONS, MeshPermission


def _permission_value(permission: str) -> str:
    try:
        return MeshPermission(permission).value
    except ValueError:
        return str(permission)


def _role_allows(role: str, permission: str) -> bool:
    wanted = _permission_value(permission)
    allowed = DEFAULT_ROLE_PERMISSIONS.get(str(role or "user"), set())
    return any(getattr(item, "value", str(item)) == wanted for item in allowed)


def _iter_permission_values(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    try:
        return tuple(
            str(getattr(item, "value", item)).strip()
            for item in value
            if str(getattr(item, "value", item)).strip()
        )
    except TypeError:
        text = str(getattr(value, "value", value)).strip()
        return (text,) if text else ()


def _explicit_permissions(user: Any) -> set[str]:
    values = set(_iter_permission_values(getattr(user, "permissions", None)))
    values.update(_iter_permission_values(getattr(user, "scopes", None)))
    return values


def require_role(roles: str | list[str]):
    allowed_roles = [roles] if isinstance(roles, str) else list(roles)

    def role_checker(user=Depends(_legacy.get_current_user_from_maas)):
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        role = str(getattr(user, "role", "user") or "user")
        if role == "admin" or role in allowed_roles:
            return user
        raise HTTPException(
            status_code=403,
            detail=f"Required role(s): {', '.join(allowed_roles)}",
        )

    return role_checker


def require_permission(permission: str):
    def permission_checker(user=Depends(_legacy.get_current_user_from_maas)):
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        role = str(getattr(user, "role", "user") or "user")
        permissions = _explicit_permissions(user)
        if role == "admin" or "*" in permissions:
            return user
        if permission in permissions or _role_allows(role, permission):
            return user
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return permission_checker


class _OIDCValidatorCompat:
    issuer: str | None = None
    client_id: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)


_legacy.require_role = require_role
_legacy.require_permission = require_permission

if not hasattr(_legacy, "oidc_validator"):
    _legacy.oidc_validator = _OIDCValidatorCompat()

if not hasattr(_legacy, "oauth"):
    _legacy.oauth = None

if not hasattr(_legacy, "require_mesh_access"):
    _legacy.require_mesh_access = _modular_require_mesh_access

globals().update(_legacy.__dict__)
_sys.modules[__name__] = _legacy
