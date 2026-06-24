"""Compatibility alias for the DB-backed MaaS auth API."""

import sys as _sys
from typing import Any, Iterable, Dict

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from types import SimpleNamespace
from src.api.maas_auth_models import (ApiKeyResponse, UserLoginRequest,
                                      UserRegisterRequest, TokenResponse)
from src.core.reliability_policy import mark_degraded_dependency
from src.database import User, Session as UserSession, get_db
from src.api.maas_security import oidc_validator, ApiKeyManager

# Legacy compatibility namespace
_legacy = SimpleNamespace()
from src.services.maas_auth_service import MaaSAuthService
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

# Lazy import of authlib — incompatible with cryptography>=46 in some builds
try:
    from authlib.integrations.starlette_client import OAuth as _OAuth
    _oauth_available = True
except Exception as _authlib_err:
    logger.warning(f"[MaaS Auth] authlib unavailable ({_authlib_err}); OIDC redirect flow disabled")
    _OAuth = None
    _oauth_available = False

router = APIRouter(prefix="/api/v1/maas/auth", tags=["MaaS Auth"])
from src.api.maas.endpoints.auth import router as _modular_auth_router
router.include_router(_modular_auth_router)

auth_service = MaaSAuthService(
    api_key_factory=ApiKeyManager.generate,
    default_plan="starter",
)
from src.core.rbac import DEFAULT_ROLE_PERMISSIONS, MeshPermission
from src.api.maas.auth import require_mesh_access as _modular_require_mesh_access
from src.api.maas.auth import get_current_user as get_current_user_from_maas


def _maas_auth_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit", "refresh"))


def _maas_auth_user_model_available() -> bool:
    return all(
        hasattr(User, attr)
        for attr in (
            "id",
            "email",
            "role",
            "plan",
            "api_key",
            "permissions",
            "created_at",
            "oidc_id",
            "oidc_provider",
        )
    )


def _maas_auth_session_model_available() -> bool:
    return all(
        hasattr(UserSession, attr)
        for attr in ("id", "token", "user_id", "email", "expires_at")
    )


def _maas_auth_service_available() -> bool:
    return all(
        callable(getattr(auth_service, attr, None))
        for attr in ("register", "login", "rotate_api_key")
    )


def _maas_auth_api_key_manager_available() -> bool:
    return callable(getattr(ApiKeyManager, "generate", None))


def _maas_auth_rbac_available() -> bool:
    return (
        isinstance(DEFAULT_ROLE_PERMISSIONS, dict)
        and callable(_permission_to_value)
        and callable(require_role)
        and callable(require_permission)
        and callable(require_mesh_access)
    )


def _maas_auth_token_helpers_available() -> bool:
    return callable(secrets.token_urlsafe) and callable(secrets.compare_digest)


def _maas_auth_audit_log_available() -> bool:
    return callable(record_audit_log)


def _maas_auth_oidc_enabled() -> bool:
    return bool(getattr(oidc_validator, "enabled", False))


def _maas_auth_oidc_redirect_available() -> bool:
    return not _maas_auth_oidc_enabled() or oauth is not None


def _maas_auth_bootstrap_token_configured() -> bool:
    return bool(os.getenv("BOOTSTRAP_TOKEN", "").strip())


