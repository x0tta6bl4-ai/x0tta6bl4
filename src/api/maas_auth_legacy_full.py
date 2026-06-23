"""
MaaS Auth Shim — x0tta6bl4
==========================

Compatibility shim for v4.0 architecture.
Redirects to modular auth router in src/api/maas/endpoints/auth.py.

DEPRECATED: Use src.api.maas.auth or src.api.maas.endpoints.auth instead.
"""

import logging
import os
import hashlib
import secrets
import sys
import warnings
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

# Import from modular router
from .maas.endpoints.auth import (
    router as modular_router,
    root_router,
    register,
    login,
    rotate_api_key,
    get_profile as get_my_profile,
    auth_callback,
    _db_auth_service as auth_service,
    bootstrap_admin,
    login_oidc,
    make_admin,
    list_api_keys,
    find_user_by_api_key,
)
from .maas.auth import (
    api_key_header,
    bearer_scheme,
    get_current_user as _modular_get_current_user_from_maas,
    require_role,
    require_permission,
    require_enterprise,
    require_pro,
    require_mesh_owner,
    require_mesh_access,
)
from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth_models import UserRegisterRequest
from src.api.maas_security import ApiKeyManager
from src.coordination.events import EventType
from src.core.reliability_policy import mark_degraded_dependency
from src.database import Session as UserSession
from src.database import User, get_db
from .maas.registry import record_audit_log

# Mock objects for tests
class _OIDCValidatorCompat:
    enabled = False
    issuer = ""
    client_id = ""
    def validate(self, token): return None

oidc_validator = _OIDCValidatorCompat()
oauth = None

logger = logging.getLogger(__name__)

warnings.warn(
    "src.api.maas_auth_legacy_full is deprecated. Use src.api.maas.auth instead.",
    DeprecationWarning,
    stacklevel=2,
)

_modular_register = register
_modular_login = login
_modular_rotate_api_key = rotate_api_key
_modular_get_my_profile = get_my_profile
_modular_auth_callback = auth_callback
_modular_bootstrap_admin = bootstrap_admin
_modular_login_oidc = login_oidc

def _maas_auth_user_model_available() -> bool:
    return User is not None and getattr(User, "__tablename__", "") == "users"


def _maas_auth_session_model_available() -> bool:
    return UserSession is not None and getattr(UserSession, "__tablename__", "") == "sessions"


def _maas_auth_service_available() -> bool:
    return callable(getattr(auth_service, "register", None)) and callable(
        getattr(auth_service, "login", None)
    )


def _maas_auth_api_key_manager_available() -> bool:
    return callable(getattr(ApiKeyManager, "generate", None)) and callable(
        getattr(ApiKeyManager, "hash_key", None)
    )


def _maas_auth_rbac_available() -> bool:
    return callable(require_role) and callable(require_permission)


def _maas_auth_token_helpers_available() -> bool:
    return callable(get_current_user_from_maas)


def _maas_auth_audit_log_available() -> bool:
    return callable(record_audit_log)


def _maas_auth_oidc_enabled() -> bool:
    return bool(
        getattr(oidc_validator, "enabled", False)
        or (
            getattr(oidc_validator, "issuer", None)
            and getattr(oidc_validator, "client_id", None)
        )
    )


def _maas_auth_oidc_redirect_available() -> bool:
    return oauth is not None


def _maas_auth_bootstrap_token_configured() -> bool:
    return bool(os.getenv("BOOTSTRAP_TOKEN"))


def _maas_auth_db_ready(db: Any) -> bool:
    return all(callable(getattr(db, name, None)) for name in ("query", "add", "commit", "refresh"))


def _maas_auth_public_module():
    return sys.modules.get("src.api.maas_auth", sys.modules[__name__])


def _maas_auth_public_attr(name: str) -> Any:
    return getattr(_maas_auth_public_module(), name, globals()[name])


