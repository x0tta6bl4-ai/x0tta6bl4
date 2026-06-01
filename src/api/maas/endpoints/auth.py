"""
MaaS Auth Endpoints - Authentication endpoints.

Provides REST API endpoints for user registration, login, and API key management.
"""

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from collections import deque
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from src.database import User, get_db

from src.api.maas_auth_models import UserRegisterRequest as DBUserRegisterRequest
from src.api.maas_security import ApiKeyManager
from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.maas_auth_service import MaaSAuthService
from ..auth import (
    UserContext,
    get_auth_service,
    get_current_user,
)
from ..models import (
    ApiKeyRotateRequest,
    ApiKeyRotateResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserProfileResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
root_router = APIRouter(tags=["auth"])
_db_auth_service = MaaSAuthService(
    api_key_factory=ApiKeyManager.generate,
    default_plan="starter",
)


# In-memory user store (replace with database in production)
_user_store: Dict[str, Dict[str, Any]] = {}
_PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 60_000
_LOGIN_ATTEMPT_WINDOW_SECONDS = 300.0
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_ATTEMPTS: Dict[str, deque[float]] = {}
_LOGIN_ATTEMPT_LOCK = threading.Lock()
_MODULAR_AUTH_REGISTER_SOURCE_AGENT = "maas-modular-auth-register"
_MODULAR_AUTH_LOGIN_SOURCE_AGENT = "maas-modular-auth-login"
_MODULAR_AUTH_API_KEY_SOURCE_AGENT = "maas-modular-auth-api-key-rotation"
_MODULAR_AUTH_PROFILE_SOURCE_AGENT = "maas-modular-auth-profile-read"
_MODULAR_AUTH_SESSION_SOURCE_AGENT = "maas-modular-auth-session-control"
_MODULAR_AUTH_ACCOUNT_SOURCE_AGENT = "maas-modular-auth-account-delete"
_MODULAR_AUTH_LAYERS = {
    _MODULAR_AUTH_REGISTER_SOURCE_AGENT: "api_modular_auth_registration_intent",
    _MODULAR_AUTH_LOGIN_SOURCE_AGENT: "api_modular_auth_login_intent",
    _MODULAR_AUTH_API_KEY_SOURCE_AGENT: "api_modular_auth_credential_rotation",
    _MODULAR_AUTH_PROFILE_SOURCE_AGENT: "api_modular_auth_profile_observed_state",
    _MODULAR_AUTH_SESSION_SOURCE_AGENT: "api_modular_auth_session_control_action",
    _MODULAR_AUTH_ACCOUNT_SOURCE_AGENT: "api_modular_auth_account_delete_control_action",
}
_MODULAR_AUTH_CLAIM_BOUNDARY = (
    "Modular MaaS auth endpoint evidence only. It records local in-memory auth "
    "store reads/writes and AuthService credential/session calls with redacted "
    "request metadata; it does not expose raw credentials or prove external IdP "
    "authentication, durable database persistence, downstream API-key acceptance, "
    "billing cancellation, mesh termination, or complete account cleanup."
)
_KNOWN_PLAN_BUCKETS = {"free", "starter", "pro", "enterprise", "business", "premium"}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _auth_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is not None:
        event_bus = getattr(getattr(request, "state", None), "event_bus", None)
        if isinstance(event_bus, EventBus):
            return event_bus
        project_root = getattr(getattr(request, "state", None), "project_root", ".")
    else:
        project_root = "."
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize modular MaaS auth EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any, *, length: int = 16) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _safe_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, min(value, 1_000_000))
    try:
        return max(0, min(int(value), 1_000_000))
    except (TypeError, ValueError):
        return 0


def _length_bucket(value: Any) -> str:
    if value is None:
        return "missing"
    size = len(str(value))
    if size == 0:
        return "empty"
    if size <= 16:
        return "short"
    if size <= 64:
        return "medium"
    if size <= 256:
        return "long"
    return "very_long"


def _plan_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "missing"
    return text if text in _KNOWN_PLAN_BUCKETS else "custom"


