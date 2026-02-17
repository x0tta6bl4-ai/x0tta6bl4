"""
Shim for backward compatibility.
The PQC mTLS logic has been moved to libx0t.security.pqc_mtls.
"""
from src.libx0t.security.pqc_mtls import *
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.security.pqc_mtls is moved to libx0t.security.pqc_mtls. Please update your imports.")
