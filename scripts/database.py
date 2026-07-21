#!/usr/bin/env python3
"""
Database module для x0tta6bl4 Telegram Bot
Использует SQLite для хранения пользователей

Optimizations:
- WAL mode for concurrent read/write
- Connection pooling for reduced overhead
- Memory-mapped temp storage
- 64MB cache for faster queries
"""

import functools
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from os import PathLike
from pathlib import Path
from queue import Queue, Empty
import secrets
import sqlite3
import threading
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Generator,
    List,
    NamedTuple,
    Optional,
    Protocol,
    TypeVar,
    TypedDict,
    Union,
)
import os

logger = logging.getLogger(__name__)

# ============================================================================
# TYPE DEFINITIONS - TypedDict for strict type safety
# ============================================================================

class UserRecord(TypedDict, total=False):
    """Type-safe user record from database."""
    user_id: int
    username: Optional[str]
    created_at: str
    trial_used: bool
    plan: str
    expires_at: Optional[str]
    vpn_uuid: Optional[str]
    vpn_config: Optional[str]
    payment_amount: Optional[float]
    payment_currency: Optional[str]
    last_activity: str
    zkp_public_key: Optional[str]
    subscription_token: Optional[str]
    subscription_updated_at: Optional[str]
    egress_mode: str
    extra_device_slots: int
    delivery_profile: str
    entry_node: str
    client_family: str
    stealth_mode_enabled: bool

class DeviceRecord(TypedDict, total=False):
    """Type-safe device record from database."""
    device_id: int
    user_id: int
    device_name: str
    device_type: str
    vpn_uuid: str
    xray_email: Optional[str]
    status: str
    profile_kind: str
    first_seen_at: Optional[str]
    last_seen_at: Optional[str]
    last_ip: Optional[str]
    last_handshake_at: Optional[str]
    created_at: str
    revoked_at: Optional[str]

class PaymentRecord(TypedDict, total=False):
    """Type-safe payment record from database."""
    payment_id: int
    user_id: int
    amount: float
    currency: str
    payment_date: str
    payment_provider: Optional[str]
    payment_status: Optional[str]

class ReferralRecord(TypedDict, total=False):
    """Type-safe referral record from database."""
    referral_id: int
    referrer_user_id: int
    referred_user_id: int
    opened_at: str
    paid_at: Optional[str]
    first_payment_amount: Optional[float]
    first_payment_currency: Optional[str]

class ActivityRecord(TypedDict, total=False):
    """Type-safe activity log record."""
    log_id: int
    user_id: int
    action: str
    timestamp: str

class PromoCodeRecord(TypedDict, total=False):
    """Type-safe promo code record."""
    code: str
    promo_type: str
    value: int
    plan_key: Optional[str]
    max_uses: int
    used_count: int
    expires_at: Optional[str]
    created_at: str


class OfflineSubscriptionRecord(TypedDict, total=False):
    """Type-safe offline subscription claim record."""
    claim_code: str
    subscription_token: Optional[str]
    vpn_uuid: str
    xray_email: str
    plan: str
    days: int
    expires_at: str
    label: Optional[str]
    issued_at: str
    claimed_at: Optional[str]
    claimed_by_tg_id: Optional[int]


# ============================================================================
# ENUMS for type safety
# ============================================================================

class EgressMode(str, Enum):
    """Egress routing mode."""
    DIRECT = "direct"
    WARP = "warp"

class DeviceStatus(str, Enum):
    """Device status values."""
    ACTIVE = "active"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

class PaymentStatus(str, Enum):
    """Payment status values."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class ProfileKind(str, Enum):
    """VPN profile kind."""
    REALITY = "reality"
    XHTTP = "xhttp"
    VMess = "vmess"
    SHADOWSOCKS = "shadowsocks"
    TROJAN = "trojan"


# ============================================================================
# METRICS & MONITORING
# ============================================================================

@dataclass(frozen=True)
class QueryMetrics:
    """Metrics for a single database query."""
    operation: str
    duration_ms: float
    rows_affected: int = 0
    error: Optional[str] = None

class MetricsCollector(Protocol):
    """Protocol for metrics collection."""
    def record(self, metric: QueryMetrics) -> None: ...

class _DefaultMetricsCollector:
    """Default metrics collector that logs slow queries."""
    SLOW_QUERY_THRESHOLD_MS: Final[float] = 100.0
    
    def record(self, metric: QueryMetrics) -> None:
        if metric.error:
            logger.warning(f"DB operation {metric.operation} failed: {metric.error}")
        elif metric.duration_ms > self.SLOW_QUERY_THRESHOLD_MS:
            logger.info(f"Slow query: {metric.operation} took {metric.duration_ms:.1f}ms")

_metrics_collector: MetricsCollector = _DefaultMetricsCollector()

def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set custom metrics collector for database operations."""
    global _metrics_collector
    _metrics_collector = collector


# ============================================================================
# RETRY LOGIC with exponential backoff
# ============================================================================

T = TypeVar("T")

