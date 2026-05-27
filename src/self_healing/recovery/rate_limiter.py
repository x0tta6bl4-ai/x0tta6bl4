"""
Recovery Actions for MAPE-K
"""
import logging
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Self-healing recovery action event only. It records local policy, safety, "
    "and execution decisions and does not prove production rollout or live "
    "operator-approved remediation by itself."
)



class RateLimiter:
    """
    Rate limiter for recovery actions.

    Prevents too many actions from being executed in a short time.
    """

    def __init__(self, max_actions: int = 10, window_seconds: int = 60):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self.action_times: deque = deque()

    def allow(self) -> bool:
        """
        Check if action is allowed.

        Returns:
            True if action is allowed
        """
        now = datetime.now()

        # Remove old actions outside window
        while (
            self.action_times
            and (now - self.action_times[0]).total_seconds() > self.window_seconds
        ):
            self.action_times.popleft()

        # Check if limit exceeded
        if len(self.action_times) >= self.max_actions:
            logger.warning(
                f"Rate limit exceeded: {len(self.action_times)}/{self.max_actions} actions in {self.window_seconds}s"
            )
            return False

        # Record action
        self.action_times.append(now)
        return True
