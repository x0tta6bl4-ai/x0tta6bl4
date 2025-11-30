#!/usr/bin/env python3
"""
Rate limiter для x0tta6bl4 Telegram Bot
Защита от спама и злоупотреблений
"""

import time
import logging
from typing import Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMITS = {
    'trial': {'count': 1, 'window': timedelta(days=365)},  # 1 trial per year
    'config': {'count': 10, 'window': timedelta(hours=1)},  # 10 configs per hour
    'subscribe': {'count': 5, 'window': timedelta(hours=1)},  # 5 subscribe attempts per hour
    'general': {'count': 20, 'window': timedelta(minutes=1)},  # 20 messages per minute
}

# Storage for rate limits
_rate_limit_storage: Dict[int, Dict[str, list]] = defaultdict(lambda: defaultdict(list))


def check_rate_limit(user_id: int, action: str) -> Tuple[bool, Optional[str]]:
    """
    Check if user exceeded rate limit for action
    
    Args:
        user_id: Telegram user ID
        action: Action name (trial, config, subscribe, general)
    
    Returns:
        (allowed, error_message)
    """
    if action not in RATE_LIMITS:
        return True, None
    
    limit = RATE_LIMITS[action]
    now = datetime.now()
    window_start = now - limit['window']
    
    # Get user's action history
    user_actions = _rate_limit_storage[user_id][action]
    
    # Remove old entries
    user_actions[:] = [ts for ts in user_actions if ts > window_start]
    
    # Check limit
    if len(user_actions) >= limit['count']:
        remaining = (user_actions[0] + limit['window'] - now).total_seconds()
        if remaining > 0:
            minutes = int(remaining / 60)
            return False, f"Слишком много запросов. Попробуй через {minutes} минут."
    
    # Record action
    user_actions.append(now)
    
    return True, None


def reset_rate_limit(user_id: int, action: Optional[str] = None):
    """Reset rate limit for user (admin function)"""
    if action:
        _rate_limit_storage[user_id][action].clear()
    else:
        _rate_limit_storage[user_id].clear()
    logger.info(f"Rate limit reset for user {user_id}, action: {action or 'all'}")


def get_rate_limit_info(user_id: int, action: str) -> Dict:
    """Get rate limit info for user"""
    if action not in RATE_LIMITS:
        return {}
    
    limit = RATE_LIMITS[action]
    now = datetime.now()
    window_start = now - limit['window']
    
    user_actions = _rate_limit_storage[user_id][action]
    user_actions[:] = [ts for ts in user_actions if ts > window_start]
    
    return {
        'used': len(user_actions),
        'limit': limit['count'],
        'remaining': limit['count'] - len(user_actions),
        'window': limit['window'].total_seconds()
    }

