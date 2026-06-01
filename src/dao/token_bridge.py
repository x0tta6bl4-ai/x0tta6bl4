"""
X0T Token Bridge Shim - Backward compatibility for v4.0 architecture.
Redirects to src.dao.bridge package.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .bridge.core import (
    EpochRewardScheduler,
    TokenBridge,
    WEB3_AVAILABLE,
    Web3,
)
from .bridge.types import (
    BridgeConfig,
    BridgeDirection,
    BridgeTransaction,
    TOKEN_BRIDGE_CLAIM_BOUNDARY,
    TOKEN_BRIDGE_CHAIN_READ_CLAIM_BOUNDARY,
)

logger = logging.getLogger(__name__)

# Re-exports for backward compatibility
__all__ = [
    "TokenBridge",
    "EpochRewardScheduler",
    "BridgeConfig",
    "BridgeDirection",
    "BridgeTransaction",
    "TOKEN_BRIDGE_CLAIM_BOUNDARY",
    "TOKEN_BRIDGE_CHAIN_READ_CLAIM_BOUNDARY",
    "WEB3_AVAILABLE",
    "Web3",
]

if TYPE_CHECKING:
    from src.dao.token import MeshToken
