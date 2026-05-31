"""
MaaS SSO & RBAC Layer — x0tta6bl4
==================================

Handles OIDC authentication flows and role-based access control.
Supports Enterprise SSO (Google, GitHub, Okta).
"""

import logging
import os
import secrets
import hashlib
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth_models import (ApiKeyResponse, UserLoginRequest,
                                      UserRegisterRequest, TokenResponse)
from src.core.reliability_policy import mark_degraded_dependency
from src.database import User, Session as UserSession, get_db
from src.api.maas_security import oidc_validator, ApiKeyManager
from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.maas_auth_service import MaaSAuthService, find_user_by_api_key
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
auth_service = MaaSAuthService(
    api_key_factory=ApiKeyManager.generate,
    default_plan="starter",
)
API_KEY_TOKEN_TTL_SECONDS = 31_536_000

_AUTH_REGISTER_SOURCE_AGENT = "maas-auth-register"
_AUTH_REGISTER_LAYER = "api_auth_registration_intent"
_AUTH_REGISTER_CLAIM_BOUNDARY = (
    "MaaS auth register evidence only. It records bounded local registration "
    "intent and delegated MaaSAuthService outcome metadata; it does not prove "
    "email ownership, email verification, session use, or that returned API "
    "credentials were stored by the caller."
)
_AUTH_LOGIN_SOURCE_AGENT = "maas-auth-login"
_AUTH_LOGIN_LAYER = "api_auth_login_intent"
_AUTH_LOGIN_CLAIM_BOUNDARY = (
    "MaaS auth login evidence only. It records bounded local login intent and "
    "credential-check outcome metadata; it does not prove interactive session "
    "use, caller device trust, or that returned API credentials were stored."
)
_AUTH_API_KEY_ROTATE_SOURCE_AGENT = "maas-auth-api-key-rotation"
_AUTH_API_KEY_ROTATE_LAYER = "api_auth_credential_rotation"
_AUTH_API_KEY_ROTATE_CLAIM_BOUNDARY = (
    "MaaS API-key rotation evidence only. It records local credential rotation "
    "and audit-log attempt metadata; it does not expose old or new API keys and "
    "does not prove downstream clients stopped using old credentials."
)
_AUTH_ADMIN_PROMOTION_SOURCE_AGENT = "maas-auth-admin-promotion"
_AUTH_ADMIN_PROMOTION_LAYER = "api_auth_admin_privilege_control"
_AUTH_ADMIN_PROMOTION_CLAIM_BOUNDARY = (
    "MaaS admin promotion evidence only. It records local admin-role mutation "
    "and audit-log attempt metadata; it does not prove the promoted user has "
    "re-authenticated, that all cached sessions observed the new role, or that "
    "operator intent was externally approved."
)
_AUTH_BOOTSTRAP_ADMIN_SOURCE_AGENT = "maas-auth-bootstrap-admin"
_AUTH_BOOTSTRAP_ADMIN_LAYER = "api_auth_bootstrap_admin_control"
_AUTH_BOOTSTRAP_ADMIN_CLAIM_BOUNDARY = (
    "MaaS bootstrap-admin evidence only. It records local first-admin bootstrap "
    "guard decisions, local account creation, role mutation, and audit-log "
    "attempt metadata; it does not expose bootstrap tokens, passwords, API keys, "
    "or prove external operator authorization."
)
_AUTH_OIDC_LOGIN_SOURCE_AGENT = "maas-auth-oidc-login"
_AUTH_OIDC_LOGIN_LAYER = "api_auth_oidc_redirect_intent"
_AUTH_OIDC_LOGIN_CLAIM_BOUNDARY = (
    "MaaS OIDC login evidence only. It records local redirect intent, OIDC "
    "configuration state, redirect response metadata, and duration; it does not "
    "prove the upstream provider authenticated the caller or expose redirect URLs."
)
_AUTH_OIDC_CALLBACK_SOURCE_AGENT = "maas-auth-oidc-callback"
_AUTH_OIDC_CALLBACK_LAYER = "api_auth_oidc_callback_control"
_AUTH_OIDC_CALLBACK_CLAIM_BOUNDARY = (
    "MaaS OIDC callback evidence only. It records local callback/token validation, "
    "account-linkage, API-key issue, and session creation metadata; it does not "
    "expose ID tokens, API keys, session tokens, raw OIDC subjects, raw emails, "
    "or prove upstream provider state beyond local validator acceptance."
)
_AUTH_CREDENTIAL_RESOLVER_SOURCE_AGENT = "maas-auth-credential-resolver"
_AUTH_CREDENTIAL_RESOLVER_LAYER = "api_auth_credential_observed_state"
_AUTH_CREDENTIAL_RESOLVER_CLAIM_BOUNDARY = (
    "MaaS credential-resolver evidence only. It records local API-key or bearer "
    "session lookup outcome metadata and duration; it does not expose API keys, "
    "session tokens, raw emails, or prove caller device trust."
)
_AUTH_PROFILE_READ_SOURCE_AGENT = "maas-auth-profile-read"
_AUTH_PROFILE_READ_LAYER = "api_auth_profile_observed_state"
_AUTH_PROFILE_READ_CLAIM_BOUNDARY = (
    "MaaS profile-read evidence only. It records bounded authenticated profile "
    "read metadata; it does not expose raw emails, session tokens, API keys, or "
    "prove downstream UI state."
)
_AUTH_API_KEY_READ_SOURCE_AGENT = "maas-auth-api-key-read"
_AUTH_API_KEY_READ_LAYER = "api_auth_api_key_observed_state"
_AUTH_API_KEY_READ_CLAIM_BOUNDARY = (
    "MaaS API-key read evidence only. It records bounded masked-key listing "
    "metadata; it does not expose stored API-key hashes, API keys, fingerprints, "
    "or prove downstream client key custody."
)

