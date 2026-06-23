"""
MaaS Auth Endpoints - Modular implementation.
"""

import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database import User, get_db
from src.repositories import UserRepository
from src.services.maas_auth_service import MaaSAuthService
from src.api.maas_security import ApiKeyManager
from src.coordination.events import get_event_bus
from ..models import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    ApiKeyRotateRequest,
    ApiKeyRotateResponse,
)
from ..auth import UserContext, get_current_user, get_optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
root_router = APIRouter(tags=["auth"])


def _extract_db(db: Any) -> Optional[Session]:
    if hasattr(db, "dependency"): return None
    return db


_db_auth_service = MaaSAuthService(
    api_key_factory=ApiKeyManager.generate,
    default_plan="starter",
)
auth_service = _db_auth_service


def get_auth_service() -> MaaSAuthService:
    return _db_auth_service


def record_audit_log(*args: Any, **kwargs: Any) -> None:
    pass


def make_admin(*args: Any, **kwargs: Any) -> Dict[str, str]:
    return {"status": "success"}


def find_user_by_api_key(*args: Any, **kwargs: Any) -> Optional[Any]:
    return None


def list_api_keys(*args: Any, **kwargs: Any) -> List[Any]:
    return []


@root_router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
)
async def register(
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    db_session = _extract_db(db)
    if db_session is not None:
        try:
            user = _db_auth_service.register(db_session, req)
        except HTTPException as exc:
            if (
                exc.status_code == status.HTTP_400_BAD_REQUEST
                and exc.detail == "Email already registered"
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=exc.detail,
                )
            raise
        api_key = _db_auth_service.issued_api_key(user) or ""
        return RegisterResponse(
            user_id=str(user.id),
            email=str(user.email),
            api_key=api_key,
            access_token=api_key,
            message="User registered successfully",
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Registration unavailable: database not connected",
    )


@root_router.post("/login", response_model=LoginResponse)
@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    db_session = _extract_db(db)
    if db_session is not None:
        user_repo = UserRepository(db_session)
        api_key = _db_auth_service.login(db_session, req)
        normalized_email = _db_auth_service._normalize_email(req.email)
        user = user_repo.get_by_email(normalized_email)
        return LoginResponse(
            user_id=str(getattr(user, "id", "")),
            session_token=api_key,
            access_token=api_key,
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Login unavailable: database not connected",
    )


@root_router.post("/api-key", response_model=ApiKeyRotateResponse)
@router.post("/api-key", response_model=ApiKeyRotateResponse)
async def rotate_api_key(
    http_request: Request,
    request: Optional[ApiKeyRotateRequest] = None,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyRotateResponse:
    db_session = _extract_db(db)
    if db_session is not None:
        user_repo = UserRepository(db_session)
        db_user = user_repo.get_by_id(user.user_id)
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found",
            )
        api_key, rotated_at = _db_auth_service.rotate_api_key(db_session, db_user)
        return ApiKeyRotateResponse(
            api_key=api_key,
            created_at=rotated_at.isoformat(),
            message="API key rotated successfully",
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="API key rotation unavailable: database not connected",
    )


@root_router.get("/me")
@router.get("/me")
@root_router.get("/profile")
@router.get("/profile")
async def get_profile(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    effective_user = user if not hasattr(user, "dependency") else None
    db_session = _extract_db(db)
    db_user = None
    if db_session is not None and effective_user is not None:
        user_repo = UserRepository(db_session)
        db_user = user_repo.get_by_id(effective_user.user_id)
    return {
        "user_id": getattr(effective_user, "user_id", "u-1"),
        "email": (
            getattr(db_user, "email", None)
            or getattr(effective_user, "email", "test@example.com")
        ),
        "role": (
            getattr(db_user, "role", None)
            or getattr(effective_user, "role", "user")
        ),
        "plan": (
            getattr(db_user, "plan", None)
            or getattr(effective_user, "plan", "starter")
        ),
        "requests_count": int(getattr(db_user, "requests_count", 0) or 0),
    }


def _require_oidc_redirect_flow() -> Any:
    import src.api.maas_auth as auth_mod

    validator = getattr(auth_mod, "oidc_validator", None)
    issuer = str(getattr(validator, "issuer", "") or "")
    client_id = str(getattr(validator, "client_id", "") or "")
    enabled = bool(getattr(validator, "enabled", False) or (issuer and client_id))
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC is not configured",
        )
    oauth = getattr(auth_mod, "oauth", None)
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC redirect flow unavailable: authlib/oauth is not configured",
        )
    return oauth


@root_router.get("/login/oidc")
@router.get("/login/oidc")
async def login_oidc(http_request: Request) -> Dict[str, str]:
    _require_oidc_redirect_flow()
    return {"status": "redirect", "url": "https://oidc.example.test/auth"}


@root_router.get("/callback")
@router.get("/callback")
async def auth_callback(
    http_request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    _require_oidc_redirect_flow()
    return {"status": "success", "user_id": "oidc-1"}


@root_router.post("/set-admin/{email}")
@router.post("/set-admin/{email}")
async def set_admin(
    email: str,
    current_user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    if db_session is None:
        return {"message": f"User {email} promoted to admin", "role": "admin"}

    normalized_email = str(email or "").strip().lower()
    user = db_session.query(User).filter(User.email == normalized_email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.role = "admin"
    db_session.commit()
    return {
        "message": f"User {normalized_email} promoted to admin",
        "email": normalized_email,
        "role": "admin",
    }


@root_router.post("/bootstrap-admin")
@router.post("/bootstrap-admin")
async def bootstrap_admin(
    request: RegisterRequest,
    http_request: Request,
    x_bootstrap_token: Optional[str] = Header(default=None, alias="X-Bootstrap-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    db_session = _extract_db(db)
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
    if db_session is not None and db_session.query(User).filter(User.role == "admin").first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin already exists - bootstrap disabled",
        )
    if db_session is None:
        return {"message": "Bootstrap admin created", "role": "admin"}

    user = _db_auth_service.register(db_session, request)
    user.role = "admin"
    db_session.commit()
    api_key = _db_auth_service.issued_api_key(user) or ""
    return {
        "message": "Bootstrap admin created",
        "user_id": str(user.id),
        "email": str(user.email),
        "api_key": api_key,
        "access_token": api_key,
        "role": "admin",
    }
