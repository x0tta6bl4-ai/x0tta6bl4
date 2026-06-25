"""
src.core.app — Application bootstrapping and lifecycle.

Re-exports:
    from src.core.app.app import (create_app, ...)
    from src.core.app.production_lifespan import production_lifespan
    from src.core.app.graceful_shutdown import shutdown_manager, ...
    from src.core.app.app_bootstrap import app_bootstrap
"""

from src.core.app.app import create_app
from src.core.app.app_bootstrap import app_bootstrap
from src.core.app.graceful_shutdown import ShutdownMiddleware, shutdown_manager
from src.core.app.production_lifespan import production_lifespan

__all__ = [
    "create_app",
    "production_lifespan",
    "ShutdownMiddleware",
    "shutdown_manager",
    "app_bootstrap",
]