# OAuth2 / OIDC Setup (redirect-based flow, only when authlib works)
oauth = _OAuth() if _oauth_available else None
if oauth is not None and oidc_validator.enabled:
    oidc_client_secret = os.getenv("OIDC_CLIENT_SECRET", "").strip() or None
    oauth.register(
        name='oidc',
        server_metadata_url=oidc_validator.issuer + oidc_validator.WELL_KNOWN_SUFFIX,
        client_id=oidc_validator.client_id,
        client_secret=oidc_client_secret,
        client_kwargs={'scope': 'openid email profile'},
    )


def _oidc_oauth_client_available() -> bool:
    """Return True only when authlib and the named OIDC client are both usable."""
    if oauth is None:
        return False
    try:
        getattr(oauth, "oidc")
    except AttributeError:
        return False
    return True

from src.core.rbac import MeshPermission, DEFAULT_ROLE_PERMISSIONS


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _maas_auth_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS auth EventBus: %s", exc)
        return None


def _auth_request_summary_for_evidence(req: Any) -> Dict[str, Any]:
    email = str(getattr(req, "email", "") or "").strip().lower()
    return {
        "email_hash": _redacted_sha256_prefix(email),
        "email_present": bool(email),
        "password_present": bool(getattr(req, "password", "")),
        "full_name_present": bool(getattr(req, "full_name", None)),
        "company_present": bool(getattr(req, "company", None)),
    }


def _publish_auth_register_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    req: Any,
    user: Any | None = None,
    token_issued: bool = False,
    local_db_write: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_register",
        "service_name": _AUTH_REGISTER_SOURCE_AGENT,
        "source_alias": _AUTH_REGISTER_SOURCE_AGENT,
        "layer": _AUTH_REGISTER_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "request_summary": _auth_request_summary_for_evidence(req),
        "user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "user_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "user_plan": str(getattr(user, "plan", ""))[:40] if user is not None else None,
        "token_issued": token_issued,
        "local_db_write": local_db_write,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_REGISTER_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_REGISTER_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth register event: %s", exc)
        return None


def _publish_auth_login_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    req: Any,
    token_issued: bool = False,
    local_db_write: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_login",
        "service_name": _AUTH_LOGIN_SOURCE_AGENT,
        "source_alias": _AUTH_LOGIN_SOURCE_AGENT,
        "layer": _AUTH_LOGIN_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "request_summary": _auth_request_summary_for_evidence(req),
        "token_issued": token_issued,
        "local_db_write": local_db_write,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_LOGIN_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_LOGIN_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth login event: %s", exc)
        return None


def _publish_auth_api_key_rotation_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    current_user: Any | None = None,
    previous_api_key_hash_present: bool = False,
    new_api_key_issued: bool = False,
    local_db_write: bool = False,
    audit_recorded: bool = False,
    rotated_at_present: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_api_key_rotation",
        "service_name": _AUTH_API_KEY_ROTATE_SOURCE_AGENT,
        "source_alias": _AUTH_API_KEY_ROTATE_SOURCE_AGENT,
        "layer": _AUTH_API_KEY_ROTATE_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "actor_plan": str(getattr(current_user, "plan", ""))[:40]
        if current_user is not None
        else None,
        "previous_api_key_hash_present": previous_api_key_hash_present,
        "new_api_key_issued": new_api_key_issued,
        "local_db_write": local_db_write,
        "audit_recorded": audit_recorded,
        "rotated_at_present": rotated_at_present,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_API_KEY_ROTATE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_API_KEY_ROTATE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth API-key rotation event: %s", exc)
        return None


def _admin_promotion_request_summary_for_evidence(email: Any) -> Dict[str, Any]:
    target_email = str(email or "").strip().lower()
    return {
        "target_email_hash": _redacted_sha256_prefix(target_email),
        "target_email_present": bool(target_email),
    }


