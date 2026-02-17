"""
Shim for backward compatibility.
The PQC tunnel logic has been moved to libx0t.network.pqc_tunnel.
"""
from src.libx0t.network.pqc_tunnel import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.network.pqc_tunnel is moved to libx0t.network.pqc_tunnel. Please update your imports.")
