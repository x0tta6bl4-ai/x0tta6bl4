"""
Shim for backward compatibility.
The post-quantum security logic has been moved to libx0t.security.post_quantum.
"""
from src.libx0t.security.post_quantum import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.security.post_quantum is moved to libx0t.security.post_quantum. Please update your imports.")