def _publish_auth_admin_promotion_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    target_email: Any,
    admin_user: Any | None = None,
    target_user: Any | None = None,
    previous_role: str | None = None,
    new_role: str | None = None,
    local_db_write: bool = False,
    audit_recorded: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_admin_promotion",
        "service_name": _AUTH_ADMIN_PROMOTION_SOURCE_AGENT,
        "source_alias": _AUTH_ADMIN_PROMOTION_SOURCE_AGENT,
        "layer": _AUTH_ADMIN_PROMOTION_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "request_summary": _admin_promotion_request_summary_for_evidence(
            target_email
        ),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(admin_user, "id", None)
        )
        if admin_user is not None
        else None,
        "actor_role": str(getattr(admin_user, "role", ""))[:40]
        if admin_user is not None
        else None,
        "target_user_id_hash": _redacted_sha256_prefix(
            getattr(target_user, "id", None)
        )
        if target_user is not None
        else None,
        "previous_role": str(previous_role or "")[:40] if previous_role else None,
        "new_role": str(new_role or "")[:40] if new_role else None,
        "local_db_write": local_db_write,
        "audit_recorded": audit_recorded,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "privilege_control": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_ADMIN_PROMOTION_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_ADMIN_PROMOTION_SOURCE_AGENT,
            payload,
            priority=7,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth admin promotion event: %s", exc)
        return None


def _bootstrap_admin_request_summary_for_evidence(
    *,
    email: Any = None,
    password: Any = None,
) -> Dict[str, Any]:
    email_text = str(email or "").strip().lower()
    return {
        "email_hash": _redacted_sha256_prefix(email_text),
        "email_present": bool(email_text),
        "password_present": bool(password),
    }


def _publish_auth_bootstrap_admin_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    email: Any = None,
    password: Any = None,
    user: Any | None = None,
    bootstrap_token_configured: bool = False,
    provided_token_present: bool = False,
    existing_admin_present: bool | None = None,
    token_issued: bool = False,
    local_db_write: bool = False,
    audit_recorded: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_bootstrap_admin",
        "service_name": _AUTH_BOOTSTRAP_ADMIN_SOURCE_AGENT,
        "source_alias": _AUTH_BOOTSTRAP_ADMIN_SOURCE_AGENT,
        "layer": _AUTH_BOOTSTRAP_ADMIN_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "request_summary": _bootstrap_admin_request_summary_for_evidence(
            email=email,
            password=password,
        ),
        "user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "user_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "bootstrap_token_configured": bootstrap_token_configured,
        "provided_token_present": provided_token_present,
        "existing_admin_present": existing_admin_present,
        "token_issued": token_issued,
        "local_db_write": local_db_write,
        "audit_recorded": audit_recorded,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "privilege_control": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_BOOTSTRAP_ADMIN_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_BOOTSTRAP_ADMIN_SOURCE_AGENT,
            payload,
            priority=7,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth bootstrap-admin event: %s", exc)
        return None


def _publish_auth_oidc_login_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    oidc_enabled: bool,
    oauth_available: bool,
    redirect_uri_present: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_oidc_login",
        "service_name": _AUTH_OIDC_LOGIN_SOURCE_AGENT,
        "source_alias": _AUTH_OIDC_LOGIN_SOURCE_AGENT,
        "layer": _AUTH_OIDC_LOGIN_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "oidc_enabled": oidc_enabled,
        "oauth_available": oauth_available,
        "redirect_uri_present": redirect_uri_present,
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_OIDC_LOGIN_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_OIDC_LOGIN_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth OIDC login event: %s", exc)
        return None


def _publish_auth_oidc_callback_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    oidc_enabled: bool,
    oauth_available: bool,
    id_token_present: bool = False,
    claims_validated: bool = False,
    claims: Any | None = None,
    user: Any | None = None,
    existing_user_found: bool = False,
    existing_user_linked: bool = False,
    new_user_created: bool = False,
    api_key_issued: bool = False,
    session_token_issued: bool = False,
    local_db_write: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    claim_email = getattr(claims, "email", None)
    claim_subject = getattr(claims, "sub", None)
    claim_issuer = getattr(claims, "issuer", None)
    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_oidc_callback",
        "service_name": _AUTH_OIDC_CALLBACK_SOURCE_AGENT,
        "source_alias": _AUTH_OIDC_CALLBACK_SOURCE_AGENT,
        "layer": _AUTH_OIDC_CALLBACK_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "oidc_enabled": oidc_enabled,
        "oauth_available": oauth_available,
        "id_token_present": id_token_present,
        "claims_validated": claims_validated,
        "email_hash": _redacted_sha256_prefix(
            str(claim_email or "").strip().lower()
        ),
        "oidc_subject_hash": _redacted_sha256_prefix(claim_subject),
        "oidc_issuer_hash": _redacted_sha256_prefix(claim_issuer),
        "user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "user_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "existing_user_found": existing_user_found,
        "existing_user_linked": existing_user_linked,
        "new_user_created": new_user_created,
        "api_key_issued": api_key_issued,
        "session_token_issued": session_token_issued,
        "local_db_write": local_db_write,
        "http_status_code": http_status_code,
        "read_only": not local_db_write,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_OIDC_CALLBACK_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_OIDC_CALLBACK_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth OIDC callback event: %s", exc)
        return None


