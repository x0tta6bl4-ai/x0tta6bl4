"""
FL Coordinator Singleton
========================

Глобальный доступ к FL Coordinator для использования в Telegram Bot и других компонентах.
"""

import logging
from typing import Optional

from .coordinator import CoordinatorConfig, FederatedCoordinator

logger = logging.getLogger(__name__)

# Global coordinator instance
_global_coordinator: Optional[FederatedCoordinator] = None


def get_fl_coordinator() -> FederatedCoordinator:
    """
    Get or create global FL Coordinator instance.

    Returns:
        FederatedCoordinator instance
    """
    global _global_coordinator

    if _global_coordinator is None:
        config = CoordinatorConfig(
            min_participants=5, target_participants=20, max_participants=100
        )
        _global_coordinator = FederatedCoordinator(
            coordinator_id="global-coordinator", config=config
        )
        logger.info("✅ Global FL Coordinator created")

    return _global_coordinator


async def initialize_fl_coordinator(config: Optional[CoordinatorConfig] = None):
    """Initialize global FL Coordinator with custom config."""
    global _global_coordinator

    if _global_coordinator is not None:
        logger.warning("FL Coordinator already initialized")
        return

    if config is None:
        config = CoordinatorConfig()

    _global_coordinator = FederatedCoordinator(
        coordinator_id="global-coordinator", config=config
    )

    logger.info("✅ FL Coordinator initialized")
