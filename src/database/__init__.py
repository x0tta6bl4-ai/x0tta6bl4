"""
Database module for x0tta6bl4
==============================================
SQLAlchemy ORM setup and database models.
"""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
                        Text, create_engine, inspect as sqlalchemy_inspect, event, exc as sa_exc)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from src.resilience.advanced_patterns import CircuitBreaker, CircuitBreakerConfig, CircuitState

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

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
                open_duration = (_utc_now() - _lft).total_seconds()
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
    api_key_hash = Column(String, unique=True, index=True, nullable=True)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=True)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    vpn_uuid = Column(String, unique=True, index=True, nullable=True)
    requests_count = Column(Integer, default=0)
    requests_limit = Column(Integer, default=10000)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now)


class ACLPolicy(Base):
    """Zero-trust access control rules."""
    __tablename__ = "acl_policies"
    id = Column(String, primary_key=True) # policy_id
    mesh_id = Column(String, ForeignKey("mesh_instances.id"), index=True)
    source_tag = Column(String)
    target_tag = Column(String)
    action = Column(String, default="allow")
    created_at = Column(DateTime, default=_utc_now)


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
    created_at = Column(DateTime, default=_utc_now)


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
    created_at = Column(DateTime, default=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now)
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
    issued_at = Column(DateTime, default=_utc_now)


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
    created_at = Column(DateTime, default=_utc_now)


class Session(Base):
    """Session model for user authentication sessions."""

    __tablename__ = "sessions"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now, nullable=False)
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
    created_at = Column(DateTime, default=_utc_now)

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
    verified_at = Column(DateTime, default=_utc_now)

    sbom = relationship("SBOMEntry", back_populates="node_attestations")


class PlaybookAck(Base):
    """Persistent acknowledgement records for signed playbooks."""
    __tablename__ = "playbook_acks"
    id = Column(String, primary_key=True)
    playbook_id = Column(String, ForeignKey("signed_playbooks.id"), index=True)
    node_id = Column(String, nullable=False, index=True)
    status = Column(String, default="completed")  # completed, failed, partial
    acknowledged_at = Column(DateTime, default=_utc_now)


class GlobalConfig(Base):
    """Store global configuration parameters, such as DAO-governed settings."""
    __tablename__ = "global_config"

    key = Column(String, primary_key=True, index=True)
    value_json = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
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
    created_at = Column(DateTime, default=_utc_now)

    votes = relationship("GovernanceVote", back_populates="proposal")


class GovernanceVote(Base):
    """Individual votes on governance proposals."""
    __tablename__ = "governance_votes"
    id = Column(String, primary_key=True)
    proposal_id = Column(String, ForeignKey("governance_proposals.id"), index=True)
    voter_id = Column(String, nullable=False, index=True)  # user email or id
    vote = Column(String, nullable=False)  # yes, no, abstain
    tokens = Column(Integer, nullable=False)  # raw voting power * 100 (cents)
    created_at = Column(DateTime, default=_utc_now)

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
    created_at = Column(DateTime, default=_utc_now)


DEFAULT_ALLOWED_EXTRA_TABLES = {"alembic_version", "es_events", "es_streams", "es_snapshots"}


