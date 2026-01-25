#!/usr/bin/env python3
"""
Проверка истекших подписок
Запускать через cron для автоматической проверки
"""

import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from database import get_active_users, get_user, update_user, log_activity
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    logger.error("Database module not available")


def check_expired_subscriptions():
    """Check and mark expired subscriptions"""
    if not MODULES_AVAILABLE:
        logger.error("Cannot check subscriptions: modules not available")
        return 0
    
    active_users = get_active_users()
    expired_count = 0
    
    for user in active_users:
        if not user.get('expires_at'):
            continue
        
        expires_at = datetime.fromisoformat(user['expires_at'])
        if datetime.now() >= expires_at:
            # Subscription expired
            user_id = user['user_id']
            logger.info(f"Subscription expired for user {user_id}")
            
            # Log activity
            log_activity(user_id, "subscription_expired")
            expired_count += 1
    
    if expired_count > 0:
        logger.info(f"Found {expired_count} expired subscriptions")
    else:
        logger.info("No expired subscriptions found")
    
    return expired_count


def check_expiring_soon(days: int = 7):
    """Check subscriptions expiring soon"""
    if not MODULES_AVAILABLE:
        return []
    
    active_users = get_active_users()
    expiring = []
    
    for user in active_users:
        if not user.get('expires_at'):
            continue
        
        expires_at = datetime.fromisoformat(user['expires_at'])
        days_left = (expires_at - datetime.now()).days
        
        if 0 < days_left <= days:
            expiring.append({
                'user_id': user['user_id'],
                'username': user.get('username'),
                'expires_at': expires_at,
                'days_left': days_left
            })
    
    return expiring


if __name__ == "__main__":
    expired = check_expired_subscriptions()
    expiring_soon = check_expiring_soon(7)
    
    if expiring_soon:
        logger.info(f"Subscriptions expiring in 7 days: {len(expiring_soon)}")
        for sub in expiring_soon:
            logger.info(f"  User {sub['user_id']} (@{sub.get('username', 'N/A')}) - {sub['days_left']} days left")
    
    sys.exit(0 if expired == 0 else 1)