def _maas_auth_public_helper(name: str):
    return _maas_auth_public_attr(name)


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _event_bus_from_request(request: Any):
    return getattr(getattr(request, "state", None), "event_bus", None)


def _publish_auth_event(request: Any, source_agent: str, payload: Dict[str, Any]) -> None:
    bus = _event_bus_from_request(request)
    if bus is None:
        return
    data = {
        "service_name": source_agent,
        "source_alias": source_agent,
        **payload,
    }
    bus.publish(EventType.PIPELINE_STAGE_END, source_agent, data)


def _user_id(user: Any) -> str:
    return str(getattr(user, "id", None) or getattr(user, "user_id", "") or "")


def _request_header(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", {}) or {}
    try:
        return headers.get(name) or headers.get(name.lower())
    except AttributeError:
        return None


MAAS_AUTH_READINESS_CLAIM_BOUNDARY = (
    "MaaS auth readiness reports local import, DB-session, and dependency "
    "availability only. It does not create a user, prove production readiness, "
    "or prove live authentication traffic."
)


def _maas_auth_readiness_status(db: Any) -> Dict[str, Any]:
    auth_db_ready = _maas_auth_public_helper("_maas_auth_db_ready")(db)
    user_model_ready = _maas_auth_public_helper("_maas_auth_user_model_available")()
    session_model_ready = _maas_auth_public_helper("_maas_auth_session_model_available")()
    auth_service_ready = _maas_auth_public_helper("_maas_auth_service_available")()
    api_key_manager_ready = _maas_auth_public_helper("_maas_auth_api_key_manager_available")()
    rbac_ready = _maas_auth_public_helper("_maas_auth_rbac_available")()
    token_helpers_ready = _maas_auth_public_helper("_maas_auth_token_helpers_available")()
    audit_log_ready = _maas_auth_public_helper("_maas_auth_audit_log_available")()
    oidc_enabled = _maas_auth_public_helper("_maas_auth_oidc_enabled")()
    oidc_redirect_ready = _maas_auth_public_helper("_maas_auth_oidc_redirect_available")()
    bootstrap_token_configured = _maas_auth_public_helper(
        "_maas_auth_bootstrap_token_configured"
    )()

    checks = [
        ("database", auth_db_ready),
        ("user_model", user_model_ready),
        ("session_model", session_model_ready),
        ("auth_service", auth_service_ready),
        ("api_key_manager", api_key_manager_ready),
        ("rbac", rbac_ready),
        ("token_helpers", token_helpers_ready),
        ("audit_log", audit_log_ready),
    ]
    if oidc_enabled:
        checks.append(("oidc_redirect", oidc_redirect_ready))

    degraded_dependencies = [name for name, ready in checks if not ready]
    maas_auth_runtime_ready = not degraded_dependencies

    return {
        "status": "ready" if maas_auth_runtime_ready else "degraded",
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
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "bootstrap_token": (
                "BOOTSTRAP_TOKEN is intentionally optional; when absent the "
                "bootstrap-admin endpoint is disabled."
            ),
        },
        "claim_boundary": MAAS_AUTH_READINESS_CLAIM_BOUNDARY,
        "production_readiness_claim_allowed": False,
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_auth_readiness"
        ),
    }


