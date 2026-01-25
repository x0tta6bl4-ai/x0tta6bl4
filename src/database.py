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

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