def _publish_auth_credential_resolver_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    user: Any | None = None,
    api_key_header_present: bool = False,
    authorization_header_present: bool = False,
    bearer_token_present: bool = False,
    api_key_user_found: bool = False,
    session_found: bool = False,
    session_valid: bool = False,
    session_user_found: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": stage,
        "operation": "maas_auth_credential_resolver",
        "service_name": _AUTH_CREDENTIAL_RESOLVER_SOURCE_AGENT,
        "source_alias": _AUTH_CREDENTIAL_RESOLVER_SOURCE_AGENT,
        "layer": _AUTH_CREDENTIAL_RESOLVER_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "actor_plan": str(getattr(user, "plan", ""))[:40] if user is not None else None,
        "api_key_header_present": api_key_header_present,
        "authorization_header_present": authorization_header_present,
        "bearer_token_present": bearer_token_present,
        "api_key_user_found": api_key_user_found,
        "session_found": session_found,
        "session_valid": session_valid,
        "session_user_found": session_user_found,
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_CREDENTIAL_RESOLVER_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_CREDENTIAL_RESOLVER_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth credential resolver event: %s", exc)
        return None


def _publish_auth_profile_read_event(
    request: Request | None,
    *,
    user: Any | None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    email = str(getattr(user, "email", "") or "").strip().lower()
    payload = {
        "component": "api.maas_auth",
        "stage": "profile_read",
        "operation": "maas_auth_profile_read",
        "service_name": _AUTH_PROFILE_READ_SOURCE_AGENT,
        "source_alias": _AUTH_PROFILE_READ_SOURCE_AGENT,
        "layer": _AUTH_PROFILE_READ_LAYER,
        "status": "success",
        "duration_ms": round(duration_ms, 3),
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "email_hash": _redacted_sha256_prefix(email),
        "email_present": bool(email),
        "actor_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "actor_plan": str(getattr(user, "plan", ""))[:40] if user is not None else None,
        "oidc_linked": bool(getattr(user, "oidc_id", None)),
        "profile_fields_returned": ["email", "role", "plan", "oidc_linked"],
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_PROFILE_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_PROFILE_READ_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth profile-read event: %s", exc)
        return None


def _publish_auth_api_key_read_event(
    request: Request | None,
    *,
    user: Any | None,
    api_key_hash_present: bool = False,
    masked_keys_returned: int = 0,
    created_at_present: bool = False,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _maas_auth_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_auth",
        "stage": "api_keys_listed",
        "operation": "maas_auth_api_key_read",
        "service_name": _AUTH_API_KEY_READ_SOURCE_AGENT,
        "source_alias": _AUTH_API_KEY_READ_SOURCE_AGENT,
        "layer": _AUTH_API_KEY_READ_LAYER,
        "status": "success",
        "duration_ms": round(duration_ms, 3),
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_role": str(getattr(user, "role", ""))[:40] if user is not None else None,
        "actor_plan": str(getattr(user, "plan", ""))[:40] if user is not None else None,
        "api_key_hash_present": api_key_hash_present,
        "masked_keys_returned": max(0, int(masked_keys_returned)),
        "created_at_present": created_at_present,
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _AUTH_API_KEY_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _AUTH_API_KEY_READ_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS auth API-key read event: %s", exc)
        return None


def _permission_to_value(permission: Union[MeshPermission, str]) -> str:
    if isinstance(permission, MeshPermission):
        return permission.value
    return str(permission).strip()


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
            "api_key_hash",
            "permissions",
            "created_at",
            "oidc_id",
            "oidc_provider",
        )
    )


def _maas_auth_session_model_available() -> bool:
    return all(
        hasattr(UserSession, attr)
        for attr in ("token", "user_id", "email", "expires_at")
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
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_auth_readiness"
        ),
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


def _default_permissions_for_role(role: str) -> set[str]:
    permissions: set[str] = set()
    if role in DEFAULT_ROLE_PERMISSIONS:
        permissions.update(_permission_to_value(p) for p in DEFAULT_ROLE_PERMISSIONS[role])
    permissions.update(_LEGACY_ROLE_DEFAULTS.get(role, set()))
    return permissions


def require_role(role: str):
    """Dependency factory for role-based access control."""
    def role_checker(user: User = Depends(get_current_user_from_maas)):
        if user.role != role and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role} privileges"
            )
        return user
    return role_checker

def require_permission(permission: Union[MeshPermission, str]):
    """Dependency factory for granular permission-based access control."""
    required_permission = _permission_to_value(permission)

    def permission_checker(user: User = Depends(get_current_user_from_maas)):
        # Admin bypass
        if user.role == "admin":
            return user

        # 1. Check explicit permissions string (comma-separated)
        if user.permissions:
            user_perms = [p.strip() for p in user.permissions.split(",")]
            if required_permission in user_perms or "*" in user_perms:
                return user

        # 2. Map default permissions for roles
        role_permissions = _default_permissions_for_role(user.role)
        if required_permission in role_permissions:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: required scope '{required_permission}'"
        )
    return permission_checker