def _maas_auth_readiness_status(db: Any) -> Dict[str, Any]:
    auth_db_ready = _maas_auth_db_session_available(db)
    user_model_ready = _maas_auth_user_model_available()
    session_model_ready = _maas_auth_session_model_available()
    auth_service_ready = _maas_auth_service_available()
    api_key_manager_ready = _maas_auth_api_key_manager_available()
    rbac_ready = _maas_auth_rbac_available()
    token_helpers_ready = _maas_auth_token_helpers_available()
    audit_log_ready = _maas_auth_audit_log_available()
    oidc_redirect_ready = _maas_auth_oidc_redirect_available()
    oidc_enabled = _maas_auth_oidc_enabled()
    bootstrap_token_configured = _maas_auth_bootstrap_token_configured()
    maas_auth_runtime_ready = (
        auth_db_ready
        and user_model_ready
        and session_model_ready
        and auth_service_ready
        and api_key_manager_ready
        and rbac_ready
        and token_helpers_ready
        and audit_log_ready
        and oidc_redirect_ready
    )

    degraded_dependencies = []
    if not auth_db_ready:
        degraded_dependencies.append("database")
    if not user_model_ready:
        degraded_dependencies.append("user_model")
    if not session_model_ready:
        degraded_dependencies.append("session_model")
    if not auth_service_ready:
        degraded_dependencies.append("auth_service")
    if not api_key_manager_ready:
        degraded_dependencies.append("api_key_manager")
    if not rbac_ready:
        degraded_dependencies.append("rbac")
    if not token_helpers_ready:
        degraded_dependencies.append("token_helpers")
    if not audit_log_ready:
        degraded_dependencies.append("audit_log")
    if not oidc_redirect_ready:
        degraded_dependencies.append("oidc_redirect")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "maas_auth_runtime_ready": maas_auth_runtime_ready,
        "auth_db_ready": auth_db_ready,
        "user_model_ready": user_model_ready,
        "session_model_ready": session_model_ready,
        "auth_service_ready": auth_service_ready,
        "api_key_manager_ready": api_key_manager_ready,
        "rbac_ready": rbac_ready,
        "token_helpers_ready": token_helpers_ready,
        "audit_log_ready": audit_log_ready,
        "oidc_enabled": oidc_enabled,
        "oidc_redirect_ready": oidc_redirect_ready,
        "bootstrap_token_configured": bootstrap_token_configured,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/maas/auth",
            "boundary": (
                "MaaS auth routes use the fixed /api/v1/maas/auth prefix. "
                "The legacy MaaS router is registered earlier, but its dynamic "
                "mesh routes do not match auth register/login/profile/admin paths."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Registration, login, API-key rotation, session lookup, OIDC "
                "callback, admin promotion, and bootstrap all require SQLAlchemy "
                "query/add/commit/refresh methods."
            ),
            "user_model": (
                "Auth flows depend on User identity, role, plan, API key, "
                "permissions, and OIDC linkage fields."
            ),
            "session_model": (
                "Bearer-token dashboard sessions depend on the UserSession token, "
                "user, email, and expiry fields."
            ),
            "auth_service": (
                "Email registration/login and API-key rotation are delegated to "
                "MaaSAuthService."
            ),
            "api_key_manager": "API-key creation depends on ApiKeyManager.generate.",
            "rbac": (
                "Route guards depend on MeshPermission, DEFAULT_ROLE_PERMISSIONS, "
                "require_role, require_permission, and require_mesh_access."
            ),
            "token_helpers": (
                "OIDC session creation and bootstrap token comparison depend on "
                "secrets.token_urlsafe and secrets.compare_digest."
            ),
            "audit_log": (
                "API-key rotation, admin promotion, and bootstrap emit audit logs."
            ),
            "oidc_redirect": (
                "OIDC redirect/callback are optional when OIDC is disabled; when "
                "enabled, authlib OAuth must be available."
            ),
            "bootstrap_token": (
                "BOOTSTRAP_TOKEN is intentionally optional and only gates the "
                "one-shot bootstrap-admin route."
            ),
        },
        "claim_boundary": (
            "MaaS auth readiness proves route availability and local dependency "
            "surfaces only. It does not create a user, validate credentials, "
            "query a real session, contact an OIDC provider, rotate an API key, "
            "or prove a bootstrap operation is allowed."
        ),
    }


@router.get("/readiness")
async def maas_auth_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _maas_auth_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


# Backward-compatible role scopes used by legacy MaaS routes.
_LEGACY_ROLE_DEFAULTS = {
    "operator": {
        "mesh:view",
        "mesh:update",
        "node:approve",
        "node:revoke",
        "policy:view",
        "policy:create",
        "analytics:view",
        "telemetry:view",
        "playbook:create",
        "playbook:view",
        "audit:view",
        "node:view",
    },
    "user": {
        "mesh:create",
        "mesh:view",
        "mesh:update",
        "mesh:delete",
        "billing:view",
        "marketplace:list",
        "marketplace:rent",
        "playbook:view",
    },
}


def _permission_value(val: Any) -> str:
    return str(getattr(val, "value", str(val)))

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

def _legacy_require_mesh_access(permission: Any):
    # Backward compatible wrapper that acts as a factory
    perm_str = getattr(permission, "value", str(permission))
    return require_permission(perm_str)

if not hasattr(_legacy, "require_mesh_access"):
    _legacy.require_mesh_access = _legacy_require_mesh_access

if not hasattr(_legacy, "get_current_user_from_maas"):
    _legacy.get_current_user_from_maas = get_current_user_from_maas

_legacy.router = router

globals().update(_legacy.__dict__)
_sys.modules[__name__] = _legacy