def with_retry(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    exceptions: tuple = (sqlite3.OperationalError,),
    retry_on: Optional[Callable[[Exception], bool]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for automatic retry with exponential backoff.
    
    Handles SQLITE_BUSY and other transient errors.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # Check if we should retry this specific error
                    if retry_on and not retry_on(e):
                        raise
                    
                    # Check for SQLITE_BUSY specifically
                    if isinstance(e, sqlite3.OperationalError):
                        if "database is locked" not in str(e).lower():
                            raise
                    
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        jitter = delay * 0.1 * (hash(str(e)) % 10) / 10
                        time.sleep(delay + jitter)
                        logger.debug(f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}")
                    else:
                        break
            
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry exhaustion")
        
        return wrapper
    return decorator


def _is_busy_error(e: Exception) -> bool:
    """Check if error is SQLITE_BUSY."""
    return isinstance(e, sqlite3.OperationalError) and "database is locked" in str(e).lower()


# ============================================================================
# BATCH OPERATIONS helper
# ============================================================================

@dataclass
class BatchResult:
    """Result of batch operation."""
    success_count: int
    failed_count: int
    errors: List[tuple] = field(default_factory=list)

__all__ = [
    # Connection management
    "get_db_connection", "get_db_connection_traced", "init_database",
    # Type definitions
    "UserRecord", "DeviceRecord", "PaymentRecord", "ReferralRecord",
    "ActivityRecord", "PromoCodeRecord", "OfflineSubscriptionRecord",
    # Enums
    "EgressMode", "DeviceStatus", "PaymentStatus", "ProfileKind",
    # Metrics
    "QueryMetrics", "MetricsCollector", "set_metrics_collector", "BatchResult",
    # High-level operations
    "DatabaseOperations",
    # User operations (legacy)
    "get_user", "get_user_by_subscription_token", "create_user", "update_user",
    "get_user_stats", "get_recent_users", "get_user_egress_mode", "set_user_egress_mode",
    "get_user_extra_device_slots", "add_user_extra_device_slots",
    "delete_user_account", "has_trial_claim", "ensure_trial_claim",
    # Device operations (legacy)
    "create_device", "delete_device", "get_device", "get_user_devices", "update_device", "revoke_device",
    "ensure_legacy_primary_device",
    # Payment operations (legacy)
    "create_pending_payment", "get_payment", "get_pending_payments",
    "get_pending_payments_requiring_reminder", "get_processed_payments",
    "update_payment_status", "record_payment", "transition_pending_payment",
    "expire_stale_pending_payments", "get_payment_status_summary",
    "get_payment_queue_quality_24h", "get_payment_queue_quality_prev_24h",
    "get_recent_payments_for_user",
    # Referral operations (legacy)
    "record_referral_open", "mark_referral_trial_started", "mark_referral_paid", "get_referral_summary",
    "get_top_referrers", "get_recent_referral_rewards", "get_recent_referrals", "get_global_referral_stats",
    "grant_referral_bonus_days",
    # Activity and rate limiting (legacy)
    "log_activity", "has_activity", "get_recent_activity_for_user",
    "register_request_event", "get_recent_rate_limited_count",
    "get_rate_limit_stats", "get_top_rate_limited_users", "get_suspicious_users",
    "count_recent_request_events",
    # Subscription operations (legacy)
    "ensure_user_subscription_token", "record_subscription_access",
    "mark_subscription_access_notified", "count_subscription_accesses",
    "get_subscription_accesses",
    "get_broadcast_user_ids",
    "get_offline_subscription", "claim_offline_subscription",
    # Promo codes (legacy)
    "create_promo_code", "redeem_promo_code", "list_promo_codes", "delete_promo_code",
]

DB_PATH = os.getenv("GHOST_ACCESS_DB_PATH", "x0tta6bl4.db").strip() or "x0tta6bl4.db"

# Connection pool settings
_pool: Queue = Queue(maxsize=10)
_pool_lock = threading.Lock()
_pool_initialized = False

_SQLITE_COMMIT_RETRY_ATTEMPTS: Final[int] = 3
_SQLITE_COMMIT_RETRY_DELAY_S: Final[float] = 0.15


def _is_retryable_commit_error(exc: Exception) -> bool:
    """Return True for SQLite commit failures that are worth retrying once or twice."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "database is locked",
            "database or disk is full",
            "database is busy",
            "cannot commit transaction",
        )
    )


def _create_optimized_connection() -> sqlite3.Connection:
    """Create an optimized SQLite connection."""
    conn = sqlite3.connect(
        DB_PATH,
        timeout=5.0,
        check_same_thread=False,
        isolation_level=None,  # Autocommit for better WAL performance
    )
    conn.row_factory = sqlite3.Row

    # Performance optimizations
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    conn.execute("PRAGMA synchronous=NORMAL")  # Balanced durability/speed
    conn.execute("PRAGMA busy_timeout=5000")  # Wait for busy writers instead of failing fast
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")  # In-memory temp tables
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
    conn.execute("PRAGMA page_size=4096")  # Optimal page size
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA journal_size_limit=67108864")

    return conn


def _init_pool():
    """Initialize connection pool with pre-created connections."""
    global _pool_initialized
    if _pool_initialized:
        return

    with _pool_lock:
        if _pool_initialized:
            return
        # Pre-create 3 connections
        for _ in range(3):
            try:
                conn = _create_optimized_connection()
                _pool.put(conn)
            except Exception as e:
                logger.warning(f"Failed to pre-create connection: {e}")
        _pool_initialized = True
        logger.info("Database connection pool initialized")


@contextmanager
def get_db_connection():
    """Context manager for pooled database connection."""
    _init_pool()
    conn = None

    try:
        # Try to get from pool (non-blocking)
        try:
            conn = _pool.get_nowait()
        except Empty:
            # Create new connection if pool empty
            conn = _create_optimized_connection()

        # Use BEGIN for transaction (WAL mode)
        conn.execute("BEGIN")
        yield conn
        for attempt in range(_SQLITE_COMMIT_RETRY_ATTEMPTS):
            try:
                conn.execute("COMMIT")
                break
            except Exception as exc:
                is_last_attempt = attempt >= _SQLITE_COMMIT_RETRY_ATTEMPTS - 1
                if not _is_retryable_commit_error(exc) or is_last_attempt:
                    raise
                try:
                    # Help WAL catch up before retrying a commit that failed under
                    # transient write pressure.
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception:
                    pass
                delay = _SQLITE_COMMIT_RETRY_DELAY_S * (attempt + 1)
                logger.warning(
                    "Retrying SQLite COMMIT after transient failure (%s/%s): %s",
                    attempt + 1,
                    _SQLITE_COMMIT_RETRY_ATTEMPTS,
                    exc,
                )
                time.sleep(delay)

    except Exception as e:
        if conn:
            try:
                conn.execute("ROLLBACK")
            except:
                pass
        logger.error(f"Database error: {e}")
        raise

    finally:
        if conn:
            try:
                # Return to pool
                _pool.put_nowait(conn)
            except:
                # Pool full, close connection
                conn.close()


def init_database():
    """Initialize database tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_used BOOLEAN DEFAULT 0,
                plan TEXT DEFAULT 'trial',
                expires_at TIMESTAMP,
                vpn_uuid TEXT,
                vpn_config TEXT,
                payment_amount REAL,
                payment_currency TEXT,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                zkp_public_key TEXT,
                subscription_token TEXT,
                subscription_updated_at TIMESTAMP,
                extra_device_slots INTEGER DEFAULT 0,
                delivery_profile TEXT DEFAULT 'default_nl',
                entry_node TEXT DEFAULT 'nl',
                client_family TEXT DEFAULT 'generic',
                transport_preference TEXT DEFAULT '',
                stealth_mode_enabled BOOLEAN DEFAULT 0
            )
        """)

        cursor.execute("PRAGMA table_info(users)")
        user_columns = {row["name"] for row in cursor.fetchall()}
        if "subscription_token" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN subscription_token TEXT")
        if "subscription_updated_at" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN subscription_updated_at TIMESTAMP")
        if "egress_mode" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN egress_mode TEXT DEFAULT 'direct'")
        if "onboarding_step" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_step TEXT")
        if "onboarding_device" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_device TEXT")
        if "onboarding_client" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_client TEXT")
        if "onboarding_has_app" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_has_app BOOLEAN")
        if "onboarding_client_installed" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_client_installed BOOLEAN")
        if "payment_return_target" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN payment_return_target TEXT")
        if "extra_device_slots" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN extra_device_slots INTEGER DEFAULT 0")
        if "delivery_profile" not in user_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN delivery_profile TEXT DEFAULT 'default_nl'"
            )
        if "entry_node" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN entry_node TEXT DEFAULT 'nl'")
        if "client_family" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN client_family TEXT DEFAULT 'generic'")
        if "transport_preference" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN transport_preference TEXT DEFAULT ''")
        if "stealth_mode_enabled" not in user_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN stealth_mode_enabled BOOLEAN DEFAULT 0"
            )

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_subscription_token
            ON users(subscription_token)
            WHERE subscription_token IS NOT NULL
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_expires_at
            ON users(expires_at)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trial_claims (
                user_id INTEGER PRIMARY KEY,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            """
            INSERT INTO trial_claims (user_id)
            SELECT user_id
            FROM users
            WHERE trial_used = 1
              AND user_id NOT IN (SELECT user_id FROM trial_claims)
            """
        )

        # Payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payment_provider TEXT,
                payment_status TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_status_date
            ON payments(payment_status, payment_date DESC, payment_id DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_user_status_date
            ON payments(user_id, payment_status, payment_date DESC, payment_id DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_provider_status
            ON payments(payment_provider, payment_status)
        """)

        # Activity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Processed webhooks for idempotency protection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_webhooks (
                webhook_id TEXT PRIMARY KEY,
                provider TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webhooks_provider
            ON processed_webhooks(provider, processed_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_log_user_timestamp
            ON activity_log(user_id, timestamp DESC)
        """)

        # Devices table for per-device UUID binding.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_name TEXT NOT NULL,
                device_type TEXT DEFAULT 'other',
                vpn_uuid TEXT NOT NULL UNIQUE,
                xray_email TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                profile_kind TEXT DEFAULT 'reality',
                first_seen_at TIMESTAMP,
                last_seen_at TIMESTAMP,
                last_ip TEXT,
                last_handshake_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_user_status
            ON devices(user_id, status)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_subscriptions (
                claim_code TEXT PRIMARY KEY,
                subscription_token TEXT UNIQUE,
                vpn_uuid TEXT NOT NULL UNIQUE,
                xray_email TEXT NOT NULL,
                plan TEXT NOT NULL,
                days INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                label TEXT,
                delivery_profile TEXT,
                entry_node TEXT,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_at TIMESTAMP,
                claimed_by_tg_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_subscriptions_claimed_by
            ON offline_subscriptions(claimed_by_tg_id)
        """)
        cursor.execute("PRAGMA table_info(offline_subscriptions)")
        offline_columns = {row["name"] for row in cursor.fetchall()}
        if "subscription_token" not in offline_columns:
            cursor.execute("ALTER TABLE offline_subscriptions ADD COLUMN subscription_token TEXT")
        if "delivery_profile" not in offline_columns:
            cursor.execute("ALTER TABLE offline_subscriptions ADD COLUMN delivery_profile TEXT")
        if "entry_node" not in offline_columns:
            cursor.execute("ALTER TABLE offline_subscriptions ADD COLUMN entry_node TEXT")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_offline_subscriptions_token
            ON offline_subscriptions(subscription_token)
            WHERE subscription_token IS NOT NULL
        """)

        # Referral ledger.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL UNIQUE,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_bonus_awarded_at TIMESTAMP,
                paid_at TIMESTAMP,
                first_payment_amount REAL,
                first_payment_currency TEXT,
                FOREIGN KEY (referrer_user_id) REFERENCES users(id),
                FOREIGN KEY (referred_user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer
            ON referrals(referrer_user_id)
        """)
        cursor.execute("PRAGMA table_info(referrals)")
        referral_columns = {row["name"] for row in cursor.fetchall()}
        if "trial_bonus_awarded_at" not in referral_columns:
            cursor.execute("ALTER TABLE referrals ADD COLUMN trial_bonus_awarded_at TIMESTAMP")

        # Persistent request log for rate limiting across service restarts.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_request_events_user_action_created
            ON request_events(user_id, action, created_at)
        """)

        # Subscription endpoint access tracking (new device detection).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_accesses (
                access_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_agent TEXT NOT NULL DEFAULT '',
                ip_address TEXT,
                client_app TEXT,
                client_version TEXT,
                platform TEXT,
                os_version TEXT,
                device_model TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sub_access_user_ua
            ON subscription_accesses(user_id, user_agent)
        """)

        # Promo codes table.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY COLLATE NOCASE,
                promo_type TEXT NOT NULL DEFAULT 'days',
                value INTEGER NOT NULL DEFAULT 0,
                plan_key TEXT,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_redemptions (
                redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL COLLATE NOCASE,
                user_id INTEGER NOT NULL,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        logger.info("Database initialized")


# ============================================================================
# INSTRUMENTED DATABASE OPERATIONS
# ============================================================================

@contextmanager
def get_db_connection_traced(operation: str = "unknown") -> Generator[sqlite3.Connection, None, None]:
    """Instrumented version of get_db_connection with timing metrics."""
    start_time = time.time()
    error: Optional[str] = None
    
    try:
        with get_db_connection() as conn:
            yield conn
    except Exception as e:
        error = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        _metrics_collector.record(QueryMetrics(
            operation=operation,
            duration_ms=duration_ms,
            error=error
        ))


class DatabaseOperations:
    """High-level database operations with retry and metrics."""
    
    @staticmethod
    @with_retry(max_retries=3, retry_on=_is_busy_error)
    def get_user(user_id: int) -> Optional[UserRecord]:
        """Get user by ID with retry and metrics."""
        with get_db_connection_traced(f"get_user:{user_id}") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None  # type: ignore
    
    @staticmethod
    @with_retry(max_retries=3, retry_on=_is_busy_error)
    def get_users_batch(user_ids: List[int]) -> Dict[int, UserRecord]:
        """Batch fetch multiple users efficiently."""
        if not user_ids:
            return {}
        
        with get_db_connection_traced(f"get_users_batch:{len(user_ids)}") as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(user_ids))
            cursor.execute(
                f"SELECT * FROM users WHERE user_id IN ({placeholders})",
                tuple(user_ids)
            )
            return {row["user_id"]: dict(row) for row in cursor.fetchall()}  # type: ignore
    
    @staticmethod
    @with_retry(max_retries=3, retry_on=_is_busy_error)
    def get_active_users(limit: int = 100) -> List[UserRecord]:
        """Get users with active subscriptions."""
        with get_db_connection_traced(f"get_active_users:{limit}") as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM users 
                WHERE expires_at > datetime('now') 
                ORDER BY last_activity DESC 
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]  # type: ignore
    
    @staticmethod
    @with_retry(max_retries=5, retry_on=_is_busy_error)
    def bulk_update_users(updates: List[tuple]) -> BatchResult:
        """
        Bulk update users in single transaction.
        
        Args:
            updates: List of (user_id, field_name, value) tuples
        """
        result = BatchResult(success_count=0, failed_count=0)
        
        with get_db_connection_traced(f"bulk_update_users:{len(updates)}") as conn:
            cursor = conn.cursor()
            
            for user_id, field, value in updates:
                try:
                    cursor.execute(
                        f"UPDATE users SET {field} = ? WHERE user_id = ?",
                        (value, user_id)
                    )
                    result.success_count += 1
                except Exception as e:
                    result.failed_count += 1
                    result.errors.append((user_id, str(e)))
            
            return result