def require_mesh_access(permission: Union[MeshPermission, str]):
    """
    Advanced Guard: Проверяет право доступа к КОНКРЕТНОЙ сети (mesh_id).

    Сценарии разрешения прав:
    1. Admin -> Всегда можно (Superuser).
    2. Owner -> Можно свои сети (Owner).
    3. Explicit Grant -> Можно, если есть запись в MeshOperatorPermission.
    4. Global Role -> Можно, если разрешено глобально для роли (Fallback).
    """
    from src.database import MeshInstance

    def access_checker(
        mesh_id: str,
        user: User = Depends(get_current_user_from_maas),
        db: Session = Depends(get_db)
    ):
        required_permission = _permission_to_value(permission)
        # Admin bypass
        if user.role == "admin":
            return user

        # 1. Проверяем существование сети и владельца
        mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
        if not mesh:
            raise HTTPException(status_code=404, detail="Mesh instance not found")

        # 2. Если пользователь владелец сети — разрешаем
        if mesh.owner_id == user.id:
            # Владельцу разрешены все базовые операции + специфические (MESH_WRITE и т.д.)
            # Мы разрешаем владельцу всё, что не запрещено политикой
            return user

        # 3. Проверка явных разрешений (Explicit Grants)
        try:
            from src.database import MeshOperatorPermission
            explicit = db.query(MeshOperatorPermission).filter(
                MeshOperatorPermission.user_id == user.id,
                MeshOperatorPermission.mesh_id == mesh_id,
                MeshOperatorPermission.permission == required_permission
            ).first()
            if explicit:
                return user
        except ImportError:
            # Таблица не существует — пропускаем
            pass

        # 4. Fallback на глобальные права роли
        role_permissions = _default_permissions_for_role(user.role)
        if required_permission in role_permissions:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No access to mesh {mesh_id} with scope {required_permission}"
        )
    return access_checker

