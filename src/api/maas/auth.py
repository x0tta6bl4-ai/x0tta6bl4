"""
MaaS Auth - FastAPI dependencies and authentication helpers.

Provides dependency injection for authentication, authorization, and user context.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .services import AuthService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security Schemes
# ---------------------------------------------------------------------------

# API Key authentication
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="api_key",
    description="MaaS API Key (maas_...)",
    auto_error=False,
)

# Bearer token authentication
bearer_scheme = HTTPBearer(
    scheme_name="bearer",
    description="Bearer token for session authentication",
    auto_error=False,
)


# ---------------------------------------------------------------------------
# User Context
# ---------------------------------------------------------------------------

@dataclass
class UserContext:
    """Authenticated user context."""

    user_id: str
    plan: str
    api_key: Optional[str] = None
    session_token: Optional[str] = None
    authenticated_at: datetime = None

    def __post_init__(self):
        if self.authenticated_at is None:
            self.authenticated_at = datetime.utcnow()

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return bool(self.user_id)

    @property
    def is_enterprise(self) -> bool:
        """Check if user has enterprise plan."""
        return self.plan == "enterprise"

    @property
    def is_pro(self) -> bool:
        """Check if user has pro plan or higher."""
        return self.plan in ("pro", "enterprise")


# ---------------------------------------------------------------------------
# Auth Service Instance
# ---------------------------------------------------------------------------

# Global auth service instance (can be overridden for testing)
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the global auth service."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def set_auth_service(service: AuthService) -> None:
    """Set the global auth service (for testing)."""
    global _auth_service
    _auth_service = service


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserContext:
    """
    FastAPI dependency to get the current authenticated user.

    Supports both API Key and Bearer token authentication.
    API Key takes precedence if both are provided.

    Raises:
        HTTPException: If authentication fails

    Returns:
        UserContext with user information
    """
    auth_service = get_auth_service()

    # Try API Key first
    if api_key:
        key_data = auth_service.validate_api_key(api_key)
        if key_data:
            return UserContext(
                user_id=key_data["user_id"],
                plan=key_data["plan"],
                api_key=api_key,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Try Bearer token
    if bearer:
        session = auth_service.validate_session(bearer.credentials)
        if session:
            return UserContext(
                user_id=session["user_id"],
                plan="unknown",  # Plan from session or lookup
                session_token=bearer.credentials,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "ApiKey, Bearer"},
    )


async def get_optional_user(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[UserContext]:
    """
    FastAPI dependency to get the current user (optional).

    Returns None if no credentials are provided, instead of raising.
    Useful for endpoints that have different behavior for authenticated users.

    Returns:
        UserContext if authenticated, None otherwise
    """
    auth_service = get_auth_service()

    # Try API Key first
    if api_key:
        key_data = auth_service.validate_api_key(api_key)
        if key_data:
            return UserContext(
                user_id=key_data["user_id"],
                plan=key_data["plan"],
                api_key=api_key,
            )

    # Try Bearer token
    if bearer:
        session = auth_service.validate_session(bearer.credentials)
        if session:
            return UserContext(
                user_id=session["user_id"],
                plan="unknown",
                session_token=bearer.credentials,
            )

    return None


async def require_enterprise(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Dependency that requires enterprise plan.

    Raises:
        HTTPException: If user doesn't have enterprise plan

    Returns:
        UserContext for enterprise user
    """
    if not user.is_enterprise:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise plan required",
        )
    return user


async def require_pro(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Dependency that requires pro plan or higher.

    Raises:
        HTTPException: If user doesn't have pro plan

    Returns:
        UserContext for pro user
    """
    if not user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro plan or higher required",
        )
    return user


# ---------------------------------------------------------------------------
# Mesh Ownership Dependencies
# ---------------------------------------------------------------------------

async def require_mesh_owner(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Dependency that requires user to own the mesh.

    Args:
        mesh_id: Mesh ID from path parameter
        user: Current user context

    Raises:
        HTTPException: If user doesn't own the mesh

    Returns:
        UserContext for mesh owner
    """
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
    Dependency that requires user to have access to the mesh.

    This is more permissive than ownership - it checks ACL policies.

    Args:
        mesh_id: Mesh ID from path parameter
        user: Current user context

    Raises:
        HTTPException: If user doesn't have access

    Returns:
        UserContext for user with mesh access
    """
    from .registry import get_mesh, get_mesh_policies

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    # Owner always has access
    if instance.owner_id == user.user_id:
        return user

    # Check ACL policies
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
    """
    Evaluate an ACL policy for a user action.

    Args:
        policy: Policy definition
        user: User context
        action: Action being performed
        resource: Resource being accessed

    Returns:
        True if policy allows the action
    """
    # Check principal
    principal = policy.get("principal", "*")
    if principal != "*" and principal != user.user_id:
        return False

    # Check action
    policy_action = policy.get("action", "*")
    if policy_action != "*" and policy_action != action:
        return False

    # Check resource
    policy_resource = policy.get("resource", "*")
    if policy_resource != "*" and not _match_resource(policy_resource, resource):
        return False

    # Check effect
    effect = policy.get("effect", "allow")
    return effect == "allow"


def _match_resource(pattern: str, resource: str) -> bool:
    """
    Match a resource pattern against a resource string.

    Supports wildcards:
    - * matches any single segment
    - ** matches any number of segments

    Args:
        pattern: Resource pattern (e.g., "mesh/*", "nodes/**")
        resource: Actual resource (e.g., "mesh/abc123", "nodes/xyz/actions/read")

    Returns:
        True if pattern matches resource
    """
    if pattern == resource:
        return True

    if "*" not in pattern:
        return False

    pattern_parts = pattern.split("/")
    resource_parts = resource.split("/")

    for i, p_part in enumerate(pattern_parts):
        if i >= len(resource_parts):
            return False

        if p_part == "**":
            # ** matches everything remaining
            return True

        if p_part != "*" and p_part != resource_parts[i]:
            return False

    return len(pattern_parts) == len(resource_parts)


# ---------------------------------------------------------------------------
# Rate Limiting Helpers
# ---------------------------------------------------------------------------

def check_rate_limit(
    user: UserContext,
    endpoint: str,
    requests_per_minute: int,
) -> None:
    """
    Check if user has exceeded rate limit for an endpoint.

    This is a simple in-memory rate limiter. For production,
    use a distributed rate limiter like Redis.

    Args:
        user: User context
        endpoint: Endpoint identifier
        requests_per_minute: Rate limit

    Raises:
        HTTPException: If rate limit exceeded
    """
    # This would integrate with the resilience module's rate limiter
    # For now, it's a placeholder
    pass


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # User context
    "UserContext",
    # Dependencies
    "get_current_user",
    "get_optional_user",
    "require_enterprise",
    "require_pro",
    "require_mesh_owner",
    "require_mesh_access",
    # Auth service
    "get_auth_service",
    "set_auth_service",
    # Security schemes
    "api_key_header",
    "bearer_scheme",
]