def _env_csv_set(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _allowed_extra_tables() -> set[str]:
    return DEFAULT_ALLOWED_EXTRA_TABLES | _env_csv_set("SCHEMA_PARITY_ALLOWED_EXTRA_TABLES")


def _allowed_extra_columns() -> set[str]:
    return _env_csv_set("SCHEMA_PARITY_ALLOWED_EXTRA_COLUMNS")


def _normalize_columns(columns: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not columns:
        return ()
    return tuple(sorted(col for col in columns if col))


def _expected_unique_sets(table: Any) -> set[tuple[str, ...]]:
    expected: set[tuple[str, ...]] = set()
    for column in table.columns:
        if column.unique:
            expected.add((column.name,))
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            normalized = _normalize_columns([col.name for col in constraint.columns])
            if normalized:
                expected.add(normalized)
    for index in table.indexes:
        if index.unique:
            normalized = _normalize_columns([col.name for col in index.columns])
            if normalized:
                expected.add(normalized)
    return expected


def _expected_index_sets(table: Any) -> set[tuple[str, ...]]:
    expected: set[tuple[str, ...]] = set()
    for column in table.columns:
        if column.index:
            expected.add((column.name,))
    for index in table.indexes:
        normalized = _normalize_columns([col.name for col in index.columns])
        if normalized:
            expected.add(normalized)
    return expected


def _actual_unique_sets(inspector: Any, table_name: str) -> set[tuple[str, ...]]:
    actual: set[tuple[str, ...]] = set()
    pk = _normalize_columns(inspector.get_pk_constraint(table_name).get("constrained_columns"))
    if pk:
        actual.add(pk)
    for constraint in inspector.get_unique_constraints(table_name):
        normalized = _normalize_columns(constraint.get("column_names"))
        if normalized:
            actual.add(normalized)
    for index in inspector.get_indexes(table_name):
        if index.get("unique"):
            normalized = _normalize_columns(index.get("column_names"))
            if normalized:
                actual.add(normalized)
    return actual


def _actual_index_sets(inspector: Any, table_name: str) -> set[tuple[str, ...]]:
    actual = set(_actual_unique_sets(inspector, table_name))
    for index in inspector.get_indexes(table_name):
        normalized = _normalize_columns(index.get("column_names"))
        if normalized:
            actual.add(normalized)
    return actual


def get_schema_parity_report() -> dict[str, Any]:
    inspector = sqlalchemy_inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    allowed_extra_tables = _allowed_extra_tables()
    allowed_extra_columns = _allowed_extra_columns()
    report: dict[str, Any] = {
        "missing_tables": sorted(expected_tables - actual_tables),
        "extra_tables": sorted(actual_tables - expected_tables - allowed_extra_tables),
        "missing_columns": {},
        "extra_columns": {},
        "nullable_mismatches": {},
        "primary_key_mismatches": {},
        "missing_unique_constraints": {},
        "missing_indexes": {},
        "gaps": [],
    }
    for table_name in sorted(expected_tables & actual_tables):
        table = Base.metadata.tables[table_name]
        actual_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        expected_columns = set(table.columns.keys())
        actual_column_names = set(actual_columns.keys())
        missing_columns = sorted(expected_columns - actual_column_names)
        if missing_columns:
            report["missing_columns"][table_name] = missing_columns
        extra_columns = sorted(
            column
            for column in actual_column_names - expected_columns
            if f"{table_name}.{column}" not in allowed_extra_columns
        )
        if extra_columns:
            report["extra_columns"][table_name] = extra_columns
        nullable_mismatches = []
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
        for column in table.columns:
            if column.name not in actual_columns or column.name in pk_columns:
                continue
            actual_nullable = bool(actual_columns[column.name].get("nullable"))
            expected_nullable = bool(column.nullable)
            if actual_nullable != expected_nullable:
                nullable_mismatches.append(
                    {"column": column.name, "expected_nullable": expected_nullable, "actual_nullable": actual_nullable}
                )
        if nullable_mismatches:
            report["nullable_mismatches"][table_name] = nullable_mismatches
        expected_pk = _normalize_columns([column.name for column in table.primary_key.columns])
        actual_pk = _normalize_columns(inspector.get_pk_constraint(table_name).get("constrained_columns"))
        if expected_pk != actual_pk:
            report["primary_key_mismatches"][table_name] = {"expected": list(expected_pk), "actual": list(actual_pk)}
        missing_unique = sorted(
            list(columns)
            for columns in (_expected_unique_sets(table) - _actual_unique_sets(inspector, table_name))
        )
        if missing_unique:
            report["missing_unique_constraints"][table_name] = missing_unique
        missing_indexes = sorted(
            list(columns)
            for columns in (_expected_index_sets(table) - _actual_index_sets(inspector, table_name))
        )
        if missing_indexes:
            report["missing_indexes"][table_name] = missing_indexes
    gaps: list[str] = []
    gaps.extend(f"missing table '{table}'" for table in report["missing_tables"])
    gaps.extend(f"extra table '{table}'" for table in report["extra_tables"])
    for category in (
        "missing_columns",
        "extra_columns",
        "nullable_mismatches",
        "primary_key_mismatches",
        "missing_unique_constraints",
        "missing_indexes",
    ):
        for table_name, value in report[category].items():
            gaps.append(f"{category} on '{table_name}': {value}")
    report["gaps"] = gaps
    return report


def get_alembic_head_gaps() -> List[str]:
    try:
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
    except Exception as exc:
        return [f"alembic unavailable: {exc}"]
    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"
    alembic_dir = repo_root / "alembic"
    if not alembic_ini.exists() or not alembic_dir.exists():
        return [f"alembic config/script directory missing under {repo_root}"]
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    script = ScriptDirectory.from_config(cfg)
    expected_heads = set(script.get_heads())
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
    if current_heads != expected_heads:
        return [
            "alembic revision mismatch: "
            f"current={sorted(current_heads) or ['<none>']} expected={sorted(expected_heads)}"
        ]
    return []


def get_required_schema_gaps() -> List[str]:
    return list(get_schema_parity_report()["gaps"])


def get_schema_compatibility_gaps() -> List[str]:
    return [*get_alembic_head_gaps(), *get_required_schema_gaps()]


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
            "WARNING: %d optional secret values are not set. Some features may be disabled.",
            len(empty_optional),
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
    
    missing = get_schema_compatibility_gaps()
    if not missing:
        return

    if auto_migrate:
        logger.warning(
            "Database schema drift detected (%s). Running alembic upgrade head.",
            "; ".join(missing),
        )
        run_alembic_upgrade("head")
        missing = get_schema_compatibility_gaps()
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
