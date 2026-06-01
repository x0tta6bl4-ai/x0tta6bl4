"""
MaaS Auth - FastAPI dependencies and authentication helpers.

Provides dependency injection for authentication, authorization, user context,
mesh access checks, and a small in-memory rate limiter used by the modular MaaS
API surface.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.api.maas_security import ApiKeyManager
from src.database import get_db
from src.services.maas_auth_service import MaaSAuthService, find_user_by_api_key

from .services import AuthService

logger = logging.getLogger(__name__)

_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_EVENTS: Dict[str, deque[float]] = {}


# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="api_key",
    description="MaaS API Key (maas_...)",
    auto_error=False,
)
bearer_scheme = HTTPBearer(
    scheme_name="bearer",
    description="Bearer token for session authentication",
    auto_error=False,
)

# Compatibility aliases used by the DB-backed auth path.
API_KEY_HEADER = api_key_header
BEARER_AUTH = bearer_scheme


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------

@dataclass
class UserContext:
    """Authenticated modular MaaS user context."""

    user_id: str
    plan: str
    api_key: Optional[str] = None
    session_token: Optional[str] = None
    authenticated_at: Optional[datetime] = None
    email: str = ""
    role: str = "user"
    scopes: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.authenticated_at is None:
            self.authenticated_at = datetime.utcnow()

    @property
    def id(self) -> str:
        """Compatibility alias for DB-backed helpers that expect User.id."""
        return self.user_id

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_id)

    @property
    def is_enterprise(self) -> bool:
        return self.plan == "enterprise"

    @property
    def is_pro(self) -> bool:
        return self.plan in ("pro", "enterprise")


# ---------------------------------------------------------------------------
# Auth service instances
# ---------------------------------------------------------------------------

_auth_service: Optional[AuthService] = None
_db_auth_service: Optional[MaaSAuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the modular in-memory auth service."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def set_auth_service(service: AuthService) -> None:
    """Set the modular auth service, mainly for tests."""
    global _auth_service
    _auth_service = service


def _get_db_auth_service() -> MaaSAuthService:
    """Get or create the DB-backed MaaS auth service used as fallback."""
    global _db_auth_service
    if _db_auth_service is None:
        _db_auth_service = MaaSAuthService(
            api_key_factory=ApiKeyManager.generate,
            default_plan="starter",
        )
    return _db_auth_service


def _as_user_context_from_db_user(user: Any, *, api_key: Optional[str] = None) -> UserContext:
    return UserContext(
        user_id=str(getattr(user, "id", "")),
        email=str(getattr(user, "email", "") or ""),
        role=str(getattr(user, "role", "user") or "user"),
        plan=str(getattr(user, "plan", "starter") or "starter"),
        api_key=api_key,
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserContext:
    """
    FastAPI dependency to get the current authenticated user.

    The v3.4 modular endpoints use the in-memory ``AuthService`` contract. The
    DB-backed lookup remains as a fallback so hashed persisted API keys can still
    authenticate without reintroducing plaintext DB key lookups.
    """
    auth_service = get_auth_service()

    if api_key:
        key_data = auth_service.validate_api_key(api_key)
        if key_data:
            return UserContext(
                user_id=str(key_data["user_id"]),
                plan=str(key_data.get("plan", "starter")),
                api_key=api_key,
            )

        session = auth_service.validate_session(api_key)
        if session:
            return UserContext(
                user_id=str(session["user_id"]),
                plan=str(session.get("plan", "unknown")),
                session_token=api_key,
            )

        try:
            db_user = find_user_by_api_key(db, api_key)
        except Exception as exc:
            logger.warning("DB-backed MaaS API key lookup failed: %s", exc)
            db_user = None
        if db_user is not None:
            return _as_user_context_from_db_user(db_user, api_key=api_key)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key or session token",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if bearer:
        session = auth_service.validate_session(bearer.credentials)
        if session:
            return UserContext(
                user_id=str(session["user_id"]),
                plan=str(session.get("plan", "unknown")),
                session_token=bearer.credentials,
            )

        try:
            db_user = _get_db_auth_service().validate_session(db, bearer.credentials)
        except Exception as exc:
            logger.warning("DB-backed MaaS session lookup failed: %s", exc)
            db_user = None
        if db_user is not None:
            context = _as_user_context_from_db_user(db_user)
            context.session_token = bearer.credentials
            return context

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "ApiKey, Bearer"},
    )


async def get_optional_user(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserContext]:
    """Return the current user or ``None`` when credentials are absent/invalid."""
    if not api_key and not bearer:
        return None
    try:
        return await get_current_user(request, api_key, bearer, db)
    except HTTPException:
        return None


async def require_enterprise(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Require an enterprise plan."""
    if not user.is_enterprise:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise plan required",
        )
    return user