# ============================================================================
# LEGACY API (maintained for backward compatibility)
# ============================================================================

def get_user(user_id: int) -> Optional[Dict]:
    """Get user by user_id"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_user_by_subscription_token(token: str) -> Optional[Dict]:
    """Get user by subscription token."""
    if not token:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE subscription_token = ?",
            (token,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_offline_subscription(claim_code: str) -> Optional[OfflineSubscriptionRecord]:
    """Get offline subscription by claim code."""
    if not claim_code:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM offline_subscriptions WHERE claim_code = ?",
                (claim_code,),
            )
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() and "offline_subscriptions" in str(exc):
                return None
            raise
        row = cursor.fetchone()
        return dict(row) if row else None


def get_offline_subscription_by_token(token: str) -> Optional[OfflineSubscriptionRecord]:
    """Get offline subscription by subscription token."""
    if not token:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM offline_subscriptions WHERE subscription_token = ?",
                (token,),
            )
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() and "offline_subscriptions" in str(exc):
                return None
            raise
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(
    user_id: int,
    username: Optional[str] = None,
    plan: str = "trial",
    expires_at: Optional[datetime] = None,
    vpn_uuid: Optional[str] = None,
    trial_used: Optional[bool] = None,
    delivery_profile: str = "default_nl",
    entry_node: str = "nl",
    client_family: str = "generic",
    transport_preference: str = "",
    stealth_mode_enabled: bool = False,
) -> Dict:
    """Create new user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if user exists
        existing = get_user(user_id)
        if existing:
            logger.warning(f"User {user_id} already exists")
            return existing

        # Set default expires_at for trial
        if expires_at is None and plan == "trial":
            expires_at = datetime.now() + timedelta(days=7)
        subscription_token = secrets.token_urlsafe(24)
        subscription_updated_at = datetime.now().isoformat()

        effective_trial_used = plan == "trial" if trial_used is None else bool(trial_used)

        cursor.execute(
            """
            INSERT INTO users (
                user_id, username, plan, expires_at, vpn_uuid, trial_used,
                subscription_token, subscription_updated_at, delivery_profile,
                entry_node, client_family, transport_preference, stealth_mode_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                username,
                plan,
                expires_at.isoformat() if expires_at else None,
                vpn_uuid,
                effective_trial_used,
                subscription_token,
                subscription_updated_at,
                (delivery_profile or "default_nl").strip() or "default_nl",
                (entry_node or "nl").strip() or "nl",
                (client_family or "generic").strip() or "generic",
                (transport_preference or "").strip().lower(),
                1 if stealth_mode_enabled else 0,
            ),
        )

        logger.info(f"User {user_id} created with plan {plan}")

        # Log inside the same transaction to avoid nested write locks.
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        """,
            (user_id, "user_created"),
        )

        # Must be inside the same context to ensure atomicity and visibility
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


@with_retry(retry_on=_is_busy_error)
def claim_offline_subscription(
    claim_code: str,
    tg_user_id: int,
    username: Optional[str] = None,
) -> OfflineSubscriptionRecord:
    """
    Atomically bind an offline-issued subscription to a Telegram user.

    Raises:
        LookupError: claim code does not exist
        ValueError: claim already used by another Telegram user or Telegram user already exists
    """
    normalized_code = (claim_code or "").strip().upper()
    if not normalized_code:
        raise LookupError("missing")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM offline_subscriptions WHERE claim_code = ?",
            (normalized_code,),
        )
        row = cursor.fetchone()
        if not row:
            raise LookupError("missing")

        record = dict(row)
        claimed_by = record.get("claimed_by_tg_id")
        if claimed_by is not None and int(claimed_by) != int(tg_user_id):
            raise ValueError("already_claimed")

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (tg_user_id,))
        existing_user = cursor.fetchone()
        if existing_user and claimed_by is None:
            raise ValueError("user_exists")

        if claimed_by is None:
            subscription_token = (
                (record.get("subscription_token") or "").strip() or secrets.token_urlsafe(24)
            )
            subscription_updated_at = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO users (
                    user_id, username, plan, expires_at, vpn_uuid, trial_used,
                    subscription_token, subscription_updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    tg_user_id,
                    username,
                    record["plan"],
                    record["expires_at"],
                    record["vpn_uuid"],
                    subscription_token,
                    subscription_updated_at,
                ),
            )
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (tg_user_id, "user_created"),
            )
            cursor.execute(
                """
                INSERT INTO devices (
                    user_id, device_name, device_type, vpn_uuid, xray_email, status, profile_kind
                )
                VALUES (?, ?, ?, ?, ?, 'active', 'reality')
                """,
                (
                    tg_user_id,
                    "Основное устройство",
                    "unknown",
                    record["vpn_uuid"],
                    record["xray_email"],
                ),
            )
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (tg_user_id, "device_created:Основное устройство"),
            )
            cursor.execute(
                """
                UPDATE offline_subscriptions
                SET claimed_at = CURRENT_TIMESTAMP,
                    claimed_by_tg_id = ?,
                    subscription_token = ?
                WHERE claim_code = ?
                  AND claimed_by_tg_id IS NULL
                """,
                (tg_user_id, subscription_token, normalized_code),
            )
            if cursor.rowcount != 1:
                raise sqlite3.OperationalError("offline claim race detected")
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (tg_user_id, f"offline_subscription_claimed:{normalized_code}"),
            )

        cursor.execute(
            "SELECT * FROM offline_subscriptions WHERE claim_code = ?",
            (normalized_code,),
        )
        claimed_row = cursor.fetchone()
        return dict(claimed_row) if claimed_row else record


