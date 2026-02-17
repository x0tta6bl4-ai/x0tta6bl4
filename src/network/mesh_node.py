"""
Shim for backward compatibility.
The Mesh Node logic has been moved to libx0t.network.mesh_node.
"""
from src.libx0t.network.mesh_node import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.network.mesh_node is moved to libx0t.network.mesh_node. Please update your imports.")
