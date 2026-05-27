"""
Recovery Actions for MAPE-K - Data Models
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RecoveryActionType:
    """Types of recovery actions"""

    RESTART_SERVICE = "restart_service"
    SWITCH_ROUTE = "switch_route"
    CLEAR_CACHE = "clear_cache"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    FAILOVER = "failover"
    QUARANTINE_NODE = "quarantine_node"
    EXECUTE_SCRIPT = "execute_script"
    SWITCH_PROTOCOL = "switch_protocol"
    NO_ACTION = "no_action"


@dataclass
class RecoveryResult:
    """Result of a recovery action"""

    success: bool
    action_type: str
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class CircuitBreakerState:
    """Circuit breaker state"""

    failures: int = 0
    successes: int = 0
    state: str = "closed"  # "closed", "open", "half_open"
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None


import time  # noqa: E402