def update_user(
    user_id: int,
    plan: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    vpn_uuid: Optional[str] = None,
    vpn_config: Optional[str] = None,
    zkp_public_key: Optional[str] = None,
    trial_used: Optional[bool] = None,
    egress_mode: Optional[str] = None,
    extra_device_slots: Optional[int] = None,
    delivery_profile: Optional[str] = None,
    entry_node: Optional[str] = None,
    client_family: Optional[str] = None,
    transport_preference: Optional[str] = None,
    stealth_mode_enabled: Optional[bool] = None,
) -> bool:
    """Update user data"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if plan is not None:
            updates.append("plan = ?")
            params.append(plan)

        if expires_at is not None:
            updates.append("expires_at = ?")
            params.append(expires_at.isoformat())

        if vpn_uuid is not None:
            updates.append("vpn_uuid = ?")
            params.append(vpn_uuid)

        if vpn_config is not None:
            updates.append("vpn_config = ?")
            params.append(vpn_config)

        if trial_used is not None:
            updates.append("trial_used = ?")
            params.append(1 if trial_used else 0)

        if zkp_public_key is not None:
            updates.append("zkp_public_key = ?")
            params.append(zkp_public_key)

        if egress_mode is not None:
            updates.append("egress_mode = ?")
            params.append(egress_mode)

        if extra_device_slots is not None:
            updates.append("extra_device_slots = ?")
            params.append(max(0, int(extra_device_slots)))

        if delivery_profile is not None:
            updates.append("delivery_profile = ?")
            params.append((delivery_profile or "default_nl").strip() or "default_nl")

        if entry_node is not None:
            updates.append("entry_node = ?")
            params.append((entry_node or "nl").strip() or "nl")

        if client_family is not None:
            updates.append("client_family = ?")
            params.append((client_family or "generic").strip() or "generic")

        if transport_preference is not None:
            updates.append("transport_preference = ?")
            normalized_preference = (transport_preference or "").strip().lower()
            if normalized_preference not in {"", "main", "fallback"}:
                normalized_preference = ""
            params.append(normalized_preference)

        if stealth_mode_enabled is not None:
            updates.append("stealth_mode_enabled = ?")
            params.append(1 if stealth_mode_enabled else 0)

        if not updates:
            return False

        updates.append("last_activity = ?")
        params.append(datetime.now().isoformat())
        params.append(user_id)

        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)

        return cursor.rowcount > 0


def is_user_active(user_id: int) -> bool:
    """Check if user has active subscription"""
    user = get_user(user_id)
    if not user or not user.get("expires_at"):
        return False

    expires_at = datetime.fromisoformat(user["expires_at"])
    return datetime.now() < expires_at


def get_user_extra_device_slots(user_id: int) -> int:
    """Return purchased extra device slots for a user."""
    user = get_user(user_id)
    if not user:
        return 0
    try:
        return max(0, int(user.get("extra_device_slots") or 0))
    except (TypeError, ValueError):
        return 0


def add_user_extra_device_slots(user_id: int, slots: int, *, reason: str = "device_slot_addon") -> int:
    """Atomically increase purchased extra device slots and return the new total."""
    increment = int(slots)
    if increment <= 0:
        return get_user_extra_device_slots(user_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET extra_device_slots = COALESCE(extra_device_slots, 0) + ?,
                last_activity = ?
            WHERE user_id = ?
            """,
            (increment, datetime.now().isoformat(), user_id),
        )
        if cursor.rowcount <= 0:
            raise RuntimeError(f"User {user_id} not found")
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
            """,
            (user_id, f"{reason}:{increment}"),
        )
        row = cursor.execute(
            "SELECT extra_device_slots FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        try:
            return max(0, int((row or {})["extra_device_slots"]))
        except (TypeError, ValueError, KeyError):
            return 0


def ensure_user_subscription_token(user_id: int) -> str:
    """Get or create a stable subscription token for a user."""
    user = get_user(user_id)
    if not user:
        raise RuntimeError(f"User {user_id} not found")
    token = (user.get("subscription_token") or "").strip()
    if token:
        return token

    with get_db_connection() as conn:
        cursor = conn.cursor()
        while True:
            token = secrets.token_urlsafe(24)
            cursor.execute(
                """
                UPDATE users
                SET subscription_token = ?, subscription_updated_at = ?
                WHERE user_id = ?
                  AND (subscription_token IS NULL OR subscription_token = '')
                """,
                (token, datetime.now().isoformat(), user_id),
            )
            if cursor.rowcount > 0:
                return token
            cursor.execute(
                "SELECT subscription_token FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row and row["subscription_token"]:
                return row["subscription_token"]


def get_active_users() -> List[Dict]:
    """Get all active users"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users 
            WHERE expires_at > datetime('now')
            ORDER BY expires_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def log_activity(user_id: int, action: str):
    """Log user activity"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        """,
            (user_id, action),
        )


def has_activity(user_id: int, action: str) -> bool:
    """Check whether an exact activity action already exists for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM activity_log
            WHERE user_id = ?
              AND action = ?
            LIMIT 1
            """,
            (user_id, action),
        )
        return cursor.fetchone() is not None


def record_payment(
    user_id: int,
    amount: float,
    currency: str,
    provider: str = "telegram",
    status: str = "completed",
):
    """Record payment"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments (user_id, amount, currency, payment_provider, payment_status)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, amount, currency, provider, status),
        )

        # Log inside the same transaction to avoid nested write locks.
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        """,
            (user_id, f"payment_{status}"),
        )


def create_pending_payment(
    user_id: int,
    amount: float,
    currency: str,
    provider: str,
) -> Dict:
    """Create or reuse a pending payment claim for manual review."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM payments
            WHERE user_id = ?
              AND amount = ?
              AND currency = ?
              AND payment_provider = ?
              AND payment_status = 'pending'
            ORDER BY payment_date DESC, payment_id DESC
            LIMIT 1
            """,
            (user_id, amount, currency, provider),
        )
        existing = cursor.fetchone()
        if existing:
            return dict(existing)

        cursor.execute(
            """
            INSERT INTO payments (user_id, amount, currency, payment_provider, payment_status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (user_id, amount, currency, provider),
        )
        payment_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
            """,
            (user_id, "payment_pending_created"),
        )
        cursor.execute(
            "SELECT * FROM payments WHERE payment_id = ?",
            (payment_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_payment(payment_id: int) -> Optional[Dict]:
    """Get payment by id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM payments WHERE payment_id = ?",
            (payment_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_pending_payments(limit: int = 20) -> List[Dict]:
    """Get pending payments ordered from newest to oldest."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, u.username
            FROM payments p
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE p.payment_status = 'pending'
            ORDER BY p.payment_date DESC, p.payment_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_processed_payments(limit: int = 20, include_internal: bool = False) -> List[Dict]:
    """Get processed payments ordered from newest to oldest."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if include_internal:
            cursor.execute(
                """
                SELECT p.*, u.username
                FROM payments p
                LEFT JOIN users u ON u.user_id = p.user_id
                WHERE p.payment_status IN ('approved', 'rejected', 'completed', 'expired')
                ORDER BY p.payment_date DESC, p.payment_id DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            cursor.execute(
                """
                SELECT p.*, u.username
                FROM payments p
                LEFT JOIN users u ON u.user_id = p.user_id
                WHERE p.payment_status IN ('approved', 'rejected', 'expired')
                ORDER BY p.payment_date DESC, p.payment_id DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_pending_payments_requiring_reminder(
    min_age_minutes: int,
    reminder_action_prefix: str,
    limit: int = 20,
) -> List[Dict]:
    """Get pending payments older than threshold that have not received this reminder yet."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, u.username
            FROM payments p
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE p.payment_status = 'pending'
              AND datetime(p.payment_date) <= datetime('now', ?)
              AND NOT EXISTS (
                  SELECT 1
                  FROM activity_log a
                  WHERE a.user_id = p.user_id
                    AND a.action = (? || p.payment_id)
              )
            ORDER BY p.payment_date ASC, p.payment_id ASC
            LIMIT ?
            """,
            (f"-{int(min_age_minutes)} minutes", reminder_action_prefix, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_payment_status(payment_id: int, status: str) -> bool:
    """Update payment status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE payments
            SET payment_status = ?
            WHERE payment_id = ?
            """,
            (status, payment_id),
        )
        if cursor.rowcount <= 0:
            return False
        cursor.execute(
            """
            SELECT user_id FROM payments WHERE payment_id = ?
            """,
            (payment_id,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (row["user_id"], f"payment_{status}"),
            )
        return True


def transition_pending_payment(payment_id: int, status: str) -> bool:
    """Atomically move a pending payment to a final reviewed state."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE payments
            SET payment_status = ?
            WHERE payment_id = ?
              AND payment_status = 'pending'
            """,
            (status, payment_id),
        )
        if cursor.rowcount <= 0:
            return False
        cursor.execute(
            """
            SELECT user_id FROM payments WHERE payment_id = ?
            """,
            (payment_id,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (row["user_id"], f"payment_{status}"),
            )
        return True


def approve_payment_and_activate_subscription(
    payment_id: int,
    user_id: int,
    plan_key: str,
    expires_at: datetime,
    vpn_uuid: str,
    vpn_config: str,
    provider: str,
) -> bool:
    """Atomically approve payment and activate user subscription.
    
    This ensures payment status and user subscription are updated together
    or not at all, preventing partial state on failures.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Update payment status to approved
            cursor.execute(
                """
                UPDATE payments
                SET payment_status = 'approved'
                WHERE payment_id = ?
                  AND payment_status = 'pending'
                """,
                (payment_id,),
            )
            if cursor.rowcount <= 0:
                return False

            # Update user subscription
            cursor.execute(
                """
                UPDATE users
                SET plan = ?,
                    expires_at = ?,
                    vpn_uuid = ?,
                    vpn_config = ?,
                    onboarding_step = CASE 
                        WHEN onboarding_step LIKE 'new:%' THEN 'new:access_delivered'
                        WHEN onboarding_step LIKE 'add:%' THEN 'add:access_delivered'
                        ELSE onboarding_step 
                    END,
                    payment_return_target = NULL
                WHERE user_id = ?
                """,
                (plan_key, expires_at.isoformat(), vpn_uuid, vpn_config, user_id),
            )

            # Log the activation
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (user_id, f"payment_approved_subscription_activated_{plan_key}"),
            )

            # Record billing
            cursor.execute(
                """
                INSERT INTO payments (user_id, amount, currency, payment_provider, payment_status)
                SELECT user_id, amount, currency, ?, 'completed'
                FROM payments
                WHERE payment_id = ?
                """,
                (provider, payment_id),
            )

            return True
        except Exception:
            # Transaction will be rolled back by context manager
            return False


def cancel_pending_payments_for_user(user_id: int) -> int:
    """Mark all pending payments for a user as cancelled by user.

    Returns the number of rows updated. Used by the onboarding cancel flow
    so that a late provider webhook does not surprise-activate a subscription
    the user has explicitly cancelled.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE payments
            SET payment_status = 'cancelled_by_user'
            WHERE user_id = ?
              AND payment_status = 'pending'
            """,
            (user_id,),
        )
        rowcount = cursor.rowcount or 0
        if rowcount > 0:
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (user_id, f"payment_cancelled_by_user_count_{rowcount}"),
            )
        return rowcount