def _request_summary(
    *,
    email: Optional[str] = None,
    password: Optional[str] = None,
    name: Optional[str] = None,
    revoke_old: Optional[bool] = None,
    confirm: Optional[bool] = None,
) -> Dict[str, Any]:
    return {
        "email_hash": _redacted_sha256_prefix(email),
        "email_present": bool(email),
        "email_length_bucket": _length_bucket(email),
        "password_present": password is not None,
        "password_length_bucket": _length_bucket(password),
        "name_present": bool(name),
        "name_length_bucket": _length_bucket(name),
        "revoke_old": revoke_old if isinstance(revoke_old, bool) else None,
        "confirm": confirm if isinstance(confirm, bool) else None,
        "raw_request_values_redacted": True,
    }


def _actor_summary(user: Optional[UserContext]) -> Dict[str, Any]:
    return {
        "authenticated": user is not None,
        "user_id_hash": _redacted_sha256_prefix(getattr(user, "user_id", None)),
        "plan": _plan_bucket(getattr(user, "plan", None)),
        "api_key_present": bool(getattr(user, "api_key", None)),
        "session_token_present": bool(getattr(user, "session_token", None)),
        "raw_actor_values_redacted": True,
    }


def _store_summary(
    *,
    action: str,
    attempted: bool,
    committed: bool,
    matched_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "storage_backend": "in_memory_user_store",
        "action": action,
        "attempted": bool(attempted),
        "committed": bool(committed),
        "users_total": _safe_count(len(_user_store)),
        "matched_user_id_hash": _redacted_sha256_prefix(matched_user_id),
        "raw_store_values_redacted": True,
    }


def _credential_summary(**flags: bool) -> Dict[str, Any]:
    allowed = {
        "api_key_issued",
        "api_key_revocation_attempted",
        "api_key_revoked",
        "session_token_issued",
        "session_end_attempted",
        "session_ended",
    }
    return {
        key: bool(value)
        for key, value in flags.items()
        if key in allowed
    } | {"raw_credentials_redacted": True}


def _remember_registered_user(
    *,
    user_id: str,
    email: str,
    name: Optional[str],
    plan: str,
    password: str,
    created_at: Any,
) -> None:
    _user_store[user_id] = {
        "email": email,
        "name": name,
        "plan": plan,
        "password_hash": _hash_password(password),
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else __import__("datetime").datetime.utcnow().isoformat(),
    }


def _register_db_backed_user(
    *,
    db: Session,
    request: RegisterRequest,
    http_request: Request | None,
    http_status_code: int,
) -> RegisterResponse:
    started = time.monotonic()
    normalized_email = _normalize_email(request.email)
    request_evidence = _request_summary(
        email=normalized_email,
        password=request.password,
        name=request.name,
    )

    db_req = DBUserRegisterRequest(
        email=request.email,
        password=request.password,
        full_name=request.name,
        company=None,
    )

    try:
        user = _db_auth_service.register(db, db_req)
        api_key = _db_auth_service.issued_api_key(user) or ApiKeyManager.generate()
        user.api_key = None
        user.api_key_hash = ApiKeyManager.hash_key(api_key)
        db.commit()

        _remember_registered_user(
            user_id=user.id,
            email=user.email,
            name=request.name,
            plan=user.plan or "starter",
            password=request.password,
            created_at=getattr(user, "created_at", None),
        )

        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_REGISTER_SOURCE_AGENT,
            operation="modular_auth_register",
            stage="register_created",
            status_text="success",
            started=started,
            http_status_code=http_status_code,
            request_summary=request_evidence,
            actor_summary=_actor_summary(None),
            store_summary=_store_summary(
                action="create_user",
                attempted=True,
                committed=True,
                matched_user_id=user.id,
            ),
            credential_summary=_credential_summary(api_key_issued=bool(api_key)),
        )

        return RegisterResponse(
            user_id=user.id,
            email=user.email,
            api_key=api_key,
            access_token=api_key,
            message="Registration successful",
        )
    except HTTPException as exc:
        if (
            exc.status_code == status.HTTP_400_BAD_REQUEST
            and exc.detail == "Email already registered"
        ):
            exc = HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_REGISTER_SOURCE_AGENT,
            operation="modular_auth_register",
            stage="register_blocked",
            status_text="blocked",
            started=started,
            http_status_code=exc.status_code,
            request_summary=request_evidence,
            actor_summary=_actor_summary(None),
            store_summary=_store_summary(
                action="register_call",
                attempted=True,
                committed=False,
            ),
            credential_summary=_credential_summary(api_key_issued=False),
            reason=str(exc.detail),
        )
        raise exc


