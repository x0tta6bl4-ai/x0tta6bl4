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
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine, inspect as sqlalchemy_inspect, event, exc as sa_exc)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from src.resilience.advanced_patterns import CircuitBreaker, CircuitBreakerConfig, CircuitState

logger = logging.getLogger(__name__)

# Ensure DATABASE_URL from local .env is available before engine setup.
load_dotenv(override=False)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./x0tta6bl4.db")

# Setup DB Circuit Breaker
db_circuit_breaker = CircuitBreaker(
    config=CircuitBreakerConfig(
        failure_threshold=int(os.getenv("DB_CB_FAILURE_THRESHOLD", "5")),
        recovery_timeout_seconds=int(os.getenv("DB_CB_RECOVERY_TIMEOUT", "30")),
        success_threshold=int(os.getenv("DB_CB_SUCCESS_THRESHOLD", "2"))
    ),
    name="database_circuit_breaker"
)

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
# Bind Circuit Breaker to Engine Events
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    # Update metrics with current state
    from src.monitoring.metrics import MetricsRegistry
    from src.resilience.advanced_patterns import CircuitState

    state_map = {CircuitState.CLOSED: 0, CircuitState.OPEN: 1, CircuitState.HALF_OPEN: 2}
    MetricsRegistry.db_circuit_breaker_state.set(state_map.get(db_circuit_breaker.state, 0))

    with db_circuit_breaker.lock:
        if db_circuit_breaker.state == CircuitState.OPEN:
            # P2 Reliability: Auto-Healing logic
            # If CB is open for more than 5 minutes, try disposing the engine pool
            from datetime import datetime
            _lft = db_circuit_breaker.last_failure_time
            if _lft is None:
                open_duration = 0
            elif isinstance(_lft, datetime):
                open_duration = (datetime.utcnow() - _lft).total_seconds()
            else:
                import time
                open_duration = time.time() - _lft
            if open_duration > 300: # 5 minutes
                logger.warning("🕒 Database Circuit Breaker has been OPEN for >5m. Triggering Auto-Healing: disposing engine pool.")
                engine.dispose()

            if db_circuit_breaker._should_attempt_recovery():
                db_circuit_breaker.state = CircuitState.HALF_OPEN
            else:
                raise sa_exc.OperationalError(
                    statement, parameters, 
                    Exception("Database Circuit Breaker is OPEN. Failing fast to prevent cascade failure.")
                )

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    db_circuit_breaker._on_success()

@event.listens_for(engine, "handle_error")
def handle_error(exception_context):
    # Only react to connection, operational, or timeout errors (ignore logic/data errors)
    if isinstance(exception_context.original_exception, (
        sa_exc.OperationalError, 
        sa_exc.TimeoutError, 
        sa_exc.InternalError,
        ConnectionError,
        TimeoutError
    )):
        db_circuit_breaker._on_failure()
        logger.error(f"DB Error caught by Circuit Breaker: {exception_context.original_exception}. CB State: {db_circuit_breaker.state.value}")

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
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")


class MeshInstance(Base):
    """Main mesh network metadata."""
    __tablename__ = "mesh_instances"
    id = Column(String, primary_key=True) # mesh_id
    name = Column(String)
    owner_id = Column(String, ForeignKey("users.id"), index=True)
    plan = Column(String)
    region = Column(String, default="global")
    nodes = Column(Integer, default=5)
    pqc_profile = Column(String, default="edge")
    pqc_enabled = Column(Boolean, default=True)
    obfuscation = Column(String, default="none")
    traffic_profile = Column(String, default="none")
    join_token = Column(String)
    join_token_expires_at = Column(DateTime)
    status = Column(String, default="active", index=True)
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
    ip_address = Column(String, index=True, nullable=True)
    acl_profile = Column(String, default="default")
    hardware_id = Column(String, nullable=True)
    enclave_enabled = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketplaceListing(Base):
    """P2P infrastructure listings."""
    __tablename__ = "marketplace_listings"
    id = Column(String, primary_key=True)
    owner_id = Column(String, ForeignKey("users.id"), index=True)
    node_id = Column(String, unique=True)
    region = Column(String, index=True)
    price_per_hour = Column(Integer)  # In cents
    price_token_per_hour = Column(Float, nullable=True)  # In X0T
    currency = Column(String, default="USD")  # USD or X0T
    bandwidth_mbps = Column(Integer)
    status = Column(String, default="available", index=True)  # available, escrow, rented
    renter_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    mesh_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    escrows = relationship("MarketplaceEscrow", back_populates="listing")


