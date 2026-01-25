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
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result

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
def x_hash_password__mutmut_orig(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Helper functions
def x_hash_password__mutmut_1(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(None, bcrypt.gensalt()).decode()

# Helper functions
def x_hash_password__mutmut_2(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), None).decode()

# Helper functions
def x_hash_password__mutmut_3(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(bcrypt.gensalt()).decode()

# Helper functions
def x_hash_password__mutmut_4(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), ).decode()

x_hash_password__mutmut_mutants : ClassVar[MutantDict] = {
'x_hash_password__mutmut_1': x_hash_password__mutmut_1, 
    'x_hash_password__mutmut_2': x_hash_password__mutmut_2, 
    'x_hash_password__mutmut_3': x_hash_password__mutmut_3, 
    'x_hash_password__mutmut_4': x_hash_password__mutmut_4
}

def hash_password(*args, **kwargs):
    result = _mutmut_trampoline(x_hash_password__mutmut_orig, x_hash_password__mutmut_mutants, args, kwargs)
    return result 

hash_password.__signature__ = _mutmut_signature(x_hash_password__mutmut_orig)
x_hash_password__mutmut_orig.__name__ = 'x_hash_password'

def x_generate_api_key__mutmut_orig() -> str:
    """Generate a secure API key"""
    return f"x0tta6bl4_{secrets.token_urlsafe(32)}"

def x_generate_api_key__mutmut_1() -> str:
    """Generate a secure API key"""
    return f"x0tta6bl4_{secrets.token_urlsafe(None)}"

def x_generate_api_key__mutmut_2() -> str:
    """Generate a secure API key"""
    return f"x0tta6bl4_{secrets.token_urlsafe(33)}"

x_generate_api_key__mutmut_mutants : ClassVar[MutantDict] = {
'x_generate_api_key__mutmut_1': x_generate_api_key__mutmut_1, 
    'x_generate_api_key__mutmut_2': x_generate_api_key__mutmut_2
}

def generate_api_key(*args, **kwargs):
    result = _mutmut_trampoline(x_generate_api_key__mutmut_orig, x_generate_api_key__mutmut_mutants, args, kwargs)
    return result 

generate_api_key.__signature__ = _mutmut_signature(x_generate_api_key__mutmut_orig)
x_generate_api_key__mutmut_orig.__name__ = 'x_generate_api_key'

def x_generate_session_token__mutmut_orig() -> str:
    """Generate a session token"""
    return secrets.token_urlsafe(64)

def x_generate_session_token__mutmut_1() -> str:
    """Generate a session token"""
    return secrets.token_urlsafe(None)

def x_generate_session_token__mutmut_2() -> str:
    """Generate a session token"""
    return secrets.token_urlsafe(65)

x_generate_session_token__mutmut_mutants : ClassVar[MutantDict] = {
'x_generate_session_token__mutmut_1': x_generate_session_token__mutmut_1, 
    'x_generate_session_token__mutmut_2': x_generate_session_token__mutmut_2
}

def generate_session_token(*args, **kwargs):
    result = _mutmut_trampoline(x_generate_session_token__mutmut_orig, x_generate_session_token__mutmut_mutants, args, kwargs)
    return result 

generate_session_token.__signature__ = _mutmut_signature(x_generate_session_token__mutmut_orig)
x_generate_session_token__mutmut_orig.__name__ = 'x_generate_session_token'

# Endpoints
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
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
        "api_key": user.api_key,
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
async def get_current_user():
    """Get current user profile (demo - returns first user)"""
    if not users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No users found. Please register first."
        )
    
    # Return first user for demo
    user = list(users_db.values())[0]
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        company=user["company"],
        plan=user["plan"],
        created_at=user["created_at"]
    )

@router.post("/logout")
async def logout():
    """Logout user"""
    return {"message": "Logged out successfully (demo mode)"}

