"""
src.core.app — Application bootstrapping and lifecycle.

Re-exports:
    from src.core.app.app import (create_app, ...)
    from src.core.app.production_lifespan import production_lifespan
    from src.core.app.graceful_shutdown import shutdown_manager, ...
    from src.core.app.app_bootstrap import app_bootstrap
"""
from __future__ import annotations

from src.core.app.app import (
    app,
    BeaconRequest,
    _beacons,
    _peers,
    _generate_training_data,
    _get_simulated_features,
    pqc_verify,
    get_mesh_peers,
    get_mesh_routes,
    get_mesh_status,
    receive_beacon,
    health,
    health_live,
    health_ready,
    metrics,
)
from src.core.app.app_bootstrap import app as app_bootstrap
from src.core.app.graceful_shutdown import ShutdownMiddleware, shutdown_manager
from src.core.app.production_lifespan import production_lifespan

__all__ = [
    "app",
    "BeaconRequest",
    "_beacons",
    "_peers",
    "_generate_training_data",
    "_get_simulated_features",
    "pqc_verify",
    "get_mesh_peers",
    "get_mesh_routes",
    "get_mesh_status",
    "receive_beacon",
    "health",
    "health_live",
    "health_ready",
    "metrics",
    "production_lifespan",
    "ShutdownMiddleware",
    "shutdown_manager",
    "app_bootstrap",
]