async def require_pro(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Require a pro or enterprise plan."""
    if not user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro plan or higher required",
        )
    return user


async def get_optional_current_user(
    request: Request,
    api_key: Optional[str] = Depends(API_KEY_HEADER),
    token: Optional[HTTPAuthorizationCredentials] = Depends(BEARER_AUTH),
    db: Session = Depends(get_db),
) -> Optional[UserContext]:
    """Get current user if credentials provided, otherwise None."""
    return await get_optional_user(request, api_key, token, db)


def require_role(roles: Union[str, List[str]]):
    """FastAPI dependency factory requiring one of the supplied roles."""
    allowed_roles = [roles] if isinstance(roles, str) else list(roles)

    async def role_checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role == "admin":
            return user
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {', '.join(allowed_roles)}",
            )
        return user

    return role_checker


# ---------------------------------------------------------------------------
# Mesh access helpers
# ---------------------------------------------------------------------------

async def require_mesh_owner(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Require the authenticated user to own the mesh."""
    from .registry import get_mesh

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    if instance.owner_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this mesh",
        )

    return user


async def require_mesh_access(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Require the authenticated user to have access to the mesh.

    Owner access is allowed directly. Additional ACL policies are evaluated from
    the mesh registry.
    """
    from .registry import get_mesh, get_mesh_policies

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    if instance.owner_id == user.user_id:
        return user

    policies = get_mesh_policies(mesh_id)
    for policy in policies:
        if _evaluate_policy(policy, user, "access", f"mesh/{mesh_id}"):
            return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this mesh",
    )


def _evaluate_policy(
    policy: Dict[str, Any],
    user: UserContext,
    action: str,
    resource: str,
) -> bool:
    """Evaluate a simple ACL policy for a user action."""
    principal = policy.get("principal", "*")
    if principal != "*" and principal != user.user_id:
        return False

    policy_action = policy.get("action", "*")
    if policy_action != "*" and policy_action != action:
        return False

    policy_resource = policy.get("resource", "*")
    if policy_resource != "*" and not _match_resource(policy_resource, resource):
        return False

    return policy.get("effect", "allow") == "allow"


def _match_resource(pattern: str, resource: str) -> bool:
    """Match resource patterns with ``*`` and ``**`` wildcards."""
    if pattern == resource:
        return True

    if "*" not in pattern:
        return False

    pattern_parts = pattern.split("/")
    resource_parts = resource.split("/")

    for index, pattern_part in enumerate(pattern_parts):
        if pattern_part == "**":
            return True
        if index >= len(resource_parts):
            return False
        if pattern_part != "*" and pattern_part != resource_parts[index]:
            return False

    return len(pattern_parts) == len(resource_parts)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit(
    user: UserContext,
    endpoint: str,
    requests_per_minute: int,
) -> None:
    """Check and update the in-memory per-user/per-endpoint rate limit bucket."""
    if requests_per_minute <= 0:
        raise ValueError("requests_per_minute must be a positive integer")

    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    user_key = user.user_id or "anonymous"
    bucket_key = f"{user_key}:{endpoint}"

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_EVENTS.get(bucket_key)
        if bucket is None:
            bucket = deque()
            _RATE_LIMIT_EVENTS[bucket_key] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= requests_per_minute:
            retry_after = max(1, int(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded for '{endpoint}'. "
                    f"Limit: {requests_per_minute} requests per minute."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


def _clear_rate_limit_state() -> None:
    """Clear in-memory rate limiter state; intended for tests."""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_EVENTS.clear()


get_current_user_from_maas = get_current_user

__all__ = [
    "AuthService",
    "UserContext",
    "get_auth_service",
    "set_auth_service",
    "get_current_user",
    "get_optional_user",
    "require_enterprise",
    "require_pro",
    "require_role",
    "require_mesh_owner",
    "require_mesh_access",
    "_evaluate_policy",
    "_match_resource",
    "check_rate_limit",
    "_clear_rate_limit_state",
    "api_key_header",
    "bearer_scheme",
    "API_KEY_HEADER",
    "BEARER_AUTH",
]
