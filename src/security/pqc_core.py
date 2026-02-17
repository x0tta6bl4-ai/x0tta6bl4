"""
Shim for backward compatibility. 
The core PQC logic has been moved to libx0t.security.pqc_core.
"""
from src.libx0t.security.pqc_core import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.security.pqc_core is moved to libx0t.security.pqc_core. Please update your imports.")
