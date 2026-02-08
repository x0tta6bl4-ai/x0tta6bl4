"""
User Management API
Registration, authentication, and user profile management
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request, Header
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timedelta
import secrets
import bcrypt
import hmac
import json
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.database import get_db, User, Session as DB_Session

router = APIRouter(prefix="/api/v1/users", tags=["users"])
limiter = Limiter(key_func=get_remote_address)

# In-memory user database for demo (backward compatibility)
users_db = {}

# Models
class UserCreate(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
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
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
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
        api_key=api_key,
        requests_count=0,
        requests_limit=10000  # Free tier limit
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Also update in-memory store for backward compatibility
    users_db[user_data.email] = {
        "id": user_id,
        "email": user_data.email,
        "password_hash": user.password_hash,
        "full_name": user.full_name,
        "company": user.company,
        "plan": user.plan,
        "created_at": user.created_at,
        "requests_count": user.requests_count,
        "requests_limit": user.requests_limit
    }
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        plan=user.plan,
        created_at=user.created_at
    )

@router.post("/login", response_model=SessionResponse)
@limiter.limit("5/minute")
async def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and create session"""
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not bcrypt.checkpw(credentials.password.encode(), user.password_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create session
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    session = DB_Session(
        token=token,
        user_id=user.id,
        email=user.email,
        expires_at=expires_at
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return SessionResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            company=user.company,
            plan=user.plan,
            created_at=user.created_at
        ),
        expires_at=expires_at
    )

@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current user profile based on API Key or Session"""
    api_key = request.headers.get("X-API-Key")
    auth_header = request.headers.get("Authorization")
    
    user = None
    
    # Try to authenticate with session token first
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        session_entry = db.query(DB_Session).filter(
            DB_Session.token == token,
            DB_Session.expires_at > datetime.utcnow()
        ).first()
        
        if session_entry:
            user = db.query(User).filter(User.id == session_entry.user_id).first()
            
    # If not authenticated by session, try API key
    if not user and api_key:
        user = db.query(User).filter(User.api_key == api_key).first()

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        plan=user.plan,
        created_at=user.created_at
    )

@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Logout user by invalidating session"""
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]
        db.query(DB_Session).filter(DB_Session.token == token).delete()
        db.commit()
    return {"message": "Logged out successfully"}

async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(status_code=403, detail="Admin access required")

@router.get("/stats")
@limiter.limit("30/minute")
async def get_user_stats(request: Request, admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get user statistics (admin only)"""
    total_users = db.query(User).count()
    active_sessions = db.query(DB_Session).filter(DB_Session.expires_at > datetime.utcnow()).count()
    
    plans = {
        "free": db.query(User).filter(User.plan == "free").count(),
        "pro": db.query(User).filter(User.plan == "pro").count(),
        "enterprise": db.query(User).filter(User.plan == "enterprise").count()
    }
    
    return {
        "total_users": total_users,
        "active_sessions": active_sessions,
        "plans": plans
    }

@router.get("/", response_model=list[UserResponse])
@limiter.limit("30/minute")
async def get_users(request: Request, admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get all users (admin only)"""
    users = db.query(User).all()
    return [UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company=user.company,
        plan=user.plan,
        created_at=user.created_at
    ) for user in users]