def expire_stale_pending_payments(older_than_hours: int = 24) -> List[Dict]:
    """Mark stale pending payments as expired and return affected rows."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT payment_id, user_id, amount, currency, payment_provider, payment_date
            FROM payments
            WHERE payment_status = 'pending'
              AND datetime(payment_date) <= datetime('now', ?)
            """,
            (f"-{older_than_hours} hours",),
        )
        rows = cursor.fetchall()
        if not rows:
            return []
        expired_rows: List[Dict] = []
        for row in rows:
            payment_row = dict(row)
            cursor.execute(
                """
                UPDATE payments
                SET payment_status = 'expired'
                WHERE payment_id = ?
                  AND payment_status = 'pending'
                """,
                (payment_row["payment_id"],),
            )
            if cursor.rowcount <= 0:
                continue
            expired_rows.append(payment_row)

        if expired_rows:
            cursor.executemany(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                [(row["user_id"], "payment_expired") for row in expired_rows],
            )
        return expired_rows


def get_user_stats() -> Dict:
    """Get statistics about users"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]

        # Active users
        cursor.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE expires_at > datetime('now')
        """)
        active_users = cursor.fetchone()["count"]

        # Trial users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE plan = 'trial'")
        trial_users = cursor.fetchone()["count"]

        # Pro users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE plan = 'pro'")
        pro_users = cursor.fetchone()["count"]

        # Total revenue
        cursor.execute("""
            SELECT SUM(amount) as total FROM payments
            WHERE payment_status = 'completed'
              AND payment_provider != 'admin_grant'
        """)
        total_revenue = cursor.fetchone()["total"] or 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "trial_users": trial_users,
            "pro_users": pro_users,
            "total_revenue": total_revenue,
        }


def get_recent_users(
    limit: int = 20,
    status: str = "all",
    search: str = "",
    offset: int = 0,
) -> List[Dict]:
    """Return recent users for admin directory with optional status filter and search."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clauses = []
        params: List[object] = []

        if status == "active":
            where_clauses.append(
                "expires_at IS NOT NULL AND datetime(expires_at) > datetime('now')"
            )
        elif status == "expired":
            where_clauses.append("(expires_at IS NULL OR datetime(expires_at) <= datetime('now'))")
        elif status == "trial":
            where_clauses.append("plan = 'trial'")

        search = (search or "").strip().lstrip("@")
        if search:
            if search.isdigit():
                where_clauses.append("CAST(user_id AS TEXT) LIKE ?")
                params.append(f"%{search}%")
            else:
                where_clauses.append("LOWER(COALESCE(username, '')) LIKE ?")
                params.append(f"%{search.lower()}%")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT
                user_id,
                username,
                plan,
                expires_at,
                created_at,
                last_activity,
                CASE
                    WHEN expires_at IS NOT NULL AND datetime(expires_at) > datetime('now') THEN 1
                    ELSE 0
                END as is_active
            FROM users
            {where_sql}
            ORDER BY
                is_active DESC,
                datetime(COALESCE(last_activity, created_at)) DESC,
                user_id DESC
            LIMIT ?
            OFFSET ?
            """,
            (*params, limit, max(offset, 0)),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_payment_status_summary() -> Dict:
    """Get aggregate payment counts and sums by status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        summary = {}
        for status in ("pending", "approved", "rejected", "completed", "expired"):
            if status == "completed":
                cursor.execute(
                    """
                    SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
                    FROM payments
                    WHERE payment_status = ?
                      AND payment_provider != 'admin_grant'
                    """,
                    (status,),
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
                    FROM payments
                    WHERE payment_status = ?
                    """,
                    (status,),
                )
            row = cursor.fetchone()
            summary[status] = {
                "count": row["cnt"] if row else 0,
                "total": float(row["total"] or 0),
            }
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM payments
            WHERE payment_status = 'pending'
              AND datetime(payment_date) <= datetime('now', '-10 minutes')
            """
        )
        row = cursor.fetchone()
        summary["pending_older_10m"] = row["cnt"] if row else 0
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM payments p
            WHERE p.payment_status = 'pending'
              AND EXISTS (
                  SELECT 1
                  FROM activity_log a
                  WHERE a.user_id = p.user_id
                    AND a.action = ('payment_pending_reminder_10m:' || p.payment_id)
              )
            """
        )
        row = cursor.fetchone()
        summary["pending_reminded_10m"] = row["cnt"] if row else 0
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM payments
            WHERE payment_status = 'pending'
              AND datetime(payment_date) <= datetime('now', '-1 hour')
            """
        )
        row = cursor.fetchone()
        summary["pending_older_1h"] = row["cnt"] if row else 0
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM payments p
            WHERE p.payment_status = 'pending'
              AND EXISTS (
                  SELECT 1
                  FROM activity_log a
                  WHERE a.user_id = p.user_id
                    AND a.action = ('payment_pending_reminder_1h:' || p.payment_id)
              )
            """
        )
        row = cursor.fetchone()
        summary["pending_reminded_1h"] = row["cnt"] if row else 0
        return summary


def get_payment_queue_quality_window(window_start: str, window_end: str = "now") -> Dict:
    """Get payment queue process metrics for a relative SQLite datetime window."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        metrics = {}
        queries = {
            "created": "action = 'payment_pending_created'",
            "reminded_10m": "action LIKE 'payment_pending_reminder_10m:%'",
            "reminded_1h": "action LIKE 'payment_pending_reminder_1h:%'",
            "expired": "action = 'payment_expired'",
            "approved": "action = 'payment_approved'",
        }
        for key, condition in queries.items():
            cursor.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM activity_log
                WHERE {condition}
                  AND timestamp >= datetime('now', ?)
                  AND timestamp < datetime('now', ?)
                """,
                (window_start, window_end),
            )
            row = cursor.fetchone()
            metrics[key] = int(row["cnt"] or 0)
        cursor.execute(
            """
            SELECT payment_provider
            FROM payments
            WHERE payment_status = 'completed'
              AND payment_date >= datetime('now', ?)
              AND payment_date < datetime('now', ?)
              AND (
                  payment_provider LIKE 'yoomoney_auto:%'
                  OR payment_provider LIKE 'yoomoney_manual_review:%'
                  OR payment_provider LIKE 'yookassa_auto:%'
                  OR payment_provider LIKE 'yookassa_manual_review:%'
                  OR payment_provider LIKE 'cardlink_auto:%'
                  OR payment_provider LIKE 'cardlink_manual_review:%'
              )
            """,
            (window_start, window_end),
        )
        approval_rows = [dict(row) for row in cursor.fetchall()]
        auto_approved = 0
        manual_approved = 0
        delayed_approved = 0
        for row in approval_rows:
            provider = row.get("payment_provider") or ""
            parts = provider.split(":")
            if len(parts) < 3:
                continue
            source = parts[0]
            try:
                claim_payment_id = int(parts[1])
            except ValueError:
                continue
            if source in {"yoomoney_auto", "yookassa_auto", "cardlink_auto"}:
                auto_approved += 1
            elif source in {
                "yoomoney_manual_review",
                "yookassa_manual_review",
                "cardlink_manual_review",
            }:
                manual_approved += 1
            cursor.execute(
                """
                SELECT 1
                FROM activity_log
                WHERE action = ?
                  AND timestamp >= datetime('now', ?)
                  AND timestamp < datetime('now', ?)
                LIMIT 1
                """,
                (f"payment_pending_reminder_1h:{claim_payment_id}", window_start, window_end),
            )
            if cursor.fetchone():
                delayed_approved += 1
        metrics["auto_approved"] = auto_approved
        metrics["manual_approved"] = manual_approved
        metrics["delayed_approved"] = delayed_approved
        return metrics