async def maas_auth_readiness(
    request: Request,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    """Return local dependency readiness for the legacy MaaS auth surface."""
    payload = _maas_auth_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


async def register(
    req: Any,
    request: Request = None,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    service = _maas_auth_public_attr("auth_service")
    try:
        user = service.register(db, req)
        api_key = service.issued_api_key(user) or ""
        _publish_auth_event(
            request,
            "maas-auth-register",
            {
                "operation": "maas_auth_register",
                "layer": "api_auth_registration_intent",
                "stage": "register_created",
                "status": "success",
                "request_summary": {
                    "email_hash": _redacted_sha256_prefix(str(req.email).lower()),
                    "email_present": bool(getattr(req, "email", None)),
                    "password_present": bool(getattr(req, "password", None)),
                    "full_name_present": bool(getattr(req, "full_name", None)),
                    "company_present": bool(getattr(req, "company", None)),
                },
                "user_id_hash": _redacted_sha256_prefix(_user_id(user)),
                "token_issued": bool(api_key),
                "local_db_write": True,
                "http_status_code": 200,
                "control_action": True,
                "raw_identifiers_redacted": True,
                "raw_credentials_redacted": True,
            },
        )
        return {
            "user_id": _user_id(user),
            "email": str(getattr(user, "email", getattr(req, "email", "")) or ""),
            "api_key": api_key,
            "access_token": api_key,
            "message": "User registered successfully",
        }
    except HTTPException as exc:
        _publish_auth_event(
            request,
            "maas-auth-register",
            {
                "operation": "maas_auth_register",
                "layer": "api_auth_registration_intent",
                "stage": "register_failed",
                "status": "failed",
                "request_summary": {
                    "email_hash": _redacted_sha256_prefix(str(req.email).lower()),
                    "email_present": bool(getattr(req, "email", None)),
                    "password_present": bool(getattr(req, "password", None)),
                    "full_name_present": bool(getattr(req, "full_name", None)),
                    "company_present": bool(getattr(req, "company", None)),
                },
                "token_issued": False,
                "local_db_write": False,
                "http_status_code": exc.status_code,
                "reason": f"http_{exc.status_code}",
                "control_action": True,
                "raw_identifiers_redacted": True,
                "raw_credentials_redacted": True,
            },
        )
        raise


async def login(
    req: Any,
    request: Request = None,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    service = _maas_auth_public_attr("auth_service")
    try:
        api_key = service.login(db, req)
        _publish_auth_event(
            request,
            "maas-auth-login",
            {
                "operation": "maas_auth_login",
                "layer": "api_auth_login_intent",
                "stage": "login_succeeded",
                "status": "success",
                "request_summary": {
                    "email_hash": _redacted_sha256_prefix(str(req.email).lower()),
                    "password_present": bool(getattr(req, "password", None)),
                },
                "token_issued": bool(api_key),
                "local_db_write": True,
                "http_status_code": 200,
                "raw_credentials_redacted": True,
            },
        )
        return {"user_id": "", "session_token": api_key, "access_token": api_key}
    except HTTPException as exc:
        _publish_auth_event(
            request,
            "maas-auth-login",
            {
                "operation": "maas_auth_login",
                "layer": "api_auth_login_intent",
                "stage": "login_failed",
                "status": "failed",
                "request_summary": {
                    "email_hash": _redacted_sha256_prefix(str(req.email).lower()),
                    "password_present": bool(getattr(req, "password", None)),
                },
                "token_issued": False,
                "local_db_write": False,
                "http_status_code": exc.status_code,
                "reason": f"http_{exc.status_code}",
                "raw_credentials_redacted": True,
            },
        )
        raise


async def rotate_api_key(
    request: Request,
    current_user: Any = Depends(_modular_get_current_user_from_maas),
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    service = _maas_auth_public_attr("auth_service")
    user_id = _user_id(current_user)
    previous_hash_present = bool(getattr(current_user, "api_key_hash", None))
    audit_recorded = False
    try:
        api_key, rotated_at = service.rotate_api_key(db, current_user)
        try:
            _maas_auth_public_attr("record_audit_log")(
                db, user_id, "api_key_rotated"
            )
            audit_recorded = True
        except Exception:
            audit_recorded = False
        _publish_auth_event(
            request,
            "maas-auth-api-key-rotation",
            {
                "operation": "maas_auth_api_key_rotation",
                "layer": "api_auth_credential_rotation",
                "stage": "api_key_rotated",
                "status": "success",
                "actor_user_id_hash": _redacted_sha256_prefix(user_id),
                "previous_api_key_hash_present": previous_hash_present,
                "new_api_key_issued": bool(api_key),
                "local_db_write": True,
                "audit_recorded": audit_recorded,
                "rotated_at_present": rotated_at is not None,
                "http_status_code": 200,
                "raw_credentials_redacted": True,
            },
        )
        return {"api_key": api_key, "created_at": rotated_at}
    except Exception as exc:
        _publish_auth_event(
            request,
            "maas-auth-api-key-rotation",
            {
                "operation": "maas_auth_api_key_rotation",
                "layer": "api_auth_credential_rotation",
                "stage": "api_key_rotation_failed",
                "status": "failed",
                "actor_user_id_hash": _redacted_sha256_prefix(user_id),
                "previous_api_key_hash_present": previous_hash_present,
                "new_api_key_issued": False,
                "local_db_write": False,
                "audit_recorded": False,
                "http_status_code": 500,
                "reason": type(exc).__name__,
                "raw_credentials_redacted": True,
            },
        )
        raise


async def make_admin(
    email: str,
    request: Request,
    db: Any = Depends(get_db),
    _admin: Any = Depends(require_role("admin")),
) -> Dict[str, Any]:
    admin_id = _user_id(_admin)
    normalized_email = str(email or "").strip().lower()
    target_user = db.query(User).filter(User.email == normalized_email).first()
    if target_user is None:
        _publish_auth_event(
            request,
            "maas-auth-admin-promotion",
            {
                "operation": "maas_auth_admin_promotion",
                "layer": "api_auth_admin_privilege_control",
                "stage": "target_not_found",
                "status": "denied",
                "request_summary": {
                    "target_email_hash": _redacted_sha256_prefix(normalized_email),
                },
                "actor_user_id_hash": _redacted_sha256_prefix(admin_id),
                "http_status_code": 404,
                "local_db_write": False,
                "audit_recorded": False,
                "privilege_control": True,
                "raw_identifiers_redacted": True,
            },
        )
        raise HTTPException(status_code=404, detail="User not found")

    previous_role = str(getattr(target_user, "role", "user") or "user")
    target_user.role = "admin"
    db.commit()
    audit_recorded = False
    try:
        _maas_auth_public_attr("record_audit_log")(db, admin_id, "admin_promoted")
        audit_recorded = True
    except Exception:
        audit_recorded = False
    _publish_auth_event(
        request,
        "maas-auth-admin-promotion",
        {
            "operation": "maas_auth_admin_promotion",
            "layer": "api_auth_admin_privilege_control",
            "stage": "admin_promoted",
            "status": "success",
            "request_summary": {
                "target_email_hash": _redacted_sha256_prefix(normalized_email),
            },
            "actor_user_id_hash": _redacted_sha256_prefix(admin_id),
            "target_user_id_hash": _redacted_sha256_prefix(_user_id(target_user)),
            "previous_role": previous_role,
            "new_role": "admin",
            "local_db_write": True,
            "audit_recorded": audit_recorded,
            "privilege_control": True,
            "raw_identifiers_redacted": True,
        },
    )
    return {"message": f"User {email} is now an ADMIN"}


async def bootstrap_admin(
    request: Any,
    http_request: Request = None,
    x_bootstrap_token: Any = None,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    configured_token = os.getenv("BOOTSTRAP_TOKEN", "")
    provided_token = (
        x_bootstrap_token
        if isinstance(x_bootstrap_token, str)
        else _request_header(request, "X-Bootstrap-Token")
    )
    token_configured = bool(configured_token)
    provided_present = bool(provided_token)
    if not token_configured or not secrets.compare_digest(
        configured_token, provided_token or ""
    ):
        _publish_auth_event(
            request,
            "maas-auth-bootstrap-admin",
            {
                "operation": "maas_auth_bootstrap_admin",
                "layer": "api_auth_bootstrap_admin_control",
                "stage": "bootstrap_token_denied",
                "status": "denied",
                "bootstrap_token_configured": token_configured,
                "provided_token_present": provided_present,
                "http_status_code": 403,
                "local_db_write": False,
                "audit_recorded": False,
                "privilege_control": True,
            },
        )
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    body = await request.json() if hasattr(request, "json") else {}
    email = str(body.get("email", "")).strip().lower()
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin is not None:
        _publish_auth_event(
            request,
            "maas-auth-bootstrap-admin",
            {
                "operation": "maas_auth_bootstrap_admin",
                "layer": "api_auth_bootstrap_admin_control",
                "stage": "bootstrap_admin_exists",
                "status": "denied",
                "request_summary": {
                    "email_hash": _redacted_sha256_prefix(email),
                    "password_present": bool(body.get("password")),
                },
                "bootstrap_token_configured": True,
                "provided_token_present": provided_present,
                "existing_admin_present": True,
                "token_issued": False,
                "local_db_write": False,
                "audit_recorded": False,
                "privilege_control": True,
                "http_status_code": 409,
            },
        )
        raise HTTPException(status_code=409, detail="Admin already exists")

    req = UserRegisterRequest(
        email=email,
        password=str(body.get("password", "")),
        full_name=body.get("full_name"),
        company=body.get("company"),
    )
    service = _maas_auth_public_attr("auth_service")
    user = service.register(db, req)
    user.role = "admin"
    db.commit()
    api_key = service.issued_api_key(user) or ""
    audit_recorded = False
    try:
        _maas_auth_public_attr("record_audit_log")(
            db, _user_id(user), "bootstrap_admin_created"
        )
        audit_recorded = True
    except Exception:
        audit_recorded = False
    _publish_auth_event(
        request,
        "maas-auth-bootstrap-admin",
        {
            "operation": "maas_auth_bootstrap_admin",
            "layer": "api_auth_bootstrap_admin_control",
            "stage": "bootstrap_admin_created",
            "status": "success",
            "request_summary": {
                "email_hash": _redacted_sha256_prefix(email),
                "password_present": bool(body.get("password")),
            },
            "user_id_hash": _redacted_sha256_prefix(_user_id(user)),
            "bootstrap_token_configured": True,
            "provided_token_present": provided_present,
            "existing_admin_present": False,
            "token_issued": bool(api_key),
            "local_db_write": True,
            "audit_recorded": audit_recorded,
            "privilege_control": True,
        },
    )
    return {"message": f"Bootstrap admin {email} created", "api_key": api_key}


async def login_oidc(http_request: Request) -> Any:
    validator = _maas_auth_public_attr("oidc_validator")
    oauth_client = _maas_auth_public_attr("oauth")
    oidc_enabled = bool(
        getattr(validator, "enabled", False)
        or (getattr(validator, "issuer", None) and getattr(validator, "client_id", None))
    )
    if not oidc_enabled:
        _publish_auth_event(
            http_request,
            "maas-auth-oidc-login",
            {
                "operation": "maas_auth_oidc_login",
                "layer": "api_auth_oidc_redirect_intent",
                "stage": "oidc_not_configured",
                "status": "denied",
                "oidc_enabled": False,
                "redirect_uri_present": False,
                "http_status_code": 501,
                "raw_identifiers_redacted": True,
                "raw_credentials_redacted": True,
            },
        )
        raise HTTPException(status_code=501, detail="OIDC is not configured")
    if oauth_client is None:
        _publish_auth_event(
            http_request,
            "maas-auth-oidc-login",
            {
                "operation": "maas_auth_oidc_login",
                "layer": "api_auth_oidc_redirect_intent",
                "stage": "oidc_unavailable",
                "status": "denied",
                "oidc_enabled": True,
                "oauth_available": False,
                "redirect_uri_present": False,
                "http_status_code": 501,
                "raw_identifiers_redacted": True,
                "raw_credentials_redacted": True,
            },
        )
        raise HTTPException(status_code=501, detail="OIDC redirect unavailable")

    redirect_uri = str(http_request.url_for("auth_callback"))
    result = await oauth_client.oidc.authorize_redirect(http_request, redirect_uri)
    _publish_auth_event(
        http_request,
        "maas-auth-oidc-login",
        {
            "operation": "maas_auth_oidc_login",
            "layer": "api_auth_oidc_redirect_intent",
            "stage": "oidc_redirect_created",
            "status": "success",
            "oidc_enabled": True,
            "oauth_available": True,
            "redirect_uri_present": True,
            "http_status_code": getattr(result, "status_code", 307),
            "read_only": True,
            "control_action": True,
            "raw_identifiers_redacted": True,
            "raw_credentials_redacted": True,
        },
    )
    return result


async def auth_callback(
    http_request: Request,
    db: Any = Depends(get_db),
) -> Dict[str, Any]:
    validator = _maas_auth_public_attr("oidc_validator")
    oauth_client = _maas_auth_public_attr("oauth")
    token = await oauth_client.oidc.authorize_access_token(http_request)
    id_token = token.get("id_token")
    if not id_token:
        _publish_auth_event(
            http_request,
            "maas-auth-oidc-callback",
            {
                "operation": "maas_auth_oidc_callback",
                "layer": "api_auth_oidc_callback_control",
                "stage": "oidc_callback_failed",
                "status": "failed",
                "id_token_present": False,
                "claims_validated": False,
                "api_key_issued": False,
                "session_token_issued": False,
                "local_db_write": False,
                "http_status_code": 401,
                "reason": "http_400",
                "raw_credentials_redacted": True,
            },
        )
        raise HTTPException(status_code=401, detail="OIDC authentication failed")

    claims = validator.validate(id_token)
    email = str(getattr(claims, "email", "") or "").strip().lower()
    subject = str(getattr(claims, "sub", "") or "")
    issuer = str(getattr(claims, "issuer", getattr(validator, "issuer", "")) or "")
    user = db.query(User).filter(User.oidc_id == subject).first()
    existing_user_found = user is not None
    if user is None:
        user = db.query(User).filter(User.email == email).first()
    existing_user_linked = user is not None and not existing_user_found
    if user is None:
        raise HTTPException(status_code=401, detail="OIDC user not found")

    user.oidc_id = subject
    user.oidc_provider = issuer
    api_key = _maas_auth_public_attr("auth_service").issue_api_key(db, user)
    session_token = secrets.token_urlsafe(32)
    db.commit()
    if callable(getattr(db, "refresh", None)):
        db.refresh(user)
    _publish_auth_event(
        http_request,
        "maas-auth-oidc-callback",
        {
            "operation": "maas_auth_oidc_callback",
            "layer": "api_auth_oidc_callback_control",
            "stage": "oidc_callback_authenticated",
            "status": "success",
            "id_token_present": True,
            "claims_validated": True,
            "email_hash": _redacted_sha256_prefix(email),
            "oidc_subject_hash": _redacted_sha256_prefix(subject),
            "oidc_issuer_hash": _redacted_sha256_prefix(issuer),
            "user_id_hash": _redacted_sha256_prefix(_user_id(user)),
            "existing_user_found": True,
            "existing_user_linked": existing_user_linked,
            "new_user_created": False,
            "api_key_issued": bool(api_key),
            "session_token_issued": bool(session_token),
            "local_db_write": True,
            "http_status_code": 200,
            "raw_identifiers_redacted": True,
            "raw_credentials_redacted": True,
        },
    )
    return {
        "message": "Authenticated successfully",
        "session_token": session_token,
        "user": {
            "id": _user_id(user),
            "email": email,
            "api_key": api_key,
        },
    }


async def get_current_user_from_maas(
    request: Request,
    api_key: Any = Depends(api_key_header),
    bearer: Any = Depends(bearer_scheme),
    db: Any = Depends(get_db),
) -> Any:
    if _event_bus_from_request(request) is None:
        return await _modular_get_current_user_from_maas(
            request, api_key=api_key, bearer=bearer, db=db
        )

    raw_api_key = api_key if isinstance(api_key, str) else _request_header(request, "X-API-Key")
    user = _maas_auth_public_attr("find_user_by_api_key")(db, raw_api_key)
    if user is not None:
        _publish_auth_event(
            request,
            "maas-auth-credential-resolver",
            {
                "operation": "maas_auth_credential_resolver",
                "layer": "api_auth_credential_observed_state",
                "stage": "api_key_authenticated",
                "status": "success",
                "actor_user_id_hash": _redacted_sha256_prefix(_user_id(user)),
                "api_key_header_present": bool(raw_api_key),
                "api_key_user_found": True,
                "http_status_code": 200,
                "observed_state": True,
                "read_only": True,
                "raw_credentials_redacted": True,
            },
        )
        return user

    _publish_auth_event(
        request,
        "maas-auth-credential-resolver",
        {
            "operation": "maas_auth_credential_resolver",
            "layer": "api_auth_credential_observed_state",
            "stage": "authentication_failed",
            "status": "denied",
            "api_key_header_present": bool(raw_api_key),
            "api_key_user_found": False,
            "http_status_code": 401,
            "reason": "invalid_credentials",
            "raw_credentials_redacted": True,
        },
    )
    raise HTTPException(status_code=401, detail="Invalid credentials")


async def get_my_profile(
    request: Request = None,
    user: Any = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    if request is not None and _event_bus_from_request(request) is None:
        return await _modular_get_my_profile(request=request, user=user)

    email = str(getattr(user, "email", "") or "")
    oidc_linked = bool(getattr(user, "oidc_id", None))
    payload = {
        "email": email,
        "role": str(getattr(user, "role", "user") or "user"),
        "plan": str(getattr(user, "plan", "starter") or "starter"),
        "oidc_linked": oidc_linked,
    }
    _publish_auth_event(
        request,
        "maas-auth-profile-read",
        {
            "operation": "maas_auth_profile_read",
            "layer": "api_auth_profile_observed_state",
            "actor_user_id_hash": _redacted_sha256_prefix(_user_id(user)),
            "email_hash": _redacted_sha256_prefix(email.lower()),
            "oidc_linked": oidc_linked,
            "profile_fields_returned": ["email", "role", "plan", "oidc_linked"],
            "observed_state": True,
            "control_action": False,
        },
    )
    return payload


async def list_api_keys(
    request: Request,
    current_user: Any = Depends(get_current_user_from_maas),
    db: Any = Depends(get_db),
) -> list[Dict[str, Any]]:
    api_key_hash = str(getattr(current_user, "api_key_hash", "") or "")
    created_at = getattr(current_user, "created_at", None)
    result = [
        {
            "key_masked": f"{api_key_hash[:12]}..." if api_key_hash else None,
            "created_at": created_at,
        }
    ]
    _publish_auth_event(
        request,
        "maas-auth-api-key-read",
        {
            "operation": "maas_auth_api_key_read",
            "layer": "api_auth_api_key_observed_state",
            "actor_user_id_hash": _redacted_sha256_prefix(_user_id(current_user)),
            "api_key_hash_present": bool(api_key_hash),
            "masked_keys_returned": 1 if api_key_hash else 0,
            "created_at_present": created_at is not None,
            "observed_state": True,
            "raw_credentials_redacted": True,
        },
    )
    return result


# Combined router for legacy support with absolute v1 paths.
router = APIRouter(tags=["MaaS Auth Legacy"])
router.add_api_route(
    "/api/v1/maas/auth/readiness",
    maas_auth_readiness,
    methods=["GET"],
)
router.include_router(root_router, prefix="/api/v1/maas")
router.include_router(modular_router, prefix="/api/v1/maas/auth")
legacy_router = router

# Re-exports for existing imports
__all__ = [
    "router",
    "legacy_router",
    "get_current_user_from_maas",
    "get_my_profile",
    "register",
    "login",
    "rotate_api_key",
    "auth_callback",
    "require_role",
    "require_permission",
    "require_enterprise",
    "require_pro",
    "require_mesh_owner",
    "require_mesh_access",
]