async def x_verify_admin_token__mutmut_orig(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_1(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = None
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_2(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv(None)
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_3(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("XXADMIN_TOKENXX")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_4(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("admin_token")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_5(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_6(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=None, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_7(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail=None)
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_8(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_9(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, )
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_10(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=501, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_11(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="XXAdmin token not configuredXX")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_12(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_13(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="ADMIN TOKEN NOT CONFIGURED")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_14(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token and x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_15(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_16(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token == admin_token:
        raise HTTPException(status_code=403, detail="Admin access required")

async def x_verify_admin_token__mutmut_17(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=None, detail="Admin access required")

async def x_verify_admin_token__mutmut_18(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail=None)

async def x_verify_admin_token__mutmut_19(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(detail="Admin access required")

async def x_verify_admin_token__mutmut_20(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, )

async def x_verify_admin_token__mutmut_21(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=404, detail="Admin access required")

async def x_verify_admin_token__mutmut_22(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="XXAdmin access requiredXX")

async def x_verify_admin_token__mutmut_23(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="admin access required")

async def x_verify_admin_token__mutmut_24(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="ADMIN ACCESS REQUIRED")

x_verify_admin_token__mutmut_mutants : ClassVar[MutantDict] = {
'x_verify_admin_token__mutmut_1': x_verify_admin_token__mutmut_1, 
    'x_verify_admin_token__mutmut_2': x_verify_admin_token__mutmut_2, 
    'x_verify_admin_token__mutmut_3': x_verify_admin_token__mutmut_3, 
    'x_verify_admin_token__mutmut_4': x_verify_admin_token__mutmut_4, 
    'x_verify_admin_token__mutmut_5': x_verify_admin_token__mutmut_5, 
    'x_verify_admin_token__mutmut_6': x_verify_admin_token__mutmut_6, 
    'x_verify_admin_token__mutmut_7': x_verify_admin_token__mutmut_7, 
    'x_verify_admin_token__mutmut_8': x_verify_admin_token__mutmut_8, 
    'x_verify_admin_token__mutmut_9': x_verify_admin_token__mutmut_9, 
    'x_verify_admin_token__mutmut_10': x_verify_admin_token__mutmut_10, 
    'x_verify_admin_token__mutmut_11': x_verify_admin_token__mutmut_11, 
    'x_verify_admin_token__mutmut_12': x_verify_admin_token__mutmut_12, 
    'x_verify_admin_token__mutmut_13': x_verify_admin_token__mutmut_13, 
    'x_verify_admin_token__mutmut_14': x_verify_admin_token__mutmut_14, 
    'x_verify_admin_token__mutmut_15': x_verify_admin_token__mutmut_15, 
    'x_verify_admin_token__mutmut_16': x_verify_admin_token__mutmut_16, 
    'x_verify_admin_token__mutmut_17': x_verify_admin_token__mutmut_17, 
    'x_verify_admin_token__mutmut_18': x_verify_admin_token__mutmut_18, 
    'x_verify_admin_token__mutmut_19': x_verify_admin_token__mutmut_19, 
    'x_verify_admin_token__mutmut_20': x_verify_admin_token__mutmut_20, 
    'x_verify_admin_token__mutmut_21': x_verify_admin_token__mutmut_21, 
    'x_verify_admin_token__mutmut_22': x_verify_admin_token__mutmut_22, 
    'x_verify_admin_token__mutmut_23': x_verify_admin_token__mutmut_23, 
    'x_verify_admin_token__mutmut_24': x_verify_admin_token__mutmut_24
}

def verify_admin_token(*args, **kwargs):
    result = _mutmut_trampoline(x_verify_admin_token__mutmut_orig, x_verify_admin_token__mutmut_mutants, args, kwargs)
    return result 

verify_admin_token.__signature__ = _mutmut_signature(x_verify_admin_token__mutmut_orig)
x_verify_admin_token__mutmut_orig.__name__ = 'x_verify_admin_token'

@router.get("/stats")
async def get_user_stats(admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get user statistics (admin only)"""
    total_users = db.query(User).count()
    active_sessions = db.query(Session).filter(Session.expires_at > datetime.utcnow()).count()
    
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