def get_payment_queue_quality_24h() -> Dict:
    """Get payment queue process metrics for the last 24 hours."""
    return get_payment_queue_quality_window("-24 hours", "now")


def get_payment_queue_quality_prev_24h() -> Dict:
    """Get payment queue process metrics for the previous 24 hours."""
    return get_payment_queue_quality_window("-48 hours", "-24 hours")


def get_recent_payments_for_user(
    user_id: int,
    limit: int = 5,
    include_internal: bool = False,
) -> List[Dict]:
    """Get recent payments for a specific user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if include_internal:
            cursor.execute(
                """
                SELECT payment_id, amount, currency, payment_date, payment_provider, payment_status
                FROM payments
                WHERE user_id = ?
                ORDER BY payment_date DESC, payment_id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT payment_id, amount, currency, payment_date, payment_provider, payment_status
                FROM payments
                WHERE user_id = ?
                  AND NOT (
                      payment_status = 'completed'
                      AND (
                          payment_provider = 'admin_grant'
                          OR payment_provider LIKE 'yoomoney_auto:%'
                          OR payment_provider LIKE 'yoomoney_manual_review:%'
                          OR payment_provider LIKE 'yookassa_auto:%'
                          OR payment_provider LIKE 'yookassa_manual_review:%'
                          OR payment_provider LIKE 'cardlink_auto:%'
                          OR payment_provider LIKE 'cardlink_manual_review:%'
                      )
                  )
                ORDER BY payment_date DESC, payment_id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_activity_for_user(user_id: int, limit: int = 10) -> List[Dict]:
    """Get recent activity log entries for a specific user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT log_id, action, timestamp
            FROM activity_log
            WHERE user_id = ?
            ORDER BY timestamp DESC, log_id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_user_devices(user_id: int, include_revoked: bool = False) -> List[Dict]:
    """Get devices for user ordered by creation time."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if include_revoked:
            cursor.execute(
                """
                SELECT * FROM devices
                WHERE user_id = ?
                ORDER BY created_at ASC, device_id ASC
                """,
                (user_id,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM devices
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at ASC, device_id ASC
                """,
                (user_id,),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_device(device_id: int) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_device_by_uuid(vpn_uuid: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE vpn_uuid = ?", (vpn_uuid,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_device_by_xray_email(xray_email: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE xray_email = ?", (xray_email,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_device(
    user_id: int,
    device_name: str,
    vpn_uuid: str,
    device_type: str = "other",
    xray_email: Optional[str] = None,
    profile_kind: str = "reality",
) -> Dict:
    """Create a new active device bound to its own UUID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO devices (
                user_id, device_name, device_type, vpn_uuid, xray_email, status, profile_kind
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (user_id, device_name, device_type, vpn_uuid, xray_email, profile_kind),
        )
        device_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
            """,
            (user_id, f"device_created:{device_name}"),
        )
        cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_device(device_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
        return cursor.rowcount > 0


def update_device(
    device_id: int,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
    xray_email: Optional[str] = None,
    status: Optional[str] = None,
    profile_kind: Optional[str] = None,
    last_ip: Optional[str] = None,
    first_seen_at: Optional[datetime] = None,
    last_seen_at: Optional[datetime] = None,
    last_handshake_at: Optional[datetime] = None,
    revoked_at: Optional[datetime] = None,
) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []

        if device_name is not None:
            updates.append("device_name = ?")
            params.append(device_name)
        if device_type is not None:
            updates.append("device_type = ?")
            params.append(device_type)
        if xray_email is not None:
            updates.append("xray_email = ?")
            params.append(xray_email)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if profile_kind is not None:
            updates.append("profile_kind = ?")
            params.append(profile_kind)
        if last_ip is not None:
            updates.append("last_ip = ?")
            params.append(last_ip)
        if first_seen_at is not None:
            updates.append("first_seen_at = ?")
            params.append(first_seen_at.isoformat())
        if last_seen_at is not None:
            updates.append("last_seen_at = ?")
            params.append(last_seen_at.isoformat())
        if last_handshake_at is not None:
            updates.append("last_handshake_at = ?")
            params.append(last_handshake_at.isoformat())
        if revoked_at is not None:
            updates.append("revoked_at = ?")
            params.append(revoked_at.isoformat())

        if not updates:
            return False

        params.append(device_id)
        cursor.execute(
            f"UPDATE devices SET {', '.join(updates)} WHERE device_id = ?",
            params,
        )
        return cursor.rowcount > 0


def revoke_device(device_id: int) -> bool:
    device = get_device(device_id)
    if not device:
        return False

    updated = update_device(
        device_id,
        status="revoked",
        revoked_at=datetime.now(),
    )
    if updated:
        log_activity(device["user_id"], f"device_revoked:{device_id}")
    return updated


def record_device_seen(
    vpn_uuid: str,
    source_ip: Optional[str] = None,
    seen_at: Optional[datetime] = None,
) -> bool:
    """Soft-bind device on first live use and update last seen metadata."""
    device = get_device_by_uuid(vpn_uuid)
    if not device:
        return False

    seen_at = seen_at or datetime.now()
    first_lock = not bool(device.get("first_seen_at"))
    first_seen = seen_at if first_lock else None
    updated = update_device(
        device["device_id"],
        first_seen_at=first_seen,
        last_seen_at=seen_at,
        last_handshake_at=seen_at,
        last_ip=source_ip if source_ip is not None else device.get("last_ip"),
    )
    if updated and first_lock:
        log_activity(device["user_id"], f"device_locked:{device['device_id']}")
    return updated


def record_device_seen_by_email(
    xray_email: str,
    source_ip: Optional[str] = None,
    seen_at: Optional[datetime] = None,
) -> bool:
    device = get_device_by_xray_email(xray_email)
    if not device:
        return False

    seen_at = seen_at or datetime.now()
    first_lock = not bool(device.get("first_seen_at"))
    first_seen = seen_at if first_lock else None
    updated = update_device(
        device["device_id"],
        first_seen_at=first_seen,
        last_seen_at=seen_at,
        last_handshake_at=seen_at,
        last_ip=source_ip if source_ip is not None else device.get("last_ip"),
    )
    if updated and first_lock:
        log_activity(device["user_id"], f"device_locked:{device['device_id']}")
    return updated


def ensure_legacy_primary_device(user_id: int) -> Optional[Dict]:
    """
    Backfill a single default device for existing users that still only have
    legacy users.vpn_uuid data.
    """
    user = get_user(user_id)
    if not user or not user.get("vpn_uuid"):
        return None

    existing = get_device_by_uuid(user["vpn_uuid"])
    if existing:
        return existing

    return create_device(
        user_id=user_id,
        device_name="Основное устройство",
        device_type="unknown",
        vpn_uuid=user["vpn_uuid"],
        xray_email=f"tg-{user_id}@x0tta6bl4",
        profile_kind="reality",
    )


def get_active_device_count(user_id: int) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS count FROM devices WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        row = cursor.fetchone()
        return int(row["count"]) if row else 0


def has_trial_claim(user_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM trial_claims WHERE user_id = ? LIMIT 1", (user_id,))
        return cursor.fetchone() is not None


def ensure_trial_claim(user_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO trial_claims (user_id)
            VALUES (?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        return cursor.rowcount > 0


def record_referral_open(referrer_user_id: int, referred_user_id: int) -> bool:
    if referrer_user_id == referred_user_id:
        return False

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO referrals (referrer_user_id, referred_user_id)
            VALUES (?, ?)
            ON CONFLICT(referred_user_id) DO NOTHING
            """,
            (referrer_user_id, referred_user_id),
        )
        inserted = cursor.rowcount > 0
        if inserted:
            cursor.execute(
                """
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
                """,
                (referred_user_id, f"referral_opened:{referrer_user_id}"),
            )
        return inserted


def mark_referral_paid(
    referred_user_id: int,
    amount: float,
    currency: str,
) -> Optional[int]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE referrals
            SET paid_at = COALESCE(paid_at, CURRENT_TIMESTAMP),
                first_payment_amount = COALESCE(first_payment_amount, ?),
                first_payment_currency = COALESCE(first_payment_currency, ?)
            WHERE referred_user_id = ? AND paid_at IS NULL
            """,
            (amount, currency, referred_user_id),
        )
        updated = cursor.rowcount > 0
        if updated:
            cursor.execute(
                "SELECT referrer_user_id FROM referrals WHERE referred_user_id = ?",
                (referred_user_id,),
            )
            row = cursor.fetchone()
            if row:
                referrer_user_id = int(row["referrer_user_id"])
                cursor.execute(
                    """
                    INSERT INTO activity_log (user_id, action)
                    VALUES (?, ?)
                    """,
                    (referrer_user_id, f"referral_paid:{referred_user_id}"),
                )
                return referrer_user_id
        return None


def mark_referral_trial_started(referred_user_id: int) -> Optional[int]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE referrals
            SET trial_bonus_awarded_at = COALESCE(trial_bonus_awarded_at, CURRENT_TIMESTAMP)
            WHERE referred_user_id = ? AND trial_bonus_awarded_at IS NULL
            """,
            (referred_user_id,),
        )
        updated = cursor.rowcount > 0
        if updated:
            cursor.execute(
                "SELECT referrer_user_id FROM referrals WHERE referred_user_id = ?",
                (referred_user_id,),
            )
            row = cursor.fetchone()
            if row:
                referrer_user_id = int(row["referrer_user_id"])
                cursor.execute(
                    """
                    INSERT INTO activity_log (user_id, action)
                    VALUES (?, ?)
                    """,
                    (referrer_user_id, f"referral_trial:{referred_user_id}"),
                )
                return referrer_user_id
        return None


