"""
MaaS Auth Endpoints - Authentication endpoints.

Provides REST API endpoints for user registration, login, and API key management.
"""

import hashlib
import hmac
import logging
import secrets
import threading
import time
from collections import deque
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.coordination.events import EventBus, EventType, get_event_bus
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

router = APIRouter(tags=["auth"])


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


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account.",
)
async def register(
    request: RegisterRequest,
    http_request: Request = None,
) -> RegisterResponse:
    """
    Register a new user.

    Creates a new user account and returns an API key.
    """
    import secrets

    started = time.monotonic()
    normalized_email = _normalize_email(request.email)
    request_evidence = _request_summary(
        email=normalized_email,
        password=request.password,
        name=request.name,
    )

    # Check if email already exists
    for user_id, user_data in _user_store.items():
        if user_data.get("email") == normalized_email:
            _publish_modular_auth_event(
                http_request=http_request,
                source_agent=_MODULAR_AUTH_REGISTER_SOURCE_AGENT,
                operation="modular_auth_register",
                stage="register_blocked",
                status_text="blocked",
                started=started,
                http_status_code=status.HTTP_409_CONFLICT,
                request_summary=request_evidence,
                actor_summary=_actor_summary(None),
                store_summary=_store_summary(
                    action="duplicate_email_lookup",
                    attempted=True,
                    committed=False,
                    matched_user_id=user_id,
                ),
                credential_summary=_credential_summary(api_key_issued=False),
                reason="email_already_registered",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    # Generate user ID
    user_id = f"user_{secrets.token_hex(8)}"

    # Create user
    _user_store[user_id] = {
        "email": normalized_email,
        "name": request.name,
        "plan": "free",
        "password_hash": _hash_password(request.password),
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    # Generate API key
    auth = get_auth_service()
    api_key = auth.generate_api_key(user_id, "free")
    _publish_modular_auth_event(
        http_request=http_request,
        source_agent=_MODULAR_AUTH_REGISTER_SOURCE_AGENT,
        operation="modular_auth_register",
        stage="register_created",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_201_CREATED,
        request_summary=request_evidence,
        actor_summary=_actor_summary(None),
        store_summary=_store_summary(
            action="create_user",
            attempted=True,
            committed=True,
            matched_user_id=user_id,
        ),
        credential_summary=_credential_summary(api_key_issued=True),
    )

    return RegisterResponse(
        user_id=user_id,
        email=normalized_email,
        api_key=api_key,
        message="Registration successful",
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
    session_token = auth.create_session(user_id)
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


@router.post(
    "/api-key",
    response_model=ApiKeyRotateResponse,
    summary="Rotate API key",
    description="Generate a new API key (invalidates old one).",
)
async def rotate_api_key(
    request: ApiKeyRotateRequest,
    http_request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> ApiKeyRotateResponse:
    """
        Rotate the user's API key.

        Generates a new API key and optionally revokes the old one.
        """
    started = time.monotonic()
    auth = get_auth_service()
    revoked = False

    # Revoke old key if requested
    if request.revoke_old and user.api_key:
        auth.revoke_api_key(user.api_key)
        revoked = True

    # Generate new key
    new_key = auth.generate_api_key(user.user_id, user.plan)
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
        message="API key rotated successfully",
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
) -> UserProfileResponse:
    """Get the current user's profile."""
    started = time.monotonic()
    user_data = _user_store.get(user.user_id, {})
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
        user_id=user.user_id,
        email=user_data.get("email", "unknown"),
        name=user_data.get("name"),
        plan=user.plan,
        created_at=user_data.get("created_at"),
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