def _http_event_type(status_code: int) -> EventType:
    if status_code >= 500:
        return EventType.TASK_FAILED
    if status_code >= 400:
        return EventType.TASK_BLOCKED
    return EventType.PIPELINE_STAGE_END


def _publish_modular_auth_event(
    *,
    http_request: Request | None,
    source_agent: str,
    operation: str,
    stage: str,
    status_text: str,
    started: float,
    http_status_code: int,
    request_summary: Optional[Dict[str, Any]] = None,
    actor_summary: Optional[Dict[str, Any]] = None,
    store_summary: Optional[Dict[str, Any]] = None,
    credential_summary: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    event_type: Optional[EventType] = None,
) -> Optional[str]:
    event_bus = _auth_event_bus_from_request(http_request)
    if event_bus is None:
        return None

    duration_ms = (time.monotonic() - started) * 1000.0
    layer = _MODULAR_AUTH_LAYERS[source_agent]
    payload: Dict[str, Any] = {
        "component": "api.maas.endpoints.auth",
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "stage": stage,
        "status": status_text,
        "duration_ms": round(duration_ms, 3),
        "http_status_code": http_status_code,
        "control_action": layer.endswith("_control_action")
        or "intent" in layer
        or "credential_rotation" in layer,
        "observed_state": "observed_state" in layer,
        "source_quality": "local_auth_store_observed",
        "request_summary": request_summary or {"raw_request_values_redacted": True},
        "actor_summary": actor_summary or _actor_summary(None),
        "auth_store_evidence": store_summary
        or _store_summary(action="none", attempted=False, committed=False),
        "credential_evidence": credential_summary
        or _credential_summary(),
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": _MODULAR_AUTH_CLAIM_BOUNDARY,
    }
    if reason:
        payload["reason"] = reason

    try:
        event = event_bus.publish(
            event_type or _http_event_type(http_status_code),
            source_agent,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS auth evidence: %s", exc)
        return None


def _prune_login_attempts(bucket: deque[float], now: float) -> None:
    cutoff = now - _LOGIN_ATTEMPT_WINDOW_SECONDS
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()


def _check_login_throttle(normalized_email: str) -> None:
    now = time.monotonic()
    with _LOGIN_ATTEMPT_LOCK:
        bucket = _LOGIN_ATTEMPTS.setdefault(normalized_email, deque())
        _prune_login_attempts(bucket, now)
        if len(bucket) >= _LOGIN_MAX_ATTEMPTS:
            retry_after = max(
                1,
                int(bucket[0] + _LOGIN_ATTEMPT_WINDOW_SECONDS - now),
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )


def _record_failed_login(normalized_email: str) -> None:
    now = time.monotonic()
    with _LOGIN_ATTEMPT_LOCK:
        bucket = _LOGIN_ATTEMPTS.setdefault(normalized_email, deque())
        _prune_login_attempts(bucket, now)
        bucket.append(now)


def _clear_failed_logins(normalized_email: str) -> None:
    with _LOGIN_ATTEMPT_LOCK:
        _LOGIN_ATTEMPTS.pop(normalized_email, None)


def _hash_password(password: str, *, salt_hex: Optional[str] = None) -> str:
    """Hash password with PBKDF2-HMAC-SHA256 for in-memory auth store."""
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"{_PASSWORD_HASH_SCHEME}$"
        f"{_PASSWORD_HASH_ITERATIONS}$"
        f"{salt_hex}$"
        f"{digest.hex()}"
    )


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify plaintext password against PBKDF2 hash."""
    try:
        scheme, iterations_raw, salt_hex, expected_hex = password_hash.split("$", 3)
        if scheme != _PASSWORD_HASH_SCHEME:
            return False
        iterations = int(iterations_raw)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except Exception:
        return False


@root_router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account.",
)
async def register_root(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> RegisterResponse:
    """Register a new user using the durable DB-backed auth store."""
    return _register_db_backed_user(
        db=db,
        request=request,
        http_request=http_request,
        http_status_code=status.HTTP_201_CREATED,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
    summary="Register new user",
    description="Create a new user account.",
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> RegisterResponse:
    """
    Register a new user using the same durable contract as the root endpoint.

    The namespaced endpoint keeps the historical 200 response code, but the
    returned ``api_key``/``access_token`` is persisted as ``api_key_hash`` in DB.
    """
    return _register_db_backed_user(
        db=db,
        request=request,
        http_request=http_request,
        http_status_code=status.HTTP_200_OK,
    )


@root_router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate user and get session token.",
)
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate user and get session token.",
)
async def login(
    request: LoginRequest,
    http_request: Request = None,
) -> LoginResponse:
    """
    Login with email and password.

    Returns a session token for subsequent requests.
    """
    started = time.monotonic()
    normalized_email = _normalize_email(request.email)
    request_evidence = _request_summary(
        email=normalized_email,
        password=request.password,
    )
    try:
        _check_login_throttle(normalized_email)
    except HTTPException:
        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_LOGIN_SOURCE_AGENT,
            operation="modular_auth_login",
            stage="login_rate_limited",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            request_summary=request_evidence,
            actor_summary=_actor_summary(None),
            store_summary=_store_summary(
                action="throttle_check",
                attempted=True,
                committed=False,
            ),
            credential_summary=_credential_summary(session_token_issued=False),
            reason="rate_limited",
        )
        raise

    # Find user by email
    user_id = None
    user_data = None

    for uid, data in _user_store.items():
        if data.get("email") == normalized_email:
            user_id = uid
            user_data = data
            break

    if not user_id:
        _record_failed_login(normalized_email)
        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_LOGIN_SOURCE_AGENT,
            operation="modular_auth_login",
            stage="login_rejected",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_401_UNAUTHORIZED,
            request_summary=request_evidence,
            actor_summary=_actor_summary(None),
            store_summary=_store_summary(
                action="find_user_by_email",
                attempted=True,
                committed=False,
            ),
            credential_summary=_credential_summary(session_token_issued=False),
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    password_hash = str(user_data.get("password_hash", ""))
    if not _verify_password(request.password, password_hash):
        _record_failed_login(normalized_email)
        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_LOGIN_SOURCE_AGENT,
            operation="modular_auth_login",
            stage="login_rejected",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_401_UNAUTHORIZED,
            request_summary=request_evidence,
            actor_summary=_actor_summary(None),
            store_summary=_store_summary(
                action="verify_password",
                attempted=True,
                committed=False,
                matched_user_id=user_id,
            ),
            credential_summary=_credential_summary(session_token_issued=False),
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    _clear_failed_logins(normalized_email)

    # Create session
    auth = get_auth_service()
    session_token = auth.create_session(
        user_id,
        plan=str(user_data.get("plan") or "starter"),
    )
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_LOGIN_SOURCE_AGENT,
        operation="modular_auth_login",
        stage="login_created_session",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        request_summary=request_evidence,
        actor_summary=_actor_summary(None),
        store_summary=_store_summary(
            action="verify_password",
            attempted=True,
            committed=False,
            matched_user_id=user_id,
        ),
        credential_summary=_credential_summary(session_token_issued=True),
    )

    return LoginResponse(
        user_id=user_id,
        session_token=session_token,
        expires_in=86400,  # 24 hours
    )


@root_router.get("/login/oidc", summary="Start OIDC login")
@router.get("/login/oidc", summary="Start OIDC login")
async def login_oidc(http_request: Request) -> Any:
    """Start OIDC login when enterprise OIDC is configured."""
    from src.api import maas_auth as legacy_auth

    oidc_validator = getattr(legacy_auth, "oidc_validator", None)
    if not bool(getattr(oidc_validator, "enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured",
        )
    if getattr(legacy_auth, "oauth", None) is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC redirect flow not available (authlib unavailable)",
        )
    return await legacy_auth.login_oidc(http_request)


@root_router.get("/callback", summary="Handle OIDC callback")
@router.get("/callback", summary="Handle OIDC callback")
async def auth_callback(
    http_request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Handle OIDC callback when enterprise OIDC is configured."""
    from src.api import maas_auth as legacy_auth

    oidc_validator = getattr(legacy_auth, "oidc_validator", None)
    if not bool(getattr(oidc_validator, "enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured",
        )
    if getattr(legacy_auth, "oauth", None) is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC redirect flow not available (authlib unavailable)",
        )
    return await legacy_auth.auth_callback(http_request, db)


