"""
MaaS SSO & RBAC Layer — x0tta6bl4
==================================

Handles OIDC authentication flows and role-based access control.
Supports Enterprise SSO (Google, GitHub, Okta).
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from src.api.maas_auth_models import (ApiKeyResponse, UserLoginRequest,
                                      UserRegisterRequest, TokenResponse)
from src.database import User, Session as UserSession, get_db
from src.api.maas_security import oidc_validator, ApiKeyManager
from src.services.maas_auth_service import MaaSAuthService

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

# OAuth2 / OIDC Setup (redirect-based flow, only when authlib works)
oauth = _OAuth() if _oauth_available else None
if oauth is not None and oidc_validator.enabled:
    oauth.register(
        name='oidc',
        server_metadata_url=oidc_validator.issuer + oidc_validator.WELL_KNOWN_SUFFIX,
        client_id=oidc_validator.client_id,
        client_secret=oidc_validator.audience,
        client_kwargs={'scope': 'openid email profile'},
    )

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

def require_permission(permission: str):
    """Dependency factory for granular permission-based access control (Scopes)."""
    def permission_checker(user: User = Depends(get_current_user_from_maas)):
        # Admin bypass
        if user.role == "admin":
            return user
        
        # 1. Check explicit permissions string (comma-separated)
        if user.permissions:
            user_perms = [p.strip() for p in user.permissions.split(",")]
            if permission in user_perms or "*" in user_perms:
                return user
        
        # 2. Map default permissions for roles
        role_defaults = {
            "operator": [
                "mesh:view", "mesh:update", "node:approve", "node:revoke", 
                "policy:view", "analytics:view", "telemetry:view"
            ],
            "user": [
                "mesh:create", "mesh:view", "mesh:update", "mesh:delete", 
                "billing:view", "marketplace:list", "marketplace:rent",
                "playbook:create", "playbook:view"
            ]
        }
        
        if user.role in role_defaults and permission in role_defaults[user.role]:
            return user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: required scope '{permission}'"
        )
    return permission_checker

async def get_current_user_from_maas(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Resolve user from API Key or Session Cookie."""
    # 1. Check Header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = db.query(User).filter(User.api_key == api_key).first()
        if user:
            return user
    
    # 2. Check Session Cookie / Token (for Dashboard)
    # This is a simplified version for the POC
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if session and session.expires_at > datetime.utcnow():
            return session.user
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )

@router.post("/register", response_model=TokenResponse)
async def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Regular email registration."""
    user = auth_service.register(db, req)
    return {
        "access_token": user.api_key,
        "token_type": "api_key",
        "expires_in": API_KEY_TOKEN_TTL_SECONDS,
    }

@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Regular email login."""
    api_key = auth_service.login(db, req)
    return {
        "access_token": api_key,
        "token_type": "api_key",
        "expires_in": API_KEY_TOKEN_TTL_SECONDS,
    }


@router.post("/api-key", response_model=ApiKeyResponse)
async def rotate_api_key(
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """Rotate API key for current authenticated user."""
    new_key, rotated_at = auth_service.rotate_api_key(db, current_user)
    return {"api_key": new_key, "created_at": rotated_at}

@router.get("/login/oidc")
async def login_oidc(request: Request):
    """Redirect to configured OIDC provider."""
    if not oidc_validator.enabled:
        raise HTTPException(status_code=501, detail="OIDC not configured")
    if oauth is None:
        raise HTTPException(status_code=501, detail="OIDC redirect flow not available (authlib unavailable)")

    redirect_uri = request.url_for('auth_callback')
    return await oauth.oidc.authorize_redirect(request, str(redirect_uri))

@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle OIDC callback and establish session."""
    if not oidc_validator.enabled:
        raise HTTPException(status_code=501, detail="OIDC not configured")
    if oauth is None:
        raise HTTPException(status_code=501, detail="OIDC redirect flow not available (authlib unavailable)")

    try:
        token = await oauth.oidc.authorize_access_token(request)
        id_token = token.get('id_token')
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing id_token")
            
        claims = oidc_validator.validate(id_token)
        
        # Find or create user
        user = db.query(User).filter(User.oidc_id == claims.sub).first()
        if not user:
            # Check by email as fallback
            user = db.query(User).filter(User.email == claims.email).first()
            if user:
                # Link existing user to OIDC
                user.oidc_id = claims.sub
                user.oidc_provider = claims.issuer
            else:
                # Create new enterprise user
                user = User(
                    id=str(uuid.uuid4()),
                    email=claims.email,
                    password_hash="OIDC_USER", # No local password
                    full_name=claims.name,
                    oidc_id=claims.sub,
                    oidc_provider=claims.issuer,
                    role="user", # Default role
                    api_key=ApiKeyManager.generate()
                )
                db.add(user)
            db.commit()
            db.refresh(user)
            
        # Create App Session
        session_token = secrets.token_urlsafe(64)
        new_session = UserSession(
            token=session_token,
            user_id=user.id,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        db.add(new_session)
        db.commit()
        
        # In a real app, we'd redirect to dashboard with the token
        return {
            "message": "Authenticated successfully",
            "session_token": session_token,
            "user": {
                "email": user.email,
                "role": user.role,
                "api_key": user.api_key
            }
        }
        
    except Exception as e:
        logger.error(f"OIDC Auth failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

@router.get("/me")
async def get_my_profile(user: User = Depends(get_current_user_from_maas)):
    """Get current authenticated profile."""
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "plan": user.plan,
        "oidc_linked": bool(user.oidc_id)
    }

@router.post("/set-admin/{email}")
async def make_admin(
    email: str, 
    db: Session = Depends(get_db),
    # Only existing admin can promote others
    # For bootstrap, we might need a script or env var
):
    """Utility to promote a user to admin (Bootstrap helper)."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = "admin"
    db.commit()
    return {"message": f"User {email} is now an ADMIN"}
