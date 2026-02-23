"""
Database module for x0tta6bl4
==============================================
SQLAlchemy ORM setup and database models.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Text, create_engine, inspect as sqlalchemy_inspect)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

logger = logging.getLogger(__name__)

# Ensure DATABASE_URL from local .env is available before engine setup.
load_dotenv(override=False)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./x0tta6bl4.db")

# Create engine
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif "postgresql" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True
    )
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


class SBOMEntry(Base):
    """DB-backed Software Bill of Materials registry."""
    __tablename__ = "sbom_entries"
    id = Column(String, primary_key=True)
    version = Column(String, unique=True, nullable=False, index=True)
    format = Column(String, default="CycloneDX-JSON")
    components_json = Column(Text, nullable=False)   # JSON array
    checksum_sha256 = Column(String, nullable=False)
    attestation_json = Column(Text, nullable=True)   # Sigstore bundle JSON
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    node_attestations = relationship("NodeBinaryAttestation", back_populates="sbom")


class NodeBinaryAttestation(Base):
    """Per-node binary verification records."""
    __tablename__ = "node_binary_attestations"
    id = Column(String, primary_key=True)
    node_id = Column(String, nullable=False, index=True)
    mesh_id = Column(String, nullable=True, index=True)
    sbom_id = Column(String, ForeignKey("sbom_entries.id"), nullable=False)
    agent_version = Column(String, nullable=False)
    checksum_sha256 = Column(String, nullable=False)
    status = Column(String, default="verified")  # verified, mismatch, unknown
    verified_at = Column(DateTime, default=datetime.utcnow)

    sbom = relationship("SBOMEntry", back_populates="node_attestations")


class PlaybookAck(Base):
    """Persistent acknowledgement records for signed playbooks."""
    __tablename__ = "playbook_acks"
    id = Column(String, primary_key=True)
    playbook_id = Column(String, ForeignKey("signed_playbooks.id"), index=True)
    node_id = Column(String, nullable=False, index=True)
    status = Column(String, default="completed")  # completed, failed, partial
    acknowledged_at = Column(DateTime, default=datetime.utcnow)


class GovernanceProposal(Base):
    """DAO governance proposals with DB-backed persistence."""
    __tablename__ = "governance_proposals"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    state = Column(String, default="active")  # active, passed, rejected, executed
    actions_json = Column(Text, nullable=True)   # JSON of action list
    end_time = Column(DateTime, nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    execution_hash = Column(String, nullable=True)  # Finality hash on execution
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    votes = relationship("GovernanceVote", back_populates="proposal")


class GovernanceVote(Base):
    """Individual votes on governance proposals."""
    __tablename__ = "governance_votes"
    id = Column(String, primary_key=True)
    proposal_id = Column(String, ForeignKey("governance_proposals.id"), index=True)
    voter_id = Column(String, nullable=False, index=True)  # user email or id
    vote = Column(String, nullable=False)  # yes, no, abstain
    tokens = Column(Integer, nullable=False)  # raw voting power * 100 (cents)
    created_at = Column(DateTime, default=datetime.utcnow)

    proposal = relationship("GovernanceProposal", back_populates="votes")


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


def get_required_schema_gaps() -> List[str]:
    """
    Return a list of required schema gaps that must be fixed before startup.
    """
    required_columns = {
        "marketplace_listings": {"renter_id", "mesh_id"},
        "mesh_nodes": {"last_seen"},
    }

    inspector = sqlalchemy_inspect(engine)
    table_names = set(inspector.get_table_names())
    missing: List[str] = []

    for table, columns in required_columns.items():
        if table not in table_names:
            missing.append(f"missing table '{table}'")
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for col in sorted(columns):
            if col not in existing:
                missing.append(f"missing column '{table}.{col}'")

    return missing


def run_alembic_upgrade(target: str = "head") -> None:
    """
    Run Alembic migrations for the configured DATABASE_URL.
    """
    from alembic import command
    from alembic.config import Config

    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"
    alembic_dir = repo_root / "alembic"

    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic config not found: {alembic_ini}")
    if not alembic_dir.exists():
        raise RuntimeError(f"Alembic script directory not found: {alembic_dir}")

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, target)


def ensure_schema_compatible(auto_migrate: bool = False) -> None:
    """
    Fail fast on known schema drift. Optionally try auto-migration first.
    """
    missing = get_required_schema_gaps()
    if not missing:
        return

    if auto_migrate:
        logger.warning(
            "Database schema drift detected (%s). Running alembic upgrade head.",
            "; ".join(missing),
        )
        run_alembic_upgrade("head")
        missing = get_required_schema_gaps()
        if not missing:
            logger.info("Database schema upgraded and validated successfully")
            return

    raise RuntimeError(
        "Database schema is incompatible: "
        + "; ".join(missing)
        + ". Run `alembic upgrade head`."
    )


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
