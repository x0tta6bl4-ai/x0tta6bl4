"""
PostgreSQL Database Configuration for x0tta6bl4
"""
import os
from sqlalchemy import create_engine, Column, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Get DATABASE_URL from environment, fail fast if not set in production
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./x0tta6bl4.db"  # Development default only
)

# Validate that we're not using a hardcoded password in production
if os.getenv("ENVIRONMENT") == "production" and "x0tta6bl4_password" in DATABASE_URL:
    raise ValueError("⚠️ CRITICAL: Hardcoded database password detected in production. Use DATABASE_URL environment variable.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
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

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    plan = Column(String, default="free", nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

class Session(Base):
    __tablename__ = "sessions"
    
    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

def x_init_db__mutmut_orig():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created")

def x_init_db__mutmut_1():
    """Initialize database tables"""
    Base.metadata.create_all(bind=None)
    logger.info("✅ Database tables created")

def x_init_db__mutmut_2():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info(None)

def x_init_db__mutmut_3():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("XX✅ Database tables createdXX")

def x_init_db__mutmut_4():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ database tables created")

def x_init_db__mutmut_5():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ DATABASE TABLES CREATED")

x_init_db__mutmut_mutants : ClassVar[MutantDict] = {
'x_init_db__mutmut_1': x_init_db__mutmut_1, 
    'x_init_db__mutmut_2': x_init_db__mutmut_2, 
    'x_init_db__mutmut_3': x_init_db__mutmut_3, 
    'x_init_db__mutmut_4': x_init_db__mutmut_4, 
    'x_init_db__mutmut_5': x_init_db__mutmut_5
}

def init_db(*args, **kwargs):
    result = _mutmut_trampoline(x_init_db__mutmut_orig, x_init_db__mutmut_mutants, args, kwargs)
    return result 

init_db.__signature__ = _mutmut_signature(x_init_db__mutmut_orig)
x_init_db__mutmut_orig.__name__ = 'x_init_db'

def x_get_db__mutmut_orig():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def x_get_db__mutmut_1():
    """Get database session"""
    db = None
    try:
        yield db
    finally:
        db.close()

x_get_db__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_db__mutmut_1': x_get_db__mutmut_1
}

def get_db(*args, **kwargs):
    result = _mutmut_trampoline(x_get_db__mutmut_orig, x_get_db__mutmut_mutants, args, kwargs)
    return result 

get_db.__signature__ = _mutmut_signature(x_get_db__mutmut_orig)
x_get_db__mutmut_orig.__name__ = 'x_get_db'