def get_referral_summary(referrer_user_id: int) -> Dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS opens,
                SUM(CASE WHEN u.trial_used = 1 THEN 1 ELSE 0 END) AS trial,
                SUM(CASE WHEN paid_at IS NOT NULL THEN 1 ELSE 0 END) AS paid,
                SUM(COALESCE(first_payment_amount, 0)) AS revenue
            FROM referrals
            LEFT JOIN users u ON u.user_id = referrals.referred_user_id
            WHERE referrer_user_id = ?
            """,
            (referrer_user_id,),
        )
        row = cursor.fetchone()
        cursor.execute(
            """
            SELECT SUM(CASE WHEN action LIKE 'referral_bonus_%' THEN
                CAST(REPLACE(REPLACE(action, 'referral_bonus_', ''), 'd', '') AS INTEGER)
            ELSE 0 END) AS total_bonus_days
            FROM activity_log
            WHERE user_id = ?
            """,
            (referrer_user_id,),
        )
        bonus_row = cursor.fetchone()
        return {
            "opens": int(row["opens"] or 0),
            "trial": int(row["trial"] or 0),
            "paid": int(row["paid"] or 0),
            "revenue": float(row["revenue"] or 0),
            "bonus_days": int((bonus_row or {"total_bonus_days": 0})["total_bonus_days"] or 0),
        }


def get_recent_referral_rewards(referrer_user_id: int, limit: int = 5) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT referred_user_id, paid_at, first_payment_amount, first_payment_currency
            FROM referrals
            WHERE referrer_user_id = ? AND paid_at IS NOT NULL
            ORDER BY paid_at DESC
            LIMIT ?
            """,
            (referrer_user_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_referrals(limit: int = 10) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                r.referrer_user_id,
                ref.username AS referrer_username,
                r.referred_user_id,
                referred.username AS referred_username,
                r.opened_at,
                r.trial_bonus_awarded_at,
                r.paid_at,
                r.first_payment_amount,
                r.first_payment_currency
            FROM referrals r
            LEFT JOIN users ref ON ref.user_id = r.referrer_user_id
            LEFT JOIN users referred ON referred.user_id = r.referred_user_id
            ORDER BY COALESCE(r.paid_at, r.trial_bonus_awarded_at, r.opened_at) DESC, r.referral_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_global_referral_stats() -> Dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS opens,
                SUM(CASE WHEN u.trial_used = 1 THEN 1 ELSE 0 END) AS trial,
                SUM(CASE WHEN paid_at IS NOT NULL THEN 1 ELSE 0 END) AS paid,
                SUM(COALESCE(first_payment_amount, 0)) AS revenue
            FROM referrals
            LEFT JOIN users u ON u.user_id = referrals.referred_user_id
            """
        )
        row = cursor.fetchone()
        opens = int(row["opens"] or 0)
        trial = int(row["trial"] or 0)
        paid = int(row["paid"] or 0)
        revenue = float(row["revenue"] or 0)
        cursor.execute(
            """
            SELECT SUM(CASE WHEN action LIKE 'referral_bonus_%' THEN
                CAST(REPLACE(REPLACE(action, 'referral_bonus_', ''), 'd', '') AS INTEGER)
            ELSE 0 END) AS total_bonus_days
            FROM activity_log
            WHERE action LIKE 'referral_bonus_%'
            """
        )
        bonus_row = cursor.fetchone()
        return {
            "opens": opens,
            "trial": trial,
            "paid": paid,
            "revenue": revenue,
            "bonus_days": int((bonus_row or {"total_bonus_days": 0})["total_bonus_days"] or 0),
        }


def get_rate_limit_stats() -> Dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM activity_log
            WHERE action LIKE 'rate_limited:%'
            """
        )
        total = int((cursor.fetchone() or {"total": 0})["total"] or 0)

        cursor.execute(
            """
            SELECT
                REPLACE(action, 'rate_limited:', '') AS action_name,
                COUNT(*) AS hits
            FROM activity_log
            WHERE action LIKE 'rate_limited:%'
            GROUP BY action
            ORDER BY hits DESC, action_name ASC
            LIMIT 5
            """
        )
        top_actions = [dict(row) for row in cursor.fetchall()]
        return {
            "total": total,
            "top_actions": top_actions,
        }


def register_request_event(user_id: int, action: str) -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO request_events (user_id, action)
            VALUES (?, ?)
            """,
            (user_id, action),
        )
        cursor.execute(
            """
            DELETE FROM request_events
            WHERE created_at < datetime('now', '-1 day')
            """
        )


def count_recent_request_events(user_id: int, action: str, window_seconds: int) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM request_events
            WHERE user_id = ?
              AND action = ?
              AND created_at >= datetime('now', ?)
            """,
            (user_id, action, f"-{int(window_seconds)} seconds"),
        )
        row = cursor.fetchone()
        return int(row["cnt"] or 0)