@root_router.post(
    "/api-key",
    response_model=ApiKeyRotateResponse,
    summary="Rotate API key",
    description="Generate a new API key (invalidates old one).",
)
@router.post(
    "/api-key",
    response_model=ApiKeyRotateResponse,
    summary="Rotate API key",
    description="Generate a new API key (invalidates old one).",
)
async def rotate_api_key(
    request: ApiKeyRotateRequest | None = None,
    http_request: Request = None,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyRotateResponse:
    """
        Rotate the user's API key.

        Generates a new API key and optionally revokes the old one.
        """
    started = time.monotonic()
    request = request or ApiKeyRotateRequest()
    auth = get_auth_service()
    revoked = False

    # Revoke old key if requested
    if request.revoke_old and user.api_key:
        auth.revoke_api_key(user.api_key)
        revoked = True

    # Generate new key
    new_key = ApiKeyManager.generate()
    db_user = db.query(User).filter(User.id == user.user_id).first()
    if db_user is not None:
        db_user.api_key = None
        db_user.api_key_hash = ApiKeyManager.hash_key(new_key)
        db.commit()
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_API_KEY_SOURCE_AGENT,
        operation="modular_auth_rotate_api_key",
        stage="api_key_rotated",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        request_summary=_request_summary(revoke_old=request.revoke_old),
        actor_summary=_actor_summary(user),
        store_summary=_store_summary(
            action="auth_service_api_key_rotation",
            attempted=True,
            committed=True,
            matched_user_id=user.user_id,
        ),
        credential_summary=_credential_summary(
            api_key_issued=True,
            api_key_revocation_attempted=bool(request.revoke_old and user.api_key),
            api_key_revoked=revoked,
        ),
    )

    return ApiKeyRotateResponse(
        api_key=new_key,
        created_at=__import__("datetime").datetime.utcnow().isoformat(),
        message="API key rotated successfully",
    )


