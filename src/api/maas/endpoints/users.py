"""
User Management API
Registration, authentication, and user profile management
"""

import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.core.reliability_policy import mark_degraded_dependency
from src.database import Session as DB_Session
from src.database import User, get_db
from src.api.maas_security import ApiKeyManager
from src.repositories import SessionRepository, UserRepository
from src.services.maas_auth_service import find_user_by_api_key

router = APIRouter( tags=["users"])


def _rate_limit_key(request: Request) -> str:
    """Use stable client IP in runtime, and isolate requests per test case under pytest."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return f"pytest:{request.url.path}:{secrets.token_hex(8)}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)

# Test-only in-memory store. Runtime API logic must use SQLAlchemy models.
users_db = {}


# Models
class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    company: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    company: Optional[str]
    plan: str
    created_at: datetime


class SessionResponse(BaseModel):
    token: str
    user: UserResponse
    expires_at: datetime


# Helper functions
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"x0tta6bl4_{secrets.token_urlsafe(32)}"


def generate_session_token() -> str:
    """Generate a session token"""
    return secrets.token_urlsafe(64)


# Endpoints
@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/hour")
async def register(
    request: Request, user_data: UserCreate, db: Session = Depends(get_db)
):
    """Register a new user"""
    user_repo = UserRepository(db)
    # Check if user already exists
    existing_user = user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Create user
    user_id = secrets.token_urlsafe(16)
    api_key = generate_api_key()

    user = User(
        id=user_id,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        company=user_data.company,
        plan="free",  # Default plan
        api_key=None,
        api_key_hash=ApiKeyManager.hash_key(api_key),
        requests_count=0,
        requests_limit=10000,  # Free tier limit
    )

    user = user_repo.create(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        plan=user.plan,
        created_at=user.created_at,
    )


@router.post("/login", response_model=SessionResponse)
@limiter.limit("5/minute")
async def login(
    request: Request, credentials: UserLogin, db: Session = Depends(get_db)
):
    """Login user and create session"""
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(credentials.email)

    if not user or not bcrypt.checkpw(
        credentials.password.encode(), user.password_hash.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Create session
    session_repo = SessionRepository(db)
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=24)

    session = DB_Session(
        token=token, user_id=user.id, email=user.email, expires_at=expires_at
    )

    session = session_repo.create(session)

    return SessionResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            company=user.company,
            plan=user.plan,
            created_at=user.created_at,
        ),
        expires_at=expires_at,
    )


@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current user profile based on API Key or Session"""
    user_repo = UserRepository(db)
    session_repo = SessionRepository(db)
    api_key = request.headers.get("X-API-Key")
    auth_header = request.headers.get("Authorization")

    user = None

    # Try to authenticate with session token first
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        session_entry = (
            db.query(DB_Session)
            .filter(
                DB_Session.token == token, DB_Session.expires_at > datetime.utcnow()
            )
            .first()
        )

        if session_entry:
            user = user_repo.get_by_id(session_entry.user_id)

    # If not authenticated by session, try API key
    if not user and api_key:
        user = find_user_by_api_key(db, api_key)

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Propagate user identity to request state for metrics/middleware
    request.state.user_id = user.id

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        plan=user.plan,
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Logout user by invalidating session"""
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]
        session_repo = SessionRepository(db)
        sessions = db.query(DB_Session).filter(DB_Session.token == token).all()
        for s in sessions:
            session_repo.delete(s.id)
    return {"message": "Logged out successfully"}


async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(status_code=403, detail="Admin access required")


def _users_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit", "refresh"))


def _user_model_available() -> bool:
    return all(
        hasattr(User, attr)
        for attr in (
            "id",
            "email",
            "password_hash",
            "full_name",
            "company",
            "plan",
            "api_key",
            "requests_count",
            "requests_limit",
            "created_at",
        )
    )


def _session_model_available() -> bool:
    return all(
        hasattr(DB_Session, attr)
        for attr in ("token", "user_id", "email", "expires_at", "created_at")
    )


def _password_hashing_available() -> bool:
    return all(
        callable(getattr(bcrypt, attr, None))
        for attr in ("hashpw", "checkpw", "gensalt")
    )


def _token_generation_available() -> bool:
    return callable(secrets.token_urlsafe) and callable(hmac.compare_digest)


def _users_limiter_available() -> bool:
    return callable(getattr(limiter, "limit", None))


def _users_admin_token_configured() -> bool:
    return bool(os.getenv("ADMIN_TOKEN"))


def _users_readiness_status(db: Any) -> Dict[str, Any]:
    users_db_ready = _users_db_session_available(db)
    user_model_ready = _user_model_available()
    session_model_ready = _session_model_available()
    password_hashing_ready = _password_hashing_available()
    token_generation_ready = _token_generation_available()
    rate_limiter_ready = _users_limiter_available()
    admin_token_ready = _users_admin_token_configured()
    users_runtime_ready = (
        users_db_ready
        and user_model_ready
        and session_model_ready
        and password_hashing_ready
        and token_generation_ready
        and rate_limiter_ready
        and admin_token_ready
    )

    degraded_dependencies = []
    if not users_db_ready:
        degraded_dependencies.append("database")
    if not user_model_ready:
        degraded_dependencies.append("user_model")
    if not session_model_ready:
        degraded_dependencies.append("session_model")
    if not password_hashing_ready:
        degraded_dependencies.append("password_hashing")
    if not token_generation_ready:
        degraded_dependencies.append("token_generation")
    if not rate_limiter_ready:
        degraded_dependencies.append("rate_limiter")
    if not admin_token_ready:
        degraded_dependencies.append("admin_token")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "users_runtime_ready": users_runtime_ready,
        "users_db_ready": users_db_ready,
        "user_model_ready": user_model_ready,
        "session_model_ready": session_model_ready,
        "password_hashing_ready": password_hashing_ready,
        "token_generation_ready": token_generation_ready,
        "rate_limiter_ready": rate_limiter_ready,
        "admin_token_ready": admin_token_ready,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/users",
            "boundary": (
                "Users routes use the fixed /api/v1/users prefix, so they are "
                "outside legacy MaaS catch-all matching. They are still "
                "full-mode-only because src.core.app only registers this router "
                "when light mode is disabled."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Registration, login, profile lookup, logout, stats, and user "
                "listing require a SQLAlchemy session with query/add/commit/refresh."
            ),
            "user_model": (
                "User rows carry credentials, profile fields, API keys, plan, and "
                "request quota state."
            ),
            "session_model": (
                "Session rows back bearer-token login and current-user lookup."
            ),
            "password_hashing": (
                "Registration and login depend on bcrypt hashpw/checkpw/gensalt."
            ),
            "token_generation": (
                "API keys, sessions, and admin-token comparison depend on secrets "
                "and hmac helpers."
            ),
            "rate_limiter": (
                "Public auth and admin routes are decorated with slowapi limiter rules."
            ),
            "admin_token": (
                "Stats and user-list endpoints fail closed when ADMIN_TOKEN is missing."
            ),
            "test_store": (
                "users_db is a test-only in-memory store and is intentionally not a "
                "runtime readiness dependency."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="users_readiness"
        ),
        "claim_boundary": (
            "Users readiness proves that the route imports and local dependency "
            "surfaces are present. It does not query the database, validate that "
            "bcrypt can verify every stored password, or prove that existing "
            "session tokens are unexpired."
        ),
    }


@router.get("/readiness")
async def users_readiness(request: Request, db: Session = Depends(get_db)):
    payload = _users_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/stats")
@limiter.limit("30/minute")
async def get_user_stats(
    request: Request, admin=Depends(verify_admin_token), db: Session = Depends(get_db)
):
    """Get user statistics (admin only)"""
    user_repo = UserRepository(db)
    total_users = user_repo.count()
    active_sessions = (
        db.query(DB_Session).filter(DB_Session.expires_at > datetime.utcnow()).count()
    )

    plans = {
        "free": db.query(User).filter(User.plan == "free").count(),
        "pro": db.query(User).filter(User.plan == "pro").count(),
        "enterprise": db.query(User).filter(User.plan == "enterprise").count(),
    }

    return {
        "total_users": total_users,
        "active_sessions": active_sessions,
        "plans": plans,
    }


@router.get("/", response_model=list[UserResponse])
@limiter.limit("30/minute")
async def get_users(
    request: Request, admin=Depends(verify_admin_token), db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    user_repo = UserRepository(db)
    users = user_repo.get_all(limit=200)
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            company=user.company,
            plan=user.plan,
            created_at=user.created_at,
        )
        for user in users
    ]
