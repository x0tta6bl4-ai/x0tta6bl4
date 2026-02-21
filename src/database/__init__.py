"""
Database module for x0tta6bl4
==============================================
SQLAlchemy ORM setup and database models.
"""

import os
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./x0tta6bl4.db")

# Create engine
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif "postgresql" in DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    raise ValueError(f"Unsupported database type: {DATABASE_URL}")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class User(Base):
    """User model for authentication and profile management."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    plan = Column(String, default="free")
    role = Column(String, default="user")  # "user", "admin", "operator"
    permissions = Column(Text, nullable=True)  # Comma-separated scopes
    oidc_id = Column(String, unique=True, index=True, nullable=True)
    oidc_provider = Column(String, nullable=True)
    api_key = Column(String, unique=True, index=True, nullable=True)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=True)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    vpn_uuid = Column(String, unique=True, index=True, nullable=True)
    requests_count = Column(Integer, default=0)
    requests_limit = Column(Integer, default=10000)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")


class MeshInstance(Base):
    """Main mesh network metadata."""
    __tablename__ = "mesh_instances"
    id = Column(String, primary_key=True) # mesh_id
    name = Column(String)
    owner_id = Column(String, ForeignKey("users.id"))
    plan = Column(String)
    pqc_enabled = Column(Boolean, default=True)
    obfuscation = Column(String, default="none")
    traffic_profile = Column(String, default="none")
    join_token = Column(String)
    join_token_expires_at = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)


class ACLPolicy(Base):
    """Zero-trust access control rules."""
    __tablename__ = "acl_policies"
    id = Column(String, primary_key=True) # policy_id
    mesh_id = Column(String, ForeignKey("mesh_instances.id"), index=True)
    source_tag = Column(String)
    target_tag = Column(String)
    action = Column(String, default="allow")
    created_at = Column(DateTime, default=datetime.utcnow)


class MeshNode(Base):
    """Metadata for approved nodes in a mesh."""
    __tablename__ = "mesh_nodes"
    id = Column(String, primary_key=True)
    mesh_id = Column(String, index=True)
    device_class = Column(String)
    status = Column(String, default="healthy")
    acl_profile = Column(String, default="default")
    hardware_id = Column(String, nullable=True)
    enclave_enabled = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketplaceListing(Base):
    """P2P infrastructure listings."""
    __tablename__ = "marketplace_listings"
    id = Column(String, primary_key=True)
    owner_id = Column(String, ForeignKey("users.id"))
    node_id = Column(String, unique=True)
    region = Column(String, index=True)
    price_per_hour = Column(Integer)  # In cents
    bandwidth_mbps = Column(Integer)
    status = Column(String, default="available")  # available, escrow, rented
    renter_id = Column(String, ForeignKey("users.id"), nullable=True)
    mesh_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    escrows = relationship("MarketplaceEscrow", back_populates="listing")


class MarketplaceEscrow(Base):
    """Escrow records holding payment until node health is confirmed."""
    __tablename__ = "marketplace_escrows"
    id = Column(String, primary_key=True)
    listing_id = Column(String, ForeignKey("marketplace_listings.id"), index=True)
    renter_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)  # 1-hour deposit
    status = Column(String, default="held")  # held, released, refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime, nullable=True)

    listing = relationship("MarketplaceListing", back_populates="escrows")


class Invoice(Base):
    """Commercial invoices for mesh usage."""

    __tablename__ = "invoices"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    mesh_id = Column(String)
    total_amount = Column(Integer)  # In cents
    currency = Column(String, default="USD")
    status = Column(String, default="issued")  # issued, paid, overdue
    stripe_session_id = Column(String, unique=True, index=True, nullable=True)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    issued_at = Column(DateTime, default=datetime.utcnow)


class SignedPlaybook(Base):
    """PQC-signed commands for agents."""
    __tablename__ = "signed_playbooks"
    id = Column(String, primary_key=True)
    mesh_id = Column(String, index=True)
    name = Column(String)
    payload = Column(Text) # JSON of actions
    signature = Column(Text)
    algorithm = Column(String, default="ML-DSA-65")
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    """Session model for user authentication sessions."""

    __tablename__ = "sessions"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    email = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class Payment(Base):
    """Payment model for tracking customer payments."""

    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    order_id = Column(String, unique=True, index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="RUB")
    payment_method = Column(String, nullable=False)  # "USDT", "TON", "STRIPE"
    transaction_hash = Column(String, nullable=True)
    status = Column(
        String, default="pending"
    )  # "pending", "verified", "failed", "refunded"
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class License(Base):
    """License model for tracking activation tokens."""

    __tablename__ = "licenses"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    order_id = Column(String, index=True, nullable=True)
    tier = Column(String, default="basic")  # "basic", "pro", "enterprise"
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class BillingWebhookEvent(Base):
    """Processed billing webhook events for idempotency and replay protection."""

    __tablename__ = "billing_webhook_events"

    event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="processing", nullable=False)  # processing | done | failed
    response_json = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Centralized audit log for all administrative and mutating actions."""

    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    action = Column(String, index=True, nullable=False)  # e.g., "create_mesh", "update_policy"
    method = Column(String, nullable=False)  # GET, POST, etc.
    path = Column(String, nullable=False)
    payload = Column(Text, nullable=True)  # Request body (filtered)
    status_code = Column(Integer, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create all tables
def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


# Dependency for getting database session
def get_db():
    """FastAPI dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