class MarketplaceEscrow(Base):
    """Escrow records holding payment until node health is confirmed."""
    __tablename__ = "marketplace_escrows"
    id = Column(String, primary_key=True)
    listing_id = Column(String, ForeignKey("marketplace_listings.id"), index=True)
    renter_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=True)  # 1-hour deposit in USD cents
    amount_token = Column(Float, nullable=True)  # 1-hour deposit in X0T
    currency = Column(String, default="USD")  # USD or X0T
    status = Column(String, default="held", index=True)  # held, released, refunded, expired
    auto_renew = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)
    released_at = Column(DateTime, nullable=True)

    listing = relationship("MarketplaceListing", back_populates="escrows")


class Invoice(Base):
    """Commercial invoices for mesh usage."""

    __tablename__ = "invoices"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    mesh_id = Column(String, index=True)
    total_amount = Column(Integer)  # In cents
    currency = Column(String, default="USD")
    status = Column(String, default="issued", index=True)  # issued, paid, overdue
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
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
        String, default="pending", index=True
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
    status = Column(String, default="verified", index=True)  # verified, mismatch, unknown
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


class GlobalConfig(Base):
    """Store global configuration parameters, such as DAO-governed settings."""
    __tablename__ = "global_config"

    key = Column(String, primary_key=True, index=True)
    value_json = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, ForeignKey("users.id"), nullable=True)


class GovernanceProposal(Base):
    """DAO governance proposals with DB-backed persistence."""
    __tablename__ = "governance_proposals"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    state = Column(String, default="active", index=True)  # active, passed, rejected, executed
    actions_json = Column(Text, nullable=True)   # JSON of action list
    end_time = Column(DateTime, nullable=False, index=True)
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
    user_agent = Column(String, nullable=True)
    correlation_id = Column(String, index=True, nullable=True)
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


def validate_required_secrets() -> None:
    """
    Validate that critical environment secrets are set.
    Raises RuntimeError if any required secret is missing or empty.
    """
    
    # Critical secrets that MUST be set in production
    REQUIRED_SECRETS = [
        "FLASK_SECRET_KEY",
        "JWT_SECRET_KEY",
        "CSRF_SECRET_KEY",
    ]
    
    # Optional secrets (can be empty but should be documented)
    OPTIONAL_SECRETS = [
        "OPERATOR_PRIVATE_KEY",
        "VPN_SERVER",
        "VPN_PORT",
        "VPN_SESSION_TOKEN",
        "GENEVA_MASTER_KEY",
    ]
    
    missing_critical = []
    empty_optional = []
    
    for secret in REQUIRED_SECRETS:
        value = os.getenv(secret, "")
        if not value:
            missing_critical.append(secret)
    
    for secret in OPTIONAL_SECRETS:
        value = os.getenv(secret, "")
        if not value:
            empty_optional.append(secret)
    
    if missing_critical:
        raise RuntimeError(
            f"CRITICAL: Missing required secrets: {', '.join(missing_critical)}. "
            f"Set via environment variables, Kubernetes secrets, or secret manager before deployment."
        )
    
    if empty_optional:
        logger.warning(
            f"WARNING: Optional secrets not set: {', '.join(empty_optional)}. "
            f"Some features may be disabled."
        )


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
    Also validates required secrets are set.
    """
    # Validate secrets first - fail fast before any DB operations
    validate_required_secrets()
    
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