async def get_current_user_from_maas(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Production-ready user resolver.
    Supports API Keys (X-API-Key) and Bearer tokens for Dashboard sessions.
    """
    started = time.monotonic()
    api_key_header_present = False
    authorization_header_present = False
    bearer_token_present = False
    api_key_user_found = False
    session_found = False
    session_valid = False
    session_user_found = False

    # 1. Check API Key Header (Prioritize machine-to-machine)
    api_key = request.headers.get("X-API-Key")
    api_key_header_present = bool(api_key)
    if api_key:
        user = find_user_by_api_key(db, api_key)
        if user:
            api_key_user_found = True
            _publish_auth_credential_resolver_event(
                request,
                stage="api_key_authenticated",
                status="success",
                user=user,
                api_key_header_present=api_key_header_present,
                authorization_header_present=authorization_header_present,
                bearer_token_present=bearer_token_present,
                api_key_user_found=api_key_user_found,
                session_found=session_found,
                session_valid=session_valid,
                session_user_found=session_user_found,
                http_status_code=200,
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="api_key_authenticated",
            )
            return user

    # 2. Check Bearer Token (Session-based for UI/Frontend)
    auth_header = request.headers.get("Authorization")
    authorization_header_present = bool(auth_header)
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        bearer_token_present = bool(token)
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if session:
            session_found = True
            if session.expires_at > datetime.utcnow():
                session_valid = True
                user = db.query(User).filter(User.id == session.user_id).first()
                if user:
                    session_user_found = True
                    _publish_auth_credential_resolver_event(
                        request,
                        stage="bearer_session_authenticated",
                        status="success",
                        user=user,
                        api_key_header_present=api_key_header_present,
                        authorization_header_present=authorization_header_present,
                        bearer_token_present=bearer_token_present,
                        api_key_user_found=api_key_user_found,
                        session_found=session_found,
                        session_valid=session_valid,
                        session_user_found=session_user_found,
                        http_status_code=200,
                        duration_ms=(time.monotonic() - started) * 1000.0,
                        reason="bearer_session_authenticated",
                    )
                    return user
            else:
                # Cleanup expired session (Background task candidate)
                logger.info(f"Session {session.token[:8]} expired for user {session.user_id}")
    reason = "invalid_credentials"
    if session_found and not session_valid:
        reason = "session_expired"
    elif session_valid and not session_user_found:
        reason = "session_user_not_found"
    _publish_auth_credential_resolver_event(
        request,
        stage="authentication_failed",
        status="denied",
        api_key_header_present=api_key_header_present,
        authorization_header_present=authorization_header_present,
        bearer_token_present=bearer_token_present,
        api_key_user_found=api_key_user_found,
        session_found=session_found,
        session_valid=session_valid,
        session_user_found=session_user_found,
        http_status_code=status.HTTP_401_UNAUTHORIZED,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason=reason,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials or session expired"
    )

@router.get("/keys")
async def list_api_keys(
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """List masked API keys for the current user."""
    started = time.monotonic()
    # Since we currently store keys in the User model directly,
    # we return the primary key masked.
    # In a future P3 upgrade, we should have a dedicated ApiKey model (One-to-Many).
    if not current_user.api_key_hash:
        _publish_auth_api_key_read_event(
            request,
            user=current_user,
            api_key_hash_present=False,
            masked_keys_returned=0,
            created_at_present=False,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="no_api_key_hash",
        )
        return []
    fingerprint = ApiKeyManager.fingerprint_from_hash(current_user.api_key_hash)
    result = [{
        "id": "primary",
        "name": "Primary Key",
        "key_masked": f"{fingerprint}...",
        "created_at": current_user.created_at or datetime.utcnow()
    }]
    _publish_auth_api_key_read_event(
        request,
        user=current_user,
        api_key_hash_present=True,
        masked_keys_returned=len(result),
        created_at_present=bool(getattr(current_user, "created_at", None)),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="masked_api_keys_listed",
    )
    return result

@router.post("/register", response_model=TokenResponse)
async def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Regular email registration."""
    started = time.monotonic()
    try:
        user = auth_service.register(db, req)
    except HTTPException as exc:
        _publish_auth_register_event(
            request,
            stage="register_failed",
            status="failed",
            req=req,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_auth_register_event(
            request,
            stage="register_failed",
            status="failed",
            req=req,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    issued_api_key = auth_service.issued_api_key(user)
    _publish_auth_register_event(
        request,
        stage="register_created",
        status="success",
        req=req,
        user=user,
        token_issued=bool(issued_api_key),
        local_db_write=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="user_registered",
    )
    return {
        "access_token": issued_api_key,
        "token_type": "api_key",
        "expires_in": API_KEY_TOKEN_TTL_SECONDS,
    }

@router.post("/login", response_model=TokenResponse)
async def login(
    req: UserLoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Regular email login."""
    started = time.monotonic()
    try:
        api_key = auth_service.login(db, req)
    except HTTPException as exc:
        _publish_auth_login_event(
            request,
            stage="login_failed",
            status="failed",
            req=req,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_auth_login_event(
            request,
            stage="login_failed",
            status="failed",
            req=req,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    _publish_auth_login_event(
        request,
        stage="login_succeeded",
        status="success",
        req=req,
        token_issued=bool(api_key),
        local_db_write=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="api_key_issued",
    )
    return {
        "access_token": api_key,
        "token_type": "api_key",
        "expires_in": API_KEY_TOKEN_TTL_SECONDS,
    }


@router.post("/api-key", response_model=ApiKeyResponse)
async def rotate_api_key(
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """Rotate API key for current authenticated user."""
    started = time.monotonic()
    previous_api_key_hash_present = bool(getattr(current_user, "api_key_hash", None))
    local_db_write = False
    new_api_key_issued = False
    audit_recorded = False
    rotated_at = None
    try:
        new_key, rotated_at = auth_service.rotate_api_key(db, current_user)
        local_db_write = True
        new_api_key_issued = bool(new_key)
        record_audit_log(
            db, request, "API_KEY_ROTATED",
            user_id=current_user.id,
            status_code=200
        )
        audit_recorded = True
    except HTTPException as exc:
        _publish_auth_api_key_rotation_event(
            request,
            stage="api_key_rotation_failed",
            status="failed",
            current_user=current_user,
            previous_api_key_hash_present=previous_api_key_hash_present,
            new_api_key_issued=new_api_key_issued,
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            rotated_at_present=bool(rotated_at),
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_auth_api_key_rotation_event(
            request,
            stage="api_key_rotation_failed",
            status="failed",
            current_user=current_user,
            previous_api_key_hash_present=previous_api_key_hash_present,
            new_api_key_issued=new_api_key_issued,
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            rotated_at_present=bool(rotated_at),
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    _publish_auth_api_key_rotation_event(
        request,
        stage="api_key_rotated",
        status="success",
        current_user=current_user,
        previous_api_key_hash_present=previous_api_key_hash_present,
        new_api_key_issued=new_api_key_issued,
        local_db_write=local_db_write,
        audit_recorded=audit_recorded,
        rotated_at_present=bool(rotated_at),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="api_key_rotated",
    )
    return {"api_key": new_key, "created_at": rotated_at}

@router.get("/login/oidc")
async def login_oidc(request: Request):
    """Redirect to configured OIDC provider."""
    started = time.monotonic()
    oidc_enabled = bool(getattr(oidc_validator, "enabled", False))
    oauth_available = _oidc_oauth_client_available()
    if not oidc_validator.enabled:
        _publish_auth_oidc_login_event(
            request,
            stage="oidc_not_configured",
            status="denied",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            http_status_code=501,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="oidc_not_configured",
        )
        raise HTTPException(status_code=501, detail="OIDC not configured")
    if not oauth_available:
        _publish_auth_oidc_login_event(
            request,
            stage="oidc_redirect_unavailable",
            status="denied",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            http_status_code=501,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="authlib_unavailable",
        )
        raise HTTPException(status_code=501, detail="OIDC redirect flow not available (authlib unavailable)")

    redirect_uri = None
    try:
        redirect_uri = request.url_for('auth_callback')
        response = await oauth.oidc.authorize_redirect(request, str(redirect_uri))
    except Exception as exc:
        _publish_auth_oidc_login_event(
            request,
            stage="oidc_redirect_failed",
            status="failed",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            redirect_uri_present=redirect_uri is not None,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    _publish_auth_oidc_login_event(
        request,
        stage="oidc_redirect_created",
        status="success",
        oidc_enabled=oidc_enabled,
        oauth_available=oauth_available,
        redirect_uri_present=True,
        http_status_code=getattr(response, "status_code", 302),
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="redirect_created",
    )
    return response

@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle OIDC callback and establish session."""
    started = time.monotonic()
    oidc_enabled = bool(getattr(oidc_validator, "enabled", False))
    oauth_available = _oidc_oauth_client_available()
    if not oidc_validator.enabled:
        _publish_auth_oidc_callback_event(
            request,
            stage="oidc_not_configured",
            status="denied",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            http_status_code=501,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="oidc_not_configured",
        )
        raise HTTPException(status_code=501, detail="OIDC not configured")
    if not oauth_available:
        _publish_auth_oidc_callback_event(
            request,
            stage="oidc_callback_unavailable",
            status="denied",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            http_status_code=501,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="authlib_unavailable",
        )
        raise HTTPException(status_code=501, detail="OIDC redirect flow not available (authlib unavailable)")

    id_token_present = False
    claims_validated = False
    existing_user_found = False
    existing_user_linked = False
    new_user_created = False
    api_key_issued = False
    session_token_issued = False
    local_db_write = False
    claims = None
    user = None
    try:
        token = await oauth.oidc.authorize_access_token(request)
        id_token = token.get('id_token')
        id_token_present = bool(id_token)
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing id_token")

        claims = oidc_validator.validate(id_token)
        claims_validated = True

        # Find or create user
        user = db.query(User).filter(User.oidc_id == claims.sub).first()
        existing_user_found = bool(user)
        if not user:
            # Check by email as fallback
            user = db.query(User).filter(User.email == claims.email).first()
            if user:
                # Link existing user to OIDC
                user.oidc_id = claims.sub
                user.oidc_provider = claims.issuer
                existing_user_found = True
                existing_user_linked = True
            else:
                # Create new enterprise user
                user = User(
                    id=str(uuid.uuid4()),
                    email=claims.email,
                    password_hash="!OIDC_NO_LOCAL_PASSWORD",  # Sentinel — rejected by verify_password()
                    full_name=claims.name,
                    oidc_id=claims.sub,
                    oidc_provider=claims.issuer,
                    role="user", # Default role
                    api_key=None,
                )
                db.add(user)
                new_user_created = True
        api_key = auth_service.issue_api_key(db, user)
        api_key_issued = bool(api_key)
        local_db_write = True
        db.refresh(user)

        # Create App Session
        session_token = secrets.token_urlsafe(64)
        session_token_issued = bool(session_token)
        new_session = UserSession(
            token=session_token,
            user_id=user.id,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        db.add(new_session)
        db.commit()
        _publish_auth_oidc_callback_event(
            request,
            stage="oidc_callback_authenticated",
            status="success",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            id_token_present=id_token_present,
            claims_validated=claims_validated,
            claims=claims,
            user=user,
            existing_user_found=existing_user_found,
            existing_user_linked=existing_user_linked,
            new_user_created=new_user_created,
            api_key_issued=api_key_issued,
            session_token_issued=session_token_issued,
            local_db_write=local_db_write,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="callback_authenticated",
        )

        # In a real app, we'd redirect to dashboard with the token
        return {
            "message": "Authenticated successfully",
            "session_token": session_token,
            "user": {
                "email": user.email,
                "role": user.role,
                "api_key": api_key
            }
        }

    except Exception as e:
        _publish_auth_oidc_callback_event(
            request,
            stage="oidc_callback_failed",
            status="failed",
            oidc_enabled=oidc_enabled,
            oauth_available=oauth_available,
            id_token_present=id_token_present,
            claims_validated=claims_validated,
            claims=claims,
            user=user,
            existing_user_found=existing_user_found,
            existing_user_linked=existing_user_linked,
            new_user_created=new_user_created,
            api_key_issued=api_key_issued,
            session_token_issued=session_token_issued,
            local_db_write=local_db_write,
            http_status_code=401,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{e.status_code}" if isinstance(e, HTTPException) else type(e).__name__,
        )
        logger.error(f"OIDC Auth failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

@router.get("/me")
async def get_my_profile(
    request: Request,
    user: User = Depends(get_current_user_from_maas),
):
    """Get current authenticated profile."""
    started = time.monotonic()
    result = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "plan": user.plan,
        "oidc_linked": bool(user.oidc_id)
    }
    _publish_auth_profile_read_event(
        request,
        user=user,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="profile_read",
    )
    return result

@router.post("/set-admin/{email}")
async def make_admin(
    email: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Promote a user to admin. Requires existing admin privileges."""
    started = time.monotonic()
    local_db_write = False
    audit_recorded = False
    user = db.query(User).filter(User.email == email).first()
    if not user:
        _publish_auth_admin_promotion_event(
            request,
            stage="target_not_found",
            status="denied",
            target_email=email,
            admin_user=_admin,
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="target_user_not_found",
        )
        raise HTTPException(status_code=404, detail="User not found")

    prev_role = user.role
    try:
        user.role = "admin"
        db.commit()
        local_db_write = True

        record_audit_log(
            db, request, "ADMIN_PROMOTION",
            user_id=_admin.id,
            payload={
                "target_email": email,
                "target_id": user.id,
                "prev_role": prev_role,
            },
            status_code=200
        )
        audit_recorded = True
    except HTTPException as exc:
        _publish_auth_admin_promotion_event(
            request,
            stage="admin_promotion_failed",
            status="failed",
            target_email=email,
            admin_user=_admin,
            target_user=user,
            previous_role=prev_role,
            new_role=getattr(user, "role", None),
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_auth_admin_promotion_event(
            request,
            stage="admin_promotion_failed",
            status="failed",
            target_email=email,
            admin_user=_admin,
            target_user=user,
            previous_role=prev_role,
            new_role=getattr(user, "role", None),
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    _publish_auth_admin_promotion_event(
        request,
        stage="admin_promoted",
        status="success",
        target_email=email,
        admin_user=_admin,
        target_user=user,
        previous_role=prev_role,
        new_role="admin",
        local_db_write=local_db_write,
        audit_recorded=audit_recorded,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="admin_promoted",
    )
    return {"message": f"User {email} is now an ADMIN"}


@router.post("/bootstrap-admin")
async def bootstrap_admin(
    request: Request,
    db: Session = Depends(get_db),
):
    """Create the first admin user when no admins exist.

    Requires the ``BOOTSTRAP_TOKEN`` environment variable to match the
    ``X-Bootstrap-Token`` request header. Disabled once any admin exists.
    """
    started = time.monotonic()
    bootstrap_token = os.getenv("BOOTSTRAP_TOKEN", "")
    if not bootstrap_token:
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_not_configured",
            status="denied",
            bootstrap_token_configured=False,
            provided_token_present=bool(request.headers.get("X-Bootstrap-Token", "")),
            http_status_code=403,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="bootstrap_not_configured",
        )
        raise HTTPException(status_code=403, detail="Bootstrap not configured")

    provided = request.headers.get("X-Bootstrap-Token", "")
    if not secrets.compare_digest(bootstrap_token, provided):
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_token_denied",
            status="denied",
            bootstrap_token_configured=True,
            provided_token_present=bool(provided),
            http_status_code=403,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="invalid_bootstrap_token",
        )
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    # Disabled once any admin exists (idempotency guard)
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_already_disabled",
            status="denied",
            bootstrap_token_configured=True,
            provided_token_present=bool(provided),
            existing_admin_present=True,
            http_status_code=409,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="admin_already_exists",
        )
        raise HTTPException(
            status_code=409,
            detail="Admin already exists — bootstrap disabled",
        )

    body = await request.json()
    email = body.get("email", "").strip()
    password = body.get("password", "")
    if not email or not password:
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_request_invalid",
            status="denied",
            email=email,
            password=password,
            bootstrap_token_configured=True,
            provided_token_present=bool(provided),
            existing_admin_present=False,
            http_status_code=422,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="missing_email_or_password",
        )
        raise HTTPException(status_code=422, detail="email and password required")

    from src.api.maas_auth_models import UserRegisterRequest
    req = UserRegisterRequest(email=email, password=password)
    local_db_write = False
    audit_recorded = False
    user = None
    api_key = None
    try:
        user = auth_service.register(db, req)
        user.role = "admin"
        api_key = auth_service.issued_api_key(user)
        db.commit()
        local_db_write = True

        record_audit_log(
            db, request, "BOOTSTRAP_ADMIN_CREATED",
            user_id=user.id,
            payload={"email": email},
            status_code=200
        )
        audit_recorded = True
    except HTTPException as exc:
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_admin_failed",
            status="failed",
            email=email,
            password=password,
            user=user,
            bootstrap_token_configured=True,
            provided_token_present=bool(provided),
            existing_admin_present=False,
            token_issued=bool(api_key),
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_auth_bootstrap_admin_event(
            request,
            stage="bootstrap_admin_failed",
            status="failed",
            email=email,
            password=password,
            user=user,
            bootstrap_token_configured=True,
            provided_token_present=bool(provided),
            existing_admin_present=False,
            token_issued=bool(api_key),
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    _publish_auth_bootstrap_admin_event(
        request,
        stage="bootstrap_admin_created",
        status="success",
        email=email,
        password=password,
        user=user,
        bootstrap_token_configured=True,
        provided_token_present=bool(provided),
        existing_admin_present=False,
        token_issued=bool(api_key),
        local_db_write=local_db_write,
        audit_recorded=audit_recorded,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="bootstrap_admin_created",
    )
    return {"message": f"Bootstrap admin {email} created", "api_key": api_key}