def get_top_rate_limited_users(limit: int = 5) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                a.user_id,
                u.username,
                COUNT(*) AS hits
            FROM activity_log a
            LEFT JOIN users u ON u.user_id = a.user_id
            WHERE a.action LIKE 'rate_limited:%'
            GROUP BY a.user_id
            ORDER BY hits DESC, a.user_id ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_rate_limited_count(user_id: int, window_hours: int = 24) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM activity_log
            WHERE user_id = ?
              AND action LIKE 'rate_limited:%'
              AND timestamp >= datetime('now', ?)
            """,
            (user_id, f"-{int(window_hours)} hours"),
        )
        row = cursor.fetchone()
        return int(row["cnt"] or 0)


def get_suspicious_users(limit: int = 10, threshold: int = 10) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                a.user_id,
                u.username,
                COUNT(*) AS hits
            FROM activity_log a
            LEFT JOIN users u ON u.user_id = a.user_id
            WHERE a.action LIKE 'rate_limited:%'
              AND a.timestamp >= datetime('now', '-24 hours')
            GROUP BY a.user_id
            HAVING COUNT(*) >= ?
            ORDER BY hits DESC, a.user_id ASC
            LIMIT ?
            """,
            (threshold, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_top_referrers(limit: int = 5) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                referrer_user_id,
                u.username AS referrer_username,
                COUNT(*) AS opens,
                SUM(CASE WHEN paid_at IS NOT NULL THEN 1 ELSE 0 END) AS paid,
                SUM(COALESCE(first_payment_amount, 0)) AS revenue
            FROM referrals
            LEFT JOIN users u ON u.user_id = referrals.referrer_user_id
            GROUP BY referrer_user_id
            ORDER BY paid DESC, revenue DESC, opens DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def grant_referral_bonus_days(user_id: int, days: int, cap_days: Optional[int] = None) -> int:
    user = get_user(user_id)
    if not user:
        return 0

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT SUM(CASE WHEN action LIKE 'referral_bonus_%' THEN
                CAST(REPLACE(REPLACE(action, 'referral_bonus_', ''), 'd', '') AS INTEGER)
            ELSE 0 END) AS total_bonus_days
            FROM activity_log
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        current_bonus_days = int(row["total_bonus_days"] or 0)

    grant_days = days
    if cap_days is not None:
        remaining = max(cap_days - current_bonus_days, 0)
        grant_days = min(days, remaining)

    if grant_days <= 0:
        return 0

    now = datetime.now()
    current_expiry_raw = user.get("expires_at")
    current_expiry = None
    if current_expiry_raw:
        try:
            current_expiry = datetime.fromisoformat(current_expiry_raw)
        except ValueError:
            current_expiry = None

    base_time = current_expiry if current_expiry and current_expiry > now else now
    new_expiry = base_time + timedelta(days=grant_days)

    update_user(user_id, expires_at=new_expiry)
    log_activity(user_id, f"referral_bonus_{grant_days}d")
    return grant_days


def record_subscription_access(
    user_id: int,
    user_agent: str,
    ip_address: str | None = None,
    parsed: dict | None = None,
) -> dict | None:
    """Record subscription endpoint access. Returns access dict if this is a NEW device, else None."""

    def is_browserish(ua: str, client_app: str) -> bool:
        ua_lower = (ua or "").lower()
        if (client_app or "").strip():
            return False
        return (
            "mozilla/" in ua_lower
            or "applewebkit/" in ua_lower
            or "chrome/" in ua_lower
            or "safari/" in ua_lower
            or "wv)" in ua_lower
        )

    parsed = parsed or {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT access_id, notified FROM subscription_accesses WHERE user_id = ? AND user_agent = ?",
            (user_id, user_agent),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE subscription_accesses SET last_seen_at = CURRENT_TIMESTAMP, ip_address = ? WHERE access_id = ?",
                (ip_address, existing["access_id"]),
            )
            return None  # known device

        platform = (parsed.get("platform") or "").strip()
        client_app = (parsed.get("client_app") or "").strip()
        if platform and ip_address:
            cursor.execute(
                """
                SELECT access_id, user_agent, client_app
                FROM subscription_accesses
                WHERE user_id = ?
                  AND ip_address = ?
                  AND platform = ?
                  AND last_seen_at >= datetime('now', '-5 minutes')
                ORDER BY access_id DESC
                LIMIT 3
                """,
                (user_id, ip_address, platform),
            )
            recent_rows = cursor.fetchall()
            for row in recent_rows:
                existing_client_app = (row["client_app"] or "").strip()
                existing_ua = row["user_agent"] or ""
                existing_browserish = is_browserish(existing_ua, existing_client_app)
                new_browserish = is_browserish(user_agent, client_app)
                should_merge = (existing_browserish and client_app) or (
                    new_browserish and existing_client_app
                )
                if not should_merge:
                    continue
                cursor.execute(
                    """
                    UPDATE subscription_accesses
                    SET
                        user_agent = ?,
                        ip_address = ?,
                        client_app = ?,
                        client_version = ?,
                        platform = ?,
                        os_version = ?,
                        device_model = ?,
                        last_seen_at = CURRENT_TIMESTAMP
                    WHERE access_id = ?
                    """,
                    (
                        user_agent if client_app else existing_ua,
                        ip_address,
                        client_app or existing_client_app,
                        parsed.get("client_version", ""),
                        platform,
                        parsed.get("os_version", ""),
                        parsed.get("device_model", ""),
                        row["access_id"],
                    ),
                )
                return None

        cursor.execute(
            """
            INSERT INTO subscription_accesses
                (user_id, user_agent, ip_address, client_app, client_version, platform, os_version, device_model, notified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                user_id,
                user_agent,
                ip_address,
                parsed.get("client_app", ""),
                parsed.get("client_version", ""),
                parsed.get("platform", ""),
                parsed.get("os_version", ""),
                parsed.get("device_model", ""),
            ),
        )
        access_id = cursor.lastrowid
        cursor.execute(
            "SELECT * FROM subscription_accesses WHERE access_id = ?",
            (access_id,),
        )
        return dict(cursor.fetchone())


def mark_subscription_access_notified(access_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE subscription_accesses SET notified = 1 WHERE access_id = ?",
            (access_id,),
        )


def count_subscription_accesses(user_id: int) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM subscription_accesses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0


def get_subscription_accesses(user_id: int) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                access_id,
                user_id,
                user_agent,
                ip_address,
                client_app,
                client_version,
                platform,
                os_version,
                device_model,
                first_seen_at,
                last_seen_at,
                notified
            FROM subscription_accesses
            WHERE user_id = ?
            ORDER BY access_id
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


# --- Broadcast helpers ---


def get_broadcast_user_ids(audience: str = "all") -> list[int]:
    """Return user_ids for broadcast. audience: all, active, paid, trial, expired."""
    with get_db_connection() as conn:
        if audience == "active":
            rows = conn.execute(
                "SELECT id FROM users WHERE expires_at > datetime('now')"
            ).fetchall()
        elif audience == "paid":
            rows = conn.execute(
                "SELECT id FROM users WHERE expires_at > datetime('now') AND plan != 'trial'"
            ).fetchall()
        elif audience == "trial":
            rows = conn.execute(
                "SELECT id FROM users WHERE expires_at > datetime('now') AND plan = 'trial'"
            ).fetchall()
        elif audience == "expired":
            rows = conn.execute(
                "SELECT id FROM users WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"
            ).fetchall()
        else:  # all
            rows = conn.execute("SELECT id FROM users").fetchall()
        return [row["user_id"] for row in rows]


# --- Promo code helpers ---


def create_promo_code(
    code: str,
    promo_type: str = "days",
    value: int = 0,
    plan_key: str | None = None,
    max_uses: int = 1,
    expires_at: str | None = None,
) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO promo_codes (code, promo_type, value, plan_key, max_uses, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (code.strip(), promo_type, value, plan_key, max_uses, expires_at),
        )


def get_promo_code(code: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM promo_codes WHERE code = ?", (code.strip(),)).fetchone()
        return dict(row) if row else None


def redeem_promo_code(code: str, user_id: int) -> dict | None:
    """Try to redeem a promo code. Returns promo dict on success, None on failure."""
    promo = get_promo_code(code)
    if not promo:
        return None
    if promo["used_count"] >= promo["max_uses"]:
        return None
    if promo["expires_at"]:
        try:
            exp = datetime.strptime(promo["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp:
                return None
        except (ValueError, TypeError):
            pass
    with get_db_connection() as conn:
        # Check if user already redeemed
        existing = conn.execute(
            "SELECT 1 FROM promo_redemptions WHERE code = ? AND user_id = ?",
            (code.strip(), user_id),
        ).fetchone()
        if existing:
            return None
        conn.execute(
            "INSERT INTO promo_redemptions (code, user_id) VALUES (?, ?)",
            (code.strip(), user_id),
        )
        conn.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?",
            (code.strip(),),
        )
    return promo


def list_promo_codes() -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM promo_codes ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_promo_code(code: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM promo_codes WHERE code = ?", (code.strip(),))
        return cursor.rowcount > 0


def get_user_egress_mode(user_id: int) -> str:
    """Get user egress mode: direct or warp."""
    user = get_user(user_id)
    if not user:
        return "direct"
    mode = (user.get("egress_mode") or "direct").strip().lower()
    return mode if mode in {"direct", "warp"} else "direct"


def set_user_egress_mode(user_id: int, mode: str) -> bool:
    """Set user egress mode: direct or warp."""
    normalized = (mode or "").strip().lower()
    if normalized not in {"direct", "warp"}:
        return False
    return update_user(user_id, egress_mode=normalized)


def delete_user_account(user_id: int) -> dict:
    """Delete user account and anonymize payment history. Returns summary."""
    summary = {"devices_removed": 0, "activities_removed": 0, "payments_anonymized": 0}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Remove devices
        cursor.execute("SELECT COUNT(*) as cnt FROM devices WHERE user_id = ?", (user_id,))
        summary["devices_removed"] = cursor.fetchone()["cnt"]
        cursor.execute("DELETE FROM devices WHERE user_id = ?", (user_id,))
        # Remove subscription accesses
        cursor.execute("DELETE FROM subscription_accesses WHERE user_id = ?", (user_id,))
        # Remove activity log
        cursor.execute("SELECT COUNT(*) as cnt FROM activity_log WHERE user_id = ?", (user_id,))
        summary["activities_removed"] = cursor.fetchone()["cnt"]
        cursor.execute("DELETE FROM activity_log WHERE user_id = ?", (user_id,))
        # Remove request events
        cursor.execute("DELETE FROM request_events WHERE user_id = ?", (user_id,))
        # Remove referrals
        cursor.execute(
            "DELETE FROM referrals WHERE referrer_user_id = ? OR referred_user_id = ?",
            (user_id, user_id),
        )
        # Remove promo redemptions
        cursor.execute("DELETE FROM promo_redemptions WHERE user_id = ?", (user_id,))
        # Anonymize payments (keep for accounting, remove PII)
        cursor.execute("SELECT COUNT(*) as cnt FROM payments WHERE user_id = ?", (user_id,))
        summary["payments_anonymized"] = cursor.fetchone()["cnt"]
        cursor.execute(
            "UPDATE payments SET user_id = 0 WHERE user_id = ?",
            (user_id,),
        )
        # Delete user record
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    return summary


def is_webhook_processed(webhook_id: str, provider: str) -> bool:
    """Check if a webhook has already been processed for idempotency protection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_webhooks WHERE webhook_id = ? AND provider = ?",
            (webhook_id, provider),
        )
        return cursor.fetchone() is not None


def record_webhook_processed(webhook_id: str, provider: str, result: str = "success") -> bool:
    """Record a webhook as processed to prevent duplicate processing."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO processed_webhooks (webhook_id, provider, result)
                VALUES (?, ?, ?)
                """,
                (webhook_id, provider, result),
            )
            return True
    except Exception:
        # Duplicate key exception means already processed
        return False
