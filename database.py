#!/usr/bin/env python3
"""
Database module для x0tta6bl4 Telegram Bot
Использует SQLite для хранения пользователей
"""

import sqlite3
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = "x0tta6bl4_users.db"


@contextmanager
def get_db_connection():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
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
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Activity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        logger.info("Database initialized")


def get_user(user_id: int) -> Optional[Dict]:
    """Get user by user_id"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def create_user(
    user_id: int,
    username: Optional[str] = None,
    plan: str = "trial",
    expires_at: Optional[datetime] = None,
    vpn_uuid: Optional[str] = None
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
        
        cursor.execute("""
            INSERT INTO users (user_id, username, plan, expires_at, vpn_uuid, trial_used)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            username,
            plan,
            expires_at.isoformat() if expires_at else None,
            vpn_uuid,
            plan == "trial"
        ))
        
        # Log activity
        log_activity(user_id, "user_created")
        
        logger.info(f"User {user_id} created with plan {plan}")
        return get_user(user_id)


def update_user(
    user_id: int,
    plan: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    vpn_uuid: Optional[str] = None,
    vpn_config: Optional[str] = None
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
        
        if not updates:
            return False
        
        updates.append("last_activity = ?")
        params.append(datetime.now().isoformat())
        params.append(user_id)
        
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
            params
        )
        
        return cursor.rowcount > 0


def is_user_active(user_id: int) -> bool:
    """Check if user has active subscription"""
    user = get_user(user_id)
    if not user or not user.get('expires_at'):
        return False
    
    expires_at = datetime.fromisoformat(user['expires_at'])
    return datetime.now() < expires_at


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
        cursor.execute("""
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        """, (user_id, action))


def record_payment(
    user_id: int,
    amount: float,
    currency: str,
    provider: str = "telegram",
    status: str = "completed"
):
    """Record payment"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO payments (user_id, amount, currency, payment_provider, payment_status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, currency, provider, status))
        
        log_activity(user_id, f"payment_{status}")


def get_user_stats() -> Dict:
    """Get statistics about users"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Active users
        cursor.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE expires_at > datetime('now')
        """)
        active_users = cursor.fetchone()['count']
        
        # Trial users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE plan = 'trial'")
        trial_users = cursor.fetchone()['count']
        
        # Pro users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE plan = 'pro'")
        pro_users = cursor.fetchone()['count']
        
        # Total revenue
        cursor.execute("""
            SELECT SUM(amount) as total FROM payments 
            WHERE payment_status = 'completed'
        """)
        total_revenue = cursor.fetchone()['total'] or 0
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'trial_users': trial_users,
            'pro_users': pro_users,
            'total_revenue': total_revenue
        }

