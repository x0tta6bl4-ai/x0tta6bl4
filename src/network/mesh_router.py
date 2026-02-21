"""
Shim for backward compatibility.
The Mesh Router logic has been moved to libx0t.network.mesh_router.
"""
from src.libx0t.network.mesh_router import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.network.mesh_router is moved to libx0t.network.mesh_router. Please update your imports.")
