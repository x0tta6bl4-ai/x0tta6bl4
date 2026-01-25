#!/usr/bin/env python3
"""
Admin commands для x0tta6bl4 Telegram Bot
Расширенные функции для администратора
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from database import (
        get_user, get_active_users, get_user_stats,
        log_activity, update_user
    )
    from vpn_config_generator import generate_vless_link
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    logger.warning("Admin commands modules not available")


def is_admin(user_id: int) -> bool:
    """Check if user is admin with logging (SECURITY FIX)"""
    # ✅ SECURITY FIX: Support multiple admins via comma-separated list
    admin_ids_str = os.getenv("ADMIN_USER_IDS", os.getenv("ADMIN_USER_ID", ""))
    
    if not admin_ids_str:
        logger.warning("⚠️ ADMIN_USER_IDS not set! No admins configured.")
        return False
    
    # Parse comma-separated admin IDs
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    is_admin_user = user_id in admin_ids
    
    # ✅ SECURITY FIX: Log all admin access attempts
    if not is_admin_user:
        logger.warning(f"🚨 Unauthorized admin access attempt by user {user_id}")
        if MODULES_AVAILABLE:
            log_activity(user_id, "admin_access_denied")
    else:
        logger.info(f"✅ Admin access granted to user {user_id}")
    
    return is_admin_user


def format_user_info(user: Dict) -> str:
    """Format user info for admin"""
    if not user:
        return "User not found"
    
    info = f"**User ID:** {user['user_id']}\n"
    info += f"**Username:** @{user.get('username', 'N/A')}\n"
    info += f"**Plan:** {user.get('plan', 'N/A')}\n"
    
    if user.get('expires_at'):
        expires_at = datetime.fromisoformat(user['expires_at'])
        days_left = (expires_at - datetime.now()).days
        info += f"**Expires:** {expires_at.strftime('%d.%m.%Y')} ({days_left} days left)\n"
    else:
        info += "**Expires:** N/A\n"
    
    if user.get('trial_used'):
        info += "**Trial:** Used ✅\n"
    else:
        info += "**Trial:** Available\n"
    
    if user.get('vpn_uuid'):
        info += f"**VPN UUID:** `{user['vpn_uuid']}`\n"
    
    if user.get('payment_amount'):
        info += f"**Payment:** ${user['payment_amount']:.2f} {user.get('payment_currency', 'USD')}\n"
    
    info += f"**Created:** {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y %H:%M')}\n"
    info += f"**Last Activity:** {datetime.fromisoformat(user.get('last_activity', user['created_at'])).strftime('%d.%m.%Y %H:%M')}"
    
    return info


def get_admin_stats() -> str:
    """Get detailed admin statistics"""
    if not MODULES_AVAILABLE:
        return "Statistics not available"
    
    stats = get_user_stats()
    active_users = get_active_users()
    
    text = "**📊 Admin Statistics**\n\n"
    text += f"**Total Users:** {stats['total_users']}\n"
    text += f"**Active Users:** {stats['active_users']}\n"
    text += f"**Trial Users:** {stats['trial_users']}\n"
    text += f"**Pro Users:** {stats['pro_users']}\n"
    text += f"**Total Revenue:** ${stats['total_revenue']:.2f}\n\n"
    
    # Expiring soon (within 7 days)
    expiring_soon = []
    for user in active_users:
        if user.get('expires_at'):
            expires_at = datetime.fromisoformat(user['expires_at'])
            days_left = (expires_at - datetime.now()).days
            if 0 < days_left <= 7:
                expiring_soon.append((user, days_left))
    
    if expiring_soon:
        text += f"**⚠️ Expiring Soon (≤7 days):** {len(expiring_soon)}\n"
        for user, days in expiring_soon[:5]:  # Show first 5
            text += f"  • User {user['user_id']} (@{user.get('username', 'N/A')}) - {days} days\n"
    
    return text


def get_user_list(limit: int = 20) -> List[Dict]:
    """Get list of users"""
    if not MODULES_AVAILABLE:
        return []
    
    active_users = get_active_users()
    return active_users[:limit]


def extend_user_subscription(user_id: int, days: int) -> bool:
    """Extend user subscription by days"""
    if not MODULES_AVAILABLE:
        return False
    
    user = get_user(user_id)
    if not user:
        return False
    
    if user.get('expires_at'):
        current_expires = datetime.fromisoformat(user['expires_at'])
        new_expires = current_expires + timedelta(days=days)
    else:
        new_expires = datetime.now() + timedelta(days=days)
    
    update_user(user_id, expires_at=new_expires)
    log_activity(user_id, f"subscription_extended_{days}_days")
    
    return True


def revoke_user_access(user_id: int) -> bool:
    """Revoke user access (set expires_at to past)"""
    if not MODULES_AVAILABLE:
        return False
    
    past_date = datetime.now() - timedelta(days=1)
    update_user(user_id, expires_at=past_date)
    log_activity(user_id, "access_revoked")
    
    return True

