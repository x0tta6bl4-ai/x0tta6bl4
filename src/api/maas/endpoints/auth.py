"""
MaaS Auth Endpoints - Authentication endpoints.

Provides REST API endpoints for user registration, login, and API key management.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import (
    UserContext,
    get_auth_service,
    get_current_user,
    get_optional_user,
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


# In-memory user store (replace with database in production)
_user_store: Dict[str, Dict[str, Any]] = {}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account.",
)
async def register(
    request: RegisterRequest,
) -> RegisterResponse:
    """
    Register a new user.

    Creates a new user account and returns an API key.
    """
    import secrets

    # Check if email already exists
    for user_id, user_data in _user_store.items():
        if user_data.get("email") == request.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    # Generate user ID
    user_id = f"user_{secrets.token_hex(8)}"

    # Create user
    _user_store[user_id] = {
        "email": request.email,
        "name": request.name,
        "plan": "free",
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    # Generate API key
    auth = get_auth_service()
    api_key = auth.generate_api_key(user_id, "free")

    return RegisterResponse(
        user_id=user_id,
        email=request.email,
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
) -> LoginResponse:
    """
    Login with email and password.

    Returns a session token for subsequent requests.
    """
    # Find user by email
    user_id = None
    user_data = None

    for uid, data in _user_store.items():
        if data.get("email") == request.email:
            user_id = uid
            user_data = data
            break

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # In production, verify password hash
    # For now, accept any password for demo

    # Create session
    auth = get_auth_service()
    session_token = auth.create_session(user_id)

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
    user: UserContext = Depends(get_current_user),
) -> ApiKeyRotateResponse:
    """
        Rotate the user's API key.

        Generates a new API key and optionally revokes the old one.
        """
    auth = get_auth_service()

    # Revoke old key if requested
    if request.revoke_old and user.api_key:
        auth.revoke_api_key(user.api_key)

    # Generate new key
    new_key = auth.generate_api_key(user.user_id, user.plan)

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
) -> UserProfileResponse:
    """Get the current user's profile."""
    user_data = _user_store.get(user.user_id, {})

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
) -> Dict[str, Any]:
    """End the current session."""
    if user.session_token:
        auth = get_auth_service()
        auth.end_session(user.session_token)

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
    confirm: bool = Query(..., description="Confirm account deletion"),
) -> Dict[str, Any]:
    """Delete the user account."""
    if not confirm:
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
    if user.user_id in _user_store:
        del _user_store[user.user_id]

    # In production, also:
    # - Terminate all meshes
    # - Cancel subscriptions
    # - Delete billing records

    return {
        "message": "Account deleted successfully",
        "user_id": user.user_id,
    }


__all__ = ["router"]