@root_router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get user profile",
    description="Get the current user's profile.",
)
@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get user profile",
    description="Get the current user's profile.",
)
async def get_profile(
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Get the current user's profile."""
    started = time.monotonic()
    user_data = _user_store.get(user.user_id, {})
    db_user = db.query(User).filter(User.id == user.user_id).first()
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_PROFILE_SOURCE_AGENT,
        operation="modular_auth_get_profile",
        stage="profile_read",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        actor_summary=_actor_summary(user),
        store_summary=_store_summary(
            action="read_user_profile",
            attempted=True,
            committed=False,
            matched_user_id=user.user_id if user_data else None,
        ),
        credential_summary=_credential_summary(),
    )

    return UserProfileResponse(
        id=user.user_id,
        user_id=user.user_id,
        email=(getattr(db_user, "email", None) if db_user is not None else None)
        or user_data.get("email", "unknown"),
        name=user_data.get("name"),
        plan=str(
            (getattr(db_user, "plan", None) if db_user is not None else None)
            or user_data.get("plan")
            or user.plan
        ),
        role=(getattr(db_user, "role", None) if db_user is not None else None)
        or user.role,
        requests_count=0,
        created_at=user_data.get("created_at"),
    )


@root_router.post("/set-admin/{email}", summary="Promote user to admin")
@router.post("/set-admin/{email}", summary="Promote user to admin")
async def set_admin(
    email: str,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Promote an existing user to admin. Requires an admin caller."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    normalized_email = _normalize_email(email)
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.role = "admin"
    db.commit()
    return {
        "message": f"User {normalized_email} promoted to admin",
        "email": normalized_email,
        "role": "admin",
    }


@root_router.post("/bootstrap-admin", summary="Bootstrap first admin")
@router.post("/bootstrap-admin", summary="Bootstrap first admin")
async def bootstrap_admin(
    request: RegisterRequest,
    http_request: Request = None,
    x_bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create the first admin using a local bootstrap token."""
    bootstrap_token = os.getenv("BOOTSTRAP_TOKEN", "")
    if not bootstrap_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap token not configured",
        )
    if not secrets.compare_digest(bootstrap_token, x_bootstrap_token or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bootstrap token",
        )
    if db.query(User).filter(User.role == "admin").first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin already exists - bootstrap disabled",
        )

    response = _register_db_backed_user(
        db=db,
        request=request,
        http_request=http_request,
        http_status_code=status.HTTP_200_OK,
    )
    user = db.query(User).filter(User.id == response.user_id).first()
    if user is not None:
        user.role = "admin"
        db.commit()

    return {
        "message": "Bootstrap admin created",
        "user_id": response.user_id,
        "email": response.email,
        "api_key": response.api_key,
        "access_token": response.access_token,
    }


@root_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="End the current session.",
)
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="End the current session.",
)
async def logout(
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> Dict[str, Any]:
    """End the current session."""
    started = time.monotonic()
    ended = False
    if user.session_token:
        auth = get_auth_service()
        auth.end_session(user.session_token)
        ended = True
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_SESSION_SOURCE_AGENT,
        operation="modular_auth_logout",
        stage="session_logout",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        actor_summary=_actor_summary(user),
        store_summary=_store_summary(
            action="auth_service_session_end",
            attempted=bool(user.session_token),
            committed=ended,
            matched_user_id=user.user_id,
        ),
        credential_summary=_credential_summary(
            session_end_attempted=bool(user.session_token),
            session_ended=ended,
        ),
    )

    return {
        "message": "Logged out successfully",
    }


@root_router.delete(
    "/account",
    status_code=status.HTTP_200_OK,
    summary="Delete account",
    description="Delete the user account and all associated data.",
)
@router.delete(
    "/account",
    status_code=status.HTTP_200_OK,
    summary="Delete account",
    description="Delete the user account and all associated data.",
)
async def delete_account(
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    confirm: bool = Query(..., description="Confirm account deletion"),
) -> Dict[str, Any]:
    """Delete the user account."""
    started = time.monotonic()
    if not confirm:
        _publish_modular_auth_event(
            http_request=http_request,
            source_agent=_MODULAR_AUTH_ACCOUNT_SOURCE_AGENT,
            operation="modular_auth_delete_account",
            stage="account_delete_blocked",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            request_summary=_request_summary(confirm=confirm),
            actor_summary=_actor_summary(user),
            store_summary=_store_summary(
                action="delete_user",
                attempted=False,
                committed=False,
                matched_user_id=user.user_id,
            ),
            credential_summary=_credential_summary(),
            reason="confirmation_required",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required",
        )

    # Revoke API key
    if user.api_key:
        auth = get_auth_service()
        auth.revoke_api_key(user.api_key)

    # End session
    if user.session_token:
        auth = get_auth_service()
        auth.end_session(user.session_token)

    # Delete user data
    user_existed = user.user_id in _user_store
    if user.user_id in _user_store:
        del _user_store[user.user_id]
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_ACCOUNT_SOURCE_AGENT,
        operation="modular_auth_delete_account",
        stage="account_deleted",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        request_summary=_request_summary(confirm=confirm),
        actor_summary=_actor_summary(user),
        store_summary=_store_summary(
            action="delete_user",
            attempted=True,
            committed=user_existed,
            matched_user_id=user.user_id,
        ),
        credential_summary=_credential_summary(
            api_key_revocation_attempted=bool(user.api_key),
            api_key_revoked=bool(user.api_key),
            session_end_attempted=bool(user.session_token),
            session_ended=bool(user.session_token),
        ),
    )

    # In production, also:
    # - Terminate all meshes
    # - Cancel subscriptions
    # - Delete billing records

    return {
        "message": "Account deleted successfully",
        "user_id": user.user_id,
    }


__all__ = ["router"]
